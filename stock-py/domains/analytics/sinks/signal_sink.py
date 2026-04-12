from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from infra.analytics.clickhouse_client import ClickHouseClient


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SignalAnalyticsSink:
    def __init__(self, client: ClickHouseClient) -> None:
        self.client = client

    async def handle_signal_generated(self, payload: dict[str, Any]) -> dict[str, Any]:
        analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
        exit_levels = analysis.get("exit_levels") if isinstance(analysis.get("exit_levels"), dict) else {}
        row = {
            "occurred_at": payload.get("occurred_at") or utcnow(),
            "signal_id": payload.get("signal_id"),
            "symbol": str(payload.get("symbol") or "UNKNOWN").upper(),
            "signal_type": str(payload.get("signal_type") or "signal").lower(),
            "price": payload.get("price"),
            "entry_price": payload.get("entry_price") or payload.get("price"),
            "score": payload.get("score"),
            "source": payload.get("source") or "unknown",
            "strategy": analysis.get("strategy") or payload.get("strategy") or "unknown",
            "strategy_window": payload.get("strategy_window")
            or analysis.get("strategy_window")
            or "default",
            "market_regime": payload.get("market_regime")
            or analysis.get("market_regime")
            or "unknown",
            "market_regime_detail": analysis.get("market_regime_detail"),
            "risk_reward_ratio": payload.get("risk_reward_ratio")
            or analysis.get("risk_reward_ratio"),
            "atr_multiplier": payload.get("atr_multiplier")
            or analysis.get("atr_multiplier")
            or exit_levels.get("atr_multiplier"),
            "stop_loss": payload.get("stop_loss")
            or analysis.get("stop_loss")
            or exit_levels.get("stop_loss"),
            "take_profit_1": payload.get("take_profit_1")
            or analysis.get("take_profit_1")
            or exit_levels.get("take_profit_1"),
            "take_profit_2": payload.get("take_profit_2")
            or analysis.get("take_profit_2")
            or exit_levels.get("take_profit_2"),
            "take_profit_3": payload.get("take_profit_3")
            or analysis.get("take_profit_3")
            or exit_levels.get("take_profit_3"),
            "calibration_version": analysis.get("calibration_version"),
            "analysis": analysis,
            "recipient_count": len(payload.get("user_ids") or []),
            "user_ids": payload.get("user_ids") or [],
        }
        await self.client.insert_rows("signal_events", [row])
        return row

    async def handle_scanner_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            "occurred_at": payload.get("occurred_at") or utcnow(),
            "decision_id": payload.get("decision_id"),
            "run_id": payload.get("run_id"),
            "symbol": str(payload.get("symbol") or "UNKNOWN").upper(),
            "decision": payload.get("decision") or "unknown",
            "reason": payload.get("reason") or "",
            "signal_type": payload.get("signal_type"),
            "score": payload.get("score"),
            "suppressed": bool(payload.get("suppressed", False)),
            "dedupe_key": payload.get("dedupe_key"),
            "strategy": payload.get("strategy") or "unknown",
        }
        await self.client.insert_rows("scanner_decision_events", [row])
        return row

    async def handle_strategy_rankings_refreshed(
        self, payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for ranking in payload.get("rankings") or []:
            evidence = ranking.get("evidence") if isinstance(ranking.get("evidence"), dict) else {}
            rows.append(
                {
                    "occurred_at": payload.get("occurred_at") or utcnow(),
                    "strategy_name": ranking.get("strategy_name") or "unknown",
                    "rank": int(ranking.get("rank") or 0),
                    "score": float(ranking.get("score") or 0.0),
                    "degradation": float(ranking.get("degradation") or 0.0),
                    "symbols_covered": int(ranking.get("symbols_covered") or 0),
                    "timeframe": payload.get("timeframe") or ranking.get("timeframe") or "1d",
                    "stable": bool(evidence.get("stable", ranking.get("degradation", 0.0) < 5.0)),
                    "top_symbols": self._extract_top_symbols(ranking, evidence),
                    "evidence": evidence,
                }
            )
        if rows:
            await self.client.insert_rows("strategy_health_events", rows)
        return rows

    @staticmethod
    def _extract_top_symbols(
        ranking: dict[str, Any], evidence: dict[str, Any]
    ) -> list[dict[str, Any]]:
        if isinstance(ranking.get("top_symbols"), list):
            return ranking["top_symbols"]
        windows = evidence.get("windows") if isinstance(evidence.get("windows"), dict) else {}
        for window_data in windows.values():
            if isinstance(window_data, dict) and isinstance(window_data.get("top_symbols"), list):
                return window_data["top_symbols"]
        return []
