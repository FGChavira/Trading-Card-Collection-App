import csv

import db as db


def _resolve_set_code(cur, set_name: str, category: str) -> str:
    """
    Alter set_name from cards table to match the name column of sets table in order to retrieve set_code.

    Args:
        cur:
        set_name (str): Value from set_name column of cards table.
        category (str): Category of cards being imported.

    Returns:
        str: Value from set_code columns of sets table.
    """
    cur.execute(
        "SELECT set_code FROM sets WHERE LOWER(name) = LOWER(%s) AND LOWER(category) = LOWER(%s)",
        (set_name, category),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError(
            f"No set found with name '{set_name}' and category '{category}'."
        )
    return row[0]


def bulk_import_tcg(file_path: str):
    """
    Bulk import TCG cards into tcg_cards table using user provided .csv file.

    Args:
        file_path (str): File path to user provided .csv file containing card data.
    """
    with open(file_path, mode="r", encoding="utf-8-sig") as bulk_file:
        reader = csv.DictReader(bulk_file)
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                for record in reader:
                    set_code = _resolve_set_code(
                        cur, record["set_name"], record["category"]
                    )
                    cur.execute(
                        """
                        INSERT INTO tcg_cards (name, category, id_in_set, rarity, set_code, quantity, variant, grade, grading_company)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (category, set_code, id_in_set, variant)
                        DO UPDATE SET
                            quantity = tcg_cards.quantity + EXCLUDED.quantity;
                        """,
                        (
                            record["name"],
                            record["category"],
                            record["id_in_set"],
                            record["rarity"],
                            set_code,
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
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                for record in reader:
                    set_code = _resolve_set_code(
                        cur, record["set_name"], record["sport"]
                    )
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
                            set_code,
                            record.get("quantity") or 1,
                            record["parallel"],
                            record["card_type"],
                            record.get("grade") or "N/A",
                            record.get("grading_company") or "N/A",
                        ),
                    )
                conn.commit()
    print("Bulk cards have been imported.")


def bulk_import_collector(file_path):
    """
    Bulk import collector cards into collector_cards table using user provided .csv file.

    Args:
        file_path (str): File path to user provided .csv file containing card data.
    """
    with open(file_path, mode="r", encoding="utf-8-sig") as bulk_file:
        reader = csv.DictReader(bulk_file)
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                for record in reader:
                    set_code = _resolve_set_code(
                        cur, record["set_name"], record["category"]
                    )
                    cur.execute(
                        """
                        INSERT INTO collector_cards (name, category, id_in_set, description, rarity, set_code, quantity, variant, grade, grading_company)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (category, set_code, id_in_set, variant)
                        DO UPDATE SET
                            quantity = collector_cards.quantity + EXCLUDED.quantity;
                        """,
                        (
                            record["name"],
                            record["category"],
                            record["id_in_set"],
                            record["description"] or "",
                            record["rarity"],
                            set_code,
                            record.get("quantity") or 1,
                            record["variant"],
                            record.get("grade") or "N/A",
                            record.get("grading_company") or "N/A",
                        ),
                    )
                conn.commit()
    print("Bulk cards have been imported.")
