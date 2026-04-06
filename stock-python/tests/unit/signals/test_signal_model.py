"""
Unit tests for Signals domain - tested by Notifications Team (Agent C).

Original developer: Signals Team (Agent B)
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from domains.signals.signal import (
    Signal, SignalType, SignalStatus, SignalValidation, SignalAlert
)


class TestSignalModel:
    """Test Signal model and enums."""
    
    def test_signal_type_enum_values(self):
        """Test SignalType enum has correct values."""
        assert SignalType.BUY.value == "buy"
        assert SignalType.SELL.value == "sell"
        assert SignalType.SPLIT_BUY.value == "split_buy"
        assert SignalType.SPLIT_SELL.value == "split_sell"
    
    def test_signal_status_enum_values(self):
        """Test SignalStatus enum has correct values."""
        assert SignalStatus.PENDING.value == "pending"
        assert SignalStatus.ACTIVE.value == "active"
        assert SignalStatus.TRIGGERED.value == "triggered"
        assert SignalStatus.EXPIRED.value == "expired"
        assert SignalStatus.CANCELLED.value == "cancelled"
    
    def test_signal_validation_enum_values(self):
        """Test SignalValidation enum has correct values."""
        assert SignalValidation.SFP.value == "sfp"
        assert SignalValidation.CHOCH.value == "choch"
        assert SignalValidation.FVG.value == "fvg"
        assert SignalValidation.VALIDATED.value == "validated"
    
    def test_signal_creation(self):
        """Test Signal object creation with all fields."""
        signal = Signal(
            id=1,
            stock_id=1,
            symbol="AAPL",
            signal_type=SignalType.BUY,
            status=SignalStatus.PENDING,
            entry_price=150.0,
            stop_loss=145.0,
            take_profit_1=155.0,
            take_profit_2=160.0,
            take_profit_3=165.0,
            probability=0.75,
            confidence=80.0,
            risk_reward_ratio=2.0,
            sfp_validated=True,
            chooch_validated=True,
            fvg_validated=False,
            validation_status=SignalValidation.CHOCH,
            atr_value=2.5,
            atr_multiplier=2.0,
            reasoning="Bullish setup",
            generated_at=datetime.utcnow()
        )
        
        assert signal.symbol == "AAPL"
        assert signal.signal_type == SignalType.BUY
        assert signal.status == SignalStatus.PENDING
        assert signal.confidence == 80.0
        assert signal.sfp_validated is True
        assert signal.chooch_validated is True
        assert signal.fvg_validated is False
    
    def test_signal_alert_creation(self):
        """Test SignalAlert creation."""
        alert = SignalAlert(
            signal_id=1,
            alert_type="generated",
            message="New buy signal for AAPL",
            sent=False
        )
        
        assert alert.signal_id == 1
        assert alert.alert_type == "generated"
        assert alert.sent is False
        assert alert.created_at is not None


class TestSignalEdgeCases:
    """Test edge cases for Signal model."""
    
    def test_signal_with_null_optional_fields(self):
        """Test Signal creation with null optional fields."""
        signal = Signal(
            stock_id=1,
            symbol="TSLA",
            signal_type=SignalType.SELL,
            status=SignalStatus.PENDING,
            entry_price=200.0,
            probability=0.5,
            confidence=50.0
        )
        
        assert signal.stop_loss is None
        assert signal.take_profit_1 is None
        assert signal.take_profit_2 is None
        assert signal.take_profit_3 is None
        assert signal.risk_reward_ratio is None
        assert signal.atr_value is None
        assert signal.reasoning is None
    
    def test_signal_status_transitions(self):
        """Test valid signal status transitions."""
        signal = Signal(
            stock_id=1,
            symbol="MSFT",
            signal_type=SignalType.BUY,
            status=SignalStatus.PENDING,
            entry_price=300.0,
            probability=0.6,
            confidence=60.0
        )
        
        # Test pending -> active
        signal.status = SignalStatus.ACTIVE
        assert signal.status == SignalStatus.ACTIVE
        
        # Test active -> triggered
        signal.status = SignalStatus.TRIGGERED
        signal.triggered_at = datetime.utcnow()
        assert signal.status == SignalStatus.TRIGGERED
        assert signal.triggered_at is not None
    
    def test_validation_status_progression(self):
        """Test validation status progression."""
        signal = Signal(
            stock_id=1,
            symbol="GOOGL",
            signal_type=SignalType.BUY,
            status=SignalStatus.PENDING,
            entry_price=100.0,
            probability=0.3,
            confidence=30.0,
            validation_status=SignalValidation.SFP,
            sfp_validated=True
        )
        
        # Progress through validations
        signal.chooch_validated = True
        signal.validation_status = SignalValidation.CHOCH
        
        signal.fvg_validated = True
        signal.validation_status = SignalValidation.VALIDATED
        
        assert signal.validation_status == SignalValidation.VALIDATED
        assert signal.sfp_validated is True
        assert signal.chooch_validated is True
        assert signal.fvg_validated is True


class TestSignalErrorHandling:
    """Test error handling for Signal model."""
    
    def test_invalid_signal_type(self):
        """Test handling of invalid signal type."""
        # Should raise or handle invalid enum
        with pytest.raises(ValueError):
            SignalType("invalid_type")
    
    def test_negative_prices(self):
        """Test handling of negative prices - should be allowed but flagged."""
        signal = Signal(
            stock_id=1,
            symbol="TEST",
            signal_type=SignalType.BUY,
            status=SignalStatus.PENDING,
            entry_price=-10.0,  # Invalid but allowed at model level
            probability=0.5,
            confidence=50.0
        )
        
        assert signal.entry_price < 0  # Model allows, business logic should catch
    
    def test_confidence_bounds(self):
        """Test confidence value bounds."""
        # Confidence should be 0-100 but model doesn't enforce
        signal = Signal(
            stock_id=1,
            symbol="TEST",
            signal_type=SignalType.BUY,
            status=SignalStatus.PENDING,
            entry_price=100.0,
            probability=1.5,  # Invalid probability > 1
            confidence=150.0   # Invalid confidence > 100
        )
        
        assert signal.probability > 1  # Model allows, business logic should enforce
        assert signal.confidence > 100


class TestSignalAlertTypes:
    """Test different alert types."""
    
    @pytest.mark.parametrize("alert_type,expected_message", [
        ("generated", "New buy signal"),
        ("triggered", "Signal triggered"),
        ("expired", "Signal expired"),
        ("stopped_out", "Stop loss hit"),
        ("tp_hit", "Take profit hit")
    ])
    def test_alert_types(self, alert_type, expected_message):
        """Test various alert types."""
        signal = Signal(
            stock_id=1,
            symbol="AAPL",
            signal_type=SignalType.BUY,
            status=SignalStatus.PENDING,
            entry_price=150.0,
            probability=0.7,
            confidence=70.0
        )
        signal.id = 1
        
        alert = SignalAlert(
            signal_id=signal.id,
            alert_type=alert_type,
            message=f"Test alert: {alert_type}",
            sent=False
        )
        
        assert alert.alert_type == alert_type
        assert alert.sent is False