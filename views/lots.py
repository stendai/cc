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
        
        # Przycisk do migracji danych - NAPRAWIONY IMPORT
        if st.button("🔄 Utwórz/Napraw tabele lotów"):
            try:
                # Import z db.py zamiast nieistniejącego modułu
                from db import check_database_structure, init_database
                
                # Re-inicjalizuj bazę z nowymi tabelami
                init_database()
                
                # Sprawdź strukturę
                check_database_structure()
                
                st.success("✅ Struktura bazy naprawiona! Odśwież stronę.")
                st.rerun()
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
        
        # NOWE: Dodaj datę kursu NBP (jeden dzień przed datą zakupu)
        display_df['nbp_rate_date'] = (pd.to_datetime(df['purchase_date']) - pd.Timedelta(days=1)).dt.strftime('%d.%m.%Y')
        
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
                'usd_pln_rate', 'nbp_rate_date', 'remaining_value_usd', 'remaining_value_pln'
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
                'nbp_rate_date': 'Data kursu NBP',
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
        
        # Przycisk do migracji danych - UPROSZCZONY
        if st.button("🔄 Zmigruj istniejące transakcje do systemu lotów"):
            st.info("💡 Migracja będzie dostępna po pełnym wdrożeniu systemu lotów.")

def show_summary_tab():
    """Wyświetla podsumowanie lotów."""
    
    st.markdown("### 📊 Podsumowanie portfela według lotów")
    
    try:
        # Pobierz wszystkie aktywne loty
        lots = StockLotsRepository.get_all_lots(include_closed=False)
        
        if lots:
            df = pd.DataFrame(lots)
            
            # Grupuj według symboli
            summary_by_stock = df.groupby('symbol').agg({
                'remaining_quantity': 'sum',
                'remaining_value_usd': 'sum',
                'remaining_value_pln': 'sum'
            }).reset_index()
            
            # Formatowanie
            display_summary = summary_by_stock.copy()
            display_summary['remaining_value_usd'] = display_summary['remaining_value_usd'].apply(format_currency)
            display_summary['remaining_value_pln'] = display_summary['remaining_value_pln'].apply(lambda x: format_currency(x, "PLN"))
            
            st.dataframe(
                display_summary.rename(columns={
                    'symbol': 'Symbol akcji',
                    'remaining_quantity': 'Posiadane akcje',
                    'remaining_value_usd': 'Wartość USD',
                    'remaining_value_pln': 'Wartość PLN'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Wykresy
            col1, col2 = st.columns(2)
            
            with col1:
                fig_pie = px.pie(
                    summary_by_stock,
                    values='remaining_value_pln',
                    names='symbol',
                    title="Alokacja portfela (PLN)"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                fig_bar = px.bar(
                    summary_by_stock,
                    x='symbol',
                    y='remaining_quantity',
                    title="Ilość akcji według symboli"
                )
                st.plotly_chart(fig_bar, use_container_width=True)
        
        else:
            st.info("Brak aktywnych lotów w portfelu.")
            
    except Exception as e:
        st.error(f"❌ Błąd przy generowaniu podsumowania: {e}")


def show_realized_gains_tab():
    """Wyświetla zrealizowane zyski/straty."""
    
    st.markdown("### 💰 Zrealizowane zyski/straty")
    
    # Wybór roku
    current_year = datetime.now().year
    year_filter = st.selectbox(
        "Rok",
        ["Wszystkie"] + [str(year) for year in range(current_year, 2020, -1)],
        key="realized_gains_year_filter"
    )
    
    # ROZSZERZONE POBIERANIE DANYCH - z kursami zakupu i sprzedaży
    try:
        from db import execute_query
        
        # Zapytanie z dodatkowymi danymi o kursach
        query = """
            SELECT 
                sls.*,
                sl.lot_number,
                sl.purchase_date,
                sl.purchase_price_usd,
                sl.purchase_price_pln,
                sl.usd_pln_rate as purchase_usd_pln_rate,
                s.symbol
            FROM stock_lot_sales sls
            JOIN stock_lots sl ON sls.lot_id = sl.id
            JOIN stocks s ON sl.stock_id = s.id
        """
        
        params = []
        if year_filter != "Wszystkie":
            query += " WHERE strftime('%Y', sls.sale_date) = ?"
            params.append(year_filter)
        
        query += " ORDER BY sls.sale_date DESC"
        
        sales_data = execute_query(query, tuple(params))
        
        if sales_data:
            df = pd.DataFrame([dict(row) for row in sales_data])
            
            # Oblicz daty kursów NBP (D-1)
            df['purchase_nbp_date'] = (pd.to_datetime(df['purchase_date']) - pd.Timedelta(days=1))
            df['sale_nbp_date'] = (pd.to_datetime(df['sale_date']) - pd.Timedelta(days=1))
            
            # Formatowanie dla wyświetlenia
            display_df = df.copy()
            display_df['sale_date'] = pd.to_datetime(display_df['sale_date']).dt.strftime('%d.%m.%Y')
            display_df['purchase_date'] = pd.to_datetime(display_df['purchase_date']).dt.strftime('%d.%m.%Y')
            display_df['purchase_nbp_date'] = display_df['purchase_nbp_date'].dt.strftime('%d.%m.%Y')
            display_df['sale_nbp_date'] = display_df['sale_nbp_date'].dt.strftime('%d.%m.%Y')
            
            # Formatowanie kwot
            display_df['purchase_price_usd'] = display_df['purchase_price_usd'].apply(format_currency)
            display_df['purchase_price_pln'] = display_df['purchase_price_pln'].apply(lambda x: format_currency(x, "PLN"))
            display_df['sale_price_usd'] = display_df['sale_price_usd'].apply(format_currency)
            display_df['sale_price_pln'] = display_df['sale_price_pln'].apply(lambda x: format_currency(x, "PLN"))
            display_df['gain_loss_pln'] = display_df['gain_loss_pln'].apply(lambda x: format_gain_loss(x)[0] + " PLN")
            display_df['tax_due_pln'] = display_df['tax_due_pln'].apply(lambda x: format_currency(x, "PLN"))
            
            # Formatowanie kursów
            display_df['purchase_usd_pln_rate'] = display_df['purchase_usd_pln_rate'].apply(lambda x: f"{x:.4f}")
            display_df['usd_pln_rate'] = display_df['usd_pln_rate'].apply(lambda x: f"{x:.4f}")
            
            # PODZIELONE TABELE
            st.markdown("#### 📋 Szczegóły transakcji")
            
            # TABELA 1: Podstawowe info o transakcji
            st.markdown("**🔍 Informacje o sprzedaży:**")
            basic_df = display_df[[
                'sale_date', 'symbol', 'lot_number', 'quantity_sold', 'gain_loss_pln', 'tax_due_pln'
            ]].rename(columns={
                'sale_date': 'Data sprzedaży',
                'symbol': 'Symbol',
                'lot_number': 'Nr Lotu',
                'quantity_sold': 'Ilość',
                'gain_loss_pln': 'Zysk/Strata',
                'tax_due_pln': 'Podatek należny'
            })
            
            st.dataframe(basic_df, use_container_width=True, hide_index=True)
            
            # TABELA 2: Szczegóły kursów i cen
            st.markdown("**💱 Kursy NBP i ceny:**")
            rates_df = display_df[[
                'symbol', 'lot_number',
                'purchase_date', 'purchase_nbp_date', 'purchase_price_usd', 'purchase_price_pln', 'purchase_usd_pln_rate',
                'sale_nbp_date', 'sale_price_usd', 'sale_price_pln', 'usd_pln_rate'
            ]].rename(columns={
                'symbol': 'Symbol',
                'lot_number': 'Nr Lotu',
                'purchase_date': 'Data zakupu',
                'purchase_nbp_date': 'Kurs zakupu (D-1)',
                'purchase_price_usd': 'Zakup USD',
                'purchase_price_pln': 'Zakup PLN', 
                'purchase_usd_pln_rate': 'Kurs zakupu',
                'sale_nbp_date': 'Kurs sprzedaży (D-1)',
                'sale_price_usd': 'Sprzedaż USD',
                'sale_price_pln': 'Sprzedaż PLN',
                'usd_pln_rate': 'Kurs sprzedaży'
            })
            
            st.dataframe(rates_df, use_container_width=True, hide_index=True)
            
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
        
        else:
            filter_text = f" w {year_filter} roku" if year_filter != "Wszystkie" else ""
            st.info(f"Brak zrealizowanych sprzedaży{filter_text}.")
            
    except Exception as e:
        st.error(f"❌ Błąd pobierania danych: {e}")
        st.info("💡 Sprawdź czy tabela stock_lot_sales istnieje.")



def show_tax_tab():
    """Wyświetla kalkulacje podatkowe."""
    
    st.markdown("### 🧾 Rozliczenia podatkowe (FIFO)")
    
    # Wybór roku
    current_year = datetime.now().year
    tax_year = st.selectbox(
        "Rok podatkowy",
        options=list(range(current_year, 2020, -1)),
        index=0
    )
    
    st.info("💡 Kalkulacje podatkowe będą dostępne po pełnym wdrożeniu systemu sprzedaży FIFO.")

def show_analysis_tab():
    """Wyświetla analizę portfela według lotów."""
    
    st.markdown("### 🔍 Analiza portfela")
    
    st.info("💡 Szczegółowa analiza będzie dostępna w przyszłej wersji.")