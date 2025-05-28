import argparse
import os
import sys
import sqlite3 # For specific SQLite error handling
import mysql.connector # For specific MySQL error handling

# Add project root to Python path to allow importing from src
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src.sql.connection import db_connect
except ImportError:
    print("Error: Could not import db_connect from src.sql.connection.")
    print(f"Current sys.path: {sys.path}")
    print(f"Project root calculated as: {project_root}")
    sys.exit(1)

# Embedded DDL statements
ALL_DDL_STATEMENTS = '''
use finance;

DROP TABLE fixed_income_operations ;
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

DROP TABLE variable_income_operations;
CREATE TABLE variable_income_operations (
  ticker varchar(50) NOT NULL,
  operation_type varchar(10) NOT NULL,
  operation_date date NOT NULL,
  amount double NOT NULL,
  price double NOT NULL,
  currency varchar(50) DEFAULT NULL,
  PRIMARY KEY (ticker, operation_type, operation_date, amount, price)
);

DROP TABLE asset_price;
CREATE TABLE asset_price (
    ticker VARCHAR(50),
    quote_date DATE,
    open_price DOUBLE,
    close_price DOUBLE,
    PRIMARY KEY (ticker, quote_date)
);

DROP TABLE daily_asset_price;
CREATE TABLE daily_asset_price (
    ticker VARCHAR(50),
    date DATE,
    price DOUBLE,
    PRIMARY KEY (ticker, date)
);

DROP TABLE dates;
CREATE TABLE dates (
    date DATE,
    PRIMARY KEY (date)
);

DROP TABLE variable_income_daily_balance;
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

CREATE TABLE index_series(
    financial_index varchar(30),
    date DATE,
    factor DOUBLE,
    PRIMARY KEY (financial_index, date)
);

DROP TABLE fixed_income_daily_balance ;
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

DROP TABLE daily_balance ;
CREATE TABLE daily_balance (
	asset VARCHAR(50),
	date DATE,
	value DOUBLE,
	type VARCHAR(50),
	PRIMARY KEY (asset, type, date)
);

DROP TABLE fgts_operations;
CREATE TABLE fgts_operations (
    date DATE,
    company VARCHAR(50),
    operation VARCHAR(50),
    value DOUBLE,
    balance DOUBLE,
    PRIMARY KEY (date, company, operation)
);

DROP TABLE fgts_daily_balance;
CREATE TABLE fgts_daily_balance (
    date DATE,
    balance DOUBLE,
    PRIMARY KEY (date)
);

DROP TABLE operations;
CREATE TABLE operations (
 asset VARCHAR(50),
 operation_type VARCHAR(50),
 operation_date DATE,
 value DOUBLE,
 currency VARCHAR(50),
 dolar_price DOUBLE
);

DROP TABLE financial_returns;
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

DROP TABLE summary_returns;
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

DROP TABLE target_percentage;
CREATE TABLE target_percentage(
    name VARCHAR(50),
    percentage DOUBLE,
    PRIMARY KEY (name)
);

DROP TABLE transaction_categories;
CREATE TABLE transaction_categories (
    main_category VARCHAR(100) NOT NULL,
    sub_category VARCHAR(100) NOT NULL,
    PRIMARY KEY (main_category, sub_category)
);

DROP TABLE ofx_transactions;
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

def get_embedded_ddl_statements():
    """Cleans and splits the embedded DDL statements."""
    # Simple split by semicolon
    statements = [stmt.strip() for stmt in ALL_DDL_STATEMENTS.split(';') if stmt.strip()]
    
    # Filter out 'USE database;' statements and empty statements
    cleaned_statements = []
    for stmt in statements:
        if stmt.lower().startswith("use ") or not stmt:
            continue
        cleaned_statements.append(stmt)
    return cleaned_statements

def create_tables(target_db_arg):
    """Creates tables in the specified database using embedded DDL statements."""
    print(f"Attempting to connect to '{target_db_arg}' database...")
    conn = None
    try:
        conn = db_connect(target_db=target_db_arg)
        cursor = conn.cursor()
        print(f"Successfully connected to '{target_db_arg}' database.")

        print("Processing embedded DDL statements...")
        sql_statements = get_embedded_ddl_statements()

        if not sql_statements:
            print("No SQL statements found in the embedded DDL.")
            return

        print(f"Found {len(sql_statements)} SQL statements to execute.")

        for stmt_index, sql in enumerate(sql_statements):
            print(f"Executing statement {stmt_index + 1}/{len(sql_statements)}: {sql[:100]}{'...' if len(sql) > 100 else ''}")
            try:
                cursor.execute(sql)
                if not sql.lower().startswith("drop"): 
                    conn.commit() 
                print(f"Successfully executed: {sql.split()[0]} {sql.split()[1] if len(sql.split()) > 1 else ''}...")
            except (sqlite3.OperationalError, mysql.connector.Error) as e:
                if "no such table" in str(e).lower() or \
                   "unknown table" in str(e).lower() or \
                   ("1051" in str(e) and "unknown table" in str(e).lower()): 
                    print(f"  Info: Table not found for DROP statement (ignored): {sql.split()[2] if len(sql.split()) > 2 else sql}")
                elif sql.lower().startswith("drop table") and "1051" in str(e): 
                     print(f"  Info: Could not drop table (might not exist or other issue): {e}")
                elif "already exists" in str(e).lower() or \
                     ("1050" in str(e) and "table" in str(e).lower() and "already exists" in str(e).lower()): 
                    print(f"  Info: Table already exists for CREATE statement (ignored): {sql.split()[2] if len(sql.split()) > 2 else sql}")
                else:
                    print(f"  Error executing statement: {sql}")
                    print(f"  Database error: {e}")
        
        print("\nTable creation process completed.")

    except (sqlite3.Error, mysql.connector.Error, ValueError) as e:
        print(f"Database connection or setup error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create database tables from embedded DDL SQL.")
    parser.add_argument(
        "--target_db",
        type=str,
        default="local",
        choices=["local", "remote"],
        help="The target database ('local' for SQLite, 'remote' for MySQL). Default is 'local'."
    )
    # The --ddl_file argument is no longer needed as DDL is embedded.
    # Keep this comment to note its removal.
    # parser.add_argument(
    #     "--ddl_file",
    #     type=str,
    #     default=os.path.join(project_root, "src", "sql", "ddl", "tables.sql"),
    #     help="Path to the DDL SQL file. Defaults to 'src/sql/ddl/tables.sql' relative to project root."
    # )

    args = parser.parse_args()
    
    create_tables(args.target_db) 