"""
Portfolio Tracker - Example Configuration
Skopiuj ten plik jako config.py i dostosuj ustawienia do swoich potrzeb.
"""

# Ustawienia bazy danych
DATABASE_CONFIG = {
    "path": "portfolio.db",
    "backup_enabled": True,
    "backup_interval_days": 7
}

# Ustawienia API zewnętrznych
API_CONFIG = {
    "yahoo_finance": {
        "enabled": True,
        "timeout": 10,
        "retry_attempts": 3
    },
    "nbp": {
        "enabled": True,
        "base_url": "http://api.nbp.pl/api",
        "timeout": 10,
        "cache_days": 30
    }
}

# Ustawienia podatkowe (Polska)
TAX_CONFIG = {
    "capital_gains_rate": 0.19,  # 19%
    "dividend_rate": 0.19,       # 19%
    "us_withholding_rate": 0.15, # 15% (umowa podatkowa)
    "quarterly_payments": True,
    "default_currency": "PLN"
}

# Ustawienia interfejsu
UI_CONFIG = {
    "theme": "light",  # light/dark
    "currency_display": "USD",  # USD/PLN/BOTH
    "date_format": "%d.%m.%Y",  # Polski format daty
    "decimal_places": 2,
    "chart_height": 400
}

# Ustawienia powiadomień
NOTIFICATIONS_CONFIG = {
    "expiring_options_days": 30,
    "assignment_risk_threshold": 0.05,  # 5%
    "tax_payment_reminders": True
}

# Ustawienia raportów
REPORTS_CONFIG = {
    "export_formats": ["CSV", "XLSX", "PDF"],
    "include_charts": True,
    "watermark": "Portfolio Tracker"
}

# Ustawienia bezpieczeństwa
SECURITY_CONFIG = {
    "backup_encryption": False,  # Wymaga dodatkowych bibliotek
    "session_timeout": 3600,     # 1 godzina w sekundach
    "log_transactions": True
}

# Ustawienia wydajności
PERFORMANCE_CONFIG = {
    "cache_prices_minutes": 5,
    "max_transactions_display": 100,
    "chart_data_points": 365
}

# Lokalizacja
LOCALE_CONFIG = {
    "language": "pl",
    "timezone": "Europe/Warsaw",
    "currency_symbol": "zł",
    "thousands_separator": " ",
    "decimal_separator": ","
}

# Ustawienia deweloperskie
DEV_CONFIG = {
    "debug_mode": False,
    "verbose_logging": False,
    "mock_api_responses": False,
    "profiling_enabled": False
}