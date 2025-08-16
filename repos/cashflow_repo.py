from typing import List, Optional, Dict, Any
from datetime import date, datetime
from db import execute_query, execute_insert, execute_update

class CashflowRepository:
    
    @staticmethod
    def get_all_cashflows() -> List[Dict[str, Any]]:
        """Pobiera wszystkie przepływy pieniężne."""
        query = """
            SELECT 
                c.*,
                s.symbol as stock_symbol,
                s.name as stock_name
            FROM cashflows c
            LEFT JOIN stocks s ON c.related_stock_id = s.id
            ORDER BY c.date DESC, c.created_at DESC
        """
        return [dict(row) for row in execute_query(query)]
    
    @staticmethod
    def add_cashflow(transaction_type: str, amount_usd: float, date_value: date,
                    description: str = None, related_stock_id: int = None,
                    related_option_id: int = None) -> int:
        """Dodaje nowy przepływ pieniężny."""
        query = """
            INSERT INTO cashflows 
            (transaction_type, amount_usd, date, description, 
             related_stock_id, related_option_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        return execute_insert(query, (
            transaction_type, amount_usd, date_value, description,
            related_stock_id, related_option_id
        ))
    
    @staticmethod
    def get_cashflows_by_type(transaction_type: str) -> List[Dict[str, Any]]:
        """Pobiera przepływy pieniężne według typu."""
        query = """
            SELECT 
                c.*,
                s.symbol as stock_symbol
            FROM cashflows c
            LEFT JOIN stocks s ON c.related_stock_id = s.id
            WHERE c.transaction_type = ?
            ORDER BY c.date DESC
        """
        return [dict(row) for row in execute_query(query, (transaction_type,))]
    
    @staticmethod
    def get_cashflow_summary(year: Optional[int] = None) -> Dict[str, Any]:
        """Pobiera podsumowanie przepływów pieniężnych."""
        base_query = """
            SELECT 
                SUM(CASE WHEN transaction_type = 'DEPOSIT' THEN amount_usd ELSE 0 END) as total_deposits,
                SUM(CASE WHEN transaction_type = 'WITHDRAWAL' THEN amount_usd ELSE 0 END) as total_withdrawals,
                SUM(CASE WHEN transaction_type = 'DIVIDEND' THEN amount_usd ELSE 0 END) as total_dividends,
                SUM(CASE WHEN transaction_type = 'OPTION_PREMIUM' THEN amount_usd ELSE 0 END) as total_option_premiums,
                SUM(CASE WHEN transaction_type = 'COMMISSION' THEN amount_usd ELSE 0 END) as total_commissions,
                SUM(CASE WHEN transaction_type = 'TAX' THEN amount_usd ELSE 0 END) as total_taxes,
                SUM(CASE WHEN transaction_type IN ('DEPOSIT', 'DIVIDEND', 'OPTION_PREMIUM') 
                    THEN amount_usd 
                    ELSE -amount_usd END) as net_cashflow
            FROM cashflows
        """
        
        params = []
        if year:
            base_query += " WHERE strftime('%Y', date) = ?"
            params.append(str(year))
        
        result = execute_query(base_query, params)
        return dict(result[0]) if result else {}
    
    @staticmethod
    def get_monthly_cashflows(year: int) -> List[Dict[str, Any]]:
        """Pobiera przepływy pieniężne pogrupowane według miesięcy."""
        query = """
            SELECT 
                strftime('%m', date) as month,
                strftime('%Y-%m', date) as year_month,
                SUM(CASE WHEN transaction_type IN ('DEPOSIT', 'DIVIDEND', 'OPTION_PREMIUM') 
                    THEN amount_usd ELSE 0 END) as inflows,
                SUM(CASE WHEN transaction_type IN ('WITHDRAWAL', 'COMMISSION', 'TAX') 
                    THEN amount_usd ELSE 0 END) as outflows,
                SUM(CASE WHEN transaction_type IN ('DEPOSIT', 'DIVIDEND', 'OPTION_PREMIUM') 
                    THEN amount_usd 
                    ELSE -amount_usd END) as net_flow
            FROM cashflows
            WHERE strftime('%Y', date) = ?
            GROUP BY strftime('%Y-%m', date)
            ORDER BY year_month
        """
        return [dict(row) for row in execute_query(query, (str(year),))]
    
    @staticmethod
    def get_account_balance() -> float:
        """Oblicza aktualny stan konta."""
        query = """
            SELECT 
                SUM(CASE 
                    WHEN transaction_type IN ('DEPOSIT', 'DIVIDEND', 'OPTION_PREMIUM') 
                    THEN amount_usd 
                    ELSE -amount_usd 
                END) as balance
            FROM cashflows
        """
        result = execute_query(query)
        return result[0]['balance'] if result and result[0]['balance'] else 0.0
    
    @staticmethod
    def get_cashflows_by_date_range(start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Pobiera przepływy pieniężne w określonym okresie."""
        query = """
            SELECT 
                c.*,
                s.symbol as stock_symbol
            FROM cashflows c
            LEFT JOIN stocks s ON c.related_stock_id = s.id
            WHERE c.date BETWEEN ? AND ?
            ORDER BY c.date DESC
        """
        return [dict(row) for row in execute_query(query, 
                    (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))]
    
    @staticmethod
    def delete_cashflow(cashflow_id: int) -> bool:
        """Usuwa przepływ pieniężny."""
        return execute_update("DELETE FROM cashflows WHERE id = ?", (cashflow_id,)) > 0
    
    @staticmethod
    def update_cashflow(cashflow_id: int, transaction_type: str = None,
                       amount_usd: float = None, date_value: date = None,
                       description: str = None) -> bool:
        """Aktualizuje istniejący przepływ pieniężny."""
        
        # Pobierz aktualne dane
        current = execute_query("SELECT * FROM cashflows WHERE id = ?", (cashflow_id,))
        if not current:
            return False
        
        current_data = dict(current[0])
        
        # Użyj nowych wartości lub zachowaj stare
        new_type = transaction_type if transaction_type is not None else current_data['transaction_type']
        new_amount = amount_usd if amount_usd is not None else current_data['amount_usd']
        new_date = date_value if date_value is not None else current_data['date']
        new_description = description if description is not None else current_data['description']
        
        query = """
            UPDATE cashflows 
            SET transaction_type = ?, amount_usd = ?, date = ?, description = ?
            WHERE id = ?
        """
        
        return execute_update(query, (
            new_type, new_amount, new_date, new_description, cashflow_id
        )) > 0
    
    @staticmethod
    def get_investment_analysis() -> Dict[str, Any]:
        """Analizuje efektywność inwestycji."""
        
        # Całkowite wpłaty
        deposits_query = """
            SELECT SUM(amount_usd) as total
            FROM cashflows
            WHERE transaction_type = 'DEPOSIT'
        """
        deposits_result = execute_query(deposits_query)
        total_deposits = deposits_result[0]['total'] if deposits_result and deposits_result[0]['total'] else 0
        
        # Całkowite wypłaty
        withdrawals_query = """
            SELECT SUM(amount_usd) as total
            FROM cashflows
            WHERE transaction_type = 'WITHDRAWAL'
        """
        withdrawals_result = execute_query(withdrawals_query)
        total_withdrawals = withdrawals_result[0]['total'] if withdrawals_result and withdrawals_result[0]['total'] else 0
        
        # Otrzymane dywidendy
        dividends_query = """
            SELECT SUM(amount_usd) as total
            FROM cashflows
            WHERE transaction_type = 'DIVIDEND'
        """
        dividends_result = execute_query(dividends_query)
        total_dividends = dividends_result[0]['total'] if dividends_result and dividends_result[0]['total'] else 0
        
        # Premium z opcji
        options_query = """
            SELECT SUM(amount_usd) as total
            FROM cashflows
            WHERE transaction_type = 'OPTION_PREMIUM'
        """
        options_result = execute_query(options_query)
        total_options = options_result[0]['total'] if options_result and options_result[0]['total'] else 0
        
        # Aktualna wartość portfela (z tabeli stocks)
        portfolio_query = """
            SELECT SUM(quantity * current_price_usd) as total
            FROM stocks
            WHERE quantity > 0
        """
        portfolio_result = execute_query(portfolio_query)
        current_portfolio_value = portfolio_result[0]['total'] if portfolio_result and portfolio_result[0]['total'] else 0
        
        # Oblicz zwrot z inwestycji
        net_invested = total_deposits - total_withdrawals
        total_income = total_dividends + total_options
        total_value = current_portfolio_value + total_withdrawals + total_income
        
        if net_invested > 0:
            roi_percentage = ((total_value - total_deposits) / total_deposits) * 100
        else:
            roi_percentage = 0
        
        return {
            'total_deposits': total_deposits,
            'total_withdrawals': total_withdrawals,
            'net_invested': net_invested,
            'total_dividends': total_dividends,
            'total_option_premiums': total_options,
            'total_income': total_income,
            'current_portfolio_value': current_portfolio_value,
            'total_value': total_value,
            'roi_percentage': roi_percentage
        }
    
    @staticmethod
    def get_cashflow_chart_data() -> List[Dict[str, Any]]:
        """Pobiera dane do wykresu przepływów pieniężnych."""
        query = """
            SELECT 
                date,
                transaction_type,
                amount_usd,
                SUM(CASE 
                    WHEN transaction_type IN ('DEPOSIT', 'DIVIDEND', 'OPTION_PREMIUM') 
                    THEN amount_usd 
                    ELSE -amount_usd 
                END) OVER (ORDER BY date, created_at) as running_balance
            FROM cashflows
            ORDER BY date, created_at
        """
        return [dict(row) for row in execute_query(query)]