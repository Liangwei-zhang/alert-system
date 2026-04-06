from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from domains.market_data.quality_service import OhlcvQualityService


class OhlcvImportService:
    def __init__(
        self,
        session: Any,
        *,
        repository: Any | None = None,
        quality_service: OhlcvQualityService | None = None,
        publisher: Any | None = None,
    ) -> None:
        self.session = session
        self.repository = repository
        self.quality_service = quality_service or OhlcvQualityService()
        self.publisher = publisher

    async def import_batch(
        self,
        symbol: str,
        timeframe: str,
        bars: list[dict[str, Any]],
        *,
        source: str = "marketdata.worker",
    ) -> dict[str, Any]:
        normalized_rows: list[dict[str, Any]] = []
        anomalies: list[dict[str, Any]] = []

        for raw in bars:
            try:
                normalized_rows.append(self.normalize_bar(raw, symbol, timeframe))
            except ValueError as exc:
                anomalies.append(
                    {
                        "code": "normalization_error",
                        "severity": "error",
                        "timestamp": self._try_timestamp(raw),
                        "details": {"error": str(exc), "row": raw},
                    }
                )

        report = self.quality_service.validate_batch(symbol, timeframe, normalized_rows)
        anomalies.extend(report["anomalies"])

        repository = self.repository or self._build_repository()
        if anomalies:
            await repository.quarantine_bad_rows(symbol, timeframe, anomalies, source=source)
        saved_rows = await repository.bulk_upsert_bars(
            symbol,
            timeframe,
            report["valid_rows"],
            source=source,
        )

        publisher = self.publisher or self._build_publisher()
        await self.quality_service.emit_quality_event(
            publisher,
            symbol=symbol,
            timeframe=timeframe,
            imported_count=len(saved_rows),
            anomaly_count=len(anomalies),
            source=source,
        )
        await publisher.publish_after_commit(
            topic="ops.audit.logged",
            key=f"{symbol.upper()}:{timeframe.lower()}",
            payload={
                "entity": "market_data",
                "entity_id": symbol.upper(),
                "action": "ohlcv.imported",
                "source": source,
                "timeframe": timeframe.lower(),
                "imported_count": len(saved_rows),
                "anomaly_count": len(anomalies),
            },
        )
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe.lower(),
            "imported_count": len(saved_rows),
            "anomaly_count": len(anomalies),
        }

    def normalize_bar(self, raw: dict[str, Any], symbol: str, timeframe: str) -> dict[str, Any]:
        timestamp = self._coerce_timestamp(
            raw.get("timestamp") or raw.get("bar_time") or raw.get("date") or raw.get("datetime")
        )
        if timestamp is None:
            raise ValueError("timestamp is required")

        def parse_float(name: str) -> float:
            value = raw.get(name)
            if value in (None, ""):
                raise ValueError(f"{name} is required")
            try:
                return float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be numeric") from exc

        return {
            "symbol": symbol.strip().upper(),
            "timeframe": timeframe.strip().lower(),
            "timestamp": timestamp,
            "open": parse_float("open"),
            "high": parse_float("high"),
            "low": parse_float("low"),
            "close": parse_float("close"),
            "volume": float(raw.get("volume", 0) or 0),
            "source": raw.get("source"),
        }

    def _build_repository(self) -> Any:
        from domains.market_data.repository import OhlcvRepository

        return OhlcvRepository(self.session)

    def _build_publisher(self) -> Any:
        from infra.events.outbox import OutboxPublisher

        return OutboxPublisher(self.session)

    @staticmethod
    def _coerce_timestamp(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        if isinstance(value, str) and value.strip():
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        return None

    def _try_timestamp(self, raw: dict[str, Any]) -> datetime | None:
        return self._coerce_timestamp(
            raw.get("timestamp") or raw.get("bar_time") or raw.get("date") or raw.get("datetime")
        )
