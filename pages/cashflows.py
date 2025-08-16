import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import plotly.express as px
import plotly.graph_objects as go

from repos.cashflow_repo import CashflowRepository
from repos.stock_repo import StockRepository
from services.nbp import nbp_service
from utils.formatting import (
    format_currency, format_percentage, format_gain_loss, 
    format_polish_date, get_status_color
)

def show():
    """Wyświetla stronę zarządzania przepływami pieniężnymi."""
    
    st.markdown("## 💸 Przepływy pieniężne")
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Przegląd", "➕ Dodaj przepływ", "📈 Analiza", "📋 Historia", "💹 ROI"
    ])
    
    with tab1:
        show_overview_tab()
    
    with tab2:
        show_add_cashflow_tab()
    
    with tab3:
        show_analysis_tab()
    
    with tab4:
        show_history_tab()
    
    with tab5:
        show_roi_tab()

def show_overview_tab():
    """Wyświetla przegląd przepływów pieniężnych."""
    
    st.markdown("### 📊 Przegląd przepływów pieniężnych")
    
    # Aktualny stan konta
    account_balance = CashflowRepository.get_account_balance()
    
    # Podsumowanie dla bieżącego roku
    current_year = datetime.now().year
    summary = CashflowRepository.get_cashflow_summary(current_year)
    total_summary = CashflowRepository.get_cashflow_summary()
    
    # Metryki główne
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        balance_color = "green" if account_balance >= 0 else "red"
        st.metric(
            "💰 Stan konta",
            format_currency(account_balance)
        )
    
    with col2:
        net_flow = summary.get('net_cashflow', 0)
        st.metric(
            f"📊 Przepływ netto {current_year}",
            format_currency(net_flow),
            delta=format_currency(net_flow) if net_flow != 0 else None
        )
    
    with col3:
        total_deposits = summary.get('total_deposits', 0)
        st.metric(
            f"⬇️ Wpłaty {current_year}",
            format_currency(total_deposits)
        )
    
    with col4:
        total_withdrawals = summary.get('total_withdrawals', 0)
        st.metric(
            f"⬆️ Wypłaty {current_year}",
            format_currency(total_withdrawals)
        )
    
    # Dodatkowe metryki
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        dividends = summary.get('total_dividends', 0)
        st.metric("💎 Dywidendy", format_currency(dividends))
    
    with col2:
        option_premiums = summary.get('total_option_premiums', 0)
        st.metric("🎯 Premium opcje", format_currency(option_premiums))
    
    with col3:
        commissions = summary.get('total_commissions', 0)
        st.metric("💸 Prowizje", format_currency(commissions))
    
    with col4:
        taxes = summary.get('total_taxes', 0)
        st.metric("🧾 Podatki", format_currency(taxes))
    
    # Przeliczenie na PLN
    current_usd_rate = nbp_service.get_current_usd_rate()
    if current_usd_rate:
        st.markdown("#### 🇵🇱 Wartości w PLN")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            balance_pln = account_balance * current_usd_rate
            st.metric(
                "💰 Stan konta (PLN)",
                format_currency(balance_pln, "PLN")
            )
        
        with col2:
            net_flow_pln = net_flow * current_usd_rate
            st.metric(
                f"📊 Przepływ netto {current_year} (PLN)",
                format_currency(net_flow_pln, "PLN")
            )
        
        with col3:
            st.info(f"💱 Kurs USD/PLN: {current_usd_rate:.4f}")
    
    # Wykres miesięczny
    monthly_cashflows = CashflowRepository.get_monthly_cashflows(current_year)
    
    if monthly_cashflows:
        st.markdown("#### 📈 Miesięczne przepływy pieniężne")
        
        df = pd.DataFrame(monthly_cashflows)
        
        fig = go.Figure()
        
        # Wpływy
        fig.add_trace(go.Bar(
            x=df['year_month'],
            y=df['inflows'],
            name='Wpływy',
            marker_color='green',
            text=[format_currency(x) for x in df['inflows']],
            textposition='auto'
        ))
        
        # Wypływy
        fig.add_trace(go.Bar(
            x=df['year_month'],
            y=-df['outflows'],  # Ujemne dla lepszej wizualizacji
            name='Wypływy',
            marker_color='red',
            text=[format_currency(x) for x in df['outflows']],
            textposition='auto'
        ))
        
        # Przepływ netto jako linia
        fig.add_trace(go.Scatter(
            x=df['year_month'],
            y=df['net_flow'],
            mode='lines+markers',
            name='Przepływ netto',
            line=dict(color='blue', width=3),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            title=f"Przepływy pieniężne {current_year}",
            xaxis_title="Miesiąc",
            yaxis_title="Kwota (USD)",
            height=500,
            barmode='relative'
        )
        
        # Dodaj linię zerową
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Ostatnie przepływy
    st.markdown("#### 📋 Ostatnie przepływy")
    
    recent_cashflows = CashflowRepository.get_all_cashflows()[:10]  # Ostatnie 10
    
    if recent_cashflows:
        df = pd.DataFrame(recent_cashflows)
        
        # Formatowanie
        display_df = df.copy()
        display_df['amount_usd'] = display_df.apply(lambda row: 
            format_gain_loss(row['amount_usd'] if row['transaction_type'] in ['DEPOSIT', 'DIVIDEND', 'OPTION_PREMIUM'] 
                           else -row['amount_usd'])[0], axis=1)
        display_df['date'] = pd.to_datetime(display_df['date']).dt.strftime('%d.%m.%Y')
        
        # Mapowanie typów transakcji
        type_map = {
            'DEPOSIT': '⬇️ Wpłata',
            'WITHDRAWAL': '⬆️ Wypłata',
            'DIVIDEND': '💎 Dywidenda',
            'OPTION_PREMIUM': '🎯 Premium opcji',
            'COMMISSION': '💸 Prowizja',
            'TAX': '🧾 Podatek'
        }
        display_df['transaction_type'] = display_df['transaction_type'].map(type_map)
        
        st.dataframe(
            display_df[[
                'date', 'transaction_type', 'amount_usd', 'description', 'stock_symbol'
            ]].rename(columns={
                'date': 'Data',
                'transaction_type': 'Typ',
                'amount_usd': 'Kwota',
                'description': 'Opis',
                'stock_symbol': 'Akcja'
            }),
            use_container_width=True,
            hide_index=True
        )
    
    else:
        st.info("Brak zarejestrowanych przepływów pieniężnych.")

def show_add_cashflow_tab():
    """Formularz dodawania nowego przepływu pieniężnego."""
    
    st.markdown("### ➕ Dodaj przepływ pieniężny")
    
    with st.form("add_cashflow_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Typ transakcji
            transaction_type = st.selectbox(
                "Typ transakcji *",
                ["DEPOSIT", "WITHDRAWAL", "DIVIDEND", "OPTION_PREMIUM", "COMMISSION", "TAX"],
                format_func=lambda x: {
                    "DEPOSIT": "⬇️ Wpłata",
                    "WITHDRAWAL": "⬆️ Wypłata", 
                    "DIVIDEND": "💎 Dywidenda",
                    "OPTION_PREMIUM": "🎯 Premium opcji",
                    "COMMISSION": "💸 Prowizja",
                    "TAX": "🧾 Podatek"
                }[x]
            )
            
            # Kwota
            amount = st.number_input(
                "Kwota (USD) *",
                min_value=0.01,
                value=100.0,
                step=0.01,
                format="%.2f"
            )
        
        with col2:
            # Data
            transaction_date = st.date_input(
                "Data *",
                value=date.today(),
                max_value=date.today()
            )
            
            # Powiązana akcja (opcjonalne)
            stocks = StockRepository.get_all_stocks()
            stock_options = [None] + stocks
            
            related_stock = st.selectbox(
                "Powiązana akcja",
                options=stock_options,
                format_func=lambda x: "Brak" if x is None else f"{x['symbol']} - {x['name']}"
            )
        
        # Opis
        description = st.text_area(
            "Opis",
            placeholder="Opcjonalny opis transakcji..."
        )
        
        # Informacja o wpływie na stan konta
        if transaction_type in ['DEPOSIT', 'DIVIDEND', 'OPTION_PREMIUM']:
            impact = f"⬆️ Zwiększy stan konta o {format_currency(amount)}"
            impact_color = "green"
        else:
            impact = f"⬇️ Zmniejszy stan konta o {format_currency(amount)}"
            impact_color = "red"
        
        st.info(impact)
        
        # Przycisk dodania
        submitted = st.form_submit_button(
            "💾 Dodaj przepływ",
            type="primary",
            use_container_width=True
        )
        
        if submitted:
            try:
                cashflow_id = CashflowRepository.add_cashflow(
                    transaction_type=transaction_type,
                    amount_usd=amount,
                    date_value=transaction_date,
                    description=description,
                    related_stock_id=related_stock['id'] if related_stock else None
                )
                
                st.success(f"✅ Przepływ został dodany! (ID: {cashflow_id})")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Błąd podczas dodawania przepływu: {str(e)}")

def show_analysis_tab():
    """Wyświetla analizę przepływów pieniężnych."""
    
    st.markdown("### 📈 Analiza przepływów pieniężnych")
    
    # Wybór okresu analizy
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Data od",
            value=date.today() - timedelta(days=365)
        )
    
    with col2:
        end_date = st.date_input(
            "Data do",
            value=date.today()
        )
    
    if start_date > end_date:
        st.error("Data początkowa nie może być późniejsza niż końcowa!")
        return
    
    # Pobierz dane z wybranego okresu
    period_cashflows = CashflowRepository.get_cashflows_by_date_range(start_date, end_date)
    
    if period_cashflows:
        df = pd.DataFrame(period_cashflows)
        
        # Analiza według typu transakcji
        st.markdown("#### 📊 Rozkład według typu transakcji")
        
        type_analysis = df.groupby('transaction_type')['amount_usd'].sum().reset_index()
        type_analysis['transaction_type'] = type_analysis['transaction_type'].map({
            'DEPOSIT': 'Wpłaty',
            'WITHDRAWAL': 'Wypłaty',
            'DIVIDEND': 'Dywidendy',
            'OPTION_PREMIUM': 'Premium opcji',
            'COMMISSION': 'Prowizje',
            'TAX': 'Podatki'
        })
        
        # Wykres kołowy
        fig = px.pie(
            type_analysis,
            values='amount_usd',
            names='transaction_type',
            title=f"Rozkład przepływów ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Analiza trendów czasowych
        st.markdown("#### 📈 Trendy czasowe")
        
        # Grupuj według miesięcy
        df['date'] = pd.to_datetime(df['date'])
        df['year_month'] = df['date'].dt.to_period('M').astype(str)
        
        monthly_trends = df.groupby(['year_month', 'transaction_type'])['amount_usd'].sum().unstack(fill_value=0)
        
        # Wykres liniowy trendów
        fig = go.Figure()
        
        colors = {
            'DEPOSIT': 'green',
            'WITHDRAWAL': 'red',
            'DIVIDEND': 'purple',
            'OPTION_PREMIUM': 'orange',
            'COMMISSION': 'brown',
            'TAX': 'pink'
        }
        
        for transaction_type in monthly_trends.columns:
            fig.add_trace(go.Scatter(
                x=monthly_trends.index,
                y=monthly_trends[transaction_type],
                mode='lines+markers',
                name=transaction_type,
                line=dict(color=colors.get(transaction_type, 'blue'))
            ))
        
        fig.update_layout(
            title="Trendy miesięczne według typu transakcji",
            xaxis_title="Miesiąc",
            yaxis_title="Kwota (USD)",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Statystyki okresu
        st.markdown("#### 📊 Statystyki okresu")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_inflows = df[df['transaction_type'].isin(['DEPOSIT', 'DIVIDEND', 'OPTION_PREMIUM'])]['amount_usd'].sum()
            st.metric("💰 Łączne wpływy", format_currency(total_inflows))
        
        with col2:
            total_outflows = df[df['transaction_type'].isin(['WITHDRAWAL', 'COMMISSION', 'TAX'])]['amount_usd'].sum()
            st.metric("💸 Łączne wypływy", format_currency(total_outflows))
        
        with col3:
            net_flow = total_inflows - total_outflows
            st.metric("📊 Przepływ netto", format_currency(net_flow))
        
        with col4:
            avg_transaction = df['amount_usd'].mean()
            st.metric("📈 Średnia transakcja", format_currency(avg_transaction))
        
        # Top transakcje
        st.markdown("#### 🔝 Największe transakcje")
        
        top_transactions = df.nlargest(5, 'amount_usd')
        
        display_top = top_transactions.copy()
        display_top['date'] = display_top['date'].dt.strftime('%d.%m.%Y')
        display_top['amount_usd'] = display_top['amount_usd'].apply(format_currency)
        display_top['transaction_type'] = display_top['transaction_type'].map({
            'DEPOSIT': '⬇️ Wpłata',
            'WITHDRAWAL': '⬆️ Wypłata',
            'DIVIDEND': '💎 Dywidenda',
            'OPTION_PREMIUM': '🎯 Premium opcji',
            'COMMISSION': '💸 Prowizja',
            'TAX': '🧾 Podatek'
        })
        
        st.dataframe(
            display_top[['date', 'transaction_type', 'amount_usd', 'description']].rename(columns={
                'date': 'Data',
                'transaction_type': 'Typ',
                'amount_usd': 'Kwota',
                'description': 'Opis'
            }),
            use_container_width=True,
            hide_index=True
        )
    
    else:
        st.info(f"Brak przepływów w okresie {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")

def show_history_tab():
    """Wyświetla pełną historię przepływów pieniężnych."""
    
    st.markdown("### 📋 Historia przepływów pieniężnych")
    
    # Filtry
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Filtr typu transakcji
        type_filter = st.selectbox(
            "Typ transakcji",
            ["Wszystkie", "DEPOSIT", "WITHDRAWAL", "DIVIDEND", "OPTION_PREMIUM", "COMMISSION", "TAX"],
            format_func=lambda x: x if x == "Wszystkie" else {
                "DEPOSIT": "⬇️ Wpłaty",
                "WITHDRAWAL": "⬆️ Wypłaty",
                "DIVIDEND": "💎 Dywidendy",
                "OPTION_PREMIUM": "🎯 Premium opcji",
                "COMMISSION": "💸 Prowizje",
                "TAX": "🧾 Podatki"
            }[x]
        )
    
    with col2:
        # Filtr roku
        current_year = datetime.now().year
        year_filter = st.selectbox(
            "Rok",
            ["Wszystkie"] + [str(year) for year in range(current_year, 2020, -1)]
        )
    
    with col3:
        # Liczba rekordów
        limit = st.selectbox(
            "Pokaż ostatnie",
            [25, 50, 100, 250, "Wszystkie"]
        )
    
    # Pobierz i przefiltruj dane
    if type_filter == "Wszystkie":
        cashflows = CashflowRepository.get_all_cashflows()
    else:
        cashflows = CashflowRepository.get_cashflows_by_type(type_filter)
    
    # Filtruj według roku
    if year_filter != "Wszystkie":
        cashflows = [cf for cf in cashflows 
                    if datetime.strptime(cf['date'], '%Y-%m-%d').year == int(year_filter)]
    
    # Ogranicz liczbę rekordów
    if limit != "Wszystkie":
        cashflows = cashflows[:limit]
    
    if cashflows:
        df = pd.DataFrame(cashflows)
        
        # Formatowanie
        display_df = df.copy()
        display_df['date'] = pd.to_datetime(display_df['date']).dt.strftime('%d.%m.%Y')
        display_df['amount_usd'] = display_df.apply(lambda row: 
            format_gain_loss(row['amount_usd'] if row['transaction_type'] in ['DEPOSIT', 'DIVIDEND', 'OPTION_PREMIUM'] 
                           else -row['amount_usd'])[0], axis=1)
        
        # Mapowanie typów
        type_map = {
            'DEPOSIT': '⬇️ Wpłata',
            'WITHDRAWAL': '⬆️ Wypłata',
            'DIVIDEND': '💎 Dywidenda',
            'OPTION_PREMIUM': '🎯 Premium opcji',
            'COMMISSION': '💸 Prowizja',
            'TAX': '🧾 Podatek'
        }
        display_df['transaction_type'] = display_df['transaction_type'].map(type_map)
        
        st.dataframe(
            display_df[[
                'date', 'transaction_type', 'amount_usd', 'description', 'stock_symbol'
            ]].rename(columns={
                'date': 'Data',
                'transaction_type': 'Typ',
                'amount_usd': 'Kwota',
                'description': 'Opis',
                'stock_symbol': 'Akcja'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Statystyki
        st.markdown("#### 📊 Statystyki")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_records = len(cashflows)
            st.metric("📋 Łączne rekordy", total_records)
        
        with col2:
            date_range = f"{min(cf['date'] for cf in cashflows)} - {max(cf['date'] for cf in cashflows)}"
            st.text("📅 Zakres dat:")
            st.caption(date_range)
        
        with col3:
            total_amount = sum(cf['amount_usd'] for cf in cashflows 
                             if cf['transaction_type'] in ['DEPOSIT', 'DIVIDEND', 'OPTION_PREMIUM'])
            st.metric("💰 Suma wpływów", format_currency(total_amount))
        
        with col4:
            avg_amount = sum(cf['amount_usd'] for cf in cashflows) / len(cashflows)
            st.metric("📊 Średnia kwota", format_currency(avg_amount))
    
    else:
        st.info("Brak przepływów spełniających kryteria filtrowania.")

def show_roi_tab():
    """Wyświetla analizę zwrotu z inwestycji (ROI)."""
    
    st.markdown("### 💹 Analiza zwrotu z inwestycji (ROI)")
    
    # Pobierz analizę inwestycji
    investment_analysis = CashflowRepository.get_investment_analysis()
    
    if investment_analysis:
        # Główne metryki ROI
        st.markdown("#### 💰 Kluczowe wskaźniki")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_invested = investment_analysis['net_invested']
            st.metric(
                "💵 Kwota zainwestowana",
                format_currency(total_invested)
            )
        
        with col2:
            current_value = investment_analysis['current_portfolio_value']
            st.metric(
                "📈 Aktualna wartość portfela",
                format_currency(current_value)
            )
        
        with col3:
            total_income = investment_analysis['total_income']
            st.metric(
                "💎 Łączne dochody pasywne",
                format_currency(total_income)
            )
            st.caption(f"Dywidendy: {format_currency(investment_analysis['total_dividends'])}")
            st.caption(f"Opcje: {format_currency(investment_analysis['total_option_premiums'])}")
        
        with col4:
            roi_pct = investment_analysis['roi_percentage']
            roi_color = "green" if roi_pct >= 0 else "red"
            st.metric(
                "📊 ROI całkowity",
                format_percentage(roi_pct),
                delta=f"{roi_pct:+.1f}%"
            )
        
        # Szczegółowy breakdown
        st.markdown("#### 🔍 Szczegółowy breakdown")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**💰 Przepływy pieniężne:**")
            st.text(f"Wpłaty: {format_currency(investment_analysis['total_deposits'])}")
            st.text(f"Wypłaty: {format_currency(investment_analysis['total_withdrawals'])}")
            st.text(f"Netto zainwestowane: {format_currency(investment_analysis['net_invested'])}")
            
            st.markdown("**💎 Dochody pasywne:**")
            st.text(f"Dywidendy: {format_currency(investment_analysis['total_dividends'])}")
            st.text(f"Premium opcji: {format_currency(investment_analysis['total_option_premiums'])}")
            st.text(f"Łączne: {format_currency(investment_analysis['total_income'])}")
        
        with col2:
            st.markdown("**📈 Wartość inwestycji:**")
            st.text(f"Portfel akcji: {format_currency(investment_analysis['current_portfolio_value'])}")
            st.text(f"Wypłaty: {format_currency(investment_analysis['total_withdrawals'])}")
            st.text(f"Dochody: {format_currency(investment_analysis['total_income'])}")
            st.text(f"Łączna wartość: {format_currency(investment_analysis['total_value'])}")
            
            # Oblicz zysk/stratę
            total_gain_loss = investment_analysis['total_value'] - investment_analysis['total_deposits']
            st.markdown("**🎯 Wynik inwestycji:**")
            gain_text, gain_color = format_gain_loss(total_gain_loss)
            st.text(f"Zysk/Strata: {gain_text}")
        
        # Wykres ROI w czasie
        st.markdown("#### 📈 ROI w czasie")
        
        # Pobierz dane do wykresu
        chart_data = CashflowRepository.get_cashflow_chart_data()
        
        if chart_data:
            df = pd.DataFrame(chart_data)
            df['date'] = pd.to_datetime(df['date'])
            
            # Dodaj wartość portfela (uproszczenie - w rzeczywistości trzeba by pobierać historyczne ceny)
            current_portfolio_value = investment_analysis['current_portfolio_value']
            df['total_value'] = df['running_balance'] + current_portfolio_value
            
            # Oblicz ROI
            df['roi_pct'] = ((df['total_value'] - df['running_balance'].where(df['running_balance'] > 0, 1)) / 
                           df['running_balance'].where(df['running_balance'] > 0, 1) * 100)
            
            fig = go.Figure()
            
            # Linia ROI
            fig.add_trace(go.Scatter(
                x=df['date'],
                y=df['roi_pct'],
                mode='lines',
                name='ROI (%)',
                line=dict(color='blue', width=2),
                fill='tonexty'
            ))
            
            fig.update_layout(
                title="Zwrot z inwestycji w czasie",
                xaxis_title="Data",
                yaxis_title="ROI (%)",
                height=400
            )
            
            # Dodaj linię 0%
            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Analiza dochodów pasywnych
        st.markdown("#### 💎 Analiza dochodów pasywnych")
        
        passive_income = investment_analysis['total_income']
        if passive_income > 0 and total_invested > 0:
            passive_yield = (passive_income / total_invested) * 100
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("💰 Łączne dochody pasywne", format_currency(passive_income))
            
            with col2:
                st.metric("📊 Rentowność pasywna", format_percentage(passive_yield))
            
            with col3:
                monthly_passive = passive_income / 12  # Uproszczenie
                st.metric("📅 Średni dochód miesięczny", format_currency(monthly_passive))
        
        # Projekcja przyszłych dochodów
        st.markdown("#### 🔮 Projekcja przyszłych dochodów")
        
        if passive_income > 0:
            # Prosta projekcja na podstawie obecnej rentowności
            annual_yield = (passive_income / total_invested) * 100 if total_invested > 0 else 0
            
            projection_years = st.slider("Projekcja na lata:", 1, 10, 5)
            
            projected_income = []
            for year in range(1, projection_years + 1):
                # Projekcja z założeniem stałej rentowności
                projected_annual = current_value * (annual_yield / 100)
                projected_income.append({
                    'year': f"Rok {year}",
                    'projected_income': projected_annual,
                    'cumulative_income': projected_annual * year
                })
            
            if projected_income:
                proj_df = pd.DataFrame(projected_income)
                
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    x=proj_df['year'],
                    y=proj_df['projected_income'],
                    name='Przewidywany roczny dochód',
                    marker_color='lightblue'
                ))
                
                fig.add_trace(go.Scatter(
                    x=proj_df['year'],
                    y=proj_df['cumulative_income'],
                    mode='lines+markers',
                    name='Skumulowany dochód',
                    line=dict(color='red', width=3),
                    yaxis='y2'
                ))
                
                fig.update_layout(
                    title=f"Projekcja dochodów pasywnych (rentowność {annual_yield:.1f}%)",
                    xaxis_title="Rok",
                    yaxis_title="Roczny dochód (USD)",
                    yaxis2=dict(
                        title="Skumulowany dochód (USD)",
                        overlaying='y',
                        side='right'
                    ),
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Tabela projekcji
                display_proj = proj_df.copy()
                display_proj['projected_income'] = display_proj['projected_income'].apply(format_currency)
                display_proj['cumulative_income'] = display_proj['cumulative_income'].apply(format_currency)
                
                st.dataframe(
                    display_proj.rename(columns={
                        'year': 'Rok',
                        'projected_income': 'Przewidywany dochód roczny',
                        'cumulative_income': 'Skumulowany dochód'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
        
        # Przeliczenie na PLN
        current_usd_rate = nbp_service.get_current_usd_rate()
        if current_usd_rate:
            st.markdown("#### 🇵🇱 Wartości w PLN")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                invested_pln = total_invested * current_usd_rate
                st.metric(
                    "💵 Zainwestowane (PLN)",
                    format_currency(invested_pln, "PLN")
                )
            
            with col2:
                value_pln = investment_analysis['total_value'] * current_usd_rate
                st.metric(
                    "💰 Aktualna wartość (PLN)",
                    format_currency(value_pln, "PLN")
                )
            
            with col3:
                income_pln = total_income * current_usd_rate
                st.metric(
                    "💎 Dochody pasywne (PLN)",
                    format_currency(income_pln, "PLN")
                )
        
        # Porównanie z innymi inwestycjami
        st.markdown("#### 📊 Porównanie z innymi inwestycjami")
        
        st.info(f"""
        **🎯 Twoja rentowność: {roi_pct:.1f}% ({annual_yield:.1f}% rocznie)**
        
        **Porównanie z rynkiem:**
        - 🏦 Lokata bankowa (2%): {2 * projection_years:.0f}% za {projection_years} lat
        - 📈 S&P 500 (historycznie ~10%): {10 * projection_years:.0f}% za {projection_years} lat
        - 🏠 Obligacje (3-4%): {3.5 * projection_years:.0f}% za {projection_years} lat
        - 💰 Inflacja (~3%): -{3 * projection_years:.0f}% siły nabywczej za {projection_years} lat
        
        💡 **Wskazówki:**
        - ROI powyżej 7% rocznie jest bardzo dobrym wynikiem
        - Dochody pasywne powyżej 4% to stabilna rentowność
        - Diversyfikacja zmniejsza ryzyko
        """)
    
    else:
        st.info("Brak danych do analizy ROI. Dodaj wpłaty i transakcje.")
        
        # Kalkulator potencjalnego ROI
        st.markdown("#### 🧮 Kalkulator potencjalnego ROI")
        
        with st.expander("Oblicz potencjalny zwrot z inwestycji"):
            col1, col2 = st.columns(2)
            
            with col1:
                initial_investment = st.number_input(
                    "Planowana inwestycja (USD)",
                    min_value=100.0,
                    value=10000.0,
                    step=100.0
                )
                
                expected_annual_return = st.slider(
                    "Oczekiwany zwrot roczny (%)",
                    min_value=1.0,
                    max_value=20.0,
                    value=8.0,
                    step=0.1
                )
            
            with col2:
                investment_years = st.slider(
                    "Okres inwestycji (lata)",
                    min_value=1,
                    max_value=30,
                    value=10
                )
                
                monthly_contribution = st.number_input(
                    "Miesięczna dopłata (USD)",
                    min_value=0.0,
                    value=500.0,
                    step=50.0
                )
            
            if st.button("🧮 Oblicz projekcję"):
                # Oblicz złożone oprocentowanie
                annual_rate = expected_annual_return / 100
                monthly_rate = annual_rate / 12
                months = investment_years * 12
                
                # Wartość początkowej inwestycji
                future_value_initial = initial_investment * (1 + annual_rate) ** investment_years
                
                # Wartość miesięcznych dopłat (annuity)
                if monthly_contribution > 0:
                    future_value_contributions = monthly_contribution * (((1 + monthly_rate) ** months - 1) / monthly_rate)
                else:
                    future_value_contributions = 0
                
                total_future_value = future_value_initial + future_value_contributions
                total_invested = initial_investment + (monthly_contribution * months)
                total_return = total_future_value - total_invested
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("💰 Łącznie zainwestowane", format_currency(total_invested))
                
                with col2:
                    st.metric("📈 Przyszła wartość", format_currency(total_future_value))
                
                with col3:
                    st.metric("🎯 Zysk", format_currency(total_return))
                
                # Wykres projekcji
                years_data = []
                for year in range(1, investment_years + 1):
                    value_initial = initial_investment * (1 + annual_rate) ** year
                    months_so_far = year * 12
                    if monthly_contribution > 0:
                        value_contributions = monthly_contribution * (((1 + monthly_rate) ** months_so_far - 1) / monthly_rate)
                    else:
                        value_contributions = 0
                    
                    total_value = value_initial + value_contributions
                    invested_so_far = initial_investment + (monthly_contribution * months_so_far)
                    
                    years_data.append({
                        'year': year,
                        'total_value': total_value,
                        'total_invested': invested_so_far,
                        'profit': total_value - invested_so_far
                    })
                
                proj_df = pd.DataFrame(years_data)
                
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=proj_df['year'],
                    y=proj_df['total_invested'],
                    mode='lines+markers',
                    name='Łącznie zainwestowane',
                    line=dict(color='blue')
                ))
                
                fig.add_trace(go.Scatter(
                    x=proj_df['year'],
                    y=proj_df['total_value'],
                    mode='lines+markers',
                    name='Wartość portfela',
                    line=dict(color='green')
                ))
                
                fig.add_trace(go.Scatter(
                    x=proj_df['year'],
                    y=proj_df['profit'],
                    mode='lines+markers',
                    name='Zysk',
                    line=dict(color='orange'),
                    fill='tonexty'
                ))
                
                fig.update_layout(
                    title="Projekcja wzrostu inwestycji",
                    xaxis_title="Rok",
                    yaxis_title="Wartość (USD)",
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)