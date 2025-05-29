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
    
    col1, col2 = st.columns(2)
    with col1:
        deposit = st.number_input("Depósito Mensal (R$):", value=1000.0, min_value=0.0, step=100.0, format="%.2f")
    with col2:
        monthly_return_rate = st.number_input("Retorno Mensal Esperado (%):", value=0.75, min_value=0.0, max_value=5.0, step=0.01, format="%.2f") / 100

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

    # Create forecast chart
    fig_forecast = px.area(df_forecast, x='Date', y='Balance', title='Projeção de Crescimento da Carteira', hover_data=['Age'])
    fig_forecast.update_xaxes(title_text='Data')
    fig_forecast.update_yaxes(title_text='Saldo Projetado (R$)')
    st.plotly_chart(fig_forecast, use_container_width=True)

    # Investment milestones
    targets = [100000, 500000, 1000000, 5000000, 10000000]
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

                milestones_data.append({
                    'Meta': format_currency(target, 'R$'),
                    'Tempo para Alcançar': time_to_reach,
                    'Data da Meta': target_month_str,
                    'Idade na Meta': f"{age_years} anos",
                    'Retorno Mensal na Meta': format_currency(projected_return, 'R$')
                })

    if milestones_data:
        st.subheader("🎯 Marcos dos Investimentos")
        st.dataframe(pd.DataFrame(milestones_data), hide_index=True)

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
            AVG(moving_avg_deposit_6) as avg_deposit_6m,
            AVG(moving_avg_profit_6) as avg_profit_6m
        FROM summary_returns 
        WHERE moving_avg_deposit_6 IS NOT NULL AND moving_avg_profit_6 IS NOT NULL
        ORDER BY year DESC, month DESC
        LIMIT 6
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
    
    # Prepare display data
    display_data = []
    
    for _, row in df.iterrows():
        asset = row['asset']
        value = row['value']
        expected_percentage = row['expected_percentage']
        actual_percentage = row['actual_percentage']
        absolute_diff = row['absolute_diff']
        diff_ratio = row['diff_ratio']
        asset_type = row['type']
        
        # Convert to float to handle any string values
        try:
            expected_percentage_float = float(expected_percentage) if expected_percentage is not None else 0.0
            actual_percentage_float = float(actual_percentage) if actual_percentage is not None else 0.0
        except (ValueError, TypeError):
            expected_percentage_float = 0.0
            actual_percentage_float = 0.0
        
        suggested_aport = diff_ratio * aporte_input if aporte_input > 0 else 0
        
        display_data.append({
            'Ativo': asset,
            'Tipo': '🏦 Renda Fixa' if asset_type == 'fixed_income' else '📈 Renda Variável',
            'Valor Atual': format_currency(value, 'R$'),
            'Meta %': f"{expected_percentage_float:.1f}%",
            'Atual %': f"{actual_percentage_float:.1f}%",
            'Diferença': format_currency(absolute_diff, 'R$'),
            'Alocação Sugerida': format_currency(suggested_aport, 'R$') if aporte_input > 0 else '-'
        })
    
    df_display = pd.DataFrame(display_data)
    st.dataframe(df_display, hide_index=True, use_container_width=True)

def plot_history():
    st.header("📊 Performance Histórica")
    
    dates = get_dates()
    if dates.empty:
        st.warning("Nenhum dado histórico disponível.")
        return

    # Date selection in sidebar
    with st.sidebar:
        st.header("📅 Período do Histórico")
        max_date = pd.to_datetime(dates['end_date'].iloc[0])
        min_date = pd.to_datetime(dates['start_date'].iloc[0])
        default_start = max_date - pd.DateOffset(years=2)
        if default_start < min_date:
            default_start = min_date
        
        start_date = st.date_input('Data Inicial', value=default_start.date(), min_value=min_date.date(), max_value=max_date.date())
        end_date = st.date_input('Data Final', value=max_date.date(), min_value=min_date.date(), max_value=max_date.date())

    if start_date > end_date:
        st.error("A data final deve ser posterior à data inicial.")
        return

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
                                         y=['moving_avg_profit_12', 'moving_avg_deposit_12'],
                                         labels={'value': 'Valor (R$)', 'year_month': 'Ano-Mês'},
                                         title='📈 Médias Móveis de 12 Meses: Retornos e Depósitos',
                                         color_discrete_map={'moving_avg_profit_12': '#1f77b4', 'moving_avg_deposit_12': '#d62728'})
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

# Database debugging section
with st.expander("🔍 Informações de Debug do Banco de Dados", expanded=False):
    st.subheader("Status das Tabelas de Investimentos")
    
    tables_to_check = [
        "daily_balance",
        "summary_returns", 
        "financial_returns",
        "target_percentage",
        "variable_income_daily_balance",
        "fixed_income_daily_balance", 
        "variable_income_operations",
        "fixed_income_operations",
        "asset_price",
        "daily_asset_price",
        "index_series"
    ]
    
    debug_results = []
    
    for table in tables_to_check:
        try:
            # Check if table exists and count rows
            count_query = f"SELECT COUNT(*) as row_count FROM {table}"
            result = run_query(count_query, target_db="local")
            
            if not result.empty:
                row_count = result['row_count'].iloc[0]
                status = "✅ Tem dados" if row_count > 0 else "⚠️ Vazia"
                
                # Get date range for time-series tables
                date_info = ""
                if table in ["daily_balance", "variable_income_daily_balance", "fixed_income_daily_balance", "asset_price", "daily_asset_price", "index_series"]:
                    try:
                        date_query = f"SELECT MIN(date) as min_date, MAX(date) as max_date FROM {table}"
                        date_result = run_query(date_query, target_db="local")
                        if not date_result.empty and row_count > 0:
                            min_date = date_result['min_date'].iloc[0]
                            max_date = date_result['max_date'].iloc[0]
                            date_info = f" | {min_date} até {max_date}"
                    except:
                        date_info = " | Período de datas indisponível"
                        
                debug_results.append({
                    "Tabela": table,
                    "Status": status,
                    "Quantidade de Linhas": row_count,
                    "Informações Adicionais": date_info
                })
            else:
                debug_results.append({
                    "Tabela": table,
                    "Status": "❌ Query falhou",
                    "Quantidade de Linhas": 0,
                    "Informações Adicionais": ""
                })
                
        except Exception as e:
            debug_results.append({
                "Tabela": table,
                "Status": "❌ Erro",
                "Quantidade de Linhas": 0,
                "Informações Adicionais": str(e)
            })
    
    # Display results
    debug_df = pd.DataFrame(debug_results)
    st.dataframe(debug_df, hide_index=True, use_container_width=True)
    
    # Summary
    empty_tables = [r["Tabela"] for r in debug_results if r["Quantidade de Linhas"] == 0]
    error_tables = [r["Tabela"] for r in debug_results if "Erro" in r["Status"] or "falhou" in r["Status"]]
    
    if empty_tables:
        st.warning(f"⚠️ Tabelas vazias: {', '.join(empty_tables)}")
    if error_tables:
        st.error(f"❌ Tabelas com erros: {', '.join(error_tables)}")
    
    if not empty_tables and not error_tables:
        st.success("✅ Todas as tabelas de investimentos têm dados!")

# Check if we have data
dates_check = get_dates()
if dates_check.empty:
    st.error("❌ Nenhum dado de investimento encontrado no banco de dados.")
    st.info("Certifique-se de que os dados de investimentos foram carregados no banco de dados local.")
    st.info("💡 Verifique a seção 'Informações de Debug do Banco de Dados' acima para ver quais tabelas precisam de dados.")
    st.stop()

# Get total portfolio value for forecast
last_state = get_last_state()
current_balance = last_state['value'].sum() if not last_state.empty else 0

# Main dashboard sections
plot_summary()

st.markdown("---")
if current_balance > 0:
    plot_forecast(current_balance)
else:
    st.warning("⚠️ Não é possível exibir a projeção: Nenhum saldo atual da carteira encontrado.")

st.markdown("---")
plot_history() 