import streamlit as st
import sys
import os

# Dodaj katalogi do PYTHONPATH
sys.path.append(os.path.dirname(__file__))

# Import modułów - sprawdź czy wszystkie istnieją
try:
    from db import init_database
    from views import dashboard, stocks, options, dividends, cashflows, taxes
    
    # Próbuj zaimportować lots
    try:
        from views import lots
        LOTS_AVAILABLE = True
    except ImportError as e:
        st.error(f"Brak modułu lots: {e}")
        LOTS_AVAILABLE = False
        
except ImportError as e:
    st.error(f"Błąd importu: {e}")
    st.stop()

# Konfiguracja strony
st.set_page_config(
    page_title="Portfolio Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicjalizacja bazy danych
@st.cache_resource
def initialize_database():
    init_database()
    return True

initialize_database()

# CSS do customizacji wyglądu
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .metric-container {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    
    .sidebar-info {
        background-color: #e8f4f8;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    
    /* Ukryj domyślną nawigację Streamlit */
    .css-1d391kg {
        display: none;
    }
    
    /* Ukryj sidebar pages navigation */
    section[data-testid="stSidebar"] > div:first-child > div:first-child > div:first-child {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # Tytuł aplikacji
    st.markdown('<h1 class="main-header">📈 Portfolio Tracker</h1>', unsafe_allow_html=True)
    
    # Sidebar - nawigacja
    with st.sidebar:
        st.markdown("### Nawigacja")
        
        # Menu główne - dynamiczne w zależności od dostępności lots
        menu_options = [
            "🏠 Dashboard",
            "📊 Akcje"
        ]
        
        # Dodaj loty tylko jeśli dostępne
        if LOTS_AVAILABLE:
            menu_options.append("📦 Loty akcji")
        
        menu_options.extend([
            "📋 Opcje",
            "💰 Dywidendy", 
            "💸 Przepływy pieniężne",
            "🧾 Podatki"
        ])
        
        page = st.selectbox("Wybierz stronę:", menu_options)
        
        st.markdown("---")
        
        # Status systemu
        st.markdown('<div class="sidebar-info">', unsafe_allow_html=True)
        st.markdown("**ℹ️ Status systemu**")
        st.markdown("- Wszystkie kwoty w USD")
        st.markdown("- Kursy NBP do podatków")
        st.markdown("- Dane w czasie rzeczywistym")
        
        if LOTS_AVAILABLE:
            st.markdown("- ✅ System lotów FIFO")
        else:
            st.markdown("- ❌ System lotów niedostępny")
            st.markdown("💡 Utwórz plik views/lots.py")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Debug info
        if st.checkbox("🔧 Debug info"):
            st.markdown("**📁 Status plików:**")
            files_to_check = [
                "views/lots.py",
                "repos/stock_lots_repo.py"
            ]
            
            for file_path in files_to_check:
                if os.path.exists(file_path):
                    st.markdown(f"✅ {file_path}")
                else:
                    st.markdown(f"❌ {file_path}")
    
    # Routing do odpowiednich stron
    try:
        if page == "🏠 Dashboard":
            dashboard.show()
        elif page == "📊 Akcje":
            stocks.show()
        elif page == "📦 Loty akcji":
            if LOTS_AVAILABLE:
                lots.show()
            else:
                st.error("❌ Moduł lotów nie jest dostępny!")
                st.markdown("""
                **Aby włączyć system lotów:**
                1. Utwórz plik `views/lots.py` z kodem widoku lotów
                2. Utwórz plik `repos/stock_lots_repo.py` z kodem repozytorium  
                3. Uruchom migrację: `python safe_migration.py`
                4. Restart aplikacji
                """)
        elif page == "📋 Opcje":
            options.show()
        elif page == "💰 Dywidendy":
            dividends.show()
        elif page == "💸 Przepływy pieniężne":
            cashflows.show()
        elif page == "🧾 Podatki":
            taxes.show()
    except Exception as e:
        st.error(f"Błąd podczas ładowania strony: {str(e)}")
        st.exception(e)

if __name__ == "__main__":
    main()