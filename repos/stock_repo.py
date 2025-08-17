from typing import List, Optional, Dict, Any
from datetime import date, datetime
from db import execute_query, execute_insert, execute_update

class StockRepository:
    
    @staticmethod
    def get_all_stocks() -> List[Dict[str, Any]]:
        """Pobiera wszystkie akcje z portfela."""
        query = """
            SELECT s.*, 
                   COALESCE(s.quantity, 0) as quantity,
                   COALESCE(s.avg_price_usd, 0) as avg_price_usd,
                   COALESCE(s.current_price_usd, 0) as current_price_usd,
                   (COALESCE(s.quantity, 0) * COALESCE(s.avg_price_usd, 0)) as total_cost,
                   (COALESCE(s.quantity, 0) * COALESCE(s.current_price_usd, 0)) as current_value,
                   ((COALESCE(s.quantity, 0) * COALESCE(s.current_price_usd, 0)) - 
                    (COALESCE(s.quantity, 0) * COALESCE(s.avg_price_usd, 0))) as unrealized_gain_loss
            FROM stocks s
            WHERE s.quantity > 0
            ORDER BY s.symbol
        """
        return [dict(row) for row in execute_query(query)]
    
    @staticmethod
    def get_stock_by_symbol(symbol: str) -> Optional[Dict[str, Any]]:
        """Pobiera akcję po symbolu."""
        query = "SELECT * FROM stocks WHERE symbol = ?"
        result = execute_query(query, (symbol,))
        return dict(result[0]) if result else None
    
    @staticmethod
    def get_stock_by_id(stock_id: int) -> Optional[Dict[str, Any]]:
        """Pobiera akcję po ID."""
        query = "SELECT * FROM stocks WHERE id = ?"
        result = execute_query(query, (stock_id,))
        return dict(result[0]) if result else None
    
    @staticmethod
    def add_stock(symbol: str, name: str) -> int:
        """Dodaje nową akcję do bazy."""
        query = """
            INSERT INTO stocks (symbol, name, quantity, avg_price_usd)
            VALUES (?, ?, 0, 0.0)
        """
        return execute_insert(query, (symbol.upper(), name))
    
    @staticmethod
    def update_stock_price(stock_id: int, current_price: float) -> bool:
        """Aktualizuje aktualną cenę akcji."""
        query = """
            UPDATE stocks 
            SET current_price_usd = ?, last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        return execute_update(query, (current_price, stock_id)) > 0
    
    @staticmethod
    def get_stock_transactions(stock_id: int) -> List[Dict[str, Any]]:
        """Pobiera wszystkie transakcje dla danej akcji."""
        query = """
            SELECT st.*, s.symbol, s.name
            FROM stock_transactions st
            JOIN stocks s ON st.stock_id = s.id
            WHERE st.stock_id = ?
            ORDER BY st.transaction_date DESC
        """
        return [dict(row) for row in execute_query(query, (stock_id,))]
    
    @staticmethod
    def add_transaction(stock_id: int, transaction_type: str, quantity: int, 
                       price: float, commission: float, transaction_date: date, 
                       notes: str = None) -> int:
        """Dodaje transakcję akcji z obsługą lotów."""
        
        # Pobierz kurs NBP z dnia poprzedzającego transakcję
        from services.nbp import nbp_service
        from datetime import timedelta
        
        try:
            prev_date = transaction_date - timedelta(days=1)
            usd_pln_rate = nbp_service.get_usd_pln_rate(prev_date)
            if not usd_pln_rate:
                # Jeśli nie ma kursu, spróbuj z dnia transakcji
                usd_pln_rate = nbp_service.get_usd_pln_rate(transaction_date) or 4.0
        except Exception as e:
            print(f"⚠️ Błąd pobierania kursu NBP: {e}")
            usd_pln_rate = 4.0  # Kurs domyślny
        
        # Oblicz kwoty w PLN
        price_pln = price * usd_pln_rate
        commission_pln = commission * usd_pln_rate
        
        # NAPRAWIONY INSERT - dodane brakujące kolumny
        query = """
            INSERT INTO stock_transactions 
            (stock_id, transaction_type, quantity, price_usd, commission_usd, 
             transaction_date, usd_pln_rate, price_pln, commission_pln, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        transaction_id = execute_insert(
            query, 
            (stock_id, transaction_type, quantity, price, commission, 
             transaction_date, usd_pln_rate, price_pln, commission_pln, notes)
        )
        
        # Obsługa lotów
        if transaction_type == 'BUY':
            try:
                # Utwórz nowy lot
                from repos.stock_lots_repo import StockLotsRepository
                lot_id = StockLotsRepository.create_lot_from_purchase(
                    stock_id, transaction_id, quantity, price, 
                    commission, transaction_date, usd_pln_rate
                )
                
                print(f"📦 Utworzono lot {lot_id} dla {quantity} akcji po ${price:.2f} (kurs {usd_pln_rate:.4f})")
                
            except Exception as e:
                print(f"⚠️ Błąd tworzenia lotu: {e}")
        
        elif transaction_type == 'SELL':
# NOWE: Sprawdź czy można sprzedać (rezerwacje)
            try:
                from repos.stock_lots_repo import StockLotsRepository
                availability = StockLotsRepository.check_shares_available_for_sale(stock_id, quantity)
                
                if not availability['can_sell']:
                    raise ValueError(f"Nie można sprzedać {quantity} akcji. Dostępne: {availability['available_shares']} (reszta zarezerwowana pod opcje)")
                
                print(f"✅ Sprawdzenie rezerwacji: można sprzedać {quantity} z {availability['available_shares']} dostępnych")
                
            except Exception as check_error:
                # Usuń transakcję jeśli sprawdzenie się nie powiodło
                execute_update("DELETE FROM stock_transactions WHERE id = ?", (transaction_id,))
                raise ValueError(f"Blokada sprzedaży: {check_error}")
            
            try:
                # Przetwórz sprzedaż FIFO
                sale_details = StockLotsRepository.process_sale_fifo(
                    stock_id, transaction_id, quantity, price,
                    transaction_date, usd_pln_rate
                )
                
                # Opcjonalnie zapisz podsumowanie sprzedaży w notatkach
                if not notes:
                    lots_sold = [f"Lot {sd['lot_number']}: {sd['quantity_sold']} szt." for sd in sale_details]
                    notes = f"FIFO: {', '.join(lots_sold)}"
                    execute_update(
                        "UPDATE stock_transactions SET notes = ? WHERE id = ?",
                        (notes, transaction_id)
                    )
                    
            except ValueError as e:
                # Jeśli nie można wykonać sprzedaży, usuń transakcję
                execute_update("DELETE FROM stock_transactions WHERE id = ?", (transaction_id,))
                raise e
            except Exception as e:
                print(f"⚠️ Błąd przetwarzania sprzedaży: {e}")
                # Usuń transakcję przy błędzie
                execute_update("DELETE FROM stock_transactions WHERE id = ?", (transaction_id,))
                raise e
        
        # Aktualizuj ilość i średnią cenę akcji
        StockRepository._update_stock_position(stock_id)
        
        return transaction_id
    
    @staticmethod
    def _update_stock_position(stock_id: int):
        """Prywatna metoda do aktualizacji pozycji akcji po transakcji."""
        # Pobierz wszystkie transakcje dla tej akcji
        transactions = execute_query("""
            SELECT transaction_type, quantity, price_usd
            FROM stock_transactions
            WHERE stock_id = ?
            ORDER BY transaction_date ASC
        """, (stock_id,))
        
        total_quantity = 0
        total_cost = 0.0
        
        for transaction in transactions:
            if transaction['transaction_type'] == 'BUY':
                total_quantity += transaction['quantity']
                total_cost += transaction['quantity'] * transaction['price_usd']
            elif transaction['transaction_type'] == 'SELL':
                # Przy sprzedaży zmniejszamy ilość, ale nie zmieniamy średniej ceny
                total_quantity -= transaction['quantity']
        
        # Oblicz średnią cenę
        avg_price = total_cost / total_quantity if total_quantity > 0 else 0.0
        
        # Aktualizuj akcję
        execute_update("""
            UPDATE stocks 
            SET quantity = ?, avg_price_usd = ?
            WHERE id = ?
        """, (total_quantity, avg_price, stock_id))
    
    @staticmethod
    def get_transactions_for_tax_calculation(year: int) -> List[Dict[str, Any]]:
        """Pobiera transakcje do kalkulacji podatkowej."""
        query = """
            SELECT 
                s.symbol,
                st.transaction_type,
                st.quantity,
                st.price_usd,
                st.commission_usd,
                st.transaction_date,
                s.id as stock_id
            FROM stock_transactions st
            JOIN stocks s ON st.stock_id = s.id
            WHERE strftime('%Y', st.transaction_date) = ?
            ORDER BY s.symbol, st.transaction_date
        """
        return [dict(row) for row in execute_query(query, (str(year),))]
    
    @staticmethod
    def delete_transaction(transaction_id: int) -> bool:
        """Usuwa transakcję i aktualizuje pozycję akcji."""
        # Pobierz informacje o transakcji przed usunięciem
        transaction_info = execute_query(
            "SELECT stock_id FROM stock_transactions WHERE id = ?", 
            (transaction_id,)
        )
        
        if not transaction_info:
            return False
        
        stock_id = transaction_info[0]['stock_id']
        
        # Usuń transakcję
        deleted = execute_update("DELETE FROM stock_transactions WHERE id = ?", (transaction_id,)) > 0
        
        if deleted:
            # Zaktualizuj pozycję akcji
            StockRepository._update_stock_position(stock_id)
        
        return deleted
    
    @staticmethod
    def search_stocks(search_term: str) -> List[Dict[str, Any]]:
        """Wyszukuje akcje po symbolu lub nazwie."""
        query = """
            SELECT * FROM stocks
            WHERE symbol LIKE ? OR name LIKE ?
            ORDER BY symbol
        """
        search_pattern = f"%{search_term}%"
        return [dict(row) for row in execute_query(query, (search_pattern, search_pattern))]
        
    def get_stocks_for_options() -> List[Dict[str, Any]]:
        """Pobiera wszystkie akcje dostępne do opcji (nawet z quantity=0)."""
        query = """
            SELECT s.*, 
                   COALESCE(s.quantity, 0) as quantity,
                   COALESCE(s.avg_price_usd, 0) as avg_price_usd,
                   COALESCE(s.current_price_usd, 0) as current_price_usd
            FROM stocks s
            ORDER BY s.symbol
        """
        return [dict(row) for row in execute_query(query)]