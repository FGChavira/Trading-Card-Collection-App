import psycopg2
import os
from dotenv import load_dotenv

from contextlib import contextmanager
import psycopg2.extras
from psycopg2 import pool

load_dotenv()


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "card_collection"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

_connection_pool = None

def _get_pool():
    """
    Return the shared connection pool, creating it on first use.
    """
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=int(os.getenv("DB_POOL_MIN", "1")),
            maxconn=int(os.getenv("DB_POOL_MAX", "10")),
            **DB_CONFIG,
        )
    return _connection_pool


@contextmanager
def get_connection():
    """
    Borrow a connection from the pool and return it when done.

    Used as a context manager: with get_connection() as conn: ...
    The connection is returned to the pool (not closed) on exit.
    """
    pool_ = _get_pool()
    conn = pool_.getconn()
    try:
        yield conn
    finally:
        pool_.putconn(conn)

    # """
    # Connect to database using DB_CONFIG parameters.
    # """
    # return psycopg2.connect(**DB_CONFIG)


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
                        complete_set_size INTEGER,
                        master_set_size INTEGER,
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

def _fetch_set_counts(cur, set_name: str):
    """
    Look up the official complete-set and master-set totals from the sets table.

    Return (complete_set_size, master_set_size) or (None, None) if the set is unknown.
    """
    cur.execute(
        """
        SELECT complete_set_size, master_set_size
        FROM sets
        WHERE LOWER(name) = LOWER(%s)
        """,
        (set_name,),
    )
    row = cur.fetchone()
    if not row:
        return None, None
    return row[0], row[1]

def display_set(search: str):
    """
    Display owned cards all within a set and progress towards completing/mastering it.

    Set totals are read from the sets table (complete_set_size, master_set_size) rather than hardcoded.
    Args:
        search (str): Name of trading card set.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = r"""
                SELECT tcg.id_in_set, tcg.name, tcg.variant, tcg.condition, tcg.quantity
                FROM tcg_cards tcg
                JOIN sets ON tcg.set_code = sets.set_code
                WHERE LOWER(sets.name) = LOWER(%s)
                ORDER BY (SUBSTRING(id_in_set FROM '\d+'))::INTEGER ASC NULLS LAST;
            """
            count_query = r"""
                SELECT COUNT(*)
                FROM (
                    SELECT DISTINCT id_in_set
                    FROM tcg_cards tcg
                    JOIN sets ON tcg.set_code = sets.set_code
                    WHERE LOWER(sets.name) = LOWER(%s)
                    AND variant IN ('Standard', 'Holo')
                ) AS distinct_cards
                """
            master_count_query = r"""
                SELECT COUNT(*)
                FROM (
                    SELECT DISTINCT id_in_set, variant
                    FROM tcg_cards tcg
                    JOIN sets ON tcg.set_code = sets.set_code
                    WHERE LOWER(sets.name) = LOWER(%s)
                    AND variant NOT IN ('Stamped', 'Promo')
                ) AS distinct_cards
                """
            cur.execute(query, (search,))
            results = cur.fetchall()

            if not results:
                print(f"You own no cards within {search}.")
                return
            
            cur.execute(count_query, (search,))
            count_result = cur.fetchone()[0]

            cur.execute(master_count_query, (search,))
            master_count_result = cur.fetchone()[0]

            complete_set_size, master_set_size = _fetch_set_counts(cur, search)

            if complete_set_size is None:
                print(
                    f"\nYou own {count_result} unique cards in {search}, but this set "
                    f"isn't in your sets table yet, so completion cannot be calculated."
                )
                return
            print(
                f"\nYou own {count_result} unique cards in {search}."
                f"\nYou need {complete_set_size - count_result} more to complete the set!"
            )

            if master_set_size is not None:
                print(
                    f"\nIncluding special variants, you own {master_count_result} unique cards."
                    f"You need {master_set_size - master_count_result} more to master the set!"
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


def search_cards(search: str, limit: int = 50, offset: int = 0):
    """
    Search all three card tables by (partial) name and return rows as dicts.

    Args:
        search (str): Partial or full card name.
        limit (int): Max rows to return.
        offset (int): Rows to skip (for pagination).

    Returns:
        list[dict]: Matching cards with a unified shape.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                r"""
                WITH combined_results AS (
                    SELECT  tcg.name, tcg.category AS group_name, tcg.id_in_set, tcg.set_code, tcg.quantity,
                            tcg.variant AS style, 'tcg' AS source,
                            sets.name AS set_name
                    FROM    tcg_cards tcg
                    LEFT JOIN sets ON tcg.set_code = sets.set_code
                    WHERE   LOWER(tcg.name) LIKE LOWER(%(term)s)
                    UNION ALL
                    SELECT  spo.name, spo.sport AS group_name, spo.id_in_set, spo.set_code, spo.quantity, 
                            spo.parallel AS style, 'sports' AS source,
                            sets.name AS set_name
                    FROM    sports_cards spo
                    LEFT JOIN sets ON spo.set_code = sets.set_code
                    WHERE   LOWER(spo.name) LIKE LOWER(%(term)s)
                )
                
                SELECT * FROM combined_results
                ORDER BY (SUBSTRING(id_in_set FROM '\d+'))::INTEGER ASC NULLS LAST
                LIMIT %(limit)s OFFSET %(offset)s;
                """,
                {"term": f"%{search}%", "limit": limit, "offset": offset},
            )
            return [dict(row) for row in cur.fetchall()]

def get_card(source: str, category: str, set_name: str,id_in_set: str):
    """
    Fetch a single card, uniquely identified by its source table, category/sport, 
    set name, and id_in_set.

    Args:
        source (str): One of 'tcg', sports', or 'collector'.
        category (str): Category (tcg/collector) or sport (sports).
        set_name (str): Human set name, e.g. 'Prismatic Evolutions'.
        id_in_set (str): Card number within the set.

    Returns:
        dict | None: The card row, or None if not found.
    """
    tables = {
        "tcg": ("tcg_cards", "category"),
        "sports": ("sports_cards", "sport"),
        "collector": ("collector_cards", "category"),
    }
    if source not in tables:
        raise ValueError(f"Unknown card source '{source}'.")
    table, group_col = tables[source]
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT  tab.*
                FROM    {table} as tab
                JOIN    sets ON tab.set_code = sets.set_code
                WHERE   LOWER(tab.{group_col}) = LOWER(%s)
                 AND    LOWER(sets.name) = LOWER(%s)
                 AND    tab.id_in_set = %s
                """,
                (category, set_name, id_in_set),
            )
            row = cur.fetchone()
            return dict(row) if row else None