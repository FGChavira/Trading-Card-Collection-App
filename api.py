import requests
import os
from dotenv import load_dotenv

import db as db

load_dotenv()

POKEMON_TCG_BASE_URL = "https://api.pokemontcg.io/v2"


def _pokemon_api_headers() -> dict:
    """
    Build auth headers for the PokemonTCG API.

    Returns:
        dict: Dictionary containing API key header or empty dict if no key was configured.
    """
    api_key = os.getenv("POKEMON_TCG_API_KEY")
    return {"X-Api-Key": api_key} if api_key else {}


def search_pokemon_card(
    search_term: str, set_code: str = "", id_in_set: str = ""
) -> dict | None:
    """
    Search for Pokemon card using PokemonTCG API and prompts user to select one.

    Args:
        search_term (str): The name of the card to search for.
        set_code (str): Optional card's set name.
        id_in_set (str): Optional card's number within the set.

    Returns:
        dict | None: Dictionary containing card details (name, set_code, id_in_set, rarity,
                     description, card_type). Or None if no card is found.
    """

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sets.name
                FROM sets
                WHERE sets.set_code = %s
                """,
                (set_code,),
            )
            record = cur.fetchone()
            set_name = record[0] if record else ""

    q_parts = [f'name:"{search_term}"']
    if set_name:
        q_parts.append(f'set.name:"{set_name}"')
    if id_in_set:
        q_parts.append(f"number:{id_in_set}")

    try:
        # Make an HTTP GET request to the PokemonTCG API
        resp = requests.get(
            f"{POKEMON_TCG_BASE_URL}/cards",
            params={"q": " ".join(q_parts), "pageSize": 100},
            headers=_pokemon_api_headers(),
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"API search failed: {e}")
        return None

    cards = resp.json().get("data", [])

    if not cards:
        print("No cards found.")
        return None

    if len(cards) == 1:
        selected = cards[0]
    else:
        print(f"\nFound {len(cards)} result(s):")
        for i, card in enumerate(cards, 1):
            display_set = card.get("set", {}).get("name", "Unknown")
            print(
                f"{i}. {card['name']} | {display_set} | #{card['number']} | {card.get('rarity', 'N/A')}"
            )

        choice = input("\nSelect a card number (0 to enter manually): ").strip()
        if not choice.isdigit() or int(choice) == 0 or int(choice) > len(cards):
            return None
        selected = cards[int(choice) - 1]

    card_type = selected.get("types") or selected.get("subtypes", [])
    if isinstance(card_type, list):
        card_type = "/".join(card_type)

    api_set_name = selected.get("set", {}).get("name", "")

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sets.set_code
                FROM sets
                WHERE sets.name = %s
                """,
                (api_set_name,),
            )
            record = cur.fetchone()
            if record:
                set_code = record[0]
            else:
                set_code = api_set_name
                print(f"\tWatning: Set '{api_set_name}' not found in your sets table.")

    return {
        "name": selected["name"],
        "set_code": set_code,
        "id_in_set": selected["number"],
        "rarity": selected.get("rarity", ""),
        "description": selected.get("flavorText", ""),
        "card_type": card_type,
    }


def enrich_pokemon_cards():
    """
    Update existing Pokemon card details using PokemonTCG API.
    Iterates tcg_cards and searches the API for each one updating the details.
    """
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, set_code, id_in_set
                FROM tcg_cards 
                WHERE LOWER(category) = 'pokemon'
                AND description IS NULL
                ORDER BY id
                """
            )
            records = cur.fetchall()

    if not records:
        print("No Pokemon cards found in the database.")
        return

    print(f"\nFound {len(records)} Pokemon card(s) to enrich.")
    updated = 0

    for record_id, name, set_code, id_in_set in records:
        print(f"\n--- {name} | Set: {set_code} | #{id_in_set} ---")
        api_data = search_pokemon_card(name, set_code=set_code, id_in_set=id_in_set)
        if not api_data:
            print("Skipping.")
            continue

        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE tcg_cards
                        SET name = %s, set_code = %s, id_in_set = %s,
                            rarity = %s, description = %s, card_type = %s
                        WHERE id = %s
                        """,
                        (
                            api_data["name"],
                            api_data["set_code"],
                            api_data["id_in_set"],
                            api_data["rarity"],
                            api_data["description"],
                            api_data["card_type"],
                            record_id,
                        ),
                    )
                    conn.commit()
            print(
                f"Updated: {api_data['name']} ({api_data['set_code']} #{api_data['id_in_set']})"
            )
            updated += 1
        except Exception as e:
            print(f"Could not update record {record_id}: {e}")

    print(f"\nEnrichment complete. {updated}/{len(records)} card(s) updated.")
