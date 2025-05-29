from backend.investments.asset_pricing import update_asset_price
from backend.investments.preprocessing import preprocess_data
from backend.investments.raw_data import upsert_raw_data
# db_connect is no longer needed here as connection is passed in
# from sql.connection import db_connect 


def process_all(db_conn): # Modified to accept db_conn
    print("Starting entire data processing pipeline (process_all in investment.py)...")
    # conn = None # Connection is now passed as db_conn
    try:
        # print("Connecting to the database for the main process...")
        # conn = db_connect() # Connection is passed in
        # print("Database connection established.")
        print("Using provided database connection.")

        print("Calling upsert_raw_data from backend.investments.raw_data...")
        upsert_raw_data(db_conn) # Use passed-in db_conn
        print("upsert_raw_data finished.")

        print("Calling update_asset_price from backend.investments.asset_pricing...")
        update_asset_price(db_conn) # Use passed-in db_conn
        print("update_asset_price finished.")

        print("Calling preprocess_data from backend.investments.preprocessing...")
        preprocess_data(db_conn) # Use passed-in db_conn
        print("preprocess_data finished.")

    except Exception as e:
        print(f"An error occurred during the investments process_all pipeline: {e}")
        # Optionally re-raise the exception if the caller needs to handle it
        raise # Re-raise so run.py can see it if needed
    # finally:
        # The connection is managed by the caller (run.py), so no close here.
        # if conn:
            # print("Closing database connection for the main process.")
            # conn.close()
            # print("Database connection closed.")
    print("Entire investments data processing pipeline finished.")
