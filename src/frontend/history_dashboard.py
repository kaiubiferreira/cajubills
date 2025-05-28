from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from backend.investments.contants import EQUITY_TARGET, FIXED_INCOME_TARGET, BIRTH_DATE
from sql.connection import run_query


def get_daily_balance(start_date, end_date):
    query = (f"SELECT date, sum(value) as value "
             f"FROM daily_balance "
             f"WHERE date BETWEEN '{start_date}' AND '{end_date}' "
             f"GROUP BY date")
    return run_query(query)


def get_daily_balance_by_asset(start_date, end_date):
    query = (f"SELECT asset, date, value "
             f"FROM daily_balance "
             f"WHERE date BETWEEN '{start_date}' AND '{end_date}'")
    return run_query(query)


def get_daily_balance_by_type(start_date, end_date):
    query = (f"SELECT type, date, sum(value) as value "
             f"FROM daily_balance "
             f"WHERE date BETWEEN '{start_date}' AND '{end_date}' "
             f"GROUP BY type, date")
    df = run_query(query)

    df['percentage'] = df.groupby('date')['value'].transform(
        lambda x: x / x.sum() * 100)
    return df


def get_dates():
    query = "SELECT MIN(date) AS start_date, MAX(date) AS end_date FROM daily_balance;"
    return run_query(query)


def get_summary_returns(start_date, end_date):
    query = ("SELECT CONCAT(year, '-', LPAD(month, 2, '0')) AS 'year_month', total_deposit, total_profit, "
             "moving_avg_profit_6, moving_avg_profit_12, moving_avg_deposit_6, moving_avg_deposit_12, "
             "total_return, moving_avg_return_6, moving_avg_return_12 "
             "FROM summary_returns "
             f"WHERE year >= year('{start_date}') AND year <= year('{end_date}') ")

    monthly_returns = run_query(query)
    monthly_returns['total'] = monthly_returns['total_deposit'] + monthly_returns['total_profit']
    monthly_returns['deposit_percentage'] = (monthly_returns['total_deposit'] / monthly_returns['total']) * 100
    monthly_returns['profit_percentage'] = (monthly_returns['total_profit'] / monthly_returns['total']) * 100

    return monthly_returns


def get_summary_by_asset(start_date, end_date):
    query = ("SELECT asset, CONCAT(year, '-', LPAD(month, 2, '0')) AS 'year_month', "
             "deposit, profit, net_increase "
             "FROM financial_returns "
             f"WHERE year >= year('{start_date}') AND year <= year('{end_date}') ")

    df = run_query(query)
    return df


def get_last_state():
    query = ("""
    WITH DATA
    AS(
        SELECT 
            asset, 
            value, 
            type, 
            percentage AS expected_percentage,
            (value / total_value) * 100 AS actual_percentage,
            CASE WHEN percentage > 0 THEN percentage - (value / total_value) * 100 ELSE 0 END AS diff,
            (percentage * total_value / 100.0) - value AS absolute_diff
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
        CASE WHEN absolute_diff > 0 THEN absolute_diff / positive_diff ELSE 0 END AS diff_ratio
    FROM DATA
    CROSS JOIN POSITIVE_DIFF_TOTAL
    ORDER BY type, value DESC
    """)
    return run_query(query)


def get_last_results():
    query = ("""
        SELECT total_deposit, total_profit, total_return,
        moving_avg_deposit_12, moving_avg_profit_12, moving_avg_return_12
        FROM summary_returns
        ORDER BY year DESC, month DESC
        LIMIT 1 
    """)
    return run_query(query)


def format_currency(amount, currency_symbol) -> str:
    formatted_amount = f"{amount:,.2f}"
    return f"{currency_symbol} {formatted_amount}"


def plot_last_results():
    st.title("Last Results")

    # Get the last results from the database
    df = get_last_results()

    total_deposit = df['total_deposit'].iloc[0]
    total_profit = df['total_profit'].iloc[0]
    total_return = df['total_return'].iloc[0]
    moving_avg_deposit_12 = df['moving_avg_deposit_12'].iloc[0]
    moving_avg_profit_12 = df['moving_avg_profit_12'].iloc[0]
    moving_avg_return_12 = df['moving_avg_return_12'].iloc[0]

    # Construct the HTML for the results

    html = f"""
    <style>
        .bold {{ font-weight: bold; }}
        .dark-green {{ background-color: #2A8E28; }}
        .dark-blue {{ background-color: #1E4F90; }}
        .pale-green {{ background-color: #70C76F; }}
        .pale-blue {{ background-color: #517FBA; }}
        .dark-yellow {{ background-color: #a78300; }}
        .pale-yellow {{ background-color: #FFD336; }}
        td, th {{ padding: 8px; }}
        .table-container-thin {{
            display: flex;
            justify-content: space-around;
            margin: 20px 0;
        }}
        .table-thin {{
            border-collapse: collapse;
            width: 30%; /* Adjust the width as needed */
        }}
    </style>
    <div class="table-container-thin">
        <table class="table-thin dark-green">
            <tr class="bold">
                <th>Total Deposit</th>
            </tr>
            <tr class="pale-green">
                <td>{format_currency(total_deposit, 'R$')}</td>
            </tr>
            <tr class="bold">
                <th>Moving Avg (12 months)</th>
            </tr>
            <tr class="pale-green">
                <td>{format_currency(moving_avg_deposit_12, 'R$')}</td>
            </tr>
        </table>

        <table class="table-thin dark-blue">
            <tr class="bold">
                <th>Total Profit</th>
            </tr>
            <tr class="pale-blue">
                <td>{format_currency(total_profit, 'R$')}</td>
            </tr>
            <tr class="bold">
                <th>Moving Avg (12 months)</th>
            </tr>
            <tr class="pale-blue">
                <td>{format_currency(moving_avg_profit_12, 'R$')}</td>
            </tr>
        </table>

        <table class="table-thin dark-yellow">
            <tr class="bold">
                <th>Total Return</th>
            </tr>
            <tr class="pale-yellow">
                <td>{total_return:,.2f} %</td>
            </tr>
            <tr class="bold">
                <th>Moving Avg (12 months)</th>
            </tr>
            <tr class="pale-yellow">
                <td>{moving_avg_return_12:,.2f} %</td>
            </tr>
        </table>
    </div>
    """

    # Render the HTML in the Streamlit app
    st.html(html)


def plot_forecast(current_balance):
    st.title("Projection")
    col1, col2 = st.columns(2)
    with col1:
        deposit = float(st.text_input("Monthly Deposit (R$): ", value=10000))
    with col2:
        monthly_return_rate = float(st.text_input("Expected Return (~0.75% to 1.0%): ", value=0.8)) / 100

    # Create date range for the next 20 years
    current_date = datetime.now()
    date_list = [current_date + timedelta(days=30 * i) for i in range(50 * 12)]

    # Initialize balance list
    balance_list = []

    # Calculate balance for each month
    for i, date in enumerate(date_list):
        if i == 0:
            balance = current_balance
        else:
            balance = balance_list[i - 1] * (1 + monthly_return_rate) + deposit
        balance_list.append(balance)

    # Create DataFrame
    df = pd.DataFrame(data={'Date': date_list, 'Balance': balance_list})
    december_balances = df[df['Date'].dt.month == 12]['Balance'].to_numpy()

    # Create a date range for the next 10 years
    next_10_years = datetime.now() + timedelta(days=10 * 365)  # Approximation for 10 years

    # Filter the DataFrame to include only dates within the next 10 years
    df_filtered = df[df['Date'] <= next_10_years]

    # Create the figure with the filtered data
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_filtered['Date'], y=df_filtered['Balance'], mode='lines', name='Balance'))
    fig.update_layout(title='Projected Balance Over Time (Next 10 Years)',
                      xaxis_title='Date',
                      yaxis_title='Balance')

    st.plotly_chart(fig)

    targets = [100000, 500000, 1000000, 5000000, 10000000]
    next_modules = [((current_balance // target) + 1) * target for target in targets]

    html_table = """<table>
        <tr>
            <th class="bold dark-blue">Amount</th>
            <th class="bold dark-blue">Time</th>
            <th class="bold dark-blue">Date</th>
            <th class="bold dark-blue">Age</th>
            <th class="bold dark-blue">Monthly Return</th>
        </tr>
    """

    for target in next_modules:
        target_month = df[df['Balance'] >= target].iloc[0]
        target_month_str = target_month['Date'].strftime('%B, %Y')
        total_months_to_reach = (target_month['Date'] - current_date).days // 30
        projected_return = target_month['Balance'] * monthly_return_rate
        years_to_reach = total_months_to_reach // 12
        months_remaining = total_months_to_reach % 12
        age_years = (target_month['Date'] - BIRTH_DATE).days // 365

        if total_months_to_reach > 12:
            time_to_reach = f"{years_to_reach} year(s) and {months_remaining} month(s)"
        else:
            time_to_reach = f"{total_months_to_reach} months"

        html_table += f"""
        <tr>
            <td class="pale-blue">{format_currency(target, "R$")}</td>
            <td class="pale-blue">{time_to_reach}</td>
            <td class="pale-blue">{target_month_str}</td>
            <td class="pale-blue">{age_years} years</td>
            <td class="pale-blue">{format_currency(projected_return, "R$")}</td>
        </tr>
        """

    html_table += "</table>"

    # Create a year-end projections table
    year_end_table_html = """
    <div style='display: flex; justify-content: center;'>
        <table style='border-collapse: collapse;'>
            <tr>
                <th class="bold dark-green" style='border: 1px solid black; padding: 8px;'>Year</th>
                <th class="bold dark-green" style='border: 1px solid black; padding: 8px;'>Age</th>
                <th class="bold dark-green" style='border: 1px solid black; padding: 8px;'>Balance</th>
            </tr>
    """

    # Get current year
    current_year = current_date.year

    # Calculate expected year-end balances for the current year and the next 3 years
    for year in range(current_year, current_year + 5):
        year_end_date = datetime(year, 12, 31)
        months_remaining = (year_end_date - current_date).days // 30
        age_years = (year_end_date - BIRTH_DATE).days // 365

        if months_remaining < 0:
            # If the year-end date has already passed, use the last calculated balance
            expected_balance = balance_list[-1]
        else:
            # Calculate the balance at year-end using the suitable index
            expected_balance = balance_list[min(months_remaining + (year - current_year - 1) * 12, len(balance_list) - 1)]

        year_end_table_html += f"""
        <tr>
            <td class="pale-green" style='border: 1px solid black; padding: 8px;'>{year}</td>
            <td class="pale-green" style='border: 1px solid black; padding: 8px;'>{age_years}</td>
            <td class="pale-green" style='border: 1px solid black; padding: 8px;'>{format_currency(expected_balance, "R$")}</td>
        </tr>
        """

    year_end_table_html += "</table></div>"

    st.subheader("Next Years: ")
    st.html(year_end_table_html)

    st.subheader(f"Milestones: ")
    st.html(html_table)


def plot_summary():
    st.title("Current State")
    aporte_input = st.text_input("Aporte: ")
    aporte = 0
    if aporte_input:
        aporte = float(aporte_input)
    df = get_last_state()
    fixed_income_target = FIXED_INCOME_TARGET
    equity_target = EQUITY_TARGET

    fixed_income_sum = df[df['type'] == 'fixed_income']['value'].sum()
    equity_sum = df[df['type'] == 'equity']['value'].sum()
    total_sum = fixed_income_sum + equity_sum
    fixed_income_percentage = 100 * fixed_income_sum / total_sum
    equity_percentage = 100 * equity_sum / total_sum
    fixed_income_diff = fixed_income_percentage - fixed_income_target
    equity_diff = equity_percentage - equity_target
    fixed_income_diff_color = 'red' if abs(fixed_income_diff) > 1.0 else 'white'
    equity_diff_color = 'red' if abs(equity_diff) > 1.0 else 'white'

    html = f"""
    <style>
        .bold {{ font-weight: bold; }}
        .dark-green {{ background-color: #2A8E28; }}
        .dark-blue {{ background-color: #1E4F90; }}
        .pale-green {{ background-color: #70C76F; }}
        .pale-blue {{ background-color: #517FBA; }}
        .dark-yellow {{ background-color: #a78300; }}
         td, th {{ padding: 8px; }}
         .table-container {{
            display: flex;
            justify-content: center;
            margin: 20px 0;
        }}
    </style>
    <div class="table-container">
    <table class="table">
        <tr class="bold dark-yellow">
            <td>Asset</td>
            <td>Value</td>
            <td>Target %</td>
            <td>Actual %</td>
            <td>Diff $</td>
            <td>Next: </td>
        </tr>
        <tr class="bold dark-green">
            <td>Renda Fixa</td>
            <td>{format_currency(fixed_income_sum, 'R$')}</td>
            <td>{fixed_income_target} %</td>
            <td style="color: {fixed_income_diff_color};">{100 * fixed_income_sum / total_sum:.1f} %</td>
            <td style="color: {fixed_income_diff_color};">{format_currency(fixed_income_diff / 100 * fixed_income_sum, 'R$')}</td>
            <td></td>
        </tr>
    """

    for _, row in df[df['type'] == 'fixed_income'].iterrows():
        diff_color = 'red' if abs(row['diff']) > 1.0 else 'white'
        html += f"""
        <tr class="pale-green">
            <td>{row['asset']}</td>
            <td>{format_currency(row['value'], 'R$')}</td>
            <td>{row['expected_percentage']:.1f} %</td>
            <td style="color: {diff_color};">{row['actual_percentage']:.1f} %</td>
            <td style="color: {diff_color};">{format_currency(row['absolute_diff'], 'R$')}</td>
            <td class="bold">{format_currency(row['diff_ratio'] * aporte, 'R$')}</td>
        </tr>
        """

    html += f"""
        <tr class="bold dark-blue">
            <td>Renda Variavel</td>
            <td>{format_currency(equity_sum, 'R$')}</td>
            <td>{equity_target} %</td>
            <td style="color: {equity_diff_color};">{100 * equity_sum / total_sum:.1f} %</td>
            <td style="color: {equity_diff_color};">{format_currency(equity_diff / 100 * equity_sum, 'R$')}</td>
            <td></td>
        </tr>
    """

    # Add rows for equity
    for _, row in df[df['type'] == 'equity'].iterrows():
        diff_color = 'red' if abs(row['diff']) > 1.0 else 'white'
        html += f"""
        <tr class="pale-blue">
            <td>{row['asset']}</td>
            <td>{format_currency(row['value'], 'R$')}</td>
            <td>{row['expected_percentage']:.1f} %</td>
            <td style="color: {diff_color};">{row['actual_percentage']:.1f} %</td>
            <td style="color: {diff_color};">{format_currency(row['absolute_diff'], 'R$')}</td>
            <td class="bold">{format_currency(row['diff_ratio'] * aporte, 'R$')}</td>
        </tr>
        """

    html += f"""
        <tr class="bold dark-yellow">
            <td>Total</td>
            <td colspan="5" style="text-align: center;">{format_currency(total_sum, 'R$')}</td>
        </tr>
    """

    html += "</table></div>"

    st.html(html)
    st.divider()

    plot_last_results()
    plot_forecast(total_sum)


def plot_history():
    st.divider()
    dates = get_dates()

    start_date = st.sidebar.date_input('Start Date',
                                       value=(pd.to_datetime(dates['end_date'].max()) - pd.DateOffset(years=2)))
    end_date = st.sidebar.date_input('End Date', value=pd.to_datetime(dates['end_date'].max()))

    daily_balance = get_daily_balance(start_date, end_date)
    daily_balance_by_asset = get_daily_balance_by_asset(start_date, end_date)
    daily_balance_by_type = get_daily_balance_by_type(start_date, end_date)
    monthly_returns = get_summary_returns(start_date, end_date)
    summary_by_asset = get_summary_by_asset(start_date, end_date)

    st.title("Summary Over Time")

    fig_balance = px.area(
        daily_balance,
        x='date',
        y='value',
        title='Daily Balance'
    )
    st.plotly_chart(fig_balance)

    col1, col2 = st.columns(2)

    with col1:
        fig_percentage = px.area(
            daily_balance_by_type,
            x='date',
            y='percentage',
            color='type',
            title='Fixed vs Variable %',
        )

        fig_percentage.add_hline(y=70, line_dash="dash", line_color="red",
                                 annotation_text="Goal (70%)",
                                 annotation_position="bottom right")

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
    with col2:
        fig_type = px.area(
            daily_balance_by_type,
            x='date',
            y='value',
            color='type',
            title='Fixed vs Variable $'
        )
        fig_type.update_layout(
            legend=dict(
                orientation="h",  # Horizontal orientation
                yanchor="bottom",  # Anchor to the bottom of the legend
                y=-0.3,  # Adjust vertical positioning below the plot
                xanchor="center",  # Center the legend
                x=0.5  # Align legend in the middle
            )
        )
        st.plotly_chart(fig_type, use_container_width=True)

    fig_asset = px.bar(
        daily_balance_by_asset,
        x='date',
        y='value',
        color='asset',
        title='Daily Balance by Asset'
    )

    st.plotly_chart(fig_asset)

    st.title("Returns x Deposits")

    # Create a bar plot using Plotly
    fig_returns_deposits = px.bar(monthly_returns,
                                  x='year_month',
                                  y=['total_profit', 'total_deposit'],
                                  barmode='group',
                                  labels={'value': 'Amount', 'year_month': 'Year-Month'},
                                  title='Total Profit and Total Deposit',
                                  color_discrete_map={'total_profit': 'green', 'total_deposit': 'orange'})

    fig_returns_deposits = px.line(monthly_returns,
                                   x='year_month',
                                   y=['moving_avg_profit_12', 'moving_avg_deposit_12'])

    fig_returns_deposits.update_layout(xaxis_title='Year-Month',
                                       yaxis_title='Amount',
                                       legend_title='Metrics')

    st.plotly_chart(fig_returns_deposits)

    fig_increase_by_asset = px.bar(summary_by_asset,
                                   x='year_month',
                                   y='net_increase',
                                   color="asset",
                                   title='Total Increase By Asset')

    st.plotly_chart(fig_increase_by_asset)

    st.title("Returns")

    col1, col2 = st.columns(2)
    with col1:
        fig_returns = go.Figure()

        # Add bar trace for total profit
        fig_returns.add_trace(
            go.Bar(x=monthly_returns['year_month'], y=monthly_returns['total_profit'], name='Total Profit',
                   marker_color='skyblue'))

        # Add line trace for moving average - 6 months
        fig_returns.add_trace(go.Scatter(x=monthly_returns['year_month'], y=monthly_returns['moving_avg_profit_6'],
                                         name='6-Month Moving Average', mode='lines+markers',
                                         line=dict(color='yellow', width=2)))

        # Add line trace for moving average - 12 months
        fig_returns.add_trace(go.Scatter(x=monthly_returns['year_month'], y=monthly_returns['moving_avg_profit_12'],
                                         name='12-Month Moving Average', mode='lines+markers',
                                         line=dict(color='green', width=2)))

        # Customize layout
        fig_returns.update_layout(title='Total Profit with Moving Averages',
                                  xaxis_title='Year-Month',
                                  yaxis_title='Amount',
                                  xaxis=dict(tickformat='%Y-%m'),
                                  legend=dict(x=0.1, y=1))
        st.plotly_chart(fig_returns)
    with col2:
        fig_returns_percentage = go.Figure()

        # Add bar trace for total profit
        fig_returns_percentage.add_trace(
            go.Bar(x=monthly_returns['year_month'], y=monthly_returns['total_return'], name='Total Return',
                   marker_color='skyblue'))

        # Add line trace for moving average - 6 months
        fig_returns_percentage.add_trace(
            go.Scatter(x=monthly_returns['year_month'], y=monthly_returns['moving_avg_return_6'],
                       name='6-Month Moving Average', mode='lines+markers',
                       line=dict(color='yellow', width=2)))

        # Add line trace for moving average - 12 months
        fig_returns_percentage.add_trace(
            go.Scatter(x=monthly_returns['year_month'], y=monthly_returns['moving_avg_return_12'],
                       name='12-Month Moving Average', mode='lines+markers',
                       line=dict(color='green', width=2)))

        # Customize layout
        fig_returns_percentage.update_layout(title='Total Return with Moving Averages',
                                             xaxis_title='Year-Month',
                                             yaxis_title='Amount',
                                             xaxis=dict(tickformat='%Y-%m'),
                                             legend=dict(x=0.1, y=1))

        st.plotly_chart(fig_returns_percentage)

    fig_return_by_asset = px.bar(summary_by_asset,
                                 x='year_month',
                                 y='profit',
                                 color="asset",
                                 title='Total Return By Asset')

    st.plotly_chart(fig_return_by_asset)

    st.title("Deposits")
    fig_deposits = go.Figure()

    # Add bar trace for total profit
    fig_deposits.add_trace(
        go.Bar(x=monthly_returns['year_month'], y=monthly_returns['total_deposit'], name='Total Deposit',
               marker_color='skyblue'))

    fig_deposits.add_trace(go.Scatter(x=monthly_returns['year_month'], y=monthly_returns['moving_avg_deposit_6'],
                                      name='6-Month Moving Average', mode='lines+markers',
                                      line=dict(color='yellow', width=2)))

    fig_deposits.add_trace(go.Scatter(x=monthly_returns['year_month'], y=monthly_returns['moving_avg_deposit_12'],
                                      name='12-Month Moving Average', mode='lines+markers',
                                      line=dict(color='green', width=2)))

    fig_deposits.update_layout(title='Total Deposits',
                               xaxis_title='Year-Month',
                               yaxis_title='Amount',
                               xaxis=dict(tickformat='%Y-%m'),
                               legend=dict(x=0.1, y=1))

    st.plotly_chart(fig_deposits)

    fig_deposit_by_asset = px.bar(summary_by_asset,
                                  x='year_month',
                                  y='deposit',
                                  color="asset",
                                  title='Total Deposit By Asset')

    st.plotly_chart(fig_deposit_by_asset)


plot_summary()
plot_history()
