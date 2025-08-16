import sqlite3
import os
from contextlib import contextmanager
from typing import Optional

DATABASE_PATH = "portfolio.db"

def init_database():
    """Inicjalizuje bazę danych i tworzy niezbędne tabele."""
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        
        # Usuń stare tabele jeśli istnieją (dla pełnego resetu)
        cursor.execute("DROP TABLE IF EXISTS stock_transactions")
        cursor.execute("DROP TABLE IF EXISTS options")
        cursor.execute("DROP TABLE IF EXISTS dividends")
        cursor.execute("DROP TABLE IF EXISTS cashflows")
        cursor.execute("DROP TABLE IF EXISTS exchange_rates")
        cursor.execute("DROP TABLE IF EXISTS stocks")
        
        # Tabela akcji
        cursor.execute("""
            CREATE TABLE stocks (
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
        
        # Tabela transakcji akcji - POPRAWIONA NAZWA KOLUMNY
        cursor.execute("""
            CREATE TABLE stock_transactions (
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
            CREATE TABLE options (
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
            CREATE TABLE dividends (
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
            CREATE TABLE cashflows (
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
            CREATE TABLE exchange_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency_pair TEXT NOT NULL,
                rate REAL NOT NULL,
                date DATE NOT NULL,
                source TEXT DEFAULT 'NBP',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(currency_pair, date)
            )
        """)
        
        # Dodaj przykładowe dane testowe
        cursor.execute("""
            INSERT INTO stocks (symbol, name, quantity, avg_price_usd, current_price_usd)
            VALUES 
                ('AAPL', 'Apple Inc.', 0, 0.0, 0.0),
                ('MSFT', 'Microsoft Corporation', 0, 0.0, 0.0),
                ('GOOGL', 'Alphabet Inc.', 0, 0.0, 0.0)
        """)
        
        # Dodaj przykładowy kurs USD/PLN
        cursor.execute("""
            INSERT INTO exchange_rates (currency_pair, rate, date, source)
            VALUES ('USD/PLN', 4.0, date('now'), 'NBP')
        """)
        
        conn.commit()
        print("✅ Baza danych została zainicjalizowana z nową strukturą")

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

def check_database_structure():
    """Sprawdza i wyświetla strukturę bazy danych."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Pobierz listę tabel
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("📊 Struktura bazy danych:")
        for table in tables:
            table_name = table['name']
            print(f"\n🔹 Tabela: {table_name}")
            
            # Pobierz kolumny tabeli
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            for col in columns:
                print(f"   - {col['name']} ({col['type']})")

def backup_database(backup_path: str = None):
    """Tworzy kopię zapasową bazy danych."""
    if backup_path is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"portfolio_backup_{timestamp}.db"
    
    try:
        import shutil
        shutil.copy2(DATABASE_PATH, backup_path)
        print(f"✅ Kopia zapasowa utworzona: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Błąd tworzenia kopii zapasowej: {e}")
        return False

def restore_database(backup_path: str):
    """Przywraca bazę danych z kopii zapasowej."""
    try:
        import shutil
        shutil.copy2(backup_path, DATABASE_PATH)
        print(f"✅ Baza danych przywrócona z: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Błąd przywracania bazy danych: {e}")
        return False

# Inicjalizuj bazę danych przy imporcie modułu
if __name__ == "__main__":
    # Utwórz kopię zapasową jeśli baza istnieje
    if os.path.exists(DATABASE_PATH):
        backup_database()
    
    init_database()
    check_database_structure()
    print("🎉 Baza danych gotowa do użycia!")