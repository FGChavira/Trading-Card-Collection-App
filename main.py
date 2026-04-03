import psycopg2
import requests
import csv
import os
from dotenv import load_dotenv

load_dotenv()

POKEMON_TCG_BASE_URL = "https://api.pokemontcg.io/v2"

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "card_collection"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}


def get_connection():
    """
    Connect to database using DB_CONFIG parameters.
    """
    return psycopg2.connect(**DB_CONFIG)


def _pokemon_api_headers() -> dict:
    """
    Build auth headers for the PokemonTCG API.

    Returns:
        dict: Dictionary containing API key header or empty dict if no key was configured.
    """
    api_key = os.getenv("POKEMON_TCG_API_KEY")
    return {"X-Api-Key": api_key} if api_key else {}


def search_pokemon_card(
    search_term: str, set_id: str = "", id_in_set: str = ""
) -> dict | None:
    """
    Search for Pokemon card using PokemonTCG API and prompts user to select one.

    Args:
        search_term (str): The name of the card to search for.
        set_id (str): Optional card's set name.
        id_in_set (str): Optional card's number within the set.

    Returns:
        dict | None: Dictionary containing card details (name, set_id, id_in_set, rarity,
                     description, card_type). Or None if no card is found.
    """
    q_parts = [f'name:"{search_term}"']
    if set_id:
        q_parts.append(f'set.name:"{set_id}"')
    if id_in_set:
        q_parts.append(f"number:{id_in_set}")

    try:
        # Make an HTTP GET request to the PokemonTCG API
        resp = requests.get(
            f"{POKEMON_TCG_BASE_URL}/cards",
            params={"q": " ".join(q_parts), "pageSize": 20},
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
            set_name = card.get("set", {}).get("name", "Unknown")
            print(
                f"{i}. {card['name']} | {set_name} | #{card['number']} | {card.get('rarity', 'N/A')}"
            )

        choice = input("\nSelect a card number (0 to enter manually): ").strip()
        if not choice.isdigit() or int(choice) == 0 or int(choice) > len(cards):
            return None
        selected = cards[int(choice) - 1]

    card_type = selected.get("types") or selected.get("subtypes", [])
    if isinstance(card_type, list):
        card_type = "/".join(card_type)

    return {
        "name": selected["name"],
        "set_id": selected.get("set", {}).get("name", ""),
        "id_in_set": selected["number"],
        "rarity": selected.get("rarity", ""),
        "description": selected.get("flavorText", ""),
        "card_type": card_type,
    }


def init_db():
    """
    Create necessary tables.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tcg_cards (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        id_in_set TEXT NOT NULL,
                        description TEXT,
                        card_type TEXT,
                        rarity TEXT,
                        set_id TEXT,
                        condition TEXT,
                        variant TEXT DEFAULT 'Standard',
                        quantity INTEGER DEFAULT 1,
                        acquired_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        grade TEXT DEFAULT 'N/A',
                        grading_company TEXT DEFAULT 'N/A',
                        CONSTRAINT unique_tcg_card UNIQUE (category, set_id, id_in_set, variant)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sports_cards (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        players_featured TEXT NOT NULL,
                        sport TEXT NOT NULL,
                        id_in_set TEXT,
                        rarity TEXT,
                        rookie BOOLEAN DEFAULT FALSE,
                        team_name TEXT NOT NULL,
                        set_code TEXT NOT NULL,
                        condition TEXT DEFAULT 'Near Mint',
                        parallel TEXT DEFAULT 'Base',
                        card_type TEXT DEFAULT 'player',
                        quantity INTEGER DEFAULT 1,
                        acquired_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        grade TEXT DEFAULT 'N/A',
                        grading_company TEXT DEFAULT 'N/A',
                        CONSTRAINT unique_sports_card UNIQUE (sport, set_code, id_in_set, parallel)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS collector_cards (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        id_in_set TEXT,
                        description TEXT,
                        rarity TEXT,
                        set_code TEXT NOT NULL,
                        condition TEXT DEFAULT 'Near Mint',
                        variant TEXT DEFAULT 'Standard',
                        quantity INTEGER DEFAULT 1,
                        acquired_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        grade TEXT DEFAULT 'N/A',
                        grading_company TEXT DEFAULT 'N/A',
                        CONSTRAINT unique_collector_card UNIQUE (category, set_code, id_in_set, variant)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sets (
                        id SERIAL,
                        set_code TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        series TEXT DEFAULT 'N/A',
                        manufacturer TEXT,
                        release_date DATE,
                        total_cards INTEGER
                    )
                    """
                )
                conn.commit()
                print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")


def add_card():
    """
    Add individual card using details provided by user input.

    Use the API, if applicable user can provide manual details. Calls
    save_tcg_card() or save_sports_card() to insert records accordingly.
    """
    print("\nAdd Card Menu")
    print("1. TCG Card (Pokemon, One Piece)")
    print("2. Sports Card (Baseball, Football, Basketball)")
    print("3. Collector Card (Hazbin Hotel, etc.)")
    print("4. Back to menu")

    choice = input("Select a value from the menu: ")
    if choice == "1":
        category = input("Category (e.g. Pokemon, One Piece): ")

        api_data = None
        if category.lower() == "pokemon":
            api_data = search_pokemon_card(input("Card name to search: "))

        if api_data:
            name = api_data["name"]
            id_in_set = api_data["id_in_set"]
            description = api_data["description"]
            card_type = api_data["card_type"]
            set_id = api_data["set_id"]
            rarity = api_data["rarity"]
            print(f"\nPre-filled from API:")
            print(f"  Name:       {name}")
            print(f"  Set:        {set_id}")
            print(f"  ID in Set:  {id_in_set}")
            print(f"  Rarity:     {rarity}")
            print(f"  Type:       {card_type}")
        else:
            name = input("Card Name: ")
            id_in_set = input("ID in Set: ")
            description = input("Card description (can leave blank): ")
            card_type = input("Type (can leave blank): ")
            set_id = input("Set: ")
            rarity = input("Rarity: ")

        variant = input("Variant: ") or "Standard"
        grade = input("Grade (leave blank for N/A): ") or "N/A"
        grading_company = input("Grading Company (leave blank for N/A): ") or "N/A"
        quantity = int(input("Quantity: ") or 1)
        save_tcg_card(
            name,
            category,
            id_in_set,
            description,
            card_type,
            set_id,
            rarity,
            variant,
            grade,
            grading_company,
            quantity,
        )
    elif choice == "2":
        name = input("Card Name: ")
        players_featured = input("Featured Player(s): ") or name
        sport = input("Sport (e.g. Baseball, Basketball): ")
        id_in_set = input("ID in Set: ")
        set_code = input("Set Code (2025-TOPPS-S1, etc.): ")
        team_name = input("Team Name: ")
        rookie = input("Is this a rookie card? (y/n): ").lower() == "y"
        rarity = input("Rarity: ") or "Common"
        parallel = input("Parallel: ") or "Base"
        card_type = input("Card Type (Player, Team, Event): ") or "Player"
        grade = input("Grade (leave blank for N/A): ") or "N/A"
        grading_company = input("Grading Company (leave blank for N/A): ") or "N/A"
        quantity = int(input("Quantity: ") or 1)
        save_sports_card(
            name,
            players_featured,
            sport,
            id_in_set,
            set_code,
            team_name,
            rookie,
            rarity,
            parallel,
            card_type,
            grade,
            grading_company,
            quantity,
        )
    elif choice == "3":
        category = input("Category (e.g. Hazbin Hotel): ")
        name = input("Card Name: ")
        id_in_set = input("ID in Set: ")
        description = input("Card Description (can leave blank): ")
        set_code = input("Set Code (HAZBIN-01, etc.): ")
        rarity = input("Rarity: ") or "Common"
        variant = input("Variant: ") or "Standard"
        grade = input("Grade (leave blank for N/A): ") or "N/A"
        grading_company = input("Grading Company (leave blank for N/A): ") or "N/A"
        quantity = input("Quantity: ") or 1
        save_collector_card(
            name,
            category,
            id_in_set,
            description,
            set_code,
            rarity,
            variant,
            grade,
            grading_company,
            quantity,
        )


def bulk_import_tcg(file_path: str):
    """
    Bulk import TCG cards into tcg_cards table using user provided .csv file.

    Args:
        file_path (str): File path to user provided .csv file containing card data.
    """
    with open(file_path, mode="r", encoding="utf-8-sig") as bulk_file:
        reader = csv.DictReader(bulk_file)
        with get_connection() as conn:
            with conn.cursor() as cur:
                for record in reader:
                    cur.execute(
                        """
                        INSERT INTO tcg_cards (name, category, id_in_set, rarity, set_id, quantity, variant, grade, grading_company)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (category, set_id, id_in_set, variant)
                        DO UPDATE SET
                            quantity = tcg_cards.quantity + EXCLUDED.quantity;
                        """,
                        (
                            record["name"],
                            record["category"],
                            record["id_in_set"],
                            record["rarity"],
                            record["set_id"],
                            record.get("quantity") or 1,
                            record["variant"],
                            record.get("grade") or "N/A",
                            record.get("grading_company") or "N/A",
                        ),
                    )
                conn.commit()
    print("Bulk cards have been imported.")


def bulk_import_sports(file_path):
    """
    Bulk import sports cards into sports_cards table using user provided .csv file.

    Args:
        file_path (str): File path to user provided .csv file containing card data.
    """
    with open(file_path, mode="r", encoding="utf-8-sig") as bulk_file:
        reader = csv.DictReader(bulk_file)
        with get_connection() as conn:
            with conn.cursor() as cur:
                for record in reader:
                    cur.execute(
                        """
                        INSERT INTO sports_cards (name, players_featured, rookie, team_name, sport, id_in_set, rarity, set_code, quantity, parallel, card_type, grade, grading_company)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (sport, set_code, id_in_set, parallel)
                        DO UPDATE SET
                            quantity = sports_cards.quantity + EXCLUDED.quantity;
                        """,
                        (
                            record["name"],
                            record["players_featured"],
                            record["rookie"],
                            record["team_name"],
                            record["sport"],
                            record["id_in_set"],
                            record["rarity"],
                            record["set_code"],
                            record.get("quantity") or 1,
                            record["parallel"],
                            record["card_type"],
                            record.get("grade") or "N/A",
                            record.get("grading_company") or "N/A",
                        ),
                    )
                conn.commit()
    print("Bulk cards have been imported.")


def enrich_pokemon_cards():
    """
    Update existing Pokemon card details using PokemonTCG API.
    Iterates tcg_cards and searches the API for each one updating the details.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, set_id, id_in_set
                FROM tcg_cards 
                WHERE LOWER(category) = 'pokemon'
                ORDER BY id
                """
            )
            records = cur.fetchall()

    if not records:
        print("No Pokemon cards found in the database.")
        return

    print(f"\nFound {len(records)} Pokemon card(s) to enrich.")
    updated = 0

    for record_id, name, set_id, id_in_set in records:
        print(f"\n--- {name} | Set: {set_id} | #{id_in_set} ---")
        api_data = search_pokemon_card(name, set_id=set_id, id_in_set=id_in_set)
        if not api_data:
            print("Skipping.")
            continue

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE tcg_cards
                        SET name = %s, set_id = %s, id_in_set = %s,
                            rarity = %s, description = %s, card_type = %s
                        WHERE id = %s
                        """,
                        (
                            api_data["name"],
                            api_data["set_id"],
                            api_data["id_in_set"],
                            api_data["rarity"],
                            api_data["description"],
                            api_data["card_type"],
                            record_id,
                        ),
                    )
                    conn.commit()
            print(
                f"Updated: {api_data['name']} ({api_data['set_id']} #{api_data['id_in_set']})"
            )
            updated += 1
        except Exception as e:
            print(f"Could not update record {record_id}: {e}")

    print(f"\nEnrichment complete. {updated}/{len(records)} card(s) updated.")


def display_card(search: str):
    """
    Display cards currently in either table using user input.

    Args:
        search (str): Partial or full name of card to search provided by user input.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = r"""
                WITH combined_results AS (
                    SELECT name, category, id_in_set, set_id, quantity, variant AS style
                    FROM tcg_cards
                    WHERE LOWER(name) LIKE LOWER(%s)
                    UNION ALL
                    SELECT name, sport, id_in_set, set_code, quantity, parallel AS style
                    FROM sports_cards
                    WHERE LOWER(name) LIKE LOWER(%s)
                    UNION ALL
                    SELECT name, category, id_in_set, set_code, quantity, variant AS style
                    FROM collector_cards
                    WHERE LOWER(name) LIKE LOWER(%s)
                )
                SELECT * FROM combined_results
                ORDER BY (SUBSTRING(id_in_set FROM '\d+'))::INTEGER ASC NULLS LAST;
            """
            cur.execute(query, (f"%{search}%", f"%{search}%", f"%{search}%"))

            results = cur.fetchall()

            if not results:
                print(f"No cards found with '{search}'.")
                return
            print(f"\nFound {search}:")
            for card in results:
                print(
                    f"{card[0]} ({card[1]}) \nID: {card[2]} \nSet: {card[3]} \nVariant: {card[5]} \nQuantity: {card[4]}\n"
                )


def save_tcg_card(
    name: str,
    category: str,
    id_in_set: str,
    description: str,
    card_type: str,
    set_id: str,
    rarity: str,
    variant: str,
    grade: str,
    grading_company: str,
    quantity: int,
):
    """
    Insert cards into TCG table provided by add_card() function.
    If card already present in tcg_cards table, increment the existing card's quantity.

    Args:
        name (str): Name of the card.
        category (str): Card game (e.g. Pokemon, One Piece)
        id_in_set (str): Card number within the set.
        description (str): Description of the card.
        card_type (str): Type of card.
        set_id (str): Name of the set.
        rarity (str): Card rarity.
        variant (str): Card variant (e.g. Standard, Holo, etc.).
        grade (str): Card grade if graded, otherwise 'N/A'.
        grading_company (str): Grading company if graded, otherwise 'N/A'.
        quantity (int): Number of copies to add.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tcg_cards (name, category, id_in_set, description, card_type, set_id, rarity, variant, grade, grading_company, quantity)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (category, set_id, id_in_set, variant)
                DO UPDATE SET
                    quantity = tcg_cards.quantity + EXCLUDED.quantity;
                """,
                (
                    name,
                    category,
                    id_in_set,
                    description,
                    card_type,
                    set_id,
                    rarity,
                    variant,
                    grade,
                    grading_company,
                    quantity,
                ),
            )
            conn.commit()
    print(f"{name.title()} has been successfully added to your TCG collection.")


def save_sports_card(
    name: str,
    players_featured: str,
    sport: str,
    id_in_set: str,
    set_code: str,
    team_name: str,
    rookie: bool,
    rarity: str,
    parallel: str,
    card_type: str,
    grade: str,
    grading_company: str,
    quantity: int,
):
    """
    Insert cards into sports_cards table provided by add_card() function.

    Args:
        name (str): Name of the card.
        players_featured (str): Player(s) featured in the card.
        sport (str): Sport (e.g. Baseball, Basketball, etc.).
        id_in_set (str): Card number within the set.
        set_code (str): Code to identify set (e.g. 2026-TOPPS-S1, 2025-TOPPS-S1, etc.).
        team_name (str): Team name.
        rookie (bool): Whether this is a rookie card.
        rarity (str): Card rarity.
        parallel (str): Card parallel (e.g. Base, Refractor).
        card_type (str): Card type (e.g. Player, Team, Event).
        grade (str): Card grade if graded, otherwise 'N/A'.
        grading_company (str): Grading company if graded, otherwise 'N/A'.
        quantity (int): Number of copies to add.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sports_cards (name, players_featured, sport, id_in_set, set_code, team_name, rookie, rarity, parallel, card_type, grade, grading_company, quantity)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sport, set_code, id_in_set, parallel)
                DO UPDATE SET
                    quantity = sports_cards.quantity + EXCLUDED.quantity
                """,
                (
                    name,
                    players_featured,
                    sport,
                    id_in_set,
                    set_code,
                    team_name,
                    rookie,
                    rarity,
                    parallel,
                    card_type,
                    grade,
                    grading_company,
                    quantity,
                ),
            )
            conn.commit()
    print(f"{name.title()} has been successfully added to your Sports collection.")


def save_collector_card(
    name: str,
    category: str,
    id_in_set: str,
    description: str,
    set_code: str,
    rarity: str,
    variant: str,
    grade: str,
    grading_company: str,
    quantity: int,
):
    """
    Insert cards into collector table provided by add_card() function.
    If card already present in collector_cards table, increment the existing card's quantity.

    Args:
        name (str): Name of the card.
        category (str): Card game (e.g. Pokemon, One Piece)
        id_in_set (str): Card number within the set.
        description (str): Description of the card.
        set_id (str): Name of the set.
        rarity (str): Card rarity.
        variant (str): Card variant (e.g. Standard, Holo, etc.).
        grade (str): Card grade if graded, otherwise 'N/A'.
        grading_company (str): Grading company if graded, otherwise 'N/A'.
        quantity (int): Number of copies to add.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO collector_cards (name, category, id_in_set, description, set_code, rarity, variant, grade, grading_company, quantity)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (category, set_code, id_in_set, variant)
                DO UPDATE SET
                    quantity = collector_cards.quantity + EXCLUDED.quantity;
                """,
                (
                    name,
                    category,
                    id_in_set,
                    description,
                    set_code,
                    rarity,
                    variant,
                    grade,
                    grading_company,
                    quantity,
                ),
            )
            conn.commit()
    print(
        f"{name.title()} has been successfully added to your collector card collection."
    )


def main():
    """
    Main menu loop for user to select from.
    """
    init_db()
    while True:
        print("\nTrading Card Menu")
        print("1. Add a new card")
        print("2. Find a card")
        print("3. Bulk import cards (csv)")
        print("4. Enrich Pokemon cards via API")
        print("5. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            add_card()
        elif choice == "2":
            search = input("Enter the name of the card you are searching for: ")
            display_card(search)
        elif choice == "3":
            print("\nBulk Import Menu: ")
            print("1. TCG")
            print("2. Sports")
            print("3. Collector Cards (not working yet...)")
            bulk_choice = input(
                "Enter choice above on what type of card you want to bulk import: "
            )
            if bulk_choice == "3":
                break
            file_name = input("Enter the CSV filename (w/ extension): ")
            if bulk_choice == "1":
                bulk_import_tcg(file_name)
            elif bulk_choice == "2":
                bulk_import_sports(file_name)
            # elif bulk_choice == "3":
            # bulk_import_collectors(file_name)
        elif choice == "4":
            enrich_pokemon_cards()
        elif choice == "5":
            break
        else:
            print("Invalid choice. Please enter a valid selection.")


if __name__ == "__main__":
    main()
