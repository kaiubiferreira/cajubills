'''
Main script to initialize the database, create tables, and process data.
'''
import os
import sys

# Ensure src directory is in Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Ensure src is discoverable for imports like from src.sql... 
sys.path.insert(0, os.path.join(project_root, 'src')) 

# Import project-specific modules
try:
    from src.sql.database_setup import reset_local_database, create_tables_from_ddl
    from src.sql.connection import db_connect # Keep for investment processing if it still needs explicit conn
    from src.backend.investments.investment import process_all as process_all_investments
    from src.backend.spending.spending import process_all as process_all_spending
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print("Please ensure that the script is run from the project root and that all paths are correct.")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)

def main():
    """Main function to orchestrate the project setup and data processing."""
    print("===========================================")
    print("  STARTING CAJUBILLS PROJECT INITIALIZATION  ")
    print("===========================================")

    # Step 1: Reset the local database
    print("\n--- Step 1: Resetting local database ---")
    print("Skipping database reset.")
    # if reset_local_database():
    #     print("Local database reset successfully.")
    # else:
    #     print("Failed to reset local database. Aborting.")
    #     return

    # Step 2: Create tables in the local database
    print("\n--- Step 2: Creating database tables ---")
    # # The create_tables_from_ddl function defaults to "local"
    if create_tables_from_ddl(): 
        print("Database tables created successfully.")
    else:
        print("Failed to create database tables. Aborting.")
        return

    # Step 3: Process and load investments data
    print("\n--- Step 3: Processing investments data ---")
    try:
        print("Calling investments processing logic...")
        # Ensure process_all_investments from src.backend.investments.investment 
        # is adapted to accept a database connection object.
        conn_invest = db_connect(target_db="local") 
        process_all_investments(conn_invest) 
        conn_invest.close() 
        print("Investments data processing completed.")
    except Exception as e:
        print(f"Error during investments data processing: {e}")

    # # Step 4: Process and load spending data
    # print("\n--- Step 4: Processing spending data ---")
    # try:
    #     print("Calling spending processing logic...")
    #     process_all_spending(target_db="local")
    #     print("Spending data processing completed.")
    # except Exception as e:
    #     print(f"Error during spending data processing: {e}")

    print("\n===========================================")
    print("  CAJUBILLS PROJECT INITIALIZATION FINISHED  ")
    print("===========================================")

if __name__ == "__main__":
    main() 