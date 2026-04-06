"""
Signal model for trading signals (buy/sell/split-buy/split-sell).
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, DateTime, Numeric, Integer, Float, Boolean, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infra.database import Base


class SignalType(str, Enum):
    """Signal types."""
    BUY = "buy"
    SELL = "sell"
    SPLIT_BUY = "split_buy"
    SPLIT_SELL = "split_sell"


class SignalStatus(str, Enum):
    """Signal status."""
    PENDING = "pending"
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class SignalValidation(str, Enum):
    """Signal validation layer status."""
    SFP = "sfp"           # Smart Money Concept - Fair Pullback
    CHOCH = "choch"       # Change of Character (break of structure)
    FVG = "fvg"           # Fair Value Gap
    VALIDATED = "validated"


class Signal(Base):
    """Trading signal model."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(10), index=True)
    
    # Signal details
    signal_type: Mapped[SignalType] = mapped_column(SQLEnum(SignalType), index=True)
    status: Mapped[SignalStatus] = mapped_column(SQLEnum(SignalStatus), default=SignalStatus.PENDING, index=True)
    
    # Price levels
    entry_price: Mapped[float] = mapped_column(Numeric(12, 4))
    stop_loss: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    take_profit_1: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    take_profit_2: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    take_profit_3: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    
    # Probability & confidence
    probability: Mapped[float] = mapped_column(Float, default=0.0)  # Sigmoid probability (0-1)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)    # Overall confidence (0-100)
    risk_reward_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Validation layers
    sfp_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    chooch_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    fvg_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_status: Mapped[SignalValidation] = mapped_column(
        SQLEnum(SignalValidation), default=SignalValidation.SFP
    )
    
    # ATR dynamic thresholds
    atr_value: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    atr_multiplier: Mapped[float] = mapped_column(Float, default=2.0)  # Default ATR multiplier for stops
    
    # Technical indicators used
    indicators: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    
    # Reasoning/notes
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expired_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    stock: Mapped["Stock"] = relationship("Stock", back_populates="signals")
    alerts: Mapped[list["SignalAlert"]] = relationship(
        "SignalAlert", back_populates="signal", cascade="all, delete-orphan"
    )


class SignalAlert(Base):
    """Signal alert/notification model."""

    __tablename__ = "signal_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int] = mapped_column(Integer, ForeignKey("signals.id"), index=True)
    
    # Alert details
    alert_type: Mapped[str] = mapped_column(String(50))  # generated, triggered, expired, stopped_out, tp_hit
    message: Mapped[str] = mapped_column(Text)
    sent_via: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # telegram, email, webhook
    
    # Status
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    signal: Mapped["Signal"] = relationship("Signal", back_populates="alerts")
