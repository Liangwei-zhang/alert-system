from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from domains.signals.calibration_service import CalibrationService
from domains.signals.exit_level_calculator import ExitLevelCalculator
from domains.signals.strategy_selector import StrategySelector

try:
    from domains.signals.schemas import SignalCandidate as SignalCandidateModel
except Exception:  # pragma: no cover - optional in dependency-light environments
    SignalCandidateModel = None


class LiveStrategyEngine:
    def __init__(
        self,
        *,
        strategy_selector: StrategySelector | None = None,
        calibration_service: CalibrationService | None = None,
        exit_level_calculator: ExitLevelCalculator | None = None,
    ) -> None:
        self.calibration_service = calibration_service or CalibrationService()
        self.strategy_selector = strategy_selector or StrategySelector(
            calibration_service=self.calibration_service,
        )
        self.exit_level_calculator = exit_level_calculator or ExitLevelCalculator()

    def select_strategy(
        self,
        symbol: str,
        market_snapshot: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.strategy_selector.select(symbol, market_snapshot, context)

    def score_candidate_breakdown(self, candidate: dict[str, Any]) -> dict[str, Any]:
        analysis = candidate.get("analysis") if isinstance(candidate.get("analysis"), dict) else {}
        calibration = self.calibration_service.current_snapshot({"analysis": analysis}, None)

        base_score = 32.0
        signal_bias = 8.0 if str(candidate.get("type", "")).lower().startswith("buy") else 6.0
        confidence = self._percentage_to_points(
            candidate.get("confidence", analysis.get("confidence")),
            scale=0.25 * self.calibration_service.score_multiplier("confidence", calibration),
        )
        probability = self._fraction_to_points(
            candidate.get("probability", analysis.get("probability")),
            scale=30.0 * self.calibration_service.score_multiplier("probability", calibration),
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
                * 5.0
                * self.calibration_service.score_multiplier("risk_reward", calibration),
            ),
        )
        volume_bonus = (
            8.0 * self.calibration_service.score_multiplier("volume", calibration)
            if self._truthy(analysis.get("volume_confirmed", candidate.get("volume_confirmed")))
            else 0.0
        )
        trend_bonus = (
            8.0 * self.calibration_service.score_multiplier("trend", calibration)
            if self._truthy(analysis.get("trend_confirmed", candidate.get("trend_confirmed")))
            else 0.0
        )
        reversal_bonus = (
            6.0 * self.calibration_service.score_multiplier("reversal", calibration)
            if self._truthy(analysis.get("reversal_confirmed", candidate.get("reversal_confirmed")))
            else 0.0
        )
        quality_bonus = self._percentage_to_points(
            analysis.get("setup_quality"),
            scale=0.15 * self.calibration_service.score_multiplier("quality", calibration),
        )
        stale_penalty = (
            10.0 * self.calibration_service.score_multiplier("stale_penalty", calibration)
            if self._truthy(analysis.get("stale_data"))
            else 0.0
        )
        liquidity_penalty = (
            8.0 * self.calibration_service.score_multiplier("liquidity_penalty", calibration)
            if self._truthy(analysis.get("low_liquidity"))
            else 0.0
        )

        raw_total = (
            base_score
            + signal_bias
            + confidence
            + probability
            + risk_reward
            + volume_bonus
            + trend_bonus
            + reversal_bonus
            + quality_bonus
            - stale_penalty
            - liquidity_penalty
        )
        clamped_total = int(max(0, min(100, round(raw_total))))
        return {
            "calibration_version": calibration.version,
            "base_score": round(base_score, 4),
            "signal_bias": round(signal_bias, 4),
            "confidence_points": round(confidence, 4),
            "probability_points": round(probability, 4),
            "risk_reward_points": round(risk_reward, 4),
            "volume_bonus": round(volume_bonus, 4),
            "trend_bonus": round(trend_bonus, 4),
            "reversal_bonus": round(reversal_bonus, 4),
            "quality_bonus": round(quality_bonus, 4),
            "stale_penalty": round(stale_penalty, 4),
            "liquidity_penalty": round(liquidity_penalty, 4),
            "raw_total": round(raw_total, 4),
            "clamped_total": clamped_total,
        }

    def score_candidate(self, candidate: dict[str, Any]) -> int:
        return int(self.score_candidate_breakdown(candidate)["clamped_total"])

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
        if strategy.get("market_regime_detail"):
            analysis.setdefault("market_regime_detail", strategy["market_regime_detail"])
        analysis["strategy_selection"] = {
            "strategy": strategy["strategy"],
            "source": strategy.get("source", "heuristic"),
            "source_strategy": strategy.get("source_strategy", strategy["strategy"]),
            "rank": strategy.get("rank"),
            "ranking_score": strategy.get("ranking_score"),
            "combined_score": strategy.get("combined_score"),
            "signal_fit_score": strategy.get("signal_fit_score"),
            "regime_bias": strategy.get("regime_bias"),
            "degradation_penalty": strategy.get("degradation_penalty"),
            "stable": bool(strategy.get("stable", False)),
            "market_regime_detail": strategy.get("market_regime_detail"),
            "regime_reasons": list(strategy.get("regime_reasons") or []),
            "calibration_version": strategy.get("calibration_version"),
            "strategy_weight": strategy.get("strategy_weight"),
        }
        if strategy.get("candidates"):
            analysis["strategy_candidates"] = list(strategy["candidates"])
        if strategy.get("alert_decision"):
            alert_decision = dict(strategy["alert_decision"])
            analysis["alert_decision"] = alert_decision
            suppressed_reasons = alert_decision.get("suppressed_reasons")
            if isinstance(suppressed_reasons, list) and suppressed_reasons:
                analysis["suppressed_reasons"] = list(suppressed_reasons)

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

        score_breakdown = self.score_candidate_breakdown(
            {
                "type": signal_type,
                "confidence": confidence,
                "probability": probability,
                "risk_reward_ratio": risk_reward_ratio,
                "analysis": analysis,
            }
        )
        analysis["score_breakdown"] = dict(score_breakdown)
        analysis.setdefault(
            "calibration_version",
            strategy.get("calibration_version") or score_breakdown.get("calibration_version"),
        )

        base_score = self._coerce_float(market_snapshot.get("score"))
        if base_score is None:
            base_score = float(score_breakdown["clamped_total"])

        exit_levels = self.exit_level_calculator.calculate(
            signal_type=signal_type,
            entry_price=price,
            market_snapshot=market_snapshot,
            analysis=analysis,
            market_regime=strategy["market_regime"],
            risk_reward_ratio=risk_reward_ratio,
        )
        analysis["exit_levels"] = exit_levels

        adjusted_score = self._adjust_score_with_selection(base_score, strategy)
        analysis["score_breakdown"]["selected_score"] = adjusted_score

        candidate_payload = {
            "symbol": symbol.strip().upper(),
            "type": signal_type,
            "score": adjusted_score,
            "price": price,
            "reasons": reasons,
            "analysis": analysis,
            "confidence": confidence,
            "probability": probability,
            "stop_loss": exit_levels.get("stop_loss"),
            "take_profit_1": exit_levels.get("take_profit_1"),
            "take_profit_2": exit_levels.get("take_profit_2"),
            "take_profit_3": exit_levels.get("take_profit_3"),
            "risk_reward_ratio": risk_reward_ratio,
            "strategy_window": strategy["strategy_window"],
            "market_regime": strategy["market_regime"],
        }

        if SignalCandidateModel is None:
            return candidate_payload
        return SignalCandidateModel(**candidate_payload)

    def _adjust_score_with_selection(self, base_score: float, strategy: dict[str, Any]) -> int:
        combined_score = self._coerce_float(strategy.get("combined_score")) or 0.0
        selection_adjustment = max(-12.0, min(12.0, (combined_score - 20.0) * 0.55))
        alert_decision = strategy.get("alert_decision")
        if isinstance(alert_decision, dict) and not alert_decision.get("publish_allowed", True):
            selection_adjustment -= 6.0
        return int(max(0, min(100, round(base_score + selection_adjustment))))

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
