#!/usr/bin/env python3
"""
Portfolio Tracker - Setup Script
Automatycznie konfiguruje środowisko i instaluje zależności.
"""

import os
import sys
import subprocess
import platform
import argparse

def check_python_version():
    """Sprawdza wersję Pythona."""
    if sys.version_info < (3, 8):
        print("❌ Portfolio Tracker wymaga Python 3.8 lub nowszego")
        print(f"💡 Aktualna wersja: {sys.version}")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True

def create_directories():
    """Tworzy niezbędne katalogi."""
    directories = [
        "logs",
        "backups", 
        "exports",
        "data"
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"📁 Utworzono katalog: {directory}")
        else:
            print(f"✅ Katalog istnieje: {directory}")

def install_requirements():
    """Instaluje wymagane pakiety."""
    print("📦 Instalowanie zależności...")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        print("✅ Wszystkie zależności zainstalowane pomyślnie")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Błąd podczas instalacji zależności: {e}")
        return False

def initialize_database(reset=False):
    """Inicjalizuje bazę danych."""
    print("🗄️ Inicjalizowanie bazy danych...")
    
    try:
        # Import lokalny, żeby sprawdzić czy moduły są dostępne
        from db import init_database, backup_database, check_database_structure
        
        # Utwórz kopię zapasową jeśli istnieje i nie resetujemy
        if os.path.exists("portfolio.db") and not reset:
            print("💾 Tworzenie kopii zapasowej istniejącej bazy...")
            backup_database()
        
        # Inicjalizuj bazę
        init_database()
        
        # Sprawdź strukturę
        print("\n📊 Sprawdzanie struktury bazy danych:")
        check_database_structure()
        
        print("✅ Baza danych zainicjalizowana")
        return True
    except ImportError as e:
        print(f"❌ Nie można zaimportować modułu db: {e}")
        return False
    except Exception as e:
        print(f"❌ Błąd podczas inicjalizacji bazy: {e}")
        return False

def create_config_file():
    """Tworzy plik konfiguracyjny."""
    if not os.path.exists("config.py"):
        if os.path.exists("config.example.py"):
            try:
                with open("config.example.py", "r", encoding="utf-8") as src:
                    content = src.read()
                
                with open("config.py", "w", encoding="utf-8") as dst:
                    dst.write(content)
                
                print("✅ Utworzono config.py z przykładowej konfiguracji")
            except Exception as e:
                print(f"❌ Błąd podczas tworzenia config.py: {e}")
        else:
            print("⚠️ Nie znaleziono config.example.py")
    else:
        print("✅ config.py już istnieje")

def check_system_dependencies():
    """Sprawdza zależności systemowe."""
    print("🔍 Sprawdzanie zależności systemowych...")
    
    # Sprawdź dostępność git (opcjonalne)
    try:
        subprocess.run(["git", "--version"], 
                      capture_output=True, check=True)
        print("✅ Git dostępny")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️ Git niedostępny (opcjonalne)")
    
    # Sprawdź system operacyjny
    os_name = platform.system()
    print(f"🖥️ System: {os_name} {platform.release()}")
    
    if os_name == "Windows":
        print("💡 Windows wykryty - sprawdź czy masz zainstalowany Microsoft Visual C++")
    elif os_name == "Darwin":
        print("🍎 macOS wykryty")
    elif os_name == "Linux":
        print("🐧 Linux wykryty")

def run_tests():
    """Uruchamia podstawowe testy."""
    print("🧪 Uruchamianie podstawowych testów...")
    
    try:
        # Test importu głównych modułów
        import streamlit
        print("✅ Streamlit importowany poprawnie")
        
        import pandas
        print("✅ Pandas importowany poprawnie")
        
        import plotly
        print("✅ Plotly importowany poprawnie")
        
        import requests
        print("✅ Requests importowany poprawnie")
        
        import yfinance
        print("✅ yfinance importowany poprawnie")
        
        # Test połączenia z bazą danych
        from db import execute_query
        result = execute_query("SELECT COUNT(*) as count FROM stocks")
        print(f"✅ Połączenie z bazą danych: {result[0]['count']} akcji w bazie")
        
        return True
        
    except ImportError as e:
        print(f"❌ Błąd importu: {e}")
        return False
    except Exception as e:
        print(f"❌ Błąd testów: {e}")
        return False

def reset_database():
    """Resetuje bazę danych do stanu początkowego."""
    print("🔄 Resetowanie bazy danych...")
    
    response = input("⚠️ To usunie wszystkie dane! Kontynuować? (tak/nie): ").lower()
    if response not in ['tak', 'yes', 'y', 't']:
        print("❌ Anulowano resetowanie bazy danych")
        return False
    
    try:
        # Utwórz kopię zapasową przed resetem
        from db import backup_database, init_database
        
        if os.path.exists("portfolio.db"):
            print("💾 Tworzenie kopii zapasowej przed resetem...")
            backup_database()
        
        # Usuń istniejącą bazę
        if os.path.exists("portfolio.db"):
            os.remove("portfolio.db")
            print("🗑️ Usunięto starą bazę danych")
        
        # Utwórz nową bazę
        init_database()
        print("✅ Baza danych została zresetowana")
        return True
        
    except Exception as e:
        print(f"❌ Błąd resetowania bazy danych: {e}")
        return False

def display_next_steps():
    """Wyświetla następne kroki."""
    print("\n" + "="*50)
    print("🎉 Setup zakończony pomyślnie!")
    print("="*50)
    print("\n📋 Następne kroki:")
    print("1. Uruchom aplikację: python run.py")
    print("   lub: streamlit run app.py")
    print("\n2. Otwórz w przeglądarce: http://localhost:8501")
    print("\n3. Dodaj pierwszą transakcję w zakładce 'Akcje'")
    print("\n4. Sprawdź ustawienia w pliku config.py")
    print("\n💡 Wskazówki:")
    print("• Regularnie rób backup pliku portfolio.db")
    print("• Aktualizuj ceny przed ważnymi decyzjami")
    print("• Sprawdź obliczenia podatkowe z doradcą")
    print("\n📚 Dokumentacja: README.md")
    print("🐛 Problemy: Sprawdź logi w katalogu logs/")
    print("\n🔧 Dodatkowe opcje:")
    print("• Reset bazy danych: python setup.py --reset-db")
    print("• Tylko instalacja: python setup.py --install-only")

def main():
    """Główna funkcja setup."""
    parser = argparse.ArgumentParser(description='Portfolio Tracker Setup')
    parser.add_argument('--reset-db', action='store_true', help='Resetuj bazę danych')
    parser.add_argument('--install-only', action='store_true', help='Tylko instaluj zależności')
    parser.add_argument('--skip-tests', action='store_true', help='Pomiń testy')
    
    args = parser.parse_args()
    
    print("🚀 Portfolio Tracker - Setup")
    print("="*40)
    
    # Obsługa specjalnych opcji
    if args.reset_db:
        if reset_database():
            print("✅ Baza danych została zresetowana!")
        else:
            print("❌ Błąd resetowania bazy danych")
        return
    
    # Sprawdzenia wstępne
    if not check_python_version():
        sys.exit(1)
    
    check_system_dependencies()
    
    # Tworzenie struktury
    create_directories()
    create_config_file()
    
    # Instalacja zależności
    if not install_requirements():
        print("❌ Setup nie powiódł się - problem z instalacją pakietów")
        sys.exit(1)
    
    if args.install_only:
        print("✅ Instalacja zakończona!")
        return
    
    # Inicjalizacja bazy
    if not initialize_database():
        print("❌ Setup nie powiódł się - problem z bazą danych")
        sys.exit(1)
    
    # Testy
    if not args.skip_tests and not run_tests():
        print("❌ Setup nie powiódł się - problem z testami")
        sys.exit(1)
    
    # Podsumowanie
    display_next_steps()

if __name__ == "__main__":
    main()