import streamlit as st


def button(label):
    st.markdown(
        """
        <style>
        button[kind="primary"] {
            background-color: #007bff;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        button[kind="primary"]:hover {
            background-color: #0056b3;
            color: white;
        }
        button[kind="primary"]:focus {
            outline: none;
            box-shadow: none;
        }
        </style>
        """, unsafe_allow_html=True
    )

    if st.button(label, type="primary"):
        st.session_state.selected_view = label
