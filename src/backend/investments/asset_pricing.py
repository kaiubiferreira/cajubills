import yfinance as yf
import pandas as pd
from datetime import datetime, date

def update_asset_price(conn):
    print("Starting asset price update process (update_asset_price)...")
    cursor = conn.cursor()
    print("Fetching tickers and min_dates for asset price updates...")
    cursor.execute("SELECT ticker, MIN(operation_date) FROM variable_income_operations GROUP BY ticker")
    all_rows = cursor.fetchall() + [('BRL=X', datetime(2018, 1, 1).date())] # Ensure date object for BRL=X
    print(f"Found {len(all_rows)} ticker/min_date pairs for price updates (including BRL=X).")

    for ticker, min_date_obj in all_rows: # Renamed min_date to min_date_obj for clarity
        print(f"Processing ticker: {ticker}, starting from date: {min_date_obj}")
        try:
            # Ensure min_date_obj is a string in 'YYYY-MM-DD' format for yf.download
            # If min_date_obj is already a date/datetime object, strftime will work.
            # If it's a string from db that's not in YYYY-MM-DD, it might need parsing first.
            # Assuming dates from DB are date objects or YYYY-MM-DD strings.
            if isinstance(min_date_obj, (datetime, date)):
                start_date_str = min_date_obj.strftime('%Y-%m-%d')
            else:
                # Attempt to parse if it's a string, assuming 'YYYY-MM-DD' or similar
                # This part might need to be more robust if date formats vary
                try:
                    parsed_date = pd.to_datetime(min_date_obj).date()
                    start_date_str = parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    print(f"Could not parse date string '{min_date_obj}' for ticker {ticker}. Skipping.")
                    continue
            
            print(f"Downloading data for {ticker} from {start_date_str}...")
            df = yf.download(ticker, start=start_date_str, progress=False).reset_index()
            if df.empty:
                print(f"No data downloaded for ticker: {ticker}")
                continue
            print(f"Downloaded {len(df)} records for {ticker}.")
            df['ticker'] = ticker
            df = df[['ticker', 'Date', 'Open', 'Close']]
            df['Date'] = pd.to_datetime(df['Date']).dt.date
            values = [tuple(x) for x in df.to_records(index=False)]
            print(f"Inserting {len(values)} price records for {ticker} into asset_price...")
            cursor.executemany(
                """
                INSERT IGNORE INTO asset_price(ticker, quote_date, open_price, close_price)
                VALUES (%s, %s, %s, %s)
                """,
                values
            )
            print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(values)} price records for {ticker}.")
        except Exception as e:
            print(f"Error processing ticker {ticker}: {e}")
    print("Committing asset price changes...")
    conn.commit()
    print("Asset price update process finished.") 