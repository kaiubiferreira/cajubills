from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import os

# Adjust path to import from backend and sql
import sys
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from backend.investments.constants import EQUITY_TARGET, FIXED_INCOME_TARGET, BIRTH_DATE
from sql.connection import run_query

def get_daily_balance(start_date, end_date):
    query = (f"SELECT date, sum(value) as value "
             f"FROM daily_balance "
             f"WHERE date BETWEEN '{start_date}' AND '{end_date}' "
             f"GROUP BY date")
    return run_query(query, target_db="local")

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
    # Adjusted for SQLite - using strftime instead of YEAR() and MONTH() functions
    query = ("SELECT (CAST(strftime('%Y', '" + str(start_date) + "') AS INTEGER) || '-' || printf('%02d', CAST(strftime('%m', '" + str(start_date) + "') AS INTEGER))) AS 'year_month', total_deposit, total_profit, "
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
    query = ("SELECT asset, (year || '-' || printf('%02d', month)) AS 'year_month', "
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
            COALESCE(percentage, 0) AS expected_percentage,
            (value / total_value) * 100 AS actual_percentage,
            CASE WHEN COALESCE(percentage, 0) > 0 THEN COALESCE(percentage, 0) - (value / total_value) * 100 ELSE 0 END AS diff,
            (COALESCE(percentage, 0) * total_value / 100.0) - value AS absolute_diff
        FROM daily_balance t1 
        INNER JOIN ( 
        SELECT 
             MAX(date) AS max_date 
        FROM 
             daily_balance 
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
        CASE WHEN positive_diff != 0 AND absolute_diff > 0 THEN absolute_diff / positive_diff ELSE 0 END AS diff_ratio
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

def plot_last_results():
    st.header("📊 Current Investment Summary")
    
    # Get the last results from the database
    df = get_last_results()
    
    if df.empty:
        st.warning("No investment data found in database.")
        return

    total_deposit = df['total_deposit'].iloc[0]
    total_profit = df['total_profit'].iloc[0]
    total_return = df['total_return'].iloc[0]
    moving_avg_deposit_12 = df['moving_avg_deposit_12'].iloc[0]
    moving_avg_profit_12 = df['moving_avg_profit_12'].iloc[0]
    moving_avg_return_12 = df['moving_avg_return_12'].iloc[0]

    # Display metrics using Streamlit's built-in components
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="💰 Total Deposits",
            value=format_currency(total_deposit, 'R$'),
            delta=f"12m avg: {format_currency(moving_avg_deposit_12, 'R$')}"
        )
    
    with col2:
        st.metric(
            label="📈 Total Profit",
            value=format_currency(total_profit, 'R$'),
            delta=f"12m avg: {format_currency(moving_avg_profit_12, 'R$')}"
        )
    
    with col3:
        st.metric(
            label="🎯 Total Return",
            value=f"{total_return:.2f}%",
            delta=f"12m avg: {moving_avg_return_12:.2f}%"
        )

def plot_forecast(current_balance):
    st.header("📮 Investment Forecast")
    
    col1, col2 = st.columns(2)
    with col1:
        deposit = st.number_input("Monthly Deposit (R$):", value=1000.0, min_value=0.0, step=100.0, format="%.2f")
    with col2:
        monthly_return_rate = st.number_input("Expected Monthly Return (%):", value=0.75, min_value=0.0, max_value=5.0, step=0.01, format="%.2f") / 100

    # Create date range for the next N years
    forecast_years = st.slider("Forecast Horizon (Years):", min_value=1, max_value=40, value=20)
    current_date = datetime.now()
    date_list = [current_date + timedelta(days=30 * i) for i in range(forecast_years * 12)]

    # Initialize balance list
    balance_list = []
    age_list = []

    # Calculate balance for each month
    for i, date_val in enumerate(date_list):
        age_at_date = date_val.year - BIRTH_DATE.year - ((date_val.month, date_val.day) < (BIRTH_DATE.month, BIRTH_DATE.day))
        age_list.append(age_at_date)
        
        if i == 0:
            balance = current_balance
        else:
            balance = balance_list[i - 1] * (1 + monthly_return_rate) + deposit
        balance_list.append(balance)

    # Create DataFrame
    df_forecast = pd.DataFrame(data={'Date': date_list, 'Balance': balance_list, 'Age': age_list})

    # Create forecast chart
    fig_forecast = px.area(df_forecast, x='Date', y='Balance', title='Portfolio Growth Projection', hover_data=['Age'])
    fig_forecast.update_xaxes(title_text='Date')
    fig_forecast.update_yaxes(title_text='Projected Balance (R$)')
    st.plotly_chart(fig_forecast, use_container_width=True)

    # Investment milestones
    targets = [100000, 500000, 1000000, 5000000, 10000000]
    milestones_data = []

    for target in targets:
        if current_balance < target:
            target_rows = df_forecast[df_forecast['Balance'] >= target]
            if not target_rows.empty:
                target_row = target_rows.iloc[0]
                target_month_str = target_row['Date'].strftime('%B, %Y')
                months_to_reach = (target_row['Date'] - current_date).days // 30
                years_to_reach = months_to_reach // 12
                months_remaining = months_to_reach % 12
                age_years = target_row['Age']
                projected_return = target_row['Balance'] * monthly_return_rate

                if months_to_reach > 12:
                    time_to_reach = f"{years_to_reach} year(s) and {months_remaining} month(s)"
                else:
                    time_to_reach = f"{months_to_reach} months"

                milestones_data.append({
                    'Target': format_currency(target, 'R$'),
                    'Time to Reach': time_to_reach,
                    'Target Date': target_month_str,
                    'Age at Target': f"{age_years} years",
                    'Monthly Return at Target': format_currency(projected_return, 'R$')
                })

    if milestones_data:
        st.subheader("🎯 Investment Milestones")
        st.dataframe(pd.DataFrame(milestones_data), hide_index=True)

def plot_summary():
    st.header("💼 Current Portfolio Allocation")
    
    aporte_input = st.number_input("Simulate Monthly Contribution (R$):", value=0.0, min_value=0.0, step=100.0, format="%.2f")
    
    df = get_last_state()
    if df.empty:
        st.warning("No current portfolio data found.")
        return
    
    fixed_income_target = FIXED_INCOME_TARGET
    equity_target = EQUITY_TARGET

    fixed_income_sum = df[df['type'] == 'fixed_income']['value'].sum()
    equity_sum = df[df['type'] == 'equity']['value'].sum()
    total_sum = fixed_income_sum + equity_sum
    
    if total_sum == 0:
        st.warning("Total portfolio value is zero.")
        return
    
    fixed_income_percentage = 100 * fixed_income_sum / total_sum
    equity_percentage = 100 * equity_sum / total_sum
    fixed_income_diff = fixed_income_percentage - fixed_income_target
    equity_diff = equity_percentage - equity_target

    # Display overall allocation
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏦 Fixed Income")
        st.metric(
            label=f"Target: {fixed_income_target}%",
            value=f"{fixed_income_percentage:.1f}%",
            delta=f"{fixed_income_diff:.1f}%"
        )
        st.progress(min(fixed_income_percentage / 100, 1.0))
        st.caption(f"Value: {format_currency(fixed_income_sum, 'R$')}")

    with col2:
        st.subheader("📈 Equity")
        st.metric(
            label=f"Target: {equity_target}%",
            value=f"{equity_percentage:.1f}%",
            delta=f"{equity_diff:.1f}%"
        )
        st.progress(min(equity_percentage / 100, 1.0))
        st.caption(f"Value: {format_currency(equity_sum, 'R$')}")

    # Detailed allocation table
    st.subheader("📋 Detailed Asset Allocation")
    
    if aporte_input > 0:
        st.info(f"Rebalancing suggestions based on R$ {aporte_input:,.2f} monthly contribution:")
    
    # Prepare display data
    display_data = []
    
    for _, row in df.iterrows():
        asset = row['asset']
        value = row['value']
        expected_percentage = row['expected_percentage']
        actual_percentage = row['actual_percentage']
        absolute_diff = row['absolute_diff']
        diff_ratio = row['diff_ratio']
        asset_type = row['type']
        
        # Convert to float to handle any string values
        try:
            expected_percentage_float = float(expected_percentage) if expected_percentage is not None else 0.0
            actual_percentage_float = float(actual_percentage) if actual_percentage is not None else 0.0
        except (ValueError, TypeError):
            expected_percentage_float = 0.0
            actual_percentage_float = 0.0
        
        suggested_aport = diff_ratio * aporte_input if aporte_input > 0 else 0
        
        display_data.append({
            'Asset': asset,
            'Type': '🏦 Fixed Income' if asset_type == 'fixed_income' else '📈 Equity',
            'Current Value': format_currency(value, 'R$'),
            'Target %': f"{expected_percentage_float:.1f}%",
            'Actual %': f"{actual_percentage_float:.1f}%",
            'Difference': format_currency(absolute_diff, 'R$'),
            'Suggested Allocation': format_currency(suggested_aport, 'R$') if aporte_input > 0 else '-'
        })
    
    df_display = pd.DataFrame(display_data)
    st.dataframe(df_display, hide_index=True, use_container_width=True)
    
    st.subheader("💰 Portfolio Summary")
    st.metric(label="Total Portfolio Value", value=format_currency(total_sum, 'R$'))

def plot_history():
    st.header("📊 Historical Performance")
    
    dates = get_dates()
    if dates.empty:
        st.warning("No historical data available.")
        return

    # Date selection in sidebar
    with st.sidebar:
        st.header("📅 History Date Range")
        max_date = pd.to_datetime(dates['end_date'].iloc[0])
        min_date = pd.to_datetime(dates['start_date'].iloc[0])
        default_start = max_date - pd.DateOffset(years=2)
        if default_start < min_date:
            default_start = min_date
        
        start_date = st.date_input('Start Date', value=default_start.date(), min_value=min_date.date(), max_value=max_date.date())
        end_date = st.date_input('End Date', value=max_date.date(), min_value=min_date.date(), max_value=max_date.date())

    if start_date > end_date:
        st.error("End date must be after start date.")
        return

    # Load historical data
    daily_balance = get_daily_balance(start_date, end_date)
    daily_balance_by_asset = get_daily_balance_by_asset(start_date, end_date)
    daily_balance_by_type = get_daily_balance_by_type(start_date, end_date)
    monthly_returns = get_summary_returns(start_date, end_date)
    summary_by_asset = get_summary_by_asset(start_date, end_date)

    # Overall portfolio value chart
    if not daily_balance.empty:
        fig_balance = px.area(
            daily_balance,
            x='date',
            y='value',
            title='📈 Portfolio Value Over Time'
        )
        st.plotly_chart(fig_balance, use_container_width=True)
    else:
        st.info("No portfolio balance data available for the selected period.")

    # Asset allocation charts
    col1, col2 = st.columns(2)

    with col1:
        if not daily_balance_by_type.empty:
            fig_percentage = px.area(
                daily_balance_by_type,
                x='date',
                y='percentage',
                color='type',
                title='🎯 Asset Allocation (%) Over Time',
            )

            fig_percentage.add_hline(y=EQUITY_TARGET, line_dash="dash", line_color="red",
                                   annotation_text=f"Equity Target ({EQUITY_TARGET}%)",
                                   annotation_position="bottom right")
            
            fig_percentage.add_hline(y=FIXED_INCOME_TARGET, line_dash="dash", line_color="blue",
                                   annotation_text=f"Fixed Income Target ({FIXED_INCOME_TARGET}%)",
                                   annotation_position="top right")

            fig_percentage.update_layout(
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.3,
                    xanchor="center",
                    x=0.5
                )
            )
            st.plotly_chart(fig_percentage, use_container_width=True)
        else:
            st.info("No allocation percentage data available.")

    with col2:
        if not daily_balance_by_type.empty:
            fig_type = px.area(
                daily_balance_by_type,
                x='date',
                y='value',
                color='type',
                title='💰 Asset Value (R$) by Type Over Time'
            )
            fig_type.update_layout(
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.3,
                    xanchor="center",
                    x=0.5
                )
            )
            st.plotly_chart(fig_type, use_container_width=True)
        else:
            st.info("No asset value data available.")

    # Asset breakdown chart
    if not daily_balance_by_asset.empty:
        fig_asset = px.area(
            daily_balance_by_asset,
            x='date',
            y='value',
            color='asset',
            title='📊 Portfolio Value by Asset Over Time'
        )
        st.plotly_chart(fig_asset, use_container_width=True)

    # Returns analysis
    if not monthly_returns.empty:
        st.subheader("💹 Returns vs Deposits Analysis")

        # Monthly returns and deposits
        fig_returns_deposits = px.bar(monthly_returns,
                                      x='year_month',
                                      y=['total_profit', 'total_deposit'],
                                      barmode='group',
                                      labels={'value': 'Amount (R$)', 'year_month': 'Year-Month'},
                                      title='📊 Monthly Profit vs Deposits',
                                      color_discrete_map={'total_profit': '#2ca02c', 'total_deposit': '#ff7f0e'})
        st.plotly_chart(fig_returns_deposits, use_container_width=True)

        # Moving averages
        fig_ma_returns_deposits = px.line(monthly_returns,
                                         x='year_month',
                                         y=['moving_avg_profit_12', 'moving_avg_deposit_12'],
                                         labels={'value': 'Amount (R$)', 'year_month': 'Year-Month'},
                                         title='📈 12-Month Moving Averages: Returns & Deposits',
                                         color_discrete_map={'moving_avg_profit_12': '#1f77b4', 'moving_avg_deposit_12': '#d62728'})
        st.plotly_chart(fig_ma_returns_deposits, use_container_width=True)

        # Returns by asset
        if not summary_by_asset.empty:
            fig_increase_by_asset = px.bar(summary_by_asset,
                                           x='year_month',
                                           y='net_increase',
                                           color="asset",
                                           title='📊 Monthly Net Increase by Asset')
            st.plotly_chart(fig_increase_by_asset, use_container_width=True)

        # Detailed returns analysis
        st.subheader("📈 Detailed Returns Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_returns = go.Figure()
            fig_returns.add_trace(
                go.Bar(x=monthly_returns['year_month'], y=monthly_returns['total_profit'], 
                       name='Total Profit', marker_color='skyblue'))
            fig_returns.add_trace(
                go.Scatter(x=monthly_returns['year_month'], y=monthly_returns['moving_avg_profit_6'],
                           name='6-Month MA', mode='lines+markers',
                           line=dict(color='orange', width=2)))
            fig_returns.add_trace(
                go.Scatter(x=monthly_returns['year_month'], y=monthly_returns['moving_avg_profit_12'],
                           name='12-Month MA', mode='lines+markers',
                           line=dict(color='green', width=2)))
            fig_returns.update_layout(title='💰 Profit with Moving Averages',
                                      xaxis_title='Year-Month',
                                      yaxis_title='Amount (R$)')
            st.plotly_chart(fig_returns, use_container_width=True)

        with col2:
            fig_returns_percentage = go.Figure()
            fig_returns_percentage.add_trace(
                go.Bar(x=monthly_returns['year_month'], y=monthly_returns['total_return'], 
                       name='Total Return', marker_color='lightgreen'))
            fig_returns_percentage.add_trace(
                go.Scatter(x=monthly_returns['year_month'], y=monthly_returns['moving_avg_return_6'],
                           name='6-Month MA', mode='lines+markers',
                           line=dict(color='orange', width=2)))
            fig_returns_percentage.add_trace(
                go.Scatter(x=monthly_returns['year_month'], y=monthly_returns['moving_avg_return_12'],
                           name='12-Month MA', mode='lines+markers',
                           line=dict(color='green', width=2)))
            fig_returns_percentage.update_layout(title='📊 Return % with Moving Averages',
                                                  xaxis_title='Year-Month',
                                                  yaxis_title='Return (%)')
            st.plotly_chart(fig_returns_percentage, use_container_width=True)

# Main page configuration
st.set_page_config(page_title="Investment Dashboard", page_icon="💰", layout="wide")
st.title("💰 Investment Dashboard")

# Database debugging section
with st.expander("🔍 Database Debug Information", expanded=False):
    st.subheader("Investment Tables Status")
    
    tables_to_check = [
        "daily_balance",
        "summary_returns", 
        "financial_returns",
        "target_percentage",
        "variable_income_daily_balance",
        "fixed_income_daily_balance", 
        "variable_income_operations",
        "fixed_income_operations",
        "asset_price",
        "daily_asset_price",
        "index_series"
    ]
    
    debug_results = []
    
    for table in tables_to_check:
        try:
            # Check if table exists and count rows
            count_query = f"SELECT COUNT(*) as row_count FROM {table}"
            result = run_query(count_query, target_db="local")
            
            if not result.empty:
                row_count = result['row_count'].iloc[0]
                status = "✅ Has data" if row_count > 0 else "⚠️ Empty"
                
                # Get date range for time-series tables
                date_info = ""
                if table in ["daily_balance", "variable_income_daily_balance", "fixed_income_daily_balance", "asset_price", "daily_asset_price", "index_series"]:
                    try:
                        date_query = f"SELECT MIN(date) as min_date, MAX(date) as max_date FROM {table}"
                        date_result = run_query(date_query, target_db="local")
                        if not date_result.empty and row_count > 0:
                            min_date = date_result['min_date'].iloc[0]
                            max_date = date_result['max_date'].iloc[0]
                            date_info = f" | {min_date} to {max_date}"
                    except:
                        date_info = " | Date range unavailable"
                        
                debug_results.append({
                    "Table": table,
                    "Status": status,
                    "Row Count": row_count,
                    "Additional Info": date_info
                })
            else:
                debug_results.append({
                    "Table": table,
                    "Status": "❌ Query failed",
                    "Row Count": 0,
                    "Additional Info": ""
                })
                
        except Exception as e:
            debug_results.append({
                "Table": table,
                "Status": "❌ Error",
                "Row Count": 0,
                "Additional Info": str(e)
            })
    
    # Display results
    debug_df = pd.DataFrame(debug_results)
    st.dataframe(debug_df, hide_index=True, use_container_width=True)
    
    # Summary
    empty_tables = [r["Table"] for r in debug_results if r["Row Count"] == 0]
    error_tables = [r["Table"] for r in debug_results if "Error" in r["Status"] or "failed" in r["Status"]]
    
    if empty_tables:
        st.warning(f"⚠️ Empty tables: {', '.join(empty_tables)}")
    if error_tables:
        st.error(f"❌ Tables with errors: {', '.join(error_tables)}")
    
    if not empty_tables and not error_tables:
        st.success("✅ All investment tables have data!")

# Check if we have data
dates_check = get_dates()
if dates_check.empty:
    st.error("❌ No investment data found in the database.")
    st.info("Please ensure investment data has been loaded into the local database.")
    st.info("💡 Check the 'Database Debug Information' section above to see which tables need data.")
    st.stop()

# Get total portfolio value for forecast
last_state = get_last_state()
current_balance = last_state['value'].sum() if not last_state.empty else 0

# Main dashboard sections
plot_last_results()

st.markdown("---")
plot_summary()

st.markdown("---")
if current_balance > 0:
    plot_forecast(current_balance)
else:
    st.warning("⚠️ Cannot display forecast: No current portfolio balance found.")

st.markdown("---")
plot_history() 