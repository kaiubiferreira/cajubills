'''
Contains functions for initial database setup, like creating the database file.
'''
import os
import sqlite3

def create_local_database():
    """
    Ensures the local SQLite database file and its directory exist.
    The database file will be located at resources/db/cajubills_local.db.
    """
    try:
        # Determine project root (assuming this script is in src/sql/)
        # Adjust if the script location changes relative to project root.
        current_script_path = os.path.dirname(__file__)
        project_root = os.path.abspath(os.path.join(current_script_path, '..', '..'))

        db_dir = os.path.join(project_root, 'resources', 'db')
        db_path = os.path.join(db_dir, 'cajubills_local.db')

        # Create the directory if it doesn't exist
        os.makedirs(db_dir, exist_ok=True)
        print(f"Ensured directory exists: {db_dir}")

        # Connect to the database (this will create the file if it doesn't exist)
        conn = sqlite3.connect(db_path)
        conn.close()
        print(f"Local SQLite database file ensured/created at: {db_path}")
        return db_path # Optionally return the path

    except Exception as e:
        print(f"Error creating local database: {e}")
        return None

if __name__ == '__main__':
    print("Attempting to create local database...")
    created_db_path = create_local_database()
    if created_db_path:
        print(f"Script finished. Database should be at: {created_db_path}")
    else:
        print("Script finished. Database creation failed.") 