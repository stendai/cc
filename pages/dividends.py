import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import plotly.express as px
import plotly.graph_objects as go

from repos.dividends_repo import DividendsRepository
from repos.stock_repo import StockRepository
from services.nbp import nbp_service
from utils.formatting import (
    format_currency, format_percentage, format_gain_loss, 
    format_polish_date
)

def show():
    """Wyświetla stronę zarządzania dywidendami."""
    
    st.markdown("## 💰 Zarządzanie Dywidendami")
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Przegląd", "➕ Dodaj dywidendę", "📈 Analiza rentowności", "📅 Kalendarz", "🧾 Podatki"
    ])
    
    with tab1:
        show_overview_tab()
    
    with tab2:
        show_add_dividend_tab()
    
    with tab3:
        show_yield_analysis_tab()
    
    with tab4:
        show_calendar_tab()
    
    with tab5:
        show_tax_tab()

def show_overview_tab():
    """Wyświetla przegląd dywidend."""
    
    st.markdown("### 📊 Przegląd dywidend")
    
    # Podsumowanie dywidend
    current_year = datetime.now().year
    summary = DividendsRepository.get_dividend_summary(current_year)
    total_summary = DividendsRepository.get_dividend_summary()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            f"💰 Dywidendy {current_year}",
            format_currency(summary.get('total_dividends', 0))
        )
    
    with col2:
        st.metric(
            "💎 Łączne dywidendy",
            format_currency(total_summary.get('total_dividends', 0))
        )
    
    with col3:
        st.metric(
            f"📋 Wypłaty {current_year}",
            summary.get('total_payments', 0)
        )
    
    with col4:
        st.metric(
            "🏢 Spółki dywidendowe",
            total_summary.get('dividend_paying_stocks', 0)
        )
    
    # Przeliczenie na PLN
    current_usd_rate = nbp_service.get_current_usd_rate()
    if current_usd_rate:
        col1, col2 = st.columns(2)
        
        with col1:
            dividends_pln = summary.get('total_dividends', 0) * current_usd_rate
            st.metric(
                f"💰 Dywidendy {current_year} (PLN)",
                format_currency(dividends_pln, "PLN")
            )
        
        with col2:
            tax_withheld_pln = summary.get('total_tax_withheld', 0) * current_usd_rate
            st.metric(
                "🧾 Podatek u źródła (PLN)",
                format_currency(tax_withheld_pln, "PLN")
            )
    
    # Wykres miesięczny
    monthly_dividends = DividendsRepository.get_monthly_dividends(current_year)
    
    if monthly_dividends:
        st.markdown("#### 📈 Miesięczne dywidendy")
        
        df = pd.DataFrame(monthly_dividends)
        
        fig = px.bar(
            df,
            x='year_month',
            y='total_amount',
            title=f"Dywidendy w {current_year} roku",
            labels={'total_amount': 'Dywidendy (USD)', 'year_month': 'Miesiąc'}
        )
        
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    # Lista ostatnich dywidend
    st.markdown("#### 📋 Ostatnie dywidendy")
    
    dividends = DividendsRepository.get_all_dividends()
    
    if dividends:
        # Pokaż tylko ostatnie 10
        recent_dividends = dividends[:10]
        df = pd.DataFrame(recent_dividends)
        
        # Formatowanie
        display_df = df.copy()
        display_df['dividend_per_share'] = display_df['dividend_per_share'].apply(format_currency)
        display_df['total_amount_usd'] = display_df['total_amount_usd'].apply(format_currency)
        display_df['tax_withheld_usd'] = display_df['tax_withheld_usd'].apply(format_currency)
        display_df['ex_date'] = pd.to_datetime(display_df['ex_date']).dt.strftime('%d.%m.%Y')
        display_df['pay_date'] = pd.to_datetime(display_df['pay_date']).dt.strftime('%d.%m.%Y')
        
        st.dataframe(
            display_df[[
                'symbol', 'pay_date', 'ex_date', 'quantity', 
                'dividend_per_share', 'total_amount_usd', 'tax_withheld_usd'
            ]].rename(columns={
                'symbol': 'Symbol',
                'pay_date': 'Data wypłaty',
                'ex_date': 'Data ex-dividend',
                'quantity': 'Ilość akcji',
                'dividend_per_share': 'Dywidenda/akcja',
                'total_amount_usd': 'Kwota całkowita',
                'tax_withheld_usd': 'Podatek u źródła'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        if len(dividends) > 10:
            st.info(f"Wyświetlono 10 z {len(dividends)} dywidend. Więcej w zakładce 'Kalendarz'.")
    
    else:
        st.info("Brak zarejestrowanych dywidend.")

def show_add_dividend_tab():
    """Formularz dodawania nowej dywidendy."""
    
    st.markdown("### ➕ Dodaj dywidendę")
    
    # Pobierz listę akcji
    stocks = StockRepository.get_all_stocks()
    
    if not stocks:
        st.warning("⚠️ Brak akcji w portfelu. Najpierw dodaj akcje w sekcji 'Akcje'.")
        return
    
    with st.form("add_dividend_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Wybór akcji
            selected_stock = st.selectbox(
                "Akcja *",
                options=stocks,
                format_func=lambda x: f"{x['symbol']} - {x['name']}"
            )
            
            # Dywidenda na akcję
            dividend_per_share = st.number_input(
                "Dywidenda na akcję (USD) *",
                min_value=0.001,
                value=0.50,
                step=0.001,
                format="%.3f"
            )
            
            # Ilość akcji
            if selected_stock:
                default_quantity = selected_stock['quantity']
                st.info(f"💡 Posiadasz {default_quantity} akcji {selected_stock['symbol']}")
            else:
                default_quantity = 1
            
            quantity = st.number_input(
                "Ilość akcji z dywidendą *",
                min_value=1,
                value=default_quantity,
                step=1
            )
        
        with col2:
            # Data ex-dividend
            ex_date = st.date_input(
                "Data ex-dividend *",
                value=date.today() - timedelta(days=30),
                help="Data, po której kupno akcji nie uprawnia do dywidendy"
            )
            
            # Data wypłaty
            pay_date = st.date_input(
                "Data wypłaty *",
                value=date.today(),
                help="Data faktycznej wypłaty dywidendy"
            )
            
            # Podatek u źródła
            tax_withheld = st.number_input(
                "Podatek u źródła (USD)",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.2f",
                help="Podatek potrącony przez zagraniczny urząd skarbowy"
            )
        
        # Kalkulacje
        total_amount = dividend_per_share * quantity
        net_amount = total_amount - tax_withheld
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"💰 Kwota brutto: {format_currency(total_amount)}")
        with col2:
            st.info(f"🧾 Podatek u źródła: {format_currency(tax_withheld)}")
        with col3:
            st.info(f"💎 Kwota netto: {format_currency(net_amount)}")
        
        # Informacja o kursie NBP
        if pay_date:
            try:
                usd_rate = nbp_service.get_usd_pln_rate(pay_date)
                if usd_rate:
                    st.info(f"💱 Kurs NBP na {pay_date.strftime('%d.%m.%Y')}: {usd_rate:.4f} PLN/USD")
                    total_pln = total_amount * usd_rate
                    st.info(f"🇵🇱 Dywidenda w PLN: {format_currency(total_pln, 'PLN')}")
            except:
                st.warning("⚠️ Nie można pobrać kursu NBP dla wybranej daty")
        
        # Przycisk dodania
        submitted = st.form_submit_button(
            "💾 Dodaj dywidendę",
            type="primary",
            use_container_width=True
        )
        
        if submitted:
            try:
                dividend_id = DividendsRepository.add_dividend(
                    stock_id=selected_stock['id'],
                    dividend_per_share=dividend_per_share,
                    quantity=quantity,
                    total_amount=total_amount,
                    tax_withheld=tax_withheld,
                    ex_date=ex_date,
                    pay_date=pay_date
                )
                
                st.success(f"✅ Dywidenda została dodana! (ID: {dividend_id})")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Błąd podczas dodawania dywidendy: {str(e)}")

def show_yield_analysis_tab():
    """Wyświetla analizę rentowności dywidendowej."""
    
    st.markdown("### 📈 Analiza rentowności dywidendowej")
    
    # Analiza rentowności
    yield_analysis = DividendsRepository.get_dividend_yield_analysis()
    
    if yield_analysis:
        df = pd.DataFrame(yield_analysis)
        
        # Filtruj tylko spółki z dywidendami
        df_dividends = df[df['dividend_payments_12m'] > 0].copy()
        
        if not df_dividends.empty:
            # Wykres rentowności
            fig = px.scatter(
                df_dividends,
                x='symbol',
                y='current_yield_pct',
                size='total_dividends_12m',
                hover_data=['yield_on_cost_pct', 'dividend_payments_12m'],
                title="Rentowność dywidendowa (12 miesięcy)",
                labels={
                    'current_yield_pct': 'Aktualna rentowność (%)',
                    'symbol': 'Symbol akcji',
                    'total_dividends_12m': 'Dywidendy 12m (USD)'
                }
            )
            
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Tabela rentowności
            st.markdown("#### 📊 Szczegółowa analiza")
            
            # Formatowanie tabeli
            display_df = df_dividends.copy()
            display_df['avg_price_usd'] = display_df['avg_price_usd'].apply(format_currency)
            display_df['current_price_usd'] = display_df['current_price_usd'].apply(format_currency)
            display_df['total_dividends_12m'] = display_df['total_dividends_12m'].apply(format_currency)
            display_df['avg_dividend_per_share'] = display_df['avg_dividend_per_share'].apply(format_currency)
            display_df['current_yield_pct'] = display_df['current_yield_pct'].apply(lambda x: f"{x:.2f}%")
            display_df['yield_on_cost_pct'] = display_df['yield_on_cost_pct'].apply(lambda x: f"{x:.2f}%")
            
            st.dataframe(
                display_df[[
                    'symbol', 'quantity', 'avg_price_usd', 'current_price_usd',
                    'dividend_payments_12m', 'total_dividends_12m', 'avg_dividend_per_share',
                    'current_yield_pct', 'yield_on_cost_pct'
                ]].rename(columns={
                    'symbol': 'Symbol',
                    'quantity': 'Ilość akcji',
                    'avg_price_usd': 'Śr. cena zakupu',
                    'current_price_usd': 'Aktualna cena',
                    'dividend_payments_12m': 'Wypłaty 12m',
                    'total_dividends_12m': 'Dywidendy 12m',
                    'avg_dividend_per_share': 'Śr. dywidenda/akcja',
                    'current_yield_pct': 'Rentowność aktualna',
                    'yield_on_cost_pct': 'Rentowność od kosztu'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Podsumowanie
            st.markdown("#### 💡 Kluczowe wskaźniki")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                avg_yield = df_dividends['current_yield_pct'].mean()
                st.metric("📊 Średnia rentowność portfela", f"{avg_yield:.2f}%")
            
            with col2:
                best_yielder = df_dividends.loc[df_dividends['current_yield_pct'].idxmax()]
                st.metric("🏆 Najlepsza rentowność", 
                         f"{best_yielder['symbol']}: {best_yielder['current_yield_pct']:.2f}%")
            
            with col3:
                total_annual_dividends = df_dividends['total_dividends_12m'].sum()
                st.metric("💰 Roczne dywidendy", format_currency(total_annual_dividends))
        
        else:
            st.info("Brak danych o dywidendach z ostatnich 12 miesięcy.")
        
        # Analiza reinwestycji
        st.markdown("#### 🔄 Analiza potencjału reinwestycji")
        
        reinvestment_analysis = DividendsRepository.get_dividend_reinvestment_analysis()
        
        if reinvestment_analysis:
            reinvest_df = pd.DataFrame(reinvestment_analysis)
            
            # Formatowanie
            display_reinvest = reinvest_df.copy()
            display_reinvest['current_price_usd'] = display_reinvest['current_price_usd'].apply(format_currency)
            display_reinvest['total_dividends_received'] = display_reinvest['total_dividends_received'].apply(format_currency)
            display_reinvest['reinvestment_value'] = display_reinvest['reinvestment_value'].apply(format_currency)
            
            st.dataframe(
                display_reinvest[[
                    'symbol', 'current_price_usd', 'total_dividends_received',
                    'shares_could_buy', 'reinvestment_value'
                ]].rename(columns={
                    'symbol': 'Symbol',
                    'current_price_usd': 'Aktualna cena',
                    'total_dividends_received': 'Dywidendy otrzymane',
                    'shares_could_buy': 'Akcji do kupienia',
                    'reinvestment_value': 'Wartość reinwestycji'
                }),
                use_container_width=True,
                hide_index=True
            )
    
    else:
        st.info("Brak danych do analizy rentowności.")

def show_calendar_tab():
    """Wyświetla kalendarz dywidend."""
    
    st.markdown("### 📅 Kalendarz dywidend")
    
    # Wybór zakresu dat
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Data od",
            value=date.today() - timedelta(days=365),
            max_value=date.today()
        )
    
    with col2:
        end_date = st.date_input(
            "Data do",
            value=date.today(),
            max_value=date.today()
        )
    
    if start_date > end_date:
        st.error("Data początkowa nie może być późniejsza niż końcowa!")
        return
    
    # Pobierz dywidendy z wybranego okresu
    calendar_dividends = DividendsRepository.get_dividend_calendar(start_date, end_date)
    
    if calendar_dividends:
        df = pd.DataFrame(calendar_dividends)
        
        # Sortuj po dacie wypłaty
        df['pay_date_dt'] = pd.to_datetime(df['pay_date'])
        df = df.sort_values('pay_date_dt', ascending=False)
        
        # Formatowanie
        display_df = df.copy()
        display_df['dividend_per_share'] = display_df['dividend_per_share'].apply(format_currency)
        display_df['total_amount_usd'] = display_df['total_amount_usd'].apply(format_currency)
        display_df['pay_date'] = pd.to_datetime(display_df['pay_date']).dt.strftime('%d.%m.%Y')
        display_df['ex_date'] = pd.to_datetime(display_df['ex_date']).dt.strftime('%d.%m.%Y')
        
        st.dataframe(
            display_df[[
                'pay_date', 'ex_date', 'symbol', 'name', 'quantity',
                'dividend_per_share', 'total_amount_usd'
            ]].rename(columns={
                'pay_date': 'Data wypłaty',
                'ex_date': 'Data ex-dividend',
                'symbol': 'Symbol',
                'name': 'Nazwa spółki',
                'quantity': 'Ilość akcji',
                'dividend_per_share': 'Dywidenda/akcja',
                'total_amount_usd': 'Kwota całkowita'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Wykres timeline
        st.markdown("#### 📈 Timeline dywidend")
        
        # Przygotuj dane do wykresu
        monthly_totals = df.groupby(df['pay_date_dt'].dt.to_period('M'))['total_amount_usd'].sum().reset_index()
        monthly_totals['month'] = monthly_totals['pay_date_dt'].dt.strftime('%Y-%m')
        
        fig = px.bar(
            monthly_totals,
            x='month',
            y='total_amount_usd',
            title=f"Dywidendy miesięcznie ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})",
            labels={'total_amount_usd': 'Dywidendy (USD)', 'month': 'Miesiąc'}
        )
        
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        # Statystyki okresu
        st.markdown("#### 📊 Statystyki okresu")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_dividends = df['total_amount_usd'].sum()
            st.metric("💰 Łączne dywidendy", format_currency(total_dividends))
        
        with col2:
            avg_dividend = df['total_amount_usd'].mean()
            st.metric("📊 Średnia dywidenda", format_currency(avg_dividend))
        
        with col3:
            unique_companies = df['symbol'].nunique()
            st.metric("🏢 Spółki", unique_companies)
        
        with col4:
            total_payments = len(df)
            st.metric("📋 Wypłaty", total_payments)
    
    else:
        st.info(f"Brak dywidend w okresie {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")

def show_tax_tab():
    """Wyświetla informacje podatkowe dotyczące dywidend."""
    
    st.markdown("### 🧾 Podatki od dywidend")
    
    # Wybór roku podatkowego
    current_year = datetime.now().year
    tax_year = st.selectbox(
        "Rok podatkowy",
        options=list(range(current_year, 2020, -1)),
        index=0
    )
    
    # Pobierz podsumowanie podatkowe
    tax_summary = DividendsRepository.get_tax_summary_for_dividends(tax_year)
    
    if tax_summary:
        st.markdown(f"#### 📊 Podsumowanie podatkowe {tax_year}")
        
        df = pd.DataFrame(tax_summary)
        
        # Oblicz dodatkowe kolumny podatkowe
        total_dividends_usd = 0
        total_tax_withheld_usd = 0
        total_dividends_pln = 0
        total_tax_withheld_pln = 0
        total_tax_due_pln = 0
        
        for _, row in df.iterrows():
            dividend_usd = row['total_dividends_usd']
            tax_withheld_usd = row['total_tax_withheld_usd']
            
            total_dividends_usd += dividend_usd
            total_tax_withheld_usd += tax_withheld_usd
            
            # Pobierz kursy NBP dla każdej wypłaty
            payment_dates = row['payment_dates'].split(',') if row['payment_dates'] else []
            
            dividend_pln = 0
            tax_withheld_pln = 0
            
            for payment_date_str in payment_dates:
                try:
                    payment_date = datetime.strptime(payment_date_str.strip(), '%Y-%m-%d').date()
                    usd_rate = nbp_service.get_usd_pln_rate(payment_date)
                    
                    if usd_rate:
                        # Proporcjonalne przeliczenie dla tej daty
                        portion = 1 / len(payment_dates)
                        dividend_pln += (dividend_usd * portion) * usd_rate
                        tax_withheld_pln += (tax_withheld_usd * portion) * usd_rate
                
                except Exception as e:
                    st.warning(f"Błąd kursu dla {payment_date_str}: {e}")
            
            total_dividends_pln += dividend_pln
            total_tax_withheld_pln += tax_withheld_pln
        
        # Oblicz podatek należny w Polsce (19%)
        total_tax_due_pln = total_dividends_pln * 0.19
        tax_to_pay_pln = max(0, total_tax_due_pln - total_tax_withheld_pln)
        
        # Wyświetl podsumowanie
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "💰 Dywidendy brutto",
                format_currency(total_dividends_usd)
            )
            st.caption(format_currency(total_dividends_pln, "PLN"))
        
        with col2:
            st.metric(
                "🇺🇸 Podatek u źródła",
                format_currency(total_tax_withheld_usd)
            )
            st.caption(format_currency(total_tax_withheld_pln, "PLN"))
        
        with col3:
            st.metric(
                "🇵🇱 Podatek należny (19%)",
                format_currency(total_tax_due_pln, "PLN")
            )
        
        with col4:
            st.metric(
                "💸 Do dopłaty w Polsce",
                format_currency(tax_to_pay_pln, "PLN")
            )
            if tax_to_pay_pln > 0:
                st.caption("🔴 Wymagana dopłata")
            else:
                st.caption("🟢 Brak dopłaty")
        
        # Szczegółowa tabela
        st.markdown("#### 📋 Szczegóły według spółek")
        
        # Formatowanie tabeli
        display_df = df.copy()
        display_df['total_dividends_usd'] = display_df['total_dividends_usd'].apply(format_currency)
        display_df['total_tax_withheld_usd'] = display_df['total_tax_withheld_usd'].apply(format_currency)
        
        st.dataframe(
            display_df[[
                'symbol', 'total_dividends_usd', 'total_tax_withheld_usd', 'payment_count'
            ]].rename(columns={
                'symbol': 'Symbol',
                'total_dividends_usd': 'Dywidendy (USD)',
                'total_tax_withheld_usd': 'Podatek u źródła (USD)',
                'payment_count': 'Liczba wypłat'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Informacje o rozliczeniu
        st.markdown("#### ℹ️ Informacje o rozliczeniu")
        
        st.info("""
        **Ważne informacje podatkowe:**
        
        1. **Podatek u źródła (USA):** 15% zgodnie z umową o unikaniu podwójnego opodatkowania
        2. **Podatek w Polsce:** 19% od dywidend zagranicznych
        3. **Zaliczeń:** Podatek potrącony w USA można zaliczyć na podatek polski
        4. **Kursy NBP:** Użyto kursów z dat wypłat dywidend
        5. **Rozliczenie:** Dywidendy należy rozliczyć w zeznaniu rocznym PIT
        
        ⚠️ **Uwaga:** To tylko szacunkowe obliczenia. Skonsultuj się z doradcą podatkowym!
        """)
        
        # Przycisk eksportu (placeholder)
        if st.button("📄 Eksportuj zestawienie podatkowe"):
            st.info("Funkcja eksportu będzie dostępna w przyszłej wersji.")
    
    else:
        st.info(f"Brak dywidend w {tax_year} roku do rozliczenia podatkowego.")