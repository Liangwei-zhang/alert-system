from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from domains.signals.market_regime import MarketRegimeDetector
from domains.signals.strategy_profiles import normalize_strategy_name


@dataclass(frozen=True)
class CalibrationSnapshot:
    version: str
    strategy_weights: dict[str, float] = field(default_factory=dict)
    score_multipliers: dict[str, float] = field(default_factory=dict)
    atr_multipliers: dict[str, float] = field(default_factory=dict)
    source: str = "default"
    effective_from: datetime | None = None

    @property
    def effective_at(self) -> datetime | None:
        return self.effective_from


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
    DEFAULT_ATR_MULTIPLIERS = {
        "trend": 2.2,
        "trend_up": 2.15,
        "trend_down": 2.35,
        "trend_strong_up": 2.45,
        "trend_strong_down": 2.6,
        "volatile": 2.8,
        "volatile_breakout": 3.0,
        "volatile_reversal": 2.65,
        "breakout_candidate": 2.9,
        "range": 1.8,
        "range_tight": 1.55,
        "range_balanced": 1.8,
        "range_wide": 2.05,
    }

    def current_snapshot(
        self,
        market_snapshot: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> CalibrationSnapshot:
        raw_snapshot = None
        if isinstance(context, dict) and isinstance(context.get("calibration_snapshot"), dict):
            raw_snapshot = context.get("calibration_snapshot")
        analysis = (
            market_snapshot.get("analysis")
            if isinstance(market_snapshot, dict)
            and isinstance(market_snapshot.get("analysis"), dict)
            else None
        )
        if raw_snapshot is None and isinstance(analysis, dict) and isinstance(
            analysis.get("calibration_snapshot"), dict
        ):
            raw_snapshot = analysis.get("calibration_snapshot")

        return self.normalize_snapshot(raw_snapshot)

    def normalize_snapshot(self, raw_snapshot: dict[str, Any] | None) -> CalibrationSnapshot:
        if not isinstance(raw_snapshot, dict):
            return CalibrationSnapshot(
                version=self.DEFAULT_VERSION,
                strategy_weights=dict(self.DEFAULT_STRATEGY_WEIGHTS),
                score_multipliers=dict(self.DEFAULT_SCORE_MULTIPLIERS),
                atr_multipliers=dict(self.DEFAULT_ATR_MULTIPLIERS),
            )

        strategy_weights = dict(self.DEFAULT_STRATEGY_WEIGHTS)
        for name, value in dict(raw_snapshot.get("strategy_weights") or {}).items():
            numeric = self._coerce_float(value)
            if numeric is not None:
                strategy_weights[normalize_strategy_name(name)] = self._bounded_multiplier(
                    numeric
                )

        score_multipliers = dict(self.DEFAULT_SCORE_MULTIPLIERS)
        for name, value in dict(raw_snapshot.get("score_multipliers") or {}).items():
            numeric = self._coerce_float(value)
            if numeric is not None:
                score_multipliers[str(name).strip()] = self._bounded_multiplier(numeric)

        atr_multipliers = dict(self.DEFAULT_ATR_MULTIPLIERS)
        for name, value in dict(raw_snapshot.get("atr_multipliers") or {}).items():
            numeric = self._coerce_float(value)
            if numeric is not None:
                atr_multipliers[self._normalize_key(name)] = self._bounded_atr_multiplier(
                    numeric
                )

        version = str(raw_snapshot.get("version") or self.DEFAULT_VERSION).strip() or self.DEFAULT_VERSION
        source = str(raw_snapshot.get("source") or "snapshot").strip() or "snapshot"
        effective_from = self._coerce_datetime(
            raw_snapshot.get("effective_from") or raw_snapshot.get("effective_at")
        )
        return CalibrationSnapshot(
            version=version,
            strategy_weights=strategy_weights,
            score_multipliers=score_multipliers,
            atr_multipliers=atr_multipliers,
            source=source,
            effective_from=effective_from,
        )

    @staticmethod
    def snapshot_payload(snapshot: CalibrationSnapshot) -> dict[str, Any]:
        return {
            "version": snapshot.version,
            "source": snapshot.source,
            "strategy_weights": dict(snapshot.strategy_weights),
            "score_multipliers": dict(snapshot.score_multipliers),
            "atr_multipliers": dict(snapshot.atr_multipliers),
            "effective_from": snapshot.effective_from.isoformat()
            if snapshot.effective_from is not None
            else None,
        }

    def strategy_weight(self, strategy: str, snapshot: CalibrationSnapshot) -> float:
        return self._bounded_multiplier(
            snapshot.strategy_weights.get(normalize_strategy_name(strategy), 1.0)
        )

    def score_multiplier(self, factor: str, snapshot: CalibrationSnapshot) -> float:
        return self._bounded_multiplier(snapshot.score_multipliers.get(str(factor).strip(), 1.0))

    def atr_multiplier(
        self,
        regime_key: str,
        snapshot: CalibrationSnapshot,
    ) -> tuple[float, str]:
        normalized_key = self._normalize_key(regime_key)
        if normalized_key in snapshot.atr_multipliers:
            return (
                self._bounded_atr_multiplier(snapshot.atr_multipliers[normalized_key]),
                normalized_key,
            )
        fallback_family = MarketRegimeDetector.normalize_family(normalized_key)
        fallback_key = self._normalize_key(fallback_family)
        if fallback_key in snapshot.atr_multipliers:
            return (
                self._bounded_atr_multiplier(snapshot.atr_multipliers[fallback_key]),
                fallback_key,
            )
        default_key = "range"
        return (
            self._bounded_atr_multiplier(snapshot.atr_multipliers.get(default_key, 1.8)),
            default_key,
        )

    @staticmethod
    def _bounded_multiplier(value: float) -> float:
        return max(0.75, min(1.25, float(value)))

    @staticmethod
    def _bounded_atr_multiplier(value: float) -> float:
        return max(1.0, min(4.0, float(value)))

    @staticmethod
    def _normalize_key(value: Any) -> str:
        return str(value or "").strip().lower().replace(" ", "_")

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        if isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return None