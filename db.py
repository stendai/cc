import sqlite3
import os
from contextlib import contextmanager
from typing import Optional

DATABASE_PATH = "portfolio.db"

def init_database():
    """Inicjalizuje bazę danych i tworzy niezbędne tabele."""
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        
        # Tabela akcji
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                avg_price_usd REAL NOT NULL DEFAULT 0.0,
                current_price_usd REAL DEFAULT 0.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabela transakcji akcji
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL CHECK (transaction_type IN ('BUY', 'SELL')),
                quantity INTEGER NOT NULL,
                price_usd REAL NOT NULL,
                commission_usd REAL DEFAULT 0.0,
                transaction_date DATE NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (stock_id) REFERENCES stocks (id)
            )
        """)
        
        # Tabela opcji
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                option_type TEXT NOT NULL CHECK (option_type IN ('CALL', 'PUT')),
                strike_price REAL NOT NULL,
                expiry_date DATE NOT NULL,
                premium_received REAL NOT NULL,
                quantity INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'EXPIRED', 'ASSIGNED', 'CLOSED')),
                open_date DATE NOT NULL,
                close_date DATE,
                commission_usd REAL DEFAULT 0.0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (stock_id) REFERENCES stocks (id)
            )
        """)
        
        # Tabela dywidend
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dividends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                dividend_per_share REAL NOT NULL,
                quantity INTEGER NOT NULL,
                total_amount_usd REAL NOT NULL,
                tax_withheld_usd REAL DEFAULT 0.0,
                ex_date DATE NOT NULL,
                pay_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (stock_id) REFERENCES stocks (id)
            )
        """)
        
        # Tabela przepływów pieniężnych
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cashflows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_type TEXT NOT NULL CHECK (transaction_type IN ('DEPOSIT', 'WITHDRAWAL', 'DIVIDEND', 'OPTION_PREMIUM', 'COMMISSION', 'TAX')),
                amount_usd REAL NOT NULL,
                description TEXT,
                date DATE NOT NULL,
                related_stock_id INTEGER,
                related_option_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (related_stock_id) REFERENCES stocks (id),
                FOREIGN KEY (related_option_id) REFERENCES options (id)
            )
        """)
        
        # Tabela kursów walut (do przechowywania historycznych kursów USD/PLN)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exchange_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency_pair TEXT NOT NULL,
                rate REAL NOT NULL,
                date DATE NOT NULL,
                source TEXT DEFAULT 'NBP',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(currency_pair, date)
            )
        """)
        
        conn.commit()

@contextmanager
def get_connection():
    """Context manager dla połączenia z bazą danych."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Umożliwia dostęp do kolumn po nazwach
    try:
        yield conn
    finally:
        conn.close()

def execute_query(query: str, params: tuple = ()) -> list:
    """Wykonuje zapytanie SELECT i zwraca wyniki."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

def execute_insert(query: str, params: tuple = ()) -> int:
    """Wykonuje zapytanie INSERT i zwraca ID nowego rekordu."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.lastrowid

def execute_update(query: str, params: tuple = ()) -> int:
    """Wykonuje zapytanie UPDATE/DELETE i zwraca liczbę zmienionych rekordów."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount

# Inicjalizuj bazę danych przy imporcie modułu
if __name__ == "__main__":
    init_database()
    print("Baza danych została zainicjalizowana.")