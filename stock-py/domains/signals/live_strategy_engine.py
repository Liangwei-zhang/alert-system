from __future__ import annotations

from collections.abc import Iterable
from typing import Any

try:
    from domains.signals.schemas import SignalCandidate as SignalCandidateModel
except Exception:  # pragma: no cover - optional in dependency-light environments
    SignalCandidateModel = None


class LiveStrategyEngine:
    def select_strategy(
        self,
        symbol: str,
        market_snapshot: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        del symbol
        context = context or {}
        timeframe = str(
            market_snapshot.get("timeframe")
            or market_snapshot.get("strategy_window")
            or context.get("timeframe")
            or "1h"
        ).lower()
        market_regime = str(
            market_snapshot.get("market_regime")
            or context.get("market_regime")
            or self._infer_market_regime(market_snapshot)
        ).lower()

        dislocation = abs(self._coerce_float(market_snapshot.get("dislocation_pct")) or 0.0)
        momentum = self._coerce_float(market_snapshot.get("momentum_score")) or 0.0
        volatility = self._coerce_float(market_snapshot.get("volatility_score")) or 0.0

        if dislocation >= 0.03:
            strategy = "mean_reversion"
        elif momentum >= 0.65:
            strategy = "trend_continuation"
        elif volatility >= 0.75:
            strategy = "volatility_breakout"
        else:
            strategy = "range_rotation"

        return {
            "strategy": strategy,
            "strategy_window": timeframe,
            "market_regime": market_regime,
        }

    def score_candidate(self, candidate: dict[str, Any]) -> int:
        analysis = candidate.get("analysis") if isinstance(candidate.get("analysis"), dict) else {}

        confidence = self._percentage_to_points(
            candidate.get("confidence", analysis.get("confidence")),
            scale=0.25,
        )
        probability = self._fraction_to_points(
            candidate.get("probability", analysis.get("probability")),
            scale=30.0,
        )
        risk_reward = min(
            15.0,
            max(
                0.0,
                (
                    self._coerce_float(
                        candidate.get("risk_reward_ratio", analysis.get("risk_reward_ratio"))
                    )
                    or 0.0
                )
                * 5.0,
            ),
        )

        signal_bias = 8.0 if str(candidate.get("type", "")).lower().startswith("buy") else 6.0
        volume_bonus = (
            8.0
            if self._truthy(analysis.get("volume_confirmed", candidate.get("volume_confirmed")))
            else 0.0
        )
        trend_bonus = (
            8.0
            if self._truthy(analysis.get("trend_confirmed", candidate.get("trend_confirmed")))
            else 0.0
        )
        reversal_bonus = (
            6.0
            if self._truthy(analysis.get("reversal_confirmed", candidate.get("reversal_confirmed")))
            else 0.0
        )
        quality_bonus = self._percentage_to_points(analysis.get("setup_quality"), scale=0.15)

        stale_penalty = 10.0 if self._truthy(analysis.get("stale_data")) else 0.0
        liquidity_penalty = 8.0 if self._truthy(analysis.get("low_liquidity")) else 0.0

        total = (
            32.0
            + signal_bias
            + confidence
            + probability
            + risk_reward
            + volume_bonus
            + trend_bonus
            + reversal_bonus
            + quality_bonus
        )
        total -= stale_penalty + liquidity_penalty
        return int(max(0, min(100, round(total))))

    def build_signal_candidate(
        self,
        symbol: str,
        market_snapshot: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any | None:
        signal_type = self._extract_signal_type(market_snapshot)
        price = self._coerce_float(
            market_snapshot.get("price")
            or market_snapshot.get("entry_price")
            or market_snapshot.get("last_price")
            or market_snapshot.get("current_price")
            or market_snapshot.get("close")
        )
        if signal_type is None or price is None or price <= 0:
            return None

        analysis = dict(market_snapshot.get("analysis") or {})
        strategy = self.select_strategy(symbol, market_snapshot, context)
        analysis.setdefault("strategy", strategy["strategy"])
        analysis.setdefault("strategy_window", strategy["strategy_window"])
        analysis.setdefault("market_regime", strategy["market_regime"])

        reasons = self._collect_reasons(market_snapshot.get("reasons"), strategy["strategy"])
        confidence = self._normalize_percentage(
            market_snapshot.get("confidence", analysis.get("confidence")),
        )
        probability = self._normalize_fraction(
            market_snapshot.get("probability", analysis.get("probability")),
        )
        risk_reward_ratio = self._coerce_float(
            market_snapshot.get("risk_reward_ratio") or analysis.get("risk_reward_ratio")
        )

        candidate_payload = {
            "symbol": symbol.strip().upper(),
            "type": signal_type,
            "score": market_snapshot.get("score")
            or self.score_candidate(
                {
                    "type": signal_type,
                    "confidence": confidence,
                    "probability": probability,
                    "risk_reward_ratio": risk_reward_ratio,
                    "analysis": analysis,
                }
            ),
            "price": price,
            "reasons": reasons,
            "analysis": analysis,
            "confidence": confidence,
            "probability": probability,
            "stop_loss": self._coerce_float(
                market_snapshot.get("stop_loss") or analysis.get("stop_loss")
            ),
            "take_profit_1": self._coerce_float(
                market_snapshot.get("take_profit_1") or analysis.get("take_profit_1")
            ),
            "take_profit_2": self._coerce_float(
                market_snapshot.get("take_profit_2") or analysis.get("take_profit_2")
            ),
            "take_profit_3": self._coerce_float(
                market_snapshot.get("take_profit_3") or analysis.get("take_profit_3")
            ),
            "risk_reward_ratio": risk_reward_ratio,
            "strategy_window": strategy["strategy_window"],
            "market_regime": strategy["market_regime"],
        }

        if SignalCandidateModel is None:
            return candidate_payload
        return SignalCandidateModel(**candidate_payload)

    @staticmethod
    def _extract_signal_type(market_snapshot: dict[str, Any]) -> str | None:
        raw_value = (
            market_snapshot.get("signal_type")
            or market_snapshot.get("direction")
            or market_snapshot.get("action")
        )
        if raw_value is None:
            return None
        normalized = str(raw_value).strip().lower().replace("-", "_")
        if normalized in {"buy", "sell", "split_buy", "split_sell"}:
            return normalized
        return None

    def _collect_reasons(self, raw_reasons: Any, strategy: str) -> list[str]:
        reasons = []
        if isinstance(raw_reasons, str) and raw_reasons.strip():
            reasons.append(raw_reasons.strip())
        elif isinstance(raw_reasons, Iterable):
            for value in raw_reasons:
                text = str(value).strip()
                if text:
                    reasons.append(text)

        if not reasons:
            reasons.append(f"{strategy.replace('_', ' ')} setup detected")
        return reasons[:8]

    @staticmethod
    def _infer_market_regime(market_snapshot: dict[str, Any]) -> str:
        volatility = (
            LiveStrategyEngine._coerce_float(market_snapshot.get("volatility_score")) or 0.0
        )
        trend = LiveStrategyEngine._coerce_float(market_snapshot.get("trend_strength")) or 0.0
        if volatility >= 0.75:
            return "volatile"
        if trend >= 0.6:
            return "trend"
        return "range"

    @staticmethod
    def _truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value > 0
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return False

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _normalize_percentage(cls, value: Any) -> float | None:
        normalized = cls._coerce_float(value)
        if normalized is None:
            return None
        if normalized <= 1:
            normalized *= 100
        return max(0.0, min(100.0, normalized))

    @classmethod
    def _normalize_fraction(cls, value: Any) -> float | None:
        normalized = cls._coerce_float(value)
        if normalized is None:
            return None
        if normalized > 1:
            normalized /= 100
        return max(0.0, min(1.0, normalized))

    @classmethod
    def _percentage_to_points(cls, value: Any, *, scale: float) -> float:
        normalized = cls._normalize_percentage(value)
        if normalized is None:
            return 0.0
        return normalized * scale

    @classmethod
    def _fraction_to_points(cls, value: Any, *, scale: float) -> float:
        normalized = cls._normalize_fraction(value)
        if normalized is None:
            return 0.0
        return normalized * scale
