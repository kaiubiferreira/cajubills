from backend.investments.asset_pricing import update_asset_price
from backend.investments.preprocessing import preprocess_data
from backend.investments.raw_data import upsert_raw_data
from sql.connection import db_connect


def process_all():
    print("Starting entire data processing pipeline (process_all)...")
    conn = None
    try:
        print("Connecting to the database for the main process...")
        conn = db_connect()
        print("Database connection established.")

        print("Calling upsert_raw_data from backend.investments.raw_data...")
        upsert_raw_data(conn)
        print("upsert_raw_data finished.")

        print("Calling update_asset_price from backend.investments.asset_pricing...")
        update_asset_price(conn)
        print("update_asset_price finished.")

        print("Calling preprocess_data from backend.investments.preprocessing...")
        preprocess_data(conn)
        print("preprocess_data finished.")

    except Exception as e:
        print(f"An error occurred during the process_all pipeline: {e}")
        # Optionally re-raise the exception if the caller needs to handle it
        # raise
    finally:
        if conn:
            print("Closing database connection for the main process.")
            conn.close()
            print("Database connection closed.")
    print("Entire data processing pipeline finished.")
