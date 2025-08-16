import sqlite3
from datetime import date, datetime, timedelta

def check_data_before_migration():
    """Sprawdza dane przed migracją."""
    
    conn = sqlite3.connect("portfolio.db")
    cursor = conn.cursor()
    
    print("🔍 Sprawdzanie danych przed migracją...")
    
    # Sprawdź transakcje kupna
    cursor.execute("""
        SELECT st.*, s.symbol 
        FROM stock_transactions st
        JOIN stocks s ON st.stock_id = s.id
        WHERE st.transaction_type = 'BUY'
        ORDER BY st.stock_id, st.transaction_date, st.created_at
    """)
    
    transactions = cursor.fetchall()
    
    print(f"📊 Znaleziono {len(transactions)} transakcji kupna")
    
    # Sprawdź każdą transakcję
    problems = []
    
    for i, transaction in enumerate(transactions):
        transaction_id = transaction[0]
        stock_id = transaction[1]
        quantity = transaction[4]
        price_usd = transaction[5]
        commission_usd = transaction[6]
        transaction_date = transaction[7]
        symbol = transaction[-1]
        
        # Sprawdź problematyczne wartości
        issues = []
        
        if quantity is None or quantity <= 0:
            issues.append(f"quantity = {quantity}")
        
        if price_usd is None or price_usd <= 0:
            issues.append(f"price_usd = {price_usd}")
        
        if transaction_date is None:
            issues.append(f"transaction_date = {transaction_date}")
        
        if issues:
            problems.append({
                'transaction_id': transaction_id,
                'symbol': symbol,
                'date': transaction_date,
                'issues': issues
            })
            
        if i < 5:  # Pokaż pierwsze 5 dla przykładu
            print(f"  {i+1}. {symbol} - {transaction_date} - {quantity} szt. @ ${price_usd} (prowizja: ${commission_usd or 0})")
    
    if problems:
        print(f"\n⚠️ Znaleziono {len(problems)} problematycznych transakcji:")
        for problem in problems[:10]:  # Pokaż pierwsze 10
            print(f"  ID {problem['transaction_id']} ({problem['symbol']}): {', '.join(problem['issues'])}")
        
        if len(problems) > 10:
            print(f"  ... i {len(problems) - 10} więcej")
        
        return False
    
    print("✅ Wszystkie transakcje wyglądają poprawnie")
    conn.close()
    return True

def safe_add_lots_table():
    """Bezpieczna migracja z lepszym obsługiwaniem błędów."""
    
    # Najpierw sprawdź dane
    if not check_data_before_migration():
        print("❌ Problemy z danymi - przerwano migrację")
        return False
    
    conn = sqlite3.connect("portfolio.db")
    cursor = conn.cursor()
    
    try:
        # Tworzenie tabeli lotów (jak w oryginalnej migracji)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_lots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                transaction_id INTEGER NOT NULL,
                lot_number INTEGER NOT NULL,
                purchase_date DATE NOT NULL,
                quantity INTEGER NOT NULL,
                remaining_quantity INTEGER NOT NULL,
                purchase_price_usd REAL NOT NULL,
                purchase_price_pln REAL NOT NULL,
                commission_usd REAL DEFAULT 0.0,
                commission_pln REAL DEFAULT 0.0,
                usd_pln_rate REAL NOT NULL,
                status TEXT DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'PARTIAL')),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (stock_id) REFERENCES stocks (id),
                FOREIGN KEY (transaction_id) REFERENCES stock_transactions (id)
            )
        """)
        
        # Tabela sprzedaży z lotów
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_lot_sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lot_id INTEGER NOT NULL,
                sale_transaction_id INTEGER NOT NULL,
                quantity_sold INTEGER NOT NULL,
                sale_date DATE NOT NULL,
                sale_price_usd REAL NOT NULL,
                sale_price_pln REAL NOT NULL,
                gain_loss_usd REAL NOT NULL,
                gain_loss_pln REAL NOT NULL,
                tax_due_pln REAL DEFAULT 0.0,
                usd_pln_rate REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lot_id) REFERENCES stock_lots (id),
                FOREIGN KEY (sale_transaction_id) REFERENCES stock_transactions (id)
            )
        """)
        
        conn.commit()
        print("✅ Tabele lotów utworzone")
        
        # Bezpieczna migracja danych
        safe_migrate_transactions(cursor, conn)
        
        print("🎉 Migracja zakończona pomyślnie!")
        return True
        
    except Exception as e:
        print(f"❌ Błąd podczas migracji: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def safe_migrate_transactions(cursor, conn):
    """Bezpieczna migracja transakcji."""
    
    # Pobierz transakcje kupna
    cursor.execute("""
        SELECT st.*, s.symbol 
        FROM stock_transactions st
        JOIN stocks s ON st.stock_id = s.id
        WHERE st.transaction_type = 'BUY'
        ORDER BY st.stock_id, st.transaction_date, st.created_at
    """)
    
    transactions = cursor.fetchall()
    
    if not transactions:
        print("ℹ️ Brak transakcji kupna do migracji")
        return
    
    print(f"🔄 Migrowanie {len(transactions)} transakcji kupna...")
    
    lot_counter = {}
    success_count = 0
    error_count = 0
    
    for transaction in transactions:
        try:
            stock_id = transaction[1]
            transaction_id = transaction[0]
            quantity = transaction[4] or 0
            price_usd = transaction[5] or 0.0
            commission_usd = transaction[6] or 0.0
            transaction_date = transaction[7]
            symbol = transaction[-1]
            
            # Walidacja podstawowa
            if quantity <= 0 or price_usd <= 0:
                print(f"⚠️ Pomijam transakcję {transaction_id} - nieprawidłowe dane")
                error_count += 1
                continue
            
            # Kurs domyślny (można później poprawić ręcznie)
            usd_rate = 4.0
            
            # Oblicz ceny w PLN
            purchase_price_pln = price_usd * usd_rate
            commission_pln = commission_usd * usd_rate
            
            # Zwiększ licznik lotów
            if stock_id not in lot_counter:
                lot_counter[stock_id] = 0
            lot_counter[stock_id] += 1
            
            # Dodaj lot
            cursor.execute("""
                INSERT INTO stock_lots 
                (stock_id, transaction_id, lot_number, purchase_date, quantity, 
                 remaining_quantity, purchase_price_usd, purchase_price_pln, 
                 commission_usd, commission_pln, usd_pln_rate, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
            """, (
                stock_id, transaction_id, lot_counter[stock_id], transaction_date,
                quantity, quantity, price_usd, purchase_price_pln,
                commission_usd, commission_pln, usd_rate
            ))
            
            success_count += 1
            
            if success_count <= 5:  # Pokaż pierwsze 5
                print(f"📦 Lot {lot_counter[stock_id]} - {symbol}: {quantity} szt. @ ${price_usd:.2f}")
            
        except Exception as e:
            print(f"❌ Błąd migracji transakcji {transaction_id}: {e}")
            error_count += 1
            continue
    
    conn.commit()
    
    print(f"✅ Zmigrowano: {success_count} transakcji")
    if error_count > 0:
        print(f"⚠️ Błędów: {error_count}")
    
    # Aktualizuj numery lotów w transakcjach (opcjonalne)
    try:
        cursor.execute("""
            UPDATE stock_transactions 
            SET lot_number = (
                SELECT lot_number FROM stock_lots 
                WHERE stock_lots.transaction_id = stock_transactions.id
            )
            WHERE transaction_type = 'BUY'
            AND EXISTS (
                SELECT 1 FROM stock_lots 
                WHERE stock_lots.transaction_id = stock_transactions.id
            )
        """)
        conn.commit()
        print("✅ Zaktualizowano numery lotów w transakcjach")
    except Exception as e:
        print(f"⚠️ Nie udało się zaktualizować numerów lotów: {e}")

if __name__ == "__main__":
    print("🔧 Bezpieczna migracja do systemu lotów")
    print("=" * 50)
    
    # Utwórz kopię zapasową
    try:
        import shutil
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"portfolio_backup_{timestamp}.db"
        shutil.copy2("portfolio.db", backup_name)
        print(f"💾 Kopia zapasowa: {backup_name}")
    except Exception as e:
        print(f"⚠️ Nie udało się utworzyć kopii zapasowej: {e}")
        response = input("Kontynuować bez kopii zapasowej? (tak/nie): ")
        if response.lower() not in ['tak', 'yes', 'y', 't']:
            print("❌ Anulowano migrację")
            exit(1)
    
    if safe_add_lots_table():
        print("\n🎉 Migracja zakończona!")
        print("🚀 Możesz teraz uruchomić aplikację: streamlit run app.py")
    else:
        print("\n❌ Migracja nie powiodła się")
        print("💡 Sprawdź dane w bazie i spróbuj ponownie")