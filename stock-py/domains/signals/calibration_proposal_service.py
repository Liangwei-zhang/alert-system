from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any

from domains.analytics.repository import AnalyticsRepository
from domains.signals.calibration_repository import SignalCalibrationSnapshotRepository
from domains.signals.calibration_service import CalibrationService
from domains.signals.strategy_profiles import normalize_strategy_name, resolve_strategy_name


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CalibrationProposalService:
    def __init__(
        self,
        analytics_repository: AnalyticsRepository,
        calibration_repository: SignalCalibrationSnapshotRepository,
        calibration_service: CalibrationService | None = None,
    ) -> None:
        self.analytics_repository = analytics_repository
        self.calibration_repository = calibration_repository
        self.calibration_service = calibration_service or CalibrationService()

    async def build_proposal(
        self,
        *,
        signal_window_hours: int = 24,
        ranking_window_hours: int = 24 * 7,
    ) -> dict[str, Any]:
        active_snapshot_payload = await self.calibration_repository.get_active_snapshot()
        current_snapshot = self.calibration_service.normalize_snapshot(active_snapshot_payload)
        strategy_health = await self.analytics_repository.query_strategy_health(ranking_window_hours)
        signal_results = await self.analytics_repository.query_signal_results(signal_window_hours)

        canonical_health = self._canonical_strategy_health(strategy_health.get("strategies") or [])
        canonical_live_counts = self._canonical_signal_strategy_counts(
            signal_results.get("signal_strategies") or []
        )
        total_live_strategy_signals = sum(canonical_live_counts.values())

        proposed_strategy_weights: dict[str, float] = {}
        strategy_adjustments = []
        for strategy in self.calibration_service.DEFAULT_STRATEGY_WEIGHTS:
            current_weight = self.calibration_service.strategy_weight(strategy, current_snapshot)
            health_entry = canonical_health.get(strategy)
            live_count = canonical_live_counts.get(strategy, 0)
            proposed_weight, reasons = self._propose_strategy_weight(
                strategy=strategy,
                current_weight=current_weight,
                health_entry=health_entry,
                live_count=live_count,
                total_live_strategy_signals=total_live_strategy_signals,
            )
            proposed_strategy_weights[strategy] = proposed_weight
            strategy_adjustments.append(
                {
                    "key": strategy,
                    "current_value": round(current_weight, 4),
                    "proposed_value": round(proposed_weight, 4),
                    "delta": round(proposed_weight - current_weight, 4),
                    "reasons": reasons,
                }
            )

        proposed_score_multipliers, score_multiplier_adjustments = self._propose_score_multipliers(
            current_snapshot=current_snapshot,
            signal_results=signal_results,
        )

        generated_at = utcnow()
        proposed_version = self._proposal_version(generated_at)
        derived_from = self._derived_from(strategy_health, signal_results)
        summary = {
            "total_signals": int(signal_results.get("total_signals") or 0),
            "total_trade_actions": int(signal_results.get("total_trade_actions") or 0),
            "trade_action_rate": round(float(signal_results.get("trade_action_rate") or 0.0), 4),
            "executed_trade_rate": round(
                float(signal_results.get("executed_trade_rate") or 0.0),
                4,
            ),
            "overlapping_symbols": int(signal_results.get("overlapping_symbols") or 0),
            "active_calibration_version": current_snapshot.version,
        }

        notes = self._proposal_notes(
            summary=summary,
            strategy_health=strategy_health,
            canonical_health=canonical_health,
        )

        strategy_adjustments.sort(
            key=lambda item: (-abs(float(item["delta"])), item["key"])
        )
        score_multiplier_adjustments.sort(
            key=lambda item: (-abs(float(item["delta"])), item["key"])
        )

        return {
            "generated_at": generated_at,
            "signal_window_hours": int(signal_window_hours),
            "ranking_window_hours": int(ranking_window_hours),
            "current_version": current_snapshot.version,
            "proposed_version": proposed_version,
            "strategy_health_refreshed_at": strategy_health.get("refreshed_at"),
            "signal_generated_after": signal_results.get("generated_after"),
            "summary": summary,
            "strategy_weights": strategy_adjustments,
            "score_multipliers": score_multiplier_adjustments,
            "notes": notes,
            "snapshot_payload": {
                "version": proposed_version,
                "source": "proposal",
                "strategy_weights": proposed_strategy_weights,
                "score_multipliers": proposed_score_multipliers,
                "derived_from": derived_from,
                "sample_size": summary["total_signals"],
                "notes": "; ".join(notes),
            },
        }

    def _propose_strategy_weight(
        self,
        *,
        strategy: str,
        current_weight: float,
        health_entry: dict[str, Any] | None,
        live_count: int,
        total_live_strategy_signals: int,
    ) -> tuple[float, list[str]]:
        if health_entry is None and live_count <= 0:
            return round(current_weight, 4), [
                "No recent ranking or live signal evidence; keep current weight.",
            ]

        adjustment = 0.0
        reasons: list[str] = []
        if health_entry is not None:
            rank = int(health_entry.get("rank") or 0)
            score = float(health_entry.get("score") or 0.0)
            degradation = float(health_entry.get("degradation") or 0.0)
            stable = bool(health_entry.get("stable", True))

            if rank > 0:
                rank_bonus = max(0.0, (5 - min(rank, 5)) * 0.01)
                adjustment += rank_bonus
                reasons.append(f"Rank {rank} adds {rank_bonus:+.2f} support.")

            score_adjustment = max(-0.02, min(0.03, (score - 1.0) * 0.05))
            if score_adjustment:
                adjustment += score_adjustment
                reasons.append(f"Backtest score {score:.2f} contributes {score_adjustment:+.2f}.")

            degradation_penalty = min(0.06, max(0.0, degradation) / 200.0)
            if degradation_penalty:
                adjustment -= degradation_penalty
                reasons.append(
                    f"Degradation {degradation:.2f} trims {degradation_penalty:.2f}."
                )

            stability_adjustment = 0.02 if stable else -0.02
            adjustment += stability_adjustment
            reasons.append(
                "Stable ranking evidence supports this strategy."
                if stable
                else "Unstable ranking evidence dampens this strategy."
            )

        if total_live_strategy_signals >= 8:
            expected_share = 1.0 / len(self.calibration_service.DEFAULT_STRATEGY_WEIGHTS)
            live_share = live_count / total_live_strategy_signals
            live_adjustment = max(-0.02, min(0.03, (live_share - expected_share) * 0.12))
            adjustment += live_adjustment
            reasons.append(
                f"Live signal share {live_share:.0%} shifts weight by {live_adjustment:+.2f}."
            )
        elif live_count > 0:
            reasons.append("Live sample is still thin, so the signal share effect is muted.")

        proposed_weight = self.calibration_service._bounded_multiplier(
            current_weight * (1.0 + adjustment)
        )
        return round(proposed_weight, 4), reasons

    def _propose_score_multipliers(
        self,
        *,
        current_snapshot: Any,
        signal_results: dict[str, Any],
    ) -> tuple[dict[str, float], list[dict[str, Any]]]:
        total_signals = int(signal_results.get("total_signals") or 0)
        trade_action_rate = float(signal_results.get("trade_action_rate") or 0.0)
        executed_trade_rate = float(signal_results.get("executed_trade_rate") or 0.0)
        dominant_regime = self._dominant_bucket_key(signal_results.get("market_regimes") or [])
        dominant_strategy = self._canonical_strategy_name(
            self._dominant_bucket_key(signal_results.get("signal_strategies") or [])
        )

        proposed: dict[str, float] = {}
        adjustments: list[dict[str, Any]] = []
        for factor in self.calibration_service.DEFAULT_SCORE_MULTIPLIERS:
            current_value = self.calibration_service.score_multiplier(factor, current_snapshot)
            reasons: list[str] = []
            adjustment = 0.0

            if total_signals < 25:
                reasons.append("Live sample is below 25 signals; keep multiplier near neutral.")
            else:
                if factor in {"confidence", "probability", "quality", "risk_reward"}:
                    if executed_trade_rate < 20.0:
                        delta = -0.04 if factor != "risk_reward" else -0.03
                        adjustment += delta
                        reasons.append(
                            "Low executed-trade rate suggests tightening positive scoring."
                        )
                    elif executed_trade_rate >= 35.0:
                        delta = 0.02 if factor != "risk_reward" else 0.015
                        adjustment += delta
                        reasons.append(
                            "Healthy executed-trade rate allows a modest positive bias."
                        )
                    if trade_action_rate >= 80.0 and factor in {"quality", "risk_reward"}:
                        adjustment -= 0.01
                        reasons.append(
                            "High action volume relative to signals keeps quality thresholds firmer."
                        )

                if factor in {"stale_penalty", "liquidity_penalty"}:
                    if executed_trade_rate < 20.0 or trade_action_rate >= 80.0:
                        adjustment += 0.05
                        reasons.append(
                            "Low conversion or high action load increases penalty pressure."
                        )
                    elif executed_trade_rate >= 35.0:
                        adjustment -= 0.02
                        reasons.append(
                            "Healthy conversion allows slightly softer penalty multipliers."
                        )

                if factor == "trend":
                    if dominant_regime in {"trend", "trend_up", "trend_down"} or dominant_strategy == "trend_continuation":
                        adjustment += 0.04
                        reasons.append("Trend-dominant live conditions support trend scoring.")
                    elif dominant_regime == "range":
                        adjustment -= 0.03
                        reasons.append("Range-dominant live conditions reduce trend emphasis.")

                if factor == "reversal":
                    if dominant_regime == "range":
                        adjustment += 0.04
                        reasons.append("Range conditions support reversal scoring.")
                    elif dominant_regime in {"trend", "trend_up", "trend_down"}:
                        adjustment -= 0.02
                        reasons.append("Trend conditions slightly reduce reversal bias.")

                if factor == "volume":
                    if dominant_strategy == "volatility_breakout" or dominant_regime in {"volatile", "breakout_candidate"}:
                        adjustment += 0.03
                        reasons.append("Breakout or volatile conditions increase volume confirmation value.")

            proposed_value = self.calibration_service._bounded_multiplier(
                current_value * (1.0 + adjustment)
            )
            proposed[factor] = round(proposed_value, 4)
            adjustments.append(
                {
                    "key": factor,
                    "current_value": round(current_value, 4),
                    "proposed_value": round(proposed_value, 4),
                    "delta": round(proposed_value - current_value, 4),
                    "reasons": reasons or ["No directional evidence; keep current multiplier."],
                }
            )

        return proposed, adjustments

    def _canonical_strategy_health(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            canonical = self._canonical_strategy_name(row.get("strategy_name"))
            if canonical is None:
                continue
            entry = grouped.setdefault(
                canonical,
                {
                    "rank": None,
                    "score_values": [],
                    "degradation_values": [],
                    "stable_values": [],
                    "signals_generated": 0,
                },
            )
            rank = int(row.get("rank") or 0)
            if rank > 0:
                entry["rank"] = rank if entry["rank"] is None else min(entry["rank"], rank)
            entry["score_values"].append(float(row.get("score") or 0.0))
            entry["degradation_values"].append(float(row.get("degradation") or 0.0))
            entry["stable_values"].append(bool(row.get("stable", True)))
            entry["signals_generated"] += int(row.get("signals_generated") or 0)

        return {
            strategy: {
                "rank": values["rank"] or 0,
                "score": round(max(values["score_values"] or [0.0]), 4),
                "degradation": round(mean(values["degradation_values"] or [0.0]), 4),
                "stable": any(values["stable_values"]),
                "signals_generated": values["signals_generated"],
            }
            for strategy, values in grouped.items()
        }

    def _canonical_signal_strategy_counts(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        grouped: dict[str, int] = {}
        for row in rows:
            canonical = self._canonical_strategy_name(row.get("key"))
            if canonical is None:
                continue
            grouped[canonical] = grouped.get(canonical, 0) + int(row.get("count") or 0)
        return grouped

    @staticmethod
    def _dominant_bucket_key(rows: list[dict[str, Any]]) -> str | None:
        if not rows:
            return None
        first = rows[0]
        if not isinstance(first, dict):
            return None
        value = first.get("key")
        return str(value).strip() if value not in (None, "") else None

    @staticmethod
    def _proposal_version(generated_at: datetime) -> str:
        return f"signals-v2-proposal-{generated_at:%Y%m%d}"

    @staticmethod
    def _derived_from(strategy_health: dict[str, Any], signal_results: dict[str, Any]) -> str:
        refreshed_at = strategy_health.get("refreshed_at")
        generated_after = signal_results.get("generated_after")
        refreshed_text = refreshed_at.isoformat() if isinstance(refreshed_at, datetime) else "unknown"
        generated_text = (
            generated_after.isoformat() if isinstance(generated_after, datetime) else "unknown"
        )
        return f"strategy-health:{refreshed_text} + signal-results:{generated_text}"

    @staticmethod
    def _proposal_notes(
        *,
        summary: dict[str, Any],
        strategy_health: dict[str, Any],
        canonical_health: dict[str, dict[str, Any]],
    ) -> list[str]:
        notes = [
            f"{summary['total_signals']} live signals and {summary['total_trade_actions']} trade actions fed this proposal.",
        ]
        if summary["total_signals"] < 25:
            notes.append("Live sample is still thin; review manually before turning this into an active snapshot.")
        refreshed_at = strategy_health.get("refreshed_at")
        if isinstance(refreshed_at, datetime):
            notes.append(f"Backtest strategy health last refreshed at {refreshed_at.isoformat()}.")
        if not canonical_health:
            notes.append("No canonical backtest strategy evidence was available, so the proposal stayed conservative.")
        return notes

    def _canonical_strategy_name(self, value: Any) -> str | None:
        resolved = resolve_strategy_name(value)
        if resolved:
            return resolved
        normalized = normalize_strategy_name(value)
        if normalized in self.calibration_service.DEFAULT_STRATEGY_WEIGHTS:
            return normalized
        return None