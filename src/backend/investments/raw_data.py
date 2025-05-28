import os
import sys

from backend.investments.sheets import get_fixed_income, get_stock, get_fgts, get_cdi, get_ipca, get_target

sys.path.append(os.path.abspath(os.path.join('..', '..')))  # Adjusted for deeper structure if needed


def upsert_raw_data(conn):
    print("Starting raw data upsert process (upsert_raw_data)...")

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
    cursor.executemany(
        """
        INSERT IGNORE INTO variable_income_operations(ticker, operation_type, operation_date, amount, price, currency)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        variable_income
    )
    print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(variable_income)} variable income operations.")

    print("Inserting CDI data into index_series...")
    cursor.executemany(
        """
        INSERT IGNORE INTO index_series(financial_index, date, factor)
        VALUES (%s, %s, %s)
        """,
        cdi
    )
    print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(cdi)} CDI records for index_series.")

    print("Inserting IPCA data into index_series...")
    cursor.executemany(
        """
        INSERT IGNORE INTO index_series(financial_index, date, factor)
        VALUES (%s, %s, %s)
        """,
        ipca
    )
    print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(ipca)} IPCA records for index_series.")

    print("Deleting from fixed_income_operations...")
    cursor.execute("DELETE FROM fixed_income_operations")
    print("Inserting into fixed_income_operations...")
    cursor.executemany(
        """
        INSERT IGNORE INTO fixed_income_operations (asset, operation_type, quotas, purchase_date, due_date, financial_index, value, pre_rate, post_rate, tax_rate, is_pgbl)
        VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        fixed_income
    )
    print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(fixed_income)} fixed income operations.")

    print("Deleting from fgts_operations...")
    cursor.execute("DELETE FROM fgts_operations")
    print("Inserting into fgts_operations...")
    cursor.executemany(
        """
        INSERT IGNORE INTO fgts_operations (date, company, operation, value, balance)
        VALUES(%s, %s, %s, %s, %s)
        """,
        fgts
    )
    print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(fgts)} FGTS operations.")

    print("Deleting from target_percentage...")
    cursor.execute("DELETE FROM target_percentage")
    print("Inserting into target_percentage...")
    cursor.executemany(
        """
        INSERT IGNORE INTO target_percentage (name, percentage)
        VALUES(%s, %s)
        """,
        target
    )
    print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(target)} target percentage records.")

    print("Committing raw data changes...")
    conn.commit()
    print("Raw data upsert process finished.")
