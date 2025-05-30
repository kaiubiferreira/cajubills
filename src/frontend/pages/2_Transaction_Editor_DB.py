import streamlit as st
import pandas as pd
import os
import sys
import altair as alt
import numpy as np
from datetime import date
from dateutil.relativedelta import relativedelta
import plotly.express as px

# Add the src directory to the path to import from backend modules
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, '..', '..')
sys.path.append(src_dir)

from sql.connection import run_query

# Define column names for consistency with the original app
COLUMN_ID = 'id'
COLUMN_MEMO = 'memo'
COLUMN_MAIN_CATEGORY = 'main_category'
COLUMN_SUB_CATEGORY = 'sub_category'
COLUMN_DATE = 'date'
COLUMN_AMOUNT = 'amount'
COLUMN_TYPE = 'type'
COLUMN_ACCOUNT_TYPE = 'account_type'
COLUMN_COMBINED_CATEGORY_DISPLAY = "Categoria / Sub categoria"

# Fix the path construction to correctly point to resources directory
# current_dir is pages/, we need to go up 3 levels to get to project root
# pages -> frontend -> src -> project_root
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
USER_CATEGORIES_FILE = os.path.join(project_root, 'resources', 'user_defined_categories.csv')
USER_BUDGET_FILE = os.path.join(project_root, 'resources', 'user_defined_budget.csv')

def load_user_categories():
    if os.path.exists(USER_CATEGORIES_FILE):
        try:
            return pd.read_csv(USER_CATEGORIES_FILE)
        except pd.errors.EmptyDataError:
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

def load_user_budget():
    budget_dict = {}
    if os.path.exists(USER_BUDGET_FILE):
        try:
            budget_df = pd.read_csv(USER_BUDGET_FILE)
            if not budget_df.empty:
                for _, row in budget_df.iterrows():
                    budget_dict[(row['MainCategory'], row['SubCategory'])] = float(row['BudgetAmount'])
        except pd.errors.EmptyDataError:
            st.info("Arquivo de orçamento encontrado, mas está vazio.")
        except Exception as e:
            st.error(f"Erro ao carregar o arquivo de orçamento: {e}")
    return budget_dict

def save_user_budget(budget_dict):
    if not budget_dict:
        df_to_save = pd.DataFrame(columns=['MainCategory', 'SubCategory', 'BudgetAmount'])
    else:
        records = []
        for (main_cat, sub_cat), budget_amount in budget_dict.items():
            records.append({
                'MainCategory': main_cat,
                'SubCategory': sub_cat,
                'BudgetAmount': budget_amount
            })
        df_to_save = pd.DataFrame(records)
    
    try:
        df_to_save.to_csv(USER_BUDGET_FILE, index=False)
        st.toast("Orçamento salvo com sucesso!", icon="✅")
    except Exception as e:
        st.error(f"Erro ao salvar o arquivo de orçamento: {e}")
        st.toast("Falha ao salvar o orçamento.", icon="❌")

@st.cache_data
def load_all_transactions_data_from_db(filter_start_date: date):
    """
    Load transactions from the local database and merge with user-defined categories from CSV.
    """
    try:
        # Load transactions from database
        query = """
        SELECT id, date, type, amount, memo, account_type, main_category, sub_category
        FROM ofx_transactions
        ORDER BY date DESC
        """
        
        transactions_df = run_query(query, target_db="local")
        
        if transactions_df.empty:
            st.warning("Nenhuma transação encontrada no banco de dados.")
            return pd.DataFrame()
        
        # Convert date column to datetime and then to date objects
        if COLUMN_DATE in transactions_df.columns:
            try:
                transactions_df[COLUMN_DATE] = pd.to_datetime(transactions_df[COLUMN_DATE]).dt.date
            except Exception as e:
                st.warning(f"Não foi possível formatar a coluna de data: {e}")
        
        # Ensure amount is numeric
        if COLUMN_AMOUNT in transactions_df.columns:
            transactions_df[COLUMN_AMOUNT] = pd.to_numeric(transactions_df[COLUMN_AMOUNT], errors='coerce').fillna(0.0)
        
        # Load user-defined categories from CSV and override database categories
        user_categories_df = load_user_categories()
        if not user_categories_df.empty:
            # Create a mapping of transaction_id to user-defined categories
            user_categories_map = {}
            for _, row in user_categories_df.iterrows():
                user_categories_map[row[COLUMN_ID]] = (row[COLUMN_MAIN_CATEGORY], row[COLUMN_SUB_CATEGORY])
            
            # Override categories for transactions that have user-defined categories
            for index, row in transactions_df.iterrows():
                transaction_id = row[COLUMN_ID]
                if transaction_id in user_categories_map:
                    main_cat, sub_cat = user_categories_map[transaction_id]
                    transactions_df.loc[index, COLUMN_MAIN_CATEGORY] = main_cat
                    transactions_df.loc[index, COLUMN_SUB_CATEGORY] = sub_cat
        
        # Apply date filter
        if COLUMN_DATE in transactions_df.columns:
            end_date_filter = date.today()
            transactions_df = transactions_df[
                (transactions_df[COLUMN_DATE] >= filter_start_date) & 
                (transactions_df[COLUMN_DATE] <= end_date_filter)
            ]
        
        return transactions_df
        
    except Exception as e:
        st.error(f"Erro ao carregar transações do banco de dados: {e}")
        return pd.DataFrame()

st.set_page_config(layout="wide")
st.title("Editor de Categorias de Transações (Fonte: Banco de Dados)")

# Global Date Filter
default_start_date = date.today() - relativedelta(months=9)

selected_start_date = st.date_input(
    "Selecione a Data de Início para Análise:",
    value=default_start_date,
    min_value=date(2000, 1, 1),
    max_value=date.today(),
    key='global_start_date_db'
)

st.markdown("---")

# Load data from database
raw_transactions_df = load_all_transactions_data_from_db(filter_start_date=selected_start_date)

if not raw_transactions_df.empty:
    
    def prepare_cash_flow_data(df_input):
        if df_input.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame() 

        categories_to_exclude = ['Ignorar', 'Investimentos', 'Extraordinários']
        df_chart = df_input[~df_input[COLUMN_MAIN_CATEGORY].isin(categories_to_exclude)].copy()
        
        if df_chart.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        df_chart[COLUMN_DATE] = pd.to_datetime(df_chart[COLUMN_DATE])
        df_chart['YearMonth'] = df_chart[COLUMN_DATE].dt.strftime('%Y-%m')
        df_chart = df_chart.sort_values(by='YearMonth')

        # Data for Net line (Overall Net Cash Flow) & its MA
        monthly_net_data_raw = df_chart.groupby('YearMonth') \
                                   .agg(Amount=(COLUMN_AMOUNT, 'sum'))
        
        # Ensure complete month index for net flow and its MA
        if not df_chart.empty:
            all_months_idx_net = pd.date_range(start=df_chart[COLUMN_DATE].min(), end=df_chart[COLUMN_DATE].max(), freq='MS').strftime('%Y-%m')
            base_month_df_net = pd.DataFrame(index=all_months_idx_net)
        else:
            base_month_df_net = pd.DataFrame()

        monthly_net_data = base_month_df_net.join(monthly_net_data_raw, how='left').fillna(0).reset_index().rename(columns={'index': 'YearMonth'})
        monthly_net_data = monthly_net_data.sort_values(by='YearMonth')
        
        # Convert YearMonth string to datetime for proper chart rendering
        monthly_net_data['YearMonthDate'] = pd.to_datetime(monthly_net_data['YearMonth'] + '-01')
        
        if not monthly_net_data.empty:
            monthly_net_data['Net_MA'] = monthly_net_data['Amount'].rolling(window=3, min_periods=1).mean()
        
        net_flow_ma_df = monthly_net_data[['YearMonthDate', 'Net_MA']].copy().rename(columns={'Net_MA':'MovingAverage'})
        if not net_flow_ma_df.empty: 
            net_flow_ma_df['MAType'] = 'Net Flow MA'

        # Data for Income/Expense Summary & Moving Averages
        base_month_df_income_expense = base_month_df_net 

        income_monthly_raw = df_chart[
            (df_chart[COLUMN_AMOUNT] > 0) & (df_chart[COLUMN_MAIN_CATEGORY] == 'Renda')
        ].groupby('YearMonth').agg(Amount=(COLUMN_AMOUNT, 'sum'))
        income_monthly = base_month_df_income_expense.join(income_monthly_raw, how='left').fillna(0).reset_index().rename(columns={'index': 'YearMonth'})
        if not income_monthly.empty: 
            income_monthly['Type'] = 'Income'
            income_monthly['YearMonthDate'] = pd.to_datetime(income_monthly['YearMonth'] + '-01')
            income_monthly['Income_MA'] = income_monthly['Amount'].rolling(window=3, min_periods=1).mean()
        
        expenses_monthly_raw = df_chart[df_chart[COLUMN_AMOUNT] < 0].groupby('YearMonth')\
            .agg(Amount=(COLUMN_AMOUNT, 'sum'))
        expenses_monthly = base_month_df_income_expense.join(expenses_monthly_raw, how='left').fillna(0).reset_index().rename(columns={'index': 'YearMonth'})
        if not expenses_monthly.empty: 
            expenses_monthly['Type'] = 'Expenses'
            expenses_monthly['YearMonthDate'] = pd.to_datetime(expenses_monthly['YearMonth'] + '-01')
            expenses_monthly['Expenses_MA'] = expenses_monthly['Amount'].rolling(window=3, min_periods=1).mean()
        
        monthly_income_expense_summary = pd.concat([income_monthly, expenses_monthly[expenses_monthly['Type'] == 'Expenses'] ], ignore_index=True)\
            .sort_values(by=['YearMonth', 'Type'])

        income_ma_df = income_monthly[['YearMonthDate', 'Income_MA']].copy().rename(columns={'Income_MA':'MovingAverage'})
        if not income_ma_df.empty: 
            income_ma_df['MAType'] = 'Income MA'

        expenses_ma_df = expenses_monthly[['YearMonthDate', 'Expenses_MA']].copy().rename(columns={'Expenses_MA':'MovingAverage'})
        if not expenses_ma_df.empty: 
            expenses_ma_df['MAType'] = 'Expenses MA'

        # Expense/Income Ratio calculation
        expense_income_ratio_df = pd.DataFrame()
        if not income_monthly.empty and not expenses_monthly.empty:
            ratio_df = income_monthly[['YearMonth', 'Amount']].merge(
                expenses_monthly[['YearMonth', 'Amount']], 
                on='YearMonth', 
                suffixes=('_income', '_expenses')
            )
            ratio_df['Ratio'] = ratio_df.apply(
                lambda row: abs(row['Amount_expenses']) / row['Amount_income'] 
                if row['Amount_income'] > 0 else 0, axis=1
            )
            ratio_df['YearMonthDate'] = pd.to_datetime(ratio_df['YearMonth'] + '-01')
            expense_income_ratio_df = ratio_df[['YearMonthDate', 'Ratio']].copy()

        return monthly_net_data, monthly_income_expense_summary, income_ma_df, expenses_ma_df, net_flow_ma_df, expense_income_ratio_df

    # Cash Flow Charts - Split into two side-by-side charts
    st.subheader("Visão Geral do Fluxo de Caixa")
    
    net_flow_data, income_expense_data, income_ma_data, expenses_ma_data, net_flow_ma_data, expense_income_ratio_data = prepare_cash_flow_data(raw_transactions_df.copy())

    # Define colors for consistency
    color_income = '#4CAF50'      # Green
    color_expenses = '#F44336'    # Red  
    color_income_ma = '#2E7D32'   # Dark Green
    color_expenses_ma = '#C62828' # Dark Red
    color_net_flow_ma = '#FF9800' # Orange
    color_ratio_line = '#9C27B0'  # Purple

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Quanto sobrou?")
        if not net_flow_data.empty:
            base_x_encoding_net = alt.X('YearMonthDate:T', title='Mês')
            
            net_flow_bars = alt.Chart(net_flow_data).mark_bar(width={"band": 0.8}).encode(
                x=base_x_encoding_net,
                y=alt.Y('Amount:Q', title='Fluxo de Caixa Líquido (R$)'),
                color=alt.condition(alt.datum.Amount > 0, alt.value(color_income), alt.value(color_expenses)),
                tooltip=['YearMonthDate:T', alt.Tooltip('Amount:Q', format='.2f', title='Fluxo Líquido')]
            )

            net_ma_line = alt.Chart(net_flow_ma_data).mark_line(color=color_net_flow_ma, point=True, strokeDash=[3,3]).encode(
                x=alt.X('YearMonthDate:T'),
                y=alt.Y('MovingAverage:Q', title='Média Móvel 3 Meses - Fluxo Líquido'),
                tooltip=['YearMonthDate:T', alt.Tooltip('MovingAverage:Q', format='.2f', title='Média Móvel Fluxo Líquido (3 Meses)')]
            )
            
            net_flow_chart_final = alt.layer(net_flow_bars, net_ma_line).resolve_scale(
                y='shared'
            ).properties(title='Fluxo de Caixa Líquido Mensal (com Média Móvel 3 Meses)')
            st.altair_chart(net_flow_chart_final, use_container_width=True)
        else:
            st.write("Sem dados para o gráfico de Fluxo de Caixa Líquido Mensal.")

    with col2:
        st.subheader("Fluxo de Caixa")
        if not income_expense_data.empty:
            base_x_encoding_summary = alt.X('YearMonthDate:T', title='Mês')
            
            # Bars for Income and Expenses
            bars = alt.Chart(income_expense_data).mark_bar(opacity=0.7, width={"band": 0.8}).encode(
                x=base_x_encoding_summary,
                y=alt.Y('Amount:Q', title='Valor (R$)'),
                color=alt.Color('Type:N', scale=alt.Scale(domain=['Income', 'Expenses'], range=[color_income, color_expenses])),
                tooltip=['YearMonthDate:T', 'Type:N', alt.Tooltip('Amount:Q', format='.2f')]
            )

            # Line for Income Moving Average
            income_ma_line = alt.Chart(income_ma_data).mark_line(color=color_income_ma, point=True, strokeDash=[3,3]).encode(
                x=alt.X('YearMonthDate:T'),
                y=alt.Y('MovingAverage:Q', title='Média Móvel 3 Meses'),
                tooltip=['YearMonthDate:T', alt.Tooltip('MovingAverage:Q', format='.2f', title='Média Móvel Renda (3 Meses)')]
            )

            # Line for Expenses Moving Average
            expenses_ma_line = alt.Chart(expenses_ma_data).mark_line(color=color_expenses_ma, point=True, strokeDash=[3,3]).encode(
                x=alt.X('YearMonthDate:T'),
                y=alt.Y('MovingAverage:Q'),
                tooltip=['YearMonthDate:T', alt.Tooltip('MovingAverage:Q', format='.2f', title='Média Móvel Despesas (3 Meses)')]
            )
            
            # Ratio Line
            ratio_line_chart = alt.Chart(expense_income_ratio_data).mark_line(
                color=color_ratio_line, 
                point=True, 
                strokeDash=[2,2], 
                interpolate='monotone'
            ).encode(
                x=alt.X('YearMonthDate:T', axis=alt.Axis(title=None, labels=False, ticks=False)),
                y=alt.Y('Ratio:Q', axis=alt.Axis(title='Proporção Despesas/Renda (%)', format='~s')), 
                tooltip=['YearMonthDate:T', alt.Tooltip('Ratio:Q', title='Proporção Despesas/Renda')]
            )

            # Layer the charts
            base_chart_with_ma = alt.layer(bars, income_ma_line, expenses_ma_line).resolve_scale(y='shared')
            
            income_expense_summary_chart_final = alt.layer(
                base_chart_with_ma, 
                ratio_line_chart
            ).resolve_scale(
                y='independent'
            ).properties(title='Renda e Despesas por Mês (com MM 3 Meses e Proporção)')
            
            st.altair_chart(income_expense_summary_chart_final, use_container_width=True)
        else:
            st.write("Sem dados para o gráfico de Renda e Despesas.")

    # Expenses by Main Category Chart
    def prepare_main_category_expense_data(df_input):
        if df_input.empty:
            return pd.DataFrame()

        categories_to_exclude = ['Ignorar', 'Investimentos', 'Extraordinários'] 
        df_analysis = df_input[~df_input[COLUMN_MAIN_CATEGORY].isin(categories_to_exclude)].copy()
        
        if df_analysis.empty:
            return pd.DataFrame()

        df_analysis[COLUMN_DATE] = pd.to_datetime(df_analysis[COLUMN_DATE])
        df_analysis['YearMonth'] = df_analysis[COLUMN_DATE].dt.strftime('%Y-%m')

        # Group by YearMonth and Main Category, summing amounts
        main_cat_expenses_df = df_analysis.groupby(['YearMonth', COLUMN_MAIN_CATEGORY], as_index=False)\
                                     .agg(Amount=(COLUMN_AMOUNT, 'sum'))
        
        # Filter for categories that are net expenses (sum < 0)
        main_cat_expenses_df = main_cat_expenses_df[main_cat_expenses_df['Amount'] < 0]

        # Take the absolute value for display
        if not main_cat_expenses_df.empty:
            main_cat_expenses_df['Amount'] = main_cat_expenses_df['Amount'].abs()
            # Convert YearMonth string to datetime for proper chart rendering
            main_cat_expenses_df['YearMonthDate'] = pd.to_datetime(main_cat_expenses_df['YearMonth'] + '-01')
        
        main_cat_expenses_df = main_cat_expenses_df[main_cat_expenses_df['Amount'] != 0] 
        main_cat_expenses_df = main_cat_expenses_df.sort_values(by=['YearMonth', COLUMN_MAIN_CATEGORY])
        return main_cat_expenses_df

    main_category_expenses_data = prepare_main_category_expense_data(raw_transactions_df.copy())

    st.subheader("No que foi gasto?")
    
    if not main_category_expenses_data.empty:
        main_category_chart = alt.Chart(main_category_expenses_data).mark_bar(width={"band": 0.8}).encode(
            x=alt.X('YearMonthDate:T', timeUnit='yearmonth', title='Mês'),
            y=alt.Y('Amount:Q', title='Valor (R$)'),
            color=alt.Color(f'{COLUMN_MAIN_CATEGORY}:N', 
                          legend=alt.Legend(title="Categoria Principal", columns=2)),
            tooltip=['YearMonthDate:T', f'{COLUMN_MAIN_CATEGORY}:N', alt.Tooltip('Amount:Q', format='.2f')]
        ).add_selection(
            alt.selection_interval(bind='scales')
        ).properties(
            width=800,
            height=400,
            title="Despesas Mensais por Categoria Principal"
        )
        st.altair_chart(main_category_chart, use_container_width=True)

    # Category Filter and Subcategory Analysis
    def get_subcategory_options(df, main_category_selection):
        if df.empty:
            return ["Todas as Subcategorias"]
        
        options = ["Todas as Subcategorias"]
        if main_category_selection != "Todas as Categorias":
            filtered_df = df[df[COLUMN_MAIN_CATEGORY] == main_category_selection]
            if not filtered_df.empty:
                unique_subcategories = sorted(filtered_df[COLUMN_SUB_CATEGORY].unique())
                options.extend(unique_subcategories)
        return options

    def prepare_subcategory_expense_data(df_input, main_cat_filter, sub_cat_filter):
        if df_input.empty:
            return pd.DataFrame(), pd.DataFrame()

        categories_to_exclude = ['Ignorar', 'Investimentos', 'Extraordinários'] 
        df_analysis = df_input[~df_input[COLUMN_MAIN_CATEGORY].isin(categories_to_exclude)].copy()
        df_analysis = df_analysis[df_analysis[COLUMN_AMOUNT] < 0].copy()

        if df_analysis.empty:
            return pd.DataFrame(), pd.DataFrame()
            
        df_analysis[COLUMN_AMOUNT] = df_analysis[COLUMN_AMOUNT].abs()
        df_analysis[COLUMN_DATE] = pd.to_datetime(df_analysis[COLUMN_DATE])
        df_analysis['YearMonth'] = df_analysis[COLUMN_DATE].dt.strftime('%Y-%m')

        # Data for subcategory bars (filtered by main and then sub category)
        df_for_bars = df_analysis.copy()
        if main_cat_filter != "All Categories":
            df_for_bars = df_for_bars[df_for_bars[COLUMN_MAIN_CATEGORY] == main_cat_filter]
        if sub_cat_filter != "All Subcategories":
            df_for_bars = df_for_bars[df_for_bars[COLUMN_SUB_CATEGORY] == sub_cat_filter]
        
        subcategory_bars_df = pd.DataFrame()
        if not df_for_bars.empty:
            subcategory_bars_df = df_for_bars.groupby(['YearMonth', COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY], as_index=False)\
                                         .agg(Amount=(COLUMN_AMOUNT, 'sum'))
            subcategory_bars_df = subcategory_bars_df[subcategory_bars_df['Amount'] != 0]
            subcategory_bars_df = subcategory_bars_df.sort_values(by=['YearMonth', COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY])
            # Convert YearMonth string to datetime for proper chart rendering
            if not subcategory_bars_df.empty:
                subcategory_bars_df['YearMonthDate'] = pd.to_datetime(subcategory_bars_df['YearMonth'] + '-01')

        # Data for Total MA line (depends only on main category filter)
        df_for_total_ma = df_analysis.copy()
        if main_cat_filter != "All Categories":
            df_for_total_ma = df_for_total_ma[df_for_total_ma[COLUMN_MAIN_CATEGORY] == main_cat_filter]

        total_ma_df = pd.DataFrame()
        if not df_for_total_ma.empty:
            monthly_totals = df_for_total_ma.groupby('YearMonth', as_index=False)\
                                           .agg(TotalAmount=(COLUMN_AMOUNT, 'sum'))
            if not monthly_totals.empty:
                monthly_totals = monthly_totals.sort_values(by='YearMonth')
                monthly_totals['TotalMA'] = monthly_totals['TotalAmount'].rolling(window=3, min_periods=1).mean()
                # Convert YearMonth string to datetime for proper chart rendering
                monthly_totals['YearMonthDate'] = pd.to_datetime(monthly_totals['YearMonth'] + '-01')
                total_ma_df = monthly_totals[['YearMonthDate', 'TotalMA']].copy()

        return subcategory_bars_df, total_ma_df

    # Category filters
    st.subheader("Análise por Categoria")
    
    col1, col2 = st.columns(2)
    
    with col1:
        main_categories = ["Todas as Categorias"] + sorted(raw_transactions_df[COLUMN_MAIN_CATEGORY].unique().tolist())
        selected_filter_category = st.selectbox(
            "Filtrar por Categoria Principal:",
            options=main_categories,
            key='main_category_filter_db'
        )
    
    with col2:
        subcategory_options = get_subcategory_options(raw_transactions_df, selected_filter_category)
        selected_sub_category = st.selectbox(
            "Filtrar por Subcategoria:",
            options=subcategory_options,
            key='sub_category_filter_db'
        )

    # Subcategory expense analysis
    subcategory_bars_data, total_ma_data = prepare_subcategory_expense_data(
        raw_transactions_df.copy(), selected_filter_category, selected_sub_category
    )

    if not subcategory_bars_data.empty or not total_ma_data.empty:
        layers = []
        
        if not subcategory_bars_data.empty:
            subcategory_bars_chart = alt.Chart(subcategory_bars_data).mark_bar(opacity=0.8, width={"band": 0.8}).encode(
                x=alt.X('YearMonthDate:T', timeUnit='yearmonth', title='Mês'),
                y=alt.Y('Amount:Q', title='Valor (R$)'),
                color=alt.Color(f'{COLUMN_SUB_CATEGORY}:N', legend=alt.Legend(title="Subcategoria")),
                tooltip=['YearMonthDate:T', f'{COLUMN_MAIN_CATEGORY}:N', f'{COLUMN_SUB_CATEGORY}:N', alt.Tooltip('Amount:Q', format='.2f')]
            )
            layers.append(subcategory_bars_chart)

        if not total_ma_data.empty:
            total_ma_line = alt.Chart(total_ma_data).mark_line(
                color='red', strokeWidth=3, strokeDash=[5, 5]
            ).encode(
                x=alt.X('YearMonthDate:T'),
                y=alt.Y('TotalMA:Q'),
                tooltip=['YearMonthDate:T', alt.Tooltip('TotalMA:Q', format='.2f', title='Média Móvel 3 Meses')]
            )
            layers.append(total_ma_line)

        if layers:
            combined_chart = alt.layer(*layers).add_selection(
                alt.selection_interval(bind='scales')
            ).resolve_scale(
                color='independent'
            ).properties(
                width=800,
                height=400,
                title=f"Análise de Subcategorias: {selected_filter_category}"
            )
            st.altair_chart(combined_chart, use_container_width=True)

    # Transaction Editor Section
    st.subheader("Editor de Transações")
    
    # Initialize session state
    if 'transactions_to_edit' not in st.session_state:
        st.session_state.transactions_to_edit = []
    if 'last_filter' not in st.session_state:
        st.session_state.last_filter = "Todas as Categorias"
    if 'last_sub_filter' not in st.session_state:
        st.session_state.last_sub_filter = "Todas as Subcategorias"

    # Check if filters changed to reload data OR if this is the first load
    force_reload_editor_state = (
        st.session_state.last_filter != selected_filter_category or 
        st.session_state.last_sub_filter != selected_sub_category or
        not st.session_state.transactions_to_edit  # Force reload if no transactions loaded yet
    )

    # Filter transactions for editor
    filtered_transactions_df = raw_transactions_df.copy()
    if selected_filter_category != "Todas as Categorias":
        filtered_transactions_df = filtered_transactions_df[
            filtered_transactions_df[COLUMN_MAIN_CATEGORY] == selected_filter_category
        ]
    if selected_sub_category != "Todas as Subcategorias":
        filtered_transactions_df = filtered_transactions_df[
            filtered_transactions_df[COLUMN_SUB_CATEGORY] == selected_sub_category
        ]

    # Display transactions toggle
    display_transactions = st.checkbox("Mostrar Transações para Edição", value=True, key='display_transactions_db')

    if force_reload_editor_state:
        if not filtered_transactions_df.empty:
            temp_df = filtered_transactions_df[[COLUMN_ID, COLUMN_DATE, COLUMN_MEMO, COLUMN_AMOUNT, COLUMN_TYPE, COLUMN_ACCOUNT_TYPE, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]].copy()
            temp_df[COLUMN_COMBINED_CATEGORY_DISPLAY] = temp_df[COLUMN_MAIN_CATEGORY].astype(str) + " / " + temp_df[COLUMN_SUB_CATEGORY].astype(str)

            # Adjust amount sign based on type for display
            def adjust_amount_sign(row):
                amount = row[COLUMN_AMOUNT]
                trans_type = str(row[COLUMN_TYPE]).upper() if pd.notna(row[COLUMN_TYPE]) else ""
                
                if trans_type == 'DEBIT':
                    return -abs(amount)
                elif trans_type == 'CREDIT':
                    return abs(amount)
                return amount

            if COLUMN_AMOUNT in temp_df.columns and COLUMN_TYPE in temp_df.columns:
                 temp_df[COLUMN_AMOUNT] = temp_df.apply(adjust_amount_sign, axis=1)
            
            st.session_state.transactions_to_edit = temp_df.to_dict(orient='records')
        else:
            st.session_state.transactions_to_edit = []
        st.session_state.last_filter = selected_filter_category
        st.session_state.last_sub_filter = selected_sub_category

    # Display transactions editor
    if display_transactions:
        if st.session_state.transactions_to_edit:
            editor_df = pd.DataFrame(st.session_state.transactions_to_edit)

            # Define column order and display names
            ordered_columns_for_display = [
                COLUMN_DATE, 
                COLUMN_MEMO, 
                COLUMN_AMOUNT, 
                COLUMN_COMBINED_CATEGORY_DISPLAY,
                COLUMN_ACCOUNT_TYPE,
                COLUMN_TYPE
            ]
            
            if not editor_df.empty:
                existing_cols_for_display = [col for col in ordered_columns_for_display if col in editor_df.columns]
                editor_df_display = editor_df[existing_cols_for_display + [COLUMN_ID, COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]]
            else:
                editor_df_display = editor_df

            # Prepare category options for dropdown
            all_combined_categories_for_dropdown = set()
            if not raw_transactions_df.empty:
                for _, row in raw_transactions_df.iterrows():
                    main_cat = str(row[COLUMN_MAIN_CATEGORY])
                    sub_cat = str(row[COLUMN_SUB_CATEGORY])
                    all_combined_categories_for_dropdown.add(f"{main_cat} / {sub_cat}")
            
            default_combined_category = "Não Categorizado / Não Categorizado"
            if default_combined_category not in all_combined_categories_for_dropdown:
                all_combined_categories_for_dropdown.add(default_combined_category)
            
            sorted_combined_categories = sorted(list(all_combined_categories_for_dropdown))

            st.markdown("### Editar Transações na Tabela")
            editor_key = "transaction_data_editor_db"
            
            column_config = {
                COLUMN_ID: None,
                COLUMN_MAIN_CATEGORY: None,
                COLUMN_SUB_CATEGORY: None,
                COLUMN_DATE: st.column_config.DateColumn("Data", disabled=True, format="YYYY-MM-DD"),
                COLUMN_MEMO: st.column_config.TextColumn("Descrição", disabled=True),
                COLUMN_AMOUNT: st.column_config.NumberColumn("Valor", format="%.2f", disabled=True),
                COLUMN_COMBINED_CATEGORY_DISPLAY: st.column_config.SelectboxColumn(
                    COLUMN_COMBINED_CATEGORY_DISPLAY,
                    options=sorted_combined_categories,
                    required=False,
                    width="large"
                ),
                COLUMN_ACCOUNT_TYPE: st.column_config.TextColumn("Conta", disabled=True),
                COLUMN_TYPE: st.column_config.TextColumn("Tipo", disabled=True)
            }
            
            edited_df_from_editor = st.data_editor(
                editor_df_display,
                column_config=column_config,
                key=editor_key,
                hide_index=True,
                num_rows="fixed"
            )

            # Save All Button
            if st.button("Salvar Todas as Alterações", key="save_all_button_db"):
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
                                elif combined_value_str:
                                    new_main_cat_val = combined_value_str.strip()
                                    new_sub_cat_val = "Não Categorizado"
                                else:
                                    new_main_cat_val = "Não Categorizado"
                                    new_sub_cat_val = "Não Categorizado"
                            
                            # Save if categories have actually changed
                            if (new_main_cat_val != original_main_cat_val or 
                                new_sub_cat_val != original_sub_cat_val):
                                save_user_category(transaction_id_val, new_main_cat_val, new_sub_cat_val)
                                actually_saved_something = True
                        
                        if actually_saved_something:
                            load_all_transactions_data_from_db.clear()
                            st.toast("Todas as alterações foram salvas com sucesso!", icon="✅")
                            st.session_state[editor_key]["edited_rows"] = {} 
                            st.rerun()
                        else:
                            st.toast("Nenhuma alteração para salvar.", icon="🤷")
                    else:
                        st.toast("Nenhuma edição feita para salvar.", icon="🤷")
                else:
                    st.toast("Nenhuma alteração detectada.", icon="ℹ️")
        else:
            st.info("Nenhuma transação para exibir com os filtros selecionados.")

    # Budget Planning Section
    if 'budget_values_dict' not in st.session_state:
        st.session_state.budget_values_dict = load_user_budget()

    def calculate_average_spent(df, main_category, sub_category, end_date_for_avg_calc):
        if df.empty or pd.isna(end_date_for_avg_calc):
            return 0.0
        
        try:
            if isinstance(end_date_for_avg_calc, pd.Timestamp):
                end_date_for_avg_calc = end_date_for_avg_calc.date()
            start_date_for_avg_calc = end_date_for_avg_calc - relativedelta(months=3)
        except TypeError:
            return 0.0

        category_df = df[
            (df[COLUMN_MAIN_CATEGORY] == main_category) &
            (df[COLUMN_SUB_CATEGORY] == sub_category)
        ]
        
        expenses_df = category_df[
            (category_df[COLUMN_AMOUNT] < 0) &
            (category_df[COLUMN_DATE] >= start_date_for_avg_calc) &
            (category_df[COLUMN_DATE] <= end_date_for_avg_calc)
        ]
        
        if expenses_df.empty:
            return 0.0
        
        total_spent = expenses_df[COLUMN_AMOUNT].abs().sum()
        return round(total_spent / 3.0, 2)

    budget_table_data_list = []
    
    if not raw_transactions_df.empty:
        budgetable_df = raw_transactions_df[
            ~raw_transactions_df[COLUMN_MAIN_CATEGORY].isin(['Ignorar', 'Extraordinários'])
        ].copy()

        if not budgetable_df.empty:
            latest_date_in_view = budgetable_df[COLUMN_DATE].max()
            if pd.isna(latest_date_in_view):
                latest_date_in_view = date.today() 

            unique_categories = budgetable_df[[COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]].drop_duplicates().sort_values(
                by=[COLUMN_MAIN_CATEGORY, COLUMN_SUB_CATEGORY]
            )

            for _, row in unique_categories.iterrows():
                mc = row[COLUMN_MAIN_CATEGORY]
                sc = row[COLUMN_SUB_CATEGORY]
                avg_spent = calculate_average_spent(budgetable_df, mc, sc, latest_date_in_view)
                current_budget = st.session_state.budget_values_dict.get((mc, sc), 0.0)
                
                budget_table_data_list.append({
                    "Categoria Principal": mc,
                    "Subcategoria": sc,
                    "Média Gasto (3M)": avg_spent,
                    "Orçamento (R$)": current_budget
                })

    current_budget_df_for_editor = pd.DataFrame(budget_table_data_list)
    st.session_state.last_budget_df_for_editor = current_budget_df_for_editor.copy()

    if not current_budget_df_for_editor.empty:
        st.markdown("### Planejamento de Orçamento")
        
        # Create two columns: left for budget table, right for donut chart
        col_budget_left, col_budget_right = st.columns([2, 1])
        
        with col_budget_left:
            budget_editor_key = "budget_data_editor_db"
            budget_column_config = {
                "Categoria Principal": st.column_config.TextColumn("Categoria Principal", disabled=True),
                "Subcategoria": st.column_config.TextColumn("Subcategoria", disabled=True),
                "Média Gasto (3M)": st.column_config.NumberColumn("Média Gasto 3 Meses", format="%.2f", disabled=True),
                "Orçamento (R$)": st.column_config.NumberColumn("Orçamento (R$)", format="%.2f", min_value=0.0)
            }
            
            edited_budget_df = st.data_editor(
                current_budget_df_for_editor,
                column_config=budget_column_config,
                key=budget_editor_key,
                hide_index=True,
                num_rows="fixed",
                use_container_width=True
            )
        
        with col_budget_right:
            st.markdown("#### 📊 Distribuição por Categoria")
            
            # Prepare data for donut chart - group by main category
            main_category_budget = {}
            for (main_cat, _), budget_val in st.session_state.budget_values_dict.items():
                budget_val = float(budget_val)
                if budget_val > 0:  # Only include categories with budget > 0
                    if main_cat in main_category_budget:
                        main_category_budget[main_cat] += budget_val
                    else:
                        main_category_budget[main_cat] = budget_val
            
            # Create donut chart if there's budget data
            if main_category_budget:
                # Prepare data for plotly
                categories = list(main_category_budget.keys())
                values = list(main_category_budget.values())
                
                # Create donut chart
                fig_donut = px.pie(
                    values=values,
                    names=categories,
                    title="Orçamento por Categoria Principal",
                    hole=0.4  # This makes it a donut chart
                )
                
                # Update layout for better display
                fig_donut.update_traces(
                    textposition='inside', 
                    textinfo='percent+label',
                    textfont_size=10
                )
                
                fig_donut.update_layout(
                    showlegend=True,
                    legend=dict(
                        orientation="v",
                        yanchor="middle",
                        y=0.5,
                        xanchor="left",
                        x=1.01
                    ),
                    margin=dict(l=0, r=0, t=30, b=0),
                    height=400
                )
                
                st.plotly_chart(fig_donut, use_container_width=True)
            else:
                st.info("📊 Defina valores de orçamento para visualizar a distribuição")

        # Process changes from the data editor automatically
        if budget_editor_key in st.session_state and "edited_rows" in st.session_state[budget_editor_key]:
            edited_budget_rows = st.session_state[budget_editor_key]["edited_rows"]
            
            if edited_budget_rows:
                for row_idx_str, changed_cols_dict in edited_budget_rows.items():
                    row_idx = int(row_idx_str)
                    
                    if "Orçamento (R$)" in changed_cols_dict:
                        new_budget_value = changed_cols_dict["Orçamento (R$)"]
                        
                        if hasattr(st.session_state, 'last_budget_df_for_editor') and row_idx < len(st.session_state.last_budget_df_for_editor):
                            main_cat = st.session_state.last_budget_df_for_editor.iloc[row_idx]["Categoria Principal"]
                            sub_cat = st.session_state.last_budget_df_for_editor.iloc[row_idx]["Subcategoria"]
                            
                            st.session_state.budget_values_dict[(main_cat, sub_cat)] = float(new_budget_value)
                
                # Clear the edited rows after processing
                st.session_state[budget_editor_key]["edited_rows"] = {}

        if st.button("Salvar Orçamento", key="save_budget_button_db"):
            save_user_budget(st.session_state.budget_values_dict)
            st.rerun()
    else:
        st.info("Nenhuma categoria encontrada para planejamento de orçamento. Certifique-se de que há dados de transações carregados.")

    # Budget Summary Section
    st.markdown("---")
    st.subheader("Resumo do Orçamento")
    
    # Calculate budget summaries based on the latest budget_values_dict
    total_budgeted_income = 0.0
    total_budgeted_expenses = 0.0
    total_budgeted_investments = 0.0
    INCOME_CATEGORIES = ["Renda"] 
    INVESTMENT_CATEGORIES = ["Investimentos"]

    for (main_cat, _), budget_val in st.session_state.budget_values_dict.items():
        budget_val = float(budget_val)  # Ensure it's a float
        if main_cat in INCOME_CATEGORIES:
            total_budgeted_income += budget_val
        elif main_cat in INVESTMENT_CATEGORIES:
            total_budgeted_investments += budget_val
        elif main_cat not in ['Ignorar', 'Extraordinários']:  # Already filtered out from budgetable_df
            total_budgeted_expenses += budget_val
            
    # Calculate "Disponível" (Available)
    available_budget = total_budgeted_income - total_budgeted_expenses - total_budgeted_investments

    col_summary1, col_summary2, col_summary3, col_summary4 = st.columns(4)
    
    with col_summary1:
        st.metric(label="Total de Renda Orçada", value=f"R$ {total_budgeted_income:.2f}")
    
    with col_summary2:
        expense_percentage_str = "(N/A)"
        if total_budgeted_income > 0:
            expense_percentage = (total_budgeted_expenses / total_budgeted_income) * 100
            expense_percentage_str = f"({expense_percentage:.1f}%)"
        st.metric(label="Total de Despesas Orçadas", value=f"R$ {total_budgeted_expenses:.2f} {expense_percentage_str}")
    
    with col_summary3:
        investment_percentage_str = "(N/A)"
        if total_budgeted_income > 0:
            investment_percentage = (total_budgeted_investments / total_budgeted_income) * 100
            investment_percentage_str = f"({investment_percentage:.1f}%)"
        st.metric(label="Total de Investimentos Orçados", value=f"R$ {total_budgeted_investments:.2f} {investment_percentage_str}")
    
    with col_summary4:
        st.metric(label="Disponível", value=f"R$ {available_budget:.2f}", delta_color="off")

    # Save Budget Button
    if st.button("Salvar Orçamento", key="save_budget_main_button_db"):
        save_user_budget(st.session_state.budget_values_dict)
        st.rerun()

else:
    st.warning("Nenhuma transação encontrada. Certifique-se de que os dados foram carregados no banco de dados.")
    st.info("Execute o processamento backend para carregar dados OFX no banco de dados primeiro.") 