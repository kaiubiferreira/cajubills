import streamlit as st

from dashboard import plot_history
from style import button

st.title("CajuBills")

col1, col2, col3 = st.columns(3)

st.session_state.selected_view = ""

with col1:
    button("Home")

with col2:
    button("History")

with col3:
    button("Forecast")

if st.session_state.selected_view == "History":
    plot_history()
