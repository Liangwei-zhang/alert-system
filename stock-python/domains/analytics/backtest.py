"""
Backtest model for storing backtest results and configurations.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
import json

from sqlalchemy import String, DateTime, Numeric, Float, Integer, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from infra.database import Base


class BacktestStatus(str, Enum):
    """Backtest status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Backtest(Base):
    """Backtest model for storing backtest configurations and results."""

    __tablename__ = "backtests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Strategy used
    strategy_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    strategy_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Symbol and timeframe
    symbol: Mapped[str] = mapped_column(String(10), index=True)
    timeframe: Mapped[str] = mapped_column(String(20))
    
    # Date range
    start_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    
    # Initial capital
    initial_capital: Mapped[float] = mapped_column(Numeric(12, 2), default=10000.0)
    
    # Status
    status: Mapped[BacktestStatus] = mapped_column(
        String(20), default=BacktestStatus.PENDING, index=True
    )
    
    # Performance metrics (JSON)
    metrics: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    
    # Equity curve (JSON array of {date, equity})
    equity_curve: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    
    # Trades (JSON array)
    trades: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    
    # Configuration (JSON)
    config: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    
    # Error message if failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# Pydantic schemas for API
from pydantic import BaseModel, ConfigDict, Field


class BacktestConfig(BaseModel):
    """Backtest configuration."""
    initial_capital: float = 10000.0
    commission: float = 0.001  # 0.1% per trade
    slippage: float = 0.0005  # 0.05% slippage
    position_sizing: str = "fixed"  # fixed, percent, kelly
    position_percent: float = 10.0  # % of capital per position
    allow_short: bool = False
    max_positions: int = 1


class BacktestCreate(BaseModel):
    """Backtest creation schema."""
    name: str
    description: Optional[str] = None
    strategy_id: Optional[int] = None
    strategy_name: Optional[str] = None
    symbol: str
    timeframe: str = "1d"
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000.0
    config: Optional[BacktestConfig] = None


class BacktestMetrics(BaseModel):
    """Performance metrics from backtest."""
    # Return metrics
    total_return: float = 0.0
    total_return_percent: float = 0.0
    annual_return: float = 0.0
    annual_return_percent: float = 0.0
    
    # Risk metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    volatility: float = 0.0
    
    # Trade metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_trade_return: float = 0.0
    avg_holding_period: float = 0.0
    
    # Portfolio metrics
    final_equity: float = 0.0
    peak_equity: float = 0.0
    
    # Risk-adjusted
    calmar_ratio: float = 0.0
    tail_ratio: float = 0.0
    
    model_config = ConfigDict(from_attributes=True)


class BacktestTrade(BaseModel):
    """Individual trade from backtest."""
    trade_id: int
    entry_date: datetime
    exit_date: Optional[datetime] = None
    symbol: str
    direction: str  # long or short
    entry_price: float
    exit_price: Optional[float] = None
    quantity: float
    pnl: float = 0.0
    pnl_percent: float = 0.0
    commission: float = 0.0
    holding_period: int = 0  # days
    status: str = "open"  # open, closed


class BacktestEquityPoint(BaseModel):
    """Equity curve point."""
    date: datetime
    equity: float
    drawdown: float = 0.0
    drawdown_percent: float = 0.0


class BacktestResponse(BaseModel):
    """Backtest response schema."""
    id: int
    name: str
    description: Optional[str] = None
    strategy_id: Optional[int] = None
    strategy_name: Optional[str] = None
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    status: str
    metrics: Optional[BacktestMetrics] = None
    equity_curve: List[BacktestEquityPoint] = []
    trades: List[BacktestTrade] = []
    config: Optional[BacktestConfig] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BacktestListResponse(BaseModel):
    """List of backtests."""
    backtests: List[BacktestResponse]
    total: int
    page: int = 1
    page_size: int = 20