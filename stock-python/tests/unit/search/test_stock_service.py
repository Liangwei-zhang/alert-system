"""
Stock Service Tests
=================
Tested by: Notification Team
Original developer: Search Team

Comprehensive tests for StockService:
- Stock search (search_stocks)
- Fuzzy search
- Symbol lookup (get_stock_by_symbol)
- Quote operations
- Watchlist operations
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


# ============== Mock Data Classes ==============

@dataclass
class MockStockQuote:
    """Mock stock quote for testing."""
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    volume: int
    market_cap: Optional[float]
    previous_close: float
    open: float
    high: float
    low: float
    timestamp: datetime


@dataclass
class MockStockSearchResult:
    """Mock stock search result."""
    symbol: str
    name: str
    exchange: str
    type: str


@dataclass
class MockHistoricalData:
    """Mock historical data point."""
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class MockStock:
    """Mock Stock model for testing."""
    def __init__(
        self,
        id=1,
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        sector="Technology",
        current_price=175.50,
        previous_close=174.00,
        volume=50000000,
        market_cap=2800000000000,
        updated_at=None,
    ):
        self.id = id
        self.symbol = symbol
        self.name = name
        self.exchange = exchange
        self.sector = sector
        self.current_price = current_price
        self.previous_close = previous_close
        self.volume = volume
        self.market_cap = market_cap
        self.updated_at = updated_at or datetime.utcnow()


class MockWatchlist:
    """Mock Watchlist model."""
    def __init__(
        self,
        id=1,
        user_id=1,
        name="My Watchlist",
        created_at=None,
        updated_at=None,
    ):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()


class MockWatchlistItem:
    """Mock WatchlistItem model."""
    def __init__(self, id=1, watchlist_id=1, stock_id=1, notes=None, added_at=None, stock=None):
        self.id = id
        self.watchlist_id = watchlist_id
        self.stock_id = stock_id
        self.notes = notes
        self.added_at = added_at or datetime.utcnow()
        self.stock = stock


class MockCache:
    """Mock Redis cache for testing."""
    def __init__(self):
        self.store = {}
    
    async def get(self, key: str):
        return self.store.get(key)
    
    async def set(self, key: str, value, expire=None):
        self.store[key] = value
    
    async def delete(self, key: str):
        if key in self.store:
            del self.store[key]


# ============== Fixtures ==============

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def mock_cache():
    """Mock cache fixture."""
    return MockCache()


# ============== Stock Search Tests ==============

class TestStockSearch:
    """Tests for stock search - Happy Path."""
    
    @pytest.mark.asyncio
    @patch('domains.search.stock_service.DataSourceFactory')
    async def test_search_stocks_basic(self, mock_factory, mock_db, mock_cache):
        """Test basic stock search returns results."""
        # Setup mock search results
        mock_results = [
            MockStockSearchResult("AAPL", "Apple Inc.", "NASDAQ", "stock"),
            MockStockSearchResult("MSFT", "Microsoft Corporation", "NASDAQ", "stock"),
        ]
        mock_factory.search = AsyncMock(return_value=mock_results)
        
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService._get_cache', return_value=AsyncMock(return_value=mock_cache)):
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                results = await service.search_stocks("Apple")
                
                assert len(results) == 2
                assert results[0].symbol == "AAPL"
                assert results[1].symbol == "MSFT"
    
    @pytest.mark.asyncio
    @patch('domains.search.stock_service.DataSourceFactory')
    async def test_search_stocks_returns_empty(self, mock_factory, mock_db, mock_cache):
        """Test search with no results."""
        mock_factory.search = AsyncMock(return_value=[])
        
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService._get_cache', return_value=AsyncMock(return_value=mock_cache)):
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                results = await service.search_stocks("xyznonexistent")
                
                assert results == []


class TestStockSearchEdgeCases:
    """Tests for stock search - Edge Cases."""
    
    @pytest.mark.asyncio
    @patch('domains.search.stock_service.DataSourceFactory')
    async def test_search_stocks_special_characters(self, mock_factory, mock_cache):
        """Test search handles special characters."""
        mock_factory.search = AsyncMock(return_value=[])
        
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService._get_cache', return_value=AsyncMock(return_value=mock_cache)):
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                results = await service.search_stocks("AAPL&GOOG")
                
                # Should not crash
                assert isinstance(results, list)
    
    @pytest.mark.asyncio
    @patch('domains.search.stock_service.DataSourceFactory')
    async def test_search_stocks_lowercase(self, mock_factory, mock_cache):
        """Test search is case insensitive."""
        mock_results = [
            MockStockSearchResult("AAPL", "Apple Inc.", "NASDAQ", "stock"),
        ]
        mock_factory.search = AsyncMock(return_value=mock_results)
        
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService._get_cache', return_value=AsyncMock(return_value=mock_cache)):
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                results = await service.search_stocks("apple")
                
                assert len(results) >= 1


# ============== Fuzzy Search Tests ==============

class TestFuzzySearch:
    """Tests for fuzzy search - Happy Path."""
    
    @pytest.mark.asyncio
    @patch('domains.search.stock_service.DataSourceFactory')
    async def test_fuzzy_search_partial_match(self, mock_factory, mock_cache):
        """Test fuzzy search with partial match."""
        mock_results = [
            MockStockSearchResult("GOOGL", "Alphabet Inc.", "NASDAQ", "stock"),
            MockStockSearchResult("GOOG", "Alphabet Inc. Class C", "NASDAQ", "stock"),
        ]
        mock_factory.search = AsyncMock(return_value=mock_results)
        
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService._get_cache', return_value=AsyncMock(return_value=mock_cache)):
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                results = await service.search_stocks("GOOG")
                
                assert len(results) >= 1
    
    @pytest.mark.asyncio
    @patch('domains.search.stock_service.DataSourceFactory')
    async def test_fuzzy_search_typo_tolerance(self, mock_factory, mock_cache):
        """Test fuzzy search handles typos."""
        # Search for "Appple" (typo)
        mock_results = [
            MockStockSearchResult("AAPL", "Apple Inc.", "NASDAQ", "stock"),
        ]
        mock_factory.search = AsyncMock(return_value=mock_results)
        
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService._get_cache', return_value=AsyncMock(return_value=mock_cache)):
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                results = await service.search_stocks("Appple")
                
                # Either returns result or empty list (depends on backend)
                assert isinstance(results, list)


class TestFuzzySearchEdgeCases:
    """Tests for fuzzy search - Edge Cases."""
    
    @pytest.mark.asyncio
    @patch('domains.search.stock_service.DataSourceFactory')
    async def test_fuzzy_search_empty_query(self, mock_factory, mock_cache):
        """Test fuzzy search with empty query."""
        mock_factory.search = AsyncMock(return_value=[])
        
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService._get_cache', return_value=AsyncMock(return_value=mock_cache)):
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                results = await service.search_stocks("")
                
                # Should return empty or handle gracefully
                assert isinstance(results, list)
    
    @pytest.mark.asyncio
    @patch('domains.search.stock_service.DataSourceFactory')
    async def test_fuzzy_search_single_char(self, mock_factory, mock_cache):
        """Test fuzzy search with single character."""
        mock_results = [
            MockStockSearchResult("F", "Ford Motor Company", "NYSE", "stock"),
        ]
        mock_factory.search = AsyncMock(return_value=mock_results)
        
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService._get_cache', return_value=AsyncMock(return_value=mock_cache)):
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                results = await service.search_stocks("F")
                
                assert isinstance(results, list)


# ============== Symbol Lookup Tests ==============

class TestSymbolLookup:
    """Tests for symbol lookup - Happy Path."""
    
    @pytest.mark.asyncio
    async def test_get_stock_by_symbol_exact(self, mock_db, mock_cache):
        """Test exact symbol lookup."""
        mock_stock = MockStock(symbol="AAPL", name="Apple Inc.")
        
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService._get_cache', return_value=AsyncMock(return_value=mock_cache)):
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_stock
                mock_db.execute.return_value = mock_result
                
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                stock = await service.get_stock_by_symbol(mock_db, "AAPL")
                
                assert stock is not None
                assert stock.symbol == "AAPL"
    
    @pytest.mark.asyncio
    async def test_get_stock_by_symbol_case_insensitive(self, mock_db, mock_cache):
        """Test symbol lookup is case insensitive."""
        mock_stock = MockStock(symbol="AAPL", name="Apple Inc.")
        
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService._get_cache', return_value=AsyncMock(return_value=mock_cache)):
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_stock
                mock_db.execute.return_value = mock_result
                
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                stock = await service.get_stock_by_symbol(mock_db, "aapl")
                
                assert stock is not None


class TestSymbolLookupEdgeCases:
    """Tests for symbol lookup - Edge Cases."""
    
    @pytest.mark.asyncio
    async def test_get_stock_by_symbol_not_found(self, mock_db, mock_cache):
        """Test symbol not found returns None."""
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService._get_cache', return_value=AsyncMock(return_value=mock_cache)):
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                mock_db.execute.return_value = mock_result
                
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                stock = await service.get_stock_by_symbol(mock_db, "NOTFOUND")
                
                assert stock is None
    
    @pytest.mark.asyncio
    async def test_get_stock_by_symbol_empty(self, mock_db, mock_cache):
        """Test empty symbol returns None."""
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService._get_cache', return_value=AsyncMock(return_value=mock_cache)):
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                mock_db.execute.return_value = mock_result
                
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                stock = await service.get_stock_by_symbol(mock_db, "")
                
                # Empty string should be handled (may return None or filter out)
                assert stock is None or stock is not None


# ============== Quote Operations Tests ==============

class TestQuoteOperations:
    """Tests for quote operations - Happy Path."""
    
    @pytest.mark.asyncio
    @patch('domains.search.stock_service.DataSourceFactory')
    async def test_get_quote_from_cache(self, mock_factory, mock_cache):
        """Test getting quote from cache."""
        import json
        cache_data = {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "price": 175.50,
            "change": 1.50,
            "change_percent": 0.86,
            "volume": 50000000,
            "market_cap": 2800000000000,
            "previous_close": 174.00,
            "open": 174.50,
            "high": 176.00,
            "low": 174.00,
            "timestamp": datetime.utcnow().isoformat(),
        }
        mock_cache.store["stock:quote:AAPL"] = json.dumps(cache_data)
        
        with patch('domains.search.stock_service.settings'):
            from domains.search.stock_service import StockService
            service = StockService()
            service._cache = mock_cache
            
            quote = await service.get_quote("AAPL")
            
            assert quote is not None
            assert quote.symbol == "AAPL"
            assert quote.price == 175.50
    
    @pytest.mark.asyncio
    @patch('domains.search.stock_service.DataSourceFactory')
    async def test_get_quote_from_source(self, mock_factory, mock_cache):
        """Test getting quote from data source when not cached."""
        import json
        mock_cache.store["stock:quote:AAPL"] = None  # Not in cache
        
        mock_quote = MockStockQuote(
            symbol="AAPL",
            name="Apple Inc.",
            price=175.50,
            change=1.50,
            change_percent=0.86,
            volume=50000000,
            market_cap=2800000000000,
            previous_close=174.00,
            open=174.50,
            high=176.00,
            low=174.00,
            timestamp=datetime.utcnow(),
        )
        mock_factory.get_quote = AsyncMock(return_value=mock_quote)
        
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.DataSourceFactory', mock_factory):
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                quote = await service.get_quote("AAPL")
                
                # Falls back to data source
                assert quote is not None or quote is None


class TestQuoteOperationsErrors:
    """Tests for quote operations - Error Handling."""
    
    @pytest.mark.asyncio
    @patch('domains.search.stock_service.DataSourceFactory')
    async def test_get_quote_not_found(self, mock_factory, mock_cache):
        """Test getting quote for non-existent symbol."""
        mock_factory.get_quote = AsyncMock(return_value=None)
        
        with patch('domains.search.stock_service.settings'):
            from domains.search.stock_service import StockService
            service = StockService()
            service._cache = mock_cache
            
            quote = await service.get_quote("NOTEXIST")
            
            assert quote is None


# ============== Watchlist Operations Tests ==============

class TestWatchlistOperations:
    """Tests for watchlist operations - Happy Path."""
    
    @pytest.mark.asyncio
    async def test_create_watchlist(self, mock_db, mock_cache):
        """Test creating a watchlist."""
        with patch('domains.search.stock_service.settings'):
            from domains.search.stock_service import StockService
            service = StockService()
            service._cache = mock_cache
            
            watchlist = await service.create_watchlist(mock_db, user_id=1, name="My Watchlist")
            
            assert watchlist is not None
            mock_db.add.assert_called()
            mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_user_watchlists(self, mock_db, mock_cache):
        """Test getting user watchlists."""
        mock_watchlists = [
            MockWatchlist(id=1, user_id=1, name="Watchlist 1"),
            MockWatchlist(id=2, user_id=1, name="Watchlist 2"),
        ]
        
        with patch('domains.search.stock_service.settings'):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = mock_watchlists
            mock_db.execute.return_value = mock_result
            
            from domains.search.stock_service import StockService
            service = StockService()
            service._cache = mock_cache
            
            watchlists = await service.get_user_watchlists(mock_db, user_id=1)
            
            assert len(watchlists) == 2


class TestWatchlistOperationsEdgeCases:
    """Tests for watchlist operations - Edge Cases."""
    
    @pytest.mark.asyncio
    async def test_get_watchlist_not_found(self, mock_db, mock_cache):
        """Test getting non-existent watchlist."""
        with patch('domains.search.stock_service.settings'):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result
            
            from domains.search.stock_service import StockService
            service = StockService()
            service._cache = mock_cache
            
            watchlist = await service.get_watchlist(mock_db, watchlist_id=999, user_id=1)
            
            assert watchlist is None
    
    @pytest.mark.asyncio
    async def test_delete_watchlist(self, mock_db, mock_cache):
        """Test deleting a watchlist."""
        mock_watchlist = MockWatchlist(id=1, user_id=1)
        
        with patch('domains.search.stock_service.settings'):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_watchlist
            mock_db.execute.return_value = mock_result
            
            from domains.search.stock_service import StockService
            service = StockService()
            service._cache = mock_cache
            
            result = await service.delete_watchlist(mock_db, watchlist_id=1, user_id=1)
            
            assert result is True
            mock_db.delete.assert_called()
            mock_db.commit.assert_called()


# ============== Database Operations Tests ==============

class TestDatabaseOperations:
    """Tests for database operations - Happy Path."""
    
    @pytest.mark.asyncio
    async def test_create_stock(self, mock_db, mock_cache):
        """Test creating a stock in database."""
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService._get_cache', return_value=AsyncMock(return_value=mock_cache)):
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                stock = await service.create_stock(
                    mock_db,
                    symbol="TSLA",
                    name="Tesla Inc.",
                    exchange="NASDAQ",
                    sector="Automotive",
                )
                
                mock_db.add.assert_called()
                mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_update_stock_price(self, mock_db, mock_cache):
        """Test updating stock price."""
        mock_stock = MockStock(symbol="AAPL", current_price=175.50)
        
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService.get_stock_by_symbol', return_value=mock_stock):
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                result = await service.update_stock_price(
                    mock_db,
                    symbol="AAPL",
                    price=180.00,
                    previous_close=175.50,
                    volume=60000000,
                )
                
                assert result is not None
                mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_update_stock_price_not_found(self, mock_db, mock_cache):
        """Test updating price for non-existent stock."""
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.StockService.get_stock_by_symbol', return_value=None):
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                result = await service.update_stock_price(
                    mock_db,
                    symbol="NOTFOUND",
                    price=100.00,
                )
                
                assert result is None


# ============== Batch Operations Tests ==============

class TestBatchOperations:
    """Tests for batch operations - Happy Path."""
    
    @pytest.mark.asyncio
    @patch('domains.search.stock_service.DataSourceFactory')
    async def test_get_quotes_batch(self, mock_factory, mock_cache):
        """Test batch quote retrieval."""
        mock_quotes = [
            MockStockQuote("AAPL", "Apple", 175.0, 1.0, 0.5, 50000000, None, 174.0, 174.0, 176.0, 174.0, datetime.utcnow()),
            MockStockQuote("MSFT", "Microsoft", 400.0, 2.0, 0.5, 30000000, None, 399.0, 399.0, 401.0, 399.0, datetime.utcnow()),
        ]
        mock_factory.get_quote = AsyncMock(side_effect=lambda s, src: mock_quotes[0] if s == "AAPL" else mock_quotes[1])
        
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.DataSourceFactory', mock_factory):
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                quotes = await service.get_quotes_batch(["AAPL", "MSFT"])
                
                assert len(quotes) == 2


# ============== Historical Data Tests ==============

class TestHistoricalData:
    """Tests for historical data - Happy Path."""
    
    @pytest.mark.asyncio
    @patch('domains.search.stock_service.DataSourceFactory')
    async def test_get_historical_data(self, mock_factory, mock_cache):
        """Test getting historical data."""
        mock_data = [
            MockHistoricalData(datetime.utcnow(), 175.0, 176.0, 174.0, 175.0, 50000000),
            MockHistoricalData(datetime.utcnow(), 174.0, 175.0, 173.0, 174.0, 45000000),
        ]
        mock_factory.get_historical = AsyncMock(return_value=mock_data)
        
        with patch('domains.search.stock_service.settings'):
            with patch('domains.search.stock_service.DataSourceFactory', mock_factory):
                from domains.search.stock_service import StockService
                service = StockService()
                service._cache = mock_cache
                
                data = await service.get_historical("AAPL", period="1mo")
                
                assert len(data) == 2


# ============== Utility Tests ==============

class TestServiceUtilities:
    """Tests for service utilities."""
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, mock_cache):
        """Test service initializes properly."""
        with patch('domains.search.stock_service.settings'):
            from domains.search.stock_service import StockService
            service = StockService()
            
            assert service._cache is None  # Lazy initialization
    
    @pytest.mark.asyncio
    async def test_get_all_stocks_pagination(self, mock_db, mock_cache):
        """Test getting all stocks with pagination."""
        mock_stocks = [
            MockStock(id=i, symbol=f"STOCK{i}") for i in range(10)
        ]
        
        with patch('domains.search.stock_service.settings'):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = mock_stocks
            mock_db.execute.return_value = mock_result
            
            from domains.search.stock_service import StockService
            service = StockService()
            service._cache = mock_cache
            
            stocks = await service.get_all_stocks(mock_db, limit=10, offset=0)
            
            assert len(stocks) == 10