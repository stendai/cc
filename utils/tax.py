from datetime import date, datetime
from typing import Union, Optional, Tuple
import requests
from db import execute_query, execute_insert

# Stawki podatkowe w Polsce
CAPITAL_GAINS_TAX_RATE = 0.19  # 19% podatek od zysków kapitałowych
DIVIDEND_TAX_RATE = 0.19       # 19% podatek od dywidend
US_WITHHOLDING_TAX = 0.15      # 15% podatek u źródła w USA (umowa podatkowa)

def get_nbp_exchange_rate(date_value: Union[str, date], from_cache: bool = True) -> Optional[float]:
    """
    Pobiera kurs USD/PLN z NBP na określoną datę.
    
    Args:
        date_value: Data w formacie YYYY-MM-DD lub obiekt date
        from_cache: Czy używać cache z bazy danych
    
    Returns:
        Kurs USD/PLN lub None jeśli nie można pobrać
    """
    if isinstance(date_value, str):
        date_obj = datetime.strptime(date_value, "%Y-%m-%d").date()
    else:
        date_obj = date_value
    
    date_str = date_obj.strftime("%Y-%m-%d")
    
    # Sprawdź cache w bazie danych
    if from_cache:
        cached_rate = execute_query(
            "SELECT rate FROM exchange_rates WHERE currency_pair = 'USD/PLN' AND date = ?",
            (date_str,)
        )
        if cached_rate:
            return cached_rate[0]['rate']
    
    try:
        # Pobierz z API NBP
        url = f"http://api.nbp.pl/api/exchangerates/rates/a/usd/{date_str}/"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            rate = data['rates'][0]['mid']
            
            # Zapisz w cache
            execute_insert(
                "INSERT OR REPLACE INTO exchange_rates (currency_pair, rate, date, source) VALUES (?, ?, ?, ?)",
                ("USD/PLN", rate, date_str, "NBP")
            )
            
            return rate
        else:
            # Jeśli nie ma kursu na daną datę, spróbuj z poprzedniego dnia roboczego
            return get_previous_working_day_rate(date_obj)
            
    except requests.RequestException:
        # W przypadku błędu sieci, spróbuj znaleźć ostatni dostępny kurs
        return get_last_available_rate(date_obj)

def get_previous_working_day_rate(date_obj: date, max_days: int = 10) -> Optional[float]:
    """Znajduje kurs z poprzedniego dnia roboczego."""
    from datetime import timedelta
    
    current_date = date_obj
    for _ in range(max_days):
        current_date -= timedelta(days=1)
        # Pomiń weekendy
        if current_date.weekday() >= 5:  # Sobota = 5, Niedziela = 6
            continue
            
        rate = get_nbp_exchange_rate(current_date, from_cache=True)
        if rate:
            return rate
    
    return None

def get_last_available_rate(date_obj: date) -> Optional[float]:
    """Znajduje ostatni dostępny kurs z bazy danych."""
    rates = execute_query(
        "SELECT rate FROM exchange_rates WHERE currency_pair = 'USD/PLN' AND date <= ? ORDER BY date DESC LIMIT 1",
        (date_obj.strftime("%Y-%m-%d"),)
    )
    return rates[0]['rate'] if rates else None

def calculate_capital_gains_tax(gain_usd: float, transaction_date: Union[str, date]) -> Tuple[float, float, float]:
    """
    Oblicza podatek od zysków kapitałowych.
    
    Args:
        gain_usd: Zysk w USD
        transaction_date: Data transakcji
    
    Returns:
        Tuple: (zysk_w_pln, podatek_w_pln, kurs_nbp)
    """
    if gain_usd <= 0:
        return 0.0, 0.0, 0.0
    
    exchange_rate = get_nbp_exchange_rate(transaction_date)
    if not exchange_rate:
        raise ValueError(f"Nie można pobrać kursu NBP na datę {transaction_date}")
    
    gain_pln = gain_usd * exchange_rate
    tax_pln = gain_pln * CAPITAL_GAINS_TAX_RATE
    
    return gain_pln, tax_pln, exchange_rate

def calculate_dividend_tax(dividend_usd: float, us_tax_withheld_usd: float, 
                         payment_date: Union[str, date]) -> Tuple[float, float, float, float]:
    """
    Oblicza podatek od dywidend z uwzględnieniem podatku u źródła w USA.
    
    Args:
        dividend_usd: Dywidenda brutto w USD
        us_tax_withheld_usd: Podatek potrącony w USA
        payment_date: Data wypłaty dywidendy
    
    Returns:
        Tuple: (dywidenda_pln, podatek_do_zaplaty_pln, podatek_usa_pln, kurs_nbp)
    """
    exchange_rate = get_nbp_exchange_rate(payment_date)
    if not exchange_rate:
        raise ValueError(f"Nie można pobrać kursu NBP na datę {payment_date}")
    
    dividend_pln = dividend_usd * exchange_rate
    us_tax_pln = us_tax_withheld_usd * exchange_rate
    
    # Podatek należny w Polsce (19%)
    total_tax_due_pln = dividend_pln * DIVIDEND_TAX_RATE
    
    # Podatek do zapłaty w Polsce po odliczeniu podatku USA
    tax_to_pay_pln = max(0, total_tax_due_pln - us_tax_pln)
    
    return dividend_pln, tax_to_pay_pln, us_tax_pln, exchange_rate

def calculate_option_premium_tax(premium_usd: float, transaction_date: Union[str, date]) -> Tuple[float, float, float]:
    """
    Oblicza podatek od premium z opcji.
    
    Args:
        premium_usd: Otrzymane premium w USD
        transaction_date: Data transakcji
    
    Returns:
        Tuple: (premium_pln, podatek_pln, kurs_nbp)
    """
    exchange_rate = get_nbp_exchange_rate(transaction_date)
    if not exchange_rate:
        raise ValueError(f"Nie można pobrać kursu NBP na datę {transaction_date}")
    
    premium_pln = premium_usd * exchange_rate
    tax_pln = premium_pln * CAPITAL_GAINS_TAX_RATE
    
    return premium_pln, tax_pln, exchange_rate

def calculate_fifo_cost_basis(transactions: list, quantity_sold: int) -> Tuple[float, list]:
    """
    Oblicza koszty uzyskania przychodu metodą FIFO.
    
    Args:
        transactions: Lista transakcji zakupu [(quantity, price, date), ...]
        quantity_sold: Ilość sprzedanych akcji
    
    Returns:
        Tuple: (średnia_cena_sprzedanych, wykorzystane_transakcje)
    """
    if not transactions or quantity_sold <= 0:
        return 0.0, []
    
    # Sortuj transakcje po dacie (FIFO)
    sorted_transactions = sorted(transactions, key=lambda x: x[2])
    
    remaining_to_sell = quantity_sold
    total_cost = 0.0
    used_transactions = []
    
    for quantity, price, date in sorted_transactions:
        if remaining_to_sell <= 0:
            break
        
        quantity_to_use = min(remaining_to_sell, quantity)
        cost = quantity_to_use * price
        total_cost += cost
        
        used_transactions.append((quantity_to_use, price, date))
        remaining_to_sell -= quantity_to_use
    
    if remaining_to_sell > 0:
        raise ValueError(f"Niewystarczająca ilość akcji do sprzedaży. Brakuje: {remaining_to_sell}")
    
    average_cost = total_cost / quantity_sold
    return average_cost, used_transactions

def get_tax_year_summary(year: int) -> dict:
    """
    Generuje podsumowanie podatkowe za dany rok.
    
    Args:
        year: Rok podatkowy
    
    Returns:
        Słownik z podsumowaniem podatkowym
    """
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    # Zyski/straty kapitałowe
    capital_gains_query = """
        SELECT st.symbol, st.price_usd * st.quantity as proceeds,
               st.transaction_date, st.quantity
        FROM stock_transactions st
        JOIN stocks s ON st.stock_id = s.id
        WHERE st.transaction_type = 'SELL' 
        AND st.transaction_date BETWEEN ? AND ?
    """
    
    # Dywidendy
    dividends_query = """
        SELECT s.symbol, d.total_amount_usd, d.tax_withheld_usd, d.pay_date
        FROM dividends d
        JOIN stocks s ON d.stock_id = s.id
        WHERE d.pay_date BETWEEN ? AND ?
    """
    
    # Premium z opcji
    options_query = """
        SELECT s.symbol, o.premium_received, o.open_date, o.status
        FROM options o
        JOIN stocks s ON o.stock_id = s.id
        WHERE o.open_date BETWEEN ? AND ?
        OR (o.close_date BETWEEN ? AND ? AND o.status = 'CLOSED')
    """
    
    capital_gains = execute_query(capital_gains_query, (start_date, end_date))
    dividends = execute_query(dividends_query, (start_date, end_date))
    options = execute_query(options_query, (start_date, end_date, start_date, end_date))
    
    summary = {
        'year': year,
        'capital_gains': capital_gains,
        'dividends': dividends,
        'options': options,
        'total_tax_due_pln': 0.0,
        'total_us_tax_credit_pln': 0.0
    }
    
    return summary

def estimate_quarterly_tax_payment(current_gains_usd: float, current_date: date) -> float:
    """
    Szacuje kwartalną zaliczkę podatkową.
    
    Args:
        current_gains_usd: Aktualne zyski w USD
        current_date: Aktualna data
    
    Returns:
        Szacowana zaliczka w PLN
    """
    if current_gains_usd <= 0:
        return 0.0
    
    exchange_rate = get_nbp_exchange_rate(current_date)
    if not exchange_rate:
        return 0.0
    
    gains_pln = current_gains_usd * exchange_rate
    estimated_tax = gains_pln * CAPITAL_GAINS_TAX_RATE
    
    return estimated_tax