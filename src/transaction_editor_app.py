import streamlit as st
import pandas as pd
import os
from ofx_parser_script import process_all_ofx_files, categorize_transactions, COLUMN_ID, COLUMN_MEMO, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY, COLUMN_DATE, COLUMN_AMOUNT

USER_CATEGORIES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources', 'user_defined_categories.csv')

def load_user_categories():
    if os.path.exists(USER_CATEGORIES_FILE):
        try:
            return pd.read_csv(USER_CATEGORIES_FILE)
        except pd.errors.EmptyDataError:
            # Return an empty DataFrame with the expected columns if the CSV is empty
            return pd.DataFrame(columns=[COLUMN_ID, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY])
        except Exception as e:
            st.error(f"Error loading user-defined categories: {e}")
            return pd.DataFrame(columns=[COLUMN_ID, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY])
    return pd.DataFrame(columns=[COLUMN_ID, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY])

def save_user_category(transaction_id, main_category, sub_category):
    user_categories_df = load_user_categories()
    # Remove existing entry for this transaction_id if it exists
    user_categories_df = user_categories_df[user_categories_df[COLUMN_ID] != transaction_id]
    # Append new entry
    new_entry = pd.DataFrame([{COLUMN_ID: transaction_id, COLUMN_MAIN_CATEGORY: main_category, COLUMN_SUB_CATEGORY: sub_category}])
    user_categories_df = pd.concat([user_categories_df, new_entry], ignore_index=True)
    user_categories_df.to_csv(USER_CATEGORIES_FILE, index=False)

def get_project_root():
    # Assumes this script is in src/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@st.cache_data # Cache the loaded and processed transactions
def load_all_transactions_data():
    project_root = get_project_root()
    resources_base_path = os.path.join(project_root, 'resources', 'files')
    
    # Check if the OFX files directory exists
    if not os.path.isdir(resources_base_path):
        st.error(f"Error: Base directory for OFX files not found: {resources_base_path}")
        st.error("Please ensure the 'resources/files' directory exists at the project root or adjust path in the script.")
        return pd.DataFrame() # Return empty DataFrame

    combined_df = process_all_ofx_files(resources_base_path)
    if not combined_df.empty:
        # Ensure date is in datetime format and just date part
        if COLUMN_DATE in combined_df.columns:
            try:
                combined_df[COLUMN_DATE] = pd.to_datetime(combined_df[COLUMN_DATE]).dt.date
            except Exception as e:
                st.warning(f"Could not format date column: {e}")
        if COLUMN_AMOUNT in combined_df.columns:
            combined_df[COLUMN_AMOUNT] = pd.to_numeric(combined_df[COLUMN_AMOUNT], errors='coerce').fillna(0.0)
        # Pass the user categories file path to categorize_transactions
        categorized_df = categorize_transactions(combined_df.copy(), USER_CATEGORIES_FILE)
        return categorized_df
    return pd.DataFrame()

st.set_page_config(layout="wide")
st.title("Transaction Category Editor")

# Load data - this will be cached
raw_transactions_df = load_all_transactions_data()

if not raw_transactions_df.empty:
    st.info(f"Loaded {len(raw_transactions_df)} total transactions.")

    # --- Filtering --- 
    all_available_main_categories = sorted(list(raw_transactions_df[COLUMN_MAIN_CATEGORY].unique()))
    filter_options = ["All Categories"] + all_available_main_categories
    
    selected_filter_category = st.selectbox(
        "Filter by Main Category:",
        options=filter_options,
        key='filter_main_category'
    )

    # Apply filter
    if selected_filter_category == "All Categories":
        filtered_transactions_df = raw_transactions_df.copy()
    else:
        filtered_transactions_df = raw_transactions_df[raw_transactions_df[COLUMN_MAIN_CATEGORY] == selected_filter_category].copy()
    
    st.write(f"Displaying {len(filtered_transactions_df)} transactions after filter.")

    # --- Session state for editable transactions --- 
    # Re-initialize session state if filter changes or if it's not initialized
    if 'last_filter' not in st.session_state or st.session_state.last_filter != selected_filter_category or 'transactions_to_edit' not in st.session_state:
        st.session_state.transactions_to_edit = filtered_transactions_df[[COLUMN_ID, COLUMN_DATE, COLUMN_MEMO, COLUMN_AMOUNT, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]].to_dict(orient='records')
        st.session_state.last_filter = selected_filter_category

    # --- Displaying transactions --- 
    if not filtered_transactions_df.empty:
        # Get unique categories for dropdowns from the unfiltered data to have all options
        all_main_categories_for_dropdown = sorted(list(raw_transactions_df[COLUMN_MAIN_CATEGORY].unique()))
        if 'Não Categorizado' not in all_main_categories_for_dropdown:
            all_main_categories_for_dropdown.insert(0, 'Não Categorizado')
        
        all_sub_categories_for_dropdown = sorted(list(raw_transactions_df[COLUMN_SUB_CATEGORY].unique()))
        if 'Não Categorizado' not in all_sub_categories_for_dropdown:
            all_sub_categories_for_dropdown.insert(0, 'Não Categorizado')

        st.markdown("### Edit Transactions")

        # Column Headers
        header_cols = st.columns([1.5, 3, 1.5, 2, 2]) # Date, Descrição, Valor, Main Category, Subcategory
        header_cols[0].markdown("**Date**")
        header_cols[1].markdown("**Descrição**")
        header_cols[2].markdown("**Valor**")
        header_cols[3].markdown("**Main Category**")
        header_cols[4].markdown("**Subcategory**")
        st.markdown("--- ", unsafe_allow_html=True)

        def handle_category_autosave(tx_id, loop_idx):
            # Retrieve current values from session state using their keys
            new_main_cat = st.session_state[f"main_{tx_id}_{loop_idx}"]
            new_sub_cat = st.session_state[f"sub_{tx_id}_{loop_idx}"]
            
            save_user_category(tx_id, new_main_cat, new_sub_cat)
            
            # Update in-memory session state for immediate reflection (optional, but good for consistency)
            for tx in st.session_state.transactions_to_edit:
                if tx[COLUMN_ID] == tx_id:
                    tx[COLUMN_MAIN_CATEGORY] = new_main_cat
                    tx[COLUMN_SUB_CATEGORY] = new_sub_cat
                    break
            
            load_all_transactions_data.clear() # Invalidate cache
            st.toast(f"Auto-saved: {tx_id} to {new_main_cat} / {new_sub_cat}", icon="💾")
            # No explicit rerun needed, as widget interaction causes it.
            # If categories were to affect filtering or other elements immediately, a rerun might be desired.

        for i, transaction in enumerate(st.session_state.transactions_to_edit):
            cols = st.columns([1.5, 3, 1.5, 2, 2]) # Date, Descrição, Valor, Main Category, Subcategory
            
            transaction_date = transaction.get(COLUMN_DATE, 'N/A')
            if isinstance(transaction_date, pd.Timestamp):
                cols[0].text(transaction_date.strftime('%Y-%m-%d'))
            else:
                cols[0].text(str(transaction_date)) # Display date
            
            cols[1].text(transaction.get(COLUMN_MEMO, 'N/A'))
            
            amount = transaction.get(COLUMN_AMOUNT, 0.0)
            cols[2].text(f"{amount:.2f}") # Display Amount
            
            # Editable Main Category Column
            current_main_cat_val = transaction.get(COLUMN_MAIN_CATEGORY, 'Não Categorizado')
            current_main_cat_index = all_main_categories_for_dropdown.index(current_main_cat_val) if current_main_cat_val in all_main_categories_for_dropdown else 0
            cols[3].selectbox(
                f"MainCat_{transaction[COLUMN_ID]}_{i}",
                all_main_categories_for_dropdown, 
                index=current_main_cat_index, 
                key=f"main_{transaction[COLUMN_ID]}_{i}", 
                label_visibility="collapsed",
                on_change=handle_category_autosave,
                args=(transaction[COLUMN_ID], i)
            )
            
            # Editable Subcategory Column
            current_sub_cat_val = transaction.get(COLUMN_SUB_CATEGORY, 'Não Categorizado')
            current_sub_cat_index = all_sub_categories_for_dropdown.index(current_sub_cat_val) if current_sub_cat_val in all_sub_categories_for_dropdown else 0
            cols[4].selectbox(
                f"SubCat_{transaction[COLUMN_ID]}_{i}",
                all_sub_categories_for_dropdown, 
                index=current_sub_cat_index, 
                key=f"sub_{transaction[COLUMN_ID]}_{i}", 
                label_visibility="collapsed",
                on_change=handle_category_autosave,
                args=(transaction[COLUMN_ID], i)
            )
        st.markdown("--- ", unsafe_allow_html=True)
    else:
        st.write("No transactions match the current filter.")

else:
    st.warning("No transactions loaded. Please check your OFX file paths and ensure they contain data.")

if st.sidebar.button("Refresh All Data"):
    load_all_transactions_data.clear() # Clear the cache
    st.experimental_rerun() # Rerun the app to reload data from scratch

# To run this app: streamlit run src/transaction_editor_app.py 