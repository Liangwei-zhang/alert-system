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
        row = {
            "occurred_at": payload.get("occurred_at") or utcnow(),
            "signal_id": payload.get("signal_id"),
            "symbol": str(payload.get("symbol") or "UNKNOWN").upper(),
            "signal_type": str(payload.get("signal_type") or "signal").lower(),
            "price": payload.get("price"),
            "score": payload.get("score"),
            "source": payload.get("source") or "unknown",
            "strategy": analysis.get("strategy") or payload.get("strategy") or "unknown",
            "strategy_window": payload.get("strategy_window")
            or analysis.get("strategy_window")
            or "default",
            "market_regime": payload.get("market_regime")
            or analysis.get("market_regime")
            or "unknown",
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
