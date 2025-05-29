from datetime import datetime, timedelta

from .constants import NU_PRICES


def _prepare_date_dimension_and_nu_prices(cursor):
    print("Defining date range for 'dates' table (2018-01-01 to today)...")
    start_date_obj = datetime(2018, 1, 1)
    end_date_obj = datetime.today()

    date_list = []
    current_date_iter = start_date_obj
    while current_date_iter <= end_date_obj:
        date_list.append((current_date_iter.date(),))
        current_date_iter += timedelta(days=1)
    print(f"Created date list with {len(date_list)} dates.")

    print(f"Inserting {len(NU_PRICES)} NU price records into asset_price...")
    cursor.executemany(
        """
        INSERT OR IGNORE INTO asset_price(ticker, quote_date, open_price, close_price)
        VALUES(?, ?, ?, ?)
        """, NU_PRICES)
    print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(NU_PRICES)} NU price records.")

    print(f"Inserting {len(date_list)} records into 'dates' table...")
    cursor.executemany(
        "INSERT OR IGNORE INTO dates(date) VALUES(?)",
        date_list
    )
    print(f"Processed {cursor.rowcount if cursor.rowcount != -1 else len(date_list)} records for 'dates' table.")


def _populate_daily_asset_price(cursor):
    print("Deleting from daily_asset_price...")
    cursor.execute("DELETE FROM daily_asset_price")
    print("Populating daily_asset_price...")
    cursor.execute(
        """
        INSERT OR IGNORE INTO daily_asset_price(ticker, date, price)
        WITH date_range AS
        (
            SELECT
                ticker,
                quote_date,
                LEAD(quote_date) OVER(PARTITION BY ticker ORDER BY quote_date) as next_date,
                close_price
            FROM asset_price ap
        )
        SELECT
            ticker,
            COALESCE(d.date, quote_date) as date,
            close_price as price
        FROM date_range dr
        LEFT JOIN dates d
        ON d.date >= dr.quote_date AND d.date < dr.next_date
        """
    )
    print(f"Populated daily_asset_price. Rows affected: {cursor.rowcount}")


def _populate_variable_income_daily_balance(cursor):
    print("Deleting from variable_income_daily_balance...")
    cursor.execute("DELETE FROM variable_income_daily_balance")
    print("Populating variable_income_daily_balance...")
    cursor.execute(
        """
        INSERT INTO variable_income_daily_balance
        WITH dolar AS(
            SELECT date, price as dolar_price
            FROM daily_asset_price
            WHERE ticker = "BRL=X"
        ),
        currency AS (
            SELECT ticker, MAX(currency) as currency
            FROM variable_income_operations
            GROUP BY ticker
        ),
        operation AS (
            SELECT 	
                ticker,
                currency,
                operation_date,
                LEAD(operation_date) OVER (PARTITION BY ticker ORDER BY operation_date) AS next_operation_date,
                SUM(CASE WHEN operation_type = "buy" THEN amount else amount * -1 END) AS amount
            FROM variable_income_operations o
            GROUP BY ticker, currency, operation_date, operation_type
        ),
        balance AS (
            SELECT
                p.ticker,
                p.date,
                p.price,
                d.dolar_price,
                c.currency, 
                o.amount as amount_change,
                SUM(COALESCE(o.amount, 0)) OVER(PARTITION BY p.ticker ORDER BY p.date) AS amount
            FROM daily_asset_price p
            LEFT JOIN operation o
            ON p.ticker = o.ticker AND p.date = o.operation_date
            LEFT JOIN dolar d
            ON d.date = p.date
            INNER JOIN currency c
            ON c.ticker = p.ticker 
        )
        SELECT
            b.ticker,
            b.date,
            b.price,
            b.dolar_price,
            b.currency,
            b.amount_change,
            b.amount,
            CASE WHEN b.currency = "dolar" THEN (b.price * b.dolar_price) * b.amount ELSE b.price * b.amount END as value
        FROM balance b
        WHERE b.amount <> 0;
        """
    )
    print(f"Populated variable_income_daily_balance. Rows affected: {cursor.rowcount}")


def _populate_fixed_income_non_tesouro_selic(cursor):
    print("Deleting from fixed_income_daily_balance (this step only handles non-Tesouro Selic)...")
    # Note: This deletion might be too broad if _process_tesouro_selic_operations appends.
    # Consider if Tesouro Selic data should be deleted here or specifically before its insertion.
    # For now, assuming this is the primary population step for the table before Tesouro Selic.
    cursor.execute("DELETE FROM fixed_income_daily_balance")
    print("Populating fixed_income_daily_balance (Part 1: Non-Tesouro Selic)...")
    cursor.execute(
        """
         INSERT INTO fixed_income_daily_balance
         WITH base_ipca AS(
                SELECT 
                    financial_index,
                    date,
                    COALESCE(lead(date) OVER (PARTITION BY financial_index ORDER BY date), "2099-01-01") AS next_date,
                factor
            FROM index_series
            WHERE financial_index = "ipca"
        ), daily_indexes AS(
            SELECT 
                ipca.financial_index,
                i.date,
                1 + ipca.factor/100/21 AS factor
            FROM index_series i
            INNER JOIN base_ipca ipca
            ON i.date >= ipca.date and i.date < ipca.next_date
            WHERE i.financial_index = "cdi"
            UNION
            SELECT financial_index, date, factor
            FROM index_series 
            WHERE financial_index <> "ipca"
        ), daily_rates AS (
            SELECT 
                i.date,
                i.factor,
                op.asset,
                op.purchase_date,
                op.value,
                op.pre_rate,
                op.post_rate,
                op.due_date,
                op.tax_rate,
                op.is_pgbl,
                pow((1.0 + pre_rate),(1.0/252)) -1 as daily_pre_rate,
                (op.post_rate * (i.factor - 1) + 1) as daily_post_rate,
                pow((1.0 + pre_rate),(1.0/252)) -1 + (op.post_rate * (i.factor - 1) + 1) as total_daily_rate,
                EXP(SUM(LN(pow((1.0 + pre_rate),(1.0/252)) -1  + (op.post_rate * (i.factor - 1) + 1))) OVER (PARTITION BY op.asset, op.purchase_date ORDER BY i.date)) AS cumulative_daily_rate
            FROM fixed_income_operations op
            INNER JOIN daily_indexes i
            ON op.financial_index = i.financial_index
            AND i.date BETWEEN op.purchase_date AND op.due_date
            WHERE op.asset NOT LIKE "%Tesouro Selic%"
        ), grouped AS (
            SELECT 
                asset,
                due_date,
                date,
                tax_rate,
                SUM(value) as deposit_value,
                SUM(cumulative_daily_rate * value) AS gross_value,
                SUM(CASE WHEN is_pgbl THEN cumulative_daily_rate * value * tax_rate ELSE (cumulative_daily_rate * value - value) * tax_rate END) AS tax_value,
                SUM(cumulative_daily_rate * value - CASE WHEN is_pgbl THEN cumulative_daily_rate * value * tax_rate ELSE (cumulative_daily_rate * value - value) * tax_rate END) AS net_value
            FROM daily_rates
            GROUP BY asset, date, due_date, tax_rate
        ), values_range AS(
             SELECT 
                asset,
                due_date,
                date,
                COALESCE (lead(date) OVER (PARTITION BY asset ORDER BY date), due_date) next_date,
                tax_rate,
                deposit_value,
                gross_value,
                tax_value,
                net_value
            FROM grouped
        )
        SELECT r.asset, r.due_date, d.date, r.tax_rate, r.deposit_value, r.gross_value, r.tax_value, r.net_value
        FROM dates d
        INNER JOIN values_range r
        ON d.date >= r.date and d.date < next_date 
        ORDER BY d.date DESC
        """
    )
    print(f"Populated fixed_income_daily_balance (Part 1). Rows affected: {cursor.rowcount}")


def _process_tesouro_selic_operations(cursor):
    print("Fetching Tesouro Selic operations for manual processing...")
    cursor.execute("""
        WITH operations AS (
            SELECT
                asset,
                purchase_date,
                due_date,
                COALESCE (lead(purchase_date) OVER (PARTITION BY asset ORDER BY purchase_date), due_date) AS next_date,
                CASE operation_type WHEN "buy" THEN quotas ELSE quotas * -1 END quotas,
                CASE operation_type WHEN "buy" THEN value ELSE value * -1 END value
            FROM fixed_income_operations
            WHERE asset like "%Tesouro Selic%"
        )
        SELECT asset, i.date, due_date, i.factor, quotas, value
        FROM index_series i
        INNER JOIN operations o
        ON i.date >= o.purchase_date and i.date < o.next_date 
        WHERE i.financial_index = "cdi"
        ORDER BY asset, i.date
    """)
    all_rows = cursor.fetchall()
    print(f"Fetched {len(all_rows)} rows for Tesouro Selic processing.")

    previous_asset = ""
    quota_balance = 0
    balance = 0
    compound_values = []
    previous_purchase_value = 0
    print("Processing Tesouro Selic data to calculate compounded values...")
    for i, (asset, date_val, due_date_val, factor, quota, value) in enumerate(all_rows):
        if asset != previous_asset:
            previous_asset = asset
            quota_balance = quota
            balance = value
            previous_purchase_value = value
        else:
            if previous_purchase_value != value:
                balance = balance + value
                previous_purchase_value = value
                quota_balance += quota

            if quota_balance > 0:
                new_balance = balance * factor
                balance = new_balance
            else:
                balance = 0

        if (balance > 0):
            compound_values.append(
                (previous_asset, due_date_val, date_val, 0.0, previous_purchase_value, balance, 0, balance))
    print(f"Finished processing Tesouro Selic data. {len(compound_values)} compounded values to insert.")

    if compound_values:
        print("Inserting compounded Tesouro Selic values into fixed_income_daily_balance...")
        # This appends to fixed_income_daily_balance. Ensure previous step doesn't conflict.
        cursor.executemany(
            """
            INSERT INTO fixed_income_daily_balance(asset, due_date, date, tax_rate, deposit_value, gross_value, tax_value, net_value)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            compound_values
        )
        print(
            f"Inserted {cursor.rowcount if cursor.rowcount != -1 else len(compound_values)} Tesouro Selic compounded records.")
    else:
        print("No Tesouro Selic compounded values to insert.")


def _populate_fgts_daily_balance(cursor):
    print("Deleting from fgts_daily_balance...")
    cursor.execute("DELETE FROM fgts_daily_balance")
    print("Populating fgts_daily_balance...")
    cursor.execute("""
    INSERT INTO fgts_daily_balance
    WITH fgts_by_company AS(
        SELECT strftime('%Y', date) as year, strftime('%m', date) as month, company, max(balance) as balance
        FROM fgts_operations    
        GROUP BY strftime('%Y', date), strftime('%m', date), company
     ), fgts_by_date AS (
        SELECT date(year || '-' || printf('%02d', month) || '-01') AS date, sum(balance) as balance, count(*) as companies
        FROM fgts_by_company    
        GROUP BY date
        HAVING count(*) > 1
    ), fgts_range AS (
        SELECT date, COALESCE(LEAD(date) OVER (ORDER BY date), "2099-01-01") as next_date, balance
        FROM fgts_by_date 
    )
    SELECT d.date, f.balance
    FROM dates d
    INNER JOIN fgts_range f
    ON d.date >= f.date and d.date < f.next_date
""")
    print(f"Populated fgts_daily_balance. Rows affected: {cursor.rowcount}")


def _populate_daily_balance_summary(cursor):
    print("Deleting from daily_balance...")
    cursor.execute("DELETE FROM daily_balance")
    print("Populating daily_balance...")
    cursor.execute("""
    INSERT INTO daily_balance
    WITH daily_balances_cte AS
    (
        SELECT
            ticker,
            date,
            value,
            'equity' as type
        FROM variable_income_daily_balance
        WHERE date <= (SELECT max(date) FROM fixed_income_daily_balance)
        UNION
        SELECT
            asset as ticker,
            date,
            net_value as value,
            'fixed_income' as type
        FROM fixed_income_daily_balance
        WHERE date <= (SELECT max(date) FROM variable_income_daily_balance)
    )
    SELECT ticker, date, value, type
    FROM daily_balances_cte
""")
    print(f"Populated daily_balance. Rows affected: {cursor.rowcount}")


def _populate_operations_summary(cursor):
    print("Deleting from operations...")
    cursor.execute("DELETE FROM operations")
    print("Populating operations...")
    cursor.execute("""
    INSERT INTO operations
    WITH all_operations AS(
        SELECT
            asset,
            operation_type, purchase_date as operation_date,
            CASE WHEN operation_type = "buy" THEN value ELSE value * -1 END value,
            "real" as currency
        FROM fixed_income_operations
        UNION ALL
        SELECT
            ticker,
            operation_type,
            operation_date,
            amount * price * (CASE operation_type WHEN "buy" THEN 1 ELSE -1 END) AS value,
            currency
        FROM variable_income_operations
    )
    SELECT o.asset,
        o.operation_type,
        o.operation_date,
        CASE o.currency WHEN "dolar" THEN d.price * o.value ELSE o.value END AS value,
        o.currency,
        d.price as dolar_price
    FROM all_operations o
    LEFT JOIN daily_asset_price d
    ON d.ticker = "BRL=X" AND d.date = o.operation_date
    ORDER BY operation_date DESC
""")
    print(f"Populated operations. Rows affected: {cursor.rowcount}")


def _populate_financial_returns(cursor):
    print("Deleting from financial_returns...")
    cursor.execute("DELETE FROM financial_returns")
    print("Populating financial_returns...")
    cursor.execute("""
    INSERT INTO financial_returns
    WITH deposits AS
    (
        SELECT asset, CAST(strftime('%Y', operation_date) AS INTEGER) AS year, CAST(strftime('%m', operation_date) AS INTEGER) AS month, sum(value) deposit
        FROM operations
        GROUP BY asset, strftime('%Y', operation_date), strftime('%m', operation_date)
    ),
    balance_by_asset AS (
        SELECT asset, date, SUM(value) as value
        FROM daily_balance
        GROUP BY asset, date
    ),
    balance AS (
        SELECT asset, date, value, lag(value) OVER (PARTITION BY asset ORDER by date) as lag_value, lag(date) OVER (PARTITION BY asset ORDER by date) AS lag_date,
        ROW_NUMBER () OVER (PARTITION BY asset, strftime('%Y', date), strftime('%m', date) ORDER BY date) as r
        FROM balance_by_asset
    ),
    summary AS (
        SELECT
            b.asset,
            CAST(strftime('%Y', b.date) AS INTEGER) as year,
            CAST(strftime('%m', b.date) AS INTEGER) as month,
            b.value,
            COALESCE (b.lag_value, 0) as lag_value,
            lead(b.lag_value) OVER (PARTITION BY b.asset ORDER BY b.date) as next_value,
            COALESCE (d.deposit, 0) AS deposit
        FROM balance b
        LEFT JOIN deposits d
        ON d.year = CAST(strftime('%Y', b.date) AS INTEGER)
        AND d.month = CAST(strftime('%m', b.date) AS INTEGER)
        AND d.asset = b.asset
        WHERE b.r = 1
    )
    SELECT s.asset, s.year, s.month,
        s.lag_value as month_start_value,
        s.next_value as month_end_value,
        s.deposit,
        s.next_value - s.lag_value as net_increase, 
        s.next_value - s.lag_value - s.deposit as profit,
        (s.next_value - s.lag_value - s.deposit) / s.lag_value * 100 as relative_return
    FROM summary s
    WHERE s.next_value IS NOT NULL 
    ORDER by s.year DESC, s.month DESC
""")
    print(f"Populated financial_returns. Rows affected: {cursor.rowcount}")


def _populate_summary_returns(cursor):
    print("Deleting from summary_returns...")
    cursor.execute("DELETE FROM summary_returns")
    print("Populating summary_returns...")
    cursor.execute("""
    INSERT INTO summary_returns
    WITH summary AS (
        SELECT
            year,
            month,
            SUM(month_end_value) as month_end_value,
            SUM(deposit) AS total_deposit,
            SUM(profit) AS total_profit,
            SUM(profit) / SUM(month_start_value) * 100 as total_return
        FROM financial_returns
        GROUP BY year, month
    )
    SELECT
        year, 
        month,
        month_end_value,
        total_deposit,
        total_profit,
        total_return,
        AVG(SUM(total_deposit)) OVER (ORDER BY year, month ROWS BETWEEN 3 PRECEDING AND CURRENT ROW),
        AVG(SUM(total_profit)) OVER (ORDER BY year, month ROWS BETWEEN 3 PRECEDING AND CURRENT ROW),
        AVG(SUM(total_return)) OVER (ORDER BY year, month ROWS BETWEEN 3 PRECEDING AND CURRENT ROW),
        AVG(SUM(total_deposit)) OVER (ORDER BY year, month ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
        AVG(SUM(total_profit)) OVER (ORDER BY year, month ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
        AVG(SUM(total_return)) OVER (ORDER BY year, month ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
        AVG(SUM(total_deposit)) OVER (ORDER BY year, month ROWS BETWEEN 9 PRECEDING AND CURRENT ROW),
        AVG(SUM(total_profit)) OVER (ORDER BY year, month ROWS BETWEEN 9 PRECEDING AND CURRENT ROW),
        AVG(SUM(total_return)) OVER (ORDER BY year, month ROWS BETWEEN 9 PRECEDING AND CURRENT ROW),
        AVG(SUM(total_deposit)) OVER (ORDER BY year, month ROWS BETWEEN 12 PRECEDING AND CURRENT ROW),
        AVG(SUM(total_profit)) OVER (ORDER BY year, month ROWS BETWEEN 12 PRECEDING AND CURRENT ROW),
        AVG(SUM(total_return)) OVER (ORDER BY year, month ROWS BETWEEN 12 PRECEDING AND CURRENT ROW)
    FROM summary
    GROUP BY
        year,
        month,
        total_deposit, 
        total_profit, 
        total_return,
        month_end_value
""")
    print(f"Populated summary_returns. Rows affected: {cursor.rowcount}")


def preprocess_data(conn):
    print("Starting data preprocessing (preprocess_data)...")
    cursor = conn.cursor()
    print("Database cursor obtained for preprocessing.")

    _prepare_date_dimension_and_nu_prices(cursor)
    _populate_daily_asset_price(cursor)
    _populate_variable_income_daily_balance(cursor)
    _populate_fixed_income_non_tesouro_selic(cursor)
    _process_tesouro_selic_operations(cursor)
    _populate_fgts_daily_balance(cursor)
    _populate_daily_balance_summary(cursor)
    _populate_operations_summary(cursor)
    _populate_financial_returns(cursor)
    _populate_summary_returns(cursor)

    print("Committing preprocessed data changes...")
    conn.commit()
    print("Data preprocessing finished.")
