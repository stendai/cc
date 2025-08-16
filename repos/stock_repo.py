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
        """Dodaje transakcję akcji."""
        query = """
            INSERT INTO stock_transactions 
            (stock_id, transaction_type, quantity, price_usd, commission_usd, transaction_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        transaction_id = execute_insert(
            query, 
            (stock_id, transaction_type, quantity, price, commission, transaction_date, notes)
        )
        
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
    def get_portfolio_summary() -> Dict[str, Any]:
        """Pobiera podsumowanie całego portfela akcji."""
        query = """
            SELECT 
                COUNT(*) as total_positions,
                SUM(quantity * avg_price_usd) as total_cost,
                SUM(quantity * current_price_usd) as current_value,
                SUM((quantity * current_price_usd) - (quantity * avg_price_usd)) as unrealized_gain_loss
            FROM stocks
            WHERE quantity > 0
        """
        result = execute_query(query)
        return dict(result[0]) if result else {}
    
    @staticmethod
    def get_realized_gains_losses(year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Pobiera zrealizowane zyski/straty ze sprzedaży akcji."""
        base_query = """
            SELECT 
                s.symbol,
                st.quantity as sold_quantity,
                st.price_usd as sale_price,
                st.transaction_date,
                st.commission_usd,
                (st.quantity * st.price_usd - st.commission_usd) as gross_proceeds
            FROM stock_transactions st
            JOIN stocks s ON st.stock_id = s.id
            WHERE st.transaction_type = 'SELL'
        """
        
        params = []
        if year:
            base_query += " AND strftime('%Y', st.transaction_date) = ?"
            params.append(str(year))
        
        base_query += " ORDER BY st.transaction_date DESC"
        
        return [dict(row) for row in execute_query(base_query, params)]
    
    @staticmethod
    def get_stock_performance() -> List[Dict[str, Any]]:
        """Pobiera wydajność każdej akcji w portfelu."""
        query = """
            SELECT 
                s.symbol,
                s.name,
                s.quantity,
                s.avg_price_usd,
                s.current_price_usd,
                (s.current_price_usd - s.avg_price_usd) as price_change,
                ((s.current_price_usd - s.avg_price_usd) / s.avg_price_usd * 100) as price_change_pct,
                (s.quantity * s.avg_price_usd) as total_cost,
                (s.quantity * s.current_price_usd) as current_value,
                ((s.quantity * s.current_price_usd) - (s.quantity * s.avg_price_usd)) as unrealized_gain_loss,
                (((s.quantity * s.current_price_usd) - (s.quantity * s.avg_price_usd)) / 
                 (s.quantity * s.avg_price_usd) * 100) as return_pct
            FROM stocks s
            WHERE s.quantity > 0
            ORDER BY return_pct DESC
        """
        return [dict(row) for row in execute_query(query)]
    
    @staticmethod
    def get_transactions_for_tax_calculation(year: int) -> List[Dict[str, Any]]:
        """Pobiera transakcje potrzebne do obliczeń podatkowych."""
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