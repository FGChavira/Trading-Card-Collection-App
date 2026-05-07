import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

import db as db

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "card_collection"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


def get_connection():
    """
    Connect to database using DB_CONFIG parameters.
    """
    return psycopg2.connect(**DB_CONFIG)


def init_db():
    """
    Create necessary tables.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tcg_cards (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        id_in_set TEXT NOT NULL,
                        description TEXT,
                        card_type TEXT,
                        rarity TEXT,
                        set_code TEXT,
                        condition TEXT,
                        variant TEXT DEFAULT 'Standard',
                        quantity INTEGER DEFAULT 1,
                        acquired_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        grade TEXT DEFAULT 'N/A',
                        grading_company TEXT DEFAULT 'N/A',
                        CONSTRAINT unique_tcg_card UNIQUE (category, set_code, id_in_set, variant)
                    )
                    """)
                cur.execute("""
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
                    """)
                cur.execute("""
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
                    """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sets (
                        id SERIAL PRIMARY KEY,
                        set_code TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        series TEXT DEFAULT 'N/A',
                        manufacturer TEXT,
                        release_year SMALLINT,
                        total_cards INTEGER,
                        CONSTRAINT sets_unique UNIQUE (set_code, category)
                    )
                    """)
                conn.commit()
                print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")


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
                    SELECT name, category, id_in_set, set_code, quantity, variant AS style
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
    set_code: str,
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
        set_code (str): Name of the set.
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
                INSERT INTO tcg_cards (name, category, id_in_set, description, card_type, set_code, rarity, variant, grade, grading_company, quantity)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (category, set_code, id_in_set, variant)
                DO UPDATE SET
                    quantity = tcg_cards.quantity + EXCLUDED.quantity;
                """,
                (
                    name,
                    category,
                    id_in_set,
                    description,
                    card_type,
                    set_code,
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
        set_code (str): Name of the set.
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
