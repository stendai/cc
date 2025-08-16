import pandas as pd
from typing import Union, Optional
from datetime import datetime, date

def format_currency(amount: Union[float, int], currency: str = "USD", decimals: int = 2) -> str:
    """Formatuje kwotę jako walutę."""
    if amount is None:
        return "N/A"
    
    if currency == "USD":
        symbol = "$"
    elif currency == "PLN":
        symbol = "zł"
    else:
        symbol = currency
    
    formatted = f"{amount:,.{decimals}f}"
    
    if currency == "PLN":
        return f"{formatted} {symbol}"
    else:
        return f"{symbol}{formatted}"

def format_percentage(value: Union[float, int], decimals: int = 2) -> str:
    """Formatuje wartość jako procent."""
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}%"

def format_shares(quantity: Union[float, int]) -> str:
    """Formatuje liczbę akcji."""
    if quantity is None:
        return "N/A"
    return f"{int(quantity)} szt."

def format_date(date_value: Union[str, date, datetime], format_str: str = "%Y-%m-%d") -> str:
    """Formatuje datę."""
    if date_value is None:
        return "N/A"
    
    if isinstance(date_value, str):
        try:
            date_value = datetime.strptime(date_value, "%Y-%m-%d").date()
        except ValueError:
            return date_value
    
    if isinstance(date_value, datetime):
        date_value = date_value.date()
    
    return date_value.strftime(format_str)

def format_polish_date(date_value: Union[str, date, datetime]) -> str:
    """Formatuje datę w polskim formacie."""
    if date_value is None:
        return "N/A"
    
    if isinstance(date_value, str):
        try:
            date_value = datetime.strptime(date_value, "%Y-%m-%d").date()
        except ValueError:
            return date_value
    
    if isinstance(date_value, datetime):
        date_value = date_value.date()
    
    return date_value.strftime("%d.%m.%Y")

def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """Oblicza procentową zmianę między dwiema wartościami."""
    if old_value == 0:
        return 0.0
    return ((new_value - old_value) / old_value) * 100

def format_gain_loss(amount: Union[float, int], show_sign: bool = True) -> tuple[str, str]:
    """Formatuje zysk/stratę z odpowiednim kolorem."""
    if amount is None:
        return "N/A", "gray"
    
    color = "green" if amount >= 0 else "red"
    sign = "+" if amount > 0 and show_sign else ""
    formatted = f"{sign}{format_currency(amount)}"
    
    return formatted, color

def format_option_description(option_type: str, strike: float, expiry: Union[str, date]) -> str:
    """Formatuje opis opcji."""
    if isinstance(expiry, str):
        try:
            expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            expiry_str = expiry_date.strftime("%d.%m.%Y")
        except ValueError:
            expiry_str = expiry
    else:
        expiry_str = expiry.strftime("%d.%m.%Y")
    
    return f"{option_type} ${strike:.2f} exp. {expiry_str}"

def calculate_days_to_expiry(expiry_date: Union[str, date, datetime]) -> int:
    """Oblicza liczbę dni do wygaśnięcia."""
    if isinstance(expiry_date, str):
        expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d").date()
    elif isinstance(expiry_date, datetime):
        expiry_date = expiry_date.date()
    
    today = date.today()
    delta = expiry_date - today
    return delta.days

def format_days_to_expiry(days: int) -> tuple[str, str]:
    """Formatuje dni do wygaśnięcia z odpowiednim kolorem."""
    if days < 0:
        return "Wygasła", "red"
    elif days == 0:
        return "Dzisiaj", "orange"
    elif days <= 7:
        return f"{days} dni", "orange"
    elif days <= 30:
        return f"{days} dni", "yellow"
    else:
        return f"{days} dni", "green"

def style_dataframe(df: pd.DataFrame, currency_columns: list = None, 
                   percentage_columns: list = None, gain_loss_columns: list = None) -> pd.DataFrame:
    """Stylizuje DataFrame z odpowiednim formatowaniem."""
    styled_df = df.copy()
    
    # Formatowanie kolumn walutowych
    if currency_columns:
        for col in currency_columns:
            if col in styled_df.columns:
                styled_df[col] = styled_df[col].apply(lambda x: format_currency(x) if pd.notnull(x) else "N/A")
    
    # Formatowanie kolumn procentowych
    if percentage_columns:
        for col in percentage_columns:
            if col in styled_df.columns:
                styled_df[col] = styled_df[col].apply(lambda x: format_percentage(x) if pd.notnull(x) else "N/A")
    
    return styled_df

def get_status_color(status: str) -> str:
    """Zwraca kolor dla różnych statusów."""
    status_colors = {
        'OPEN': 'green',
        'CLOSED': 'blue',
        'EXPIRED': 'orange',
        'ASSIGNED': 'red',
        'ACTIVE': 'green',
        'INACTIVE': 'gray',
        'BUY': 'red',
        'SELL': 'green'
    }
    return status_colors.get(status.upper(), 'gray')

def format_number_compact(number: Union[float, int]) -> str:
    """Formatuje liczbę w kompaktowej formie (K, M, B)."""
    if number is None:
        return "N/A"
    
    if abs(number) >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f}B"
    elif abs(number) >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    elif abs(number) >= 1_000:
        return f"{number / 1_000:.1f}K"
    else:
        return f"{number:.1f}"