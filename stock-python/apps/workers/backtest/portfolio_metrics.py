"""
Portfolio-level backtest metrics.

Features:
- Portfolio-level performance metrics
- Position correlation analysis
- Sector exposure tracking
- Risk-adjusted returns
- Drawdown analysis
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from domains.analytics.backtest import BacktestTrade


@dataclass
class PortfolioMetrics:
    """Portfolio-level metrics."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_pnl_pct: float
    avg_win: float
    avg_loss: float
    avg_holding_period: float  # hours
    
    # Risk metrics
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    volatility: float
    
    # Position metrics
    avg_positions_per_day: float
    avg_position_size: float
    largest_position: float
    smallest_position: float
    
    # Time metrics
    avg_trade_duration_hours: float
    longest_trade_hours: float
    shortest_trade_hours: float


@dataclass
class PositionSummary:
    """Summary of a single position."""
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    holding_hours: float
    sector: Optional[str] = None


@dataclass
class SectorExposure:
    """Sector exposure summary."""
    sector: str
    total_pnl: float
    trade_count: int
    avg_position_size: float
    exposure_pct: float


class PortfolioAnalyzer:
    """Analyze portfolio-level metrics from backtest trades."""
    
    def __init__(self, trades: list[BacktestTrade]):
        self.trades = trades
    
    def calculate_metrics(self) -> PortfolioMetrics:
        """Calculate all portfolio metrics."""
        if not self.trades:
            return self._empty_metrics()
        
        # Basic counts
        total = len(self.trades)
        winners = [t for t in self.trades if t.pnl > 0]
        losers = [t for t in self.trades if t.pnl <= 0]
        
        winning_count = len(winners)
        losing_count = len(losers)
        
        win_rate = winning_count / total if total > 0 else 0
        
        # PnL
        total_pnl = sum(t.pnl for t in self.trades)
        
        # Calculate portfolio value for percentage
        entry_values = [t.entry_price * t.quantity for t in self.trades]
        portfolio_value = np.mean(entry_values) if entry_values else 1
        total_pnl_pct = (total_pnl / portfolio_value * 100) if portfolio_value > 0 else 0
        
        # Average win/loss
        avg_win = np.mean([t.pnl for t in winners]) if winners else 0
        avg_loss = np.mean([t.pnl for t in losers]) if losers else 0
        
        # Holding periods
        holding_hours = []
        for t in self.trades:
            if t.exit_date and t.entry_date:
                hours = (t.exit_date - t.entry_date).total_seconds() / 3600
                holding_hours.append(hours)
        
        avg_holding = np.mean(holding_hours) if holding_hours else 0
        
        # Risk metrics
        returns = [t.pnl_pct / 100 for t in self.trades if t.pnl_pct != 0]
        sharpe = self._sharpe_ratio(returns)
        sortino = self._sortino_ratio(returns)
        volatility = np.std(returns) * 100 if returns else 0
        
        # Drawdown
        max_dd, max_dd_pct = self._max_drawdown(returns)
        
        # Position metrics
        quantities = [t.quantity for t in self.trades]
        avg_size = np.mean(quantities) if quantities else 0
        largest = max(quantities) if quantities else 0
        smallest = min(quantities) if quantities else 0
        
        # Positions per day
        dates = set(t.entry_date.date() for t in self.trades if t.entry_date)
        days_count = len(dates) or 1
        avg_positions = total / days_count
        
        # Time metrics
        longest = max(holding_hours) if holding_hours else 0
        shortest = min(holding_hours) if holding_hours else 0
        
        return PortfolioMetrics(
            total_trades=total,
            winning_trades=winning_count,
            losing_trades=losing_count,
            win_rate=round(win_rate * 100, 2),
            total_pnl=round(total_pnl, 2),
            total_pnl_pct=round(total_pnl_pct, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            avg_holding_period=round(avg_holding, 1),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            max_drawdown=round(max_dd, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            volatility=round(volatility, 2),
            avg_positions_per_day=round(avg_positions, 2),
            avg_position_size=round(avg_size, 2),
            largest_position=round(largest, 2),
            smallest_position=round(smallest, 2),
            avg_trade_duration_hours=round(avg_holding, 1),
            longest_trade_hours=round(longest, 1),
            shortest_trade_hours=round(shortest, 1)
        )
    
    def _empty_metrics(self) -> PortfolioMetrics:
        """Return empty metrics."""
        return PortfolioMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0,
            total_pnl=0,
            total_pnl_pct=0,
            avg_win=0,
            avg_loss=0,
            avg_holding_period=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            max_drawdown=0,
            max_drawdown_pct=0,
            volatility=0,
            avg_positions_per_day=0,
            avg_position_size=0,
            largest_position=0,
            smallest_position=0,
            avg_trade_duration_hours=0,
            longest_trade_hours=0,
            shortest_trade_hours=0
        )
    
    def _sharpe_ratio(self, returns: list[float], risk_free: float = 0.02) -> float:
        """Calculate Sharpe ratio."""
        if not returns or len(returns) < 2:
            return 0
        
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0
        
        # Annualize (assuming daily returns)
        return (avg_return - risk_free) / std_return * np.sqrt(252)
    
    def _sortino_ratio(self, returns: list[float], risk_free: float = 0.02) -> float:
        """Calculate Sortino ratio (downside deviation)."""
        if not returns or len(returns) < 2:
            return 0
        
        avg_return = np.mean(returns)
        
        # Downside returns only
        downside = [r for r in returns if r < 0]
        
        if not downside:
            return 0
        
        downside_std = np.std(downside)
        
        if downside_std == 0:
            return 0
        
        return (avg_return - risk_free) / downside_std * np.sqrt(252)
    
    def _max_drawdown(self, returns: list[float]) -> tuple[float, float]:
        """Calculate maximum drawdown."""
        if not returns:
            return 0, 0
        
        # Cumulative returns
        cumulative = np.cumprod([1 + r for r in returns])
        
        # Running maximum
        running_max = np.maximum.accumulate(cumulative)
        
        # Drawdown
        drawdown = (cumulative - running_max) / running_max
        
        max_dd = abs(np.min(drawdown)) if len(drawdown) > 0 else 0
        max_dd_pct = max_dd * 100
        
        return max_dd, max_dd_pct
    
    def get_position_summaries(self) -> list[PositionSummary]:
        """Get summaries of all positions."""
        return [
            PositionSummary(
                symbol=t.symbol,
                direction=t.direction.value if t.direction else "unknown",
                entry_price=t.entry_price,
                exit_price=t.exit_price or 0,
                pnl=t.pnl,
                pnl_pct=t.pnl_pct,
                holding_hours=(
                    (t.exit_date - t.entry_date).total_seconds() / 3600
                    if t.exit_date and t.entry_date else 0
                )
            )
            for t in self.trades
        ]
    
    def get_sector_exposure(self) -> list[SectorExposure]:
        """Calculate sector exposure."""
        # Group by symbol (simplified - would need sector data)
        # This is a placeholder
        symbol_pnl = {}
        symbol_count = {}
        
        for t in self.trades:
            if t.symbol not in symbol_pnl:
                symbol_pnl[t.symbol] = 0
                symbol_count[t.symbol] = 0
            
            symbol_pnl[t.symbol] += t.pnl
            symbol_count[t.symbol] += 1
        
        total_pnl = sum(symbol_pnl.values())
        
        exposures = []
        for symbol, pnl in symbol_pnl.items():
            exposures.append(
                SectorExposure(
                    sector=symbol,  # Would map to sector
                    total_pnl=round(pnl, 2),
                    trade_count=symbol_count[symbol],
                    avg_position_size=0,  # Would calculate
                    exposure_pct=round(pnl / total_pnl * 100, 2) if total_pnl > 0 else 0
                )
            )
        
        return sorted(exposures, key=lambda x: x.exposure_pct, reverse=True)


class CorrelationAnalyzer:
    """Analyze position correlations."""
    
    @staticmethod
    def calculate_correlations(
        positions: list[PositionSummary]
    ) -> dict[tuple[str, str], float]:
        """
        Calculate correlation between position return series.
        
        Returns:
            Dict mapping (symbol1, symbol2) to correlation
        """
        if len(positions) < 2:
            return {}
        
        # Group by symbol
        symbol_returns = {}
        for pos in positions:
            if pos.symbol not in symbol_returns:
                symbol_returns[pos.symbol] = []
            symbol_returns[pos.symbol].append(pos.pnl_pct / 100)
        
        # Calculate correlations
        correlations = {}
        symbols = list(symbol_returns.keys())
        
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                s1, s2 = symbols[i], symbols[j]
                
                r1 = symbol_returns[s1]
                r2 = symbol_returns[s2]
                
                # Pad to same length
                max_len = max(len(r1), len(r2))
                r1 = r1 + [0] * (max_len - len(r1))
                r2 = r2 + [0] * (max_len - len(r2))
                
                corr = np.corrcoef(r1[:min(len(r1), len(r2))], 
                                 r2[:min(len(r1), len(r2))])[0, 1]
                
                correlations[(s1, s2)] = round(corr, 3) if not np.isnan(corr) else 0
        
        return correlations
    
    @staticmethod
    def get_high_correlation_pairs(
        correlations: dict[tuple[str, str], float],
        threshold: float = 0.5
    ) -> list[tuple[tuple[str, str], float]]:
        """
        Get highly correlated pairs.
        
        Args:
            correlations: Dict of correlations
            threshold: Correlation threshold
            
        Returns:
            List of (pair, correlation) tuples above threshold
        """
        return [
            (pair, corr)
            for pair, corr in correlations.items()
            if abs(corr) >= threshold
        ]


class RiskAnalyzer:
    """Analyze portfolio risk metrics."""
    
    @staticmethod
    def calculate_var(
        positions: list[PositionSummary],
        confidence: float = 0.95
    ) -> float:
        """
        Calculate Value at Risk.
        
        Args:
            positions: List of positions
            confidence: Confidence level (0.95 = 95%)
            
        Returns:
            VaR as percentage
        """
        if not positions:
            return 0
        
        returns = [pos.pnl_pct for pos in positions]
        
        if not returns:
            return 0
        
        # VaR = percentile of returns
        var = np.percentile(returns, (1 - confidence) * 100)
        
        return round(abs(var), 2)
    
    @staticmethod
    def calculate_cvar(
        positions: list[PositionSummary],
        confidence: float = 0.95
    ) -> float:
        """
        Calculate Conditional VaR (Expected Shortfall).
        
        Args:
            positions: List of positions
            confidence: Confidence level
            
        Returns:
            CVaR as percentage
        """
        if not positions:
            return 0
        
        returns = [pos.pnl_pct for pos in positions if pos.pnl_pct < 0]
        
        if not returns:
            return 0
        
        # CVaR = average of returns below VaR
        var = RiskAnalyzer.calculate_var(positions, confidence)
        
        cvar = np.mean([r for r in returns if r <= -var])
        
        return round(abs(cvar), 2)
    
    @staticmethod
    def calculate_beta(
        positions: list[PositionSummary],
        market_returns: list[float]
    ) -> dict[str, float]:
        """
        Calculate portfolio betas by symbol.
        
        Args:
            positions: List of positions
            market_returns: Market returns
            
        Returns:
            Dict mapping symbol to beta
        """
        if not positions or not market_returns:
            return {}
        
        # Group returns by symbol
        symbol_returns = {}
        for pos in positions:
            if pos.symbol not in symbol_returns:
                symbol_returns[pos.symbol] = []
            symbol_returns[pos.symbol].append(pos.pnl_pct / 100)
        
        betas = {}
        for symbol, returns in symbol_returns.items():
            if len(returns) < 2:
                continue
            
            # Pad to match market returns
            mkt = market_returns[:len(returns)]
            pos = returns
            
            if len(mkt) < 2:
                continue
            
            # Calculate beta
            covariance = np.cov(mkt, pos)[0, 1]
            variance = np.var(mkt)
            
            if variance > 0:
                betas[symbol] = round(covariance / variance, 2)
        
        return betas


class PortfolioMetricsService:
    """Service for portfolio-level backtest metrics."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_metrics(
        self,
        backtest_id: Optional[int] = None
    ) -> PortfolioMetrics:
        """
        Get portfolio metrics.
        
        Args:
            backtest_id: Optional backtest ID filter
            
        Returns:
            PortfolioMetrics
        """
        from domains.analytics.backtest import Backtest
        
        query = self.db.query(BacktestTrade)
        
        if backtest_id:
            query = query.filter(BacktestTrade.backtest_id == backtest_id)
        
        trades = query.all()
        
        analyzer = PortfolioAnalyzer(trades)
        return analyzer.calculate_metrics()
    
    def get_risk_report(
        self,
        backtest_id: Optional[int] = None
    ) -> dict:
        """
        Get comprehensive risk report.
        
        Args:
            backtest_id: Optional backtest ID filter
            
        Returns:
            Dict with risk metrics
        """
        query = self.db.query(BacktestTrade)
        
        if backtest_id:
            query = query.filter(BacktestTrade.backtest_id == backtest_id)
        
        trades = query.all()
        
        analyzer = PortfolioAnalyzer(trades)
        positions = analyzer.get_position_summaries()
        
        return {
            "portfolio": {
                "var_95": RiskAnalyzer.calculate_var(positions, 0.95),
                "var_99": RiskAnalyzer.calculate_var(positions, 0.99),
                "cvar_95": RiskAnalyzer.calculate_cvar(positions, 0.95),
                "cvar_99": RiskAnalyzer.calculate_cvar(positions, 0.99),
                "max_drawdown": analyzer.calculate_metrics().max_drawdown_pct,
                "volatility": analyzer.calculate_metrics().volatility
            },
            "correlation": CorrelationAnalyzer.get_high_correlation_pairs(
                CorrelationAnalyzer.calculate_correlations(positions)
            ),
            "exposure": [
                {
                    "sector": e.sector,
                    "exposure_pct": e.exposure_pct,
                    "total_pnl": e.total_pnl,
                    "trade_count": e.trade_count
                }
                for e in analyzer.get_sector_exposure()[:10]
            ]
        }
    
    def get_performance_report(
        self,
        backtest_id: Optional[int] = None
    ) -> dict:
        """
        Get performance report.
        
        Args:
            backtest_id: Optional backtest ID filter
            
        Returns:
            Dict with performance metrics
        """
        metrics = self.get_metrics(backtest_id)
        
        return {
            "summary": {
                "total_trades": metrics.total_trades,
                "win_rate": metrics.win_rate,
                "total_pnl": metrics.total_pnl,
                "total_pnl_pct": metrics.total_pnl_pct,
                "avg_win": metrics.avg_win,
                "avg_loss": metrics.avg_loss,
                "profit_factor": abs(metrics.avg_win / metrics.avg_loss) if metrics.avg_loss != 0 else 0
            },
            "risk_adjusted": {
                "sharpe_ratio": metrics.sharpe_ratio,
                "sortino_ratio": metrics.sortino_ratio,
                "max_drawdown_pct": metrics.max_drawdown_pct,
                "volatility": metrics.volatility
            },
            "timing": {
                "avg_trade_duration_hours": metrics.avg_trade_duration_hours,
                "longest_trade_hours": metrics.longest_trade_hours,
                "shortest_trade_hours": metrics.shortest_trade_hours,
                "avg_positions_per_day": metrics.avg_positions_per_day
            }
        }