import streamlit as st
import sys
import os

# Dodaj katalogi do PYTHONPATH
sys.path.append(os.path.dirname(__file__))

# Import modułów - zmieniony import z pages na views
from db import init_database
from views import dashboard, stocks, options, dividends, cashflows, taxes

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
        
        # Menu główne
        page = st.selectbox(
            "Wybierz stronę:",
            [
                "🏠 Dashboard",
                "📊 Akcje", 
                "📋 Opcje",
                "💰 Dywidendy",
                "💸 Przepływy pieniężne",
                "🧾 Podatki"
            ]
        )
        
        st.markdown("---")
        
        # Informacje systemowe
        st.markdown('<div class="sidebar-info">', unsafe_allow_html=True)
        st.markdown("**ℹ️ Informacje**")
        st.markdown("- Wszystkie kwoty w USD")
        st.markdown("- Kursy NBP do podatków")
        st.markdown("- Dane w czasie rzeczywistym")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Routing do odpowiednich stron
    try:
        if page == "🏠 Dashboard":
            dashboard.show()
        elif page == "📊 Akcje":
            stocks.show()
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