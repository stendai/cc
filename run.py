#!/usr/bin/env python3
"""
Portfolio Tracker - Runner Script
Uruchamia aplikację Streamlit z odpowiednimi parametrami.
"""

import subprocess
import sys
import os

def main():
    """Główna funkcja uruchamiająca aplikację."""
    
    print("🚀 Uruchamianie Portfolio Tracker...")
    print("📊 Sprawdź czy wszystkie zależności są zainstalowane")
    
    # Sprawdź czy streamlit jest zainstalowany
    try:
        import streamlit
        print("✅ Streamlit znaleziony")
    except ImportError:
        print("❌ Streamlit nie jest zainstalowany!")
        print("💡 Uruchom: pip install -r requirements.txt")
        sys.exit(1)
    
    # Sprawdź czy plik app.py istnieje
    if not os.path.exists("app.py"):
        print("❌ Nie znaleziono pliku app.py!")
        sys.exit(1)
    
    # Parametry uruchamiania Streamlit
    cmd = [
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", "8501",
        "--server.address", "localhost",
        "--browser.gatherUsageStats", "false"
    ]
    
    try:
        print("🌐 Uruchamianie na http://localhost:8501")
        print("🛑 Aby zatrzymać aplikację, naciśnij Ctrl+C")
        print("-" * 50)
        
        # Uruchom Streamlit
        subprocess.run(cmd, check=True)
        
    except KeyboardInterrupt:
        print("\n✅ Aplikacja została zatrzymana przez użytkownika")
    except subprocess.CalledProcessError as e:
        print(f"❌ Błąd podczas uruchamiania: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Nieoczekiwany błąd: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()