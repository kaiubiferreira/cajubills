import streamlit as st

st.set_page_config(
    page_title="CajuBills Finance Dashboard",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Welcome to CajuBills! 💰")
st.sidebar.success("Select a dashboard or tool above.")

st.markdown("""
### Your Personal Finance Overview

Use the navigation panel on the left to explore your financial data:

- **Investments Dashboard**: Track your investment performance, allocations, and projections.
- **Transaction Editor**: View, categorize, and manage your financial transactions.

This dashboard is powered by data processed from your financial accounts and sheets.
Ensure you have run the main data processing pipeline (`run.py`) to have the latest data.
""")

# Add any other global elements or introductions here if needed. 