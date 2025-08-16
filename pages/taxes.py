import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import plotly.express as px
import plotly.graph_objects as go

from repos.stock_repo import StockRepository
from repos.dividends_repo import DividendsRepository
from repos.options_repo import OptionsRepository
from services.nbp import nbp_service
from utils.tax import (
    calculate_capital_gains_tax, calculate_dividend_tax, 
    calculate_option_premium_tax, get_tax_year_summary,
    estimate_quarterly_tax_payment
)
from utils.formatting import (
    format_currency, format_percentage, format_polish_date
)

def show():
    """Wyświetla stronę zarządzania podatkami."""
    
    st.markdown("## 🧾 Rozliczenia podatkowe")
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Przegląd", "💰 Zyski kapitałowe", "💎 Dywidendy", "🎯 Opcje", "📋 Zestawienie roczne"
    ])
    
    with tab1:
        show_overview_tab()
    
    with tab2:
        show_capital_gains_tab()
    
    with tab3:
        show_dividends_tax_tab()
    
    with tab4:
        show_options_tax_tab()
    
    with tab5:
        show_annual_summary_tab()

def show_overview_tab():
    """Wyświetla przegląd podatkowy."""
    
    st.markdown("### 📊 Przegląd podatkowy")
    
    # Wybór roku podatkowego
    current_year = datetime.now().year
    tax_year = st.selectbox(
        "Rok podatkowy",
        options=list(range(current_year, 2020, -1)),
        index=0
    )
    
    # Informacja o stawkach podatkowych
    st.info("""
    **🇵🇱 Stawki podatkowe w Polsce:**
    - Podatek od zysków kapitałowych: **19%**
    - Podatek od dywidend: **19%**
    - Podatek u źródła (USA): **15%** (można zaliczyć)
    """)
    
    # Szybkie podsumowanie
    try:
        # Zyski z akcji
        capital_gains = calculate_year_capital_gains(tax_year)
        
        # Dywidendy
        dividends_summary = DividendsRepository.get_tax_summary_for_dividends(tax_year)
        
        # Opcje
        options_summary = OptionsRepository.get_options_for_tax_calculation(tax_year)
        
        # Metryki główne
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_capital_gains_pln = sum(gain.get('gain_pln', 0) for gain in capital_gains)
            st.metric(
                "💰 Zyski kapitałowe",
                format_currency(total_capital_gains_pln, "PLN")
            )
        
        with col2:
            total_dividends_pln = 0
            if dividends_summary:
                for div in dividends_summary:
                    # Uproszczone przeliczenie - w rzeczywistości należy użyć kursów z dat wypłat
                    avg_rate = 4.0  # Przykładowy kurs
                    total_dividends_pln += div['total_dividends_usd'] * avg_rate
            
            st.metric(
                "💎 Dywidendy",
                format_currency(total_dividends_pln, "PLN")
            )
        
        with col3:
            total_options_pln = 0
            if options_summary:
                for opt in options_summary:
                    # Uproszczone przeliczenie
                    avg_rate = 4.0
                    total_options_pln += opt['premium_received'] * opt['quantity'] * avg_rate
            
            st.metric(
                "🎯 Premium opcji",
                format_currency(total_options_pln, "PLN")
            )
        
        with col4:
            # Szacunkowy podatek należny
            total_tax_base = total_capital_gains_pln + total_dividends_pln + total_options_pln
            estimated_tax = total_tax_base * 0.19
            
            st.metric(
                "🧾 Szacunkowy podatek",
                format_currency(estimated_tax, "PLN")
            )
        
        # Ostrzeżenia i uwagi
        if estimated_tax > 0:
            st.warning(f"""
            ⚠️ **Uwaga podatkowa dla {tax_year}:**
            
            Szacunkowy podatek do zapłaty: **{format_currency(estimated_tax, "PLN")}**
            
            Pamiętaj o:
            - Składaniu zeznania podatkowego do 30 kwietnia {tax_year + 1} roku
            - Wpłacie podatku do 31 maja {tax_year + 1} roku
            - Możliwości płacenia zaliczek kwartalnych
            """)
        
        # Kalkulator zaliczki kwartalnej
        st.markdown("#### 💳 Kalkulator zaliczki kwartalnej")
        
        col1, col2 = st.columns(2)
        
        with col1:
            current_gains_usd = st.number_input(
                "Aktualne zyski w USD",
                min_value=0.0,
                value=0.0,
                step=100.0
            )
        
        with col2:
            if st.button("🧮 Oblicz zaliczkę"):
                if current_gains_usd > 0:
                    quarterly_tax = estimate_quarterly_tax_payment(current_gains_usd, date.today())
                    st.success(f"Szacunkowa zaliczka kwartalna: {format_currency(quarterly_tax, 'PLN')}")
                else:
                    st.info("Wprowadź kwotę zysków do obliczenia zaliczki")
        
        # Harmonogram dat podatkowych
        st.markdown("#### 📅 Ważne daty podatkowe")
        
        tax_dates = [
            ("31 stycznia", "Zaliczka za Q4 poprzedniego roku"),
            ("30 kwietnia", "Zaliczka za Q1 + zeznanie roczne"),
            ("31 maja", "Wpłata podatku rocznego"),
            ("31 lipca", "Zaliczka za Q2"),
            ("31 października", "Zaliczka za Q3")
        ]
        
        for date_str, description in tax_dates:
            st.text(f"📅 {date_str}: {description}")
        
    except Exception as e:
        st.error(f"Błąd podczas pobierania danych podatkowych: {e}")

def show_capital_gains_tab():
    """Wyświetla analizę zysków kapitałowych."""
    
    st.markdown("### 💰 Zyski kapitałowe z akcji")
    
    # Wybór roku
    current_year = datetime.now().year
    tax_year = st.selectbox(
        "Rok podatkowy",
        options=list(range(current_year, 2020, -1)),
        index=0,
        key="capital_gains_year"
    )
    
    st.info("""
    **ℹ️ Informacje o podatkach od zysków kapitałowych:**
    
    - Stawka podatku: **19%** od zysku
    - Koszty uzyskania przychodu: cena zakupu + prowizje
    - Kursy NBP: z dnia transakcji sprzedaży
    - Metoda FIFO: pierwsze kupione, pierwsze sprzedane
    """)
    
    # Pobierz transakcje sprzedaży
    try:
        sales_transactions = StockRepository.get_transactions_for_tax_calculation(tax_year)
        sales_only = [t for t in sales_transactions if t['transaction_type'] == 'SELL']
        
        if sales_only:
            # Oblicz zyski/straty dla każdej sprzedaży
            capital_gains_data = []
            
            for sale in sales_only:
                # W rzeczywistej implementacji tutaj by była logika FIFO
                # Na potrzeby przykładu upraszczamy
                
                symbol = sale['symbol']
                quantity = sale['quantity']
                sale_price = sale['price_usd']
                sale_date = datetime.strptime(sale['transaction_date'], '%Y-%m-%d').date()
                
                # Pobierz średnią cenę akcji (uproszczenie - w rzeczywistości FIFO)
                stock = StockRepository.get_stock_by_symbol(symbol)
                if stock:
                    avg_cost = stock['avg_price_usd']
                    
                    # Oblicz zysk/stratę
                    proceeds = quantity * sale_price
                    cost_basis = quantity * avg_cost
                    gain_loss_usd = proceeds - cost_basis
                    
                    # Pobierz kurs NBP
                    try:
                        usd_rate = nbp_service.get_usd_pln_rate(sale_date)
                        if usd_rate:
                            gain_loss_pln = gain_loss_usd * usd_rate
                            tax_pln = max(0, gain_loss_pln * 0.19)
                            
                            capital_gains_data.append({
                                'symbol': symbol,
                                'sale_date': sale_date,
                                'quantity': quantity,
                                'sale_price_usd': sale_price,
                                'avg_cost_usd': avg_cost,
                                'proceeds_usd': proceeds,
                                'cost_basis_usd': cost_basis,
                                'gain_loss_usd': gain_loss_usd,
                                'usd_rate': usd_rate,
                                'gain_loss_pln': gain_loss_pln,
                                'tax_pln': tax_pln
                            })
                    except Exception as e:
                        st.error(f"Błąd kursu NBP dla {sale_date}: {e}")
            
            if capital_gains_data:
                df = pd.DataFrame(capital_gains_data)
                
                # Podsumowanie
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_proceeds = df['proceeds_usd'].sum()
                    st.metric("💰 Łączne wpływy", format_currency(total_proceeds))
                
                with col2:
                    total_cost = df['cost_basis_usd'].sum()
                    st.metric("💵 Łączne koszty", format_currency(total_cost))
                
                with col3:
                    total_gain_pln = df['gain_loss_pln'].sum()
                    gain_text = format_currency(total_gain_pln, "PLN")
                    st.metric("📈 Zysk/Strata", gain_text)
                
                with col4:
                    total_tax = df['tax_pln'].sum()
                    st.metric("🧾 Podatek należny", format_currency(total_tax, "PLN"))
                
                # Szczegółowa tabela
                st.markdown("#### 📋 Szczegółowe zestawienie sprzedaży")
                
                display_df = df.copy()
                display_df['sale_date'] = display_df['sale_date'].apply(format_polish_date)
                display_df['sale_price_usd'] = display_df['sale_price_usd'].apply(format_currency)
                display_df['avg_cost_usd'] = display_df['avg_cost_usd'].apply(format_currency)
                display_df['proceeds_usd'] = display_df['proceeds_usd'].apply(format_currency)
                display_df['cost_basis_usd'] = display_df['cost_basis_usd'].apply(format_currency)
                display_df['gain_loss_usd'] = display_df['gain_loss_usd'].apply(format_currency)
                display_df['usd_rate'] = display_df['usd_rate'].apply(lambda x: f"{x:.4f}")
                display_df['gain_loss_pln'] = display_df['gain_loss_pln'].apply(lambda x: format_currency(x, "PLN"))
                display_df['tax_pln'] = display_df['tax_pln'].apply(lambda x: format_currency(x, "PLN"))
                
                st.dataframe(
                    display_df[[
                        'symbol', 'sale_date', 'quantity', 'sale_price_usd', 'avg_cost_usd',
                        'gain_loss_usd', 'usd_rate', 'gain_loss_pln', 'tax_pln'
                    ]].rename(columns={
                        'symbol': 'Symbol',
                        'sale_date': 'Data sprzedaży',
                        'quantity': 'Ilość',
                        'sale_price_usd': 'Cena sprzedaży',
                        'avg_cost_usd': 'Średni koszt',
                        'gain_loss_usd': 'Zysk/Strata USD',
                        'usd_rate': 'Kurs NBP',
                        'gain_loss_pln': 'Zysk/Strata PLN',
                        'tax_pln': 'Podatek PLN'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Wykres zysków/strat
                fig = px.bar(
                    df,
                    x='symbol',
                    y='gain_loss_pln',
                    color='gain_loss_pln',
                    color_continuous_scale=['red', 'gray', 'green'],
                    title=f"Zyski/Straty kapitałowe {tax_year}",
                    labels={'gain_loss_pln': 'Zysk/Strata (PLN)', 'symbol': 'Symbol akcji'}
                )
                
                st.plotly_chart(fig, use_container_width=True)
        
        else:
            st.info(f"Brak transakcji sprzedaży w {tax_year} roku.")
    
    except Exception as e:
        st.error(f"Błąd podczas obliczania zysków kapitałowych: {e}")

def show_dividends_tax_tab():
    """Wyświetla analizę podatkową dywidend."""
    
    st.markdown("### 💎 Podatek od dywidend")
    
    # Wybór roku
    current_year = datetime.now().year
    tax_year = st.selectbox(
        "Rok podatkowy",
        options=list(range(current_year, 2020, -1)),
        index=0,
        key="dividends_tax_year"
    )
    
    st.info("""
    **ℹ️ Informacje o podatkach od dywidend:**
    
    - Stawka podatku w Polsce: **19%**
    - Podatek u źródła (USA): **15%** (można zaliczyć)
    - Kursy NBP: z dnia wypłaty dywidendy
    - Zaliczenie: podatek USA można zaliczyć na podatek polski
    """)
    
    # Pobierz dywidendy za dany rok
    dividends_summary = DividendsRepository.get_tax_summary_for_dividends(tax_year)
    
    if dividends_summary:
        # Oblicz szczegółowe dane podatkowe
        tax_data = []
        total_dividend_pln = 0
        total_us_tax_pln = 0
        total_pl_tax_due = 0
        total_pl_tax_to_pay = 0
        
        for dividend in dividends_summary:
            symbol = dividend['symbol']
            dividend_usd = dividend['total_dividends_usd']
            us_tax_usd = dividend['total_tax_withheld_usd']
            payment_count = dividend['payment_count']
            
            # Pobierz daty wypłat
            payment_dates = dividend['payment_dates'].split(',') if dividend['payment_dates'] else []
            
            # Oblicz średni kurs NBP dla tego okresu (uproszczenie)
            avg_rate = 4.0  # W rzeczywistej aplikacji pobierz rzeczywiste kursy
            
            try:
                if payment_dates:
                    # Użyj kursu z pierwszej daty wypłaty jako przykład
                    first_date = datetime.strptime(payment_dates[0].strip(), '%Y-%m-%d').date()
                    avg_rate = nbp_service.get_usd_pln_rate(first_date) or 4.0
            except:
                pass
            
            # Przelicz na PLN
            dividend_pln = dividend_usd * avg_rate
            us_tax_pln = us_tax_usd * avg_rate
            
            # Oblicz podatek należny w Polsce
            pl_tax_due = dividend_pln * 0.19
            pl_tax_to_pay = max(0, pl_tax_due - us_tax_pln)
            
            total_dividend_pln += dividend_pln
            total_us_tax_pln += us_tax_pln
            total_pl_tax_due += pl_tax_due
            total_pl_tax_to_pay += pl_tax_to_pay
            
            tax_data.append({
                'symbol': symbol,
                'dividend_usd': dividend_usd,
                'us_tax_usd': us_tax_usd,
                'avg_rate': avg_rate,
                'dividend_pln': dividend_pln,
                'us_tax_pln': us_tax_pln,
                'pl_tax_due': pl_tax_due,
                'pl_tax_to_pay': pl_tax_to_pay,
                'payment_count': payment_count
            })
        
        # Podsumowanie główne
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "💰 Dywidendy brutto",
                format_currency(total_dividend_pln, "PLN")
            )
        
        with col2:
            st.metric(
                "🇺🇸 Podatek u źródła",
                format_currency(total_us_tax_pln, "PLN")
            )
        
        with col3:
            st.metric(
                "🇵🇱 Podatek należny (19%)",
                format_currency(total_pl_tax_due, "PLN")
            )
        
        with col4:
            color = "green" if total_pl_tax_to_pay == 0 else "red"
            st.metric(
                "💸 Do dopłaty w Polsce",
                format_currency(total_pl_tax_to_pay, "PLN")
            )
            if total_pl_tax_to_pay > 0:
                st.caption("🔴 Wymagana dopłata")
            else:
                st.caption("🟢 Brak dopłaty")
        
        # Szczegółowa tabela
        st.markdown("#### 📋 Szczegółowe zestawienie dywidend")
        
        if tax_data:
            df = pd.DataFrame(tax_data)
            
            # Formatowanie
            display_df = df.copy()
            display_df['dividend_usd'] = display_df['dividend_usd'].apply(format_currency)
            display_df['us_tax_usd'] = display_df['us_tax_usd'].apply(format_currency)
            display_df['avg_rate'] = display_df['avg_rate'].apply(lambda x: f"{x:.4f}")
            display_df['dividend_pln'] = display_df['dividend_pln'].apply(lambda x: format_currency(x, "PLN"))
            display_df['us_tax_pln'] = display_df['us_tax_pln'].apply(lambda x: format_currency(x, "PLN"))
            display_df['pl_tax_due'] = display_df['pl_tax_due'].apply(lambda x: format_currency(x, "PLN"))
            display_df['pl_tax_to_pay'] = display_df['pl_tax_to_pay'].apply(lambda x: format_currency(x, "PLN"))
            
            st.dataframe(
                display_df[[
                    'symbol', 'payment_count', 'dividend_usd', 'us_tax_usd', 'avg_rate',
                    'dividend_pln', 'us_tax_pln', 'pl_tax_due', 'pl_tax_to_pay'
                ]].rename(columns={
                    'symbol': 'Symbol',
                    'payment_count': 'Wypłaty',
                    'dividend_usd': 'Dywidenda USD',
                    'us_tax_usd': 'Podatek USA USD',
                    'avg_rate': 'Kurs NBP',
                    'dividend_pln': 'Dywidenda PLN',
                    'us_tax_pln': 'Podatek USA PLN',
                    'pl_tax_due': 'Podatek należny PLN',
                    'pl_tax_to_pay': 'Do dopłaty PLN'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Wykres porównawczy podatków
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=df['symbol'],
                y=df['us_tax_pln'],
                name='Podatek u źródła (USA)',
                marker_color='blue'
            ))
            
            fig.add_trace(go.Bar(
                x=df['symbol'],
                y=df['pl_tax_to_pay'],
                name='Do dopłaty w Polsce',
                marker_color='red'
            ))
            
            fig.update_layout(
                title=f"Podatki od dywidend {tax_year}",
                xaxis_title="Symbol akcji",
                yaxis_title="Podatek (PLN)",
                barmode='stack'
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.info(f"Brak dywidend w {tax_year} roku.")

def show_options_tax_tab():
    """Wyświetla analizę podatkową opcji."""
    
    st.markdown("### 🎯 Podatek od opcji")
    
    # Wybór roku
    current_year = datetime.now().year
    tax_year = st.selectbox(
        "Rok podatkowy",
        options=list(range(current_year, 2020, -1)),
        index=0,
        key="options_tax_year"
    )
    
    st.info("""
    **ℹ️ Informacje o podatkach od opcji:**
    
    - Stawka podatku: **19%** od premium
    - Moment opodatkowania: otrzymanie premium
    - Kursy NBP: z dnia otrzymania premium
    - Opcje przydzielone: mogą generować dodatkowe skutki podatkowe
    """)
    
    # Pobierz opcje za dany rok
    options_data = OptionsRepository.get_options_for_tax_calculation(tax_year)
    
    if options_data:
        # Oblicz podatki od opcji
        tax_calculations = []
        total_premium_pln = 0
        total_tax_pln = 0
        
        for option in options_data:
            symbol = option['symbol']
            premium_per_contract = option['premium_received']
            quantity = option['quantity']
            open_date = datetime.strptime(option['open_date'], '%Y-%m-%d').date()
            status = option['status']
            
            # Całkowite premium
            total_premium_usd = premium_per_contract * quantity
            
            # Pobierz kurs NBP
            try:
                usd_rate = nbp_service.get_usd_pln_rate(open_date)
                if not usd_rate:
                    usd_rate = 4.0  # Wartość domyślna
            except:
                usd_rate = 4.0
            
            # Przelicz na PLN
            premium_pln = total_premium_usd * usd_rate
            tax_pln = premium_pln * 0.19
            
            total_premium_pln += premium_pln
            total_tax_pln += tax_pln
            
            tax_calculations.append({
                'symbol': symbol,
                'open_date': open_date,
                'status': status,
                'quantity': quantity,
                'premium_per_contract': premium_per_contract,
                'total_premium_usd': total_premium_usd,
                'usd_rate': usd_rate,
                'premium_pln': premium_pln,
                'tax_pln': tax_pln
            })
        
        # Podsumowanie
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_contracts = len(options_data)
            st.metric("📋 Kontrakty", total_contracts)
        
        with col2:
            total_premium_usd = sum(opt['premium_received'] * opt['quantity'] for opt in options_data)
            st.metric("💰 Premium USD", format_currency(total_premium_usd))
        
        with col3:
            st.metric("💎 Premium PLN", format_currency(total_premium_pln, "PLN"))
        
        with col4:
            st.metric("🧾 Podatek należny", format_currency(total_tax_pln, "PLN"))
        
        # Szczegółowa tabela
        st.markdown("#### 📋 Szczegółowe zestawienie opcji")
        
        df = pd.DataFrame(tax_calculations)
        
        # Formatowanie
        display_df = df.copy()
        display_df['open_date'] = display_df['open_date'].apply(format_polish_date)
        display_df['premium_per_contract'] = display_df['premium_per_contract'].apply(format_currency)
        display_df['total_premium_usd'] = display_df['total_premium_usd'].apply(format_currency)
        display_df['usd_rate'] = display_df['usd_rate'].apply(lambda x: f"{x:.4f}")
        display_df['premium_pln'] = display_df['premium_pln'].apply(lambda x: format_currency(x, "PLN"))
        display_df['tax_pln'] = display_df['tax_pln'].apply(lambda x: format_currency(x, "PLN"))
        
        # Mapowanie statusów
        status_map = {
            'OPEN': '🟢 Aktywna',
            'EXPIRED': '🟡 Wygasła',
            'ASSIGNED': '🔴 Przydzielona',
            'CLOSED': '🔵 Zamknięta'
        }
        display_df['status'] = display_df['status'].map(status_map)
        
        st.dataframe(
            display_df[[
                'symbol', 'open_date', 'status', 'quantity', 'premium_per_contract',
                'total_premium_usd', 'usd_rate', 'premium_pln', 'tax_pln'
            ]].rename(columns={
                'symbol': 'Symbol',
                'open_date': 'Data otwarcia',
                'status': 'Status',
                'quantity': 'Ilość',
                'premium_per_contract': 'Premium/kontrakt',
                'total_premium_usd': 'Premium USD',
                'usd_rate': 'Kurs NBP',
                'premium_pln': 'Premium PLN',
                'tax_pln': 'Podatek PLN'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Analiza według statusu
        st.markdown("#### 📊 Analiza według statusu opcji")
        
        status_analysis = df.groupby('status').agg({
            'quantity': 'sum',
            'premium_pln': 'sum',
            'tax_pln': 'sum'
        }).reset_index()
        
        status_analysis['status'] = status_analysis['status'].map(status_map)
        
        fig = px.pie(
            status_analysis,
            values='premium_pln',
            names='status',
            title="Rozkład premium według statusu opcji"
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.info(f"Brak opcji w {tax_year} roku.")

def show_annual_summary_tab():
    """Wyświetla roczne zestawienie podatkowe."""
    
    st.markdown("### 📋 Roczne zestawienie podatkowe")
    
    # Wybór roku
    current_year = datetime.now().year
    tax_year = st.selectbox(
        "Rok podatkowy",
        options=list(range(current_year, 2020, -1)),
        index=0,
        key="annual_summary_year"
    )
    
    st.info(f"""
    **📋 Zestawienie podatkowe za {tax_year} rok**
    
    Dokument przygotowany zgodnie z polskimi przepisami podatkowymi.
    Zawiera wszystkie pozycje podlegające opodatkowaniu podatkiem od zysków kapitałowych.
    """)
    
    try:
        # Zbierz wszystkie dane podatkowe
        
        # 1. Zyski kapitałowe
        capital_gains = calculate_year_capital_gains(tax_year)
        
        # 2. Dywidendy
        dividends_summary = DividendsRepository.get_tax_summary_for_dividends(tax_year)
        
        # 3. Opcje
        options_summary = OptionsRepository.get_options_for_tax_calculation(tax_year)
        
        # Podsumowanie globalne
        st.markdown("#### 💰 Podsumowanie globalne")
        
        total_capital_gains_pln = 0
        total_dividends_pln = 0
        total_dividends_tax_credit = 0
        total_options_pln = 0
        
        # Oblicz zyski kapitałowe
        if capital_gains:
            total_capital_gains_pln = sum(gain.get('gain_pln', 0) for gain in capital_gains if gain.get('gain_pln', 0) > 0)
        
        # Oblicz dywidendy (uproszczone)
        if dividends_summary:
            for div in dividends_summary:
                avg_rate = 4.0  # W rzeczywistej aplikacji użyj rzeczywistych kursów
                total_dividends_pln += div['total_dividends_usd'] * avg_rate
                total_dividends_tax_credit += div['total_tax_withheld_usd'] * avg_rate
        
        # Oblicz opcje (uproszczone)
        if options_summary:
            for opt in options_summary:
                avg_rate = 4.0
                total_options_pln += opt['premium_received'] * opt['quantity'] * avg_rate
        
        # Suma podstawy opodatkowania
        total_tax_base = total_capital_gains_pln + total_dividends_pln + total_options_pln
        
        # Podatek należny
        total_tax_due = total_tax_base * 0.19
        
        # Podatek do zapłaty (po zaliczeniu podatku u źródła)
        total_tax_to_pay = max(0, total_tax_due - total_dividends_tax_credit)
        
        # Wyświetl podsumowanie
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "💰 Podstawa opodatkowania",
                format_currency(total_tax_base, "PLN")
            )
            
            st.markdown("**Składniki:**")
            st.text(f"• Zyski kapitałowe: {format_currency(total_capital_gains_pln, 'PLN')}")
            st.text(f"• Dywidendy: {format_currency(total_dividends_pln, 'PLN')}")
            st.text(f"• Premium opcji: {format_currency(total_options_pln, 'PLN')}")
        
        with col2:
            st.metric(
                "🧾 Podatek należny (19%)",
                format_currency(total_tax_due, "PLN")
            )
            
            st.metric(
                "🇺🇸 Zaliczenie z USA",
                format_currency(total_dividends_tax_credit, "PLN")
            )
        
        with col3:
            st.metric(
                "💸 Podatek do zapłaty",
                format_currency(total_tax_to_pay, "PLN")
            )
            
            if total_tax_to_pay > 0:
                st.error("🔴 Wymagana wpłata")
            else:
                st.success("🟢 Brak wpłaty")
        
        # Szczegółowy breakdown
        st.markdown("#### 📊 Szczegółowy breakdown")
        
        breakdown_data = []
        
        # Dodaj zyski kapitałowe
        if capital_gains:
            for gain in capital_gains:
                if gain.get('gain_pln', 0) > 0:
                    breakdown_data.append({
                        'Kategoria': 'Zyski kapitałowe',
                        'Symbol': gain.get('symbol', 'N/A'),
                        'Data': gain.get('date', 'N/A'),
                        'Kwota PLN': gain.get('gain_pln', 0),
                        'Podatek PLN': gain.get('gain_pln', 0) * 0.19
                    })
        
        # Dodaj dywidendy (uproszczone)
        if dividends_summary:
            for div in dividends_summary:
                avg_rate = 4.0
                dividend_pln = div['total_dividends_usd'] * avg_rate
                breakdown_data.append({
                    'Kategoria': 'Dywidendy',
                    'Symbol': div['symbol'],
                    'Data': 'Różne daty',
                    'Kwota PLN': dividend_pln,
                    'Podatek PLN': dividend_pln * 0.19
                })
        
        # Dodaj opcje (uproszczone)
        if options_summary:
            for opt in options_summary:
                avg_rate = 4.0
                premium_pln = opt['premium_received'] * opt['quantity'] * avg_rate
                breakdown_data.append({
                    'Kategoria': 'Premium opcji',
                    'Symbol': opt['symbol'],
                    'Data': opt['open_date'],
                    'Kwota PLN': premium_pln,
                    'Podatek PLN': premium_pln * 0.19
                })
        
        if breakdown_data:
            breakdown_df = pd.DataFrame(breakdown_data)
            
            # Formatowanie
            breakdown_df['Kwota PLN'] = breakdown_df['Kwota PLN'].apply(lambda x: format_currency(x, "PLN"))
            breakdown_df['Podatek PLN'] = breakdown_df['Podatek PLN'].apply(lambda x: format_currency(x, "PLN"))
            
            st.dataframe(breakdown_df, use_container_width=True, hide_index=True)
        
        # Instrukcje rozliczenia
        st.markdown("#### 📝 Instrukcje rozliczenia")
        
        st.success(f"""
        **Kroki do rozliczenia podatku za {tax_year}:**
        
        1. **Przygotuj dokumenty:**
           - Zestawienia transakcji z brokera
           - Potwierdzenia wypłat dywidend
           - Kursy NBP z dat transakcji
        
        2. **Wypełnij PIT-38:**
           - Podstawa opodatkowania: {format_currency(total_tax_base, "PLN")}
           - Podatek należny: {format_currency(total_tax_due, "PLN")}
           - Zaliczenie z USA: {format_currency(total_dividends_tax_credit, "PLN")}
           - Do dopłaty: {format_currency(total_tax_to_pay, "PLN")}
        
        3. **Terminy:**
           - Złożenie zeznania: do 30 kwietnia {tax_year + 1}
           - Wpłata podatku: do 31 maja {tax_year + 1}
        
        4. **Zaliczenie podatku u źródła:**
           - Dołącz zaświadczenie o potrąconym podatku w USA
           - Podatek potrącony w USA można zaliczyć na podatek polski
        
        ⚠️ **Uwaga:** To tylko szacunkowe obliczenia. Skonsultuj się z doradcą podatkowym!
        """)
        
        # Przycisk do eksportu
        if st.button("📄 Generuj raport PDF"):
            st.info("Funkcja generowania raportu PDF będzie dostępna w przyszłej wersji.")
    
    except Exception as e:
        st.error(f"Błąd podczas generowania zestawienia: {e}")

def calculate_year_capital_gains(year):
    """Oblicza zyski kapitałowe za dany rok (uproszczona implementacja)."""
    try:
        sales_transactions = StockRepository.get_transactions_for_tax_calculation(year)
        sales_only = [t for t in sales_transactions if t['transaction_type'] == 'SELL']
        
        gains = []
        for sale in sales_only:
            # Uproszczona kalkulacja - w rzeczywistości trzeba użyć FIFO
            symbol = sale['symbol']
            quantity = sale['quantity']
            sale_price = sale['price_usd']
            sale_date = sale['transaction_date']
            
            # Pobierz średnią cenę (uproszczenie)
            stock = StockRepository.get_stock_by_symbol(symbol)
            if stock:
                avg_cost = stock['avg_price_usd']
                gain_usd = (sale_price - avg_cost) * quantity
                
                if gain_usd > 0:  # Tylko zyski podlegają opodatkowaniu
                    try:
                        date_obj = datetime.strptime(sale_date, '%Y-%m-%d').date()
                        usd_rate = nbp_service.get_usd_pln_rate(date_obj)
                        if usd_rate:
                            gain_pln = gain_usd * usd_rate
                            gains.append({
                                'symbol': symbol,
                                'date': sale_date,
                                'gain_usd': gain_usd,
                                'gain_pln': gain_pln,
                                'usd_rate': usd_rate
                            })
                    except:
                        pass
        
        return gains
    
    except Exception:
        return []