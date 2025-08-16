import requests
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List
from db import execute_query, execute_insert

class NBPService:
    """Serwis do pobierania kursów walut z API NBP."""
    
    BASE_URL = "http://api.nbp.pl/api"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'Portfolio-Tracker/1.0'
        })
    
    def get_exchange_rate(self, currency: str, date_value: date, 
                         table: str = 'a') -> Optional[float]:
        """
        Pobiera kurs waluty z NBP na określoną datę.
        
        Args:
            currency: Kod waluty (np. 'USD')
            date_value: Data kursu
            table: Tabela kursów ('a', 'b', 'c')
        
        Returns:
            Kurs waluty lub None jeśli nie można pobrać
        """
        # Najpierw sprawdź cache w bazie danych
        cached_rate = self._get_cached_rate(currency, date_value)
        if cached_rate:
            return cached_rate
        
        # Pobierz z API NBP
        date_str = date_value.strftime("%Y-%m-%d")
        url = f"{self.BASE_URL}/exchangerates/rates/{table}/{currency.lower()}/{date_str}/"
        
        try:
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                rate = data['rates'][0]['mid']
                
                # Zapisz w cache
                self._cache_rate(f"{currency}/PLN", rate, date_value)
                
                return rate
            
            elif response.status_code == 404:
                # Brak danych na daną datę - spróbuj poprzedni dzień roboczy
                return self._get_previous_working_day_rate(currency, date_value, table)
            
            else:
                print(f"Błąd API NBP: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            print(f"Błąd połączenia z NBP: {e}")
            # Spróbuj znaleźć ostatni dostępny kurs
            return self._get_last_available_rate(currency, date_value)
    
    def get_usd_pln_rate(self, date_value: date) -> Optional[float]:
        """Pobiera kurs USD/PLN na określoną datę."""
        return self.get_exchange_rate('USD', date_value)
    
    def get_current_usd_rate(self) -> Optional[float]:
        """Pobiera aktualny kurs USD/PLN."""
        return self.get_usd_pln_rate(date.today())
    
    def get_rate_range(self, currency: str, start_date: date, 
                      end_date: date, table: str = 'a') -> List[Dict]:
        """
        Pobiera kursy waluty z określonego zakresu dat.
        
        Args:
            currency: Kod waluty
            start_date: Data początkowa
            end_date: Data końcowa
            table: Tabela kursów
        
        Returns:
            Lista słowników z kursami
        """
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        url = f"{self.BASE_URL}/exchangerates/rates/{table}/{currency.lower()}/{start_str}/{end_str}/"
        
        try:
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                rates = []
                
                for rate_data in data['rates']:
                    rate_date = datetime.strptime(rate_data['effectiveDate'], "%Y-%m-%d").date()
                    rate_value = rate_data['mid']
                    
                    rates.append({
                        'date': rate_date,
                        'rate': rate_value,
                        'currency_pair': f"{currency}/PLN"
                    })
                    
                    # Cache każdy kurs
                    self._cache_rate(f"{currency}/PLN", rate_value, rate_date)
                
                return rates
            
            else:
                print(f"Błąd pobierania zakresu kursów: {response.status_code}")
                return []
                
        except requests.RequestException as e:
            print(f"Błąd połączenia z NBP: {e}")
            return []
    
    def get_available_currencies(self, table: str = 'a') -> List[Dict]:
        """
        Pobiera listę dostępnych walut.
        
        Args:
            table: Tabela kursów
        
        Returns:
            Lista dostępnych walut
        """
        url = f"{self.BASE_URL}/exchangerates/tables/{table}/"
        
        try:
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data[0]['rates']
            
            else:
                return []
                
        except requests.RequestException:
            return []
    
    def _get_cached_rate(self, currency: str, date_value: date) -> Optional[float]:
        """Pobiera kurs z cache w bazie danych."""
        currency_pair = f"{currency}/PLN"
        date_str = date_value.strftime("%Y-%m-%d")
        
        result = execute_query(
            "SELECT rate FROM exchange_rates WHERE currency_pair = ? AND date = ?",
            (currency_pair, date_str)
        )
        
        return result[0]['rate'] if result else None
    
    def _cache_rate(self, currency_pair: str, rate: float, date_value: date):
        """Zapisuje kurs w cache."""
        date_str = date_value.strftime("%Y-%m-%d")
        
        execute_insert(
            "INSERT OR REPLACE INTO exchange_rates (currency_pair, rate, date, source) VALUES (?, ?, ?, ?)",
            (currency_pair, rate, date_str, "NBP")
        )
    
    def _get_previous_working_day_rate(self, currency: str, date_value: date, 
                                     table: str, max_days: int = 10) -> Optional[float]:
        """Znajduje kurs z poprzedniego dnia roboczego."""
        current_date = date_value
        
        for _ in range(max_days):
            current_date -= timedelta(days=1)
            
            # Pomiń weekendy
            if current_date.weekday() >= 5:
                continue
            
            # Sprawdź cache
            cached_rate = self._get_cached_rate(currency, current_date)
            if cached_rate:
                return cached_rate
            
            # Spróbuj pobrać z API
            date_str = current_date.strftime("%Y-%m-%d")
            url = f"{self.BASE_URL}/exchangerates/rates/{table}/{currency.lower()}/{date_str}/"
            
            try:
                response = self.session.get(url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    rate = data['rates'][0]['mid']
                    
                    # Cache wynik
                    self._cache_rate(f"{currency}/PLN", rate, current_date)
                    
                    return rate
                    
            except requests.RequestException:
                continue
        
        return None
    
    def _get_last_available_rate(self, currency: str, date_value: date) -> Optional[float]:
        """Znajduje ostatni dostępny kurs z bazy danych."""
        currency_pair = f"{currency}/PLN"
        date_str = date_value.strftime("%Y-%m-%d")
        
        result = execute_query(
            """SELECT rate FROM exchange_rates 
               WHERE currency_pair = ? AND date <= ? 
               ORDER BY date DESC LIMIT 1""",
            (currency_pair, date_str)
        )
        
        return result[0]['rate'] if result else None
    
    def update_current_rates(self, currencies: List[str] = None) -> Dict[str, bool]:
        """
        Aktualizuje aktualne kursy walut.
        
        Args:
            currencies: Lista walut do aktualizacji (domyślnie USD)
        
        Returns:
            Słownik z wynikami aktualizacji
        """
        if currencies is None:
            currencies = ['USD']
        
        results = {}
        today = date.today()
        
        for currency in currencies:
            try:
                rate = self.get_exchange_rate(currency, today)
                results[currency] = rate is not None
                
                if rate:
                    print(f"✓ {currency}/PLN: {rate:.4f}")
                else:
                    print(f"✗ Nie można pobrać kursu {currency}")
                    
            except Exception as e:
                print(f"✗ Błąd aktualizacji {currency}: {e}")
                results[currency] = False
        
        return results
    
    def get_rate_history(self, currency: str, days: int = 30) -> List[Dict]:
        """
        Pobiera historię kursów waluty z ostatnich dni.
        
        Args:
            currency: Kod waluty
            days: Liczba dni wstecz
        
        Returns:
            Lista kursów historycznych
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        return self.get_rate_range(currency, start_date, end_date)
    
    def calculate_tax_amount(self, amount_usd: float, transaction_date: date, 
                           tax_rate: float = 0.19) -> Dict[str, float]:
        """
        Oblicza kwotę podatku w PLN.
        
        Args:
            amount_usd: Kwota w USD
            transaction_date: Data transakcji
            tax_rate: Stawka podatkowa (domyślnie 19%)
        
        Returns:
            Słownik z kwotami i kursem
        """
        exchange_rate = self.get_usd_pln_rate(transaction_date)
        
        if not exchange_rate:
            raise ValueError(f"Nie można pobrać kursu NBP na datę {transaction_date}")
        
        amount_pln = amount_usd * exchange_rate
        tax_pln = amount_pln * tax_rate
        
        return {
            'amount_usd': amount_usd,
            'amount_pln': amount_pln,
            'tax_pln': tax_pln,
            'exchange_rate': exchange_rate,
            'transaction_date': transaction_date.strftime("%Y-%m-%d")
        }

# Instancja globalna serwisu
nbp_service = NBPService()

def get_current_usd_rate() -> Optional[float]:
    """Funkcja pomocnicza do pobierania aktualnego kursu USD."""
    return nbp_service.get_current_usd_rate()

def get_usd_rate_for_date(date_value: date) -> Optional[float]:
    """Funkcja pomocnicza do pobierania kursu USD na określoną datę."""
    return nbp_service.get_usd_pln_rate(date_value)