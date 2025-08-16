import requests
import yfinance as yf
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time
from repos.stock_repo import StockRepository

class PricingService:
    """Serwis do pobierania aktualnych cen akcji."""
    
    def __init__(self):
        self.session = requests.Session()
        self.last_update = {}
        self.cache_duration = 300  # 5 minut cache
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Pobiera aktualną cenę akcji za pomocą yfinance.
        
        Args:
            symbol: Symbol akcji (np. 'AAPL')
        
        Returns:
            Aktualna cena lub None jeśli nie można pobrać
        """
        try:
            # Sprawdź cache
            cache_key = f"{symbol}_price"
            if self._is_cache_valid(cache_key):
                return self.last_update[cache_key]['price']
            
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Spróbuj różne pola dla ceny
            price_fields = ['regularMarketPrice', 'currentPrice', 'previousClose', 'bid', 'ask']
            
            for field in price_fields:
                if field in info and info[field] is not None:
                    price = float(info[field])
                    
                    # Cache wynik
                    self.last_update[cache_key] = {
                        'price': price,
                        'timestamp': datetime.now()
                    }
                    
                    return price
            
            return None
            
        except Exception as e:
            print(f"Błąd pobierania ceny dla {symbol}: {e}")
            return None
    
    def get_multiple_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Pobiera ceny dla wielu akcji jednocześnie.
        
        Args:
            symbols: Lista symboli akcji
        
        Returns:
            Słownik {symbol: cena}
        """
        results = {}
        
        try:
            # Pobierz dane dla wszystkich symboli naraz
            tickers = yf.Tickers(' '.join(symbols))
            
            for symbol in symbols:
                try:
                    ticker = tickers.tickers[symbol]
                    info = ticker.info
                    
                    price_fields = ['regularMarketPrice', 'currentPrice', 'previousClose']
                    
                    for field in price_fields:
                        if field in info and info[field] is not None:
                            results[symbol] = float(info[field])
                            break
                    
                    # Jeśli nie znaleziono ceny, spróbuj alternatywną metodę
                    if symbol not in results:
                        hist = ticker.history(period="1d")
                        if not hist.empty:
                            results[symbol] = float(hist['Close'].iloc[-1])
                
                except Exception as e:
                    print(f"Błąd pobierania ceny dla {symbol}: {e}")
                    continue
            
            # Cache wyniki
            for symbol, price in results.items():
                cache_key = f"{symbol}_price"
                self.last_update[cache_key] = {
                    'price': price,
                    'timestamp': datetime.now()
                }
            
        except Exception as e:
            print(f"Błąd pobierania cen: {e}")
        
        return results
    
    def update_all_stock_prices(self) -> Dict[str, bool]:
        """
        Aktualizuje ceny wszystkich akcji w portfelu.
        
        Returns:
            Słownik {symbol: success} z wynikami aktualizacji
        """
        stocks = StockRepository.get_all_stocks()
        symbols = [stock['symbol'] for stock in stocks]
        
        if not symbols:
            return {}
        
        print(f"Aktualizowanie cen dla: {', '.join(symbols)}")
        
        prices = self.get_multiple_prices(symbols)
        results = {}
        
        for stock in stocks:
            symbol = stock['symbol']
            stock_id = stock['id']
            
            if symbol in prices:
                success = StockRepository.update_stock_price(stock_id, prices[symbol])
                results[symbol] = success
                
                if success:
                    print(f"✓ {symbol}: ${prices[symbol]:.2f}")
                else:
                    print(f"✗ Błąd aktualizacji {symbol}")
            else:
                results[symbol] = False
                print(f"✗ Nie można pobrać ceny dla {symbol}")
        
        return results
    
    def get_stock_info(self, symbol: str) -> Optional[Dict]:
        """
        Pobiera szczegółowe informacje o akcji.
        
        Args:
            symbol: Symbol akcji
        
        Returns:
            Słownik z informacjami o akcji
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Wybierz najważniejsze informacje
            relevant_info = {
                'symbol': symbol,
                'longName': info.get('longName', 'N/A'),
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'currentPrice': info.get('currentPrice') or info.get('regularMarketPrice'),
                'previousClose': info.get('previousClose'),
                'marketCap': info.get('marketCap'),
                'dividendYield': info.get('dividendYield'),
                'trailingPE': info.get('trailingPE'),
                'beta': info.get('beta'),
                'fiftyTwoWeekHigh': info.get('fiftyTwoWeekHigh'),
                'fiftyTwoWeekLow': info.get('fiftyTwoWeekLow'),
                'volume': info.get('volume'),
                'avgVolume': info.get('averageVolume'),
                'currency': info.get('currency', 'USD')
            }
            
            return relevant_info
            
        except Exception as e:
            print(f"Błąd pobierania informacji dla {symbol}: {e}")
            return None
    
    def get_historical_data(self, symbol: str, period: str = "1y") -> Optional[Dict]:
        """
        Pobiera dane historyczne dla akcji.
        
        Args:
            symbol: Symbol akcji
            period: Okres danych (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        
        Returns:
            Słownik z danymi historycznymi
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            
            if hist.empty:
                return None
            
            return {
                'dates': hist.index.strftime('%Y-%m-%d').tolist(),
                'open': hist['Open'].tolist(),
                'high': hist['High'].tolist(),
                'low': hist['Low'].tolist(),
                'close': hist['Close'].tolist(),
                'volume': hist['Volume'].tolist()
            }
            
        except Exception as e:
            print(f"Błąd pobierania danych historycznych dla {symbol}: {e}")
            return None
    
    def search_stocks(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Wyszukuje akcje po nazwie lub symbolu.
        
        Args:
            query: Wyszukiwana fraza
            limit: Maksymalna liczba wyników
        
        Returns:
            Lista słowników z wynikami wyszukiwania
        """
        results = []
        
        try:
            # Prosta implementacja - w prawdziwej aplikacji można użyć API wyszukiwania
            # Na razie sprawdzamy czy podany symbol istnieje
            if len(query) <= 5:  # Prawdopodobnie symbol
                ticker = yf.Ticker(query.upper())
                info = ticker.info
                
                if 'longName' in info:
                    results.append({
                        'symbol': query.upper(),
                        'name': info.get('longName', 'N/A'),
                        'sector': info.get('sector', 'N/A'),
                        'currentPrice': info.get('currentPrice') or info.get('regularMarketPrice')
                    })
        
        except Exception as e:
            print(f"Błąd wyszukiwania akcji: {e}")
        
        return results[:limit]
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Sprawdza czy cache jest jeszcze ważny."""
        if cache_key not in self.last_update:
            return False
        
        last_update_time = self.last_update[cache_key]['timestamp']
        return (datetime.now() - last_update_time).seconds < self.cache_duration
    
    def clear_cache(self):
        """Czyści cache cen."""
        self.last_update = {}
    
    def get_market_status(self) -> Dict[str, str]:
        """
        Sprawdza status rynku (otwarty/zamknięty).
        
        Returns:
            Słownik ze statusem rynku
        """
        try:
            # Pobierz dane dla SPY jako proxy dla rynku US
            spy = yf.Ticker("SPY")
            info = spy.info
            
            return {
                'market': 'US',
                'status': 'open' if info.get('regularMarketPrice') else 'closed',
                'next_close': info.get('regularMarketTime', 'N/A'),
                'timezone': 'EST'
            }
            
        except Exception:
            return {
                'market': 'US',
                'status': 'unknown',
                'next_close': 'N/A',
                'timezone': 'EST'
            }
    
    def get_options_data(self, symbol: str, expiry_date: str = None) -> Optional[Dict]:
        """
        Pobiera dane opcji dla danej akcji.
        
        Args:
            symbol: Symbol akcji
            expiry_date: Data wygaśnięcia opcji (YYYY-MM-DD)
        
        Returns:
            Słownik z danymi opcji
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Pobierz dostępne daty wygaśnięcia
            expiry_dates = ticker.options
            
            if not expiry_dates:
                return None
            
            # Użyj podanej daty lub najbliższą dostępną
            if expiry_date and expiry_date in expiry_dates:
                target_expiry = expiry_date
            else:
                target_expiry = expiry_dates[0]  # Najbliższa data
            
            # Pobierz łańcuch opcji
            option_chain = ticker.option_chain(target_expiry)
            
            return {
                'symbol': symbol,
                'expiry_date': target_expiry,
                'available_expiries': list(expiry_dates),
                'calls': option_chain.calls.to_dict('records') if not option_chain.calls.empty else [],
                'puts': option_chain.puts.to_dict('records') if not option_chain.puts.empty else []
            }
            
        except Exception as e:
            print(f"Błąd pobierania danych opcji dla {symbol}: {e}")
            return None
    
    def get_dividend_info(self, symbol: str) -> Optional[Dict]:
        """
        Pobiera informacje o dywidendach dla akcji.
        
        Args:
            symbol: Symbol akcji
        
        Returns:
            Słownik z informacjami o dywidendach
        """
        try:
            ticker = yf.Ticker(symbol)
            dividends = ticker.dividends
            
            if dividends.empty:
                return None
            
            # Ostatnie dywidendy
            recent_dividends = dividends.tail(4)  # Ostatnie 4 kwartały
            
            info = ticker.info
            
            return {
                'symbol': symbol,
                'dividend_yield': info.get('dividendYield'),
                'dividend_rate': info.get('dividendRate'),
                'ex_dividend_date': info.get('exDividendDate'),
                'last_dividend': dividends.iloc[-1] if not dividends.empty else None,
                'recent_dividends': {
                    'dates': recent_dividends.index.strftime('%Y-%m-%d').tolist(),
                    'amounts': recent_dividends.tolist()
                },
                'annual_dividend': recent_dividends.sum() if len(recent_dividends) >= 4 else None
            }
            
        except Exception as e:
            print(f"Błąd pobierania informacji o dywidendach dla {symbol}: {e}")
            return None

# Instancja globalna serwisu
pricing_service = PricingService()

def update_portfolio_prices():
    """Funkcja pomocnicza do aktualizacji cen portfela."""
    return pricing_service.update_all_stock_prices()

def get_stock_price(symbol: str) -> Optional[float]:
    """Funkcja pomocnicza do pobierania ceny akcji."""
    return pricing_service.get_current_price(symbol)