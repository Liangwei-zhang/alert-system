"""
Position sizing engine.

Keeps the original single-action suggestion fields for compatibility,
while also producing a staged buy plan that can be shown in emails/UI.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class PositionPlanStage:
    """Single stage in a staged buy/sell plan."""
    id: str
    label: str
    target_pct: float
    suggested_shares: int
    suggested_amount: float
    trigger: str


@dataclass
class PositionSuggestion:
    """Position sizing suggestion."""
    action: str  # 'buy' or 'add'
    suggested_shares: int
    suggested_price: float
    suggested_amount: float
    target_pct: float
    notes: str
    plan: list[PositionPlanStage]


def _get_target_pct(score: int, confirmation_level: str = 'full') -> float:
    """Get target percentage of capital based on score."""
    multiplier = 0.8 if confirmation_level == 'partial' else 1.0

    if score >= 90:
        return 0.2 * multiplier
    if score >= 80:
        return 0.15 * multiplier
    if score >= 70:
        return 0.1 * multiplier
    return 0.05 * multiplier


def _get_stage_weights(score: int, is_add: bool) -> list[float]:
    """Get stage weights for splitting buy into multiple tranches."""
    if is_add:
        return [0.5, 0.3, 0.2]
    if score >= 90:
        return [0.45, 0.35, 0.2]
    if score >= 80:
        return [0.4, 0.35, 0.25]
    return [0.4, 0.3, 0.3]


def _get_stage_trigger(index: int, is_add: bool) -> str:
    """Get trigger description for each stage."""
    if is_add:
        triggers = [
            'Add on this signal to improve cost basis and rebuild exposure.',
            'Only add the second tranche if the trend confirms or support holds.',
            'Use the final tranche only if momentum is still healthy and cash remains.',
        ]
    else:
        triggers = [
            'Open a starter position on the current signal.',
            'Deploy the second tranche on a controlled pullback or strong follow-through.',
            'Finish the final tranche only after the move confirms.',
        ]
    return triggers[index] if index < len(triggers) else 'Buy only while the setup remains valid.'


def _split_into_stages(
    total_amount: float,
    total_pct: float,
    current_price: float,
    score: int,
    is_add: bool,
) -> list[PositionPlanStage]:
    """Split a position into multiple stages."""
    weights = _get_stage_weights(score, is_add)
    remaining_amount = total_amount
    remaining_pct = total_pct
    stages = []

    for index, weight in enumerate(weights):
        is_last = index == len(weights) - 1
        stage_amount = remaining_amount if is_last else total_amount * weight
        stage_pct = remaining_pct if is_last else total_pct * weight
        
        shares = int(stage_amount / current_price)
        suggested_amount = round(shares * current_price, 2)

        remaining_amount -= stage_amount
        remaining_pct -= stage_pct

        stages.append(PositionPlanStage(
            id=f'buy_stage_{index + 1}',
            label=f'Batch {index + 1}',
            target_pct=round(stage_pct * 100, 1),
            suggested_shares=shares,
            suggested_amount=suggested_amount,
            trigger=_get_stage_trigger(index, is_add),
        ))

    return [s for s in stages if s.suggested_shares > 0]


def _calc_new_avg_cost(
    old_shares: int,
    old_avg_cost: float,
    add_shares: int,
    add_price: float,
) -> float:
    """Calculate new average cost after adding to position."""
    total = old_shares + add_shares
    if total == 0:
        return 0
    return (old_shares * old_avg_cost + add_shares * add_price) / total


def calc_position(
    total_capital: float,
    available_cash: float,
    current_price: float,
    score: int,
    existing_shares: int = 0,
    existing_avg_cost: float = 0,
    confirmation_level: str = 'full',
) -> Optional[PositionSuggestion]:
    """
    Calculate position sizing for a buy signal.
    
    Args:
        total_capital: Total capital available
        available_cash: Available cash for trading
        current_price: Current stock price
        score: Buy signal score (0-100)
        existing_shares: Existing position size
        existing_avg_cost: Existing position average cost
        confirmation_level: 'full' or 'partial'
    
    Returns:
        PositionSuggestion if position is viable, None otherwise
    """
    if current_price <= 0:
        return None

    is_add = existing_shares > 0
    action = 'add' if is_add else 'buy'
    target_amount = total_capital * _get_target_pct(score, confirmation_level)

    # Cash buffer to keep for emergencies
    cash_buffer = total_capital * (0.05 if score >= 90 else 0.1)
    spendable = available_cash - cash_buffer
    if spendable <= 0:
        return None

    # Maximum 30% in single position
    max_single_position = total_capital * 0.3
    existing_value = existing_shares * existing_avg_cost
    remain_allowed = max_single_position - existing_value
    if remain_allowed <= 0:
        return None

    # Apply all constraints
    target_amount = min(target_amount, spendable, remain_allowed)
    if target_amount < current_price:
        return None

    # Build staged plan
    plan = _split_into_stages(
        target_amount,
        target_amount / total_capital,
        current_price,
        score,
        is_add,
    )
    if not plan:
        return None

    first_stage = plan[0]
    
    if is_add:
        new_avg_cost = _calc_new_avg_cost(
            existing_shares, existing_avg_cost,
            first_stage.suggested_shares, current_price
        )
        notes = (
            f"Add {first_stage.suggested_shares} shares now, then complete "
            f"{len(plan)} staged entries if the setup holds. "
            f"New estimated average cost: ${new_avg_cost:.2f}"
        )
    else:
        notes = (
            f"Buy {first_stage.suggested_shares} shares now as the starter entry, "
            f"then follow the remaining {len(plan) - 1} staged buy steps only "
            f"if the setup stays valid."
        )

    return PositionSuggestion(
        action=action,
        suggested_shares=first_stage.suggested_shares,
        suggested_price=current_price,
        suggested_amount=first_stage.suggested_amount,
        target_pct=round((target_amount / total_capital) * 100, 1),
        notes=notes,
        plan=plan,
    )


# Sell-side position management functions

def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))


def normalize_pct(value: float) -> float:
    """Normalize percentage to 1 decimal place."""
    return round(value * 100, 1)


@dataclass
class SellPlanStage:
    """Single stage in a staged sell plan."""
    id: str
    label: str
    trigger_pct: float
    sell_pct: float


def build_sell_stages(target_profit: float) -> list[SellPlanStage]:
    """Build default sell stages based on target profit."""
    stage1 = clamp(target_profit, 0.05, 0.2)
    stage2 = clamp(max(target_profit * 1.45, target_profit + 0.08), stage1 + 0.03, 0.35)
    stage3 = clamp(max(target_profit * 2, target_profit + 0.18), stage2 + 0.04, 0.5)

    return [
        SellPlanStage(id='tp1', label='Batch 1', trigger_pct=stage1, sell_pct=0.25),
        SellPlanStage(id='tp2', label='Batch 2', trigger_pct=stage2, sell_pct=0.35),
        SellPlanStage(id='tp3', label='Batch 3', trigger_pct=stage3, sell_pct=0.4),
    ]


@dataclass
class SellDecision:
    """Sell decision based on profit/loss and stages."""
    sell_pct: float
    reason: str
    stage_id: Optional[str] = None
    stages: list[SellPlanStage] = None
    stop_loss_pct: float = 0.02

    def __post_init__(self):
        if self.stages is None:
            self.stages = []


@dataclass
class PortfolioExtra:
    """Parsed portfolio extra data."""
    sell_plan_base_shares: int
    sell_plan_stages: list[SellPlanStage]
    sell_progress_completed_stage_ids: list[str]


def parse_portfolio_extra(
    extra: dict,
    shares: int,
    target_profit: float,
) -> PortfolioExtra:
    """Parse portfolio extra field for sell plan info."""
    if not extra:
        extra = {}

    stored_stages = []
    if isinstance(extra.get('sell_plan', {}).get('stages'), list):
        stored_stages = [s for s in extra['sell_plan']['stages'] if s]

    stages = stored_stages if stored_stages else build_sell_stages(target_profit)
    
    base_shares = extra.get('sell_plan', {}).get('baseShares', 0)
    base_shares = base_shares if base_shares >= shares else shares

    completed_stage_ids = []
    if isinstance(extra.get('sell_progress', {}).get('completedStageIds'), list):
        completed_stage_ids = [s for s in extra['sell_progress']['completedStageIds'] if s]

    return PortfolioExtra(
        sell_plan_base_shares=base_shares,
        sell_plan_stages=stages,
        sell_progress_completed_stage_ids=completed_stage_ids,
    )


def calc_sell_decision(
    shares: int,
    avg_cost: float,
    current_price: float,
    target_profit: float,
    stop_loss: float,
    smc_top_probability: float,
    extra: PortfolioExtra,
) -> Optional[SellDecision]:
    """Calculate whether to sell and how much."""
    if avg_cost <= 0:
        return None

    pnl_pct = (current_price - avg_cost) / avg_cost
    stop_loss_pct = stop_loss

    # Stop loss triggered
    if pnl_pct <= -stop_loss_pct:
        return SellDecision(
            sell_pct=1.0,
            reason=f"Stop loss triggered at {normalize_pct(pnl_pct)}% vs {normalize_pct(stop_loss_pct)}% limit.",
            stages=extra.sell_plan_stages or build_sell_stages(target_profit),
            stop_loss_pct=stop_loss_pct,
        )

    stages = extra.sell_plan_stages or build_sell_stages(target_profit)
    completed = set(extra.sell_progress_completed_stage_ids)
    pending_stages = [s for s in stages if s.id not in completed]
    
    if not pending_stages:
        return None

    # Check for triggered take profit stage
    for stage in pending_stages:
        if pnl_pct >= stage.trigger_pct:
            return SellDecision(
                sell_pct=stage.sell_pct,
                stage_id=stage.id,
                reason=f"{stage.label} triggered at {normalize_pct(pnl_pct)}% profit. Planned trim: {normalize_pct(stage.sell_pct)}% of the original position.",
                stages=stages,
                stop_loss_pct=stop_loss_pct,
            )

    # SMC top probability high - advance next stage early
    if smc_top_probability >= 0.85 and pnl_pct > 0:
        next_stage = pending_stages[0]
        return SellDecision(
            sell_pct=next_stage.sell_pct,
            stage_id=next_stage.id,
            reason=f"Top reversal probability is {int(smc_top_probability * 100)}%, so the next staged trim is being advanced early.",
            stages=stages,
            stop_loss_pct=stop_loss_pct,
        )

    return None