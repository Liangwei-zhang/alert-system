"""
Unit tests for Trades domain - sell scanner functionality.

Tested by: Watchlist Team
Original developer: Trades Team
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

from apps.workers.scanner.sell_scanner import (
    SellSignal,
    PortfolioInfo,
    PendingTrade,
    _normalize_reasons,
    _build_sell_notification_body,
)


class TestSellSignal:
    """Test SellSignal dataclass."""
    
    def test_sell_signal_creation(self):
        """Test SellSignal object creation."""
        signal = SellSignal(
            symbol="AAPL",
            current_price=155.0,
            smc_top_probability=0.75,
            score=80,
            reasons=["RSI overbought", "Price rejection"],
            analysis={"trend": "bearish"},
            take_profit=165.0,
            stop_loss=140.0,
            confirmation_level="full",
        )
        
        assert signal.symbol == "AAPL"
        assert signal.current_price == 155.0
        assert signal.smc_top_probability == 0.75
        assert signal.score == 80
        assert len(signal.reasons) == 2
    
    def test_sell_signal_defaults(self):
        """Test SellSignal default values."""
        signal = SellSignal(symbol="TSLA", current_price=200.0)
        
        assert signal.smc_top_probability is None
        assert signal.score is None
        assert signal.reasons is None
        assert signal.analysis is None


class TestPortfolioInfo:
    """Test PortfolioInfo dataclass."""
    
    def test_portfolio_info_creation(self):
        """Test PortfolioInfo object creation."""
        portfolio = PortfolioInfo(
            id=1,
            user_id=1,
            email="user@example.com",
            symbol="AAPL",
            shares=100,
            avg_cost=140.0,
            total_capital=10000.0,
            target_profit=0.15,
            stop_loss=0.05,
            currency="USD",
        )
        
        assert portfolio.id == 1
        assert portfolio.symbol == "AAPL"
        assert portfolio.shares == 100
        assert portfolio.avg_cost == 140.0


class TestPendingTrade:
    """Test PendingTrade dataclass."""
    
    def test_pending_trade_creation(self):
        """Test PendingTrade object creation."""
        trade = PendingTrade(
            id="test-uuid",
            user_id=1,
            symbol="AAPL",
            action="sell",
            suggested_shares=50,
            suggested_price=155.0,
            suggested_amount=7750.0,
            signal_id=1,
            link_token="token123",
            link_sig="sig456",
            expires_at="2024-01-01T00:00:00",
        )
        
        assert trade.id == "test-uuid"
        assert trade.action == "sell"
        assert trade.suggested_shares == 50


class TestSellNotificationFunctions:
    """Test notification body building functions."""
    
    def test_normalize_reasons_with_content(self):
        """Test reason normalization with content."""
        signal = SellSignal(
            symbol="AAPL",
            current_price=155.0,
            reasons=["  Reason 1  ", "Reason 2", "", "Reason 3"],
        )
        
        reasons = _normalize_reasons(signal, "fallback")
        
        assert "Reason 1" in reasons
        assert "Reason 2" in reasons
        assert "Reason 3" in reasons
        assert "" not in reasons
    
    def test_normalize_reasons_empty(self):
        """Test reason normalization with empty list."""
        signal = SellSignal(symbol="AAPL", current_price=155.0, reasons=[])
        
        reasons = _normalize_reasons(signal, "fallback text")
        
        assert reasons == ["fallback text"]
    
    def test_normalize_reasons_none(self):
        """Test reason normalization with None."""
        signal = SellSignal(symbol="AAPL", current_price=155.0, reasons=None)
        
        reasons = _normalize_reasons(signal, "fallback text")
        
        assert reasons == ["fallback text"]
    
    def test_build_sell_notification_body_with_reasons(self):
        """Test sell notification body with reasons."""
        reasons = ["RSI overbought", "Price rejection", "Trend reversal"]
        
        body = _build_sell_notification_body(
            symbol="AAPL",
            current_price=155.0,
            reasons=reasons,
            fallback="fallback",
        )
        
        assert "AAPL" in body
        assert "155.00" in body
        assert "RSI overbought" in body
    
    def test_build_sell_notification_body_without_reasons(self):
        """Test sell notification body without reasons."""
        body = _build_sell_notification_body(
            symbol="TSLA",
            current_price=200.0,
            reasons=[],
            fallback="Sell signal detected",
        )
        
        assert "TSLA" in body
        assert "200.00" in body
        assert "Sell signal detected" in body
