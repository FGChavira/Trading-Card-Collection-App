import db as db
import api as api
import bulk_import as bi


def search_pokemon_sets(search_term: str = "") -> list:
    """
    Search for Pokemon sets in the database.
    
    Args:
        search_term (str): Optional term to filter sets. If empty, returns all Pokemon sets.
    
    Returns:
        list: List of tuples containing (set_code, name).
    """
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            if search_term:
                cur.execute(
                    """
                    SELECT DISTINCT set_code, name
                    FROM sets
                    WHERE LOWER(category) = 'pokemon'
                    AND (LOWER(name) LIKE LOWER(%s) OR LOWER(set_code) LIKE LOWER(%s))
                    ORDER BY name
                    """,
                    (f"%{search_term}%", f"%{search_term}%"),
                )
            else:
                cur.execute(
                    """
                    SELECT DISTINCT set_code, name
                    FROM sets
                    WHERE LOWER(category) = 'pokemon'
                    ORDER BY name
                    """
                )
            return cur.fetchall()


def select_pokemon_set() -> tuple | None:
    """
    Allow user to search for and select a Pokemon set.
    
    Returns:
        tuple | None: Tuple of (set_code, set_name) or None if user cancels.
    """
    search_term = input("\nSearch for a Pokemon set (partial name/code, or press Enter to see all): ").strip()
    sets = search_pokemon_sets(search_term)
    
    if not sets:
        print("No sets found.")
        return None
    
    if len(sets) == 1:
        set_code, set_name = sets[0]
        print(f"Selected: {set_name} ({set_code})")
        return (set_code, set_name)
    
    print(f"\nFound {len(sets)} set(s):")
    for i, (code, name) in enumerate(sets, 1):
        print(f"{i}. {name} ({code})")
    
    choice = input("\nSelect a set number (0 to cancel): ").strip()
    if not choice.isdigit() or int(choice) == 0 or int(choice) > len(sets):
        return None
    
    set_code, set_name = sets[int(choice) - 1]
    return (set_code, set_name)


def add_pokemon_batch():
    """
    Add multiple Pokemon cards from selected set(s) in a batch.
    Allows user to search for and add multiple cards without returning to menu.
    """
    print("\n=== Add Multiple Pokemon ===")
    
    while True:
        # Select a set
        set_info = select_pokemon_set()
        if not set_info:
            break
        
        set_code, set_name = set_info
        
        # Loop to add multiple cards from this set
        while True:
            card_name = input(f"\nEnter Pokemon name to add from {set_name} (or press Enter to change set): ").strip()
            if not card_name:
                break
            
            api_data = api.search_pokemon_card(card_name, set_code=set_code)
            
            if api_data:
                name = api_data["name"]
                id_in_set = api_data["id_in_set"]
                description = api_data["description"]
                card_type = api_data["card_type"]
                set_code_result = api_data["set_code"]
                rarity = api_data["rarity"]
                print(f"\nPre-filled from API:")
                print(f"  Name:       {name}")
                print(f"  Set:        {set_code_result}")
                print(f"  ID in Set:  {id_in_set}")
                print(f"  Rarity:     {rarity}")
                print(f"  Type:       {card_type}")
            else:
                print("Could not find card via API. Skipping.")
                continue
            
            variant = input("Variant: ") or "Standard"
            grade = input("Grade (leave blank for N/A): ") or "N/A"
            grading_company = input("Grading Company (leave blank for N/A): ") or "N/A"
            quantity = int(input("Quantity: ") or 1)
            
            db.save_tcg_card(
                name,
                "Pokemon",
                id_in_set,
                description,
                card_type,
                set_code_result,
                rarity,
                variant,
                grade,
                grading_company,
                quantity,
            )
            print(f"Added {quantity}x {name}")
        
        # Ask if user wants to add from another set
        another_set = input("\nAdd cards from another set? (y/n): ").lower()
        if another_set != 'y':
            break
    
    print("\nFinished adding Pokemon.")


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

        if category.lower() == "pokemon":
            multiple = input("Are you adding multiple Pokemon? (y/n): ").lower()
            if multiple == 'y':
                add_pokemon_batch()
                return
        
        # Single card flow
        api_data = None
        if category.lower() == "pokemon":
            api_data = api.search_pokemon_card(input("Card name to search: "))

        if api_data:
            name = api_data["name"]
            id_in_set = api_data["id_in_set"]
            description = api_data["description"]
            card_type = api_data["card_type"]
            set_code = api_data["set_code"]
            rarity = api_data["rarity"]
            print(f"\nPre-filled from API:")
            print(f"  Name:       {name}")
            print(f"  Set:        {set_code}")
            print(f"  ID in Set:  {id_in_set}")
            print(f"  Rarity:     {rarity}")
            print(f"  Type:       {card_type}")
        else:
            name = input("Card Name: ")
            id_in_set = input("ID in Set: ")
            description = input("Card description (can leave blank): ")
            card_type = input("Type (can leave blank): ")
            set_code = input("Set Code (2026-ME-ASC, 2025-SV-PRE, etc.): ")
            rarity = input("Rarity: ")

        variant = input("Variant: ") or "Standard"
        grade = input("Grade (leave blank for N/A): ") or "N/A"
        grading_company = input("Grading Company (leave blank for N/A): ") or "N/A"
        quantity = int(input("Quantity: ") or 1)
        db.save_tcg_card(
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
        db.save_sports_card(
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
        quantity = int(input("Quantity: ") or 1)
        db.save_collector_card(
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


def main():
    """
    Main menu loop for user to select from.
    """
    db.init_db()
    while True:
        print("\nTrading Card Menu")
        print("1. Add a new card")
        print("2. Find a card")
        print("3. Bulk import cards (csv)")
        print("4. Enrich Pokemon cards via API")
        print("5. Track Complete/Master Set Count")
        print("6. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            add_card()
        elif choice == "2":
            search = input("Enter the name of the card you are searching for: ")
            db.display_card(search)
        elif choice == "3":
            print("\nBulk Import Menu: ")
            print("1. TCG")
            print("2. Sports")
            print("3. Collector Cards")
            bulk_choice = input(
                "Enter choice above on what type of card you want to bulk import: "
            )
            file_name = input("Enter the CSV filename (w/ extension): ")
            if bulk_choice == "1":
                bi.bulk_import_tcg(file_name)
            elif bulk_choice == "2":
                bi.bulk_import_sports(file_name)
            elif bulk_choice == "3":
                bi.bulk_import_collector(file_name)
        elif choice == "4":
            api.enrich_pokemon_cards()
        elif choice == "5":
            search = input("Enter the name of the set you want to look at.")
            db.display_set(search)
        elif choice == "6":
            break
        else:
            print("Invalid choice. Please enter a valid selection.")


if __name__ == "__main__":
    main()
