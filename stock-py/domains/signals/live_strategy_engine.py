from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

try:
    from domains.signals.schemas import SignalCandidate as SignalCandidateModel
except Exception:  # pragma: no cover - optional in dependency-light environments
    SignalCandidateModel = None


class LiveStrategyEngine:
    BENCHMARK_ONLY_SOURCE_STRATEGIES = {"buy_and_hold", "sma_cross"}
    BREAKOUT_MIN_SIGNAL_SCORE = 60.0
    RANKING_STRATEGY_ALIASES = {
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

        rankings = self._normalize_strategy_rankings(
            market_snapshot.get("strategy_rankings") or context.get("strategy_rankings")
        )
        if rankings:
            ranked_candidates = self._build_ranking_candidates(
                rankings,
                market_snapshot,
                timeframe=timeframe,
                market_regime=market_regime,
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

        selection = {
            "strategy": strategy,
            "strategy_window": timeframe,
            "market_regime": market_regime,
            "source": "heuristic",
            "source_strategy": strategy,
            "rank": None,
            "ranking_score": 4.0,
            "signal_fit_score": round(self._strategy_fit_score(strategy, market_snapshot), 4),
            "regime_bias": round(self._regime_bias(strategy, market_regime), 4),
            "degradation_penalty": 0.0,
            "stable": True,
        }
        selection["combined_score"] = round(
            float(selection["ranking_score"])
            + float(selection["signal_fit_score"])
            + float(selection["regime_bias"])
            + (self._current_signal_score(market_snapshot) * 0.12),
            4,
        )
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

        base_score = self._coerce_float(market_snapshot.get("score"))
        if base_score is None:
            base_score = float(
                self.score_candidate(
                    {
                        "type": signal_type,
                        "confidence": confidence,
                        "probability": probability,
                        "risk_reward_ratio": risk_reward_ratio,
                        "analysis": analysis,
                    }
                )
            )

        candidate_payload = {
            "symbol": symbol.strip().upper(),
            "type": signal_type,
            "score": self._adjust_score_with_selection(base_score, strategy),
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

            source_strategy = self._normalize_strategy_name(
                data.get("strategy_name") or data.get("strategy_id") or data.get("strategy")
            )
            strategy = self.RANKING_STRATEGY_ALIASES.get(source_strategy)
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
        market_regime: str,
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
            signal_fit_score = self._strategy_fit_score(strategy, market_snapshot)
            regime_bias = self._regime_bias(strategy, market_regime)
            degradation_penalty = min(18.0, max(0.0, float(ranking.get("degradation") or 0.0)))
            stability_bonus = 4.0 if bool(evidence.get("stable")) else 0.0
            coverage_bonus = min(3.0, float(ranking.get("symbols_covered") or 0) / 150.0)
            timeframe_bonus = self._timeframe_bonus(timeframe, evidence)
            combined_score = round(
                ranking_score
                + signal_fit_score
                + regime_bias
                + stability_bonus
                + coverage_bonus
                + timeframe_bonus
                + current_signal_bonus
                - degradation_penalty,
                4,
            )

            candidate = {
                "strategy": strategy,
                "strategy_window": timeframe,
                "market_regime": market_regime,
                "source": "ranking",
                "source_strategy": ranking["source_strategy"],
                "rank": ranking.get("rank"),
                "ranking_score": round(ranking_score, 4),
                "signal_fit_score": round(signal_fit_score, 4),
                "regime_bias": round(regime_bias, 4),
                "degradation_penalty": round(degradation_penalty, 4),
                "combined_score": combined_score,
                "stable": bool(evidence.get("stable", False)),
                "symbols_covered": int(ranking.get("symbols_covered") or 0),
                "evidence": evidence,
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
        normalized_strategy = self._normalize_strategy_name(strategy)
        normalized_source_strategy = self._normalize_strategy_name(source_strategy)

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

    def _adjust_score_with_selection(self, base_score: float, strategy: dict[str, Any]) -> int:
        combined_score = self._coerce_float(strategy.get("combined_score")) or 0.0
        selection_adjustment = max(-12.0, min(12.0, (combined_score - 20.0) * 0.55))
        alert_decision = strategy.get("alert_decision")
        if isinstance(alert_decision, dict) and not alert_decision.get("publish_allowed", True):
            selection_adjustment -= 6.0
        return int(max(0, min(100, round(base_score + selection_adjustment))))

    def _strategy_fit_score(self, strategy: str, market_snapshot: dict[str, Any]) -> float:
        analysis = market_snapshot.get("analysis") if isinstance(market_snapshot.get("analysis"), dict) else {}
        dislocation = min(1.0, abs(self._coerce_float(market_snapshot.get("dislocation_pct")) or 0.0) / 0.08)
        momentum = min(1.0, abs(self._coerce_float(market_snapshot.get("momentum_score")) or 0.0))
        trend = min(1.0, abs(self._coerce_float(market_snapshot.get("trend_strength")) or 0.0))
        volatility = min(1.0, abs(self._coerce_float(market_snapshot.get("volatility_score")) or 0.0))
        volume_confirmed = self._truthy(analysis.get("volume_confirmed"))
        trend_confirmed = self._truthy(analysis.get("trend_confirmed"))
        reversal_confirmed = self._truthy(analysis.get("reversal_confirmed"))
        low_trend = max(0.0, 1.0 - trend)
        low_volatility = max(0.0, 1.0 - volatility)

        if strategy == "mean_reversion":
            return (dislocation * 14.0) + (6.0 if reversal_confirmed else 0.0) + (low_trend * 4.0) + (
                low_volatility * 2.0
            )
        if strategy == "trend_continuation":
            return (trend * 11.0) + (momentum * 9.0) + (5.0 if trend_confirmed else 0.0) + (
                4.0 if volume_confirmed else 0.0
            )
        if strategy == "volatility_breakout":
            return (volatility * 11.0) + (momentum * 5.0) + (6.0 if volume_confirmed else 0.0) + (
                4.0 if trend_confirmed else 0.0
            )
        return (low_trend * 8.0) + (low_volatility * 6.0) + (dislocation * 4.0) + (
            3.0 if reversal_confirmed else 0.0
        )

    def _regime_bias(self, strategy: str, market_regime: str) -> float:
        normalized_regime = self._normalize_market_regime(market_regime)
        if normalized_regime == "trend":
            if strategy == "trend_continuation":
                return 8.0
            if strategy == "volatility_breakout":
                return 4.0
            if strategy == "mean_reversion":
                return -3.0
            if strategy == "range_rotation":
                return -2.0
        if normalized_regime == "volatile":
            if strategy == "volatility_breakout":
                return 8.0
            if strategy == "mean_reversion":
                return 3.0
            if strategy == "trend_continuation":
                return -2.0
            if strategy == "range_rotation":
                return -1.0
        if normalized_regime == "range":
            if strategy == "range_rotation":
                return 8.0
            if strategy == "mean_reversion":
                return 6.0
            if strategy == "trend_continuation":
                return -4.0
            if strategy == "volatility_breakout":
                return -1.0
        return 0.0

    def _timeframe_bonus(self, timeframe: str, evidence: dict[str, Any]) -> float:
        windows = evidence.get("windows") if isinstance(evidence.get("windows"), dict) else {}
        if not windows:
            return 0.0
        best_window_days = self._coerce_int(evidence.get("best_window_days")) or 0
        if timeframe == "1d" and best_window_days in {30, 90, 180, 365}:
            return 1.5
        return 0.0

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

    def _public_candidate_view(self, candidate: dict[str, Any]) -> dict[str, Any]:
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
        }

    @classmethod
    def _normalize_strategy_name(cls, value: Any) -> str:
        return str(value or "").strip().lower().replace(" ", "_")

    @classmethod
    def _normalize_market_regime(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"bull", "bear", "trend", "trend_up", "trend_down"}:
            return "trend"
        if normalized in {"volatile", "high_volatility"}:
            return "volatile"
        if normalized in {"range", "sideways"}:
            return "range"
        return normalized or "range"

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

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        numeric = LiveStrategyEngine._coerce_float(value)
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
