'''
Contains functions for initial database setup, like creating the database file and schema.
'''
import os
import sqlite3
import mysql.connector # For error handling consistency in create_tables_from_ddl

# Attempt to import db_connect. If this script is run directly, paths might need care.
# Assuming it will be called from project root or similar context where src. is valid.
try:
    from src.sql.connection import db_connect
except ImportError:
    # This fallback allows the script to potentially be run directly for its own functions,
    # but create_tables_from_ddl will fail if db_connect is not found.
    print("Warning: Could not import db_connect from src.sql.connection. Table creation functions might fail if called directly without proper path setup.")
    db_connect = None 

# Embedded DDL statements
ALL_DDL_STATEMENTS = '''
DROP TABLE IF EXISTS fixed_income_operations;
CREATE TABLE fixed_income_operations (
	asset VARCHAR(50),
	operation_type VARCHAR(50),
	quotas DOUBLE,
	purchase_date DATE,
	due_date DATE,
	financial_index VARCHAR(50),
	value DOUBLE,
	pre_rate DOUBLE,
	post_rate DOUBLE,
	tax_rate DOUBLE,
	is_pgbl BOOL,
	PRIMARY KEY (asset, purchase_date, operation_type, due_date, financial_index)
);

DROP TABLE IF EXISTS variable_income_operations;
CREATE TABLE variable_income_operations (
  ticker varchar(50) NOT NULL,
  operation_type varchar(10) NOT NULL,
  operation_date date NOT NULL,
  amount double NOT NULL,
  price double NOT NULL,
  currency varchar(50) DEFAULT NULL,
  PRIMARY KEY (ticker, operation_type, operation_date, amount, price)
);

DROP TABLE IF EXISTS asset_price;
CREATE TABLE asset_price (
    ticker VARCHAR(50),
    quote_date DATE,
    open_price DOUBLE,
    close_price DOUBLE,
    PRIMARY KEY (ticker, quote_date)
);

DROP TABLE IF EXISTS daily_asset_price;
CREATE TABLE daily_asset_price (
    ticker VARCHAR(50),
    date DATE,
    price DOUBLE,
    PRIMARY KEY (ticker, date)
);

DROP TABLE IF EXISTS dates;
CREATE TABLE dates (
    date DATE,
    PRIMARY KEY (date)
);

DROP TABLE IF EXISTS variable_income_daily_balance;
CREATE TABLE variable_income_daily_balance (
  ticker varchar(50) NOT NULL,
  date DATE NOT NULL,
  price double NOT NULL,
  dolar_price double NOT NULL,
  currency varchar(50) DEFAULT NULL,
  amount_change double,
  amount double,
  value double,
  PRIMARY KEY (ticker, date)
);

DROP TABLE IF EXISTS index_series;
CREATE TABLE index_series(
    financial_index varchar(30),
    date DATE,
    factor DOUBLE,
    PRIMARY KEY (financial_index, date)
);

DROP TABLE IF EXISTS fixed_income_daily_balance;
CREATE TABLE fixed_income_daily_balance (
	asset VARCHAR(50),
	due_date DATE,
	date DATE,
	tax_rate DOUBLE,
	deposit_value DOUBLE,
	gross_value DOUBLE,
	tax_value DOUBLE,
	net_value DOUBLE,
	PRIMARY KEY (asset, due_date, date)
);

DROP TABLE IF EXISTS daily_balance;
CREATE TABLE daily_balance (
	asset VARCHAR(50),
	date DATE,
	value DOUBLE,
	type VARCHAR(50),
	PRIMARY KEY (asset, type, date)
);

DROP TABLE IF EXISTS fgts_operations;
CREATE TABLE fgts_operations (
    date DATE,
    company VARCHAR(50),
    operation VARCHAR(50),
    value DOUBLE,
    balance DOUBLE,
    PRIMARY KEY (date, company, operation)
);

DROP TABLE IF EXISTS fgts_daily_balance;
CREATE TABLE fgts_daily_balance (
    date DATE,
    balance DOUBLE,
    PRIMARY KEY (date)
);

DROP TABLE IF EXISTS operations;
CREATE TABLE operations (
 asset VARCHAR(50),
 operation_type VARCHAR(50),
 operation_date DATE,
 value DOUBLE,
 currency VARCHAR(50),
 dolar_price DOUBLE
);

DROP TABLE IF EXISTS financial_returns;
CREATE TABLE financial_returns(
    asset VARCHAR(50),
    year  int,
    month int,
    month_start_value DOUBLE,
    month_end_value DOUBLE,
    deposit DOUBLE,
    net_increase DOUBLE,
    profit DOUBLE,
    relative_return DOUBLE,
    PRIMARY KEY (asset, year, month)
);

DROP TABLE IF EXISTS summary_returns;
CREATE TABLE summary_returns(
    year  int,
    month int,
    month_end_value DOUBLE,
    total_deposit DOUBLE,
    total_profit DOUBLE,
    total_return DOUBLE,
    moving_avg_deposit_3 DOUBLE,
    moving_avg_profit_3 DOUBLE,
    moving_avg_return_3 DOUBLE,
    moving_avg_deposit_6 DOUBLE,
    moving_avg_profit_6 DOUBLE,
    moving_avg_return_6 DOUBLE,
    moving_avg_deposit_9 DOUBLE,
    moving_avg_profit_9 DOUBLE,
    moving_avg_return_9 DOUBLE,
    moving_avg_deposit_12 DOUBLE,
    moving_avg_profit_12 DOUBLE,
    moving_avg_return_12 DOUBLE,
    PRIMARY KEY (year, month)
);

DROP TABLE IF EXISTS target_percentage;
CREATE TABLE target_percentage(
    name VARCHAR(50),
    percentage DOUBLE,
    PRIMARY KEY (name)
);

DROP TABLE IF EXISTS transaction_categories;
CREATE TABLE transaction_categories (
    main_category VARCHAR(100) NOT NULL,
    sub_category VARCHAR(100) NOT NULL,
    PRIMARY KEY (main_category, sub_category)
);

DROP TABLE IF EXISTS ofx_transactions;
CREATE TABLE ofx_transactions (
    id VARCHAR(255) PRIMARY KEY,
    date DATE,
    type VARCHAR(50),
    amount DECIMAL(19, 4),
    memo TEXT,
    account_type VARCHAR(50),
    main_category VARCHAR(100),
    sub_category VARCHAR(100),
    FOREIGN KEY (main_category, sub_category) REFERENCES transaction_categories(main_category, sub_category)
);
'''

def _get_ddl_statements_from_string(ddl_string):
    """Cleans and splits DDL statements from a string."""
    statements = [stmt.strip() for stmt in ddl_string.split(';') if stmt.strip()]
    cleaned_statements = []
    for stmt in statements:
        if stmt.lower().startswith("use ") or not stmt:
            continue
        cleaned_statements.append(stmt)
    return cleaned_statements

def create_tables_from_ddl(target_db_arg="local"):
    """Creates tables in the specified database using embedded DDL statements.
    
    Special handling: Preserves asset_price table data by skipping DROP statements for this table.
    """
    if not db_connect:
        print("Error: db_connect function not available. Cannot create tables.")
        return False
        
    print(f"Attempting to connect to '{target_db_arg}' database for table creation...")
    conn = None
    try:
        conn = db_connect(target_db=target_db_arg)
        cursor = conn.cursor()
        print(f"Successfully connected to '{target_db_arg}' database for table creation.")

        print("Processing embedded DDL statements for table creation...")
        sql_statements = _get_ddl_statements_from_string(ALL_DDL_STATEMENTS)

        if not sql_statements:
            print("No SQL statements found in the embedded DDL.")
            return False

        print(f"Found {len(sql_statements)} SQL statements to execute for table creation.")

        preserved_tables = ['asset_price']  # Tables to preserve data for
        skipped_drops = []

        for stmt_index, sql in enumerate(sql_statements):
            sql_lower = sql.lower().strip()
            
            # Check if this is a DROP statement for a preserved table
            skip_statement = False
            for preserved_table in preserved_tables:
                if (sql_lower.startswith("drop table if exists") or sql_lower.startswith("drop table")) and preserved_table in sql_lower:
                    print(f"⚠️  SKIPPING DROP for preserved table '{preserved_table}': {sql[:60]}...")
                    skipped_drops.append(preserved_table)
                    skip_statement = True
                    break
            
            if skip_statement:
                continue
                
            print(f"Executing DDL statement {stmt_index + 1}/{len(sql_statements)}: {sql[:100]}{'...' if len(sql) > 100 else ''}")
            try:
                cursor.execute(sql)
                if not sql.lower().startswith("drop"):
                    conn.commit()
                print(f"Successfully executed: {sql.split()[0]} {sql.split()[1] if len(sql.split()) > 1 else ''}...")
            except (sqlite3.OperationalError, mysql.connector.Error) as e:
                if "already exists" in str(e).lower() or ("1050" in str(e)):
                    print(f"  Info: Table already exists or similar issue (ignored for CREATE): {sql.split()[2] if len(sql.split()) > 2 else sql}")
                elif ("no such table" in str(e).lower() or "unknown table" in str(e).lower() or ("1051" in str(e))):
                     print(f"  Info: Table not found or similar issue (ignored for DROP): {sql.split()[2] if len(sql.split()) > 2 else sql}")
                else:
                    print(f"  Error executing DDL statement: {sql}")
                    print(f"  Database error: {e}")
        
        # Summary of preserved tables
        if skipped_drops:
            print(f"\n✅ Preserved data in tables: {', '.join(skipped_drops)}")
        
        print("\nTable creation DDL execution completed.")
        return True

    except (sqlite3.Error, mysql.connector.Error, ValueError) as e:
        print(f"Database connection or DDL setup error: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during DDL execution: {e}")
        return False
    finally:
        if conn:
            conn.close()
            print(f"Database connection for '{target_db_arg}' (table creation) closed.")


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

def reset_local_database():
    """
    Drops the existing local SQLite database file (if it exists) 
    and then recreates it as an empty database.
    """
    try:
        current_script_path = os.path.dirname(__file__)
        project_root = os.path.abspath(os.path.join(current_script_path, '..', '..'))
        db_dir = os.path.join(project_root, 'resources', 'db')
        db_path = os.path.join(db_dir, 'cajubills_local.db')

        if os.path.exists(db_path):
            print(f"Local database file found at {db_path}. Attempting to delete...")
            os.remove(db_path)
            print(f"Successfully deleted existing database file: {db_path}")
        else:
            print(f"No existing local database file found at {db_path}. Proceeding to create.")
        
        # Recreate the database (directory and empty file)
        new_db_path = create_local_database()
        if new_db_path:
            print(f"Successfully reset and recreated local database at: {new_db_path}")
            return new_db_path
        else:
            print("Failed to recreate the local database after attempting reset.")
            return None

    except Exception as e:
        print(f"Error resetting local database: {e}")
        return None

if __name__ == '__main__':
    print("Attempting to create local database...")
    created_db_path = create_local_database()
    if created_db_path:
        print(f"Script finished. Database should be at: {created_db_path}")
    else:
        print("Script finished. Database creation failed.")

    # Example of how to use reset_local_database (optional, can be commented out)
    # print("\nAttempting to reset local database...")
    # reset_db_path = reset_local_database()
    # if reset_db_path:
    #     print(f"Script finished. Database reset and should be at: {reset_db_path}")
    # else:
    #     print("Script finished. Database reset failed.") 