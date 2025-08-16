from typing import List, Optional, Dict, Any
from datetime import date, datetime
from db import execute_query, execute_insert, execute_update

class DividendsRepository:
    
    @staticmethod
    def get_all_dividends() -> List[Dict[str, Any]]:
        """Pobiera wszystkie dywidendy."""
        query = """
            SELECT 
                d.*,
                s.symbol,
                s.name as stock_name
            FROM dividends d
            JOIN stocks s ON d.stock_id = s.id
            ORDER BY d.ex_date DESC
        """
        return [dict(row) for row in execute_query(query)]
    
    @staticmethod
    def get_dividends_by_stock(stock_id: int) -> List[Dict[str, Any]]:
        """Pobiera dywidendy dla konkretnej akcji."""
        query = """
            SELECT 
                d.*,
                s.symbol,
                s.name as stock_name
            FROM dividends d
            JOIN stocks s ON d.stock_id = s.id
            WHERE d.stock_id = ?
            ORDER BY d.ex_date DESC
        """
        return [dict(row) for row in execute_query(query, (stock_id,))]
    
    @staticmethod
    def add_dividend(stock_id: int, dividend_per_share: float, quantity: int,
                    total_amount: float, tax_withheld: float, ex_date: date,
                    pay_date: date) -> int:
        """Dodaje nową dywidendę."""
        query = """
            INSERT INTO dividends 
            (stock_id, dividend_per_share, quantity, total_amount_usd, 
             tax_withheld_usd, ex_date, pay_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        return execute_insert(query, (
            stock_id, dividend_per_share, quantity, total_amount,
            tax_withheld, ex_date, pay_date
        ))
    
    @staticmethod
    def get_dividend_summary(year: Optional[int] = None) -> Dict[str, Any]:
        """Pobiera podsumowanie dywidend."""
        base_query = """
            SELECT 
                COUNT(*) as total_payments,
                SUM(total_amount_usd) as total_dividends,
                SUM(tax_withheld_usd) as total_tax_withheld,
                AVG(dividend_per_share) as avg_dividend_per_share,
                COUNT(DISTINCT stock_id) as dividend_paying_stocks
            FROM dividends
        """
        
        params = []
        if year:
            base_query += " WHERE strftime('%Y', pay_date) = ?"
            params.append(str(year))
        
        result = execute_query(base_query, params)
        return dict(result[0]) if result else {}
    
    @staticmethod
    def get_monthly_dividends(year: int) -> List[Dict[str, Any]]:
        """Pobiera dywidendy pogrupowane według miesięcy."""
        query = """
            SELECT 
                strftime('%m', pay_date) as month,
                strftime('%Y-%m', pay_date) as year_month,
                COUNT(*) as payment_count,
                SUM(total_amount_usd) as total_amount,
                SUM(tax_withheld_usd) as total_tax_withheld,
                COUNT(DISTINCT stock_id) as unique_stocks
            FROM dividends
            WHERE strftime('%Y', pay_date) = ?
            GROUP BY strftime('%Y-%m', pay_date)
            ORDER BY year_month
        """
        return [dict(row) for row in execute_query(query, (str(year),))]
    
    @staticmethod
    def get_dividend_yield_analysis() -> List[Dict[str, Any]]:
        """Analizuje rentowność dywidendową akcji w portfelu."""
        query = """
            SELECT 
                s.symbol,
                s.name,
                s.quantity,
                s.avg_price_usd,
                s.current_price_usd,
                COUNT(d.id) as dividend_payments_12m,
                SUM(d.total_amount_usd) as total_dividends_12m,
                AVG(d.dividend_per_share) as avg_dividend_per_share,
                CASE 
                    WHEN s.current_price_usd > 0 THEN 
                        (SUM(d.dividend_per_share) / s.current_price_usd) * 100
                    ELSE 0
                END as current_yield_pct,
                CASE 
                    WHEN s.avg_price_usd > 0 THEN 
                        (SUM(d.dividend_per_share) / s.avg_price_usd) * 100
                    ELSE 0
                END as yield_on_cost_pct
            FROM stocks s
            LEFT JOIN dividends d ON s.id = d.stock_id 
                AND d.pay_date >= date('now', '-12 months')
            WHERE s.quantity > 0
            GROUP BY s.id, s.symbol, s.name
            ORDER BY current_yield_pct DESC
        """
        return [dict(row) for row in execute_query(query)]
    
    @staticmethod
    def get_upcoming_dividends() -> List[Dict[str, Any]]:
        """Pobiera nadchodzące dywidendy (wymaga zewnętrznego API)."""
        # TODO: Implementacja wymaga integracji z API dostarczającym informacje o dywidendach
        # Na razie zwracamy pustą listę
        return []
    
    @staticmethod
    def get_dividend_history_chart_data(stock_id: int) -> List[Dict[str, Any]]:
        """Pobiera dane do wykresu historii dywidend dla akcji."""
        query = """
            SELECT 
                pay_date,
                dividend_per_share,
                total_amount_usd,
                quantity
            FROM dividends
            WHERE stock_id = ?
            ORDER BY pay_date ASC
        """
        return [dict(row) for row in execute_query(query, (stock_id,))]
    
    @staticmethod
    def calculate_dividend_growth_rate(stock_id: int, periods: int = 4) -> Optional[float]:
        """Oblicza stopę wzrostu dywidendy dla akcji."""
        query = """
            SELECT dividend_per_share, pay_date
            FROM dividends
            WHERE stock_id = ?
            ORDER BY pay_date DESC
            LIMIT ?
        """
        
        dividends = execute_query(query, (stock_id, periods))
        
        if len(dividends) < 2:
            return None
        
        # Oblicz średnią roczną stopę wzrostu
        first_dividend = dividends[-1]['dividend_per_share']
        last_dividend = dividends[0]['dividend_per_share']
        
        if first_dividend <= 0:
            return None
        
        years = len(dividends) - 1
        growth_rate = ((last_dividend / first_dividend) ** (1/years) - 1) * 100
        
        return growth_rate
    
    @staticmethod
    def get_tax_summary_for_dividends(year: int) -> Dict[str, Any]:
        """Pobiera podsumowanie podatkowe dywidend za dany rok."""
        query = """
            SELECT 
                s.symbol,
                SUM(d.total_amount_usd) as total_dividends_usd,
                SUM(d.tax_withheld_usd) as total_tax_withheld_usd,
                COUNT(*) as payment_count,
                GROUP_CONCAT(d.pay_date) as payment_dates
            FROM dividends d
            JOIN stocks s ON d.stock_id = s.id
            WHERE strftime('%Y', d.pay_date) = ?
            GROUP BY s.id, s.symbol
            ORDER BY total_dividends_usd DESC
        """
        return [dict(row) for row in execute_query(query, (str(year),))]
    
    @staticmethod
    def get_dividend_calendar(start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Pobiera kalendarz dywidend w określonym okresie."""
        query = """
            SELECT 
                d.pay_date,
                d.ex_date,
                s.symbol,
                s.name,
                d.dividend_per_share,
                d.total_amount_usd,
                s.quantity
            FROM dividends d
            JOIN stocks s ON d.stock_id = s.id
            WHERE d.pay_date BETWEEN ? AND ?
            ORDER BY d.pay_date ASC
        """
        return [dict(row) for row in execute_query(query, 
                    (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))]
    
    @staticmethod
    def update_dividend(dividend_id: int, dividend_per_share: float = None,
                       quantity: int = None, total_amount: float = None,
                       tax_withheld: float = None, ex_date: date = None,
                       pay_date: date = None) -> bool:
        """Aktualizuje istniejącą dywidendę."""
        
        # Pobierz aktualne dane
        current = execute_query("SELECT * FROM dividends WHERE id = ?", (dividend_id,))
        if not current:
            return False
        
        current_data = dict(current[0])
        
        # Użyj nowych wartości lub zachowaj stare
        new_dividend_per_share = dividend_per_share if dividend_per_share is not None else current_data['dividend_per_share']
        new_quantity = quantity if quantity is not None else current_data['quantity']
        new_total_amount = total_amount if total_amount is not None else current_data['total_amount_usd']
        new_tax_withheld = tax_withheld if tax_withheld is not None else current_data['tax_withheld_usd']
        new_ex_date = ex_date if ex_date is not None else current_data['ex_date']
        new_pay_date = pay_date if pay_date is not None else current_data['pay_date']
        
        query = """
            UPDATE dividends 
            SET dividend_per_share = ?, quantity = ?, total_amount_usd = ?, 
                tax_withheld_usd = ?, ex_date = ?, pay_date = ?
            WHERE id = ?
        """
        
        return execute_update(query, (
            new_dividend_per_share, new_quantity, new_total_amount,
            new_tax_withheld, new_ex_date, new_pay_date, dividend_id
        )) > 0
    
    @staticmethod
    def delete_dividend(dividend_id: int) -> bool:
        """Usuwa dywidendę."""
        return execute_update("DELETE FROM dividends WHERE id = ?", (dividend_id,)) > 0
    
    @staticmethod
    def get_dividend_reinvestment_analysis() -> List[Dict[str, Any]]:
        """Analizuje potencjał reinwestycji dywidend."""
        query = """
            SELECT 
                s.symbol,
                s.name,
                s.current_price_usd,
                SUM(d.total_amount_usd) as total_dividends_received,
                CASE 
                    WHEN s.current_price_usd > 0 THEN 
                        CAST(SUM(d.total_amount_usd) / s.current_price_usd AS INTEGER)
                    ELSE 0
                END as shares_could_buy,
                CASE 
                    WHEN s.current_price_usd > 0 THEN 
                        (SUM(d.total_amount_usd) / s.current_price_usd) * s.current_price_usd
                    ELSE 0
                END as reinvestment_value
            FROM stocks s
            LEFT JOIN dividends d ON s.id = d.stock_id 
                AND d.pay_date >= date('now', '-12 months')
            WHERE s.quantity > 0
            GROUP BY s.id, s.symbol, s.name
            HAVING total_dividends_received > 0
            ORDER BY reinvestment_value DESC
        """
        return [dict(row) for row in execute_query(query)]