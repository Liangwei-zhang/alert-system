"""
Backtest service - historical data storage and backtest engine.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Callable, Dict, Any
from enum import Enum
import json
import math

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from infra.database import Base, get_db
from domains.analytics.backtest import (
    Backtest, BacktestStatus, BacktestConfig, BacktestMetrics,
    BacktestTrade, BacktestEquityPoint, BacktestCreate
)
from domains.market_data.data_source import DataSourceFactory, HistoricalData


# Direction enum for trades
class TradeDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class OHLCV:
    """OHLCV data point."""
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class HistoricalDataStore:
    """Store and retrieve historical OHLCV data."""
    
    def __init__(self):
        self._cache: Dict[str, List[OHLCV]] = {}
    
    async def get_data(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime,
        timeframe: str = "1d"
    ) -> List[OHLCV]:
        """Get historical data for a symbol within date range."""
        cache_key = f"{symbol}:{timeframe}"
        
        # Try to fetch from source if not cached
        if cache_key not in self._cache:
            await self._fetch_and_cache(symbol, timeframe)
        
        if cache_key not in self._cache:
            return []
        
        # Filter by date range
        data = self._cache[cache_key]
        return [
            ohlcv for ohlcv in data 
            if start_date <= ohlcv.date <= end_date
        ]
    
    async def _fetch_and_cache(self, symbol: str, timeframe: str):
        """Fetch historical data and cache it."""
        # Determine period based on timeframe
        period = "2y" if timeframe in ["1d", "1w"] else "1y"
        
        historical = await DataSourceFactory.get_historical(symbol, period)
        
        cache_key = f"{symbol}:{timeframe}"
        self._cache[cache_key] = [
            OHLCV(
                date=h.date,
                open=h.open,
                high=h.high,
                low=h.low,
                close=h.close,
                volume=h.volume
            )
            for h in historical
        ]


@dataclass
class Position:
    """Active position in backtest."""
    entry_date: datetime
    entry_price: float
    direction: TradeDirection
    quantity: float
    symbol: str
    

@dataclass
class TradeResult:
    """Completed trade result."""
    entry_date: datetime
    exit_date: datetime
    symbol: str
    direction: TradeDirection
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_percent: float
    commission: float
    holding_period: int


class BacktestEngine:
    """Backtest engine for strategy testing."""
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
        slippage: float = 0.0005,
        allow_short: bool = False,
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.allow_short = allow_short
        
        self.equity = initial_capital
        self.positions: List[Position] = []
        self.trades: List[TradeResult] = []
        self.equity_curve: List[BacktestEquityPoint] = []
        
        self._peak_equity = initial_capital
        self._trade_id_counter = 0
    
    def reset(self):
        """Reset engine state."""
        self.equity = self.initial_capital
        self.positions = []
        self.trades = []
        self.equity_curve = []
        self._peak_equity = self.initial_capital
        self._trade_id_counter = 0
    
    def calculate_position_size(
        self, 
        price: float, 
        risk_percent: float = 10.0
    ) -> float:
        """Calculate position size based on available equity."""
        allocated = self.equity * (risk_percent / 100)
        return allocated / price
    
    def apply_slippage(self, price: float, direction: TradeDirection) -> float:
        """Apply slippage to price."""
        if direction == TradeDirection.LONG:
            return price * (1 + self.slippage)
        else:
            return price * (1 - self.slippage)
    
    def open_position(
        self,
        date: datetime,
        symbol: str,
        direction: TradeDirection,
        price: float,
        quantity: float
    ) -> bool:
        """Open a new position."""
        # Calculate cost with commission
        cost = price * quantity
        commission_cost = cost * self.commission
        total_cost = cost + commission_cost
        
        if total_cost > self.equity:
            return False  # Not enough capital
        
        # Apply slippage
        execution_price = self.apply_slippage(price, direction)
        
        self.equity -= cost
        self.positions.append(Position(
            entry_date=date,
            entry_price=execution_price,
            direction=direction,
            quantity=quantity,
            symbol=symbol
        ))
        
        return True
    
    def close_position(
        self,
        position: Position,
        date: datetime,
        price: float
    ) -> TradeResult:
        """Close an existing position."""
        execution_price = self.apply_slippage(price, position.direction)
        
        # Calculate PnL
        if position.direction == TradeDirection.LONG:
            pnl = (execution_price - position.entry_price) * position.quantity
        else:  # Short
            pnl = (position.entry_price - execution_price) * position.quantity
        
        # Calculate commission
        exit_value = execution_price * position.quantity
        commission_cost = exit_value * self.commission
        
        # Update equity
        self.equity += exit_value - commission_cost
        
        # Create trade result
        holding_period = (date - position.entry_date).days
        
        pnl_percent = (pnl / (position.entry_price * position.quantity)) * 100
        
        trade = TradeResult(
            entry_date=position.entry_date,
            exit_date=date,
            symbol=position.symbol,
            direction=position.direction,
            entry_price=position.entry_price,
            exit_price=execution_price,
            quantity=position.quantity,
            pnl=pnl - commission_cost,
            pnl_percent=pnl_percent,
            commission=commission_cost,
            holding_period=holding_period
        )
        
        self.trades.append(trade)
        self._trade_id_counter += 1
        trade.trade_id = self._trade_id_counter
        
        return trade
    
    def update_equity_curve(self, date: datetime):
        """Record equity point for curve."""
        # Calculate current drawdown
        if self.equity > self._peak_equity:
            self._peak_equity = self.equity
        
        drawdown = self._peak_equity - self.equity
        drawdown_percent = (drawdown / self._peak_equity * 100) if self._peak_equity > 0 else 0
        
        self.equity_curve.append(BacktestEquityPoint(
            date=date,
            equity=self.equity,
            drawdown=drawdown,
            drawdown_percent=drawdown_percent
        ))


# Strategy signal function type
Signal = Optional[Dict[str, Any]]  # {direction, price, confidence}


class BacktestService:
    """Service for running backtests and managing historical data."""
    
    def __init__(self):
        self.data_store = HistoricalDataStore()
        self._engines: Dict[int, BacktestEngine] = {}
    
    async def run_backtest(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        strategy_fn: Callable[[List[OHLCV], int], Signal],
        config: BacktestConfig = None,
        timeframe: str = "1d"
    ) -> Dict[str, Any]:
        """Run a backtest with a strategy function.
        
        Args:
            symbol: Stock symbol
            start_date: Backtest start date
            end_date: Backtest end date
            strategy_fn: Function that takes (ohlcv_data, current_index) and returns signal
            config: Backtest configuration
            timeframe: Data timeframe
        
        Returns:
            Dictionary with metrics, trades, and equity curve
        """
        config = config or BacktestConfig()
        
        # Get historical data
        data = await self.data_store.get_data(
            symbol, start_date, end_date, timeframe
        )
        
        if not data:
            raise ValueError(f"No historical data available for {symbol}")
        
        # Initialize engine
        engine = BacktestEngine(
            initial_capital=config.initial_capital,
            commission=config.commission,
            slippage=config.slippage,
            allow_short=config.allow_short
        )
        
        # Run backtest
        for i, bar in enumerate(data):
            # Update equity curve
            engine.update_equity_curve(bar.date)
            
            # Get signal from strategy
            signal = strategy_fn(data, i)
            
            if signal is None:
                continue
            
            direction = signal.get("direction")
            signal_price = signal.get("price", bar.close)
            confidence = signal.get("confidence", 1.0)
            
            # Check if we should close existing positions
            close_signal = signal.get("close", False)
            
            if close_signal and engine.positions:
                for pos in list(engine.positions):
                    engine.close_position(pos, bar.date, bar.close)
            
            # Check if we should open new position
            if direction and not engine.positions:
                # Determine position size
                if config.position_sizing == "fixed":
                    quantity = engine.calculate_position_size(
                        signal_price, config.position_percent
                    )
                else:
                    quantity = engine.calculate_position_size(
                        signal_price, config.position_percent
                    )
                
                if quantity > 0:
                    trade_dir = TradeDirection.LONG if direction == "long" else TradeDirection.SHORT
                    
                    if not config.allow_short and trade_dir == TradeDirection.SHORT:
                        continue
                    
                    engine.open_position(
                        bar.date, symbol, trade_dir, signal_price, quantity
                    )
        
        # Close any open positions at the end
        for pos in list(engine.positions):
            engine.close_position(pos, data[-1].date, data[-1].close)
        
        # Final equity curve update
        engine.update_equity_curve(data[-1].date)
        
        # Calculate metrics
        metrics = self._calculate_metrics(engine, start_date, end_date)
        
        return {
            "metrics": metrics,
            "trades": engine.trades,
            "equity_curve": engine.equity_curve
        }
    
    def _calculate_metrics(
        self, 
        engine: BacktestEngine, 
        start_date: datetime,
        end_date: datetime
    ) -> BacktestMetrics:
        """Calculate performance metrics from backtest results."""
        trades = engine.trades
        equity_curve = engine.equity_curve
        
        if not trades:
            return BacktestMetrics(
                final_equity=engine.equity,
                peak_equity=engine.initial_capital
            )
        
        # Basic metrics
        total_pnl = sum(t.pnl for t in trades)
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl <= 0]
        
        total_return = engine.equity - engine.initial_capital
        total_return_percent = (total_return / engine.initial_capital) * 100
        
        # Annualize return
        days = (end_date - start_date).days
        years = days / 365.25 if days > 0 else 1
        annual_return = total_return / years if years > 0 else 0
        annual_return_percent = total_return_percent / years if years > 0 else 0
        
        # Trade metrics
        num_trades = len(trades)
        num_winners = len(winning_trades)
        num_losers = len(losing_trades)
        win_rate = (num_winners / num_trades * 100) if num_trades > 0 else 0
        
        avg_win = sum(t.pnl for t in winning_trades) / num_winners if num_winners > 0 else 0
        avg_loss = sum(t.pnl for t in losing_trades) / num_losers if num_losers > 0 else 0
        
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        avg_trade_return = total_pnl / num_trades if num_trades > 0 else 0
        
        avg_holding = sum(t.holding_period for t in trades) / num_trades if num_trades > 0 else 0
        
        # Drawdown
        peak = engine.initial_capital
        max_dd = 0
        max_dd_percent = 0
        
        for point in equity_curve:
            if point.equity > peak:
                peak = point.equity
            dd = peak - point.equity
            dd_percent = (dd / peak * 100) if peak > 0 else 0
            
            if dd > max_dd:
                max_dd = dd
                max_dd_percent = dd_percent
        
        # Volatility (annualized std dev of returns)
        if len(trades) > 1:
            returns = [(t.pnl_percent) for t in trades]
            volatility = np.std(returns) * math.sqrt(252)  # Annualize
        else:
            volatility = 0
        
        # Sharpe ratio (assuming 0% risk-free rate)
        if volatility > 0:
            sharpe = annual_return_percent / volatility
        else:
            sharpe = 0
        
        # Sortino ratio (downside deviation)
        if len(losing_trades) > 1:
            downside_returns = [t.pnl_percent for t in losing_trades]
            downside_std = np.std(downside_returns) * math.sqrt(252)
            sortino = annual_return_percent / downside_std if downside_std > 0 else 0
        else:
            sortino = 0
        
        # Calmar ratio (annual return / max drawdown)
        calmar = annual_return_percent / max_dd_percent if max_dd_percent > 0 else 0
        
        # Tail ratio (95th percentile / 5th percentile)
        if len(trades) >= 20:
            sorted_returns = sorted([t.pnl_percent for t in trades])
            p5 = sorted_returns[int(len(sorted_returns) * 0.05)]
            p95 = sorted_returns[int(len(sorted_returns) * 0.95)]
            tail_ratio = abs(p95 / p5) if p5 != 0 else 0
        else:
            tail_ratio = 0
        
        return BacktestMetrics(
            total_return=total_return,
            total_return_percent=total_return_percent,
            annual_return=annual_return,
            annual_return_percent=annual_return_percent,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            max_drawdown_percent=max_dd_percent,
            volatility=volatility,
            total_trades=num_trades,
            winning_trades=num_winners,
            losing_trades=num_losers,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            avg_trade_return=avg_trade_return,
            avg_holding_period=avg_holding,
            final_equity=engine.equity,
            peak_equity=engine._peak_equity,
            calmar_ratio=calmar,
            tail_ratio=tail_ratio
        )
    
    async def save_backtest(
        self,
        db: AsyncSession,
        name: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        config: BacktestConfig,
        results: Dict[str, Any]
    ) -> Backtest:
        """Save backtest results to database."""
        metrics = results["metrics"]
        trades = results["trades"]
        equity_curve = results["equity_curve"]
        
        backtest = Backtest(
            name=name,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=config.initial_capital,
            status=BacktestStatus.COMPLETED,
            metrics=json.loads(metrics.model_dump_json()),
            equity_curve=[
                {"date": p.date.isoformat(), "equity": p.equity, 
                 "drawdown": p.drawdown, "drawdown_percent": p.drawdown_percent}
                for p in equity_curve
            ],
            trades=[
                {
                    "trade_id": t.trade_id,
                    "entry_date": t.entry_date.isoformat(),
                    "exit_date": t.exit_date.isoformat(),
                    "symbol": t.symbol,
                    "direction": t.direction.value,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "quantity": t.quantity,
                    "pnl": t.pnl,
                    "pnl_percent": t.pnl_percent,
                    "commission": t.commission,
                    "holding_period": t.holding_period
                }
                for t in trades
            ],
            config=config.model_dump(),
            completed_at=datetime.utcnow()
        )
        
        db.add(backtest)
        await db.commit()
        await db.refresh(backtest)
        
        return backtest
    
    async def get_backtest(self, db: AsyncSession, backtest_id: int) -> Optional[Backtest]:
        """Get backtest by ID."""
        result = await db.execute(
            select(Backtest).where(Backtest.id == backtest_id)
        )
        return result.scalar_one_or_none()
    
    async def list_backtests(
        self, 
        db: AsyncSession, 
        symbol: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Backtest]:
        """List backtests with optional symbol filter."""
        query = select(Backtest).order_by(Backtest.created_at.desc())
        
        if symbol:
            query = query.where(Backtest.symbol == symbol)
        
        query = query.limit(limit).offset(offset)
        
        result = await db.execute(query)
        return list(result.scalars().all())


# Example strategy functions

def moving_average_crossover(
    data: List[OHLCV], 
    i: int,
    short_period: int = 10,
    long_period: int = 30
) -> Signal:
    """Moving average crossover strategy signal."""
    if i < long_period:
        return None
    
    # Calculate moving averages
    short_ma = sum(d.close for d in data[i-short_period:i]) / short_period
    long_ma = sum(d.close for d in data[i-long_period:i]) / long_period
    
    # Previous bar
    prev_short = sum(d.close for d in data[i-short_period-1:i-1]) / short_period
    prev_long = sum(d.close for d in data[i-long_period-1:i-1]) / long_period
    
    # Crossover detection
    if prev_short <= prev_long and short_ma > long_ma:
        return {"direction": "long", "price": data[i].close, "confidence": 0.7}
    elif prev_short >= prev_long and short_ma < long_ma:
        return {"direction": "short", "price": data[i].close, "close": True, "confidence": 0.7}
    
    return None


def mean_reversion(
    data: List[OHLCV], 
    i: int,
    period: int = 20,
    std_multiplier: float = 2.0
) -> Signal:
    """Mean reversion strategy signal."""
    if i < period:
        return None
    
    # Calculate mean and std
    closes = [d.close for d in data[i-period:i]]
    mean = sum(closes) / period
    std = np.std(closes)
    
    current = data[i].close
    
    # Mean reversion signals
    if current < mean - std_multiplier * std:
        return {"direction": "long", "price": current, "confidence": 0.6}
    elif current > mean + std_multiplier * std:
        return {"direction": "short", "price": current, "close": True, "confidence": 0.6}
    
    # Exit if mean reversion worked
    if current > mean - std * 0.5 or current < mean + std * 0.5:
        return {"close": True}
    
    return None


# Service instance
backtest_service = BacktestService()