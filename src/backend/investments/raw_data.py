import os
import sys
import sqlite3 # For type checking
import mysql.connector # For type checking

from backend.investments.sheets import get_fixed_income, get_stock, get_fgts, get_cdi, get_ipca, get_target

sys.path.append(os.path.abspath(os.path.join('..', '..')))  # Adjusted for deeper structure if needed


def upsert_raw_data(conn):
    print("Starting raw data upsert process (upsert_raw_data)...")

    # Determine DB type and set appropriate INSERT command and placeholder
    is_sqlite = isinstance(conn, sqlite3.Connection)
    is_mysql = isinstance(conn, mysql.connector.connection.MySQLConnection)

    if is_sqlite:
        insert_command_prefix = "INSERT OR IGNORE INTO"
        placeholder = "?"
        print("Using SQLite syntax (INSERT OR IGNORE, '?' placeholder).")
    elif is_mysql:
        insert_command_prefix = "INSERT IGNORE INTO"
        placeholder = "%s"
        print("Using MySQL syntax (INSERT IGNORE, '%s' placeholder).")
    else:
        # Fallback or error if connection type is unknown
        print("Warning: Unknown database connection type. Defaulting to MySQL syntax for INSERT IGNORE.")
        insert_command_prefix = "INSERT IGNORE INTO"
        placeholder = "%s"
        # Or raise an error: raise TypeError("Unsupported database connection type")

    # Construct placeholders string based on number of columns, e.g., "(?, ?, ?)"
    def get_placeholders(count):
        return f"({', '.join([placeholder] * count)})"

    print("Fetching fixed income data...")
    fixed_income = get_fixed_income()
    print(f"Fetched {len(fixed_income)} fixed income records.")

    print("Fetching variable income (stock) data...")
    variable_income = get_stock()
    print(f"Fetched {len(variable_income)} variable income records.")

    print("Fetching FGTS data...")
    fgts = get_fgts()
    print(f"Fetched {len(fgts)} FGTS records.")

    print("Fetching CDI data...")
    cdi = get_cdi()
    print(f"Fetched {len(cdi)} CDI records.")

    print("Fetching IPCA data...")
    ipca = get_ipca()
    print(f"Fetched {len(ipca)} IPCA records.")

    print("Fetching target data...")
    target = get_target()
    print(f"Fetched {len(target)} target records.")

    cursor = conn.cursor()
    print("Database cursor obtained for raw data upsert.")

    print("Deleting from variable_income_operations...")
    cursor.execute("DELETE FROM variable_income_operations")
    print("Inserting into variable_income_operations...")
    sql_vio = f"{insert_command_prefix} variable_income_operations(ticker, operation_type, operation_date, amount, price, currency) VALUES {get_placeholders(6)}"
    cursor.executemany(sql_vio, variable_income)
    print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(variable_income)} variable income operations.")

    print("Inserting CDI data into index_series...")
    # index_series table expects: financial_index, date, factor (3 columns)
    sql_cdi = f"{insert_command_prefix} index_series(financial_index, date, factor) VALUES {get_placeholders(3)}"
    cursor.executemany(sql_cdi, cdi)
    print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(cdi)} CDI records for index_series.")

    print("Inserting IPCA data into index_series...")
    # ipca data from sheets.py is (index, date, ipca_value) - assuming 'index' maps to financial_index
    sql_ipca = f"{insert_command_prefix} index_series(financial_index, date, factor) VALUES {get_placeholders(3)}"
    cursor.executemany(sql_ipca, ipca)
    print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(ipca)} IPCA records for index_series.")

    print("Deleting from fixed_income_operations...")
    cursor.execute("DELETE FROM fixed_income_operations")
    print("Inserting into fixed_income_operations...")
    # fixed_income_operations has 11 columns
    sql_fio = f"{insert_command_prefix} fixed_income_operations (asset, operation_type, quotas, purchase_date, due_date, financial_index, value, pre_rate, post_rate, tax_rate, is_pgbl) VALUES {get_placeholders(11)}"
    cursor.executemany(sql_fio, fixed_income)
    print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(fixed_income)} fixed income operations.")

    print("Deleting from fgts_operations...")
    cursor.execute("DELETE FROM fgts_operations")
    print("Inserting into fgts_operations...")
    # fgts_operations has 5 columns
    sql_fgts = f"{insert_command_prefix} fgts_operations (date, company, operation, value, balance) VALUES {get_placeholders(5)}"
    cursor.executemany(sql_fgts, fgts)
    print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(fgts)} FGTS operations.")

    print("Deleting from target_percentage...")
    cursor.execute("DELETE FROM target_percentage")
    print("Inserting into target_percentage...")
    # target_percentage has 2 columns
    sql_tp = f"{insert_command_prefix} target_percentage (name, percentage) VALUES {get_placeholders(2)}"
    cursor.executemany(sql_tp, target)
    print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(target)} target percentage records.")

    print("Committing raw data changes...")
    conn.commit()
    print("Raw data upsert process finished.")
