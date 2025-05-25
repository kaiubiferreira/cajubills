import streamlit as st
import pandas as pd
import os
from ofx_parser_script import process_all_ofx_files, categorize_transactions, COLUMN_ID, COLUMN_MEMO, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY, COLUMN_DATE, COLUMN_AMOUNT, COLUMN_TYPE, COLUMN_ACCOUNT_TYPE

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
    st.header("Summary by Category")
    summary_df = raw_transactions_df.groupby([COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]).agg(
        transaction_count=(COLUMN_ID, 'count'),
        total_amount=(COLUMN_AMOUNT, 'sum')
    ).reset_index()
    summary_df[COLUMN_AMOUNT] = summary_df['total_amount'].round(2)

    # Prepare data for stacked bar charts
    # Count plot
    pivot_count_df = summary_df.pivot_table(
        index=COLUMN_MAIN_CATEGORY, 
        columns=COLUMN_SUB_CATEGORY, 
        values='transaction_count', 
        fill_value=0
    )
    # Sort count_df by total count per main category
    if not pivot_count_df.empty:
        sorted_count_index = pivot_count_df.sum(axis=1).sort_values(ascending=False).index
        pivot_count_df = pivot_count_df.reindex(sorted_count_index)
        # Sort sub-categories (columns) by their total sum for consistent stacking order
        sorted_sub_cat_columns_count = pivot_count_df.sum(axis=0).sort_values(ascending=False).index
        pivot_count_df = pivot_count_df[sorted_sub_cat_columns_count]

    # Amount plot
    pivot_amount_df = summary_df.pivot_table(
        index=COLUMN_MAIN_CATEGORY, 
        columns=COLUMN_SUB_CATEGORY, 
        values='total_amount', 
        fill_value=0
    )
    # Sort amount_df by total amount per main category
    if not pivot_amount_df.empty:
        sorted_amount_index = pivot_amount_df.sum(axis=1).sort_values(ascending=False).index
        pivot_amount_df = pivot_amount_df.reindex(sorted_amount_index)
        # Sort sub-categories (columns) by their total sum for consistent stacking order
        sorted_sub_cat_columns_amount = pivot_amount_df.sum(axis=0).sort_values(ascending=False).index
        pivot_amount_df = pivot_amount_df[sorted_sub_cat_columns_amount]

    plot_col1, plot_col2 = st.columns(2)
    with plot_col1:
        st.subheader("Transaction Count by Category")
        if not pivot_count_df.empty:
            st.bar_chart(pivot_count_df)
        else:
            st.write("No data to display for count chart.")
    
    with plot_col2:
        st.subheader("Transaction Amount by Category")
        if not pivot_amount_df.empty:
            st.bar_chart(pivot_amount_df)
        else:
            st.write("No data to display for amount chart.")
    
    st.markdown("--- ") # Separator before the editor

    st.header("Transaction Editor")
    st.info(f"Loaded {len(raw_transactions_df)} total transactions for editing below.")

    # --- Filtering --- 
    all_available_main_categories = sorted(list(raw_transactions_df[COLUMN_MAIN_CATEGORY].unique()))
    filter_options = ["All Categories"] + all_available_main_categories
    
    selected_filter_category = st.selectbox(
        "Filter by Main Category:",
        options=filter_options,
        key='filter_main_category'
    )

    # Apply filter and set display_transactions flag
    display_transactions = False
    if selected_filter_category == "All Categories":
        st.write("Please select a category to view and edit transactions.")
        # Clear session state for transactions if "All Categories" is selected
        if 'transactions_to_edit' in st.session_state:
            st.session_state.transactions_to_edit = [] 
    else:
        filtered_transactions_df = raw_transactions_df[raw_transactions_df[COLUMN_MAIN_CATEGORY] == selected_filter_category].copy()
        st.write(f"Displaying {len(filtered_transactions_df)} transactions for category: {selected_filter_category}")
        display_transactions = True

    # --- Session state for editable transactions --- 
    # Re-initialize session state if filter changes or if it's not initialized
    if 'last_filter' not in st.session_state or st.session_state.last_filter != selected_filter_category or 'transactions_to_edit' not in st.session_state:
        if display_transactions:
            # Ensure COLUMN_ID is included for saving purposes, and add new columns
            st.session_state.transactions_to_edit = filtered_transactions_df[[COLUMN_ID, COLUMN_DATE, COLUMN_MEMO, COLUMN_AMOUNT, COLUMN_TYPE, COLUMN_ACCOUNT_TYPE, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]].to_dict(orient='records')
        else:
            st.session_state.transactions_to_edit = []
        st.session_state.last_filter = selected_filter_category

    # --- Displaying transactions using st.data_editor --- 
    if display_transactions:
        if st.session_state.transactions_to_edit: # Check if there are transactions to show
            # Create DataFrame for the editor from the list of dicts in session state
            editor_df = pd.DataFrame(st.session_state.transactions_to_edit)

            # Prepare category lists for dropdowns in data_editor
            all_main_categories_for_dropdown = sorted(list(raw_transactions_df[COLUMN_MAIN_CATEGORY].unique()))
            if 'Não Categorizado' not in all_main_categories_for_dropdown:
                all_main_categories_for_dropdown.insert(0, 'Não Categorizado')
            
            all_sub_categories_for_dropdown = sorted(list(raw_transactions_df[COLUMN_SUB_CATEGORY].unique()))
            if 'Não Categorizado' not in all_sub_categories_for_dropdown:
                all_sub_categories_for_dropdown.insert(0, 'Não Categorizado')

            st.markdown("### Edit Transactions in Table")
            editor_key = "transaction_data_editor"
            
            column_config = {
                COLUMN_ID: None, # Hide the ID column from display
                COLUMN_DATE: st.column_config.DateColumn("Date", disabled=True, format="YYYY-MM-DD"),
                COLUMN_MEMO: st.column_config.TextColumn("Descrição", disabled=True),
                COLUMN_AMOUNT: st.column_config.NumberColumn("Valor", format="%.2f", disabled=True),
                COLUMN_TYPE: st.column_config.TextColumn("Type", disabled=True),
                COLUMN_ACCOUNT_TYPE: st.column_config.TextColumn("Account Type", disabled=True),
                COLUMN_MAIN_CATEGORY: st.column_config.SelectboxColumn(
                    "Main Category",
                    options=all_main_categories_for_dropdown,
                    required=False # Allow unsetting or set to True if category is mandatory
                ),
                COLUMN_SUB_CATEGORY: st.column_config.SelectboxColumn(
                    "Subcategory",
                    options=all_sub_categories_for_dropdown,
                    required=False # Allow unsetting
                )
            }
            
            # st.data_editor returns the edited DataFrame.
            # It uses st.session_state[key]["edited_rows"] to track edits.
            edited_df_from_editor = st.data_editor(
                editor_df, 
                column_config=column_config,
                key=editor_key,
                hide_index=True,
                num_rows="fixed" # Prevent users from adding/deleting rows
            )

            # Process edits stored in session state by the data_editor
            # Check if the editor key and 'edited_rows' exist in session_state
            if editor_key in st.session_state and "edited_rows" in st.session_state[editor_key]:
                edited_rows_data = st.session_state[editor_key]["edited_rows"] # Get the dictionary of edits
                
                if edited_rows_data: # Check if there are any edits recorded
                    actually_saved_something = False # Flag to track if any save operation occurs
                    for row_idx_str, changed_cols_dict in edited_rows_data.items():
                        row_idx = int(row_idx_str) # Convert string row index to int
                        
                        # Retrieve transaction ID and original categories from the original editor_df
                        # (DataFrame initially passed to st.data_editor)
                        transaction_id_val = editor_df.iloc[row_idx][COLUMN_ID]
                        original_main_cat_val = editor_df.iloc[row_idx][COLUMN_MAIN_CATEGORY]
                        original_sub_cat_val = editor_df.iloc[row_idx][COLUMN_SUB_CATEGORY]

                        # Determine new categories, defaulting to original if not present in changed_cols_dict
                        new_main_cat_val = changed_cols_dict.get(COLUMN_MAIN_CATEGORY, original_main_cat_val)
                        new_sub_cat_val = changed_cols_dict.get(COLUMN_SUB_CATEGORY, original_sub_cat_val)

                        # Save if categories have actually changed
                        if (new_main_cat_val != original_main_cat_val or 
                            new_sub_cat_val != original_sub_cat_val):
                            save_user_category(transaction_id_val, new_main_cat_val, new_sub_cat_val)
                            actually_saved_something = True
                    
                    if actually_saved_something:
                        load_all_transactions_data.clear() # Clear cache to reload all data
                        st.toast("Categories updated successfully!", icon="✅")
                        
                        # CRITICAL: Clear the processed edits from session state for this specific editor
                        st.session_state[editor_key]["edited_rows"] = {} 
                        
                        # Rerun the app to reflect changes everywhere
                        st.rerun()
        else: # This means display_transactions is True, but st.session_state.transactions_to_edit is empty
            st.write(f"No transactions found for category: {selected_filter_category}.")
    # If display_transactions is False, the message "Please select a category..." is shown earlier.

else:
    st.warning("No transactions loaded. Please check your OFX file paths and ensure they contain data.")

if st.sidebar.button("Refresh All Data"):
    load_all_transactions_data.clear() # Clear the cache
    st.rerun() # Rerun the app to reload data from scratch

# To run this app: streamlit run src/transaction_editor_app.py 