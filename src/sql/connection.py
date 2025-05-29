import mysql.connector
import pandas as pd
import sqlite3
import os

def db_connect(target_db: str = "local"):
    """
    Establishes a database connection.

    Args:
        target_db (str): The target database. "local" (default) for SQLite, 
                         "remote" for the Amazon RDS MySQL database.

    Returns:
        A database connection object.
    """
    if target_db == "local":
        # Define the path to the local SQLite database file in resources/db/
        # This path should match the one used in database_setup.py
        current_script_path = os.path.dirname(__file__) # src/sql
        project_root = os.path.abspath(os.path.join(current_script_path, '..', '..')) # Project root
        db_path = os.path.join(project_root, 'resources', 'db', 'cajubills_local.db')
        print(f"Connecting to local SQLite database: {db_path}")
        
        # Ensure the directory exists before trying to connect, 
        # though connect itself will create the file, the directory must exist.
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                print(f"Created database directory: {db_dir}")
            except Exception as e:
                print(f"Error creating database directory {db_dir}: {e}")
                # Decide how to handle this: raise error, or try to connect anyway?
                # For now, we will print and let sqlite3.connect try.

        conn = sqlite3.connect(db_path)
        # For SQLite, to return rows as dictionaries (similar to mysql.connector with dictionary=True)
        # or to allow column access by name, you might set conn.row_factory = sqlite3.Row
        # However, pandas.read_sql handles this well, and for cursor operations,
        # the default tuple-based rows are standard.
        # If your direct cursor usage relies on dictionary-like rows, this might be needed.
        # For now, this is a standard sqlite3 connection.
        return conn
    elif target_db == "remote":
        print("Connecting to remote Amazon RDS MySQL database...")
        host = "finance.cvm2aaxkmu43.us-east-2.rds.amazonaws.com"
        user = "admin"
        password = "Nk7f4mJr6?A"
        database = "finance"

        try:
            conn = mysql.connector.connect(
                host=host,
                port=3306,
                user=user,
                password=password,
                database=database,
                
                # RDS Best Practices
                ssl_disabled=False,           # Enable SSL for security
                connection_timeout=30,        # 30 second timeout
                autocommit=True,             # Auto-commit for consistency
                charset='utf8mb4',           # Proper UTF-8 support
                
                # Optional: Connection pooling (good for production)
                # pool_name='rds_pool',
                # pool_size=3,
                # pool_reset_session=True
            )
            print("✅ Successfully connected to RDS MySQL database")
            return conn
            
        except mysql.connector.Error as e:
            print(f"❌ MySQL Error connecting to RDS: {e}")
            raise
        except Exception as e:
            print(f"❌ Unexpected error connecting to RDS: {e}")
            raise
    else:
        raise ValueError("Invalid target_db specified. Choose 'local' or 'remote'.")


def run_query(query, target_db: str = "local"):
    """ 
    Runs a SQL query against the specified database and returns a DataFrame.
    The database connection defaults to local if not specified.
    """
    conn = db_connect(target_db=target_db) # Pass the target_db to db_connect
    df = pd.read_sql(query, conn)
    conn.close()
    return df


