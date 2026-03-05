import psycopg2
import csv
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "card_collection"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def init_db():
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
                            type TEXT,
                            rarity TEXT,
                            set_id TEXT,
                            condition TEXT,
                            variant TEXT DEFAULT 'Standard',
                            quantity INTEGER DEFAULT 1,
                            acquired_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            CONSTRAINT unique_tcg_card UNIQUE (category, set_id, id_in_set, variant)
                            )
                        """
                )
                cur.execute(
                    """
                            CREATE TABLE IF NOT EXISTS sports_cards (
                            id SERIAL PRIMARY KEY,
                            name TEXT NOT NULL,
                            sport TEXT NOT NULL,
                            id_in_set TEXT,
                            rarity TEXT,
                            rookie BOOLEAN DEFAULT FALSE,
                            team_name TEXT NOT NULL,
                            set_id TEXT,
                            condition TEXT,
                            parallel TEXT DEFAULT 'Base',
                            quantity INTEGER DEFAULT 1,
                            acquired_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            CONSTRAINT unique_sports_card UNIQUE (sport, set_id, id_in_set, parallel)
                            )
                        """
                )
                conn.commit()
                print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")


def add_card():
    print("\nAdd Card Menu")
    print("1. TCG Card (Pokemon, One Piece)")
    print("2. Sports Card (Baseball, Football, Basketball)")
    print("3. Back to menu")

    choice = input("Select a value from the menu: ")
    if choice == "1":
        name = input("Card Name: ")
        category = input("Category (e.g. Pokemon, One Piece): ")
        id_in_set = input("ID in Set: ")
        description = input("Card description (can leave blank): ")
        type = input("Type (can leave blank): ")
        set_id = input("Set: ")
        rarity = input("Rarity: ")
        variant = input("Variant: ")
        quantity = input("Quantity: ")
        save_tcg_card(
            name,
            category,
            id_in_set,
            description,
            type,
            set_id,
            rarity,
            variant,
            quantity,
        )
    elif choice == "2":
        name = input("Card Name: ")
        sport = input("Sport (e.g. Baseball, Basketball): ")
        id_in_set = input("ID in Set: ")
        team_name = input("Team Name: ")
        rookie = input("Is this a rookie card? (y/n): ").lower() == "y"
        set_id = input("Set: ")
        rarity = input("Rarity: ")
        parallel = input("Parallel: ")
        save_sports_card(
            name, sport, id_in_set, team_name, rookie, set_id, rarity, parallel
        )


def bulk_import_tcg(file_path):
    with open(file_path, mode="r", encoding="utf-8-sig") as bulk_file:
        reader = csv.DictReader(bulk_file)
        with get_connection() as conn:
            with conn.cursor() as cur:
                for record in reader:
                    cur.execute(
                        """
                                INSERT INTO tcg_cards (name, category, id_in_set, rarity, set_id, quantity, variant)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (category, set_id, id_in_set, variant)
                                DO UPDATE SET
                                    quantity = tcg_cards.quantity + 1;
                                """,
                        (
                            record["name"],
                            record["category"],
                            record["id_in_set"],
                            record["rarity"],
                            record["set_id"],
                            record.get("quantity") or 1,
                            record["variant"],
                        ),
                    )
                conn.commit()
    print("Bulk cards have been imported.")


def display_card(search):
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = r"""
                WITH combined_results AS (
                SELECT name, category, id_in_set, set_id, quantity, variant AS style
                FROM tcg_cards
                WHERE LOWER(name) LIKE LOWER(%s)
                UNION ALL
                SELECT name, sport, id_in_set, set_id, quantity, parallel AS style
                FROM sports_cards
                WHERE LOWER(name) LIKE LOWER(%s)
            )
            SELECT * FROM combined_results
            ORDER BY SUBSTRING(id_in_set FROM '\d+')::INTEGER ASC;
            """
            cur.execute(query, (f"%{search}%", f"%{search}%"))

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
    name, category, id_in_set, description, type, set_id, rarity, variant, quantity
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                        INSERT INTO tcg_cards (name, category, id_in_set, description, type, set_id, rarity, variant, quantity)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (category, set_id, id_in_set, variant)
                        DO UPDATE SET
                            quantity = tcg_cards.quantity + 1
                        """,
                (
                    name,
                    category,
                    id_in_set,
                    description,
                    type,
                    set_id,
                    rarity,
                    variant,
                    quantity,
                ),
            )
            conn.commit()
    print(f"{name.title()} has been successfully added to your TCG collection.")


def save_sports_card(
    name, sport, id_in_set, team_name, rookie, set_id, rarity, parallel
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                        INSERT INTO sports_cards (name, sport, id_in_set, team_name, rookie, set_id, rarity, parallel, quantity)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
                        ON CONFLICT (sport, set_id, id_in_set, parallel)
                        DO UPDATE SET
                            quantity = sports_cards.quantity + 1
                        """,
                (name, sport, id_in_set, team_name, rookie, set_id, rarity, parallel),
            )
            conn.commit()
    print(f"{name.title()} has been successfully added to your Sports collection.")


def main():
    init_db()
    while True:
        print("\nTrading Card Menu")
        print("1. Add a new card")
        print("2. Find a card")
        print("3. Bulk import cards (csv)")
        print("4. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            add_card()
        elif choice == "2":
            search = input("Enter the name of the card you are searching for: ")
            display_card(search)
        elif choice == "3":
            file_name = input("Enter the CSV filename (w/ extension): ")
            bulk_import_tcg(file_name)
        elif choice == "4":
            break
        else:
            print("Invalid choice. Please enter a valid selection.")


if __name__ == "__main__":
    main()
