# Wykonaj w konsoli Python w katalogu projektu:

import sqlite3

# Połącz z bazą
conn = sqlite3.connect('portfolio.db')
cursor = conn.cursor()

# Sprawdź obecną strukturę
print("=== OBECNA STRUKTURA ===")
cursor.execute("PRAGMA table_info(stock_transactions)")
columns = cursor.fetchall()
for col in columns:
    print(f"- {col[1]} ({col[2]})")

print("\n=== DODAWANIE KOLUMN ===")

# Dodaj brakujące kolumny
try:
    cursor.execute("ALTER TABLE stock_transactions ADD COLUMN usd_pln_rate REAL")
    print("✅ Dodano usd_pln_rate")
except sqlite3.OperationalError as e:
    print(f"⚠️ usd_pln_rate: {e}")

try:
    cursor.execute("ALTER TABLE stock_transactions ADD COLUMN price_pln REAL")
    print("✅ Dodano price_pln")
except sqlite3.OperationalError as e:
    print(f"⚠️ price_pln: {e}")

try:
    cursor.execute("ALTER TABLE stock_transactions ADD COLUMN commission_pln REAL")
    print("✅ Dodano commission_pln")
except sqlite3.OperationalError as e:
    print(f"⚠️ commission_pln: {e}")

# Sprawdź czy są dane do aktualizacji
cursor.execute("SELECT COUNT(*) FROM stock_transactions")
count = cursor.fetchone()[0]
print(f"\n📊 Transakcji w bazie: {count}")

if count > 0:
    print("\n=== AKTUALIZACJA ISTNIEJĄCYCH DANYCH ===")
    
    # Zaktualizuj NULL wartości
    cursor.execute("""
        UPDATE stock_transactions 
        SET 
            usd_pln_rate = COALESCE(usd_pln_rate, 4.0),
            price_pln = COALESCE(price_pln, price_usd * 4.0),
            commission_pln = COALESCE(commission_pln, commission_usd * 4.0)
        WHERE usd_pln_rate IS NULL OR price_pln IS NULL OR commission_pln IS NULL
    """)
    
    updated = cursor.rowcount
    print(f"✅ Zaktualizowano {updated} rekordów")

conn.commit()

print("\n=== NOWA STRUKTURA ===")
cursor.execute("PRAGMA table_info(stock_transactions)")
columns = cursor.fetchall()
for col in columns:
    print(f"- {col[1]} ({col[2]})")

conn.close()
print("\n🎉 Baza naprawiona! Teraz uruchom ponownie aplikację.")