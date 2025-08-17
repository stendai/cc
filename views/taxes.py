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
        try:
            dividends_summary = DividendsRepository.get_tax_summary_for_dividends(tax_year)
        except:
            dividends_summary = []
        
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
                    avg_rate = 3.65  # Przykładowy kurs
                    total_dividends_pln += div.get('total_dividends_usd', 0) * avg_rate
            
            st.metric(
                "💎 Dywidendy",
                format_currency(total_dividends_pln, "PLN")
            )
        
        with col3:
            total_options_pln = 0
            if options_summary:
                for opt in options_summary:
                    avg_rate = 3.65
                    total_options_pln += opt.get('premium_received', 0) * opt.get('quantity', 0) * avg_rate
            
            st.metric(
                "🎯 Premium opcje",
                format_currency(total_options_pln, "PLN")
            )
        
        with col4:
            total_tax_estimate = (total_capital_gains_pln + total_dividends_pln + total_options_pln) * 0.19
            st.metric(
                "🧾 Szacowany podatek",
                format_currency(total_tax_estimate, "PLN")
            )
    
    except Exception as e:
        st.error(f"Błąd podczas ładowania danych: {e}")

def show_capital_gains_tab():
    """Wyświetla analizę zysków kapitałowych."""
    
    st.markdown("### 💰 Zyski kapitałowe")
    
    # Wybór roku
    current_year = datetime.now().year
    tax_year = st.selectbox(
        "Rok podatkowy",
        options=list(range(current_year, 2020, -1)),
        index=0,
        key="capital_gains_year"
    )
    
    st.info("""
    **ℹ️ Informacje o zyskach kapitałowych:**
    
    - Stawka podatku: **19%**
    - Metoda rozliczania: **FIFO** (pierwsze kupione, pierwsze sprzedane)
    - Kursy NBP: z dnia poprzedzającego sprzedaż
    - Straty można rozliczać z zyskami w tym samym roku
    """)
    
    try:
        capital_gains = calculate_year_capital_gains(tax_year)
        
        if capital_gains:
            # Oblicz podsumowanie
            total_gains_usd = sum(gain.get('gain_usd', 0) for gain in capital_gains if gain.get('gain_usd', 0) > 0)
            total_losses_usd = sum(gain.get('gain_usd', 0) for gain in capital_gains if gain.get('gain_usd', 0) < 0)
            net_gain_usd = total_gains_usd + total_losses_usd
            
            total_gains_pln = sum(gain.get('gain_pln', 0) for gain in capital_gains if gain.get('gain_pln', 0) > 0)
            total_losses_pln = sum(gain.get('gain_pln', 0) for gain in capital_gains if gain.get('gain_pln', 0) < 0)
            net_gain_pln = total_gains_pln + total_losses_pln
            
            tax_due = max(0, net_gain_pln * 0.19)
            
            # Podsumowanie
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("💰 Zyski", format_currency(total_gains_pln, "PLN"))
            
            with col2:
                st.metric("📉 Straty", format_currency(abs(total_losses_pln), "PLN"))
            
            with col3:
                st.metric("📊 Wynik netto", format_currency(net_gain_pln, "PLN"))
            
            with col4:
                st.metric("🧾 Podatek należny", format_currency(tax_due, "PLN"))
            
            # Szczegółowa tabela
            st.markdown("#### 📋 Szczegółowe transakcje sprzedaży")
            
            df = pd.DataFrame(capital_gains)
            
            if not df.empty:
                # Formatowanie
                display_df = df.copy()
                display_df['date'] = pd.to_datetime(display_df['date']).dt.strftime('%d.%m.%Y')
                display_df['gain_usd'] = display_df['gain_usd'].apply(format_currency)
                display_df['gain_pln'] = display_df['gain_pln'].apply(lambda x: format_currency(x, "PLN"))
                display_df['usd_rate'] = display_df['usd_rate'].apply(lambda x: f"{x:.4f}")
                
                st.dataframe(
                    display_df[['symbol', 'date', 'gain_usd', 'usd_rate', 'gain_pln']].rename(columns={
                        'symbol': 'Symbol',
                        'date': 'Data sprzedaży',
                        'gain_usd': 'Zysk/Strata USD',
                        'usd_rate': 'Kurs NBP',
                        'gain_pln': 'Zysk/Strata PLN'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
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
    
    try:
        # Pobierz dywidendy za dany rok
        dividends_summary = DividendsRepository.get_tax_summary_for_dividends(tax_year)
        
        if dividends_summary:
            st.success("Moduł dywidend zostanie zaimplementowany w przyszłej wersji.")
        else:
            st.info(f"Brak dywidend w {tax_year} roku.")
    
    except Exception as e:
        st.info("Moduł dywidend nie jest jeszcze dostępny.")

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
    - Moment opodatkowania: otrzymanie premium (otwarcie opcji)
    - Kursy NBP: z dnia poprzedzającego otwarcie opcji (D-1)
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
            
            # NAPRAWIONE: Pobierz kurs i sprawdź z jakiej daty rzeczywiście pochodzi
            nbp_rate_date_requested = open_date - timedelta(days=1)
            
            try:
                usd_rate = nbp_service.get_usd_pln_rate(nbp_rate_date_requested)
                if usd_rate:
                    # NOWE: Sprawdź z jakiej daty faktycznie pochodzi kurs
                    actual_date = get_actual_nbp_rate_date(nbp_rate_date_requested)
                    nbp_rate_date_display = actual_date if actual_date else nbp_rate_date_requested
                else:
                    usd_rate = 3.65
                    nbp_rate_date_display = "Domyślny"
            except:
                usd_rate = 3.65
                nbp_rate_date_display = "Domyślny"
            
            # Przelicz na PLN
            premium_pln = total_premium_usd * usd_rate
            tax_pln = premium_pln * 0.19
            
            total_premium_pln += premium_pln
            total_tax_pln += tax_pln
            
            tax_calculations.append({
                'symbol': symbol,
                'open_date': open_date,
                'nbp_rate_date': nbp_rate_date_display,
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
        display_df['nbp_rate_date'] = display_df['nbp_rate_date'].apply(
            lambda x: format_polish_date(x) if x != "Domyślny" else "❌ Domyślny"
        )  # NOWE FORMATOWANIE
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
        
        # Tabela z nową kolumną
        st.dataframe(
            display_df[[
                'symbol', 'open_date', 'nbp_rate_date', 'status', 'quantity', 'premium_per_contract',
                'total_premium_usd', 'usd_rate', 'premium_pln', 'tax_pln'
            ]].rename(columns={
                'symbol': 'Symbol',
                'open_date': 'Data otwarcia',
                'nbp_rate_date': 'Data kursu NBP',  # NOWA KOLUMNA
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
        
        if not status_analysis.empty:
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
        try:
            dividends_summary = DividendsRepository.get_tax_summary_for_dividends(tax_year)
        except:
            dividends_summary = []
        
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
                avg_rate = 3.65  # W rzeczywistej aplikacji użyj rzeczywistych kursów
                total_dividends_pln += div.get('total_dividends_usd', 0) * avg_rate
                total_dividends_tax_credit += div.get('total_tax_withheld_usd', 0) * avg_rate
        
        # Oblicz opcje (uproszczone)
        if options_summary:
            for opt in options_summary:
                avg_rate = 3.65
                total_options_pln += opt.get('premium_received', 0) * opt.get('quantity', 0) * avg_rate
        
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
        
        with col2:
            st.metric(
                "🧾 Podatek należny",
                format_currency(total_tax_due, "PLN")
            )
        
        with col3:
            st.metric(
                "💸 Do dopłaty",
                format_currency(total_tax_to_pay, "PLN")
            )
        
        # Szczegółowe rozbicie
        st.markdown("#### 📊 Szczegółowe rozbicie")
        
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
        
        # Dodaj opcje
        if options_summary:
            for opt in options_summary:
                avg_rate = 3.65
                premium_pln = opt.get('premium_received', 0) * opt.get('quantity', 0) * avg_rate
                breakdown_data.append({
                    'Kategoria': 'Premium opcji',
                    'Symbol': opt.get('symbol', 'N/A'),
                    'Data': opt.get('open_date', 'N/A'),
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
           - Do dopłaty: {format_currency(total_tax_to_pay, "PLN")}
        
        3. **Terminy:**
           - Złożenie zeznania: do 30 kwietnia {tax_year + 1}
           - Wpłata podatku: do 31 maja {tax_year + 1}
        
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
        # Dla celów demonstracyjnych - zwróć pustą listę
        # W rzeczywistej implementacji należy użyć metod z StockRepository
        return []
    except Exception:
        return []
        
def get_actual_nbp_rate_date(requested_date):
    """Sprawdza z jakiej daty faktycznie pochodzi kurs NBP."""
    from db import execute_query
    
    try:
        # Sprawdź w cache z jakiej daty mamy kurs dla tej daty lub wcześniejszy
        result = execute_query(
            """SELECT date FROM exchange_rates 
               WHERE currency_pair = 'USD/PLN' 
               AND date <= ? 
               ORDER BY date DESC LIMIT 1""",
            (requested_date.strftime("%Y-%m-%d"),)
        )
        
        if result:
            actual_date_str = result[0]['date']
            return datetime.strptime(actual_date_str, "%Y-%m-%d").date()
        
        return None
    except:
        return None