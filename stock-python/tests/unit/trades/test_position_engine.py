"""
Unit tests for Trades domain - position engine functionality.

Tested by: Watchlist Team
Original developer: Trades Team
"""
import pytest
from unittest.mock import patch, MagicMock

from apps.workers.scanner.position_engine import (
    PositionPlanStage,
    PositionSuggestion,
    _get_target_pct,
    _get_stage_weights,
    _get_stage_trigger,
    _split_into_stages,
    _calc_new_avg_cost,
    calc_position,
    clamp,
    normalize_pct,
    build_sell_stages,
    SellPlanStage,
    calc_sell_decision,
    PortfolioExtra,
    SellDecision,
)


class TestTargetPercentage:
    """Test target percentage calculation."""
    
    def test_target_pct_full_confirmation_high_score(self):
        """Test target percentage with full confirmation and high score."""
        result = _get_target_pct(score=95, confirmation_level='full')
        assert result == 0.2
    
    def test_target_pct_full_confirmation_mid_score(self):
        """Test target percentage with full confirmation and mid score."""
        result = _get_target_pct(score=85, confirmation_level='full')
        assert result == 0.15
    
    def test_target_pct_full_confirmation_low_score(self):
        """Test target percentage with full confirmation and low score."""
        result = _get_target_pct(score=65, confirmation_level='full')
        assert result == 0.05
    
    def test_target_pct_partial_confirmation(self):
        """Test target percentage with partial confirmation."""
        result = _get_target_pct(score=95, confirmation_level='partial')
        assert result == 0.16  # 0.2 * 0.8
    
    def test_target_pct_default_confirmation(self):
        """Test target percentage with default confirmation."""
        result = _get_target_pct(score=80)
        assert result == 0.15  # Default is 'full'


class TestStageWeights:
    """Test stage weight calculation."""
    
    def test_stage_weights_add(self):
        """Test stage weights for adding to position."""
        weights = _get_stage_weights(score=80, is_add=True)
        assert weights == [0.5, 0.3, 0.2]
    
    def test_stage_weights_buy_high_score(self):
        """Test stage weights for new buy with high score."""
        weights = _get_stage_weights(score=95, is_add=False)
        assert weights == [0.45, 0.35, 0.2]
    
    def test_stage_weights_buy_mid_score(self):
        """Test stage weights for new buy with mid score."""
        weights = _get_stage_weights(score=80, is_add=False)
        assert weights == [0.4, 0.35, 0.25]
    
    def test_stage_weights_buy_low_score(self):
        """Test stage weights for new buy with low score."""
        weights = _get_stage_weights(score=60, is_add=False)
        assert weights == [0.4, 0.3, 0.3]


class TestStageTriggers:
    """Test stage trigger messages."""
    
    def test_stage_trigger_add_first(self):
        """Test add trigger for first stage."""
        trigger = _get_stage_trigger(index=0, is_add=True)
        assert "Add" in trigger
    
    def test_stage_trigger_add_second(self):
        """Test add trigger for second stage."""
        trigger = _get_stage_trigger(index=1, is_add=True)
        assert "add" in trigger.lower()
    
    def test_stage_trigger_buy_first(self):
        """Test buy trigger for first stage."""
        trigger = _get_stage_trigger(index=0, is_add=False)
        assert "Open" in trigger or "Starter" in trigger
    
    def test_stage_trigger_invalid_index(self):
        """Test trigger for invalid index."""
        trigger = _get_stage_trigger(index=10, is_add=False)
        assert "valid" in trigger.lower()


class TestSplitIntoStages:
    """Test position splitting into stages."""
    
    def test_split_into_stages_basic(self):
        """Test basic stage splitting."""
        stages = _split_into_stages(
            total_amount=1000.0,
            total_pct=0.1,
            current_price=50.0,
            score=80,
            is_add=False,
        )
        
        assert len(stages) == 3
        assert all(isinstance(s, PositionPlanStage) for s in stages)
    
    def test_split_into_stages_shares_calculated(self):
        """Test that shares are calculated correctly."""
        stages = _split_into_stages(
            total_amount=1000.0,
            total_pct=0.1,
            current_price=50.0,
            score=80,
            is_add=False,
        )
        
        # Total shares should be approximately 1000/50 = 20
        total_shares = sum(s.suggested_shares for s in stages)
        assert total_shares > 0
    
    def test_split_into_stages_add_mode(self):
        """Test stage splitting in add mode."""
        stages = _split_into_stages(
            total_amount=500.0,
            total_pct=0.05,
            current_price=25.0,
            score=70,
            is_add=True,
        )
        
        assert len(stages) == 3


class TestPositionCalculation:
    """Test main calc_position function."""
    
    def test_calc_position_new_buy_high_score(self):
        """Test position calculation for new buy with high score."""
        suggestion = calc_position(
            total_capital=10000.0,
            available_cash=10000.0,
            current_price=50.0,
            score=95,
            existing_shares=0,
            existing_avg_cost=0.0,
            confirmation_level='full',
        )
        
        assert suggestion is not None
        assert suggestion.action == 'buy'
        assert suggestion.suggested_shares > 0
        assert suggestion.target_pct > 0
    
    def test_calc_position_add_to_position(self):
        """Test position calculation for adding to existing."""
        suggestion = calc_position(
            total_capital=10000.0,
            available_cash=5000.0,
            current_price=50.0,
            score=80,
            existing_shares=100,
            existing_avg_cost=45.0,
            confirmation_level='full',
        )
        
        assert suggestion is not None
        assert suggestion.action == 'add'
    
    def test_calc_position_partial_confirmation(self):
        """Test position calculation with partial confirmation."""
        suggestion = calc_position(
            total_capital=10000.0,
            available_cash=10000.0,
            current_price=50.0,
            score=90,
            existing_shares=0,
            existing_avg_cost=0.0,
            confirmation_level='partial',
        )
        
        assert suggestion is not None
        # Partial should have reduced target percentage
        assert suggestion.target_pct < 0.2
    
    def test_calc_position_low_cash(self):
        """Test position calculation with insufficient cash."""
        suggestion = calc_position(
            total_capital=10000.0,
            available_cash=100.0,  # Very low
            current_price=50.0,
            score=85,
            existing_shares=0,
            existing_avg_cost=0.0,
            confirmation_level='full',
        )
        
        # Should still return suggestion if cash available
        # but may be 0 shares if amount too low
        assert suggestion is not None
    
    def test_calc_position_no_cash(self):
        """Test position calculation with no available cash."""
        suggestion = calc_position(
            total_capital=10000.0,
            available_cash=0.0,
            current_price=50.0,
            score=85,
            existing_shares=0,
            existing_avg_cost=0.0,
            confirmation_level='full',
        )
        
        # Returns suggestion with 0 shares when no cash
        assert suggestion is not None
        assert suggestion.suggested_shares == 0


class TestHelperFunctions:
    """Test utility helper functions."""
    
    def test_clamp_within_bounds(self):
        """Test clamp within bounds."""
        assert clamp(5.0, 0.0, 10.0) == 5.0
    
    def test_clamp_below_min(self):
        """Test clamp below minimum."""
        assert clamp(-5.0, 0.0, 10.0) == 0.0
    
    def test_clamp_above_max(self):
        """Test clamp above maximum."""
        assert clamp(15.0, 0.0, 10.0) == 10.0
    
    def test_normalize_pct_valid(self):
        """Test percentage normalization."""
        assert normalize_pct(0.5) == 0.5
    
    def test_normalize_pct_negative(self):
        """Test percentage normalization with negative."""
        assert normalize_pct(-0.1) == 0.0
    
    def test_normalize_pct_over_100(self):
        """Test percentage normalization over 100%."""
        assert normalize_pct(1.5) == 1.0


class TestSellStages:
    """Test sell stage building."""
    
    def test_build_sell_stages_basic(self):
        """Test basic sell stage building."""
        stages = build_sell_stages(target_profit=0.15)
        
        assert len(stages) > 0
        assert all(isinstance(s, SellPlanStage) for s in stages)
    
    def test_build_sell_stages_labels(self):
        """Test sell stage labels."""
        stages = build_sell_stages(target_profit=0.15)
        
        labels = [s.label for s in stages]
        assert all("sell" in label.lower() or "take" in label.lower() for label in labels)


class TestSellDecision:
    """Test sell decision calculation."""
    
    def test_calc_sell_decision_profitable(self):
        """Test sell decision for profitable position."""
        decision = calc_sell_decision(
            shares=100,
            avg_cost=100.0,
            current_price=120.0,
            target_profit=0.15,
            stop_loss=0.05,
            portfolio_extra=None,
        )
        
        assert isinstance(decision, SellDecision)
        assert decision.action in ['sell', 'hold', 'trim']
    
    def test_calc_sell_decision_at_loss(self):
        """Test sell decision for position at loss."""
        decision = calc_sell_decision(
            shares=100,
            avg_cost=100.0,
            current_price=90.0,
            target_profit=0.15,
            stop_loss=0.05,
            portfolio_extra=None,
        )
        
        assert isinstance(decision, SellDecision)
        # At loss but above stop loss - might hold or wait
        assert decision.action in ['hold', 'wait', 'sell', 'trim']
    
    def test_calc_sell_decision_stop_loss_triggered(self):
        """Test sell decision when stop loss is triggered."""
        decision = calc_sell_decision(
            shares=100,
            avg_cost=100.0,
            current_price=94.0,  # Below 95 (5% stop loss)
            target_profit=0.15,
            stop_loss=0.05,
            portfolio_extra=None,
        )
        
        assert isinstance(decision, SellDecision)
        # Stop loss triggered - should recommend selling
        assert decision.action in ['sell', 'stop_loss']
    
    def test_calc_sell_decision_target_reached(self):
        """Test sell decision when target is reached."""
        decision = calc_sell_decision(
            shares=100,
            avg_cost=100.0,
            current_price=120.0,  # 20% profit - above 15% target
            target_profit=0.15,
            stop_loss=0.05,
            portfolio_extra=None,
        )
        
        assert isinstance(decision, SellDecision)
        # Target reached - should recommend selling
        assert decision.action in ['sell', 'take_profit', 'trim']
