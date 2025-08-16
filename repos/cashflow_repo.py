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
        """Pobiera podsumowanie przepływów pieniężnych z obsługą MARGIN."""
        base_query = """
            SELECT 
                SUM(CASE WHEN transaction_type = 'DEPOSIT' THEN amount_usd ELSE 0 END) as total_deposits,
                SUM(CASE WHEN transaction_type = 'WITHDRAWAL' THEN amount_usd ELSE 0 END) as total_withdrawals,
                SUM(CASE WHEN transaction_type = 'DIVIDEND' THEN amount_usd ELSE 0 END) as total_dividends,
                SUM(CASE WHEN transaction_type = 'OPTION_PREMIUM' THEN amount_usd ELSE 0 END) as total_option_premiums,
                SUM(CASE WHEN transaction_type = 'COMMISSION' THEN amount_usd ELSE 0 END) as total_commissions,
                SUM(CASE WHEN transaction_type = 'TAX' THEN amount_usd ELSE 0 END) as total_taxes,
                SUM(CASE WHEN transaction_type = 'MARGIN_INTEREST' THEN amount_usd ELSE 0 END) as total_margin_interest,
                SUM(CASE WHEN transaction_type = 'MARGIN_CALL' THEN amount_usd ELSE 0 END) as total_margin_calls,
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
        summary = dict(result[0]) if result else {}
        
        # Zapewnij że wszystkie wartości są liczbami, nie None
        for key in summary:
            if summary[key] is None:
                summary[key] = 0.0
        
        return summary
    
    @staticmethod
    def get_monthly_cashflows(year: int) -> List[Dict[str, Any]]:
        """Pobiera przepływy pieniężne pogrupowane według miesięcy."""
        query = """
            SELECT 
                strftime('%m', date) as month,
                strftime('%Y-%m', date) as year_month,
                SUM(CASE WHEN transaction_type IN ('DEPOSIT', 'DIVIDEND', 'OPTION_PREMIUM') 
                    THEN amount_usd ELSE 0 END) as inflows,
                SUM(CASE WHEN transaction_type IN ('WITHDRAWAL', 'COMMISSION', 'TAX', 'MARGIN_INTEREST', 'MARGIN_CALL') 
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
        """Oblicza aktualny stan konta z uwzględnieniem MARGIN."""
        query = """
            SELECT 
                COALESCE(SUM(CASE 
                    WHEN transaction_type IN ('DEPOSIT', 'DIVIDEND', 'OPTION_PREMIUM') 
                    THEN amount_usd 
                    ELSE -amount_usd 
                END), 0.0) as balance
            FROM cashflows
        """
        result = execute_query(query)
        return result[0]['balance'] if result and result[0]['balance'] is not None else 0.0
    
    @staticmethod
    def get_margin_metrics() -> Dict[str, Any]:
        """Pobiera metryki związane z margin."""
        
        # Stan konta
        account_balance = CashflowRepository.get_account_balance()
        
        # Wartość portfela
        portfolio_query = """
            SELECT COALESCE(SUM(quantity * current_price_usd), 0.0) as portfolio_value
            FROM stocks
            WHERE quantity > 0
        """
        portfolio_result = execute_query(portfolio_query)
        portfolio_value = portfolio_result[0]['portfolio_value'] if portfolio_result else 0.0
        
        # Oblicz metryki margin
        total_equity = account_balance + portfolio_value
        margin_used = max(0, -account_balance)  # Ujemny stan = wykorzystany margin
        margin_available = max(0, portfolio_value * 0.5 - margin_used)  # 50% margin ratio
        maintenance_margin = portfolio_value * 0.25  # 25% maintenance margin
        
        # Margin ratio
        margin_ratio = (margin_used / total_equity * 100) if total_equity > 0 else 0
        
        # Koszty margin
        margin_costs_query = """
            SELECT COALESCE(SUM(amount_usd), 0.0) as total_margin_costs
            FROM cashflows
            WHERE transaction_type = 'MARGIN_INTEREST'
        """
        margin_costs_result = execute_query(margin_costs_query)
        total_margin_costs = margin_costs_result[0]['total_margin_costs'] if margin_costs_result else 0.0
        
        return {
            'account_balance': account_balance,
            'portfolio_value': portfolio_value,
            'total_equity': total_equity,
            'margin_used': margin_used,
            'margin_available': margin_available,
            'maintenance_margin': maintenance_margin,
            'margin_ratio': margin_ratio,
            'total_margin_costs': total_margin_costs,
            'margin_call_risk': margin_ratio > 50,  # Ryzyko margin call przy >50%
            'high_risk': margin_ratio > 75  # Wysokie ryzyko przy >75%
        }
    
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
    def get_margin_history(year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Pobiera historię transakcji margin."""
        base_query = """
            SELECT 
                date,
                transaction_type,
                amount_usd,
                description
            FROM cashflows
            WHERE transaction_type IN ('MARGIN_INTEREST', 'MARGIN_CALL')
        """
        
        params = []
        if year:
            base_query += " AND strftime('%Y', date) = ?"
            params.append(str(year))
        
        base_query += " ORDER BY date DESC"
        
        return [dict(row) for row in execute_query(base_query, params)]
    
    @staticmethod
    def calculate_margin_call_price(stock_symbol: str) -> Optional[float]:
        """Oblicza cenę akcji przy której wystąpi margin call."""
        
        # Pobierz dane o akcji
        stock_query = """
            SELECT quantity, current_price_usd
            FROM stocks
            WHERE symbol = ? AND quantity > 0
        """
        stock_result = execute_query(stock_query, (stock_symbol,))
        
        if not stock_result:
            return None
        
        stock_data = stock_result[0]
        quantity = stock_data['quantity']
        current_price = stock_data['current_price_usd']
        
        # Pobierz stan konta
        account_balance = CashflowRepository.get_account_balance()
        
        if account_balance >= 0:  # Brak margin
            return None
        
        margin_used = -account_balance
        
        # Oblicz cenę margin call (25% maintenance margin)
        # Równanie: (quantity * price + account_balance) / (quantity * price) >= 0.25
        # Rozwiązanie: price >= margin_used / (quantity * 0.75)
        
        margin_call_price = margin_used / (quantity * 0.75)
        
        return margin_call_price if margin_call_price > 0 else None
    
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
        """Analizuje efektywność inwestycji z uwzględnieniem margin."""
        
        # Całkowite wpłaty
        deposits_query = """
            SELECT COALESCE(SUM(amount_usd), 0.0) as total
            FROM cashflows
            WHERE transaction_type = 'DEPOSIT'
        """
        deposits_result = execute_query(deposits_query)
        total_deposits = deposits_result[0]['total'] if deposits_result else 0.0
        
        # Całkowite wypłaty
        withdrawals_query = """
            SELECT COALESCE(SUM(amount_usd), 0.0) as total
            FROM cashflows
            WHERE transaction_type = 'WITHDRAWAL'
        """
        withdrawals_result = execute_query(withdrawals_query)
        total_withdrawals = withdrawals_result[0]['total'] if withdrawals_result else 0.0
        
        # Otrzymane dywidendy
        dividends_query = """
            SELECT COALESCE(SUM(amount_usd), 0.0) as total
            FROM cashflows
            WHERE transaction_type = 'DIVIDEND'
        """
        dividends_result = execute_query(dividends_query)
        total_dividends = dividends_result[0]['total'] if dividends_result else 0.0
        
        # Premium z opcji
        options_query = """
            SELECT COALESCE(SUM(amount_usd), 0.0) as total
            FROM cashflows
            WHERE transaction_type = 'OPTION_PREMIUM'
        """
        options_result = execute_query(options_query)
        total_options = options_result[0]['total'] if options_result else 0.0
        
        # Koszty margin
        margin_costs_query = """
            SELECT COALESCE(SUM(amount_usd), 0.0) as total
            FROM cashflows
            WHERE transaction_type = 'MARGIN_INTEREST'
        """
        margin_costs_result = execute_query(margin_costs_query)
        total_margin_costs = margin_costs_result[0]['total'] if margin_costs_result else 0.0
        
        # Aktualna wartość portfela (z tabeli stocks)
        portfolio_query = """
            SELECT COALESCE(SUM(quantity * current_price_usd), 0.0) as total
            FROM stocks
            WHERE quantity > 0
        """
        portfolio_result = execute_query(portfolio_query)
        current_portfolio_value = portfolio_result[0]['total'] if portfolio_result else 0.0
        
        # Oblicz zwrot z inwestycji
        net_invested = total_deposits - total_withdrawals
        total_income = total_dividends + total_options
        total_costs = total_margin_costs  # Dodaj prowizje i podatki jeśli potrzebne
        
        # Wartość całkowita = portfel + wypłaty + dochody - koszty margin
        total_value = current_portfolio_value + total_withdrawals + total_income - total_costs
        
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
            'total_margin_costs': total_margin_costs,
            'total_costs': total_costs,
            'current_portfolio_value': current_portfolio_value,
            'total_value': total_value,
            'roi_percentage': roi_percentage,
            'net_profit_loss': total_value - total_deposits
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
    
    @staticmethod
    def get_margin_utilization_history() -> List[Dict[str, Any]]:
        """Pobiera historię wykorzystania margin."""
        
        # Ta funkcja wymagałaby więcej danych historycznych
        # Na razie zwracamy aktualny stan
        current_metrics = CashflowRepository.get_margin_metrics()
        
        return [{
            'date': datetime.now().date(),
            'margin_used': current_metrics['margin_used'],
            'margin_ratio': current_metrics['margin_ratio'],
            'total_equity': current_metrics['total_equity']
        }]