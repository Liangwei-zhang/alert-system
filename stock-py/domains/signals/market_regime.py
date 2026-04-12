from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MarketRegimeAssessment:
    regime: str
    detail: str
    breakout_candidate: bool
    duration_bars: int | None
    metrics: dict[str, float]
    reasons: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        return {
            "market_regime": self.regime,
            "market_regime_detail": self.detail,
            "breakout_candidate": self.breakout_candidate,
            "regime_duration_bars": self.duration_bars,
            "regime_metrics": dict(self.metrics),
            "regime_reasons": list(self.reasons),
        }


class MarketRegimeDetector:
    _TREND_TOKENS = {
        "bull",
        "bear",
        "bullish",
        "bearish",
        "trend",
        "trend_up",
        "trend_down",
        "trend_strong_up",
        "trend_strong_down",
    }
    _VOLATILE_TOKENS = {
        "volatile",
        "high_volatility",
        "breakout",
        "breakout_candidate",
        "volatile_breakout",
        "volatile_reversal",
    }
    _RANGE_TOKENS = {
        "range",
        "range_tight",
        "range_balanced",
        "range_wide",
        "sideways",
        "chop",
        "neutral",
    }

    def detect(
        self,
        market_snapshot: dict[str, Any],
        *,
        explicit_regime: Any = None,
    ) -> MarketRegimeAssessment:
        momentum = self._coerce_float(market_snapshot.get("momentum_score")) or 0.0
        trend = self._coerce_float(market_snapshot.get("trend_strength")) or 0.0
        volatility = self._coerce_float(market_snapshot.get("volatility_score")) or 0.0
        dislocation = abs(self._coerce_float(market_snapshot.get("dislocation_pct")) or 0.0)
        duration_bars = self._resolve_duration_bars(market_snapshot)
        metrics = {
            "momentum_score": round(momentum, 4),
            "trend_strength": round(trend, 4),
            "volatility_score": round(volatility, 4),
            "dislocation_pct": round(dislocation, 4),
        }

        normalized_explicit = self._normalize_token(explicit_regime)
        if normalized_explicit:
            family = self.normalize_family(normalized_explicit)
            detail = self._detail_from_explicit(normalized_explicit, momentum=momentum)
            return MarketRegimeAssessment(
                regime=family,
                detail=detail,
                breakout_candidate=detail in {"breakout_candidate", "volatile_breakout"},
                duration_bars=duration_bars,
                metrics=metrics,
                reasons=("explicit-market-regime",),
            )

        if volatility >= 0.82 and abs(momentum) >= 0.55 and trend >= 0.45:
            return MarketRegimeAssessment(
                regime="volatile",
                detail="volatile_breakout",
                breakout_candidate=True,
                duration_bars=duration_bars,
                metrics=metrics,
                reasons=("high-volatility-momentum-expansion",),
            )
        if trend >= 0.82 and abs(momentum) >= 0.75:
            return MarketRegimeAssessment(
                regime="trend",
                detail="trend_strong_down" if momentum < -0.18 else "trend_strong_up",
                breakout_candidate=False,
                duration_bars=duration_bars,
                metrics=metrics,
                reasons=("strong-trend-threshold",),
            )
        if trend >= 0.6:
            return MarketRegimeAssessment(
                regime="trend",
                detail="trend_down" if momentum < -0.15 else "trend_up",
                breakout_candidate=False,
                duration_bars=duration_bars,
                metrics=metrics,
                reasons=("trend-strength-threshold",),
            )
        if volatility >= 0.78 and dislocation >= 0.03:
            return MarketRegimeAssessment(
                regime="volatile",
                detail="volatile_reversal",
                breakout_candidate=False,
                duration_bars=duration_bars,
                metrics=metrics,
                reasons=("volatile-reversal-dislocation",),
            )
        if volatility >= 0.75:
            return MarketRegimeAssessment(
                regime="volatile",
                detail="volatile",
                breakout_candidate=False,
                duration_bars=duration_bars,
                metrics=metrics,
                reasons=("volatility-threshold",),
            )
        if volatility <= 0.22 and trend <= 0.35:
            return MarketRegimeAssessment(
                regime="range",
                detail="range_tight",
                breakout_candidate=False,
                duration_bars=duration_bars,
                metrics=metrics,
                reasons=("low-volatility-compression",),
            )
        if dislocation >= 0.03:
            return MarketRegimeAssessment(
                regime="range",
                detail="range_wide",
                breakout_candidate=False,
                duration_bars=duration_bars,
                metrics=metrics,
                reasons=("range-dislocation-extension",),
            )
        return MarketRegimeAssessment(
            regime="range",
            detail="range_balanced",
            breakout_candidate=False,
            duration_bars=duration_bars,
            metrics=metrics,
            reasons=("default-range-regime",),
        )

    @classmethod
    def normalize_family(cls, value: str) -> str:
        normalized = cls._normalize_token(value)
        if normalized in cls._TREND_TOKENS:
            return "trend"
        if normalized in cls._VOLATILE_TOKENS:
            return "volatile"
        if normalized in cls._RANGE_TOKENS:
            return "range"
        return normalized or "range"

    @classmethod
    def _detail_from_explicit(cls, value: str, *, momentum: float) -> str:
        normalized = cls._normalize_token(value)
        if normalized in {
            "trend_strong_up",
            "trend_strong_down",
            "volatile_breakout",
            "volatile_reversal",
            "range_tight",
            "range_balanced",
            "range_wide",
        }:
            return normalized
        if normalized in {"trend_down", "bear", "bearish"}:
            return "trend_down"
        if normalized in {"trend_up", "bull", "bullish"}:
            return "trend_up"
        if normalized in {"breakout", "breakout_candidate"}:
            return "breakout_candidate"
        if normalized in cls._VOLATILE_TOKENS:
            return "volatile"
        if normalized in cls._RANGE_TOKENS:
            return "range_balanced"
        if normalized in cls._TREND_TOKENS:
            return "trend_down" if momentum < -0.15 else "trend_up"
        return "range_balanced"

    @classmethod
    def _resolve_duration_bars(cls, market_snapshot: dict[str, Any]) -> int | None:
        for key in (
            "regime_duration_bars",
            "bars_in_regime",
            "regime_bars",
            "trend_streak_bars",
            "range_streak_bars",
            "volatility_streak_bars",
        ):
            numeric = cls._coerce_int(market_snapshot.get(key))
            if numeric is not None and numeric > 0:
                return numeric
        analysis = market_snapshot.get("analysis")
        if isinstance(analysis, dict):
            for key in ("regime_duration_bars", "bars_in_regime"):
                numeric = cls._coerce_int(analysis.get(key))
                if numeric is not None and numeric > 0:
                    return numeric
        return None

    @staticmethod
    def _normalize_token(value: Any) -> str:
        return str(value or "").strip().lower().replace(" ", "_")

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _coerce_int(cls, value: Any) -> int | None:
        numeric = cls._coerce_float(value)
        if numeric is None:
            return None
        return int(numeric)