import streamlit as st
import pandas as pd
from datetime import datetime, date
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from repos.stock_repo import StockRepository
from repos.options_repo import OptionsRepository
from repos.dividends_repo import DividendsRepository
from repos.cashflow_repo import CashflowRepository
from services.pricing import pricing_service
from services.nbp import nbp_service
from utils.formatting import format_currency, format_percentage, format_gain_loss

def show():
    """Wyświetla dashboard główny."""
    
    st.markdown("## 📊 Przegląd Portfela")
    
    # Przyciski akcji
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔄 Aktualizuj ceny", type="primary"):
            with st.spinner("Aktualizowanie cen..."):
                results = pricing_service.update_all_stock_prices()
                success_count = sum(1 for success in results.values() if success)
                st.success(f"Zaktualizowano {success_count}/{len(results)} cen akcji")
                st.rerun()
    
    with col2:
        if st.button("💱 Aktualizuj kursy"):
            with st.spinner("Pobieranie kursów NBP..."):
                results = nbp_service.update_current_rates(['USD'])
                if results.get('USD', False):
                    st.success("Kurs USD zaktualizowany")
                else:
                    st.error("Błąd aktualizacji kursu USD")
    
    with col3:
        current_usd_rate = nbp_service.get_current_usd_rate()
        if current_usd_rate:
            st.metric("USD/PLN", f"{current_usd_rate:.4f}")
        else:
            st.metric("USD/PLN", "N/A")
    
    with col4:
        st.metric("Status rynku", "🟢 Otwarty" if datetime.now().hour < 22 else "🔴 Zamknięty")
    
    st.markdown("---")
    
    # Sekcja podsumowania portfela
    show_portfolio_summary()
    
    st.markdown("---")
    
    # Wykresy i analiza
    col1, col2 = st.columns(2)
    
    with col1:
        show_portfolio_allocation()
    
    with col2:
        show_performance_chart()
    
    st.markdown("---")
    
    # Tabele z danymi
    col1, col2 = st.columns(2)
    
    with col1:
        show_recent_transactions()
    
    with col2:
        show_upcoming_events()

def show_portfolio_summary():
    """Wyświetla podsumowanie portfela."""
    
    # Pobierz dane
    stock_summary = StockRepository.get_portfolio_summary()
    options_summary = OptionsRepository.get_options_summary()
    
    # Oblicz kluczowe metryki
    total_cost = stock_summary.get('total_cost', 0) or 0
    current_value = stock_summary.get('current_value', 0) or 0
    unrealized_gain_loss = stock_summary.get('unrealized_gain_loss', 0) or 0
    total_premium = options_summary.get('total_premium_received', 0) or 0
    
    # Metryki główne
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "💰 Wartość portfela", 
            format_currency(current_value),
            delta=format_currency(unrealized_gain_loss) if unrealized_gain_loss != 0 else None
        )
    
    with col2:
        st.metric(
            "💵 Koszt zakupu", 
            format_currency(total_cost)
        )
    
    with col3:
        unrealized_text, unrealized_color = format_gain_loss(unrealized_gain_loss)
        return_pct = (unrealized_gain_loss / total_cost * 100) if total_cost > 0 else 0
        st.metric(
            "📈 Zysk/Strata", 
            unrealized_text,
            delta=f"{return_pct:.1f}%"
        )
    
    with col4:
        st.metric(
            "🎯 Premium opcje", 
            format_currency(total_premium)
        )
    
    with col5:
        total_positions = stock_summary.get('total_positions', 0) or 0
        open_options = options_summary.get('open_options', 0) or 0
        st.metric(
            "📊 Pozycje", 
            f"{total_positions} akcje / {open_options} opcje"
        )
    
    # Dodatkowe metryki
    if current_usd_rate := nbp_service.get_current_usd_rate():
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "💰 Wartość w PLN",
                format_currency(current_value * current_usd_rate, "PLN")
            )
        
        with col2:
            st.metric(
                "📈 Zysk/Strata w PLN",
                format_currency(unrealized_gain_loss * current_usd_rate, "PLN")
            )
        
        with col3:
            daily_change = 0  # TODO: Implement daily change calculation
            st.metric(
                "📅 Zmiana dzienna",
                format_currency(daily_change),
                delta=f"{(daily_change/current_value*100):.2f}%" if current_value > 0 else "0%"
            )

def show_portfolio_allocation():
    """Wyświetla wykres alokacji portfela."""
    
    st.markdown("### 🥧 Alokacja portfela")
    
    stocks = StockRepository.get_all_stocks()
    
    if not stocks:
        st.info("Brak akcji w portfelu")
        return
    
    # Przygotuj dane do wykresu
    df = pd.DataFrame(stocks)
    df['current_value'] = df['quantity'] * df['current_price_usd']
    df = df[df['current_value'] > 0]
    
    if df.empty:
        st.info("Brak danych do wyświetlenia")
        return
    
    # Wykres kołowy
    fig = px.pie(
        df, 
        values='current_value', 
        names='symbol',
        title="Alokacja według wartości akcji",
        hover_data=['quantity'],
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    fig.update_traces(
        textposition='inside', 
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>' +
                     'Wartość: $%{value:,.2f}<br>' +
                     'Udział: %{percent}<br>' +
                     '<extra></extra>'
    )
    
    fig.update_layout(height=400, showlegend=True)
    
    st.plotly_chart(fig, use_container_width=True)

def show_performance_chart():
    """Wyświetla wykres wydajności akcji."""
    
    st.markdown("### 📈 Wydajność akcji")
    
    performance_data = StockRepository.get_stock_performance()
    
    if not performance_data:
        st.info("Brak danych o wydajności")
        return
    
    df = pd.DataFrame(performance_data)
    df = df.dropna(subset=['return_pct'])
    
    if df.empty:
        st.info("Brak danych do wyświetlenia")
        return
    
    # Wykres słupkowy wydajności
    fig = go.Figure()
    
    colors = ['green' if x >= 0 else 'red' for x in df['return_pct']]
    
    fig.add_trace(go.Bar(
        x=df['symbol'],
        y=df['return_pct'],
        marker_color=colors,
        text=[f"{x:.1f}%" for x in df['return_pct']],
        textposition='auto',
        hovertemplate='<b>%{x}</b><br>' +
                     'Zwrot: %{y:.1f}%<br>' +
                     '<extra></extra>'
    ))
    
    fig.update_layout(
        title="Zwrot z inwestycji (%)",
        xaxis_title="Symbol akcji",
        yaxis_title="Zwrot (%)",
        height=400,
        showlegend=False
    )
    
    # Dodaj linię 0%
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    st.plotly_chart(fig, use_container_width=True)

def show_recent_transactions():
    """Wyświetla ostatnie transakcje."""
    
    st.markdown("### 📋 Ostatnie transakcje")
    
    # Pobierz ostatnie transakcje akcji - POPRAWIONE ZAPYTANIE
    try:
        query = """
            SELECT 
                t.transaction_date as data,
                'Akcje' as typ,
                s.symbol,
                t.transaction_type as operacja,
                t.quantity as ilosc,
                t.price_usd as cena,
                (t.quantity * t.price_usd) as wartosc
            FROM stock_transactions t
            JOIN stocks s ON t.stock_id = s.id
            ORDER BY t.transaction_date DESC, t.created_at DESC
            LIMIT 10
        """
        
        from db import execute_query
        transactions = execute_query(query)
        
        if transactions:
            df = pd.DataFrame([dict(t) for t in transactions])
            df['data'] = pd.to_datetime(df['data']).dt.strftime('%d.%m.%Y')
            df['wartosc'] = df['wartosc'].apply(lambda x: f"${x:,.2f}")
            df['cena'] = df['cena'].apply(lambda x: f"${x:.2f}")
            
            st.dataframe(
                df[['data', 'typ', 'symbol', 'operacja', 'ilosc', 'cena', 'wartosc']].rename(columns={
                    'data': 'Data',
                    'typ': 'Typ',
                    'symbol': 'Symbol',
                    'operacja': 'Operacja',
                    'ilosc': 'Ilość',
                    'cena': 'Cena',
                    'wartosc': 'Wartość'
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Brak ostatnich transakcji")
            
    except Exception as e:
        st.error(f"Błąd pobierania transakcji: {e}")

def show_upcoming_events():
    """Wyświetla nadchodzące wydarzenia."""
    
    st.markdown("### 📅 Nadchodzące wydarzenia")
    
    try:
        # Wygasające opcje w ciągu 30 dni
        expiring_options = OptionsRepository.get_expiring_options(30)
        
        if expiring_options:
            st.markdown("#### ⚠️ Wygasające opcje")
            
            # Pokaż tylko najbliższe 5
            recent_expiring = expiring_options[:5]
            
            for option in recent_expiring:
                days_left = int(option['days_to_expiry']) if option['days_to_expiry'] else 0
                
                if days_left <= 0:
                    urgency = "🚨 Wygasła"
                elif days_left <= 3:
                    urgency = "🔴 Bardzo pilne"
                elif days_left <= 7:
                    urgency = "🟠 Pilne"
                else:
                    urgency = "🟡 Uwaga"
                
                st.text(f"{urgency} {option['symbol']} {option['option_type']} ${option['strike_price']:.2f} - {days_left} dni")
        
        # Stan konta i alerty
        account_balance = CashflowRepository.get_account_balance()
        
        st.markdown("#### 💰 Stan konta")
        st.metric("Dostępne środki", format_currency(account_balance))
        
        if account_balance < 0:
            st.warning("⚠️ Ujemny stan konta!")
        elif account_balance < 1000:
            st.info("💡 Niski stan środków")
        
        # Sugestie akcji
        st.markdown("#### 💡 Sugestie")
        
        suggestions = []
        
        # Sprawdź czy są akcje bez ustawionej ceny
        stocks = StockRepository.get_all_stocks()
        outdated_prices = [s for s in stocks if s['current_price_usd'] == 0]
        
        if outdated_prices:
            suggestions.append("🔄 Zaktualizuj ceny akcji")
        
        if not expiring_options:
            suggestions.append("🎯 Rozważ sprzedaż opcji")
        
        if account_balance > 5000:
            suggestions.append("📈 Rozważ nowe inwestycje")
        
        for suggestion in suggestions:
            st.text(suggestion)
        
        if not suggestions:
            st.text("✅ Wszystko wygląda dobrze!")
            
    except Exception as e:
        st.error(f"Błąd pobierania wydarzeń: {e}")