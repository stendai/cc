import streamlit as st
import pandas as pd
from datetime import datetime, date
import plotly.express as px
import plotly.graph_objects as go

from repos.stock_repo import StockRepository
from services.pricing import pricing_service
from utils.formatting import (
    format_currency, format_percentage, format_gain_loss, 
    format_polish_date, get_status_color
)

def show():
    """Wyświetla stronę zarządzania akcjami."""
    
    st.markdown("## 📊 Zarządzanie Akcjami")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Portfel", "➕ Dodaj transakcję", "📋 Historia transakcji", "🔍 Analiza"
    ])
    
    with tab1:
        show_portfolio_tab()
    
    with tab2:
        show_add_transaction_tab()
    
    with tab3:
        show_transactions_history_tab()
    
    with tab4:
        show_analysis_tab()

def show_portfolio_tab():
    """Wyświetla portfolio akcji."""
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("### 💼 Aktualny portfel")
    
    with col2:
        if st.button("🔄 Aktualizuj ceny", key="update_prices"):
            with st.spinner("Aktualizowanie cen..."):
                results = pricing_service.update_all_stock_prices()
                success_count = sum(1 for success in results.values() if success)
                st.success(f"Zaktualizowano {success_count}/{len(results)} cen akcji")
                st.rerun()
    
    # Podsumowanie portfela
    summary = StockRepository.get_portfolio_summary()
    
    if summary and summary.get('total_positions', 0) > 0:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "💰 Wartość portfela", 
                format_currency(summary.get('current_value', 0))
            )
        
        with col2:
            st.metric(
                "💵 Koszt zakupu", 
                format_currency(summary.get('total_cost', 0))
            )
        
        with col3:
            gain_loss = summary.get('unrealized_gain_loss', 0)
            gain_text, gain_color = format_gain_loss(gain_loss)
            st.metric(
                "📈 Zysk/Strata", 
                gain_text
            )
        
        with col4:
            total_cost = summary.get('total_cost', 0)
            return_pct = (gain_loss / total_cost * 100) if total_cost > 0 else 0
            st.metric(
                "📊 Zwrot (%)", 
                format_percentage(return_pct)
            )
    
    # Tabela akcji
    stocks = StockRepository.get_all_stocks()
    
    if stocks:
        df = pd.DataFrame(stocks)
        
        # Oblicz dodatkowe kolumny
        df['total_cost'] = df['quantity'] * df['avg_price_usd']
        df['current_value'] = df['quantity'] * df['current_price_usd']
        df['unrealized_gain_loss'] = df['current_value'] - df['total_cost']
        df['return_pct'] = ((df['current_price_usd'] - df['avg_price_usd']) / df['avg_price_usd'] * 100).round(2)
        
        # Formatowanie dla wyświetlenia
        display_df = df.copy()
        display_df['avg_price_usd'] = display_df['avg_price_usd'].apply(format_currency)
        display_df['current_price_usd'] = display_df['current_price_usd'].apply(format_currency)
        display_df['total_cost'] = display_df['total_cost'].apply(format_currency)
        display_df['current_value'] = display_df['current_value'].apply(format_currency)
        display_df['unrealized_gain_loss'] = display_df['unrealized_gain_loss'].apply(lambda x: format_gain_loss(x)[0])
        display_df['return_pct'] = display_df['return_pct'].apply(format_percentage)
        
        st.dataframe(
            display_df[[
                'symbol', 'name', 'quantity', 'avg_price_usd', 'current_price_usd',
                'total_cost', 'current_value', 'unrealized_gain_loss', 'return_pct'
            ]].rename(columns={
                'symbol': 'Symbol',
                'name': 'Nazwa',
                'quantity': 'Ilość',
                'avg_price_usd': 'Śr. cena',
                'current_price_usd': 'Akt. cena',
                'total_cost': 'Koszt',
                'current_value': 'Wartość',
                'unrealized_gain_loss': 'Zysk/Strata',
                'return_pct': 'Zwrot %'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Wykres alokacji
        if not df.empty:
            fig = px.pie(
                df, 
                values='current_value', 
                names='symbol',
                title="Alokacja portfela według wartości"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.info("Brak akcji w portfelu. Dodaj pierwszą transakcję.")

def show_add_transaction_tab():
    """Formularz dodawania nowej transakcji."""
    
    st.markdown("### ➕ Dodaj nową transakcję")
    
    with st.form("add_transaction_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Symbol akcji
            symbol_input = st.text_input(
                "Symbol akcji *", 
                placeholder="np. AAPL",
                help="Symbol akcji (np. AAPL, MSFT, GOOGL)"
            ).upper()
            
            # Typ transakcji
            transaction_type = st.selectbox(
                "Typ transakcji *",
                ["BUY", "SELL"],
                format_func=lambda x: "Kupno" if x == "BUY" else "Sprzedaż"
            )
            
            # Ilość
            quantity = st.number_input(
                "Ilość akcji *",
                min_value=1,
                value=1,
                step=1
            )
        
        with col2:
            # Cena
            price = st.number_input(
                "Cena za akcję (USD) *",
                min_value=0.01,
                value=100.0,
                step=0.01,
                format="%.2f"
            )
            
            # Prowizja
            commission = st.number_input(
                "Prowizja (USD)",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.2f"
            )
            
            # Data transakcji
            transaction_date = st.date_input(
                "Data transakcji *",
                value=date.today(),
                max_value=date.today()
            )
        
        # Notatki
        notes = st.text_area(
            "Notatki",
            placeholder="Opcjonalne notatki o transakcji..."
        )
        
        # Podsumowanie transakcji
        total_value = quantity * price + commission
        st.info(f"💰 Całkowita wartość transakcji: {format_currency(total_value)}")
        
        # Przycisk dodania
        submitted = st.form_submit_button(
            "💾 Dodaj transakcję",
            type="primary",
            use_container_width=True
        )
        
        if submitted:
            if not symbol_input:
                st.error("Symbol akcji jest wymagany!")
                return
            
            try:
                # Sprawdź czy akcja istnieje w bazie
                stock = StockRepository.get_stock_by_symbol(symbol_input)
                
                if not stock:
                    # Pobierz informacje o akcji z API
                    with st.spinner(f"Pobieranie informacji o {symbol_input}..."):
                        stock_info = pricing_service.get_stock_info(symbol_input)
                        
                        if stock_info and stock_info.get('longName'):
                            # Dodaj nową akcję
                            stock_id = StockRepository.add_stock(
                                symbol_input, 
                                stock_info['longName']
                            )
                        else:
                            # Dodaj z podstawową nazwą
                            stock_id = StockRepository.add_stock(
                                symbol_input, 
                                f"{symbol_input} Stock"
                            )
                else:
                    stock_id = stock['id']
                
                # Dodaj transakcję
                transaction_id = StockRepository.add_transaction(
                    stock_id=stock_id,
                    transaction_type=transaction_type,
                    quantity=quantity,
                    price=price,
                    commission=commission,
                    transaction_date=transaction_date,
                    notes=notes
                )
                
                st.success(f"✅ Transakcja została dodana! (ID: {transaction_id})")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Błąd podczas dodawania transakcji: {str(e)}")

def show_transactions_history_tab():
    """Wyświetla historię wszystkich transakcji."""
    
    st.markdown("### 📋 Historia transakcji")
    
    # Filtry
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Filtr symbolu
        stocks = StockRepository.get_all_stocks()
        symbol_filter = st.selectbox(
            "Filtruj po symbolu",
            ["Wszystkie"] + [stock['symbol'] for stock in stocks]
        )
    
    with col2:
        # Filtr typu transakcji
        type_filter = st.selectbox(
            "Typ transakcji",
            ["Wszystkie", "BUY", "SELL"],
            format_func=lambda x: x if x == "Wszystkie" else ("Kupno" if x == "BUY" else "Sprzedaż")
        )
    
    with col3:
        # Liczba transakcji do wyświetlenia
        limit = st.selectbox(
            "Pokaż ostatnie",
            [10, 25, 50, 100, "Wszystkie"]
        )
    
    # Pobierz i wyfiltruj transakcje
    try:
        from db import execute_query
        
        # POPRAWIONE ZAPYTANIE - użyj pełnych nazw kolumn
        query = """
            SELECT 
                stock_transactions.id,
                stock_transactions.transaction_date,
                stocks.symbol,
                stocks.name,
                stock_transactions.transaction_type,
                stock_transactions.quantity,
                stock_transactions.price_usd,
                stock_transactions.commission_usd,
                (stock_transactions.quantity * stock_transactions.price_usd + stock_transactions.commission_usd) as total_value,
                stock_transactions.notes
            FROM stock_transactions
            JOIN stocks ON stock_transactions.stock_id = stocks.id
            WHERE 1=1
        """
        
        params = []
        
        if symbol_filter != "Wszystkie":
            query += " AND stocks.symbol = ?"
            params.append(symbol_filter)
        
        if type_filter != "Wszystkie":
            query += " AND stock_transactions.transaction_type = ?"
            params.append(type_filter)
        
        query += " ORDER BY stock_transactions.transaction_date DESC, stock_transactions.created_at DESC"
        
        if limit != "Wszystkie":
            query += f" LIMIT {limit}"
        
        transactions = execute_query(query, tuple(params))
        
        if transactions:
            df = pd.DataFrame([dict(t) for t in transactions])
            
            # Formatowanie
            df['transaction_date'] = pd.to_datetime(df['transaction_date']).dt.strftime('%d.%m.%Y')
            df['transaction_type'] = df['transaction_type'].map({
                'BUY': '🟢 Kupno',
                'SELL': '🔴 Sprzedaż'
            })
            df['price_usd'] = df['price_usd'].apply(format_currency)
            df['commission_usd'] = df['commission_usd'].apply(format_currency)
            df['total_value'] = df['total_value'].apply(format_currency)
            
            st.dataframe(
                df[[
                    'transaction_date', 'symbol', 'transaction_type', 
                    'quantity', 'price_usd', 'commission_usd', 'total_value', 'notes'
                ]].rename(columns={
                    'transaction_date': 'Data',
                    'symbol': 'Symbol',
                    'transaction_type': 'Typ',
                    'quantity': 'Ilość',
                    'price_usd': 'Cena',
                    'commission_usd': 'Prowizja',
                    'total_value': 'Wartość całkowita',
                    'notes': 'Notatki'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Statystyki
            st.markdown("#### 📊 Statystyki")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                buy_count = len([t for t in transactions if t['transaction_type'] == 'BUY'])
                st.metric("🟢 Transakcje kupna", buy_count)
            
            with col2:
                sell_count = len([t for t in transactions if t['transaction_type'] == 'SELL'])
                st.metric("🔴 Transakcje sprzedaży", sell_count)
            
            with col3:
                total_commission = sum(t['commission_usd'] for t in transactions)
                st.metric("💸 Łączne prowizje", format_currency(total_commission))
            
            with col4:
                avg_commission = total_commission / len(transactions) if transactions else 0
                st.metric("📊 Średnia prowizja", format_currency(avg_commission))
        
        else:
            st.info("Brak transakcji spełniających kryteria.")
            
    except Exception as e:
        st.error(f"Błąd pobierania transakcji: {e}")
        st.exception(e)  # Dodaj szczegóły błędu dla debugowania

def show_analysis_tab():
    """Wyświetla analizę portfela akcji."""
    
    st.markdown("### 🔍 Analiza portfela")
    
    # Wybór akcji do analizy
    stocks = StockRepository.get_all_stocks()
    
    if not stocks:
        st.info("Brak akcji w portfelu do analizy.")
        return
    
    selected_stock = st.selectbox(
        "Wybierz akcję do analizy",
        options=stocks,
        format_func=lambda x: f"{x['symbol']} - {x['name']}"
    )
    
    if selected_stock:
        col1, col2 = st.columns(2)
        
        with col1:
            show_stock_details(selected_stock)
        
        with col2:
            show_stock_chart(selected_stock['symbol'])
        
        # Historia transakcji dla wybranej akcji
        st.markdown(f"#### 📋 Historia transakcji - {selected_stock['symbol']}")
        stock_transactions = StockRepository.get_stock_transactions(selected_stock['id'])
        
        if stock_transactions:
            df = pd.DataFrame([dict(t) for t in stock_transactions])
            df['transaction_date'] = pd.to_datetime(df['transaction_date']).dt.strftime('%d.%m.%Y')
            df['transaction_type'] = df['transaction_type'].map({
                'BUY': '🟢 Kupno',
                'SELL': '🔴 Sprzedaż'
            })
            
            st.dataframe(
                df[['transaction_date', 'transaction_type', 'quantity', 'price_usd']].rename(columns={
                    'transaction_date': 'Data',
                    'transaction_type': 'Typ',
                    'quantity': 'Ilość',
                    'price_usd': 'Cena'
                }),
                use_container_width=True,
                hide_index=True
            )

def show_stock_details(stock):
    """Wyświetla szczegóły akcji."""
    
    st.markdown(f"#### 📈 {stock['symbol']} - Szczegóły")
    
    # Podstawowe metryki
    total_cost = stock['quantity'] * stock['avg_price_usd']
    current_value = stock['quantity'] * stock['current_price_usd']
    unrealized_gain = current_value - total_cost
    return_pct = (unrealized_gain / total_cost * 100) if total_cost > 0 else 0
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("💼 Ilość akcji", stock['quantity'])
        st.metric("💰 Średnia cena", format_currency(stock['avg_price_usd']))
        st.metric("💵 Koszt całkowity", format_currency(total_cost))
    
    with col2:
        st.metric("📊 Aktualna cena", format_currency(stock['current_price_usd']))
        st.metric("💎 Wartość aktualna", format_currency(current_value))
        
        gain_text, gain_color = format_gain_loss(unrealized_gain)
        st.metric("📈 Zysk/Strata", gain_text, delta=f"{return_pct:.1f}%")
    
    # Dodatkowe informacje z API
    with st.spinner("Pobieranie dodatkowych informacji..."):
        stock_info = pricing_service.get_stock_info(stock['symbol'])
        
        if stock_info:
            st.markdown("##### 📋 Informacje dodatkowe")
            
            info_col1, info_col2 = st.columns(2)
            
            with info_col1:
                if stock_info.get('sector'):
                    st.text(f"🏢 Sektor: {stock_info['sector']}")
                if stock_info.get('industry'):
                    st.text(f"🏭 Branża: {stock_info['industry']}")
                if stock_info.get('marketCap'):
                    st.text(f"💰 Kapitalizacja: {format_currency(stock_info['marketCap'])}")
            
            with info_col2:
                if stock_info.get('dividendYield'):
                    st.text(f"💎 Dywidenda: {format_percentage(stock_info['dividendYield'] * 100)}")
                if stock_info.get('trailingPE'):
                    st.text(f"📊 P/E: {stock_info['trailingPE']:.2f}")
                if stock_info.get('beta'):
                    st.text(f"📈 Beta: {stock_info['beta']:.2f}")

def show_stock_chart(symbol):
    """Wyświetla wykres historyczny akcji."""
    
    st.markdown(f"#### 📊 Wykres - {symbol}")
    
    period = st.selectbox(
        "Okres",
        ["1mo", "3mo", "6mo", "1y", "2y"],
        format_func=lambda x: {
            "1mo": "1 miesiąc",
            "3mo": "3 miesiące", 
            "6mo": "6 miesięcy",
            "1y": "1 rok",
            "2y": "2 lata"
        }[x]
    )
    
    with st.spinner("Pobieranie danych historycznych..."):
        hist_data = pricing_service.get_historical_data(symbol, period)
        
        if hist_data:
            df = pd.DataFrame({
                'Date': pd.to_datetime(hist_data['dates']),
                'Close': hist_data['close'],
                'Volume': hist_data['volume']
            })
            
            # Wykres ceny
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=df['Date'],
                y=df['Close'],
                mode='lines',
                name='Cena zamknięcia',
                line=dict(color='blue', width=2)
            ))
            
            fig.update_layout(
                title=f"Historia cen {symbol}",
                xaxis_title="Data",
                yaxis_title="Cena (USD)",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        else:
            st.error("Nie można pobrać danych historycznych.")