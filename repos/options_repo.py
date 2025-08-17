from typing import List, Optional, Dict, Any
from datetime import date, datetime
from db import execute_query, execute_insert, execute_update

class OptionsRepository:
    
    @staticmethod
    def get_all_options(include_closed: bool = False) -> List[Dict[str, Any]]:
        """Pobiera wszystkie opcje z portfela."""
        base_query = """
            SELECT 
                o.*,
                s.symbol,
                s.name as stock_name,
                s.current_price_usd,
                s.quantity as stock_quantity,
                (julianday(o.expiry_date) - julianday('now')) as days_to_expiry,
                CASE 
                    WHEN o.option_type = 'CALL' AND s.current_price_usd > o.strike_price 
                    THEN s.current_price_usd - o.strike_price
                    WHEN o.option_type = 'PUT' AND s.current_price_usd < o.strike_price 
                    THEN o.strike_price - s.current_price_usd
                    ELSE 0
                END as intrinsic_value
            FROM options o
            JOIN stocks s ON o.stock_id = s.id
        """
        
        if not include_closed:
            base_query += " WHERE o.status = 'OPEN'"
        
        base_query += " ORDER BY o.expiry_date ASC, s.symbol"
        
        return [dict(row) for row in execute_query(base_query)]
    
    @staticmethod
    def get_option_by_id(option_id: int) -> Optional[Dict[str, Any]]:
        """Pobiera opcję po ID."""
        query = """
            SELECT 
                o.*,
                s.symbol,
                s.name as stock_name,
                s.current_price_usd,
                s.quantity as stock_quantity
            FROM options o
            JOIN stocks s ON o.stock_id = s.id
            WHERE o.id = ?
        """
        result = execute_query(query, (option_id,))
        return dict(result[0]) if result else None
    
    @staticmethod
    def add_option(stock_id: int, option_type: str, strike_price: float,
                   expiry_date: date, premium_received: float, quantity: int,
                   open_date: date, commission: float = 0.0, notes: str = None) -> int:
        """Dodaje nową opcję z prostą walidacją."""
        
        # Sprawdź dostępność akcji dla covered call (uproszczone)
        if option_type == "CALL":
            shares_needed = quantity * 100
            
            stock_query = "SELECT quantity FROM stocks WHERE id = ?"
            stock_result = execute_query(stock_query, (stock_id,))
            
            if not stock_result:
                raise ValueError("Nie znaleziono akcji w portfelu")
            
            shares_owned = stock_result[0]['quantity']
            
            if shares_owned < shares_needed:
                raise ValueError(f"Niewystarczająca ilość akcji. Posiadasz: {shares_owned}, potrzebne: {shares_needed}")
        
        # Pobierz kurs NBP
        from services.nbp import nbp_service
        from datetime import timedelta
        
        try:
            prev_date = open_date - timedelta(days=1)
            usd_pln_rate = nbp_service.get_usd_pln_rate(prev_date) or 3.65
        except:
            usd_pln_rate = 3.65
        
        # Oblicz kwoty PLN
        premium_pln = premium_received * quantity * usd_pln_rate
        commission_pln = commission * usd_pln_rate
        
        # Dodaj opcję
        query = """
            INSERT INTO options 
            (stock_id, option_type, strike_price, expiry_date, premium_received, 
             quantity, open_date, commission_usd, usd_pln_rate, premium_pln, 
             commission_pln, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
        """
        
        option_id = execute_insert(query, (
            stock_id, option_type, strike_price, expiry_date, 
            premium_received, quantity, open_date, commission, 
            usd_pln_rate, premium_pln, commission_pln, notes
        ))
        
        print(f"✅ Opcja utworzona z ID: {option_id}")
        return option_id
    
    @staticmethod
    def buyback_option(option_id: int, buyback_price: float, buyback_date: date = None) -> bool:
        """Odkupuje opcję."""
        if buyback_date is None:
            buyback_date = date.today()
        
        try:
            query = "UPDATE options SET status = 'CLOSED', close_date = ? WHERE id = ?"
            success = execute_update(query, (buyback_date, option_id)) > 0
            
            if success:
                print(f"✅ Opcja {option_id} odkupiona za ${buyback_price:.2f}")
            
            return success
            
        except Exception as e:
            print(f"❌ Błąd buyback: {e}")
            return False
    
    @staticmethod
    def expire_option(option_id: int) -> bool:
        """Oznacza opcję jako wygasłą."""
        try:
            query = "UPDATE options SET status = 'EXPIRED', close_date = ? WHERE id = ?"
            success = execute_update(query, (date.today(), option_id)) > 0
            
            if success:
                print(f"✅ Opcja {option_id} oznaczona jako wygasła")
            
            return success
            
        except Exception as e:
            print(f"❌ Błąd expire: {e}")
            return False
    
    @staticmethod
    def delete_option(option_id: int) -> bool:
        """Usuwa opcję z bazy."""
        try:
            success = execute_update("DELETE FROM options WHERE id = ?", (option_id,)) > 0
            
            if success:
                print(f"✅ Opcja {option_id} usunięta z bazy")
            
            return success
            
        except Exception as e:
            print(f"❌ Błąd delete: {e}")
            return False
    
    @staticmethod
    def update_option_status(option_id: int, status: str, close_date: date = None) -> bool:
        """Aktualizuje status opcji."""
        try:
            if close_date:
                query = "UPDATE options SET status = ?, close_date = ? WHERE id = ?"
                params = (status, close_date, option_id)
            else:
                query = "UPDATE options SET status = ? WHERE id = ?"
                params = (status, option_id)
            
            return execute_update(query, params) > 0
            
        except Exception as e:
            print(f"❌ Błąd update status: {e}")
            return False
    
    @staticmethod
    def get_options_by_stock(stock_id: int) -> List[Dict[str, Any]]:
        """Pobiera wszystkie opcje dla danej akcji."""
        query = """
            SELECT 
                o.*,
                s.symbol,
                s.current_price_usd,
                (julianday(o.expiry_date) - julianday('now')) as days_to_expiry
            FROM options o
            JOIN stocks s ON o.stock_id = s.id
            WHERE o.stock_id = ?
            ORDER BY o.expiry_date DESC
        """
        return [dict(row) for row in execute_query(query, (stock_id,))]
    
    @staticmethod
    def get_expiring_options(days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Pobiera opcje wygasające w określonym czasie."""
        query = """
            SELECT 
                o.*,
                s.symbol,
                s.current_price_usd,
                (julianday(o.expiry_date) - julianday('now')) as days_to_expiry
            FROM options o
            JOIN stocks s ON o.stock_id = s.id
            WHERE o.status = 'OPEN' 
            AND julianday(o.expiry_date) - julianday('now') <= ?
            AND julianday(o.expiry_date) - julianday('now') >= 0
            ORDER BY o.expiry_date ASC
        """
        return [dict(row) for row in execute_query(query, (days_ahead,))]
    
    @staticmethod
    def get_options_summary() -> Dict[str, Any]:
        """Pobiera podsumowanie opcji."""
        query = """
            SELECT 
                COUNT(*) as total_options,
                COUNT(CASE WHEN status = 'OPEN' THEN 1 END) as open_options,
                COUNT(CASE WHEN status = 'EXPIRED' THEN 1 END) as expired_options,
                COUNT(CASE WHEN status = 'ASSIGNED' THEN 1 END) as assigned_options,
                COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as closed_options,
                SUM(CASE WHEN status = 'OPEN' THEN premium_received * quantity ELSE 0 END) as active_premium,
                SUM(premium_received * quantity) as total_premium_received
            FROM options
        """
        result = execute_query(query)
        data = dict(result[0]) if result else {}
        
        # Konwertuj None na 0
        for key, value in data.items():
            if value is None:
                data[key] = 0
        
        return data
    
    @staticmethod
    def get_covered_calls() -> List[Dict[str, Any]]:
        """Pobiera wszystkie covered calls."""
        query = """
            SELECT 
                o.*,
                s.symbol,
                s.name as stock_name,
                s.quantity as stock_quantity,
                s.current_price_usd,
                (julianday(o.expiry_date) - julianday('now')) as days_to_expiry,
                CASE 
                    WHEN s.current_price_usd > o.strike_price 
                    THEN (s.current_price_usd - o.strike_price) * o.quantity
                    ELSE 0
                END as intrinsic_value_total
            FROM options o
            JOIN stocks s ON o.stock_id = s.id
            WHERE o.option_type = 'CALL' 
            AND s.quantity >= o.quantity
            AND o.status = 'OPEN'
            ORDER BY o.expiry_date ASC
        """
        return [dict(row) for row in execute_query(query)]
    
    @staticmethod
    def get_options_performance() -> List[Dict[str, Any]]:
        """Pobiera wydajność opcji."""
        query = """
            SELECT 
                s.symbol,
                o.option_type,
                o.strike_price,
                o.expiry_date,
                o.premium_received,
                o.quantity,
                o.status,
                o.open_date,
                o.close_date,
                (o.premium_received * o.quantity) as total_premium,
                CASE 
                    WHEN o.status = 'OPEN' THEN 
                        ROUND((julianday('now') - julianday(o.open_date)) / 
                              (julianday(o.expiry_date) - julianday(o.open_date)) * 100, 2)
                    ELSE 100
                END as time_decay_pct,
                CASE 
                    WHEN o.status IN ('EXPIRED', 'CLOSED') THEN o.premium_received * o.quantity
                    WHEN o.status = 'ASSIGNED' THEN 
                        (o.strike_price - (SELECT avg_price_usd FROM stocks WHERE id = o.stock_id)) * o.quantity + 
                        o.premium_received * o.quantity
                    ELSE 0
                END as realized_profit
            FROM options o
            JOIN stocks s ON o.stock_id = s.id
            ORDER BY o.open_date DESC
        """
        return [dict(row) for row in execute_query(query)]
    
    @staticmethod
    def calculate_option_income(year: Optional[int] = None) -> Dict[str, Any]:
        """Oblicza dochód z opcji za dany rok lub ogółem."""
        base_query = """
            SELECT 
                COUNT(*) as total_contracts,
                SUM(premium_received * quantity) as total_premium,
                AVG(premium_received * quantity) as avg_premium_per_contract,
                SUM(CASE WHEN status = 'EXPIRED' THEN premium_received * quantity ELSE 0 END) as expired_premium,
                SUM(CASE WHEN status = 'ASSIGNED' THEN premium_received * quantity ELSE 0 END) as assigned_premium,
                SUM(CASE WHEN status = 'CLOSED' THEN premium_received * quantity ELSE 0 END) as closed_premium
            FROM options
        """
        
        params = []
        if year:
            base_query += " WHERE strftime('%Y', open_date) = ?"
            params.append(str(year))
        
        result = execute_query(base_query, params)
        data = dict(result[0]) if result else {}
        
        # Konwertuj None na 0
        for key, value in data.items():
            if value is None:
                data[key] = 0
        
        return data
    
    @staticmethod
    def get_options_for_tax_calculation(year: int) -> List[Dict[str, Any]]:
        """Pobiera opcje potrzebne do obliczeń podatkowych za dany rok."""
        query = """
            SELECT 
                o.*,
                s.symbol
            FROM options o
            JOIN stocks s ON o.stock_id = s.id
            WHERE strftime('%Y', o.open_date) = ?
            ORDER BY o.open_date
        """
        return [dict(row) for row in execute_query(query, (str(year),))]
    
    @staticmethod
    def get_assignment_risk() -> List[Dict[str, Any]]:
        """Pobiera opcje z wysokim ryzykiem przydziału."""
        query = """
            SELECT 
                o.*,
                s.symbol,
                s.current_price_usd,
                (julianday(o.expiry_date) - julianday('now')) as days_to_expiry,
                CASE 
                    WHEN o.option_type = 'CALL' THEN 
                        (s.current_price_usd - o.strike_price) / o.strike_price * 100
                    WHEN o.option_type = 'PUT' THEN 
                        (o.strike_price - s.current_price_usd) / o.strike_price * 100
                    ELSE 0
                END as moneyness_pct
            FROM options o
            JOIN stocks s ON o.stock_id = s.id
            WHERE o.status = 'OPEN'
            AND (
                (o.option_type = 'CALL' AND s.current_price_usd > o.strike_price * 0.95) OR
                (o.option_type = 'PUT' AND s.current_price_usd < o.strike_price * 1.05)
            )
            ORDER BY 
                CASE 
                    WHEN o.option_type = 'CALL' THEN s.current_price_usd - o.strike_price
                    WHEN o.option_type = 'PUT' THEN o.strike_price - s.current_price_usd
                END DESC
        """
        return [dict(row) for row in execute_query(query)]
    
    @staticmethod
    def get_monthly_option_income(year: int) -> List[Dict[str, Any]]:
        """Pobiera miesięczny dochód z opcji."""
        query = """
            SELECT 
                strftime('%m', open_date) as month,
                strftime('%Y-%m', open_date) as year_month,
                COUNT(*) as contracts_opened,
                SUM(premium_received * quantity) as premium_received,
                COUNT(CASE WHEN status = 'EXPIRED' THEN 1 END) as contracts_expired,
                COUNT(CASE WHEN status = 'ASSIGNED' THEN 1 END) as contracts_assigned
            FROM options
            WHERE strftime('%Y', open_date) = ?
            GROUP BY strftime('%Y-%m', open_date)
            ORDER BY year_month
        """
        return [dict(row) for row in execute_query(query, (str(year),))]
    
    @staticmethod
    def get_stocks_for_options() -> List[Dict[str, Any]]:
        """Pobiera akcje dostępne do wystawienia opcji (tylko te z quantity > 0)."""
        query = """
            SELECT id, symbol, name, quantity, current_price_usd
            FROM stocks 
            WHERE quantity > 0
            ORDER BY symbol
        """
        return [dict(row) for row in execute_query(query)]