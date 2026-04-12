from __future__ import annotations

from typing import Any, Callable

STRATEGY_RANKING_ALIASES = {
    "momentum": "trend_continuation",
    "momentum_alpha": "trend_continuation",
    "momentum-alpha": "trend_continuation",
    "trend_following": "trend_continuation",
    "trend-following": "trend_continuation",
    "trend_follow": "trend_continuation",
    "trend-follow": "trend_continuation",
    "sma_cross": "trend_continuation",
    "sma-cross": "trend_continuation",
    "buy_and_hold": "trend_continuation",
    "buy-and-hold": "trend_continuation",
    "breakout": "volatility_breakout",
    "volatility_breakout": "volatility_breakout",
    "volatility-breakout": "volatility_breakout",
    "mean_reversion": "mean_reversion",
    "mean-reversion": "mean_reversion",
    "rsi_reversion": "mean_reversion",
    "rsi-reversion": "mean_reversion",
    "bollinger_reversion": "mean_reversion",
    "bollinger-reversion": "mean_reversion",
    "range_rotation": "range_rotation",
    "range-rotation": "range_rotation",
}


def normalize_strategy_name(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def resolve_strategy_name(value: Any) -> str | None:
    normalized = normalize_strategy_name(value)
    return STRATEGY_RANKING_ALIASES.get(normalized)


def select_heuristic_strategy(
    market_snapshot: dict[str, Any],
    *,
    coerce_float: Callable[[Any], float | None],
) -> str:
    dislocation = abs(coerce_float(market_snapshot.get("dislocation_pct")) or 0.0)
    momentum = coerce_float(market_snapshot.get("momentum_score")) or 0.0
    volatility = coerce_float(market_snapshot.get("volatility_score")) or 0.0

    if dislocation >= 0.03:
        return "mean_reversion"
    if momentum >= 0.65:
        return "trend_continuation"
    if volatility >= 0.75:
        return "volatility_breakout"
    return "range_rotation"


def strategy_fit_score(
    strategy: str,
    market_snapshot: dict[str, Any],
    *,
    coerce_float: Callable[[Any], float | None],
    truthy: Callable[[Any], bool],
    normalize_percentage: Callable[[Any], float | None],
) -> float:
    analysis = market_snapshot.get("analysis") if isinstance(market_snapshot.get("analysis"), dict) else {}
    dislocation = min(1.0, abs(coerce_float(market_snapshot.get("dislocation_pct")) or 0.0) / 0.08)
    momentum = min(1.0, abs(coerce_float(market_snapshot.get("momentum_score")) or 0.0))
    trend = min(1.0, abs(coerce_float(market_snapshot.get("trend_strength")) or 0.0))
    volatility = min(1.0, abs(coerce_float(market_snapshot.get("volatility_score")) or 0.0))
    volume_confirmed = truthy(analysis.get("volume_confirmed"))
    trend_confirmed = truthy(analysis.get("trend_confirmed"))
    reversal_confirmed = truthy(analysis.get("reversal_confirmed"))
    setup_quality = (normalize_percentage(analysis.get("setup_quality")) or 0.0) / 100.0
    low_trend = max(0.0, 1.0 - trend)
    low_volatility = max(0.0, 1.0 - volatility)

    if strategy == "mean_reversion":
        return (
            (dislocation * 14.0)
            + (6.0 if reversal_confirmed else 0.0)
            + (low_trend * 4.0)
            + (low_volatility * 2.0)
            + (setup_quality * 3.0)
        )
    if strategy == "trend_continuation":
        return (
            (trend * 11.0)
            + (momentum * 9.0)
            + (5.0 if trend_confirmed else 0.0)
            + (4.0 if volume_confirmed else 0.0)
            + (setup_quality * 2.5)
        )
    if strategy == "volatility_breakout":
        return (
            (volatility * 11.0)
            + (momentum * 5.0)
            + (6.0 if volume_confirmed else 0.0)
            + (4.0 if trend_confirmed else 0.0)
            + (setup_quality * 2.0)
        )
    return (
        (low_trend * 8.0)
        + (low_volatility * 6.0)
        + (dislocation * 4.0)
        + (3.0 if reversal_confirmed else 0.0)
        + (setup_quality * 2.0)
    )


def regime_bias(strategy: str, market_regime: str) -> float:
    if market_regime == "trend":
        if strategy == "trend_continuation":
            return 8.0
        if strategy == "volatility_breakout":
            return 4.0
        if strategy == "mean_reversion":
            return -3.0
        if strategy == "range_rotation":
            return -2.0
    if market_regime == "volatile":
        if strategy == "volatility_breakout":
            return 8.0
        if strategy == "mean_reversion":
            return 3.0
        if strategy == "trend_continuation":
            return -2.0
        if strategy == "range_rotation":
            return -1.0
    if market_regime == "range":
        if strategy == "range_rotation":
            return 8.0
        if strategy == "mean_reversion":
            return 6.0
        if strategy == "trend_continuation":
            return -4.0
        if strategy == "volatility_breakout":
            return -1.0
    return 0.0