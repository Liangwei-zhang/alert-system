from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domains.signals.strategy_profiles import normalize_strategy_name


@dataclass(frozen=True)
class CalibrationSnapshot:
    version: str
    strategy_weights: dict[str, float] = field(default_factory=dict)
    score_multipliers: dict[str, float] = field(default_factory=dict)
    source: str = "default"


class CalibrationService:
    DEFAULT_VERSION = "signals-v2-default"
    DEFAULT_STRATEGY_WEIGHTS = {
        "mean_reversion": 1.0,
        "trend_continuation": 1.0,
        "volatility_breakout": 1.0,
        "range_rotation": 1.0,
    }
    DEFAULT_SCORE_MULTIPLIERS = {
        "confidence": 1.0,
        "probability": 1.0,
        "risk_reward": 1.0,
        "quality": 1.0,
        "volume": 1.0,
        "trend": 1.0,
        "reversal": 1.0,
        "stale_penalty": 1.0,
        "liquidity_penalty": 1.0,
    }

    def current_snapshot(
        self,
        market_snapshot: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> CalibrationSnapshot:
        raw_snapshot = None
        if isinstance(context, dict) and isinstance(context.get("calibration_snapshot"), dict):
            raw_snapshot = context.get("calibration_snapshot")
        analysis = market_snapshot.get("analysis") if isinstance(market_snapshot, dict) and isinstance(market_snapshot.get("analysis"), dict) else None
        if raw_snapshot is None and isinstance(analysis, dict) and isinstance(analysis.get("calibration_snapshot"), dict):
            raw_snapshot = analysis.get("calibration_snapshot")

        return self.normalize_snapshot(raw_snapshot)

    def normalize_snapshot(self, raw_snapshot: dict[str, Any] | None) -> CalibrationSnapshot:
        if not isinstance(raw_snapshot, dict):
            return CalibrationSnapshot(
                version=self.DEFAULT_VERSION,
                strategy_weights=dict(self.DEFAULT_STRATEGY_WEIGHTS),
                score_multipliers=dict(self.DEFAULT_SCORE_MULTIPLIERS),
            )

        strategy_weights = dict(self.DEFAULT_STRATEGY_WEIGHTS)
        for name, value in dict(raw_snapshot.get("strategy_weights") or {}).items():
            numeric = self._coerce_float(value)
            if numeric is not None:
                strategy_weights[normalize_strategy_name(name)] = self._bounded_multiplier(numeric)

        score_multipliers = dict(self.DEFAULT_SCORE_MULTIPLIERS)
        for name, value in dict(raw_snapshot.get("score_multipliers") or {}).items():
            numeric = self._coerce_float(value)
            if numeric is not None:
                score_multipliers[str(name).strip()] = self._bounded_multiplier(numeric)

        version = str(raw_snapshot.get("version") or self.DEFAULT_VERSION).strip() or self.DEFAULT_VERSION
        source = str(raw_snapshot.get("source") or "snapshot").strip() or "snapshot"
        return CalibrationSnapshot(
            version=version,
            strategy_weights=strategy_weights,
            score_multipliers=score_multipliers,
            source=source,
        )

    @staticmethod
    def snapshot_payload(snapshot: CalibrationSnapshot) -> dict[str, Any]:
        return {
            "version": snapshot.version,
            "source": snapshot.source,
            "strategy_weights": dict(snapshot.strategy_weights),
            "score_multipliers": dict(snapshot.score_multipliers),
        }

    def strategy_weight(self, strategy: str, snapshot: CalibrationSnapshot) -> float:
        return self._bounded_multiplier(
            snapshot.strategy_weights.get(normalize_strategy_name(strategy), 1.0)
        )

    def score_multiplier(self, factor: str, snapshot: CalibrationSnapshot) -> float:
        return self._bounded_multiplier(snapshot.score_multipliers.get(str(factor).strip(), 1.0))

    @staticmethod
    def _bounded_multiplier(value: float) -> float:
        return max(0.75, min(1.25, float(value)))

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None