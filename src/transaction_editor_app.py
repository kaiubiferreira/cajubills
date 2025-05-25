import streamlit as st
import pandas as pd
import os
import altair as alt
import numpy as np # Added numpy for np.nan
from ofx_parser_script import process_all_ofx_files, categorize_transactions, COLUMN_ID, COLUMN_MEMO, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY, COLUMN_DATE, COLUMN_AMOUNT, COLUMN_TYPE, COLUMN_ACCOUNT_TYPE
from datetime import date # Added for date operations
from dateutil.relativedelta import relativedelta # For easy date calculations

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
def load_all_transactions_data(filter_start_date: date):
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
                # Convert to datetime objects first, then extract date part
                combined_df[COLUMN_DATE] = pd.to_datetime(combined_df[COLUMN_DATE]).dt.date
            except Exception as e:
                st.warning(f"Could not format date column: {e}")
        if COLUMN_AMOUNT in combined_df.columns:
            combined_df[COLUMN_AMOUNT] = pd.to_numeric(combined_df[COLUMN_AMOUNT], errors='coerce').fillna(0.0)
        # Pass the user categories file path to categorize_transactions
        categorized_df = categorize_transactions(combined_df.copy(), USER_CATEGORIES_FILE)
            
        # Sort by date descending by default
        if COLUMN_DATE in categorized_df.columns:
            categorized_df = categorized_df.sort_values(by=COLUMN_DATE, ascending=False)

        # --- Apply date filter: from filter_start_date to today --- (Default: last 9 months)
        if COLUMN_DATE in categorized_df.columns:
            end_date_filter = date.today()
            
            # Ensure the date column is in a comparable format (it should be datetime.date objects now)
            categorized_df = categorized_df[
                (categorized_df[COLUMN_DATE] >= filter_start_date) & 
                (categorized_df[COLUMN_DATE] <= end_date_filter)
            ]

        return categorized_df
    return pd.DataFrame()

st.set_page_config(layout="wide")
st.title("Transaction Category Editor")

# --- Global Date Filter --- 
# Calculate default start date (9 months ago)
default_start_date = date.today() - relativedelta(months=9)

selected_start_date = st.date_input(
    "Select Start Date for Analysis:",
    value=default_start_date,
    min_value=date(2000, 1, 1), # Or some other reasonable min
    max_value=date.today(),
    key='global_start_date'
)

st.markdown("--- ") # Add a separator after the date input

# Load data - this will be cached
raw_transactions_df = load_all_transactions_data(filter_start_date=selected_start_date)

if not raw_transactions_df.empty:
    # st.header("Summary by Category")  # Removed header
    # summary_df = raw_transactions_df.groupby([COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]).agg(
    #     transaction_count=(COLUMN_ID, 'count'),
    #     total_amount=(COLUMN_AMOUNT, 'sum')
    # ).reset_index()
    # summary_df[COLUMN_AMOUNT] = summary_df['total_amount'].round(2)

    # # Prepare data for stacked bar charts
    # # Count plot
    # pivot_count_df = summary_df.pivot_table(
    #     index=COLUMN_MAIN_CATEGORY, 
    #     columns=COLUMN_SUB_CATEGORY, 
    #     values='transaction_count', 
    #     fill_value=0
    # )
    # # Sort count_df by total count per main category
    # if not pivot_count_df.empty:
    #     sorted_count_index = pivot_count_df.sum(axis=1).sort_values(ascending=False).index
    #     pivot_count_df = pivot_count_df.reindex(sorted_count_index)
    #     # Sort sub-categories (columns) by their total sum for consistent stacking order
    #     sorted_sub_cat_columns_count = pivot_count_df.sum(axis=0).sort_values(ascending=False).index
    #     pivot_count_df = pivot_count_df[sorted_sub_cat_columns_count]

    # # Amount plot
    # pivot_amount_df = summary_df.pivot_table(
    #     index=COLUMN_MAIN_CATEGORY, 
    #     columns=COLUMN_SUB_CATEGORY, 
    #     values='total_amount', 
    #     fill_value=0
    # )
    # # Sort amount_df by total amount per main category
    # if not pivot_amount_df.empty:
    #     sorted_amount_index = pivot_amount_df.sum(axis=1).sort_values(ascending=False).index
    #     pivot_amount_df = pivot_amount_df.reindex(sorted_amount_index)
    #     # Sort sub-categories (columns) by their total sum for consistent stacking order
    #     sorted_sub_cat_columns_amount = pivot_amount_df.sum(axis=0).sort_values(ascending=False).index
    #     pivot_amount_df = pivot_amount_df[sorted_sub_cat_columns_amount]

    # plot_col1, plot_col2 = st.columns(2) # Removed columns for plots
    # with plot_col1:
    #     st.subheader("Transaction Count by Category")
    #     if not pivot_count_df.empty:
    #         st.bar_chart(pivot_count_df)
    #     else:
    #         st.write("No data to display for count chart.")
    
    # with plot_col2:
    #     st.subheader("Transaction Amount by Category")
    #     if not pivot_amount_df.empty:
    #         st.bar_chart(pivot_amount_df)
    #     else:
    #         st.write("No data to display for amount chart.")

    # --- Monthly Income vs Expenses Chart ---
    # st.markdown("---") # Separator - keep this if the section above had one, or manage spacing if not
    st.header("Monthly Income vs. Expenses")

    def prepare_cash_flow_data(df_input):
        if df_input.empty:
            # Now returns 5 dataframes: net_flow, income_expense_summary, income_ma, expenses_ma, net_flow_ma
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame() 

        categories_to_exclude = ['Ignorar', 'Investimentos', 'Extraordinários']
        df_chart = df_input[~df_input[COLUMN_MAIN_CATEGORY].isin(categories_to_exclude)].copy()
        
        if df_chart.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        df_chart[COLUMN_DATE] = pd.to_datetime(df_chart[COLUMN_DATE])
        df_chart['YearMonth'] = df_chart[COLUMN_DATE].dt.strftime('%Y-%m')
        df_chart = df_chart.sort_values(by='YearMonth')

        # 2. Data for Net line (Overall Net Cash Flow) & its MA
        monthly_net_data_raw = df_chart.groupby('YearMonth') \
                                   .agg(Amount=(COLUMN_AMOUNT, 'sum'))
        
        # Ensure complete month index for net flow and its MA
        if not df_chart.empty:
            all_months_idx_net = pd.date_range(start=df_chart[COLUMN_DATE].min(), end=df_chart[COLUMN_DATE].max(), freq='MS').strftime('%Y-%m')
            base_month_df_net = pd.DataFrame(index=all_months_idx_net)
        else:
            base_month_df_net = pd.DataFrame()

        monthly_net_data = base_month_df_net.join(monthly_net_data_raw, how='left').fillna(0).reset_index().rename(columns={'index': 'YearMonth'})
        monthly_net_data = monthly_net_data.sort_values(by='YearMonth') # Ensure sorted before MA
        
        if not monthly_net_data.empty:
            monthly_net_data['Net_MA'] = monthly_net_data['Amount'].rolling(window=3, min_periods=1).mean()
        
        net_flow_ma_df = monthly_net_data[['YearMonth', 'Net_MA']].copy().rename(columns={'Net_MA':'MovingAverage'})
        if not net_flow_ma_df.empty: net_flow_ma_df['MAType'] = 'Net Flow MA'


        # 3. Data for Income/Expense Summary & Moving Averages
        # Create a complete month index for reliable rolling averages (re-using base_month_df_net as it covers the full range)
        base_month_df_income_expense = base_month_df_net 

        income_monthly_raw = df_chart[
            (df_chart[COLUMN_AMOUNT] > 0) & (df_chart[COLUMN_MAIN_CATEGORY] == 'Renda')
        ].groupby('YearMonth').agg(Amount=(COLUMN_AMOUNT, 'sum'))
        income_monthly = base_month_df_income_expense.join(income_monthly_raw, how='left').fillna(0).reset_index().rename(columns={'index': 'YearMonth'})
        if not income_monthly.empty: 
            income_monthly['Type'] = 'Income'
            income_monthly['Income_MA'] = income_monthly['Amount'].rolling(window=3, min_periods=1).mean()
        
        expenses_monthly_raw = df_chart[df_chart[COLUMN_AMOUNT] < 0].groupby('YearMonth')\
            .agg(Amount=(COLUMN_AMOUNT, 'sum'))
        expenses_monthly = base_month_df_income_expense.join(expenses_monthly_raw, how='left').fillna(0).reset_index().rename(columns={'index': 'YearMonth'})
        if not expenses_monthly.empty: 
            expenses_monthly['Type'] = 'Expenses'
            expenses_monthly['Expenses_MA'] = expenses_monthly['Amount'].rolling(window=3, min_periods=1).mean()
        
        monthly_income_expense_summary = pd.concat([income_monthly, expenses_monthly[expenses_monthly['Type'] == 'Expenses'] ], ignore_index=True)\
            .sort_values(by=['YearMonth', 'Type'])

        income_ma_df = income_monthly[['YearMonth', 'Income_MA']].copy().rename(columns={'Income_MA':'MovingAverage'})
        if not income_ma_df.empty: income_ma_df['MAType'] = 'Income MA'
        expenses_ma_df = expenses_monthly[['YearMonth', 'Expenses_MA']].copy().rename(columns={'Expenses_MA':'MovingAverage'})
        if not expenses_ma_df.empty: expenses_ma_df['MAType'] = 'Expenses MA'
        
        # Return 5 dataframes now
        return monthly_net_data, monthly_income_expense_summary, income_ma_df, expenses_ma_df, net_flow_ma_df

    # Unpack 5 dataframes
    net_flow_data, income_expense_summary_data, income_ma_df, expenses_ma_df, net_flow_ma_df = prepare_cash_flow_data(raw_transactions_df.copy())

    # Define stylish colors
    color_income = '#66c2a5'
    color_expenses = '#fc8d62'
    color_income_ma = '#1b9e77'
    color_expenses_ma = '#d95f02'
    color_net_flow_ma = '#7570b3' # A purple for net flow MA

    # --- Top Row of Charts (Net Flow and Income/Expense Summary) ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Overall Net Monthly Cash Flow")
        if not net_flow_data.empty:
            base_x_encoding_net = alt.X('YearMonth:O', title='Month', axis=alt.Axis(labelAngle=-45), sort=None)
            
            net_flow_bars = alt.Chart(net_flow_data).mark_bar().encode(
                x=base_x_encoding_net,
                y=alt.Y('Amount:Q', title='Net Cash Flow (R$)'),
                color=alt.condition(alt.datum.Amount > 0, alt.value(color_income), alt.value(color_expenses)),
                tooltip=['YearMonth', alt.Tooltip('Amount:Q', format='.2f', title='Net Flow')]
            )

            net_ma_line = alt.Chart(net_flow_ma_df).mark_line(color=color_net_flow_ma, point=True, strokeDash=[3,3]).encode(
                x=base_x_encoding_net,
                y=alt.Y('MovingAverage:Q', title='3-Month MA Net Flow'),
                tooltip=['YearMonth', alt.Tooltip('MovingAverage:Q', format='.2f', title='Net Flow MA (3-Month)')]
            )
            
            net_flow_chart_final = alt.layer(net_flow_bars, net_ma_line).resolve_scale(
                y='shared' # Using shared Y axis; title will be from net_flow_bars
            ).properties(title='Overall Net Cash Flow per Month (with 3-Month MA)')
            st.altair_chart(net_flow_chart_final, use_container_width=True)
        else:
            st.write("No data for Overall Net Monthly Cash Flow chart.")

    with col2:
        st.subheader("Monthly Income & Expenses Summary")
        if not income_expense_summary_data.empty:
            base_x_encoding_summary = alt.X('YearMonth:O', title='Month', axis=alt.Axis(labelAngle=-45), sort=None)
            
            # Bars for Income and Expenses
            bars = alt.Chart(income_expense_summary_data).mark_bar().encode(
                x=base_x_encoding_summary,
                y=alt.Y('Amount:Q', title='Amount (R$)'),
                color=alt.Color('Type:N', scale=alt.Scale(domain=['Income', 'Expenses'], range=[color_income, color_expenses])),
                tooltip=['YearMonth', 'Type', alt.Tooltip('Amount:Q', format='.2f')]
            )

            # Line for Income Moving Average
            income_ma_line = alt.Chart(income_ma_df).mark_line(color=color_income_ma, point=True, strokeDash=[3,3]).encode(
                x=base_x_encoding_summary,
                y=alt.Y('MovingAverage:Q', title='3-Month MA'),
                tooltip=['YearMonth', alt.Tooltip('MovingAverage:Q', format='.2f', title='Income MA (3-Month)')]
            )

            # Line for Expenses Moving Average
            expenses_ma_line = alt.Chart(expenses_ma_df).mark_line(color=color_expenses_ma, point=True, strokeDash=[3,3]).encode(
                x=base_x_encoding_summary,
                y=alt.Y('MovingAverage:Q'),
                tooltip=['YearMonth', alt.Tooltip('MovingAverage:Q', format='.2f', title='Expense MA (3-Month)')]
            )
            
            income_expense_summary_chart = alt.layer(bars, income_ma_line, expenses_ma_line).resolve_scale(
                y='shared'
            ).properties(title='Income and Expenses per Month (with 3-Month MA)')
            
            st.altair_chart(income_expense_summary_chart, use_container_width=True)
        else:
            st.write("No data for Monthly Income & Expenses Summary chart.")

    st.markdown("---")

    # --- Expenses by Main Category Chart (Moved Here) ---
    def prepare_main_category_expense_data(df_input):
        if df_input.empty:
            return pd.DataFrame()

        categories_to_exclude = ['Ignorar', 'Investimentos', 'Extraordinários'] 
        df_analysis = df_input[~df_input[COLUMN_MAIN_CATEGORY].isin(categories_to_exclude)].copy()
        
        if df_analysis.empty:
            return pd.DataFrame()

        df_analysis[COLUMN_DATE] = pd.to_datetime(df_analysis[COLUMN_DATE])
        df_analysis['YearMonth'] = df_analysis[COLUMN_DATE].dt.strftime('%Y-%m')

        # Group by YearMonth and Main Category, summing amounts (preserving signs initially)
        main_cat_expenses_df = df_analysis.groupby(['YearMonth', COLUMN_MAIN_CATEGORY], as_index=False)\
                                     .agg(Amount=(COLUMN_AMOUNT, 'sum'))
        
        # Filter for categories that are net expenses (sum < 0)
        main_cat_expenses_df = main_cat_expenses_df[main_cat_expenses_df['Amount'] < 0]

        # Now, take the absolute value for display
        if not main_cat_expenses_df.empty:
            main_cat_expenses_df['Amount'] = main_cat_expenses_df['Amount'].abs()
        
        # This filter uses the corrected column name 'Amount'
        main_cat_expenses_df = main_cat_expenses_df[main_cat_expenses_df['Amount'] != 0] 
        main_cat_expenses_df = main_cat_expenses_df.sort_values(by=['YearMonth', COLUMN_MAIN_CATEGORY])
        return main_cat_expenses_df

    main_category_expenses_data = prepare_main_category_expense_data(raw_transactions_df.copy())

    st.subheader("Expenses by Main Category")
    if not main_category_expenses_data.empty:
        base_x_exp_main = alt.X('YearMonth:O', title='Month', axis=alt.Axis(labelAngle=-45), sort=None)
        legend_selection_main_exp = alt.selection_point(fields=[COLUMN_MAIN_CATEGORY], bind='legend', name="main_exp_legend")

        main_exp_bars = alt.Chart(main_category_expenses_data).mark_bar().encode(
            x=base_x_exp_main,
            y=alt.Y('Amount:Q', title='Total Expenses (R$)'),
            color=alt.Color(f'{COLUMN_MAIN_CATEGORY}:N', legend=alt.Legend(title="Main Category")),
            tooltip=['YearMonth', alt.Tooltip(f'{COLUMN_MAIN_CATEGORY}:N', title='Main Category'), alt.Tooltip('Amount:Q', format='.2f')]
        ).add_params(
            legend_selection_main_exp
        ).transform_filter(
            legend_selection_main_exp
        ).properties(
            title='Monthly Expenses by Main Category'
        )
        st.altair_chart(main_exp_bars, use_container_width=True)
    else:
        st.write("No expense data to display by main category.")
            
    st.markdown("--- ") # Separator before Transaction Editor section
    st.header("Transaction Editor")
    st.info(f"Loaded {len(raw_transactions_df)} total transactions for editing below.")

    # --- Filtering Dropdowns --- 
    all_available_main_categories = sorted(list(raw_transactions_df[COLUMN_MAIN_CATEGORY].unique()))
    filter_options_main = ["All Categories"] + all_available_main_categories
    
    selected_filter_category = st.selectbox(
        "Filter by Main Category:",
        options=filter_options_main,
        index=0, 
        key='filter_main_category'
    )

    # --- Dynamic Subcategory Filter --- 
    def get_subcategory_options(df, main_category_selection):
        if df.empty:
            return ["All Subcategories"]
        
        categories_to_exclude_for_subfilter = ['Ignorar', 'Investimentos', 'Extraordinários']
        # Filter out excluded main categories first, unless we are looking at a specific main category already
        if main_category_selection == "All Categories":
            relevant_df_for_sub = df[~df[COLUMN_MAIN_CATEGORY].isin(categories_to_exclude_for_subfilter)]
        else:
            # If a specific main category is selected, we only care about its subcategories
            relevant_df_for_sub = df[df[COLUMN_MAIN_CATEGORY] == main_category_selection]

        if relevant_df_for_sub.empty:
            return ["All Subcategories"]
            
        unique_subcategories = sorted(list(relevant_df_for_sub[COLUMN_SUB_CATEGORY].unique()))
        return ["All Subcategories"] + unique_subcategories

    filter_options_sub = get_subcategory_options(raw_transactions_df, selected_filter_category)
    
    selected_sub_category = st.selectbox(
        "Filter by Subcategory:",
        options=filter_options_sub,
        index=0, # Default to "All Subcategories"
        key='filter_sub_category'
    )

    # --- Expenses by Subcategory Chart (uses both filters) ---
    def prepare_subcategory_expense_data(df_input, main_cat_filter, sub_cat_filter):
        if df_input.empty:
            return pd.DataFrame(), pd.DataFrame() # bars_df, total_ma_df

        categories_to_exclude = ['Ignorar', 'Investimentos', 'Extraordinários'] 
        df_analysis = df_input[~df_input[COLUMN_MAIN_CATEGORY].isin(categories_to_exclude)].copy()
        df_analysis = df_analysis[df_analysis[COLUMN_AMOUNT] < 0].copy()

        if df_analysis.empty:
            return pd.DataFrame(), pd.DataFrame()
            
        df_analysis[COLUMN_AMOUNT] = df_analysis[COLUMN_AMOUNT].abs()
        df_analysis[COLUMN_DATE] = pd.to_datetime(df_analysis[COLUMN_DATE])
        df_analysis['YearMonth'] = df_analysis[COLUMN_DATE].dt.strftime('%Y-%m')

        # Data source for subcategory bars (filtered by main and then sub category)
        df_for_bars = df_analysis.copy()
        if main_cat_filter != "All Categories":
            df_for_bars = df_for_bars[df_for_bars[COLUMN_MAIN_CATEGORY] == main_cat_filter]
        if sub_cat_filter != "All Subcategories":
            df_for_bars = df_for_bars[df_for_bars[COLUMN_SUB_CATEGORY] == sub_cat_filter]
        
        subcategory_bars_df = pd.DataFrame() # Initialize
        if not df_for_bars.empty:
            subcategory_bars_df = df_for_bars.groupby(['YearMonth', COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY], as_index=False)\
                                         .agg(Amount=(COLUMN_AMOUNT, 'sum'))
            subcategory_bars_df = subcategory_bars_df[subcategory_bars_df['Amount'] != 0]
            subcategory_bars_df = subcategory_bars_df.sort_values(by=['YearMonth', COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY])

        # Data source for Total MA line (depends only on main category filter)
        df_for_total_ma = df_analysis.copy() # Start from expenses, pre-main-category-exclusion
        if main_cat_filter != "All Categories":
            df_for_total_ma = df_for_total_ma[df_for_total_ma[COLUMN_MAIN_CATEGORY] == main_cat_filter]
        
        selected_category_total_ma_df = pd.DataFrame()
        if not df_for_total_ma.empty:
            total_expenses_selected_cat = df_for_total_ma.groupby('YearMonth')\
                                               .agg(TotalAmount=(COLUMN_AMOUNT, 'sum'))
            
            min_date_proc = pd.to_datetime(df_for_total_ma['YearMonth']).min()
            max_date_proc = pd.to_datetime(df_for_total_ma['YearMonth']).max()
            all_months_idx_proc = pd.date_range(start=min_date_proc, end=max_date_proc, freq='MS').strftime('%Y-%m')
            base_month_df_proc = pd.DataFrame(index=all_months_idx_proc)

            merged_total_df = base_month_df_proc.join(total_expenses_selected_cat, how='left').fillna({'TotalAmount': 0}).reset_index()
            merged_total_df.rename(columns={'index': 'YearMonth'}, inplace=True)
            merged_total_df = merged_total_df.sort_values(by='YearMonth')
            merged_total_df['MA_Amount'] = merged_total_df['TotalAmount'].rolling(window=3, min_periods=1).mean()
            selected_category_total_ma_df = merged_total_df[['YearMonth', 'MA_Amount']]
        
        return subcategory_bars_df, selected_category_total_ma_df

    # Pass both filters to the data preparation function
    subcategory_bars_data, selected_category_total_ma_data = prepare_subcategory_expense_data(
        raw_transactions_df.copy(), 
        selected_filter_category, 
        selected_sub_category
    )

    # Update chart title to reflect both filters
    chart_title_subcategory = f"Expenses: Main Cat: {selected_filter_category} / Sub Cat: {selected_sub_category}"
    st.subheader(chart_title_subcategory)

    if not subcategory_bars_data.empty:
        base_x_exp_sub = alt.X('YearMonth:O', title='Month', axis=alt.Axis(labelAngle=-45), sort=None)
        # If a specific subcategory is selected, legend interaction for subcategories is less meaningful for filtering bars
        # but can still be used for highlighting if desired. Or, we can conditionally disable it.
        # For now, keep it for consistency.
        legend_selection_sub_exp = alt.selection_point(fields=[COLUMN_SUB_CATEGORY], bind='legend', name="sub_exp_legend") 

        sub_exp_bars = alt.Chart(subcategory_bars_data).mark_bar().encode(
            x=base_x_exp_sub,
            y=alt.Y('Amount:Q', title='Total Expenses (R$)'),
            color=alt.Color(f'{COLUMN_SUB_CATEGORY}:N', legend=alt.Legend(title="Subcategory")),
            tooltip=['YearMonth', 
                       alt.Tooltip(f'{COLUMN_MAIN_CATEGORY}:N', title='Main Category'), 
                       alt.Tooltip(f'{COLUMN_SUB_CATEGORY}:N', title='Subcategory'), 
                       alt.Tooltip('Amount:Q', format='.2f', title='Expenses')]
        )

        # MA line for the total of the selected category
        selected_cat_total_ma_line = alt.Chart(selected_category_total_ma_data).mark_line(
            color='darkslategray', 
            point=True, 
            strokeDash=[3,3]
        ).encode(
            x=base_x_exp_sub, # Use the same x-axis
            y=alt.Y('MA_Amount:Q', title='3-Mo MA (Selected Cat. Total)'),
            tooltip=['YearMonth', 
                       alt.Tooltip('MA_Amount:Q', format='.2f', title='Total MA (Selected Cat.)')]
        )

        combined_chart = alt.layer(sub_exp_bars, selected_cat_total_ma_line).resolve_scale(
            y='shared' 
        ).add_params(
            legend_selection_sub_exp # Legend still applies to sub_exp_bars
        ).transform_filter(
            legend_selection_sub_exp # Filter still applies to sub_exp_bars
        ).properties(
            title='Monthly Expenses by Subcategory (with MA of Selected Category Total)' # Main title remains descriptive of layers
        )
        st.altair_chart(combined_chart, use_container_width=True)
    elif selected_filter_category != "All Categories" or selected_sub_category != "All Subcategories":
        st.write(f"No subcategory expense data to display for Main: '{selected_filter_category}' / Sub: '{selected_sub_category}'.")
    else:
        st.write("No expense data to display by subcategory.")
    
    # Determine transactions to display based on filter (this logic was already here)
    # THIS SECTION NEEDS TO BE UPDATED FOR SUB-CATEGORY FILTER
    if selected_filter_category == "All Categories":
        if selected_sub_category == "All Subcategories":
            filtered_transactions_df = raw_transactions_df.copy()
        else: # Specific sub-category, all main categories
            filtered_transactions_df = raw_transactions_df[raw_transactions_df[COLUMN_SUB_CATEGORY] == selected_sub_category].copy()
    else: # Specific main category selected
        if selected_sub_category == "All Subcategories":
            filtered_transactions_df = raw_transactions_df[raw_transactions_df[COLUMN_MAIN_CATEGORY] == selected_filter_category].copy()
        else: # Specific main and specific sub-category
            filtered_transactions_df = raw_transactions_df[
                (raw_transactions_df[COLUMN_MAIN_CATEGORY] == selected_filter_category) & 
                (raw_transactions_df[COLUMN_SUB_CATEGORY] == selected_sub_category)
            ].copy()

    # Update the display message
    if not filtered_transactions_df.empty:
        st.write(f"Displaying {len(filtered_transactions_df)} transactions for Main: '{selected_filter_category}' / Sub: '{selected_sub_category}'.")
    # ... other messages for empty df already handled below this block ...
    
    # display_transactions will always be True if raw_transactions_df is not empty, 
    # as this whole block is under `if not raw_transactions_df.empty:`
    display_transactions = True 


    # --- Session state for editable transactions --- 
    # Re-initialize session state if filter changes or if it's not initialized,
    # or if 'transactions_to_edit' is not in session_state (e.g., first load)
    force_reload_editor_state = False
    if ('last_filter' not in st.session_state or 
        st.session_state.last_filter != selected_filter_category or \
        'last_sub_filter' not in st.session_state or \
        st.session_state.last_sub_filter != selected_sub_category or \
        'transactions_to_edit' not in st.session_state):
        force_reload_editor_state = True
    elif (not st.session_state.transactions_to_edit and not filtered_transactions_df.empty):
        force_reload_editor_state = True
    elif (st.session_state.transactions_to_edit and 
          len(st.session_state.transactions_to_edit) != len(filtered_transactions_df) and \
          # Only consider this length mismatch a reason to reload if the filters *haven't* just changed
          # because if filters changed, a length mismatch is expected and handled by the first conditions.
          selected_filter_category == st.session_state.get('last_filter') and 
          selected_sub_category == st.session_state.get('last_sub_filter')):
        force_reload_editor_state = True

    if force_reload_editor_state:
        if not filtered_transactions_df.empty:
            temp_df = filtered_transactions_df[[COLUMN_ID, COLUMN_DATE, COLUMN_MEMO, COLUMN_AMOUNT, COLUMN_TYPE, COLUMN_ACCOUNT_TYPE, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]].copy()
            temp_df[COLUMN_COMBINED_CATEGORY_DISPLAY] = temp_df[COLUMN_MAIN_CATEGORY].astype(str) + " / " + temp_df[COLUMN_SUB_CATEGORY].astype(str)

            # Adjust amount sign based on type for display
            def adjust_amount_sign(row):
                amount = row[COLUMN_AMOUNT]
                # Ensure row[COLUMN_TYPE] is a string before calling .upper()
                trans_type = str(row[COLUMN_TYPE]).upper() if pd.notna(row[COLUMN_TYPE]) else ""
                
                if trans_type == 'DEBIT':
                    return -abs(amount)
                elif trans_type == 'CREDIT':
                    return abs(amount)
                return amount # Return original amount (which should usually be signed) for other/unknown types

            if COLUMN_AMOUNT in temp_df.columns and COLUMN_TYPE in temp_df.columns:
                 temp_df[COLUMN_AMOUNT] = temp_df.apply(adjust_amount_sign, axis=1)
            
            st.session_state.transactions_to_edit = temp_df.to_dict(orient='records')
        else:
            st.session_state.transactions_to_edit = []
        st.session_state.last_filter = selected_filter_category
        st.session_state.last_sub_filter = selected_sub_category # Store sub-category filter state

    # --- Displaying transactions using st.data_editor --- 
    if display_transactions:
        if st.session_state.transactions_to_edit: # Check if there are transactions to show
            # Create DataFrame for the editor from the list of dicts in session state
            editor_df = pd.DataFrame(st.session_state.transactions_to_edit)

            # --- Define column order and display names ---
            # Original column names from the DataFrame that will be displayed
            ordered_columns_for_display = [
                COLUMN_DATE, 
                COLUMN_MEMO, 
                COLUMN_AMOUNT, 
                COLUMN_COMBINED_CATEGORY_DISPLAY,
                COLUMN_ACCOUNT_TYPE,
                COLUMN_TYPE
            ]
            # Select and reorder columns for the editor_df
            if not editor_df.empty:
                 # Ensure all columns in ordered_columns_for_display exist in editor_df before reordering
                existing_cols_for_display = [col for col in ordered_columns_for_display if col in editor_df.columns]
                editor_df_display = editor_df[existing_cols_for_display + [COLUMN_ID, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]]
            else:
                editor_df_display = editor_df # Keep it empty if it is

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
                COLUMN_MAIN_CATEGORY: None, # Hide original main category
                COLUMN_SUB_CATEGORY: None,  # Hide original sub category
                COLUMN_DATE: st.column_config.DateColumn("Data", disabled=True, format="YYYY-MM-DD"), # Renamed
                COLUMN_MEMO: st.column_config.TextColumn("Descrição", disabled=True),
                COLUMN_AMOUNT: st.column_config.NumberColumn("Valor", format="%.2f", disabled=True),
                COLUMN_COMBINED_CATEGORY_DISPLAY: st.column_config.SelectboxColumn(
                    COLUMN_COMBINED_CATEGORY_DISPLAY,
                    options=sorted_combined_categories,
                    required=False,
                    width="large"
                ),
                COLUMN_ACCOUNT_TYPE: st.column_config.TextColumn("Conta", disabled=True), # Renamed
                COLUMN_TYPE: st.column_config.TextColumn("Tipo", disabled=True) # Renamed
            }
            
            # st.data_editor returns the edited DataFrame.
            # It uses st.session_state[key]["edited_rows"] to track edits.
            edited_df_from_editor = st.data_editor(
                editor_df_display, # Use the reordered DataFrame
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
                            
                            # Retrieve transaction ID and original categories from the original editor_df
                            # (DataFrame initially passed to st.data_editor, which is editor_df, not editor_df_display)
                            # The row_idx from edited_rows refers to the index in the DataFrame *passed to st.data_editor*.
                            # If editor_df_display was a filtered view (row-wise), this would be fine.
                            # Since it's column-reordered but has same rows and indices as editor_df, using editor_df here is also fine.
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