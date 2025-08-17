import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import plotly.express as px
import plotly.graph_objects as go

from repos.stock_repo import StockRepository
from repos.options_repo import OptionsRepository
from utils.formatting import (
    format_currency, format_percentage, format_gain_loss, 
    format_polish_date, get_status_color
)

def show():
    """Wyświetla stronę zarządzania opcjami."""
    
    st.markdown("## 📋 Zarządzanie Opcjami")
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🟢 Aktywne opcje", "➕ Dodaj opcję", "⚠️ Wygasające", "📊 Wydajność", "📋 Historia"
    ])
    
    with tab1:
        show_active_options_tab()
    
    with tab2:
        show_add_option_tab()
    
    with tab3:
        show_expiring_options_tab()
    
    with tab4:
        show_performance_tab()
    
    with tab5:
        show_history_tab()

def show_active_options_tab():
    """Wyświetla aktywne opcje z działającymi przyciskami."""
    
    st.markdown("### 🟢 Aktywne opcje")
    
    options = OptionsRepository.get_all_options(include_closed=False)
    
    if options:
        for option in options:
            with st.expander(f"📋 {option['symbol']} {option['option_type']} ${option['strike_price']:.2f} - {option['expiry_date']}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**Premium/akcja:** ${option['premium_received']:.2f}")
                    premium_total = option['premium_received'] * option['quantity'] * 100
                    st.write(f"**Premium całkowite:** ${premium_total:.2f}")
                    st.write(f"**Kontrakty:** {option['quantity']}")
                
                with col2:
                    st.write(f"**Strike:** ${option['strike_price']:.2f}")
                    st.write(f"**Otwarcie:** {option['open_date']}")
                    st.write(f"**Status:** {option['status']}")
                    if option.get('current_price_usd'):
                        st.write(f"**Cena akcji:** ${option['current_price_usd']:.2f}")
                
                with col3:
                    st.markdown("#### 🔧 Działania")
                    
                    # Buyback
                    buyback_price_per_share = st.number_input(
                        "Cena buyback/akcja:", 
                        min_value=0.01, 
                        value=max(0.01, option['premium_received'] / 2),
                        step=0.01,
                        key=f"buyback_price_{option['id']}"
                    )
                    total_buyback = buyback_price_per_share * option['quantity'] * 100
                    st.caption(f"Całkowity koszt: ${total_buyback:.2f}")
                    
                    if st.button("🔄 Buyback", key=f"buyback_{option['id']}"):
                        if OptionsRepository.buyback_option(option['id'], buyback_price_per_share):
                            st.success(f"✅ Opcja odkupiona za ${total_buyback:.2f}")
                            st.rerun()
                        else:
                            st.error("❌ Błąd buyback")
                    
                    # Expire
                    if st.button("📅 Wygasła", key=f"expire_{option['id']}"):
                        if OptionsRepository.expire_option(option['id']):
                            st.success("✅ Opcja oznaczona jako wygasła")
                            st.rerun()
                        else:
                            st.error("❌ Błąd expire")
                    
                    # Delete - działający system
                    delete_confirm_key = f"delete_confirm_{option['id']}"
                    
                    if st.button("🗑️ Usuń", key=f"delete_btn_{option['id']}", type="secondary"):
                        st.session_state[delete_confirm_key] = True
                    
                    if st.session_state.get(delete_confirm_key, False):
                        st.warning("⚠️ Usunięcie opcji jest nieodwracalne!")
                        
                        if st.checkbox(f"Potwierdzam usunięcie opcji {option['symbol']}", key=f"confirm_{option['id']}"):
                            col_del1, col_del2 = st.columns(2)
                            
                            with col_del1:
                                if st.button("✅ USUŃ", key=f"final_delete_{option['id']}", type="primary"):
                                    if OptionsRepository.delete_option(option['id']):
                                        st.success("✅ Opcja usunięta!")
                                        if delete_confirm_key in st.session_state:
                                            del st.session_state[delete_confirm_key]
                                        st.rerun()
                                    else:
                                        st.error("❌ Błąd usuwania")
                            
                            with col_del2:
                                if st.button("❌ Anuluj", key=f"cancel_{option['id']}"):
                                    if delete_confirm_key in st.session_state:
                                        del st.session_state[delete_confirm_key]
                                    st.rerun()
    else:
        st.info("Brak aktywnych opcji. Dodaj pierwszą opcję w zakładce '➕ Dodaj opcję'.")

def show_add_option_tab():
    """Formularz dodawania nowej opcji z poprawnym obliczaniem premium."""
    
    st.markdown("### ➕ Dodaj nową opcję")
    
    # Pobierz akcje
    stocks = OptionsRepository.get_stocks_for_options()
    
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
                format_func=lambda x: f"{x['symbol']} - {x['name']} (posiadasz: {x['quantity']})"
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
                value=selected_stock['current_price_usd'] if selected_stock.get('current_price_usd') else 100.0,
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
            # Premium otrzymane PER AKCJA
            premium_per_share = st.number_input(
                "Premium otrzymane (USD/akcja) *",
                min_value=0.01,
                value=1.0,
                step=0.01,
                format="%.2f",
                help="Premium jakie otrzymujesz za jedną akcję (nie za kontrakt)"
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
        
        # POPRAWIONE OBLICZENIA PREMIUM
        premium_per_contract = premium_per_share * 100  # Premium za 1 kontrakt (100 akcji)
        total_premium = premium_per_contract * quantity   # Całkowite premium za wszystkie kontrakty
        net_premium = total_premium - commission
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"💰 Premium/kontrakt: {format_currency(premium_per_contract)}")
        with col2:
            st.info(f"📊 Premium całkowite: {format_currency(total_premium)}")
        with col3:
            st.info(f"💎 Premium netto: {format_currency(net_premium)}")
        
        # Wyjaśnienie
        st.caption(f"💡 {format_currency(premium_per_share)}/akcja × 100 akcji/kontrakt × {quantity} kontrakt = {format_currency(total_premium)} całkowite")
        
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
                    premium_received=premium_per_share,  # Zapisujemy premium PER AKCJA
                    quantity=quantity,
                    open_date=open_date,
                    commission=commission,
                    notes=notes
                )
                
                st.success(f"✅ Opcja została dodana! (ID: {option_id})")
                st.success(f"💰 Otrzymane premium: {format_currency(total_premium)}")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Błąd podczas dodawania opcji: {str(e)}")

def show_expiring_options_tab():
    """Wyświetla opcje wygasające."""
    
    st.markdown("### ⚠️ Opcje wygasające")
    
    days_ahead = st.selectbox(
        "Pokaż opcje wygasające w ciągu:",
        [7, 14, 30, 60],
        format_func=lambda x: f"{x} dni"
    )
    
    expiring_options = OptionsRepository.get_expiring_options(days_ahead)
    
    if expiring_options:
        st.warning(f"⚠️ {len(expiring_options)} opcji wygasa w ciągu {days_ahead} dni!")
        
        for option in expiring_options:
            with st.expander(f"⚠️ {option['symbol']} {option['option_type']} ${option['strike_price']:.2f} - wygasa {option['expiry_date']}"):
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Dni do wygaśnięcia:** {option['days_to_expiry']:.0f}")
                    st.write(f"**Premium otrzymane:** ${option['premium_received']:.2f}/akcja")
                    st.write(f"**Kontrakty:** {option['quantity']}")
                
                with col2:
                    if option.get('current_price_usd'):
                        current_price = option['current_price_usd']
                        strike_price = option['strike_price']
                        
                        if option['option_type'] == 'CALL':
                            if current_price > strike_price:
                                st.error("🔴 W pieniądzu - ryzyko przydziału!")
                            else:
                                st.success("🟢 Poza pieniądzem")
                        else:  # PUT
                            if current_price < strike_price:
                                st.error("🔴 W pieniądzu - ryzyko przydziału!")
                            else:
                                st.success("🟢 Poza pieniądzem")
    else:
        st.success(f"✅ Brak opcji wygasających w ciągu {days_ahead} dni")

def show_performance_tab():
    """Wyświetla wydajność opcji."""
    
    st.markdown("### 📊 Wydajność opcji")
    
    # Wybór roku
    current_year = datetime.now().year
    selected_year = st.selectbox(
        "Rok",
        options=list(range(current_year, 2020, -1)),
        index=0
    )
    
    # Pobierz dochód z opcji
    yearly_income = OptionsRepository.calculate_option_income(selected_year)
    
    if yearly_income and yearly_income.get('total_contracts', 0) > 0:
        # Podsumowanie
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📋 Kontrakty", yearly_income.get('total_contracts', 0))
        
        with col2:
            st.metric("💰 Łączne premium", format_currency(yearly_income.get('total_premium', 0)))
        
        with col3:
            st.metric("📅 Premium 2025", format_currency(yearly_income.get('total_premium', 0)))
        
        with col4:
            realized = yearly_income.get('expired_premium', 0) + yearly_income.get('assigned_premium', 0)
            st.metric("✅ Premium zrealizowane", format_currency(realized))
    
    else:
        st.info(f"Brak opcji w {selected_year} roku.")

def show_history_tab():
    """Wyświetla historię opcji z możliwością usuwania."""
    
    st.markdown("### 📋 Historia opcji")
    
    # Pobierz wszystkie opcje
    all_options = OptionsRepository.get_all_options(include_closed=True)
    
    if all_options:
        # Tabela z opcjami
        for option in all_options:
            status_icon = {
                'OPEN': '🟢',
                'CLOSED': '🔵', 
                'EXPIRED': '🟡',
                'ASSIGNED': '🔴'
            }.get(option['status'], '⚪')
            
            with st.expander(f"{status_icon} {option['symbol']} {option['option_type']} ${option['strike_price']:.2f} - {option['open_date']} ({option['status']})"):
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**Premium/akcja:** ${option['premium_received']:.2f}")
                    premium_total = option['premium_received'] * option['quantity'] * 100
                    st.write(f"**Premium całkowite:** ${premium_total:.2f}")
                    st.write(f"**Kontrakty:** {option['quantity']}")
                    st.write(f"**Status:** {option['status']}")
                
                with col2:
                    st.write(f"**Strike:** ${option['strike_price']:.2f}")
                    st.write(f"**Otwarcie:** {option['open_date']}")
                    if option.get('close_date'):
                        st.write(f"**Zamknięcie:** {option['close_date']}")
                    st.write(f"**Wygaśnięcie:** {option['expiry_date']}")
                
                with col3:
                    # Usuwanie opcji z historii
                    st.markdown("#### 🗑️ Zarządzanie")
                    
                    delete_key = f"history_delete_{option['id']}"
                    
                    if st.button("🗑️ Usuń z historii", key=f"hist_del_{option['id']}", type="secondary"):
                        st.session_state[delete_key] = True
                    
                    if st.session_state.get(delete_key, False):
                        st.warning("⚠️ Usunięcie opcji z bazy jest nieodwracalne!")
                        
                        if st.checkbox(f"Potwierdzam usunięcie", key=f"hist_confirm_{option['id']}"):
                            col_a, col_b = st.columns(2)
                            
                            with col_a:
                                if st.button("✅ USUŃ", key=f"hist_final_{option['id']}", type="primary"):
                                    if OptionsRepository.delete_option(option['id']):
                                        st.success("✅ Opcja usunięta z bazy!")
                                        if delete_key in st.session_state:
                                            del st.session_state[delete_key]
                                        st.rerun()
                                    else:
                                        st.error("❌ Błąd usuwania")
                            
                            with col_b:
                                if st.button("❌ Anuluj", key=f"hist_cancel_{option['id']}"):
                                    if delete_key in st.session_state:
                                        del st.session_state[delete_key]
                                    st.rerun()
    else:
        st.info("Brak opcji w historii.")