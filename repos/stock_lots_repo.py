from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime, timedelta
from db import execute_query, execute_insert, execute_update

class StockLotsRepository:
    
    
    @staticmethod
    def get_all_lots(stock_id: int = None, include_closed: bool = False) -> List[Dict[str, Any]]:
        """Pobiera wszystkie loty akcji."""
        query = """
            SELECT 
                sl.*,
                s.symbol,
                s.name as stock_name,
                st.transaction_date as purchase_date_original,
                CASE 
                    WHEN sl.remaining_quantity = 0 THEN 'CLOSED'
                    WHEN sl.remaining_quantity < sl.quantity THEN 'PARTIAL'
                    ELSE 'OPEN'
                END as calculated_status,
                (sl.purchase_price_pln * sl.remaining_quantity) as remaining_value_pln,
                (sl.purchase_price_usd * sl.remaining_quantity) as remaining_value_usd
            FROM stock_lots sl
            JOIN stocks s ON sl.stock_id = s.id
            JOIN stock_transactions st ON sl.transaction_id = st.id
        """
        
        params = []
        conditions = []
        
        if stock_id:
            conditions.append("sl.stock_id = ?")
            params.append(stock_id)
        
        if not include_closed:
            conditions.append("sl.remaining_quantity > 0")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY s.symbol, sl.purchase_date, sl.lot_number"
        
        return [dict(row) for row in execute_query(query, tuple(params))]
    
    @staticmethod
    def create_lot_from_purchase(stock_id: int, transaction_id: int, 
                                quantity: int, price_usd: float, 
                                commission_usd: float, purchase_date: date,
                                usd_pln_rate: float) -> int:
        """Tworzy nowy lot z transakcji kupna."""
        
        # Pobierz kolejny numer lotu dla tej akcji
        lot_number_query = """
            SELECT COALESCE(MAX(lot_number), 0) + 1 as next_lot_number
            FROM stock_lots
            WHERE stock_id = ?
        """
        result = execute_query(lot_number_query, (stock_id,))
        lot_number = result[0]['next_lot_number']
        
        # Oblicz ceny w PLN
        purchase_price_pln = price_usd * usd_pln_rate
        commission_pln = commission_usd * usd_pln_rate
        
        # Utwórz lot
        query = """
            INSERT INTO stock_lots 
            (stock_id, transaction_id, lot_number, purchase_date, quantity, 
             remaining_quantity, purchase_price_usd, purchase_price_pln, 
             commission_usd, commission_pln, usd_pln_rate, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
        """
        
        return execute_insert(query, (
            stock_id, transaction_id, lot_number, purchase_date,
            quantity, quantity, price_usd, purchase_price_pln,
            commission_usd, commission_pln, usd_pln_rate
        ))
    
    @staticmethod
    def process_sale_fifo(stock_id: int, sale_transaction_id: int, 
                         quantity_to_sell: int, sale_price_usd: float,
                         sale_date: date, usd_pln_rate: float) -> List[Dict[str, Any]]:
        """Przetwarza sprzedaż metodą FIFO i zwraca szczegóły."""
        
        # Pobierz otwarte loty w kolejności FIFO
        lots_query = """
            SELECT * FROM stock_lots
            WHERE stock_id = ? AND remaining_quantity > 0
            ORDER BY purchase_date, lot_number
        """
        available_lots = execute_query(lots_query, (stock_id,))
        
        if not available_lots:
            raise ValueError(f"Brak dostępnych lotów dla sprzedaży {quantity_to_sell} akcji")
        
        # Sprawdź czy mamy wystarczającą ilość akcji
        total_available = sum(lot['remaining_quantity'] for lot in available_lots)
        if total_available < quantity_to_sell:
            raise ValueError(f"Niewystarczająca ilość akcji. Dostępne: {total_available}, potrzebne: {quantity_to_sell}")
        
        sale_details = []
        remaining_to_sell = quantity_to_sell
        sale_price_pln = sale_price_usd * usd_pln_rate
        
        for lot in available_lots:
            if remaining_to_sell <= 0:
                break
            
            lot_id = lot['id']
            lot_remaining = lot['remaining_quantity']
            
            # Ile sprzedajemy z tego lotu
            quantity_from_lot = min(remaining_to_sell, lot_remaining)
            
            # Oblicz zysk/stratę
            purchase_price_usd = lot['purchase_price_usd']
            purchase_price_pln = lot['purchase_price_pln']
            
            # Zysk/strata na sprzedanych akcjach
            gain_loss_usd = (sale_price_usd - purchase_price_usd) * quantity_from_lot
            gain_loss_pln = (sale_price_pln - purchase_price_pln) * quantity_from_lot
            
            # Podatek należny (19% od zysku)
            tax_due_pln = max(0, gain_loss_pln * 0.19)
            
            # Zapisz szczegóły sprzedaży
            sale_detail_id = execute_insert("""
                INSERT INTO stock_lot_sales 
                (lot_id, sale_transaction_id, quantity_sold, sale_date,
                 sale_price_usd, sale_price_pln, gain_loss_usd, 
                 gain_loss_pln, tax_due_pln, usd_pln_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lot_id, sale_transaction_id, quantity_from_lot, sale_date,
                sale_price_usd, sale_price_pln, gain_loss_usd,
                gain_loss_pln, tax_due_pln, usd_pln_rate
            ))
            
            # Aktualizuj pozostałą ilość w locie
            new_remaining = lot_remaining - quantity_from_lot
            new_status = 'CLOSED' if new_remaining == 0 else 'PARTIAL'
            
            execute_update("""
                UPDATE stock_lots 
                SET remaining_quantity = ?, status = ?
                WHERE id = ?
            """, (new_remaining, new_status, lot_id))
            
            # Dodaj do wyników
            sale_details.append({
                'lot_id': lot_id,
                'lot_number': lot['lot_number'],
                'purchase_date': lot['purchase_date'],
                'quantity_sold': quantity_from_lot,
                'purchase_price_usd': purchase_price_usd,
                'purchase_price_pln': purchase_price_pln,
                'sale_price_usd': sale_price_usd,
                'sale_price_pln': sale_price_pln,
                'gain_loss_usd': gain_loss_usd,
                'gain_loss_pln': gain_loss_pln,
                'tax_due_pln': tax_due_pln,
                'usd_pln_rate': usd_pln_rate,
                'sale_detail_id': sale_detail_id
            })
            
            remaining_to_sell -= quantity_from_lot
        
        return sale_details
    
    @staticmethod
    def get_lots_summary(stock_id: int = None) -> Dict[str, Any]:
        """Pobiera podsumowanie lotów."""
        base_query = """
            SELECT 
                COUNT(*) as total_lots,
                COUNT(CASE WHEN remaining_quantity > 0 THEN 1 END) as open_lots,
                COUNT(CASE WHEN remaining_quantity = 0 THEN 1 END) as closed_lots,
                SUM(quantity) as total_shares_purchased,
                SUM(remaining_quantity) as total_shares_remaining,
                SUM(purchase_price_pln * remaining_quantity) as total_value_pln,
                SUM(purchase_price_usd * remaining_quantity) as total_value_usd,
                AVG(usd_pln_rate) as avg_usd_rate
            FROM stock_lots
        """
        
        params = []
        if stock_id:
            base_query += " WHERE stock_id = ?"
            params.append(stock_id)
        
        result = execute_query(base_query, tuple(params))
        return dict(result[0]) if result else {}
    
    @staticmethod
    def get_realized_gains_by_year(year: int = None) -> List[Dict[str, Any]]:
        """Pobiera zrealizowane zyski/straty według roku."""
        query = """
            SELECT 
                s.symbol,
                sls.sale_date,
                sls.quantity_sold,
                sl.purchase_price_pln,
                sls.sale_price_pln,
                sls.gain_loss_pln,
                sls.tax_due_pln,
                sl.lot_number,
                sl.purchase_date,
                sls.usd_pln_rate
            FROM stock_lot_sales sls
            JOIN stock_lots sl ON sls.lot_id = sl.id
            JOIN stocks s ON sl.stock_id = s.id
        """
        
        params = []
        if year:
            query += " WHERE strftime('%Y', sls.sale_date) = ?"
            params.append(str(year))
        
        query += " ORDER BY sls.sale_date DESC, s.symbol"
        
        return [dict(row) for row in execute_query(query, tuple(params))]
    
    @staticmethod
    def get_tax_summary_by_year(year: int) -> Dict[str, Any]:
        """Pobiera podsumowanie podatkowe za dany rok."""
        query = """
            SELECT 
                COUNT(*) as total_sales,
                SUM(quantity_sold) as total_shares_sold,
                SUM(gain_loss_pln) as total_gain_loss_pln,
                SUM(CASE WHEN gain_loss_pln > 0 THEN gain_loss_pln ELSE 0 END) as total_gains_pln,
                SUM(CASE WHEN gain_loss_pln < 0 THEN gain_loss_pln ELSE 0 END) as total_losses_pln,
                SUM(tax_due_pln) as total_tax_due_pln,
                AVG(usd_pln_rate) as avg_usd_rate
            FROM stock_lot_sales
            WHERE strftime('%Y', sale_date) = ?
        """
        
        result = execute_query(query, (str(year),))
        return dict(result[0]) if result else {}
    
    @staticmethod
    def get_lot_details(lot_id: int) -> Optional[Dict[str, Any]]:
        """Pobiera szczegóły konkretnego lotu."""
        query = """
            SELECT 
                sl.*,
                s.symbol,
                s.name as stock_name,
                st.transaction_date,
                st.commission_usd as transaction_commission,
                (sl.purchase_price_pln * sl.remaining_quantity) as remaining_value_pln
            FROM stock_lots sl
            JOIN stocks s ON sl.stock_id = s.id
            JOIN stock_transactions st ON sl.transaction_id = st.id
            WHERE sl.id = ?
        """
        
        result = execute_query(query, (lot_id,))
        return dict(result[0]) if result else None
    
    @staticmethod
    def get_lot_sales(lot_id: int) -> List[Dict[str, Any]]:
        """Pobiera wszystkie sprzedaże z danego lotu."""
        query = """
            SELECT 
                sls.*,
                st.transaction_date as sale_transaction_date
            FROM stock_lot_sales sls
            JOIN stock_transactions st ON sls.sale_transaction_id = st.id
            WHERE sls.lot_id = ?
            ORDER BY sls.sale_date
        """
        
        return [dict(row) for row in execute_query(query, (lot_id,))]
    
    @staticmethod
    def get_fifo_preview(stock_id: int, quantity_to_sell: int) -> List[Dict[str, Any]]:
        """Podgląd sprzedaży FIFO bez faktycznego wykonania."""
        query = """
            SELECT 
                id, lot_number, purchase_date, remaining_quantity,
                purchase_price_usd, purchase_price_pln
            FROM stock_lots
            WHERE stock_id = ? AND remaining_quantity > 0
            ORDER BY purchase_date, lot_number
        """
        
        lots = execute_query(query, (stock_id,))
        preview = []
        remaining_to_sell = quantity_to_sell
        
        for lot in lots:
            if remaining_to_sell <= 0:
                break
            
            quantity_from_lot = min(remaining_to_sell, lot['remaining_quantity'])
            
            preview.append({
                'lot_id': lot['id'],
                'lot_number': lot['lot_number'],
                'purchase_date': lot['purchase_date'],
                'quantity_to_sell': quantity_from_lot,
                'purchase_price_usd': lot['purchase_price_usd'],
                'purchase_price_pln': lot['purchase_price_pln'],
                'remaining_after_sale': lot['remaining_quantity'] - quantity_from_lot
            })
            
            remaining_to_sell -= quantity_from_lot
        
        return preview
    
    def update_lot_rates(lot_id: int, new_usd_pln_rate: float) -> bool:
        """Aktualizuje kurs USD/PLN dla lotu i przelicza ceny PLN."""
        # Pobierz aktualne dane lotu
        lot = StockLotsRepository.get_lot_details(lot_id)
        if not lot:
            return False
        
        # Przelicz ceny PLN z nowym kursem
        new_purchase_price_pln = lot['purchase_price_usd'] * new_usd_pln_rate
        new_commission_pln = lot['commission_usd'] * new_usd_pln_rate
        
        # Aktualizuj lot
        query = """
            UPDATE stock_lots 
            SET usd_pln_rate = ?, purchase_price_pln = ?, commission_pln = ?
            WHERE id = ?
        """
        
        return execute_update(query, (
            new_usd_pln_rate, new_purchase_price_pln, 
            new_commission_pln, lot_id
        )) > 0
        
    @staticmethod
    def reserve_shares_for_option(option_id: int, stock_id: int, shares_needed: int) -> bool:
        """Rezerwuje akcje FIFO dla covered call."""
        
        # Pobierz dostępne loty (FIFO - najstarsze pierwsze)
        available_lots_query = """
            SELECT 
                sl.id,
                sl.lot_number,
                sl.remaining_quantity,
                sl.purchase_date,
                COALESCE(SUM(opt_res.reserved_quantity), 0) as already_reserved
            FROM stock_lots sl
            LEFT JOIN option_reservations opt_res ON sl.id = opt_res.lot_id
            WHERE sl.stock_id = ? AND sl.remaining_quantity > 0
            GROUP BY sl.id
            HAVING (sl.remaining_quantity - COALESCE(SUM(opt_res.reserved_quantity), 0)) > 0
            ORDER BY sl.purchase_date, sl.lot_number
        """
        
        available_lots = execute_query(available_lots_query, (stock_id,))
        
        if not available_lots:
            raise ValueError("Brak dostępnych akcji do rezerwacji")
        
        # Sprawdź czy mamy wystarczająco akcji
        total_available = sum(lot['remaining_quantity'] - lot['already_reserved'] for lot in available_lots)
        
        if total_available < shares_needed:
            raise ValueError(f"Niewystarczająca ilość akcji. Dostępne: {total_available}, potrzebne: {shares_needed}")
        
        # Rezerwuj akcje FIFO
        remaining_to_reserve = shares_needed
        reservations_made = []
        
        for lot in available_lots:
            if remaining_to_reserve <= 0:
                break
            
            available_in_lot = lot['remaining_quantity'] - lot['already_reserved']
            quantity_to_reserve = min(remaining_to_reserve, available_in_lot)
            
            # Utwórz rezerwację
            reservation_id = execute_insert("""
                INSERT INTO option_reservations 
                (option_id, lot_id, reserved_quantity)
                VALUES (?, ?, ?)
            """, (option_id, lot['id'], quantity_to_reserve))
            
            reservations_made.append({
                'reservation_id': reservation_id,
                'lot_id': lot['id'],
                'lot_number': lot['lot_number'],
                'quantity_reserved': quantity_to_reserve
            })
            
            remaining_to_reserve -= quantity_to_reserve
        
        print(f"✅ Zarezerwowano {shares_needed} akcji dla opcji {option_id}")
        for res in reservations_made:
            print(f"   📦 Lot #{res['lot_number']}: {res['quantity_reserved']} akcji")
        
        return True
    
    @staticmethod
    def check_shares_available_for_sale(stock_id: int, shares_to_sell: int) -> Dict[str, Any]:
        """Sprawdza czy można sprzedać akcje (czy nie są zarezerwowane)."""
        
        # Pobierz dostępne loty do sprzedaży (po odjęciu rezerwacji)
        query = """
            SELECT 
                sl.id,
                sl.lot_number,
                sl.remaining_quantity,
                COALESCE(SUM(opt_res.reserved_quantity), 0) as reserved_quantity,
                (sl.remaining_quantity - COALESCE(SUM(opt_res.reserved_quantity), 0)) as available_for_sale
            FROM stock_lots sl
            LEFT JOIN option_reservations opt_res ON sl.id = opt_res.lot_id
            WHERE sl.stock_id = ? AND sl.remaining_quantity > 0
            GROUP BY sl.id
            ORDER BY sl.purchase_date, sl.lot_number
        """
        
        lots = execute_query(query, (stock_id,))
        
        total_available = sum(lot['available_for_sale'] for lot in lots if lot['available_for_sale'] > 0)
        
        return {
            'can_sell': total_available >= shares_to_sell,
            'available_shares': total_available,
            'lots_breakdown': lots
        }  
        
def show_active_options_tab():
    """Wyświetla aktywne opcje."""
    
    st.markdown("### 🟢 Aktywne opcje")
    
    # Pobierz aktywne opcje
    options = OptionsRepository.get_all_options(include_closed=False)
    
    if options:
        for idx, option in enumerate(options):
            with st.expander(f"📋 {option['symbol']} {option['option_type']} ${option['strike_price']:.2f} - wygasa {option['expiry_date']}"):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Premium otrzymane", format_currency(option['premium_received']))
                    st.metric("Ilość kontraktów", option['quantity'])
                
                with col2:
                    st.metric("Strike price", format_currency(option['strike_price']))
                    st.metric("Data otwarcia", option['open_date'])
                
                with col3:
                    days_to_expiry = option.get('days_to_expiry', 0)
                    st.metric("Dni do wygaśnięcia", f"{days_to_expiry:.0f}")
                    
                    if option.get('current_price_usd'):
                        st.metric("Cena akcji", format_currency(option['current_price_usd']))
                
                with col4:
                    st.markdown("#### 🔧 Akcje")
                    
                    # Przyciski zarządzania
                    col_buy, col_exp, col_del = st.columns(3)
                    
                    with col_buy:
                        if st.button("🔄 Buyback", key=f"buyback_{option['id']}", help="Odkup opcję"):
                            buyback_price = st.number_input(
                                f"Cena odkupu opcji {option['symbol']}",
                                min_value=0.01,
                                value=0.01,
                                step=0.01,
                                format="%.2f",
                                key=f"buyback_price_{option['id']}"
                            )
                            
                            if st.button("Potwierdź buyback", key=f"confirm_buyback_{option['id']}"):
                                try:
                                    # Zaktualizuj status na CLOSED
                                    if OptionsRepository.update_option_status(option['id'], 'CLOSED', date.today()):
                                        # Usuń rezerwację akcji jeśli to covered call
                                        if option['option_type'] == 'CALL':
                                            from repos.stock_lots_repo import StockLotsRepository
                                            StockLotsRepository.release_option_reservation(option['id'])
                                        
                                        st.success(f"✅ Opcja odkupiona za ${buyback_price:.2f}")
                                        st.rerun()
                                    else:
                                        st.error("Błąd podczas buyback")
                                except Exception as e:
                                    st.error(f"Błąd: {e}")
                    
                    with col_exp:
                        if st.button("📅 Expired", key=f"expired_{option['id']}", help="Oznacz jako wygasłą"):
                            try:
                                if OptionsRepository.update_option_status(option['id'], 'EXPIRED', option['expiry_date']):
                                    # Usuń rezerwację akcji
                                    if option['option_type'] == 'CALL':
                                        from repos.stock_lots_repo import StockLotsRepository
                                        StockLotsRepository.release_option_reservation(option['id'])
                                    
                                    st.success("✅ Opcja oznaczona jako wygasła")
                                    st.rerun()
                                else:
                                    st.error("Błąd podczas ustawiania statusu")
                            except Exception as e:
                                st.error(f"Błąd: {e}")
                    
                    with col_del:
                        if st.button("🗑️ Usuń", key=f"delete_{option['id']}", help="Usuń opcję z bazy"):
                            if st.checkbox(f"Potwierdź usunięcie opcji {option['symbol']}", key=f"confirm_delete_{option['id']}"):
                                try:
                                    # Usuń rezerwację akcji przed usunięciem opcji
                                    if option['option_type'] == 'CALL':
                                        from repos.stock_lots_repo import StockLotsRepository
                                        StockLotsRepository.release_option_reservation(option['id'])
                                    
                                    # Usuń opcję z bazy
                                    if OptionsRepository.delete_option(option['id']):
                                        st.success("✅ Opcja usunięta z bazy danych")
                                        st.rerun()
                                    else:
                                        st.error("Błąd podczas usuwania")
                                except Exception as e:
                                    st.error(f"Błąd: {e}")
                
                # Status opcji i analiza
                if option.get('current_price_usd') and option.get('strike_price'):
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
        st.info("Brak aktywnych opcji. Dodaj pierwszą opcję w zakładce '➕ Dodaj opcję'.")

# DODAJ TAKŻE METODĘ DO RELEASE REZERWACJI W stock_lots_repo.py:

    def release_option_reservation(option_id: int) -> bool:
        """Usuwa rezerwację akcji dla opcji."""
        try:
            from db import execute_update
            result = execute_update("DELETE FROM option_reservations WHERE option_id = ?", (option_id,))
            print(f"🔓 Usunięto rezerwację dla opcji {option_id}")
            return result > 0
        except Exception as e:
            print(f"❌ Błąd usuwania rezerwacji: {e}")
        return False    