import yfinance as yf
import pandas as pd
from datetime import datetime, date, timedelta

def get_missing_data_ranges(conn):
    """
    Analyze local database to determine what asset price data is missing.
    
    Returns:
        dict: {ticker: {'min_operation_date': date, 'last_price_date': date or None, 'needs_update': bool}}
    """
    cursor = conn.cursor()
    
    # Get all tickers and their minimum operation dates
    cursor.execute("SELECT ticker, MIN(operation_date) FROM variable_income_operations GROUP BY ticker")
    operation_tickers = cursor.fetchall()
    
    # Add BRL=X for currency data
    all_required_tickers = dict(operation_tickers)
    all_required_tickers['BRL=X'] = datetime(2018, 1, 1).date()
    
    missing_data = {}
    today = date.today()
    
    for ticker, min_operation_date in all_required_tickers.items():
        # Check what price data we already have for this ticker
        cursor.execute("""
            SELECT MIN(quote_date) as first_date, MAX(quote_date) as last_date, COUNT(*) as record_count
            FROM asset_price 
            WHERE ticker = ?
        """, (ticker,))
        
        result = cursor.fetchone()
        first_date, last_date, record_count = result
        
        # Convert string dates to date objects if needed
        if first_date:
            if isinstance(first_date, str):
                first_date = datetime.strptime(first_date, '%Y-%m-%d').date()
            if isinstance(last_date, str):
                last_date = datetime.strptime(last_date, '%Y-%m-%d').date()
        
        # Determine if we need to update this ticker
        needs_update = False
        update_reason = ""
        
        if record_count == 0:
            # No data at all
            needs_update = True
            update_reason = "No price data found"
            start_date = min_operation_date
        else:
            # Check if we need more recent data (missing last 7 days)
            days_behind = (today - last_date).days if last_date else 999
            if days_behind > 7:
                needs_update = True
                update_reason = f"Data is {days_behind} days old"
                # Start from the day after our last data
                start_date = last_date + timedelta(days=1)
            else:
                update_reason = f"Up to date (last: {last_date})"
                start_date = None
        
        missing_data[ticker] = {
            'min_operation_date': min_operation_date,
            'last_price_date': last_date,
            'record_count': record_count,
            'needs_update': needs_update,
            'update_reason': update_reason,
            'start_date': start_date
        }
        
        print(f"📊 {ticker:<12} | Records: {record_count:>4} | Last: {last_date or 'None':<10} | {update_reason}")
    
    return missing_data

def update_asset_price(conn):
    print("Starting smart asset price update process...")
    print("🔍 Analyzing existing data to determine what needs updating...")
    
    # First, analyze what data we already have
    missing_data_analysis = get_missing_data_ranges(conn)
    
    # Filter to only tickers that need updates
    tickers_to_update = {k: v for k, v in missing_data_analysis.items() if v['needs_update']}
    
    print(f"\n📋 Update Summary:")
    print(f"   Total tickers: {len(missing_data_analysis)}")
    print(f"   Need updates: {len(tickers_to_update)}")
    print(f"   Already current: {len(missing_data_analysis) - len(tickers_to_update)}")
    
    if not tickers_to_update:
        print("✅ All asset price data is current! No updates needed.")
        return
    
    print(f"\n🔄 Updating {len(tickers_to_update)} tickers...")
    
    cursor = conn.cursor()
    successful_tickers = []
    failed_tickers = []

    for ticker, info in tickers_to_update.items():
        start_date = info['start_date']
        start_date_str = start_date.strftime('%Y-%m-%d')
        
        print(f"\n📈 Processing {ticker} from {start_date_str} ({info['update_reason']})...")
        
        try:
            # Create ticker object and download data
            ticker_obj = yf.Ticker(ticker)
            df = ticker_obj.history(start=start_date_str, raise_errors=True)
            
            if df.empty:
                print(f"⚠️  No new data available for {ticker}")
                failed_tickers.append((ticker, "No new data available"))
                continue
            
            # Process the data
            df = df.reset_index()
            
            # Handle different column names that yfinance might return
            if 'Date' not in df.columns and df.index.name == 'Date':
                df = df.reset_index()
            
            # Ensure we have required columns
            required_cols = ['Date', 'Open', 'Close']
            if not all(col in df.columns for col in required_cols):
                if 'Adj Close' in df.columns and 'Close' not in df.columns:
                    df['Close'] = df['Adj Close']
            
            if not all(col in df.columns for col in required_cols):
                print(f"⚠️  Missing required columns for {ticker}")
                failed_tickers.append((ticker, "Missing required columns"))
                continue
            
            df['ticker'] = ticker
            df['Date'] = pd.to_datetime(df['Date']).dt.date
            df = df[['ticker', 'Date', 'Open', 'Close']]
            
            # Filter out any dates we might already have (extra safety)
            if info['last_price_date']:
                df = df[df['Date'] > info['last_price_date']]
            
            if df.empty:
                print(f"✅ {ticker} is already up to date")
                successful_tickers.append(ticker)
                continue
            
            values = [tuple(x) for x in df.to_records(index=False)]
            
            print(f"💾 Inserting {len(values)} new price records for {ticker}...")
            cursor.executemany(
                """
                INSERT OR IGNORE INTO asset_price(ticker, quote_date, open_price, close_price)
                VALUES (?, ?, ?, ?)
                """,
                values
            )
            
            rows_affected = cursor.rowcount if cursor.rowcount != -1 else len(values)
            print(f"✅ Successfully added {rows_affected} new records for {ticker}")
            successful_tickers.append(ticker)
            
        except Exception as yf_error:
            error_msg = str(yf_error)
            
            # Handle different types of yfinance errors
            if any(keyword in error_msg.lower() for keyword in [
                "delisted", "no price data found", "no timezone found", "symbol may be delisted"
            ]):
                print(f"⚠️  {ticker} appears to be delisted or invalid. Skipping.")
                failed_tickers.append((ticker, f"Delisted/Invalid: {error_msg}"))
            elif any(keyword in error_msg.lower() for keyword in [
                "no data found", "no data available", "expecting value: line 1 column 1", "json decode error"
            ]):
                print(f"⚠️  No valid data found for {ticker}. Skipping.")
                failed_tickers.append((ticker, f"No data/JSON error: {error_msg}"))
            elif "404" in error_msg or "not found" in error_msg.lower():
                print(f"⚠️  {ticker} not found. Skipping.")
                failed_tickers.append((ticker, f"Not found: {error_msg}"))
            elif "rate limit" in error_msg.lower() or "too many requests" in error_msg.lower():
                print(f"⚠️  Rate limited for {ticker}. You may need to retry later.")
                failed_tickers.append((ticker, f"Rate limited: {error_msg}"))
            else:
                print(f"❌ Failed to download data for {ticker}: {error_msg}")
                failed_tickers.append((ticker, f"Download error: {error_msg}"))
    
    print("\n💾 Committing changes to database...")
    conn.commit()
    
    # Summary report
    print("\n" + "="*60)
    print("SMART ASSET PRICE UPDATE SUMMARY")
    print("="*60)
    print(f"📊 Tickers analyzed: {len(missing_data_analysis)}")
    print(f"📊 Required updates: {len(tickers_to_update)}")
    print(f"✅ Successfully updated: {len(successful_tickers)}")
    if successful_tickers:
        print(f"   {', '.join(successful_tickers)}")
    
    if failed_tickers:
        print(f"\n⚠️  Failed to update: {len(failed_tickers)} tickers")
        for ticker, reason in failed_tickers:
            print(f"   {ticker}: {reason}")
        print(f"\nNote: Failed tickers will be skipped in portfolio calculations.")
    
    print("="*60)
    print("Smart asset price update finished!")
    
    # Show current data status
    print(f"\n📈 Updated Data Status:")
    cursor.execute("SELECT ticker, COUNT(*) as records, MAX(quote_date) as latest_date FROM asset_price GROUP BY ticker ORDER BY ticker")
    current_status = cursor.fetchall()
    
    for ticker, record_count, latest_date in current_status:
        print(f"   {ticker:<12} | {record_count:>4} records | Latest: {latest_date}") 