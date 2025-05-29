from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import os # For path adjustments if any are needed for constants from other locations

# Adjust path to import from backend and sql
import sys
# project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')) # Old incorrect path
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')) # Correct path to cajubills/src/
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from backend.investments.constants import EQUITY_TARGET, FIXED_INCOME_TARGET, BIRTH_DATE
from sql.connection import run_query # All run_query calls here default to local_db

# --- Copy all functions from history_dashboard.py here --- 
# (get_daily_balance, get_daily_balance_by_asset, ..., plot_summary, plot_history, etc.)

def get_daily_balance(start_date, end_date):
    query = (f"SELECT date, sum(value) as value "
             f"FROM daily_balance "
             f"WHERE date BETWEEN '{start_date}' AND '{end_date}' "
             f"GROUP BY date")
    return run_query(query, target_db="local") # Explicitly state local

def get_daily_balance_by_asset(start_date, end_date):
    query = (f"SELECT asset, date, value "
             f"FROM daily_balance "
             f"WHERE date BETWEEN '{start_date}' AND '{end_date}'")
    return run_query(query, target_db="local")

def get_daily_balance_by_type(start_date, end_date):
    query = (f"SELECT type, date, sum(value) as value "
             f"FROM daily_balance "
             f"WHERE date BETWEEN '{start_date}' AND '{end_date}' "
             f"GROUP BY type, date")
    df = run_query(query, target_db="local")
    if not df.empty:
        df['percentage'] = df.groupby('date')['value'].transform(
            lambda x: x / x.sum() * 100)
    return df

def get_dates():
    query = "SELECT MIN(date) AS start_date, MAX(date) AS end_date FROM daily_balance;"
    return run_query(query, target_db="local")

def get_summary_returns(start_date, end_date):
    # Assuming CONCAT and LPAD are fine for SQLite as they are common string functions
    # If not, this query might need adjustment for SQLite date/string formatting
    query = ("SELECT (year || '-' || PRINTF('%02d', month)) AS 'year_month', total_deposit, total_profit, "
             "moving_avg_profit_6, moving_avg_profit_12, moving_avg_deposit_6, moving_avg_deposit_12, "
             "total_return, moving_avg_return_6, moving_avg_return_12 "
             "FROM summary_returns "
             f"WHERE CAST(strftime('%Y', '{start_date}') AS INTEGER) <= year AND year <= CAST(strftime('%Y', '{end_date}') AS INTEGER)")
    monthly_returns = run_query(query, target_db="local")
    if not monthly_returns.empty:
        monthly_returns['total'] = monthly_returns['total_deposit'] + monthly_returns['total_profit']
        monthly_returns['deposit_percentage'] = (monthly_returns['total_deposit'] / monthly_returns['total']) * 100
        monthly_returns['profit_percentage'] = (monthly_returns['total_profit'] / monthly_returns['total']) * 100
    return monthly_returns

def get_summary_by_asset(start_date, end_date):
    query = ("SELECT asset, (year || '-' || PRINTF('%02d', month)) AS 'year_month', "
             "deposit, profit, net_increase "
             "FROM financial_returns "
             f"WHERE CAST(strftime('%Y', '{start_date}') AS INTEGER) <= year AND year <= CAST(strftime('%Y', '{end_date}') AS INTEGER)")
    return run_query(query, target_db="local")

def get_last_state():
    query = ("""
    WITH DATA
    AS(
        SELECT 
            asset, 
            value, 
            type, 
            COALESCE(percentage, 0) AS expected_percentage, -- Ensure percentage is not NULL for calcs
            (value / total_value) * 100 AS actual_percentage,
            CASE WHEN COALESCE(percentage, 0) > 0 THEN COALESCE(percentage, 0) - (value / total_value) * 100 ELSE 0 END AS diff,
            (COALESCE(percentage, 0) * total_value / 100.0) - value AS absolute_diff
        FROM daily_balance t1 
        INNER JOIN ( 
            SELECT MAX(date) AS max_date 
            FROM daily_balance 
        ) t2 ON t1.date = t2.max_date 
        LEFT JOIN target_percentage ON asset = name
        CROSS JOIN (
            SELECT SUM(value) AS total_value
            FROM daily_balance
            WHERE date = (SELECT MAX(date) FROM daily_balance)
        ) AS total
    ),
    POSITIVE_DIFF_TOTAL AS(
        SELECT sum(absolute_diff) as positive_diff
        FROM DATA
        WHERE absolute_diff > 0
    )
    SELECT
        asset,
        value,
        type,
        expected_percentage,
        actual_percentage,
        diff,
        absolute_diff,
        CASE WHEN positive_diff != 0 THEN (CASE WHEN absolute_diff > 0 THEN absolute_diff / positive_diff ELSE 0 END) ELSE 0 END AS diff_ratio
    FROM DATA
    CROSS JOIN POSITIVE_DIFF_TOTAL
    ORDER BY type, value DESC
    """)
    return run_query(query, target_db="local")

def get_last_results():
    query = ("""
        SELECT total_deposit, total_profit, total_return,
        moving_avg_deposit_12, moving_avg_profit_12, moving_avg_return_12
        FROM summary_returns
        ORDER BY year DESC, month DESC
        LIMIT 1 
    """)
    return run_query(query, target_db="local")

def format_currency(amount, currency_symbol) -> str:
    formatted_amount = f"{amount:,.2f}"
    return f"{currency_symbol} {formatted_amount}"

# --- Main page layout functions from history_dashboard --- 
st.set_page_config(layout="wide") # Already set in app.py, but can be page-specific too
st.title("Investments Dashboard")

# These functions will be called to render parts of the page
def plot_last_results_section(): # Renamed to avoid conflict if main.py had plot_last_results
    st.header("Current Snapshot: Last Results")
    df = get_last_results()
    if df.empty:
        st.warning("No summary results found to display.")
        return

    total_deposit = df['total_deposit'].iloc[0]
    total_profit = df['total_profit'].iloc[0]
    total_return = df['total_return'].iloc[0]
    moving_avg_deposit_12 = df['moving_avg_deposit_12'].iloc[0]
    moving_avg_profit_12 = df['moving_avg_profit_12'].iloc[0]
    moving_avg_return_12 = df['moving_avg_return_12'].iloc[0]

    html = f"""
    <style>
        .metric-box {{ 
            border: 1px solid #ddd; 
            padding: 15px; 
            border-radius: 5px; 
            text-align: center; 
            margin-bottom:10px; 
            background-color: #f9f9f9;
        }}
        .metric-box h4 {{ margin-top: 0; color: #333; font-size: 1.1em;}}
        .metric-box p {{ font-size: 1.5em; font-weight: bold; color: #007bff; margin-bottom: 5px;}}
        .metric-box .sub-metric {{ font-size: 0.9em; color: #555;}}
    </style>
    <div style="display: flex; justify-content: space-around; flex-wrap: wrap;">
        <div class="metric-box" style="flex-basis: 30%;">
            <h4>Total Deposit</h4>
            <p>{format_currency(total_deposit, 'R$')}</p>
            <p class="sub-metric">12m Avg: {format_currency(moving_avg_deposit_12, 'R$')}</p>
        </div>
        <div class="metric-box" style="flex-basis: 30%;">
            <h4>Total Profit</h4>
            <p>{format_currency(total_profit, 'R$')}</p>
            <p class="sub-metric">12m Avg: {format_currency(moving_avg_profit_12, 'R$')}</p>
        </div>
        <div class="metric-box" style="flex-basis: 30%;">
            <h4>Total Return</h4>
            <p>{total_return:,.2f} %</p>
            <p class="sub-metric">12m Avg: {moving_avg_return_12:,.2f} %</p>
        </div>
    </div>
    """
    st.html(html)

def plot_summary_section():
    st.header("Current Allocation Summary")
    aporte_input = st.text_input("Simulate Monthly Contribution (R$): ", value="0") # Default to string "0"
    aporte = 0.0
    try:
        aporte = float(aporte_input)
    except ValueError:
        st.warning("Please enter a valid number for the contribution.")

    df_summary = get_last_state()
    if df_summary.empty:
        st.warning("No current state data found for summary.")
        return

    fixed_income_target_perc = FIXED_INCOME_TARGET
    equity_target_perc = EQUITY_TARGET

    fixed_income_sum = df_summary[df_summary['type'] == 'fixed_income']['value'].sum()
    equity_sum = df_summary[df_summary['type'] == 'equity']['value'].sum()
    total_sum = fixed_income_sum + equity_sum

    if total_sum == 0:
        st.info("Total investment value is zero. Cannot display allocation percentages.")
        return

    fixed_income_percentage = (fixed_income_sum / total_sum) * 100
    equity_percentage = (equity_sum / total_sum) * 100

    # Display Overall Allocation vs Target
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Overall Fixed Income")
        st.metric(label=f"Target: {fixed_income_target_perc}%", value=f"{fixed_income_percentage:.1f}%", delta=f"{(fixed_income_percentage - fixed_income_target_perc):.1f}%")
        st.progress(int(fixed_income_percentage))
        st.caption(f"Value: {format_currency(fixed_income_sum, 'R$')}")

    with col2:
        st.subheader("Overall Equity")
        st.metric(label=f"Target: {equity_target_perc}%", value=f"{equity_percentage:.1f}%", delta=f"{(equity_percentage - equity_target_perc):.1f}%")
        st.progress(int(equity_percentage))
        st.caption(f"Value: {format_currency(equity_sum, 'R$')}")

    st.subheader("Detailed Allocation & Rebalancing Suggestions (based on contribution)")
    # Prepare data for rebalancing display
    df_display = df_summary[['asset', 'type', 'value', 'expected_percentage', 'actual_percentage', 'absolute_diff', 'diff_ratio']].copy()
    df_display['value'] = df_display['value'].apply(lambda x: format_currency(x, 'R$'))
    df_display['expected_percentage'] = df_display['expected_percentage'].apply(lambda x: f"{x:.1f}%")
    df_display['actual_percentage'] = df_display['actual_percentage'].apply(lambda x: f"{x:.1f}%")
    df_display['absolute_diff'] = df_display['absolute_diff'].apply(lambda x: format_currency(x, 'R$'))
    df_display['suggested_aport'] = (df_display['diff_ratio'] * aporte).apply(lambda x: format_currency(x, 'R$'))
    df_display.rename(columns={
        'asset': 'Asset',
        'type': 'Type',
        'value': 'Current Value',
        'expected_percentage': 'Target %',
        'actual_percentage': 'Actual %',
        'absolute_diff': 'Difference (Value)',
        'suggested_aport': f'Suggested Aport (of R${aporte:,.2f})'
    }, inplace=True)
    st.dataframe(df_display[['Asset', 'Type', 'Current Value', 'Target %', 'Actual %', 'Difference (Value)', 'Suggested Aport']], hide_index=True, use_container_width=True)

def plot_history_section():
    st.header("Historical Performance")
    dates_info = get_dates()
    if dates_info.empty or pd.isna(dates_info['start_date'].iloc[0]) or pd.isna(dates_info['end_date'].iloc[0]):
        st.warning("Not enough data to display history charts.")
        return

    min_db_date = pd.to_datetime(dates_info['start_date'].iloc[0])
    max_db_date = pd.to_datetime(dates_info['end_date'].iloc[0])

    # Sidebar for date range selection for history plots
    st.sidebar.header("History Date Range")
    default_hist_start = max_db_date - pd.DateOffset(years=2)
    if default_hist_start < min_db_date:
        default_hist_start = min_db_date
        
    start_date_hist = st.sidebar.date_input('Start Date', value=default_hist_start, min_value=min_db_date, max_value=max_db_date, key="hist_start_date")
    end_date_hist = st.sidebar.date_input('End Date', value=max_db_date, min_value=min_db_date, max_value=max_db_date, key="hist_end_date")

    if start_date_hist > end_date_hist:
        st.sidebar.error("End date must be after start date.")
        return

    daily_balance_hist = get_daily_balance(start_date_hist, end_date_hist)
    daily_balance_by_asset_hist = get_daily_balance_by_asset(start_date_hist, end_date_hist)
    daily_balance_by_type_hist = get_daily_balance_by_type(start_date_hist, end_date_hist)
    monthly_returns_hist = get_summary_returns(start_date_hist, end_date_hist)
    # summary_by_asset_hist = get_summary_by_asset(start_date_hist, end_date_hist) # Currently unused

    if not daily_balance_hist.empty:
        fig_balance = px.area(daily_balance_hist, x='date', y='value', title='Overall Portfolio Value Over Time')
        st.plotly_chart(fig_balance, use_container_width=True)
    else:
        st.info("No daily balance data for selected history range.")

    col_hist1, col_hist2 = st.columns(2)
    with col_hist1:
        if not daily_balance_by_type_hist.empty:
            fig_percentage = px.area(daily_balance_by_type_hist, x='date', y='percentage', color='type', title='Asset Allocation (%) Over Time')
            fig_percentage.add_hline(y=EQUITY_TARGET, line_dash="dash", line_color="red", annotation_text=f"Equity Target ({EQUITY_TARGET}%)", annotation_position="bottom right")
            fig_percentage.add_hline(y=FIXED_INCOME_TARGET, line_dash="dash", line_color="blue", annotation_text=f"Fixed Income Target ({FIXED_INCOME_TARGET}%)", annotation_position="top right")
            fig_percentage.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5))
            st.plotly_chart(fig_percentage, use_container_width=True)
        else:
            st.info("No allocation data for selected history range.")
            
    with col_hist2:
        if not daily_balance_by_type_hist.empty:
            fig_type_value = px.area(daily_balance_by_type_hist, x='date', y='value', color='type', title='Asset Value ($) by Type Over Time')
            fig_type_value.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5))
            st.plotly_chart(fig_type_value, use_container_width=True)
        else:
            st.info("No asset value by type data for selected history range.")

    if not daily_balance_by_asset_hist.empty:
        fig_asset_value = px.area(daily_balance_by_asset_hist, x='date', y='value', color='asset', title='Asset Value ($) by Asset Over Time')
        st.plotly_chart(fig_asset_value, use_container_width=True)
    else:
        st.info("No asset value by asset data for selected history range.")

    if not monthly_returns_hist.empty:
        st.subheader("Monthly Returns vs Deposits")
        fig_returns_deposits = px.bar(monthly_returns_hist, x='year_month', y=['total_profit', 'total_deposit'], 
                                      barmode='group', labels={'value': 'Amount', 'year_month': 'Year-Month'},
                                      color_discrete_map={'total_profit': '#2ca02c', 'total_deposit': '#ff7f0e'})
        st.plotly_chart(fig_returns_deposits, use_container_width=True)
        
        st.subheader("12-Month Moving Averages: Returns & Deposits")
        fig_ma_returns_deposits = px.line(monthly_returns_hist, x='year_month', y=['moving_avg_profit_12', 'moving_avg_deposit_12'],
                                         labels={'value': 'Amount', 'year_month': 'Year-Month'},
                                         color_discrete_map={'moving_avg_profit_12': '#1f77b4', 'moving_avg_deposit_12': '#d62728'})
        st.plotly_chart(fig_ma_returns_deposits, use_container_width=True)
    else:
        st.info("No monthly returns data for selected history range.")

def plot_forecast_section():
    st.header("Investment Forecast")
    df_last = get_last_state()
    if df_last.empty or 'value' not in df_last.columns:
        st.warning("Cannot run forecast: No current balance data found.")
        return
    current_balance = df_last['value'].sum()
    st.write(f"Starting forecast based on current total balance: {format_currency(current_balance, 'R$')}")

    col1, col2 = st.columns(2)
    with col1:
        deposit = st.number_input("Monthly Deposit (R$): ", value=1000.0, min_value=0.0, step=100.0, format="%.2f")
    with col2:
        monthly_return_rate = st.number_input("Expected Monthly Return (%): ", value=0.75, min_value=0.0, max_value=5.0, step=0.01, format="%.2f") / 100

    # Create date range for the next N years
    forecast_years = st.slider("Forecast Horizon (Years):", min_value=1, max_value=40, value=20)
    current_ym = datetime.now()
    date_list = [current_ym + pd.DateOffset(months=i) for i in range(forecast_years * 12 + 1)]

    balance_list = []
    age_list = []

    for i, date_val in enumerate(date_list):
        age_at_date = date_val.year - BIRTH_DATE.year - ((date_val.month, date_val.day) < (BIRTH_DATE.month, BIRTH_DATE.day))
        age_list.append(age_at_date)
        if i == 0:
            balance = current_balance
        else:
            balance = balance_list[i - 1] * (1 + monthly_return_rate) + deposit
        balance_list.append(balance)

    df_forecast = pd.DataFrame(data={'Date': date_list, 'Balance': balance_list, 'Age': age_list})

    fig_forecast = px.area(df_forecast, x='Date', y='Balance', title='Portfolio Growth Projection', hover_data=['Age'])
    fig_forecast.update_xaxes(title_text='Date')
    fig_forecast.update_yaxes(title_text='Projected Balance (R$)')
    st.plotly_chart(fig_forecast, use_container_width=True)

# --- Page rendering starts here ---
# Call sections to build the page
plot_last_results_section()
st.markdown("--- Access Current Investment Allocation ---")
plot_summary_section()
st.markdown("--- Access Investment History ---")
plot_history_section()
st.markdown("--- Access Investment Forecast ---")
plot_forecast_section() 