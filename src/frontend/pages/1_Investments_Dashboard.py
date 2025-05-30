from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import os

# Adjust path to import from backend and sql
import sys
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from backend.investments.constants import EQUITY_TARGET, FIXED_INCOME_TARGET, BIRTH_DATE
from sql.connection import run_query

# Path for target percentages CSV file
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
TARGET_PERCENTAGES_FILE = os.path.join(project_root, 'resources', 'target_percentages.csv')

def safe_percentage_to_float(value):
    """Safely convert percentage value to float, handling strings with % symbols"""
    if value is None:
        return 0.0
    
    if isinstance(value, (int, float)):
        return float(value)
    
    if isinstance(value, str):
        # Remove % symbol if present and convert to float
        cleaned_value = value.strip().rstrip('%')
        try:
            return float(cleaned_value)
        except ValueError:
            return 0.0
    
    return 0.0

def load_target_percentages():
    """Load target percentages from CSV file"""
    if os.path.exists(TARGET_PERCENTAGES_FILE):
        try:
            df = pd.read_csv(TARGET_PERCENTAGES_FILE)
            # Check if the file is empty or has no columns
            if df.empty or len(df.columns) == 0:
                return {}
            
            # Check if required columns exist
            if 'asset' not in df.columns or 'target_percentage' not in df.columns:
                st.warning("Arquivo de metas de percentuais tem formato inválido. Criando novo arquivo.")
                return {}
            
            # Convert to dictionary for easy lookup
            target_dict = {}
            for _, row in df.iterrows():
                target_dict[row['asset']] = safe_percentage_to_float(row['target_percentage'])
            return target_dict
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            # File exists but is empty or corrupted
            st.info("Arquivo de metas de percentuais está vazio. Será criado quando você salvar suas metas.")
            return {}
        except Exception as e:
            st.warning(f"Erro ao carregar metas de percentuais: {e}")
            return {}
    return {}

def save_target_percentages(target_dict):
    """Save target percentages to CSV file"""
    try:
        # Convert dictionary to DataFrame
        if target_dict:
            data = [{'asset': asset, 'target_percentage': percentage} 
                    for asset, percentage in target_dict.items()]
            df = pd.DataFrame(data)
        else:
            # Create empty DataFrame with proper columns
            df = pd.DataFrame(columns=['asset', 'target_percentage'])
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(TARGET_PERCENTAGES_FILE), exist_ok=True)
        
        # Save to CSV
        df.to_csv(TARGET_PERCENTAGES_FILE, index=False)
        
        if target_dict:
            st.toast("Metas de percentuais salvas com sucesso!", icon="✅")
        else:
            st.toast("Metas resetadas com sucesso!", icon="🔄")
        return True
    except Exception as e:
        st.error(f"Erro ao salvar metas de percentuais: {e}")
        st.toast("Falha ao salvar as metas.", icon="❌")
        return False

def get_daily_balance(start_date, end_date):
    query = (f"SELECT date, sum(value) as value "
             f"FROM daily_balance "
             f"WHERE date BETWEEN '{start_date}' AND '{end_date}' "
             f"GROUP BY date")
    return run_query(query, target_db="local")

def get_daily_balance_by_asset(start_date, end_date):
    query = (f"SELECT asset, date, value "
             f"FROM daily_balance "
             f"WHERE date BETWEEN '{start_date}' AND '{end_date}'")
    return run_query(query, target_db="local")

def get_daily_balance_by_type(start_date, end_date):
    query = (f"SELECT type, date, sum(value) as value "
             f"FROM daily_balance "
             f"WHERE date BETWEEN '{start_date}' AND '{end_date}' "
             f"GROUP BY type, date")
    df = run_query(query, target_db="local")
    if not df.empty:
        df['percentage'] = df.groupby('date')['value'].transform(
            lambda x: x / x.sum() * 100)
    return df

def get_dates():
    query = "SELECT MIN(date) AS start_date, MAX(date) AS end_date FROM daily_balance;"
    return run_query(query, target_db="local")

def get_financial_independence_data(start_date=None, end_date=None):
    """Get data for financial independence analysis"""
    # Build date filter conditions
    portfolio_date_filter = ""
    expenses_date_filter = ""
    
    if start_date and end_date:
        portfolio_date_filter = f"AND date BETWEEN '{start_date}' AND '{end_date}'"
        expenses_date_filter = f"AND date BETWEEN '{start_date}' AND '{end_date}'"
    
    # Get monthly portfolio values (last day of each month)
    portfolio_query = f"""
        SELECT 
            year_month,
            date,
            portfolio_value
        FROM (
            SELECT 
                strftime('%Y-%m', date) as year_month,
                date,
                SUM(value) as portfolio_value,
                ROW_NUMBER() OVER (
                    PARTITION BY strftime('%Y-%m', date) 
                    ORDER BY date DESC
                ) as rn
            FROM daily_balance
            WHERE 1=1 {portfolio_date_filter}
            GROUP BY date
        ) 
        WHERE rn = 1
        ORDER BY date DESC
    """
    
    portfolio_data = run_query(portfolio_query, target_db="local")
    
    # Get monthly expenses from transactions
    expenses_query = f"""
        SELECT 
            strftime('%Y-%m', date) as year_month,
            ABS(SUM(amount)) as monthly_expenses
        FROM ofx_transactions 
        WHERE amount < 0 
        AND main_category NOT IN ('Ignorar', 'Investimentos', 'Extraordinários')
        {expenses_date_filter}
        GROUP BY strftime('%Y-%m', date)
        ORDER BY year_month DESC
    """
    
    expenses_data = run_query(expenses_query, target_db="local")
    
    # Merge data and calculate metrics
    if not portfolio_data.empty and not expenses_data.empty:
        # Merge on year_month
        merged_data = portfolio_data.merge(expenses_data, on='year_month', how='inner')
        
        # Calculate passive income (4% rule divided by 12 months)
        merged_data['passive_income'] = (merged_data['portfolio_value'] * 0.04) / 12
        
        # Calculate independence percentage
        merged_data['independence_percentage'] = (merged_data['passive_income'] / merged_data['monthly_expenses']) * 100
        
        # Convert year_month to datetime for plotting
        merged_data['date'] = pd.to_datetime(merged_data['year_month'] + '-01')
        
        return merged_data.sort_values('date')
    
    return pd.DataFrame()

def get_summary_returns(start_date, end_date):
    # Adjusted for SQLite - using the actual year and month columns from the table
    query = ("SELECT (year || '-' || printf('%02d', month)) AS 'year_month', total_deposit, total_profit, "
             "moving_avg_profit_6, moving_avg_profit_12, moving_avg_deposit_6, moving_avg_deposit_12, "
             "total_return, moving_avg_return_6, moving_avg_return_12 "
             "FROM summary_returns "
             f"WHERE CAST(strftime('%Y', '{start_date}') AS INTEGER) <= year AND year <= CAST(strftime('%Y', '{end_date}') AS INTEGER) "
             "ORDER BY year, month")
    
    monthly_returns = run_query(query, target_db="local")
    if not monthly_returns.empty:
        monthly_returns['total'] = monthly_returns['total_deposit'] + monthly_returns['total_profit']
        monthly_returns['deposit_percentage'] = (monthly_returns['total_deposit'] / monthly_returns['total']) * 100
        monthly_returns['profit_percentage'] = (monthly_returns['total_profit'] / monthly_returns['total']) * 100
    return monthly_returns

def get_summary_by_asset(start_date, end_date):
    query = ("SELECT asset, (year || '-' || printf('%02d', month)) AS 'year_month', "
             "deposit, profit, net_increase "
             "FROM financial_returns "
             f"WHERE CAST(strftime('%Y', '{start_date}') AS INTEGER) <= year AND year <= CAST(strftime('%Y', '{end_date}') AS INTEGER)")
    return run_query(query, target_db="local")

def get_last_state():
    query = ("""
    WITH DATA
    AS(
        SELECT 
            asset, 
            value, 
            type, 
            COALESCE(percentage, 0) AS expected_percentage,
            (value / total_value) * 100 AS actual_percentage,
            CASE WHEN COALESCE(percentage, 0) > 0 THEN COALESCE(percentage, 0) - (value / total_value) * 100 ELSE 0 END AS diff,
            (COALESCE(percentage, 0) * total_value / 100.0) - value AS absolute_diff
        FROM daily_balance t1 
        INNER JOIN ( 
        SELECT 
             MAX(date) AS max_date 
        FROM 
             daily_balance 
        ) t2 ON t1.date = t2.max_date 
        LEFT JOIN target_percentage ON asset = name
        CROSS JOIN (
            SELECT SUM(value) AS total_value
            FROM daily_balance
            WHERE date = (SELECT MAX(date) FROM daily_balance)
        ) AS total
    ),
    POSITIVE_DIFF_TOTAL AS(
        SELECT sum(absolute_diff) as positive_diff
        FROM DATA
        WHERE absolute_diff > 0
    )
    SELECT
        asset,
        value,
        type,
        expected_percentage,
        actual_percentage,
        diff,
        absolute_diff,
        CASE WHEN positive_diff != 0 AND absolute_diff > 0 THEN absolute_diff / positive_diff ELSE 0 END AS diff_ratio
    FROM DATA
    CROSS JOIN POSITIVE_DIFF_TOTAL
    ORDER BY type, value DESC
    """)
    return run_query(query, target_db="local")

def format_currency(amount, currency_symbol) -> str:
    formatted_amount = f"{amount:,.2f}"
    return f"{currency_symbol} {formatted_amount}"

def plot_forecast(current_balance):
    st.header("📮 Projeção de Investimentos")
    
    # Get 6-month average deposit for default value (same query as in plot_summary)
    six_months_query = ("""
        SELECT 
            AVG(total_deposit) as avg_deposit_6m,
            AVG(total_profit) as avg_profit_6m
        FROM (
            SELECT total_deposit, total_profit
            FROM summary_returns 
            ORDER BY year DESC, month DESC
            LIMIT 6
        ) AS last_six_months
    """)
    
    six_months_data = run_query(six_months_query, target_db="local")
    default_deposit = 1000.0  # Fallback default
    
    if not six_months_data.empty and not pd.isna(six_months_data['avg_deposit_6m'].iloc[0]):
        default_deposit = float(six_months_data['avg_deposit_6m'].iloc[0])
    
    col1, col2 = st.columns(2)
    with col1:
        deposit = st.number_input("Depósito Mensal (R$):", value=default_deposit, min_value=0.0, step=100.0, format="%.2f")
    with col2:
        monthly_return_rate = st.number_input("Retorno Mensal Esperado (%):", value=0.6, min_value=0.0, max_value=5.0, step=0.01, format="%.2f") / 100

    # Create date range for the next N years
    forecast_years = st.slider("Horizonte de Projeção (Anos):", min_value=1, max_value=40, value=20)
    current_date = datetime.now()
    date_list = [current_date + timedelta(days=30 * i) for i in range(forecast_years * 12)]

    # Initialize balance list
    balance_list = []
    age_list = []

    # Calculate balance for each month
    for i, date_val in enumerate(date_list):
        age_at_date = date_val.year - BIRTH_DATE.year - ((date_val.month, date_val.day) < (BIRTH_DATE.month, BIRTH_DATE.day))
        age_list.append(age_at_date)
        
        if i == 0:
            balance = current_balance
        else:
            balance = balance_list[i - 1] * (1 + monthly_return_rate) + deposit
        balance_list.append(balance)

    # Create DataFrame
    df_forecast = pd.DataFrame(data={'Date': date_list, 'Balance': balance_list, 'Age': age_list})

    # Calculate required portfolio for financial independence
    # Get current monthly expenses to calculate the required portfolio
    try:
        # Get latest monthly expenses from financial independence data
        fi_data = get_financial_independence_data()
        if not fi_data.empty:
            latest_expenses = fi_data.iloc[-1]['monthly_expenses']
            required_portfolio_fi = (latest_expenses * 12) / 0.04
        else:
            required_portfolio_fi = None
    except:
        required_portfolio_fi = None

    # Investment milestones
    targets = [100000, 500000, 1000000, 2000000, 3000000, 4000000, 5000000, 6000000, 7000000, 8000000, 9000000, 10000000,
               11000000, 12000000, 13000000, 14000000, 15000000]
    
    # Add required portfolio for financial independence to targets if calculated
    if required_portfolio_fi and required_portfolio_fi > 0:
        targets.append(int(required_portfolio_fi))
        # Sort targets to maintain order
        targets = sorted(set(targets))
    
    milestones_data = []

    for target in targets:
        if current_balance < target:
            target_rows = df_forecast[df_forecast['Balance'] >= target]
            if not target_rows.empty:
                target_row = target_rows.iloc[0]
                target_month_str = target_row['Date'].strftime('%B, %Y')
                months_to_reach = (target_row['Date'] - current_date).days // 30
                years_to_reach = months_to_reach // 12
                months_remaining = months_to_reach % 12
                age_years = target_row['Age']
                projected_return = target_row['Balance'] * monthly_return_rate

                if months_to_reach > 12:
                    time_to_reach = f"{years_to_reach} ano(s) e {months_remaining} mês(es)"
                else:
                    time_to_reach = f"{months_to_reach} meses"

                # Calculate passive income for this target
                passive_income_target = (target * 0.04) / 12
                
                # Check if this is the financial independence target
                target_label = format_currency(target, 'R$')
                if required_portfolio_fi and abs(target - required_portfolio_fi) < 1000:
                    target_label += " 🎯"  # Add target emoji for FI milestone

                milestones_data.append({
                    'Meta': target_label,
                    'Tempo para Alcançar': time_to_reach,
                    'Data da Meta': target_month_str,
                    'Idade na Meta': f"{age_years} anos",
                    'Renda Passiva': format_currency(passive_income_target, 'R$'),
                    'Retorno Mensal na Meta': format_currency(projected_return, 'R$')
                })

    # Create two columns: left for milestones table, right for forecast chart
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        if milestones_data:
            st.subheader("🎯 Marcos dos Investimentos")
            st.dataframe(pd.DataFrame(milestones_data), hide_index=True, use_container_width=True)
    
    with col_right:
        st.subheader("📈 Crescimento da Carteira")
        # Create forecast chart
        fig_forecast = px.area(df_forecast, x='Date', y='Balance', title='Projeção de Crescimento da Carteira', hover_data=['Age'])
        fig_forecast.update_xaxes(title_text='Data')
        fig_forecast.update_yaxes(title_text='Saldo Projetado (R$)')
        st.plotly_chart(fig_forecast, use_container_width=True)

def plot_summary():
    st.header("💰 Resumo da Carteira")
    
    # Get portfolio data first to calculate total value
    df = get_last_state()
    if df.empty:
        st.warning("Nenhum dado da carteira atual encontrado.")
        return
    
    fixed_income_sum = df[df['type'] == 'fixed_income']['value'].sum()
    equity_sum = df[df['type'] == 'equity']['value'].sum()
    total_sum = fixed_income_sum + equity_sum
    
    # Get 6-month averages
    six_months_query = ("""
        SELECT 
            AVG(total_deposit) as avg_deposit_6m,
            AVG(total_profit) as avg_profit_6m
        FROM (
            SELECT total_deposit, total_profit
            FROM summary_returns 
            ORDER BY year DESC, month DESC
            LIMIT 6
        ) AS last_six_months
    """)
    
    six_months_data = run_query(six_months_query, target_db="local")
    
    # Display main metrics first - 3 columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="💰 Valor Total da Carteira",
            value=format_currency(total_sum, 'R$')
        )
    
    if not six_months_data.empty:
        avg_deposit_6m = six_months_data['avg_deposit_6m'].iloc[0] if not pd.isna(six_months_data['avg_deposit_6m'].iloc[0]) else 0
        avg_profit_6m = six_months_data['avg_profit_6m'].iloc[0] if not pd.isna(six_months_data['avg_profit_6m'].iloc[0]) else 0
        
        with col2:
            st.metric(
                label="📊 Média de Aporte (6 meses)",
                value=format_currency(avg_deposit_6m, 'R$')
            )
        
        with col3:
            st.metric(
                label="📈 Média de Rendimento (6 meses)",
                value=format_currency(avg_profit_6m, 'R$')
            )
    
    st.markdown("---")
    
    aporte_input = st.number_input("Simular Contribuição Mensal (R$):", value=0.0, min_value=0.0, step=100.0, format="%.2f")
    
    if total_sum == 0:
        st.warning("O valor total da carteira é zero.")
        return
    
    fixed_income_target = FIXED_INCOME_TARGET
    equity_target = EQUITY_TARGET
    
    fixed_income_percentage = 100 * fixed_income_sum / total_sum
    equity_percentage = 100 * equity_sum / total_sum
    fixed_income_diff = fixed_income_percentage - fixed_income_target
    equity_diff = equity_percentage - equity_target

    # Display overall allocation
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏦 Renda Fixa")
        st.metric(
            label=f"Meta: {fixed_income_target}%",
            value=f"{fixed_income_percentage:.1f}%",
            delta=f"{fixed_income_diff:.1f}%"
        )
        st.progress(min(fixed_income_percentage / 100, 1.0))
        st.caption(f"Valor: {format_currency(fixed_income_sum, 'R$')}")

    with col2:
        st.subheader("📈 Renda Variável")
        st.metric(
            label=f"Meta: {equity_target}%",
            value=f"{equity_percentage:.1f}%",
            delta=f"{equity_diff:.1f}%"
        )
        st.progress(min(equity_percentage / 100, 1.0))
        st.caption(f"Valor: {format_currency(equity_sum, 'R$')}")

    # Detailed allocation table
    st.subheader("📋 Alocação Detalhada de Ativos")
    
    if aporte_input > 0:
        st.info(f"Sugestões de rebalanceamento baseadas em contribuição mensal de R$ {aporte_input:,.2f}:")
    
    # Load user-defined target percentages
    user_target_percentages = load_target_percentages()
    
    # Initialize session state for target percentages if not exists
    if 'target_percentages_dict' not in st.session_state:
        st.session_state.target_percentages_dict = user_target_percentages.copy()
    
    # Prepare display data with editable target percentages
    display_data = []
    
    for _, row in df.iterrows():
        asset = row['asset']
        value = row['value']
        expected_percentage = row['expected_percentage']
        actual_percentage = row['actual_percentage']
        absolute_diff = row['absolute_diff']
        diff_ratio = row['diff_ratio']
        asset_type = row['type']
        
        # Use user-defined target percentage if available, otherwise use database value
        if asset in st.session_state.target_percentages_dict:
            target_percentage_to_use = st.session_state.target_percentages_dict[asset]
        else:
            target_percentage_to_use = safe_percentage_to_float(expected_percentage)
        
        # Convert actual percentage to float
        actual_percentage_float = safe_percentage_to_float(actual_percentage)
        
        # Recalculate difference and ratio based on potentially updated target
        if total_sum > 0:
            target_value = (target_percentage_to_use * total_sum) / 100.0
            new_absolute_diff = target_value - value
            # Recalculate diff_ratio based on positive differences
            positive_diff_total = sum(max(0, (st.session_state.target_percentages_dict.get(r['asset'], 
                                         safe_percentage_to_float(r['expected_percentage'])) * total_sum / 100.0) - r['value'])
                                    for _, r in df.iterrows())
            new_diff_ratio = (new_absolute_diff / positive_diff_total) if positive_diff_total > 0 and new_absolute_diff > 0 else 0
        else:
            new_absolute_diff = 0
            new_diff_ratio = 0
        
        suggested_aport = new_diff_ratio * aporte_input if aporte_input > 0 else 0
        
        display_data.append({
            'Ativo': asset,
            'Tipo': '🏦 Renda Fixa' if asset_type == 'fixed_income' else '📈 Renda Variável',
            'Valor Atual': format_currency(value, 'R$'),
            'Meta %': target_percentage_to_use,
            'Atual %': f"{actual_percentage_float:.1f}%",
            'Diferença': format_currency(new_absolute_diff, 'R$'),
            'Alocação Sugerida': format_currency(suggested_aport, 'R$') if aporte_input > 0 else '-'
        })
    
    df_display = pd.DataFrame(display_data)
    
    # Configure editable data editor
    column_config = {
        'Ativo': st.column_config.TextColumn('Ativo', disabled=True),
        'Tipo': st.column_config.TextColumn('Tipo', disabled=True),
        'Valor Atual': st.column_config.TextColumn('Valor Atual', disabled=True),
        'Meta %': st.column_config.NumberColumn(
            'Meta %',
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            format="%.1f"
        ),
        'Atual %': st.column_config.TextColumn('Atual %', disabled=True),
        'Diferença': st.column_config.TextColumn('Diferença', disabled=True),
        'Alocação Sugerida': st.column_config.TextColumn('Alocação Sugerida', disabled=True)
    }
    
    # Display editable table
    edited_df = st.data_editor(
        df_display,
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        key="allocation_editor"
    )
    
    # Calculate and display total percentage
    total_meta_percentage = sum(row['Meta %'] for row in display_data)
    
    # Color coding for the total
    if abs(total_meta_percentage - 100.0) < 0.1:  # Close to 100%
        total_color = "🟢"
        total_status = "Perfeito!"
    elif total_meta_percentage > 100.0:
        total_color = "🔴"
        total_status = "Acima de 100%"
    else:
        total_color = "🟡"
        total_status = "Abaixo de 100%"
    
    st.markdown(f"**{total_color} Total das Metas: {total_meta_percentage:.1f}%** ({total_status})")
    
    # Process changes from data editor
    if "allocation_editor" in st.session_state and "edited_rows" in st.session_state["allocation_editor"]:
        edited_rows = st.session_state["allocation_editor"]["edited_rows"]
        
        if edited_rows:
            # Update session state with changes
            for row_idx_str, changes in edited_rows.items():
                row_idx = int(row_idx_str)
                if "Meta %" in changes:
                    asset_name = df_display.iloc[row_idx]['Ativo']
                    new_target = float(changes["Meta %"])
                    st.session_state.target_percentages_dict[asset_name] = new_target
    
    # Save button
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("💾 Salvar Metas", key="save_targets_btn"):
            if save_target_percentages(st.session_state.target_percentages_dict):
                st.rerun()
    
    with col2:
        if st.button("🔄 Resetar para Padrão", key="reset_targets_btn"):
            # Clear user-defined targets
            st.session_state.target_percentages_dict = {}
            if save_target_percentages({}):
                st.rerun()

def plot_financial_independence(start_date, end_date):
    st.header("🎯 Independência Financeira")
    
    # Get financial independence data with date filters
    fi_data = get_financial_independence_data(start_date, end_date)
    
    if fi_data.empty:
        st.warning("Não há dados suficientes para o período selecionado.")
        st.info("Tente expandir o período ou verificar se há dados de carteira e transações disponíveis.")
        return
    
    # Calculate current independence percentage (from latest available data)
    latest_data = fi_data.iloc[-1]
    current_independence = latest_data['independence_percentage']
    current_passive_income = latest_data['passive_income']
    current_expenses = latest_data['monthly_expenses']
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Create the chart with passive income and expenses
        fig_fi = px.bar(
            fi_data,
            x='date',
            y=['passive_income', 'monthly_expenses'],
            title='📊 Renda Passiva vs Gastos Mensais',
            labels={
                'value': 'Valor (R$)',
                'date': 'Mês',
                'variable': 'Tipo'
            },
            color_discrete_map={
                'passive_income': '#10B981',    # Modern emerald green
                'monthly_expenses': '#F59E0B'   # Vibrant amber orange
            }
        )
        
        # Update layout
        fig_fi.update_layout(
            xaxis_title='Mês',
            yaxis_title='Valor (R$)',
            legend_title='Legenda',
            barmode='group'
        )
        
        # Update legend labels
        fig_fi.for_each_trace(lambda t: t.update(
            name='Renda Passiva (4%)' if t.name == 'passive_income' else 'Gastos Mensais'
        ))
        
        st.plotly_chart(fig_fi, use_container_width=True)
    
    with col2:
        st.subheader("📈 Status da Independência")
        
        # Calculate required portfolio for independence
        required_portfolio = (current_expenses * 12) / 0.04
        
        # Current independence percentage
        if current_independence >= 100:
            independence_color = "🟢"
            independence_status = "Independência Atingida!"
        elif current_independence >= 75:
            independence_color = "🟡"
            independence_status = "Quase Lá!"
        elif current_independence >= 50:
            independence_color = "🟠"
            independence_status = "No Caminho Certo"
        else:
            independence_color = "🔴"
            independence_status = "Início da Jornada"
        
        st.metric(
            label=f"{independence_color} Independência Financeira",
            value=f"{current_independence:.1f}%",
            help=independence_status
        )
        
        st.metric(
            label="🎯 Patrimônio Necessário",
            value=format_currency(required_portfolio, 'R$'),
            help="Valor necessário para cobrir os gastos atuais (regra dos 4%)"
        )
        
        st.metric(
            label="💰 Renda Passiva Atual",
            value=format_currency(current_passive_income, 'R$'),
            help="Baseado na regra dos 4% (anual dividido por 12)"
        )
        
        st.metric(
            label="💸 Gastos Mensais",
            value=format_currency(current_expenses, 'R$'),
            help="Gastos médios do último mês (excluindo investimentos)"
        )
        
        # Progress bar
        progress_value = min(current_independence / 100, 1.0)
        st.progress(progress_value)
        
        if current_independence < 100:
            deficit = current_expenses - current_passive_income
            st.caption(f"💡 Faltam R$ {deficit:,.2f}/mês para independência")
        else:
            surplus = current_passive_income - current_expenses
            st.caption(f"🎉 Superávit de R$ {surplus:,.2f}/mês!")

def plot_history(start_date, end_date):
    st.header("📊 Performance Histórica")
    
    # Load historical data
    daily_balance = get_daily_balance(start_date, end_date)
    daily_balance_by_asset = get_daily_balance_by_asset(start_date, end_date)
    daily_balance_by_type = get_daily_balance_by_type(start_date, end_date)
    monthly_returns = get_summary_returns(start_date, end_date)
    summary_by_asset = get_summary_by_asset(start_date, end_date)

    # Overall portfolio value chart
    if not daily_balance.empty:
        fig_balance = px.area(
            daily_balance,
            x='date',
            y='value',
            title='📈 Valor da Carteira ao Longo do Tempo'
        )
        st.plotly_chart(fig_balance, use_container_width=True)
    else:
        st.info("Nenhum dado de saldo da carteira disponível para o período selecionado.")

    # Asset allocation charts
    col1, col2 = st.columns(2)

    with col1:
        if not daily_balance_by_type.empty:
            fig_percentage = px.area(
                daily_balance_by_type,
                x='date',
                y='percentage',
                color='type',
                title='🎯 Alocação de Ativos (%) ao Longo do Tempo',
            )

            fig_percentage.add_hline(y=EQUITY_TARGET, line_dash="dash", line_color="red",
                                   annotation_text=f"Meta Renda Variável ({EQUITY_TARGET}%)",
                                   annotation_position="bottom right")
            
            fig_percentage.add_hline(y=FIXED_INCOME_TARGET, line_dash="dash", line_color="blue",
                                   annotation_text=f"Meta Renda Fixa ({FIXED_INCOME_TARGET}%)",
                                   annotation_position="top right")

            fig_percentage.update_layout(
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.3,
                    xanchor="center",
                    x=0.5
                )
            )
            st.plotly_chart(fig_percentage, use_container_width=True)
        else:
            st.info("Nenhum dado de porcentagem de alocação disponível.")

    with col2:
        if not daily_balance_by_type.empty:
            fig_type = px.area(
                daily_balance_by_type,
                x='date',
                y='value',
                color='type',
                title='💰 Valor de Ativos (R$) por Tipo ao Longo do Tempo'
            )
            fig_type.update_layout(
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.3,
                    xanchor="center",
                    x=0.5
                )
            )
            st.plotly_chart(fig_type, use_container_width=True)
        else:
            st.info("Nenhum dado de valor de ativos disponível.")

    # Asset breakdown chart
    if not daily_balance_by_asset.empty:
        fig_asset = px.area(
            daily_balance_by_asset,
            x='date',
            y='value',
            color='asset',
            title='📊 Valor da Carteira por Ativo ao Longo do Tempo'
        )
        st.plotly_chart(fig_asset, use_container_width=True)

    # Returns analysis
    if not monthly_returns.empty:
        st.subheader("💹 Análise de Retornos vs Depósitos")

        # Monthly returns and deposits
        fig_returns_deposits = px.bar(monthly_returns,
                                      x='year_month',
                                      y=['total_profit', 'total_deposit'],
                                      barmode='group',
                                      labels={'value': 'Valor (R$)', 'year_month': 'Ano-Mês'},
                                      title='📊 Lucro Mensal vs Depósitos',
                                      color_discrete_map={'total_profit': '#2ca02c', 'total_deposit': '#ff7f0e'})
        st.plotly_chart(fig_returns_deposits, use_container_width=True)

        # Moving averages
        fig_ma_returns_deposits = px.line(monthly_returns,
                                         x='year_month',
                                         y=['moving_avg_profit_6', 'moving_avg_deposit_6'],
                                         labels={'value': 'Valor (R$)', 'year_month': 'Ano-Mês'},
                                         title='📈 Médias Móveis de 6 Meses: Retornos e Depósitos',
                                         color_discrete_map={'moving_avg_profit_6': '#1f77b4', 'moving_avg_deposit_6': '#d62728'})
        st.plotly_chart(fig_ma_returns_deposits, use_container_width=True)

        # Returns by asset
        if not summary_by_asset.empty:
            fig_increase_by_asset = px.bar(summary_by_asset,
                                           x='year_month',
                                           y='net_increase',
                                           color="asset",
                                           title='📊 Aumento Líquido Mensal por Ativo')
            st.plotly_chart(fig_increase_by_asset, use_container_width=True)

        # Detailed returns analysis
        st.subheader("📈 Análise Detalhada de Retornos")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_returns = go.Figure()
            fig_returns.add_trace(
                go.Bar(x=monthly_returns['year_month'], y=monthly_returns['total_profit'], 
                       name='Lucro Total', marker_color='skyblue'))
            fig_returns.add_trace(
                go.Scatter(x=monthly_returns['year_month'], y=monthly_returns['moving_avg_profit_6'],
                           name='MM 6 Meses', mode='lines+markers',
                           line=dict(color='orange', width=2)))
            fig_returns.add_trace(
                go.Scatter(x=monthly_returns['year_month'], y=monthly_returns['moving_avg_profit_12'],
                           name='MM 12 Meses', mode='lines+markers',
                           line=dict(color='green', width=2)))
            fig_returns.update_layout(title='💰 Lucro com Médias Móveis',
                                      xaxis_title='Ano-Mês',
                                      yaxis_title='Valor (R$)')
            st.plotly_chart(fig_returns, use_container_width=True)

        with col2:
            fig_returns_percentage = go.Figure()
            fig_returns_percentage.add_trace(
                go.Bar(x=monthly_returns['year_month'], y=monthly_returns['total_return'], 
                       name='Retorno Total', marker_color='lightgreen'))
            fig_returns_percentage.add_trace(
                go.Scatter(x=monthly_returns['year_month'], y=monthly_returns['moving_avg_return_6'],
                           name='MM 6 Meses', mode='lines+markers',
                           line=dict(color='orange', width=2)))
            fig_returns_percentage.add_trace(
                go.Scatter(x=monthly_returns['year_month'], y=monthly_returns['moving_avg_return_12'],
                           name='MM 12 Meses', mode='lines+markers',
                           line=dict(color='green', width=2)))
            fig_returns_percentage.update_layout(title='📊 Retorno % com Médias Móveis',
                                                  xaxis_title='Ano-Mês',
                                                  yaxis_title='Retorno (%)')
            st.plotly_chart(fig_returns_percentage, use_container_width=True)

# Main page configuration
st.set_page_config(page_title="Painel de Investimentos", page_icon="💰", layout="wide")
st.title("Painel de Investimentos")

# Check if we have data
dates_check = get_dates()
if dates_check.empty:
    st.error("❌ Nenhum dado de investimento encontrado no banco de dados.")
    st.info("Certifique-se de que os dados de investimentos foram carregados no banco de dados local.")
    st.stop()

# Get date controls for the entire page in sidebar
with st.sidebar:
    st.header("📅 Período do Histórico")
    max_date = pd.to_datetime(dates_check['end_date'].iloc[0])
    min_date = pd.to_datetime(dates_check['start_date'].iloc[0])
    default_start = max_date - pd.DateOffset(years=2)
    if default_start < min_date:
        default_start = min_date
    
    start_date = st.date_input('Data Inicial', value=default_start.date(), min_value=min_date.date(), max_value=max_date.date())
    end_date = st.date_input('Data Final', value=max_date.date(), min_value=min_date.date(), max_value=max_date.date())

if start_date > end_date:
    st.error("A data final deve ser posterior à data inicial.")
    st.stop()

# Get total portfolio value for forecast
last_state = get_last_state()
current_balance = last_state['value'].sum() if not last_state.empty else 0

# Main dashboard sections
plot_summary()

st.markdown("---")
plot_financial_independence(start_date, end_date)

st.markdown("---")
if current_balance > 0:
    plot_forecast(current_balance)
else:
    st.warning("⚠️ Não é possível exibir a projeção: Nenhum saldo atual da carteira encontrado.")

st.markdown("---")
plot_history(start_date, end_date) 