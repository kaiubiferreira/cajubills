import pandas as pd
import plotly.express as px
import streamlit as st

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


def plot():
    print("Plotting history")
    dates = get_dates()
    print(dates)

    start_date = st.sidebar.date_input('Start Date', value=pd.to_datetime(dates['start_date'].min()))
    end_date = st.sidebar.date_input('End Date', value=pd.to_datetime(dates['end_date'].max()))

    daily_balance = get_daily_balance(start_date, end_date)
    daily_balance_by_asset = get_daily_balance_by_asset(start_date, end_date)
    daily_balance_by_type = get_daily_balance_by_type(start_date, end_date)

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
                orientation="h",  # Horizontal orientation
                yanchor="bottom",  # Anchor to the bottom of the legend
                y=-0.2,  # Adjust vertical positioning below the plot
                xanchor="center",  # Center the legend
                x=0.5  # Align legend in the middle
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
                y=-0.2,  # Adjust vertical positioning below the plot
                xanchor="center",  # Center the legend
                x=0.5  # Align legend in the middle
            )
        )
        st.plotly_chart(fig_type, use_container_width=True)

    fig_asset = px.line(
        daily_balance_by_asset,
        x='date',
        y='value',
        color='asset',
        title='Daily Balance by Asset'
    )

    st.plotly_chart(fig_asset)


plot()
