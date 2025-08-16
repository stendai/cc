import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import plotly.express as px
import plotly.graph_objects as go

from repos.stock_lots_repo import StockLotsRepository
from repos.stock_repo import StockRepository
from services.nbp import nbp_service
from utils.formatting import (
    format_currency, format_percentage, format_gain_loss, 
    format_polish_date
)

def show():
    """Wyświetla stronę zarządzania lotami akcji."""
    
    st.markdown("## 📦 Zarządzanie Lotami Akcji")
    
    st.info("""
    **🔍 System Lotów (FIFO)**
    
    Każdy zakup tworzy osobny lot z kursem NBP z dnia poprzedzającego transakcję.
    Sprzedaże są rozliczane metodą FIFO (pierwsze kupione, pierwsze sprzedane).
    Automatyczne przeliczenie podatków według polskich przepisów.
    """)
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📦 Aktywne loty", "📊 Podsumowanie", "💰 Zyski zrealizowane", "🧾 Podatki", "🔍 Analiza"
    ])
    
    with tab1:
        show_active_lots_tab()
    
    with tab2:
        show_summary_tab()
    
    with tab3:
        show_realized_gains_tab()
    
    with tab4:
        show_tax_tab()
    
    with tab5:
        show_analysis_tab()

def show_active_lots_tab():
    """Wyświetla aktywne loty akcji."""
    
    st.markdown("### 📦 Aktywne loty akcji")
    
    # Filtry
    col1, col2 = st.columns(2)
    
    with col1:
        stocks = StockRepository.get_all_stocks()
        stock_filter = st.selectbox(
            "Filtruj po akcji",
            ["Wszystkie"] + [f"{stock['symbol']} - {stock['name']}" for stock in stocks]
        )
        selected_stock_id = None
        if stock_filter != "Wszystkie":
            symbol = stock_filter.split(" - ")[0]
            selected_stock_id = next((s['id'] for s in stocks if s['symbol'] == symbol), None)
    
    with col2:
        include_closed = st.checkbox("Pokaż zamknięte loty", value=False)
    
    # Pobierz loty z obsługą błędów
    try:
        lots = StockLotsRepository.get_all_lots(
            stock_id=selected_stock_id, 
            include_closed=include_closed
        )
    except Exception as e:
        st.error(f"❌ Błąd pobierania lotów: {e}")
        st.info("💡 Sprawdź czy system lotów jest poprawnie skonfigurowany.")
        
        # Przycisk do migracji danych
        if st.button("🔄 Utwórz/Napraw tabele lotów"):
            try:
                from check_db_structure import check_database_structure
                if check_database_structure():
                    st.success("✅ Struktura bazy naprawiona! Odśwież stronę.")
                    st.rerun()
                else:
                    st.error("❌ Nie udało się naprawić struktury bazy")
            except Exception as repair_e:
                st.error(f"❌ Błąd naprawy: {repair_e}")
        return
    
    if lots:
        df = pd.DataFrame(lots)
        
        # Sortuj według akcji i daty zakupu
        df = df.sort_values(['symbol', 'purchase_date', 'lot_number'])
        
        # Formatowanie dla wyświetlenia
        display_df = df.copy()
        display_df['purchase_date'] = pd.to_datetime(display_df['purchase_date']).dt.strftime('%d.%m.%Y')
        display_df['purchase_price_usd'] = display_df['purchase_price_usd'].apply(format_currency)
        display_df['purchase_price_pln'] = display_df['purchase_price_pln'].apply(lambda x: format_currency(x, "PLN"))
        display_df['remaining_value_usd'] = display_df['remaining_value_usd'].apply(format_currency)
        display_df['remaining_value_pln'] = display_df['remaining_value_pln'].apply(lambda x: format_currency(x, "PLN"))
        display_df['usd_pln_rate'] = display_df['usd_pln_rate'].apply(lambda x: f"{x:.4f}")
        
        # Mapowanie statusów
        status_map = {
            'OPEN': '🟢 Otwarty',
            'PARTIAL': '🟡 Częściowy',
            'CLOSED': '🔴 Zamknięty'
        }
        display_df['calculated_status'] = display_df['calculated_status'].map(status_map)
        
        st.dataframe(
            display_df[[
                'symbol', 'lot_number', 'purchase_date', 'calculated_status',
                'quantity', 'remaining_quantity', 'purchase_price_usd', 'purchase_price_pln',
                'usd_pln_rate', 'remaining_value_usd', 'remaining_value_pln'
            ]].rename(columns={
                'symbol': 'Symbol',
                'lot_number': 'Nr Lotu',
                'purchase_date': 'Data zakupu',
                'calculated_status': 'Status',
                'quantity': 'Ilość kupiona',
                'remaining_quantity': 'Pozostało',
                'purchase_price_usd': 'Cena USD',
                'purchase_price_pln': 'Cena PLN',
                'usd_pln_rate': 'Kurs NBP',
                'remaining_value_usd': 'Wartość USD',
                'remaining_value_pln': 'Wartość PLN'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Statystyki
        st.markdown("#### 📊 Statystyki lotów")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_lots = len(df)
            active_lots = len(df[df['remaining_quantity'] > 0])
            st.metric("📦 Łączne loty", f"{active_lots}/{total_lots}")
        
        with col2:
            total_shares = df['remaining_quantity'].sum()
            st.metric("📊 Pozostałe akcje", int(total_shares))
        
        with col3:
            total_value_usd = df['remaining_value_usd'].sum()
            st.metric("💰 Wartość USD", format_currency(total_value_usd))
        
        with col4:
            total_value_pln = df['remaining_value_pln'].sum()
            st.metric("💰 Wartość PLN", format_currency(total_value_pln, "PLN"))
        
        # Wykres alokacji według lotów
        if not df[df['remaining_quantity'] > 0].empty:
            active_df = df[df['remaining_quantity'] > 0].copy()
            
            fig = px.treemap(
                active_df,
                path=['symbol', 'lot_number'],
                values='remaining_value_pln',
                title="Alokacja według lotów (wartość PLN)",
                hover_data=['purchase_date', 'remaining_quantity']
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.info("Brak lotów do wyświetlenia.")
        
        # Przycisk do migracji danych
        if st.button("🔄 Zmigruj istniejące transakcje do systemu lotów"):
            try:
                from db_lots_migration import add_lots_table
                add_lots_table()
                st.success("✅ Migracja zakończona! Odśwież stronę.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Błąd migracji: {e}")

def show_summary_tab():
    """Wyświetla podsumowanie lotów."""
    
    st.markdown("### 📊 Podsumowanie lotów")
    
    # Globalne podsumowanie
    summary = StockLotsRepository.get_lots_summary()
    
    if summary and summary.get('total_lots', 0) > 0:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📦 Łączne loty", summary.get('total_lots', 0))
            st.metric("🟢 Otwarte loty", summary.get('open_lots', 0))
        
        with col2:
            st.metric("📊 Akcje kupione", summary.get('total_shares_purchased', 0))
            st.metric("📈 Akcje pozostałe", summary.get('total_shares_remaining', 0))
        
        with col3:
            st.metric("💰 Wartość USD", format_currency(summary.get('total_value_usd', 0)))
            st.metric("💱 Średni kurs", f"{summary.get('avg_usd_rate', 0):.4f}")
        
        with col4:
            st.metric("💰 Wartość PLN", format_currency(summary.get('total_value_pln', 0), "PLN"))
        
        # Podsumowanie według akcji
        st.markdown("#### 📈 Podsumowanie według akcji")
        
        stocks = StockRepository.get_all_stocks()
        
        for stock in stocks:
            stock_summary = StockLotsRepository.get_lots_summary(stock['id'])
            
            if stock_summary.get('total_lots', 0) > 0:
                with st.expander(f"📊 {stock['symbol']} - {stock['name']}"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.text(f"Loty: {stock_summary.get('open_lots', 0)}/{stock_summary.get('total_lots', 0)}")
                        st.text(f"Akcje: {stock_summary.get('total_shares_remaining', 0)} szt.")
                    
                    with col2:
                        st.text(f"Wartość USD: {format_currency(stock_summary.get('total_value_usd', 0))}")
                        st.text(f"Wartość PLN: {format_currency(stock_summary.get('total_value_pln', 0), 'PLN')}")
                    
                    with col3:
                        avg_rate = stock_summary.get('avg_usd_rate', 0)
                        st.text(f"Średni kurs: {avg_rate:.4f}")
                        
                        # Porównaj z aktualnym kursem
                        current_rate = nbp_service.get_current_usd_rate()
                        if current_rate:
                            rate_diff = ((current_rate - avg_rate) / avg_rate * 100) if avg_rate > 0 else 0
                            st.text(f"Różnica kursu: {rate_diff:+.1f}%")
    
    else:
        st.info("Brak danych o lotach.")

def show_realized_gains_tab():
    """Wyświetla zrealizowane zyski/straty."""
    
    st.markdown("### 💰 Zrealizowane zyski/straty")
    
    # Wybór roku
    current_year = datetime.now().year
    year_filter = st.selectbox(
        "Rok",
        ["Wszystkie"] + [str(year) for year in range(current_year, 2020, -1)]
    )
    
    # Pobierz dane z obsługą błędów
    try:
        year_param = int(year_filter) if year_filter != "Wszystkie" else None
        realized_gains = StockLotsRepository.get_realized_gains_by_year(year_param)
    except Exception as e:
        st.error(f"❌ Błąd pobierania danych: {e}")
        st.info("💡 Sprawdź czy tabele lotów istnieją. Uruchom: python check_db_structure.py")
        return
    
    if realized_gains:
        df = pd.DataFrame(realized_gains)
        
        # Formatowanie
        display_df = df.copy()
        display_df['sale_date'] = pd.to_datetime(display_df['sale_date']).dt.strftime('%d.%m.%Y')
        display_df['purchase_date'] = pd.to_datetime(display_df['purchase_date']).dt.strftime('%d.%m.%Y')
        display_df['purchase_price_pln'] = display_df['purchase_price_pln'].apply(lambda x: format_currency(x, "PLN"))
        display_df['sale_price_pln'] = display_df['sale_price_pln'].apply(lambda x: format_currency(x, "PLN"))
        display_df['gain_loss_pln'] = display_df['gain_loss_pln'].apply(lambda x: format_gain_loss(x)[0] + " PLN")
        display_df['tax_due_pln'] = display_df['tax_due_pln'].apply(lambda x: format_currency(x, "PLN"))
        display_df['usd_pln_rate'] = display_df['usd_pln_rate'].apply(lambda x: f"{x:.4f}")
        
        st.dataframe(
            display_df[[
                'sale_date', 'symbol', 'lot_number', 'purchase_date', 'quantity_sold',
                'purchase_price_pln', 'sale_price_pln', 'gain_loss_pln', 'tax_due_pln', 'usd_pln_rate'
            ]].rename(columns={
                'sale_date': 'Data sprzedaży',
                'symbol': 'Symbol',
                'lot_number': 'Nr Lotu',
                'purchase_date': 'Data zakupu',
                'quantity_sold': 'Ilość',
                'purchase_price_pln': 'Cena zakupu PLN',
                'sale_price_pln': 'Cena sprzedaży PLN',
                'gain_loss_pln': 'Zysk/Strata',
                'tax_due_pln': 'Podatek należny',
                'usd_pln_rate': 'Kurs sprzedaży'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Podsumowanie
        st.markdown("#### 💰 Podsumowanie")
        
        total_gain_loss = df['gain_loss_pln'].sum()
        total_tax = df['tax_due_pln'].sum()
        total_sales = len(df)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📊 Sprzedaże", total_sales)
        
        with col2:
            st.metric("💰 Łączny wynik", format_gain_loss(total_gain_loss)[0] + " PLN")
        
        with col3:
            st.metric("🧾 Podatek należny", format_currency(total_tax, "PLN"))
        
        with col4:
            avg_gain = total_gain_loss / total_sales if total_sales > 0 else 0
            st.metric("📈 Średni zysk", format_gain_loss(avg_gain)[0] + " PLN")
        
        # Wykres zysków w czasie
        if not df.empty:
            df['sale_date_dt'] = pd.to_datetime(df['sale_date'])
            monthly_gains = df.groupby(df['sale_date_dt'].dt.to_period('M'))['gain_loss_pln'].sum().reset_index()
            monthly_gains['month'] = monthly_gains['sale_date_dt'].dt.strftime('%Y-%m')
            
            fig = px.bar(
                monthly_gains,
                x='month',
                y='gain_loss_pln',
                title="Miesięczne zyski/straty zrealizowane",
                color='gain_loss_pln',
                color_continuous_scale=['red', 'gray', 'green']
            )
            
            fig.add_hline(y=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.info(f"Brak zrealizowanych zysków/strat" + (f" w {year_filter} roku" if year_filter != "Wszystkie" else "") + ".")

def show_tax_tab():
    """Wyświetla podsumowanie podatkowe."""
    
    st.markdown("### 🧾 Podsumowanie podatkowe")
    
    # Wybór roku
    current_year = datetime.now().year
    tax_year = st.selectbox(
        "Rok podatkowy",
        options=list(range(current_year, 2020, -1)),
        index=0,
        key="tax_year_lots"
    )
    
    # Pobierz podsumowanie podatkowe
    tax_summary = StockLotsRepository.get_tax_summary_by_year(tax_year)
    
    if tax_summary and tax_summary.get('total_sales', 0) > 0:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📊 Transakcje sprzedaży", tax_summary.get('total_sales', 0))
        
        with col2:
            st.metric("📈 Akcje sprzedane", tax_summary.get('total_shares_sold', 0))
        
        with col3:
            total_gains = tax_summary.get('total_gains_pln', 0)
            st.metric("💰 Zyski", format_currency(total_gains, "PLN"))
        
        with col4:
            total_losses = abs(tax_summary.get('total_losses_pln', 0))
            st.metric("📉 Straty", format_currency(total_losses, "PLN"))
        
        # Główne metryki podatkowe
        st.markdown("#### 💰 Obliczenia podatkowe")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            net_gain_loss = tax_summary.get('total_gain_loss_pln', 0)
            st.metric(
                "📊 Wynik netto", 
                format_gain_loss(net_gain_loss)[0] + " PLN"
            )
        
        with col2:
            tax_due = tax_summary.get('total_tax_due_pln', 0)
            st.metric(
                "🧾 Podatek należny (19%)", 
                format_currency(tax_due, "PLN")
            )
        
        with col3:
            avg_rate = tax_summary.get('avg_usd_rate', 0)
            st.metric(
                "💱 Średni kurs USD/PLN", 
                f"{avg_rate:.4f}"
            )
        
        # Szczegółowa tabela
        st.markdown("#### 📋 Szczegółowe zestawienie podatkowe")
        
        realized_gains = StockLotsRepository.get_realized_gains_by_year(tax_year)
        
        if realized_gains:
            df = pd.DataFrame(realized_gains)
            
            # Grupuj według akcji
            summary_by_stock = df.groupby('symbol').agg({
                'quantity_sold': 'sum',
                'gain_loss_pln': 'sum',
                'tax_due_pln': 'sum'
            }).reset_index()
            
            # Formatowanie
            summary_by_stock['quantity_sold'] = summary_by_stock['quantity_sold'].astype(int)
            summary_by_stock['gain_loss_pln'] = summary_by_stock['gain_loss_pln'].apply(lambda x: format_gain_loss(x)[0] + " PLN")
            summary_by_stock['tax_due_pln'] = summary_by_stock['tax_due_pln'].apply(lambda x: format_currency(x, "PLN"))
            
            st.dataframe(
                summary_by_stock.rename(columns={
                    'symbol': 'Symbol akcji',
                    'quantity_sold': 'Sprzedane akcje',
                    'gain_loss_pln': 'Zysk/Strata PLN',
                    'tax_due_pln': 'Podatek należny PLN'
                }),
                use_container_width=True,
                hide_index=True
            )
        
        # Informacje o rozliczeniu
        st.markdown("#### ℹ️ Informacje o rozliczeniu podatkowym")
        
        st.info(f"""
        **📋 Zestawienie podatkowe za {tax_year} rok (System FIFO)**
        
        **Podstawowe informacje:**
        - Stawka podatku od zysków kapitałowych: **19%**
        - Metoda rozliczania: **FIFO** (pierwsze kupione, pierwsze sprzedane)
        - Kursy NBP: z dnia poprzedzającego sprzedaż
        - Straty można rozliczać z zyskami w tym samym roku
        
        **Wynik za {tax_year}:**
        - Wynik netto: **{format_gain_loss(net_gain_loss)[0]} PLN**
        - Podatek należny: **{format_currency(tax_due, "PLN")}**
        
        **Terminy:**
        - Zeznanie podatkowe: do 30 kwietnia {tax_year + 1}
        - Wpłata podatku: do 31 maja {tax_year + 1}
        
        ⚠️ **Uwaga:** To obliczenia szacunkowe. Skonsultuj się z doradcą podatkowym!
        """)
        
        # Przycisk eksportu
        if st.button("📄 Eksportuj zestawienie podatkowe"):
            st.info("Funkcja eksportu będzie dostępna w przyszłej wersji.")
    
    else:
        st.info(f"Brak transakcji sprzedaży w {tax_year} roku.")

def show_analysis_tab():
    """Wyświetla analizę portfela według lotów."""
    
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
        stock_lots = StockLotsRepository.get_all_lots(
            stock_id=selected_stock['id'], 
            include_closed=True
        )
        
        if stock_lots:
            df = pd.DataFrame(stock_lots)
            
            # Analiza kosztów według dat
            st.markdown(f"#### 📊 Analiza kosztów - {selected_stock['symbol']}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Średnie ceny zakupu w czasie
                df_sorted = df.sort_values('purchase_date')
                
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=pd.to_datetime(df_sorted['purchase_date']),
                    y=df_sorted['purchase_price_usd'],
                    mode='markers+lines',
                    name='Cena USD',
                    marker=dict(size=df_sorted['quantity']*2),
                    line=dict(color='blue')
                ))
                
                fig.update_layout(
                    title="Ceny zakupu w czasie",
                    xaxis_title="Data zakupu",
                    yaxis_title="Cena (USD)",
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Kursy USD/PLN w czasie
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=pd.to_datetime(df_sorted['purchase_date']),
                    y=df_sorted['usd_pln_rate'],
                    mode='markers+lines',
                    name='Kurs USD/PLN',
                    marker=dict(size=df_sorted['quantity']*2),
                    line=dict(color='green')
                ))
                
                fig.update_layout(
                    title="Kursy NBP w czasie zakupów",
                    xaxis_title="Data zakupu",
                    yaxis_title="Kurs USD/PLN",
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            # Symulacja sprzedaży FIFO
            st.markdown("#### 🎯 Symulacja sprzedaży FIFO")
            
            max_shares = df['remaining_quantity'].sum()
            if max_shares > 0:
                col1, col2 = st.columns(2)
                
                with col1:
                    shares_to_sell = st.number_input(
                        "Ilość akcji do sprzedaży",
                        min_value=1,
                        max_value=int(max_shares),
                        value=min(100, int(max_shares)),
                        step=1
                    )
                
                with col2:
                    sale_price = st.number_input(
                        "Cena sprzedaży (USD)",
                        min_value=0.01,
                        value=float(selected_stock['current_price_usd'] or 100),
                        step=0.01,
                        format="%.2f"
                    )
                
                if st.button("🔍 Podgląd sprzedaży FIFO"):
                    preview = StockLotsRepository.get_fifo_preview(
                        selected_stock['id'], 
                        shares_to_sell
                    )
                    
                    if preview:
                        preview_df = pd.DataFrame(preview)
                        
                        # Oblicz potencjalne zyski/straty
                        current_rate = nbp_service.get_current_usd_rate() or 4.0
                        sale_price_pln = sale_price * current_rate
                        
                        preview_df['sale_price_pln'] = sale_price_pln
                        preview_df['gain_loss_usd'] = (sale_price - preview_df['purchase_price_usd']) * preview_df['quantity_to_sell']
                        preview_df['gain_loss_pln'] = (sale_price_pln - preview_df['purchase_price_pln']) * preview_df['quantity_to_sell']
                        preview_df['tax_due_pln'] = preview_df['gain_loss_pln'].apply(lambda x: max(0, x * 0.19))
                        
                        # Formatowanie
                        display_preview = preview_df.copy()
                        display_preview['purchase_date'] = pd.to_datetime(display_preview['purchase_date']).dt.strftime('%d.%m.%Y')
                        display_preview['purchase_price_usd'] = display_preview['purchase_price_usd'].apply(format_currency)
                        display_preview['purchase_price_pln'] = display_preview['purchase_price_pln'].apply(lambda x: format_currency(x, "PLN"))
                        display_preview['gain_loss_pln'] = display_preview['gain_loss_pln'].apply(lambda x: format_gain_loss(x)[0] + " PLN")
                        display_preview['tax_due_pln'] = display_preview['tax_due_pln'].apply(lambda x: format_currency(x, "PLN"))
                        
                        st.dataframe(
                            display_preview[[
                                'lot_number', 'purchase_date', 'quantity_to_sell', 'remaining_after_sale',
                                'purchase_price_usd', 'purchase_price_pln', 'gain_loss_pln', 'tax_due_pln'
                            ]].rename(columns={
                                'lot_number': 'Nr Lotu',
                                'purchase_date': 'Data zakupu',
                                'quantity_to_sell': 'Do sprzedaży',
                                'remaining_after_sale': 'Pozostanie',
                                'purchase_price_usd': 'Cena zakupu USD',
                                'purchase_price_pln': 'Cena zakupu PLN',
                                'gain_loss_pln': 'Zysk/Strata',
                                'tax_due_pln': 'Podatek należny'
                            }),
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Podsumowanie symulacji
                        total_gain_loss = preview_df['gain_loss_pln'].sum()
                        total_tax = preview_df['tax_due_pln'].sum()
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("💰 Łączny wynik", format_gain_loss(total_gain_loss)[0] + " PLN")
                        
                        with col2:
                            st.metric("🧾 Podatek należny", format_currency(total_tax, "PLN"))
                        
                        with col3:
                            net_proceeds = (shares_to_sell * sale_price_pln) - total_tax
                            st.metric("💎 Wpływy netto", format_currency(net_proceeds, "PLN"))
        
        else:
            st.info(f"Brak lotów dla akcji {selected_stock['symbol']}")