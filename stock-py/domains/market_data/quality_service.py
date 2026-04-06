from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


class OhlcvQualityService:
    _timeframe_steps = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "1d": timedelta(days=1),
        "1w": timedelta(days=7),
    }

    def validate_batch(
        self,
        symbol: str,
        timeframe: str,
        bars: list[dict[str, Any]],
    ) -> dict[str, Any]:
        anomalies: list[dict[str, Any]] = []
        symbol = symbol.strip().upper()
        timeframe = timeframe.strip().lower()

        previous_input_time: datetime | None = None
        for bar in bars:
            timestamp = self._coerce_timestamp(bar.get("timestamp"))
            if timestamp is None:
                continue
            if previous_input_time is not None and timestamp < previous_input_time:
                anomalies.append(
                    {
                        "code": "time_reversal",
                        "severity": "warning",
                        "timestamp": timestamp,
                        "details": {"symbol": symbol, "timeframe": timeframe},
                    }
                )
            previous_input_time = timestamp

        valid_rows: list[dict[str, Any]] = []
        seen: set[datetime] = set()
        expected_step = self._timeframe_steps.get(timeframe, timedelta(days=1))
        gap_threshold = expected_step * (
            4 if timeframe.endswith("d") or timeframe.endswith("w") else 2
        )
        previous_valid_time: datetime | None = None

        for bar in sorted(bars, key=lambda item: self._sort_key(item.get("timestamp"))):
            normalized = self._normalize_bar(symbol, timeframe, bar)
            if normalized is None:
                anomalies.append(
                    {
                        "code": "invalid_row",
                        "severity": "error",
                        "timestamp": self._coerce_timestamp(bar.get("timestamp")),
                        "details": {"symbol": symbol, "timeframe": timeframe, "row": bar},
                    }
                )
                continue

            timestamp = normalized["timestamp"]
            if timestamp in seen:
                anomalies.append(
                    {
                        "code": "duplicate_bar",
                        "severity": "warning",
                        "timestamp": timestamp,
                        "details": {"symbol": symbol, "timeframe": timeframe},
                    }
                )
                continue

            if previous_valid_time is not None and timestamp - previous_valid_time > gap_threshold:
                anomalies.append(
                    {
                        "code": "missing_bar_gap",
                        "severity": "warning",
                        "timestamp": timestamp,
                        "details": {
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "previous_timestamp": previous_valid_time.isoformat(),
                            "current_timestamp": timestamp.isoformat(),
                        },
                    }
                )

            seen.add(timestamp)
            previous_valid_time = timestamp
            valid_rows.append(normalized)

        return {
            "valid_rows": valid_rows,
            "anomalies": anomalies,
            "stats": {
                "symbol": symbol,
                "timeframe": timeframe,
                "received_count": len(bars),
                "valid_count": len(valid_rows),
                "anomaly_count": len(anomalies),
            },
        }

    async def emit_quality_event(
        self,
        publisher: Any,
        *,
        symbol: str,
        timeframe: str,
        imported_count: int,
        anomaly_count: int,
        source: str,
    ) -> None:
        payload = {
            "symbol": symbol.strip().upper(),
            "timeframe": timeframe.strip().lower(),
            "imported_count": imported_count,
            "anomaly_count": anomaly_count,
            "source": source,
        }
        await publisher.publish_after_commit(
            topic="marketdata.ohlcv.imported",
            key=f"{payload['symbol']}:{payload['timeframe']}",
            payload=payload,
        )

    @staticmethod
    def _sort_key(value: Any) -> tuple[int, str]:
        timestamp = OhlcvQualityService._coerce_timestamp(value)
        if timestamp is None:
            return (1, "")
        return (0, timestamp.isoformat())

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

    def _normalize_bar(
        self, symbol: str, timeframe: str, bar: dict[str, Any]
    ) -> dict[str, Any] | None:
        timestamp = self._coerce_timestamp(bar.get("timestamp"))
        if timestamp is None:
            return None

        try:
            opened = float(bar.get("open"))
            high = float(bar.get("high"))
            low = float(bar.get("low"))
            close = float(bar.get("close"))
            volume = float(bar.get("volume", 0) or 0)
        except (TypeError, ValueError):
            return None

        if min(opened, high, low, close) <= 0 or volume < 0:
            return None
        if high < max(opened, close, low):
            return None
        if low > min(opened, close, high):
            return None

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": timestamp,
            "open": opened,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "source": bar.get("source"),
        }
