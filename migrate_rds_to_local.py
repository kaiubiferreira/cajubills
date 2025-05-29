#!/usr/bin/env python3
"""
One-off script to migrate asset_price data from RDS to local SQLite database.

Usage: python migrate_rds_to_local.py

This script will:
1. Connect to RDS and fetch all asset_price data
2. Connect to local SQLite and insert the data
3. Handle duplicates gracefully
"""

import sys
import os

# Add src to path to use existing connection system
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from sql.connection import db_connect
import pandas as pd

def migrate_asset_price_data():
    """
    Migrate asset_price data from RDS to local database
    """
    rds_conn = None
    local_conn = None
    
    try:
        print("🔗 Connecting to RDS database...")
        rds_conn = db_connect(target_db="remote")
        rds_cursor = rds_conn.cursor()
        
        print("📊 Fetching asset_price data from RDS...")
        rds_cursor.execute("SELECT ticker, quote_date, open_price, close_price FROM asset_price ORDER BY ticker, quote_date")
        rds_data = rds_cursor.fetchall()
        
        print(f"✅ Found {len(rds_data)} records in RDS asset_price table")
        
        if not rds_data:
            print("⚠️  No data found in RDS. Nothing to migrate.")
            return
        
        print("🔗 Connecting to local SQLite database...")
        local_conn = db_connect(target_db="local")
        local_cursor = local_conn.cursor()
        
        # Check if local table exists and has data
        try:
            local_cursor.execute("SELECT COUNT(*) FROM asset_price")
            local_count = local_cursor.fetchone()[0]
            print(f"📊 Local database currently has {local_count} asset_price records")
        except Exception:
            print("⚠️  Local asset_price table might not exist yet")
            local_count = 0
        
        print("💾 Inserting data into local database...")
        
        # Use INSERT OR IGNORE to handle duplicates gracefully
        insert_query = """
            INSERT OR IGNORE INTO asset_price (ticker, quote_date, open_price, close_price)
            VALUES (?, ?, ?, ?)
        """
        
        # Insert data in batches for better performance
        batch_size = 1000
        total_inserted = 0
        
        for i in range(0, len(rds_data), batch_size):
            batch = rds_data[i:i + batch_size]
            local_cursor.executemany(insert_query, batch)
            local_conn.commit()
            
            batch_inserted = local_cursor.rowcount if local_cursor.rowcount > 0 else len(batch)
            total_inserted += batch_inserted
            
            print(f"📝 Processed batch {i//batch_size + 1}: {len(batch)} records")
        
        # Final count check
        local_cursor.execute("SELECT COUNT(*) FROM asset_price")
        final_local_count = local_cursor.fetchone()[0]
        
        print("\n" + "="*60)
        print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
        print("="*60)
        print(f"📊 RDS records found: {len(rds_data)}")
        print(f"📊 Local records before: {local_count}")
        print(f"📊 Local records after: {final_local_count}")
        print(f"📊 Net records added: {final_local_count - local_count}")
        print("="*60)
        
        # Show sample of migrated data
        print("\n🔍 Sample of migrated data:")
        local_cursor.execute("SELECT ticker, quote_date, close_price FROM asset_price ORDER BY quote_date DESC LIMIT 5")
        sample_data = local_cursor.fetchall()
        
        for row in sample_data:
            ticker, date, price = row
            print(f"   {ticker:<10} {date} ${price:.2f}")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        print("💡 Make sure both databases are accessible and the local database has been initialized")
        raise
        
    finally:
        # Clean up connections
        if rds_conn:
            rds_conn.close()
            print("🔗 RDS connection closed")
        if local_conn:
            local_conn.close()
            print("🔗 Local connection closed")

def verify_migration():
    """
    Quick verification that the migration worked
    """
    try:
        print("\n🔍 Verifying migration...")
        
        # Count records in both databases
        rds_conn = db_connect(target_db="remote")
        rds_cursor = rds_conn.cursor()
        rds_cursor.execute("SELECT COUNT(*) FROM asset_price")
        rds_count = rds_cursor.fetchone()[0]
        rds_conn.close()
        
        local_conn = db_connect(target_db="local")
        local_cursor = local_conn.cursor()
        local_cursor.execute("SELECT COUNT(*) FROM asset_price")
        local_count = local_cursor.fetchone()[0]
        local_conn.close()
        
        print(f"✅ RDS has {rds_count} records")
        print(f"✅ Local has {local_count} records")
        
        if local_count >= rds_count:
            print("🎉 Migration verification PASSED!")
        else:
            print("⚠️  Local has fewer records than RDS - some data may not have migrated")
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting asset_price data migration from RDS to Local")
    print("="*60)
    
    try:
        migrate_asset_price_data()
        verify_migration()
        
        print("\n✅ Migration script completed successfully!")
        print("💡 You can now run your investment processing with local data")
        
    except KeyboardInterrupt:
        print("\n⚠️  Migration interrupted by user")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1) 