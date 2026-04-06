"""
Unit tests for Trades domain - buy scanner functionality.

Tested by: Watchlist Team
Original developer: Trades Team
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

from apps.workers.scanner.buy_scanner import (
    BuySignal,
    UserPortfolio,
    PendingTrade,
    _build_buy_notification_body,
    _summarize_reasons,
    _generate_trade_link,
    process_buy_signal,
)


class TestBuySignal:
    """Test BuySignal dataclass."""
    
    def test_buy_signal_creation(self):
        """Test BuySignal object creation."""
        signal = BuySignal(
            symbol="AAPL",
            score=85,
            price=150.0,
            reasons=["Strong momentum", "Volume spike"],
            analysis={"rsi": 45},
            take_profit=160.0,
            stop_loss=145.0,
            confirmation_level="full",
        )
        
        assert signal.symbol == "AAPL"
        assert signal.score == 85
        assert signal.price == 150.0
        assert len(signal.reasons) == 2
        assert signal.take_profit == 160.0
        assert signal.stop_loss == 145.0
    
    def test_buy_signal_defaults(self):
        """Test BuySignal default values."""
        signal = BuySignal(symbol="TSLA", score=75, price=200.0)
        
        assert signal.reasons == []
        assert signal.analysis == {}
        assert signal.take_profit is None
        assert signal.stop_loss is None
        assert signal.confirmation_level is None


class TestUserPortfolio:
    """Test UserPortfolio dataclass."""
    
    def test_user_portfolio_creation(self):
        """Test UserPortfolio object creation."""
        portfolio = UserPortfolio(
            user_id=1,
            email="user@example.com",
            total_capital=10000.0,
            currency="USD",
            existing_shares=50.0,
            existing_avg_cost=145.0,
        )
        
        assert portfolio.user_id == 1
        assert portfolio.email == "user@example.com"
        assert portfolio.total_capital == 10000.0
        assert portfolio.existing_shares == 50.0


class TestPendingTrade:
    """Test PendingTrade dataclass."""
    
    def test_pending_trade_creation(self):
        """Test PendingTrade object creation."""
        trade = PendingTrade(
            id="test-uuid",
            user_id=1,
            symbol="AAPL",
            action="buy",
            suggested_shares=10,
            suggested_price=150.0,
            suggested_amount=1500.0,
            signal_id=1,
            link_token="token123",
            link_sig="sig456",
            expires_at="2024-01-01T00:00:00",
        )
        
        assert trade.id == "test-uuid"
        assert trade.user_id == 1
        assert trade.symbol == "AAPL"
        assert trade.action == "buy"
        assert trade.suggested_shares == 10


class TestBuyNotificationFunctions:
    """Test notification body building functions."""
    
    def test_build_buy_notification_body_with_reasons(self):
        """Test notification body with reasons."""
        signal = BuySignal(
            symbol="AAPL",
            score=85,
            price=150.0,
            reasons=["Strong momentum", "Volume spike", "RSI oversold"],
        )
        
        body = _build_buy_notification_body(signal)
        
        assert "AAPL" in body
        assert "85" in body
        assert "150.00" in body
        assert "Strong momentum" in body
    
    def test_build_buy_notification_body_without_reasons(self):
        """Test notification body without reasons."""
        signal = BuySignal(symbol="TSLA", score=70, price=200.0)
        
        body = _build_buy_notification_body(signal)
        
        assert "TSLA" in body
        assert "Buy signal detected" in body
    
    def test_summarize_reasons_with_content(self):
        """Test reason summarization with content."""
        reasons = ["Reason 1", "Reason 2", "Reason 3", "Reason 4"]
        
        result = _summarize_reasons(reasons, "fallback")
        
        assert result == "Reason 1, Reason 2, Reason 3"
    
    def test_summarize_reasons_empty(self):
        """Test reason summarization with empty list."""
        result = _summarize_reasons([], "fallback text")
        
        assert result == "fallback text"


class TestTradeLinkGeneration:
    """Test trade link generation."""
    
    @patch('apps.workers.scanner.buy_scanner.settings')
    def test_generate_trade_link(self, mock_settings):
        """Test trade link token and signature generation."""
        mock_settings.TRADE_LINK_SECRET = "test_secret"
        
        token, sig = _generate_trade_link(user_id=1, symbol="AAPL")
        
        assert token is not None
        assert len(token) > 0
        assert sig is not None
        assert len(sig) == 64  # SHA256 hexdigest length
    
    @patch('apps.workers.scanner.buy_scanner.settings')
    def test_generate_trade_link_different_users(self, mock_settings):
        """Test different users get different signatures."""
        mock_settings.TRADE_LINK_SECRET = "test_secret"
        
        token1, sig1 = _generate_trade_link(user_id=1, symbol="AAPL")
        token2, sig2 = _generate_trade_link(user_id=2, symbol="AAPL")
        
        assert sig1 != sig2
    
    @patch('apps.workers.scanner.buy_scanner.settings')
    def test_generate_trade_link_different_symbols(self, mock_settings):
        """Test different symbols get different signatures."""
        mock_settings.TRADE_LINK_SECRET = "test_secret"
        
        token1, sig1 = _generate_trade_link(user_id=1, symbol="AAPL")
        token2, sig2 = _generate_trade_link(user_id=1, symbol="TSLA")
        
        assert sig1 != sig2
