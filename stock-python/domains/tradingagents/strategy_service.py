"""
Strategy service for trading strategy management.
"""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from domains.tradingagents.strategy import (
    Strategy, StrategyType, StrategyStatus, 
    StrategySignalConfig
)
from domains.signals.signal import Signal, SignalType, SignalStatus


class StrategyService:
    """Service layer for strategy management."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_strategy(
        self,
        name: str,
        strategy_type: StrategyType,
        description: Optional[str] = None,
        **config
    ) -> Strategy:
        """Create a new trading strategy."""
        strategy = Strategy(
            name=name,
            description=description,
            strategy_type=strategy_type,
            use_sfp=config.get("use_sfp", True),
            use_chooch=config.get("use_chooch", True),
            use_fvg=config.get("use_fvg", True),
            default_risk_percent=config.get("default_risk_percent", 1.0),
            max_position_size=config.get("max_position_size", 10.0),
            default_atr_multiplier=config.get("default_atr_multiplier", 2.0),
            min_probability=config.get("min_probability", 0.5),
            min_confidence=config.get("min_confidence", 50.0),
            min_risk_reward=config.get("min_risk_reward", 1.5),
            tp1_percent=config.get("tp1_percent", 1.0),
            tp2_percent=config.get("tp2_percent", 2.0),
            tp3_percent=config.get("tp3_percent", 3.0),
            partial_tp_percent=config.get("partial_tp_percent", 50.0),
            symbols=json.dumps(config.get("symbols", [])),
            timeframes=json.dumps(config.get("timeframes", ["1h", "4h", "1d"]))
        )
        
        self.db.add(strategy)
        self.db.commit()
        self.db.refresh(strategy)
        
        return strategy
    
    def get_strategy_by_id(self, strategy_id: int) -> Optional[Strategy]:
        """Get strategy by ID."""
        return self.db.query(Strategy).filter(Strategy.id == strategy_id).first()
    
    def get_strategy_by_name(self, name: str) -> Optional[Strategy]:
        """Get strategy by name."""
        return self.db.query(Strategy).filter(Strategy.name == name).first()
    
    def get_active_strategies(self) -> list[Strategy]:
        """Get all active strategies."""
        return self.db.query(Strategy).filter(
            Strategy.status == StrategyStatus.ACTIVE
        ).all()
    
    def update_strategy(
        self, 
        strategy_id: int, 
        **updates
    ) -> Optional[Strategy]:
        """Update strategy configuration."""
        strategy = self.get_strategy_by_id(strategy_id)
        if not strategy:
            return None
        
        for key, value in updates.items():
            if hasattr(strategy, key):
                # Handle JSON fields
                if key in ["symbols", "timeframes"] and isinstance(value, list):
                    setattr(strategy, key, json.dumps(value))
                else:
                    setattr(strategy, key, value)
        
        strategy.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(strategy)
        
        return strategy
    
    def pause_strategy(self, strategy_id: int) -> Optional[Strategy]:
        """Pause a strategy."""
        return self.update_strategy(
            strategy_id, status=StrategyStatus.PAUSED
        )
    
    def resume_strategy(self, strategy_id: int) -> Optional[Strategy]:
        """Resume a paused strategy."""
        return self.update_strategy(
            strategy_id, status=StrategyStatus.ACTIVE
        )
    
    def archive_strategy(self, strategy_id: int) -> Optional[Strategy]:
        """Archive a strategy."""
        return self.update_strategy(
            strategy_id, status=StrategyStatus.ARCHIVED
        )
    
    def delete_strategy(self, strategy_id: int) -> bool:
        """Delete a strategy."""
        strategy = self.get_strategy_by_id(strategy_id)
        if strategy:
            self.db.delete(strategy)
            self.db.commit()
            return True
        return False
    
    def get_strategy_config(
        self, 
        strategy_id: int
    ) -> Optional[StrategySignalConfig]:
        """Get signal config for a strategy."""
        return self.db.query(StrategySignalConfig).filter(
            StrategySignalConfig.strategy_id == strategy_id
        ).first()
    
    def create_strategy_config(
        self,
        strategy_id: int,
        **config
    ) -> StrategySignalConfig:
        """Create signal config for a strategy."""
        strategy_config = StrategySignalConfig(
            strategy_id=strategy_id,
            signal_type_filter=config.get("signal_type_filter"),
            sfp_weight=config.get("sfp_weight", 0.3),
            chooch_weight=config.get("chooch_weight", 0.4),
            fvg_weight=config.get("fvg_weight", 0.3),
            atr_period=config.get("atr_period", 14),
            atr_multiplier_stop=config.get("atr_multiplier_stop", 2.0),
            atr_multiplier_target=config.get("atr_multiplier_target", 3.0),
            min_volume=config.get("min_volume"),
            min_price=config.get("min_price"),
            max_price=config.get("max_price")
        )
        
        self.db.add(strategy_config)
        self.db.commit()
        self.db.refresh(strategy_config)
        
        return strategy_config
    
    def filter_signal_by_strategy(
        self,
        signal: Signal,
        strategy: Strategy
    ) -> bool:
        """
        Check if a signal meets strategy criteria.
        
        Returns True if signal passes all filters.
        """
        # Check signal type filter
        if strategy.symbols:
            symbols = json.loads(strategy.symbols)
            if symbols and signal.symbol not in symbols:
                return False
        
        # Check probability threshold
        if signal.probability < strategy.min_probability:
            return False
        
        # Check confidence threshold
        if signal.confidence < strategy.min_confidence:
            return False
        
        # Check risk-reward ratio
        if signal.risk_reward_ratio and signal.risk_reward_ratio < strategy.min_risk_reward:
            return False
        
        # Check validation layers
        if strategy.use_sfp and not signal.sfp_validated:
            return False
        if strategy.use_chooch and not signal.chooch_validated:
            return False
        if strategy.use_fvg and not signal.fvg_validated:
            return False
        
        return True
    
    def calculate_position_size(
        self,
        strategy: Strategy,
        account_balance: float,
        entry_price: float,
        stop_loss: float
    ) -> dict:
        """Calculate position size based on risk management rules."""
        if entry_price == 0 or stop_loss == entry_price:
            return {"shares": 0, "total_value": 0}
        
        # Calculate risk amount
        risk_amount = account_balance * (strategy.default_risk_percent / 100)
        
        # Calculate stop loss distance
        sl_distance = abs(entry_price - stop_loss)
        
        if sl_distance == 0:
            return {"shares": 0, "total_value": 0}
        
        # Calculate shares
        shares = int(risk_amount / sl_distance)
        
        # Apply max position size limit
        max_shares = int((account_balance * (strategy.max_position_size / 100)) / entry_price)
        shares = min(shares, max_shares)
        
        total_value = shares * entry_price
        
        return {
            "shares": shares,
            "total_value": round(total_value, 2),
            "risk_amount": round(risk_amount, 2),
            "risk_percent": strategy.default_risk_percent
        }
    
    def calculate_take_profit_levels(
        self,
        strategy: Strategy,
        entry_price: float,
        stop_loss: float,
        direction: str
    ) -> dict:
        """Calculate take profit levels based on strategy."""
        risk = abs(entry_price - stop_loss)
        
        if direction.lower() == "bullish":
            return {
                "tp1": round(entry_price + (risk * strategy.tp1_percent), 4),
                "tp2": round(entry_price + (risk * strategy.tp2_percent), 4),
                "tp3": round(entry_price + (risk * strategy.tp3_percent), 4),
                "partial_tp_percent": strategy.partial_tp_percent
            }
        else:
            return {
                "tp1": round(entry_price - (risk * strategy.tp1_percent), 4),
                "tp2": round(entry_price - (risk * strategy.tp2_percent), 4),
                "tp3": round(entry_price - (risk * strategy.tp3_percent), 4),
                "partial_tp_percent": strategy.partial_tp_percent
            }
    
    def get_strategy_performance(
        self, 
        strategy_id: int
    ) -> dict:
        """Get performance metrics for a strategy."""
        strategy = self.get_strategy_by_id(strategy_id)
        if not strategy:
            return None
        
        total = strategy.winning_trades + strategy.losing_trades
        win_rate = (strategy.winning_trades / total * 100) if total > 0 else 0
        avg_pnl = (strategy.total_pnl / total) if total > 0 else 0
        
        return {
            "strategy_id": strategy_id,
            "name": strategy.name,
            "total_trades": total,
            "winning_trades": strategy.winning_trades,
            "losing_trades": strategy.losing_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(float(strategy.total_pnl), 2),
            "average_pnl": round(avg_pnl, 2)
        }
    
    def update_strategy_stats(
        self,
        strategy_id: int,
        is_win: bool,
        pnl: float
    ) -> Optional[Strategy]:
        """Update strategy performance stats after trade."""
        strategy = self.get_strategy_by_id(strategy_id)
        if not strategy:
            return None
        
        strategy.total_signals += 1
        if is_win:
            strategy.winning_trades += 1
        else:
            strategy.losing_trades += 1
        strategy.total_pnl += pnl
        
        self.db.commit()
        self.db.refresh(strategy)
        
        return strategy


class StrategyRunner:
    """Runner for executing strategies against market data."""
    
    def __init__(self, db: Session):
        self.db = db
        self.service = StrategyService(db)
    
    def run_strategy(
        self,
        strategy_id: int,
        stock_symbol: str,
        high: list,
        low: list,
        close: list,
        volume: list
    ) -> Optional[Signal]:
        """
        Run a strategy against OHLCV data.
        
        Returns a Signal if strategy criteria are met.
        """
        from domains.signals.signal_service import SignalService
        
        strategy = self.service.get_strategy_by_id(strategy_id)
        if not strategy or strategy.status != StrategyStatus.ACTIVE:
            return None
        
        # Get stock
        from domains.search.stock import Stock
        stock = self.db.query(Stock).filter(Stock.symbol == stock_symbol.upper()).first()
        if not stock:
            return None
        
        # Generate signal
        signal_service = SignalService(self.db)
        signal = signal_service.create_signal_from_ohlcv(
            stock, high, low, close, volume, strategy_id
        )
        
        if signal:
            # Filter by strategy criteria
            if not self.service.filter_signal_by_strategy(signal, strategy):
                # Signal doesn't meet criteria, cancel it
                signal_service.cancel_signal(signal.id)
                return None
        
        return signal
    
    def run_all_active_strategies(
        self,
        stock_symbol: str,
        high: list,
        low: list,
        close: list,
        volume: list
    ) -> list[Signal]:
        """Run all active strategies against data."""
        signals = []
        strategies = self.service.get_active_strategies()
        
        for strategy in strategies:
            signal = self.run_strategy(
                strategy.id, stock_symbol, high, low, close, volume
            )
            if signal:
                signals.append(signal)
        
        return signals
