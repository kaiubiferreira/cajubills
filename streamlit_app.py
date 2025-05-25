import streamlit as st
import pandas as pd
import os

# Ensure the 'src' directory is in the Python path for the import
# This is often handled by running streamlit from the project root
# or by setting PYTHONPATH. For direct script execution, this might be needed:
# import sys
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

try:
    from src.ofx_parser_script import (
        process_all_ofx_files,
        categorize_transactions,
        COLUMN_CATEGORY,
        COLUMN_AMOUNT,
        COLUMN_MEMO,
        COLUMN_DATE,
        COLUMN_ACCOUNT_TYPE,
        COLUMN_TYPE, # Transaction type DEBIT/CREDIT
        COLUMN_ID    # Added missing import for COLUMN_ID
    )
except ImportError:
    st.error("Failed to import 'ofx_parser_script'. "
             "Ensure 'src/ofx_parser_script.py' exists and the 'src' directory is accessible. "
             "If running from a different directory, you might need to adjust PYTHONPATH.")
    st.stop()


@st.cache_data # Cache the data loading and processing
def load_transaction_data():
    """Loads, processes, and categorizes OFX transaction data."""
    # Construct path to resources/files relative to this script's location (project root)
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    resources_base_path = os.path.join(current_script_dir, 'resources', 'files')

    if not os.path.isdir(resources_base_path):
        st.error(f"Error: Base directory for OFX files not found: {resources_base_path}. "
                 "Please ensure 'resources/files' directory exists at the project root.")
        return pd.DataFrame()

    combined_df = process_all_ofx_files(resources_base_path)

    if combined_df.empty:
        # process_all_ofx_files should print warnings if no files/data found
        st.warning("No transaction data was loaded from OFX files. Please check source files and paths.")
        return pd.DataFrame()

    categorized_df = categorize_transactions(combined_df.copy()) # Use .copy() as good practice
    
    # --- Add signed amount for display ---
    # COLUMN_AMOUNT from ofx_parser_script is already an absolute value.
    if not categorized_df.empty and COLUMN_AMOUNT in categorized_df.columns and COLUMN_TYPE in categorized_df.columns:
        categorized_df['signed_amount'] = categorized_df[COLUMN_AMOUNT]
        # Apply negative sign for DEBIT transactions
        categorized_df.loc[categorized_df[COLUMN_TYPE].str.upper() == 'DEBIT', 'signed_amount'] *= -1
    elif not categorized_df.empty:
        categorized_df['signed_amount'] = 0.0 
        st.warning("Could not create signed amounts due to missing Amount or Type columns in the source data.")
    # --- End signed amount ----
    
    return categorized_df

def display_app():
    """Main function to display the Streamlit application."""
    st.set_page_config(page_title="OFX Transaction Viewer", layout="wide")
    st.title("💰 OFX Transaction Viewer")

    # Load data
    master_df = load_transaction_data()

    if master_df.empty:
        st.info("No transaction data available to display. Please check OFX file processing.")
        return

    # --- 1. Category Summary ---
    st.header("📊 Category Summary")
    if COLUMN_CATEGORY in master_df.columns and 'signed_amount' in master_df.columns:
        # Calculate summary: sum of amounts and count of transactions per category
        category_summary_agg = master_df.groupby(COLUMN_CATEGORY).agg(
            total_amount=('signed_amount', 'sum'),
            transaction_count=('signed_amount', 'size')  # 'size' counts rows in each group
        ).sort_values(by='total_amount', ascending=False)

        if not category_summary_agg.empty:
            st.subheader("Net Total by Category (Income - Expenses)")
            # Bar chart will still show only the total amount for clarity
            st.bar_chart(category_summary_agg['total_amount'])

            with st.expander("View Category Summary Data Table"):
                # Rename for display
                display_summary_df = category_summary_agg.reset_index().rename(columns={
                    COLUMN_CATEGORY: 'Category',
                    'total_amount': 'Net Total Amount',
                    'transaction_count': 'Transaction Count'
                })
                st.dataframe(
                    display_summary_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={ # Optional: format the amount column if needed
                        "Net Total Amount": st.column_config.NumberColumn(format="%.2f")
                    }
                )
        else:
            st.info("No data to summarize by category (perhaps all amounts are zero or no categories found).")
    else:
        st.warning(f"Required columns ('{COLUMN_CATEGORY}' or 'signed_amount') not found in the data. "
                   "Cannot display category summary.")

    st.divider()

    # --- NEW: Memo Summary Table ---
    st.header("📝 Memo Summary")
    if COLUMN_MEMO in master_df.columns and COLUMN_CATEGORY in master_df.columns and 'signed_amount' in master_df.columns:
        # --- Category Filter for Memo Summary ---
        unique_categories_for_memo_summary = sorted(master_df[COLUMN_CATEGORY].unique().tolist())
        options_for_memo_cat_filter = ["All Categories"] + unique_categories_for_memo_summary
        
        selected_memo_cat_options = st.multiselect(
            "Filter Memo Summary by Category:",
            options=options_for_memo_cat_filter,
            default=["All Categories"],
            key="memo_summary_category_filter" # Unique key for this multiselect
        )

        filtered_master_for_memo_summary = master_df.copy()
        if selected_memo_cat_options and "All Categories" not in selected_memo_cat_options:
            filtered_master_for_memo_summary = filtered_master_for_memo_summary[
                filtered_master_for_memo_summary[COLUMN_CATEGORY].isin(selected_memo_cat_options)
            ]
        elif not selected_memo_cat_options:
            filtered_master_for_memo_summary = pd.DataFrame(columns=master_df.columns)
        # --- End Category Filter for Memo Summary ---

        if not filtered_master_for_memo_summary.empty:
            memo_summary_agg = filtered_master_for_memo_summary.groupby(
                [COLUMN_MEMO, COLUMN_CATEGORY] # Group by both Memo and Category
            ).agg(
                transaction_count=('signed_amount', 'size'),
                total_amount=('signed_amount', 'sum')
            ).sort_values(by='transaction_count', ascending=False)

            if not memo_summary_agg.empty:
                st.subheader("Summary by Transaction Description (and Category)")
                
                display_memo_summary_df = memo_summary_agg.reset_index().rename(columns={
                    COLUMN_MEMO: 'Description',
                    COLUMN_CATEGORY: 'Category', # Add Category to display
                    'transaction_count': 'Transaction Count',
                    'total_amount': 'Net Total Amount'
                })
                
                # Reorder columns to have Category next to Description
                cols_order = ['Description', 'Category', 'Transaction Count', 'Net Total Amount']
                # Ensure all columns in cols_order actually exist to prevent errors if something was empty
                existing_cols_for_reorder = [col for col in cols_order if col in display_memo_summary_df.columns]
                display_memo_summary_df = display_memo_summary_df[existing_cols_for_reorder]

                st.dataframe(
                    display_memo_summary_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Net Total Amount": st.column_config.NumberColumn(format="%.2f")
                    }
                )
            else:
                st.info("No memo data to summarize for the selected categories.")
        else:
            st.info("No transactions match the selected categories for Memo Summary.")
    else:
        st.warning(f"Required columns ('{COLUMN_MEMO}', '{COLUMN_CATEGORY}' or 'signed_amount') not found for Memo Summary.")
    
    st.divider()
    # --- END: Memo Summary Table ---

    # --- 2. Transaction Filters and Table ---
    st.header("📄 Transaction Details")

    # Prepare DataFrame for display - select and reorder columns
    display_columns_ordered = [
        COLUMN_DATE, COLUMN_MEMO, 'signed_amount', COLUMN_CATEGORY, # Use signed_amount
        COLUMN_TYPE, COLUMN_ACCOUNT_TYPE, COLUMN_ID
    ]
    # Filter out any columns that might not exist in master_df for some reason
    existing_display_columns = [col for col in display_columns_ordered if col in master_df.columns]
    
    # Make a working copy for filtering
    view_df = master_df[existing_display_columns].copy()


    # Category Filter
    if COLUMN_CATEGORY in view_df.columns:
        unique_categories = sorted(view_df[COLUMN_CATEGORY].unique().tolist())
        
        # Add an "All Categories" option
        options_for_multiselect = ["All Categories"] + unique_categories
        
        selected_category_options = st.multiselect(
            "Filter by Category:",
            options=options_for_multiselect,
            default=["All Categories"] # Default to showing all
        )

        # Apply filter
        if selected_category_options and "All Categories" not in selected_category_options:
            view_df = view_df[view_df[COLUMN_CATEGORY].isin(selected_category_options)]
        elif not selected_category_options: # If user deselects everything including "All"
             view_df = pd.DataFrame(columns=existing_display_columns) # Show empty table
        # If "All Categories" is selected (or is the only one selected), no category filter is applied to view_df

    else:
        st.warning(f"'{COLUMN_CATEGORY}' column not found. Cannot filter by category.")

    # Display Transaction Table
    if not view_df.empty:
        st.subheader(f"Displaying {len(view_df)} Transactions")
        # Sort by date by default (newest first)
        st.dataframe(
            view_df.sort_values(by=COLUMN_DATE, ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "signed_amount": st.column_config.NumberColumn(
                    "Amount", # Display name for the column
                    format="%.2f"
                )
            }
        )
    elif master_df.empty : # This case is already handled by the top-level empty check
        pass # Already handled: no data to display at all
    else: # master_df is not empty, but view_df is (due to filters)
        st.info("No transactions match the current filter criteria.")

if __name__ == "__main__":
    display_app() 