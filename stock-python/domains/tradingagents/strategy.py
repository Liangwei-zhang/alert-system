"""
Strategy model for trading strategies.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, DateTime, Numeric, Float, Boolean, Text, Integer, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from infra.database import Base


class StrategyType(str, Enum):
    """Strategy types."""
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    SMC = "smart_money_concept"  # SFP, CHOCH, FVG based
    SCALPING = "scalping"
    SWING = "swing"


class StrategyStatus(str, Enum):
    """Strategy status."""
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Strategy(Base):
    """Trading strategy model."""

    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Strategy type & config
    strategy_type: Mapped[StrategyType] = mapped_column(SQLEnum(StrategyType))
    status: Mapped[StrategyStatus] = mapped_column(
        SQLEnum(StrategyStatus), default=StrategyStatus.ACTIVE, index=True
    )
    
    # SMC/Gen 3.1 specific settings
    use_sfp: Mapped[bool] = mapped_column(Boolean, default=True)
    use_chooch: Mapped[bool] = mapped_column(Boolean, default=True)
    use_fvg: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Risk management
    default_risk_percent: Mapped[float] = mapped_column(Float, default=1.0)  # % risk per trade
    max_position_size: Mapped[float] = mapped_column(Float, default=10.0)    # Max % of portfolio
    default_atr_multiplier: Mapped[float] = mapped_column(Float, default=2.0)
    
    # Signal filters
    min_probability: Mapped[float] = mapped_column(Float, default=0.5)
    min_confidence: Mapped[float] = mapped_column(Float, default=50.0)
    min_risk_reward: Mapped[float] = mapped_column(Float, default=1.5)
    
    # Take profit levels
    tp1_percent: Mapped[float] = mapped_column(Float, default=1.0)   # TP1 at 1R
    tp2_percent: Mapped[float] = mapped_column(Float, default=2.0)   # TP2 at 2R
    tp3_percent: Mapped[float] = mapped_column(Float, default=3.0)   # TP3 at 3R
    partial_tp_percent: Mapped[float] = mapped_column(Float, default=50.0)  # Close 50% at TP1
    
    # Active symbols (JSON array)
    symbols: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    
    # Timeframes
    timeframes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    
    # Performance tracking
    total_signals: Mapped[int] = mapped_column(Integer, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0)
    losing_trades: Mapped[int] = mapped_column(Integer, default=0)
    total_pnl: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class StrategySignalConfig(Base):
    """Configuration for signal generation per strategy."""

    __tablename__ = "strategy_signal_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_id: Mapped[int] = mapped_column(Integer, ForeignKey("strategies.id"), index=True)
    
    # Signal parameters
    signal_type_filter: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # buy, sell, or None for all
    
    # Probability thresholds
    sfp_weight: Mapped[float] = mapped_column(Float, default=0.3)
    chooch_weight: Mapped[float] = mapped_column(Float, default=0.4)
    fvg_weight: Mapped[float] = mapped_column(Float, default=0.3)
    
    # ATR settings
    atr_period: Mapped[int] = mapped_column(Integer, default=14)
    atr_multiplier_stop: Mapped[float] = mapped_column(Float, default=2.0)
    atr_multiplier_target: Mapped[float] = mapped_column(Float, default=3.0)
    
    # Additional filters
    min_volume: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    min_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    max_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
