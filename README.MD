# 📈 Portfolio Tracker

Kompleksowa aplikacja do zarządzania portfelem inwestycyjnym napisana w Streamlit. Umożliwia śledzenie akcji, opcji, dywidend, przepływów pieniężnych oraz rozliczeń podatkowych zgodnie z polskimi przepisami.

## 🚀 Funkcjonalności

### 📊 Dashboard
- Przegląd portfela w czasie rzeczywistym
- Automatyczna aktualizacja cen z Yahoo Finance
- Kursy walut z API NBP
- Wykresy wydajności i alokacji

### 📈 Zarządzanie Akcjami
- Dodawanie transakcji kupna/sprzedaży
- Automatyczne obliczanie średnich cen (FIFO)
- Śledzenie zysków/strat niezrealizowanych
- Analiza wydajności poszczególnych pozycji
- Wykresy historyczne cen

### 📋 Opcje
- Zarządzanie kontraktami opcyjnymi (Call/Put)
- Śledzenie premium otrzymanych
- Analiza ryzyka przydziału
- Covered calls i naked options
- Alerty dla wygasających opcji

### 💰 Dywidendy
- Rejestracja wypłat dywidend
- Analiza rentowności dywidendowej
- Kalendarz dywidend
- Analiza potencjału reinwestycji
- Obliczenia podatkowe z automatycznym kursem NBP

### 💸 Przepływy Pieniężne
- Śledzenie wpłat i wypłat
- Analiza ROI (zwrotu z inwestycji)
- Kategoryzacja przepływów
- Wykresy trendów miesięcznych
- Przeliczenia na PLN

### 🧾 Podatki
- Automatyczne obliczenia zgodne z polskim prawem
- Zyski kapitałowe (19% podatek)
- Dywidendy z zaliczeniem podatku u źródła
- Premium z opcji
- Kursy NBP z dat transakcji
- Generowanie zestawień rocznych

## 🛠️ Technologie

- **Frontend**: Streamlit
- **Backend**: Python 3.8+
- **Baza danych**: SQLite
- **API zewnętrzne**: 
  - Yahoo Finance (yfinance) - ceny akcji
  - NBP API - kursy walut
- **Wizualizacje**: Plotly
- **Analiza danych**: Pandas, NumPy

## 📦 Instalacja

1. **Klonuj repozytorium:**
```bash
git clone <repository-url>
cd portfolio-tracker
```

2. **Utwórz środowisko wirtualne:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# lub
venv\Scripts\activate  # Windows
```

3. **Zainstaluj zależności:**
```bash
pip install -r requirements.txt
```

4. **Uruchom aplikację:**
```bash
streamlit run app.py
```

5. **Otwórz w przeglądarce:**
```
http://localhost:8501
```

## 📁 Struktura projektu

```
portfolio-tracker/
├── app.py                 # Główny plik aplikacji
├── db.py                  # Konfiguracja bazy danych
├── requirements.txt       # Zależności Python
├── pages/                 # Strony aplikacji
│   ├── __init__.py
│   ├── dashboard.py       # Dashboard główny
│   ├── stocks.py          # Zarządzanie akcjami
│   ├── options.py         # Zarządzanie opcjami
│   ├── dividends.py       # Zarządzanie dywidendami
│   ├── cashflows.py       # Przepływy pieniężne
│   └── taxes.py           # Rozliczenia podatkowe
├── repos/                 # Repozytoria danych
│   ├── __init__.py
│   ├── stock_repo.py      # Operacje na akcjach
│   ├── options_repo.py    # Operacje na opcjach
│   ├── dividends_repo.py  # Operacje na dywidendach
│   └── cashflow_repo.py   # Operacje na przepływach
├── services/              # Serwisy zewnętrzne
│   ├── __init__.py
│   ├── pricing.py         # Pobieranie cen (Yahoo Finance)
│   └── nbp.py            # Kursy NBP
└── utils/                 # Narzędzia pomocnicze
    ├── __init__.py
    ├── formatting.py      # Formatowanie danych
    └── tax.py            # Obliczenia podatkowe
```

## 🎯 Podstawowe użycie

### 1. Dodawanie pierwszej akcji
1. Przejdź do zakładki "📊 Akcje"
2. Kliknij "➕ Dodaj transakcję"
3. Wprowadź symbol akcji (np. AAPL)
4. Wybierz "BUY", wprowadź ilość i cenę
5. Zapisz transakcję

### 2. Aktualizacja cen
1. Na Dashboard kliknij "🔄 Aktualizuj ceny"
2. System pobierze aktualne ceny z Yahoo Finance
3. Zobaczysz zaktualizowane wartości portfela

### 3. Dodawanie dywidendy
1. Przejdź do "💰 Dywidendy"
2. Kliknij "➕ Dodaj dywidendę" 
3. Wybierz akcję i wprowadź kwotę dywidendy
4. System automatycznie pobierze kurs NBP

### 4. Zarządzanie opcjami
1. Przejdź do "📋 Opcje"
2. Dodaj nową opcję z strike price i datą wygaśnięcia
3. Śledź wygasające opcje w zakładce "⚠️ Wygasające"

### 5. Rozliczenia podatkowe
1. Przejdź do "🧾 Podatki"
2. Wybierz rok podatkowy
3. Zobacz automatyczne obliczenia podatku
4. Wygeneruj zestawienie roczne

## ⚙️ Konfiguracja

### Baza danych
Aplikacja automatycznie tworzy bazę SQLite (`portfolio.db`) przy pierwszym uruchomieniu.

### API zewnętrzne
- **Yahoo Finance**: Nie wymaga konfiguracji
- **NBP API**: Publiczne API, bez konieczności rejestracji

## 🔒 Bezpieczeństwo i prywatność

- Wszystkie dane przechowywane lokalnie (SQLite)
- Brak połączeń z brokerami (tylko pobieranie cen)
- Nie są przechowywane dane uwierzytelniające
- Możliwość backupu przez kopiowanie pliku `portfolio.db`

## 📊 Przykładowe funkcje

### Automatyczne obliczenia:
- ✅ Średnie ceny zakupu (FIFO)
- ✅ Zyski/straty niezrealizowane  
- ✅ Rentowność dywidendowa
- ✅ Podatki z kursami NBP
- ✅ ROI całkowity portfela

### Alerty i powiadomienia:
- ⚠️ Opcje wygasające w ciągu 30 dni
- 🚨 Opcje z wysokim ryzykiem przydziału
- 💰 Szacunkowe płatności podatkowe

## 🤝 Wsparcie

Aplikacja została stworzona dla polskich inwestorów i uwzględnia:
- Polskie przepisy podatkowe (19% podatek)
- Kursy NBP z dat transakcji
- Formularz PIT-38 (zyski kapitałowe)
- Zaliczenie podatku u źródła z USA

## ⚠️ Zastrzeżenia

- **Nie jest to poradnictwo finansowe ani podatkowe**
- Obliczenia mają charakter szacunkowy
- Zawsze skonsultuj się z doradcą podatkowym
- Weryfikuj wyniki przed złożeniem zeznania podatkowego

## 📈 Rozwój

Planowane funkcje:
- [ ] Import danych z brokerów (CSV)
- [ ] Eksport raportów do PDF
- [ ] Integracja z więcej API (Alpha Vantage, IEX)
- [ ] Powiadomienia email
- [ ] Analiza Monte Carlo
- [ ] Backtesting strategii

## 📄 Licencja

MIT License - szczegóły w pliku LICENSE

## 👨‍💻 Autor

Aplikacja stworzona dla społeczności polskich inwestorów DIY.

---

**💡 Tip**: Regularne aktualizowanie cen i wprowadzanie transakcji pozwoli na dokładne śledzenie wydajności portfela!