import streamlit as st
import pandas as pd
import os
from ofx_parser_script import process_all_ofx_files, categorize_transactions, COLUMN_ID, COLUMN_MEMO, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY, COLUMN_DATE, COLUMN_AMOUNT, COLUMN_TYPE, COLUMN_ACCOUNT_TYPE

COLUMN_COMBINED_CATEGORY_DISPLAY = "Categoria / Sub categoria" # New constant

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
    
    # Set index=0 to default to "All Categories"
    selected_filter_category = st.selectbox(
        "Filter by Main Category:",
        options=filter_options,
        index=0, 
        key='filter_main_category'
    )

    # Determine transactions to display based on filter
    if selected_filter_category == "All Categories":
        filtered_transactions_df = raw_transactions_df.copy()
        if not filtered_transactions_df.empty:
            st.write(f"Displaying all {len(filtered_transactions_df)} transactions.")
        # If filtered_transactions_df is empty (i.e. raw_transactions_df was empty), 
        # the later logic will handle showing "No transactions available".
    else:
        filtered_transactions_df = raw_transactions_df[raw_transactions_df[COLUMN_MAIN_CATEGORY] == selected_filter_category].copy()
        if not filtered_transactions_df.empty:
            st.write(f"Displaying {len(filtered_transactions_df)} transactions for category: {selected_filter_category}.")
        # If filtered_transactions_df is empty for a specific category, 
        # the later logic will handle showing "No transactions found for category...".
    
    # display_transactions will always be True if raw_transactions_df is not empty, 
    # as this whole block is under `if not raw_transactions_df.empty:`
    display_transactions = True 


    # --- Session state for editable transactions --- 
    # Re-initialize session state if filter changes or if it's not initialized,
    # or if 'transactions_to_edit' is not in session_state (e.g., first load)
    if ('last_filter' not in st.session_state or \
        st.session_state.last_filter != selected_filter_category or \
        'transactions_to_edit' not in st.session_state or \
        # Force reload if current transactions_to_edit is empty but shouldn't be (e.g. switched to 'All Categories' and it's empty)
        (not st.session_state.transactions_to_edit and not filtered_transactions_df.empty) or \
        # Force reload if the number of transactions to edit mismatches the filtered count (covers some edge cases of state)
        (st.session_state.transactions_to_edit and len(st.session_state.transactions_to_edit) != len(filtered_transactions_df)) and selected_filter_category == st.session_state.get('last_filter', None) ):


        if not filtered_transactions_df.empty:
            temp_df = filtered_transactions_df[[COLUMN_ID, COLUMN_DATE, COLUMN_MEMO, COLUMN_AMOUNT, COLUMN_TYPE, COLUMN_ACCOUNT_TYPE, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]].copy()
            temp_df[COLUMN_COMBINED_CATEGORY_DISPLAY] = temp_df[COLUMN_MAIN_CATEGORY].astype(str) + " / " + temp_df[COLUMN_SUB_CATEGORY].astype(str)
            st.session_state.transactions_to_edit = temp_df.to_dict(orient='records')
        else:
            st.session_state.transactions_to_edit = []
        st.session_state.last_filter = selected_filter_category

    # --- Displaying transactions using st.data_editor --- 
    if display_transactions:
        if st.session_state.transactions_to_edit: # Check if there are transactions to show
            # Create DataFrame for the editor from the list of dicts in session state
            editor_df = pd.DataFrame(st.session_state.transactions_to_edit)

            # Prepare category lists for dropdowns in data_editor
            # Create combined category options for the dropdown
            unique_main_categories = raw_transactions_df[COLUMN_MAIN_CATEGORY].unique()
            unique_sub_categories = raw_transactions_df[COLUMN_SUB_CATEGORY].unique()
            
            all_combined_categories_for_dropdown = set()
            if not raw_transactions_df.empty:
                for _, row in raw_transactions_df.iterrows():
                    main_cat = str(row[COLUMN_MAIN_CATEGORY])
                    sub_cat = str(row[COLUMN_SUB_CATEGORY])
                    all_combined_categories_for_dropdown.add(f"{main_cat} / {sub_cat}")
            
            # Ensure "Não Categorizado / Não Categorizado" is an option
            default_combined_category = "Não Categorizado / Não Categorizado"
            if default_combined_category not in all_combined_categories_for_dropdown:
                all_combined_categories_for_dropdown.add(default_combined_category)
            
            sorted_combined_categories = sorted(list(all_combined_categories_for_dropdown))


            st.markdown("### Edit Transactions in Table")
            editor_key = "transaction_data_editor"
            
            column_config = {
                COLUMN_ID: None, # Hide the ID column from display
                COLUMN_DATE: st.column_config.DateColumn("Date", disabled=True, format="YYYY-MM-DD"),
                COLUMN_MEMO: st.column_config.TextColumn("Descrição", disabled=True),
                COLUMN_AMOUNT: st.column_config.NumberColumn("Valor", format="%.2f", disabled=True),
                COLUMN_TYPE: st.column_config.TextColumn("Type", disabled=True),
                COLUMN_ACCOUNT_TYPE: st.column_config.TextColumn("Account Type", disabled=True),
                COLUMN_MAIN_CATEGORY: None, # Hide original main category
                COLUMN_SUB_CATEGORY: None,  # Hide original sub category
                COLUMN_COMBINED_CATEGORY_DISPLAY: st.column_config.SelectboxColumn(
                    COLUMN_COMBINED_CATEGORY_DISPLAY,
                    options=sorted_combined_categories,
                    required=False,
                    width="large"  # Added width parameter
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

            # --- Save All Button ---
            if st.button("Save All Changes", key="save_all_button"):
                if editor_key in st.session_state and "edited_rows" in st.session_state[editor_key]:
                    edited_rows_data = st.session_state[editor_key]["edited_rows"]
                    
                    if edited_rows_data:
                        actually_saved_something = False
                        for row_idx_str, changed_cols_dict in edited_rows_data.items():
                            row_idx = int(row_idx_str)
                            
                            transaction_id_val = editor_df.iloc[row_idx][COLUMN_ID]
                            original_main_cat_val = editor_df.iloc[row_idx][COLUMN_MAIN_CATEGORY]
                            original_sub_cat_val = editor_df.iloc[row_idx][COLUMN_SUB_CATEGORY]

                            new_main_cat_val = original_main_cat_val
                            new_sub_cat_val = original_sub_cat_val

                            if COLUMN_COMBINED_CATEGORY_DISPLAY in changed_cols_dict:
                                combined_value_str = changed_cols_dict[COLUMN_COMBINED_CATEGORY_DISPLAY]
                                if combined_value_str and " / " in combined_value_str:
                                    parts = combined_value_str.split(" / ", 1)
                                    new_main_cat_val = parts[0].strip()
                                    new_sub_cat_val = parts[1].strip()
                                elif combined_value_str: # Handle cases with no " / " (e.g. just main category)
                                    new_main_cat_val = combined_value_str.strip()
                                    new_sub_cat_val = "Não Categorizado" # Default sub_category
                                else: # Handle empty selection
                                    new_main_cat_val = "Não Categorizado"
                                    new_sub_cat_val = "Não Categorizado"
                            
                            # Save if categories have actually changed
                            if (new_main_cat_val != original_main_cat_val or 
                                new_sub_cat_val != original_sub_cat_val):
                                save_user_category(transaction_id_val, new_main_cat_val, new_sub_cat_val)
                                actually_saved_something = True
                        
                        if actually_saved_something:
                            load_all_transactions_data.clear()
                            st.toast("All changes saved successfully!", icon="✅")
                            st.session_state[editor_key]["edited_rows"] = {} 
                            st.rerun()
                        else:
                            st.toast("No changes to save.", icon="🤷")
                    else:
                        st.toast("No edits made to save.", icon="🤷")
                else:
                    st.toast("No edits detected.", icon="🤷")
        else: # This means display_transactions is True, but st.session_state.transactions_to_edit is empty
            if selected_filter_category == "All Categories" and raw_transactions_df.empty:
                 st.write("No transactions available to display.")
            elif selected_filter_category == "All Categories" and not raw_transactions_df.empty: # Should be caught by filtered_transactions_df
                 st.write("No transactions to display. Check data loading.") # Should ideally not happen if raw_transactions_df is not empty
            else:
                 st.write(f"No transactions found for category: {selected_filter_category}.")
    # If display_transactions is False, the message "Please select a category..." is shown earlier.

else:
    st.warning("No transactions loaded. Please check your OFX file paths and ensure they contain data.")

if st.sidebar.button("Refresh All Data"):
    load_all_transactions_data.clear() # Clear the cache
    st.rerun() # Rerun the app to reload data from scratch

# To run this app: streamlit run src/transaction_editor_app.py 