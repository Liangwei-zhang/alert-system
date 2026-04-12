from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from domains.signals.calibration_service import CalibrationService, CalibrationSnapshot
from domains.signals.market_regime import MarketRegimeAssessment, MarketRegimeDetector
from domains.signals.strategy_profiles import (
    normalize_strategy_name,
    regime_bias,
    resolve_strategy_name,
    select_heuristic_strategy,
    strategy_fit_score,
)


class StrategySelector:
    BENCHMARK_ONLY_SOURCE_STRATEGIES = {"buy_and_hold", "sma_cross"}
    BREAKOUT_MIN_SIGNAL_SCORE = 60.0

    def __init__(
        self,
        *,
        regime_detector: MarketRegimeDetector | None = None,
        calibration_service: CalibrationService | None = None,
    ) -> None:
        self.regime_detector = regime_detector or MarketRegimeDetector()
        self.calibration_service = calibration_service or CalibrationService()

    def select(
        self,
        symbol: str,
        market_snapshot: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del symbol
        context = context or {}
        timeframe = str(
            market_snapshot.get("timeframe")
            or market_snapshot.get("strategy_window")
            or context.get("timeframe")
            or "1h"
        ).lower()
        regime_assessment = self.regime_detector.detect(
            market_snapshot,
            explicit_regime=market_snapshot.get("market_regime") or context.get("market_regime"),
        )
        calibration = self.calibration_service.current_snapshot(market_snapshot, context)

        rankings = self._normalize_strategy_rankings(
            market_snapshot.get("strategy_rankings") or context.get("strategy_rankings")
        )
        if rankings:
            ranked_candidates = self._build_ranking_candidates(
                rankings,
                market_snapshot,
                timeframe=timeframe,
                regime_assessment=regime_assessment,
                calibration=calibration,
            )
            if ranked_candidates:
                winner = ranked_candidates[0]
                winner["alert_decision"] = self._build_alert_decision(
                    market_snapshot,
                    strategy=str(winner["strategy"]),
                    source_strategy=str(winner.get("source_strategy") or winner["strategy"]),
                    ranking_score=float(winner["ranking_score"]),
                    combined_score=float(winner["combined_score"]),
                    signal_fit_score=float(winner["signal_fit_score"]),
                    regime_bias=float(winner["regime_bias"]),
                    degradation_penalty=float(winner["degradation_penalty"]),
                )
                winner["candidates"] = [
                    self._public_candidate_view(candidate) for candidate in ranked_candidates[:4]
                ]
                return winner

        strategy = select_heuristic_strategy(
            market_snapshot,
            coerce_float=self._coerce_float,
        )
        strategy_weight = self.calibration_service.strategy_weight(strategy, calibration)
        selection = {
            "strategy": strategy,
            "strategy_window": timeframe,
            "market_regime": regime_assessment.regime,
            "market_regime_detail": regime_assessment.detail,
            "regime_reasons": list(regime_assessment.reasons),
            "source": "heuristic",
            "source_strategy": strategy,
            "rank": None,
            "ranking_score": 4.0,
            "signal_fit_score": round(self._strategy_fit_score(strategy, market_snapshot), 4),
            "regime_bias": round(regime_bias(strategy, regime_assessment.regime), 4),
            "degradation_penalty": 0.0,
            "stable": True,
            "calibration_version": calibration.version,
            "strategy_weight": round(strategy_weight, 4),
        }
        unweighted_score = (
            float(selection["ranking_score"])
            + float(selection["signal_fit_score"])
            + float(selection["regime_bias"])
            + (self._current_signal_score(market_snapshot) * 0.12)
        )
        selection["combined_score"] = round(unweighted_score * strategy_weight, 4)
        selection["alert_decision"] = self._build_alert_decision(
            market_snapshot,
            strategy=str(selection["strategy"]),
            source_strategy=str(selection.get("source_strategy") or selection["strategy"]),
            ranking_score=float(selection["ranking_score"]),
            combined_score=float(selection["combined_score"]),
            signal_fit_score=float(selection["signal_fit_score"]),
            regime_bias=float(selection["regime_bias"]),
            degradation_penalty=0.0,
        )
        selection["candidates"] = [self._public_candidate_view(selection)]
        return selection

    def _normalize_strategy_rankings(self, raw_rankings: Any) -> list[dict[str, Any]]:
        if raw_rankings in (None, "", []):
            return []

        if isinstance(raw_rankings, dict):
            raw_items = [raw_rankings]
        elif isinstance(raw_rankings, Iterable) and not isinstance(raw_rankings, (str, bytes)):
            raw_items = list(raw_rankings)
        else:
            return []

        normalized: list[dict[str, Any]] = []
        for item in raw_items:
            if hasattr(item, "model_dump"):
                data = item.model_dump()
            elif isinstance(item, dict):
                data = dict(item)
            else:
                data = {
                    "strategy_name": getattr(item, "strategy_name", getattr(item, "strategy", None)),
                    "rank": getattr(item, "rank", None),
                    "score": getattr(item, "score", None),
                    "degradation": getattr(item, "degradation", None),
                    "symbols_covered": getattr(item, "symbols_covered", None),
                    "evidence": getattr(item, "evidence", None),
                }

            source_strategy = normalize_strategy_name(
                data.get("strategy_name") or data.get("strategy_id") or data.get("strategy")
            )
            strategy = resolve_strategy_name(source_strategy)
            if strategy is None:
                continue

            evidence = data.get("evidence")
            if isinstance(evidence, str):
                try:
                    evidence = json.loads(evidence)
                except json.JSONDecodeError:
                    evidence = {}
            if not isinstance(evidence, dict):
                evidence = {}

            normalized.append(
                {
                    "strategy": strategy,
                    "source_strategy": source_strategy,
                    "rank": self._coerce_int(data.get("rank")),
                    "score": self._coerce_float(data.get("score")) or 0.0,
                    "degradation": self._coerce_float(data.get("degradation")) or 0.0,
                    "symbols_covered": self._coerce_int(data.get("symbols_covered")) or 0,
                    "evidence": evidence,
                }
            )
        return normalized

    def _build_ranking_candidates(
        self,
        rankings: list[dict[str, Any]],
        market_snapshot: dict[str, Any],
        *,
        timeframe: str,
        regime_assessment: MarketRegimeAssessment,
        calibration: CalibrationSnapshot,
    ) -> list[dict[str, Any]]:
        candidates_by_strategy: dict[str, dict[str, Any]] = {}
        current_signal_bonus = self._current_signal_score(market_snapshot) * 0.12

        for ranking in rankings:
            strategy = str(ranking["strategy"])
            evidence = ranking["evidence"] if isinstance(ranking.get("evidence"), dict) else {}
            ranking_score = self._ranking_score(
                ranking.get("score"),
                rank=ranking.get("rank"),
            )
            signal_fit = self._strategy_fit_score(strategy, market_snapshot)
            regime_fit = regime_bias(strategy, regime_assessment.regime)
            degradation_penalty = min(18.0, max(0.0, float(ranking.get("degradation") or 0.0)))
            stability_bonus = 4.0 if bool(evidence.get("stable")) else 0.0
            coverage_bonus = min(3.0, float(ranking.get("symbols_covered") or 0) / 150.0)
            timeframe_bonus = self._timeframe_bonus(timeframe, evidence)
            strategy_weight = self.calibration_service.strategy_weight(strategy, calibration)
            unweighted_score = (
                ranking_score
                + signal_fit
                + regime_fit
                + stability_bonus
                + coverage_bonus
                + timeframe_bonus
                + current_signal_bonus
                - degradation_penalty
            )
            candidate = {
                "strategy": strategy,
                "strategy_window": timeframe,
                "market_regime": regime_assessment.regime,
                "market_regime_detail": regime_assessment.detail,
                "regime_reasons": list(regime_assessment.reasons),
                "source": "ranking",
                "source_strategy": ranking["source_strategy"],
                "rank": ranking.get("rank"),
                "ranking_score": round(ranking_score, 4),
                "signal_fit_score": round(signal_fit, 4),
                "regime_bias": round(regime_fit, 4),
                "degradation_penalty": round(degradation_penalty, 4),
                "combined_score": round(unweighted_score * strategy_weight, 4),
                "stable": bool(evidence.get("stable", False)),
                "symbols_covered": int(ranking.get("symbols_covered") or 0),
                "evidence": evidence,
                "calibration_version": calibration.version,
                "strategy_weight": round(strategy_weight, 4),
            }
            current_best = candidates_by_strategy.get(strategy)
            if current_best is None or float(candidate["combined_score"]) > float(
                current_best["combined_score"]
            ):
                candidates_by_strategy[strategy] = candidate

        return sorted(
            candidates_by_strategy.values(),
            key=lambda item: (
                float(item["combined_score"]),
                -float(item.get("rank") or 99),
            ),
            reverse=True,
        )

    def _build_alert_decision(
        self,
        market_snapshot: dict[str, Any],
        *,
        strategy: str,
        source_strategy: str,
        ranking_score: float,
        combined_score: float,
        signal_fit_score: float,
        regime_bias: float,
        degradation_penalty: float,
    ) -> dict[str, Any]:
        suppressed_reasons: list[str] = []
        current_signal_score = self._current_signal_score(market_snapshot)
        setup_quality = self._normalize_percentage(
            (market_snapshot.get("analysis") or {}).get("setup_quality")
        )
        analysis = market_snapshot.get("analysis") if isinstance(market_snapshot.get("analysis"), dict) else {}
        normalized_strategy = normalize_strategy_name(strategy)
        normalized_source_strategy = normalize_strategy_name(source_strategy)

        if combined_score < 18.0:
            suppressed_reasons.append("combined-score-below-threshold")
        if degradation_penalty >= 12.0:
            suppressed_reasons.append("strategy-degradation-detected")
        if normalized_source_strategy in self.BENCHMARK_ONLY_SOURCE_STRATEGIES:
            suppressed_reasons.append("benchmark-only-strategy")
        if signal_fit_score < 6.0:
            suppressed_reasons.append("signal-fit-weak")
        if current_signal_score < 48.0:
            suppressed_reasons.append("signal-confidence-weak")
        if (
            normalized_strategy == "volatility_breakout"
            and current_signal_score < self.BREAKOUT_MIN_SIGNAL_SCORE
        ):
            suppressed_reasons.append("breakout-confidence-weak")
        if (
            setup_quality is not None
            and setup_quality < 52.0
            and not any(
                self._truthy(analysis.get(field_name))
                for field_name in ("volume_confirmed", "trend_confirmed", "reversal_confirmed")
            )
        ):
            suppressed_reasons.append("setup-quality-weak")

        return {
            "publish_allowed": not suppressed_reasons,
            "suppressed_reasons": suppressed_reasons,
            "current_signal_score": round(current_signal_score, 4),
            "ranking_score": round(ranking_score, 4),
            "combined_score": round(combined_score, 4),
            "signal_fit_score": round(signal_fit_score, 4),
            "regime_bias": round(regime_bias, 4),
            "degradation_penalty": round(degradation_penalty, 4),
        }

    def _current_signal_score(self, market_snapshot: dict[str, Any]) -> float:
        analysis = market_snapshot.get("analysis") if isinstance(market_snapshot.get("analysis"), dict) else {}
        confidence = self._normalize_percentage(
            market_snapshot.get("confidence", analysis.get("confidence"))
        ) or 0.0
        probability = self._normalize_fraction(
            market_snapshot.get("probability", analysis.get("probability"))
        ) or 0.0
        setup_quality = self._normalize_percentage(analysis.get("setup_quality")) or 0.0
        volume_bonus = 6.0 if self._truthy(analysis.get("volume_confirmed")) else 0.0
        trend_bonus = 4.0 if self._truthy(analysis.get("trend_confirmed")) else 0.0
        reversal_bonus = 3.0 if self._truthy(analysis.get("reversal_confirmed")) else 0.0
        return min(
            100.0,
            (confidence * 0.4)
            + ((probability * 100.0) * 0.3)
            + (setup_quality * 0.2)
            + volume_bonus
            + trend_bonus
            + reversal_bonus,
        )

    def _ranking_score(self, score: Any, *, rank: Any) -> float:
        normalized_score = max(-30.0, min(30.0, (self._coerce_float(score) or 0.0) / 10.0))
        normalized_rank = max(1, self._coerce_int(rank) or 5)
        rank_bonus = max(0.0, 18.0 - ((normalized_rank - 1) * 4.0))
        return normalized_score + rank_bonus

    def _strategy_fit_score(self, strategy: str, market_snapshot: dict[str, Any]) -> float:
        return strategy_fit_score(
            strategy,
            market_snapshot,
            coerce_float=self._coerce_float,
            truthy=self._truthy,
            normalize_percentage=self._normalize_percentage,
        )

    @staticmethod
    def _timeframe_bonus(timeframe: str, evidence: dict[str, Any]) -> float:
        windows = evidence.get("windows") if isinstance(evidence.get("windows"), dict) else {}
        if not windows:
            return 0.0
        best_window_days = StrategySelector._coerce_int(evidence.get("best_window_days")) or 0
        if timeframe == "1d" and best_window_days in {30, 90, 180, 365}:
            return 1.5
        return 0.0

    @staticmethod
    def _public_candidate_view(candidate: dict[str, Any]) -> dict[str, Any]:
        return {
            "strategy": candidate["strategy"],
            "source": candidate.get("source", "heuristic"),
            "source_strategy": candidate.get("source_strategy", candidate["strategy"]),
            "rank": candidate.get("rank"),
            "ranking_score": candidate.get("ranking_score"),
            "combined_score": candidate.get("combined_score"),
            "signal_fit_score": candidate.get("signal_fit_score"),
            "regime_bias": candidate.get("regime_bias"),
            "degradation_penalty": candidate.get("degradation_penalty"),
            "stable": bool(candidate.get("stable", False)),
            "market_regime_detail": candidate.get("market_regime_detail"),
            "strategy_weight": candidate.get("strategy_weight"),
            "calibration_version": candidate.get("calibration_version"),
        }

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

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        numeric = StrategySelector._coerce_float(value)
        if numeric is None:
            return None
        return int(numeric)

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