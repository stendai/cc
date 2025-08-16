import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import plotly.express as px
import plotly.graph_objects as go

from repos.options_repo import OptionsRepository
from repos.stock_repo import StockRepository
from utils.formatting import (
    format_currency, format_percentage, format_gain_loss, 
    format_polish_date, format_days_to_expiry, get_status_color
)

def show():
    """Wyświetla stronę zarządzania opcjami."""
    
    st.markdown("## 📋 Zarządzanie Opcjami")
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Aktywne opcje", "➕ Dodaj opcję", "📊 Wydajność", "⚠️ Wygasające", "📋 Historia"
    ])
    
    with tab1:
        show_active_options_tab()
    
    with tab2:
        show_add_option_tab()
    
    with tab3:
        show_performance_tab()
    
    with tab4:
        show_expiring_options_tab()
    
    with tab5:
        show_history_tab()

def show_active_options_tab():
    """Wyświetla aktywne opcje."""
    
    st.markdown("### 📈 Aktywne opcje")
    
    # Podsumowanie opcji
    summary = OptionsRepository.get_options_summary()
    
    if summary:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "📋 Wszystkie opcje", 
                summary.get('total_options', 0)
            )
        
        with col2:
            st.metric(
                "🟢 Aktywne opcje", 
                summary.get('open_options', 0)
            )
        
        with col3:
            st.metric(
                "💰 Aktywne premium", 
                format_currency(summary.get('active_premium', 0))
            )
        
        with col4:
            st.metric(
                "💎 Łączne premium", 
                format_currency(summary.get('total_premium_received', 0))
            )
    
    # Lista aktywnych opcji
    options = OptionsRepository.get_all_options(include_closed=False)
    
    if options:
        df = pd.DataFrame(options)
        
        # Oblicz dodatkowe kolumny
        df['total_premium'] = df['premium_received'] * df['quantity']
        df['days_to_expiry'] = df['days_to_expiry'].fillna(0).astype(int)
        
        # Status kolory dla dni do wygaśnięcia
        def get_expiry_color(days):
            if days < 0:
                return "🔴"
            elif days <= 7:
                return "🟠"
            elif days <= 30:
                return "🟡"
            else:
                return "🟢"
        
        df['expiry_status'] = df['days_to_expiry'].apply(get_expiry_color)
        
        # Formatowanie dla wyświetlenia
        display_df = df.copy()
        display_df['strike_price'] = display_df['strike_price'].apply(format_currency)
        display_df['premium_received'] = display_df['premium_received'].apply(format_currency)
        display_df['total_premium'] = display_df['total_premium'].apply(format_currency)
        display_df['current_price_usd'] = display_df['current_price_usd'].apply(format_currency)
        display_df['intrinsic_value'] = display_df['intrinsic_value'].apply(format_currency)
        display_df['expiry_date'] = pd.to_datetime(display_df['expiry_date']).dt.strftime('%d.%m.%Y')
        display_df['open_date'] = pd.to_datetime(display_df['open_date']).dt.strftime('%d.%m.%Y')
        
        st.dataframe(
            display_df[[
                'symbol', 'option_type', 'strike_price', 'expiry_date', 
                'expiry_status', 'days_to_expiry', 'quantity', 'premium_received', 
                'total_premium', 'current_price_usd', 'intrinsic_value'
            ]].rename(columns={
                'symbol': 'Symbol',
                'option_type': 'Typ',
                'strike_price': 'Strike',
                'expiry_date': 'Wygaśnięcie',
                'expiry_status': 'Status',
                'days_to_expiry': 'Dni do wygaśnięcia',
                'quantity': 'Ilość',
                'premium_received': 'Premium/szt',
                'total_premium': 'Premium całkowite',
                'current_price_usd': 'Cena akcji',
                'intrinsic_value': 'Wartość wewnętrzna'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Analiza ryzyka przydziału
        st.markdown("#### ⚠️ Analiza ryzyka przydziału")
        
        risk_options = OptionsRepository.get_assignment_risk()
        
        if risk_options:
            risk_df = pd.DataFrame(risk_options)
            
            st.warning(f"🚨 {len(risk_options)} opcji z wysokim ryzykiem przydziału!")
            
            # Wyświetl opcje wysokiego ryzyka
            risk_display = risk_df.copy()
            risk_display['moneyness_pct'] = risk_display['moneyness_pct'].apply(lambda x: f"{x:.1f}%")
            risk_display['strike_price'] = risk_display['strike_price'].apply(format_currency)
            risk_display['current_price_usd'] = risk_display['current_price_usd'].apply(format_currency)
            
            st.dataframe(
                risk_display[['symbol', 'option_type', 'strike_price', 'current_price_usd', 'moneyness_pct', 'days_to_expiry']].rename(columns={
                    'symbol': 'Symbol',
                    'option_type': 'Typ',
                    'strike_price': 'Strike',
                    'current_price_usd': 'Cena akcji',
                    'moneyness_pct': 'Moneyness %',
                    'days_to_expiry': 'Dni do wygaśnięcia'
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("✅ Brak opcji z wysokim ryzykiem przydziału")
    
    else:
        st.info("Brak aktywnych opcji. Dodaj pierwszą opcję.")

def show_add_option_tab():
    """Formularz dodawania nowej opcji."""
    
    st.markdown("### ➕ Dodaj nową opcję")
    
    # Pobierz listę akcji
    stocks = StockRepository.get_all_stocks()
    
    if not stocks:
        st.warning("⚠️ Brak akcji w portfelu. Najpierw dodaj akcje w sekcji 'Akcje'.")
        return
    
    with st.form("add_option_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Wybór akcji
            selected_stock = st.selectbox(
                "Akcja bazowa *",
                options=stocks,
                format_func=lambda x: f"{x['symbol']} - {x['name']}"
            )
            
            # Typ opcji
            option_type = st.selectbox(
                "Typ opcji *",
                ["CALL", "PUT"],
                format_func=lambda x: "Call (opcja kupna)" if x == "CALL" else "Put (opcja sprzedaży)"
            )
            
            # Cena wykonania
            strike_price = st.number_input(
                "Cena wykonania (USD) *",
                min_value=0.01,
                value=100.0,
                step=0.01,
                format="%.2f"
            )
            
            # Data wygaśnięcia
            expiry_date = st.date_input(
                "Data wygaśnięcia *",
                value=date.today() + timedelta(days=30),
                min_value=date.today()
            )
        
        with col2:
            # Premium otrzymane
            premium_received = st.number_input(
                "Premium otrzymane (USD/akcja) *",
                min_value=0.01,
                value=1.0,
                step=0.01,
                format="%.2f"
            )
            
            # Ilość kontraktów
            quantity = st.number_input(
                "Ilość kontraktów *",
                min_value=1,
                value=1,
                step=1,
                help="1 kontrakt = 100 akcji"
            )
            
            # Prowizja
            commission = st.number_input(
                "Prowizja (USD)",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.2f"
            )
            
            # Data otwarcia
            open_date = st.date_input(
                "Data otwarcia *",
                value=date.today(),
                max_value=date.today()
            )
        
        # Notatki
        notes = st.text_area(
            "Notatki",
            placeholder="Opcjonalne notatki o opcji..."
        )
        
        # Podsumowanie opcji
        total_premium = premium_received * quantity * 100  # 100 akcji na kontrakt
        net_premium = total_premium - commission
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"💰 Premium całkowite: {format_currency(total_premium)}")
        with col2:
            st.info(f"💸 Prowizja: {format_currency(commission)}")
        with col3:
            st.info(f"💎 Premium netto: {format_currency(net_premium)}")
        
        # Sprawdzenie covered call
        if selected_stock and option_type == "CALL":
            shares_needed = quantity * 100
            shares_owned = selected_stock['quantity']
            
            if shares_owned >= shares_needed:
                st.success(f"✅ Covered Call: Posiadasz {shares_owned} akcji (potrzebujesz {shares_needed})")
            else:
                st.warning(f"⚠️ Naked Call: Posiadasz {shares_owned} akcji (potrzebujesz {shares_needed})")
        
        # Przycisk dodania
        submitted = st.form_submit_button(
            "💾 Dodaj opcję",
            type="primary",
            use_container_width=True
        )
        
        if submitted:
            try:
                option_id = OptionsRepository.add_option(
                    stock_id=selected_stock['id'],
                    option_type=option_type,
                    strike_price=strike_price,
                    expiry_date=expiry_date,
                    premium_received=premium_received,
                    quantity=quantity,
                    open_date=open_date,
                    commission=commission,
                    notes=notes
                )
                
                st.success(f"✅ Opcja została dodana! (ID: {option_id})")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Błąd podczas dodawania opcji: {str(e)}")

def show_performance_tab():
    """Wyświetla wydajność opcji."""
    
    st.markdown("### 📊 Wydajność opcji")
    
    # Podsumowanie dochodów
    summary = OptionsRepository.get_options_summary()
    current_year = datetime.now().year
    yearly_income = OptionsRepository.calculate_option_income(current_year)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "💰 Łączne premium",
            format_currency(summary.get('total_premium_received', 0))
        )
    
    with col2:
        st.metric(
            f"📅 Premium {current_year}",
            format_currency(yearly_income.get('total_premium', 0))
        )
    
    with col3:
        expired_premium = summary.get('total_premium_received', 0) - summary.get('active_premium', 0)
        st.metric(
            "✅ Premium zrealizowane",
            format_currency(expired_premium)
        )
    
    with col4:
        avg_premium = yearly_income.get('avg_premium_per_contract', 0)
        st.metric(
            "📊 Śr. premium/kontrakt",
            format_currency(avg_premium)
        )
    
    # Wykres miesięcznych dochodów
    monthly_income = OptionsRepository.get_monthly_option_income(current_year)
    
    if monthly_income:
        st.markdown("#### 📈 Miesięczne dochody z opcji")
        
        df = pd.DataFrame(monthly_income)
        
        fig = px.bar(
            df,
            x='year_month',
            y='premium_received',
            title=f"Dochody z opcji w {current_year}",
            labels={'premium_received': 'Premium (USD)', 'year_month': 'Miesiąc'}
        )
        
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    # Analiza wydajności poszczególnych opcji
    performance_data = OptionsRepository.get_options_performance()
    
    if performance_data:
        st.markdown("#### 📋 Wydajność poszczególnych opcji")
        
        df = pd.DataFrame(performance_data)
        
        # Formatowanie
        display_df = df.copy()
        display_df['strike_price'] = display_df['strike_price'].apply(format_currency)
        display_df['premium_received'] = display_df['premium_received'].apply(format_currency)
        display_df['total_premium'] = display_df['total_premium'].apply(format_currency)
        display_df['realized_profit'] = display_df['realized_profit'].apply(format_currency)
        display_df['expiry_date'] = pd.to_datetime(display_df['expiry_date']).dt.strftime('%d.%m.%Y')
        display_df['open_date'] = pd.to_datetime(display_df['open_date']).dt.strftime('%d.%m.%Y')
        
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
                'symbol', 'option_type', 'strike_price', 'expiry_date',
                'status', 'total_premium', 'time_decay_pct', 'realized_profit'
            ]].rename(columns={
                'symbol': 'Symbol',
                'option_type': 'Typ',
                'strike_price': 'Strike',
                'expiry_date': 'Wygaśnięcie',
                'status': 'Status',
                'total_premium': 'Premium',
                'time_decay_pct': 'Upływ czasu %',
                'realized_profit': 'Zysk zrealizowany'
            }),
            use_container_width=True,
            hide_index=True
        )

def show_expiring_options_tab():
    """Wyświetla opcje wygasające w najbliższym czasie."""
    
    st.markdown("### ⚠️ Opcje wygasające")
    
    # Wybór okresu
    days_ahead = st.selectbox(
        "Pokaż opcje wygasające w ciągu:",
        [7, 14, 30, 60],
        format_func=lambda x: f"{x} dni"
    )
    
    expiring_options = OptionsRepository.get_expiring_options(days_ahead)
    
    if expiring_options:
        st.warning(f"⚠️ {len(expiring_options)} opcji wygasa w ciągu {days_ahead} dni!")
        
        df = pd.DataFrame(expiring_options)
        
        # Dodaj kolory dla statusu wygaśnięcia
        def get_urgency_emoji(days):
            if days <= 1:
                return "🚨"
            elif days <= 3:
                return "🔴"
            elif days <= 7:
                return "🟠"
            else:
                return "🟡"
        
        df['urgency'] = df['days_to_expiry'].apply(get_urgency_emoji)
        df['days_to_expiry'] = df['days_to_expiry'].astype(int)
        
        # Formatowanie
        display_df = df.copy()
        display_df['strike_price'] = display_df['strike_price'].apply(format_currency)
        display_df['current_price_usd'] = display_df['current_price_usd'].apply(format_currency)
        display_df['premium_received'] = display_df['premium_received'].apply(format_currency)
        display_df['expiry_date'] = pd.to_datetime(display_df['expiry_date']).dt.strftime('%d.%m.%Y')
        
        st.dataframe(
            display_df[[
                'urgency', 'symbol', 'option_type', 'strike_price', 
                'expiry_date', 'days_to_expiry', 'current_price_usd', 'premium_received'
            ]].rename(columns={
                'urgency': 'Pilność',
                'symbol': 'Symbol',
                'option_type': 'Typ',
                'strike_price': 'Strike',
                'expiry_date': 'Wygaśnięcie',
                'days_to_expiry': 'Dni pozostało',
                'current_price_usd': 'Cena akcji',
                'premium_received': 'Premium'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Akcje dla wygasających opcji
        st.markdown("#### 🎯 Zalecane akcje")
        
        for idx, option in enumerate(expiring_options[:3]):  # Pokaż top 3
            with st.expander(f"{option['symbol']} {option['option_type']} ${option['strike_price']:.2f}"):
                
                current_price = option['current_price_usd']
                strike_price = option['strike_price']
                option_type = option['option_type']
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Aktualna cena:** {format_currency(current_price)}")
                    st.write(f"**Strike:** {format_currency(strike_price)}")
                    st.write(f"**Dni do wygaśnięcia:** {int(option['days_to_expiry'])}")
                
                with col2:
                    if option_type == 'CALL':
                        if current_price > strike_price:
                            st.error("🔴 W pieniądzu - ryzyko przydziału!")
                            st.write("💡 Rozważ zamknięcie pozycji")
                        else:
                            st.success("🟢 Poza pieniądzem")
                            st.write("💡 Prawdopodobnie wygaśnie bezwartościowo")
                    else:  # PUT
                        if current_price < strike_price:
                            st.error("🔴 W pieniądzu - ryzyko przydziału!")
                            st.write("💡 Rozważ zamknięcie pozycji")
                        else:
                            st.success("🟢 Poza pieniądzem")
                            st.write("💡 Prawdopodobnie wygaśnie bezwartościowo")
                
                # Przycisk do aktualizacji statusu
                if st.button(f"Zamknij opcję {option['symbol']}", key=f"close_{idx}"):
                    if OptionsRepository.update_option_status(option['id'], 'CLOSED', date.today()):
                        st.success("Opcja została zamknięta!")
                        st.rerun()
                    else:
                        st.error("Błąd podczas zamykania opcji")
    
    else:
        st.success(f"✅ Brak opcji wygasających w ciągu {days_ahead} dni")

def show_history_tab():
    """Wyświetla historię wszystkich opcji."""
    
    st.markdown("### 📋 Historia opcji")
    
    # Filtry
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Filtr statusu
        status_filter = st.selectbox(
            "Status opcji",
            ["Wszystkie", "OPEN", "EXPIRED", "ASSIGNED", "CLOSED"],
            format_func=lambda x: {
                "Wszystkie": "Wszystkie",
                "OPEN": "🟢 Aktywne",
                "EXPIRED": "🟡 Wygasłe", 
                "ASSIGNED": "🔴 Przydzielone",
                "CLOSED": "🔵 Zamknięte"
            }[x]
        )
    
    with col2:
        # Filtr typu opcji
        type_filter = st.selectbox(
            "Typ opcji",
            ["Wszystkie", "CALL", "PUT"],
            format_func=lambda x: x if x == "Wszystkie" else ("Call" if x == "CALL" else "Put")
        )
    
    with col3:
        # Filtr roku
        year_filter = st.selectbox(
            "Rok",
            ["Wszystkie"] + [str(year) for year in range(datetime.now().year, 2020, -1)]
        )
    
    # Pobierz wszystkie opcje z filtrami
    if status_filter == "Wszystkie":
        options = OptionsRepository.get_all_options(include_closed=True)
    else:
        options = [opt for opt in OptionsRepository.get_all_options(include_closed=True) 
                  if opt['status'] == status_filter]
    
    # Zastosuj dodatkowe filtry
    if type_filter != "Wszystkie":
        options = [opt for opt in options if opt['option_type'] == type_filter]
    
    if year_filter != "Wszystkie":
        options = [opt for opt in options 
                  if datetime.strptime(opt['open_date'], '%Y-%m-%d').year == int(year_filter)]
    
    if options:
        df = pd.DataFrame(options)
        
        # Oblicz dodatkowe kolumny
        df['total_premium'] = df['premium_received'] * df['quantity']
        
        # Formatowanie
        display_df = df.copy()
        display_df['strike_price'] = display_df['strike_price'].apply(format_currency)
        display_df['premium_received'] = display_df['premium_received'].apply(format_currency)
        display_df['total_premium'] = display_df['total_premium'].apply(format_currency)
        display_df['expiry_date'] = pd.to_datetime(display_df['expiry_date']).dt.strftime('%d.%m.%Y')
        display_df['open_date'] = pd.to_datetime(display_df['open_date']).dt.strftime('%d.%m.%Y')
        
        # Mapowanie statusów z kolorami
        status_map = {
            'OPEN': '🟢 Aktywna',
            'EXPIRED': '🟡 Wygasła',
            'ASSIGNED': '🔴 Przydzielona',
            'CLOSED': '🔵 Zamknięta'
        }
        display_df['status'] = display_df['status'].map(status_map)
        
        st.dataframe(
            display_df[[
                'symbol', 'option_type', 'strike_price', 'expiry_date',
                'open_date', 'status', 'quantity', 'premium_received', 'total_premium'
            ]].rename(columns={
                'symbol': 'Symbol',
                'option_type': 'Typ',
                'strike_price': 'Strike',
                'expiry_date': 'Wygaśnięcie',
                'open_date': 'Data otwarcia',
                'status': 'Status',
                'quantity': 'Ilość',
                'premium_received': 'Premium/szt',
                'total_premium': 'Premium całkowite'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Statystyki
        st.markdown("#### 📊 Statystyki")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_contracts = len(options)
            st.metric("📋 Łączne kontrakty", total_contracts)
        
        with col2:
            total_premium = sum(opt['premium_received'] * opt['quantity'] for opt in options)
            st.metric("💰 Łączne premium", format_currency(total_premium))
        
        with col3:
            call_count = len([opt for opt in options if opt['option_type'] == 'CALL'])
            st.metric("📞 Opcje Call", call_count)
        
        with col4:
            put_count = len([opt for opt in options if opt['option_type'] == 'PUT'])
            st.metric("📉 Opcje Put", put_count)
    
    else:
        st.info("Brak opcji spełniających kryteria filtrowania.")