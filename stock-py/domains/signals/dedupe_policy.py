from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SignalDedupePolicy:
    def __init__(self, cooldown_minutes: int = 60) -> None:
        self.cooldown = timedelta(minutes=cooldown_minutes)

    def build_dedupe_key(
        self,
        symbol: str,
        signal_type: str,
        strategy_window: str | None,
        market_regime: str | None,
    ) -> str:
        normalized_symbol = symbol.strip().upper()
        normalized_type = signal_type.strip().lower()
        normalized_window = (strategy_window or "default").strip().lower().replace(" ", "-")
        normalized_regime = (market_regime or "unknown").strip().lower().replace(" ", "-")
        return ":".join([normalized_symbol, normalized_type, normalized_window, normalized_regime])

    def should_suppress(
        self,
        *,
        existing_generated_at: datetime | None,
        existing_dedupe_key: str | None,
        candidate_dedupe_key: str,
        now: datetime | None = None,
    ) -> bool:
        if existing_generated_at is None or existing_dedupe_key is None:
            return False
        if existing_generated_at.tzinfo is None:
            existing_generated_at = existing_generated_at.replace(tzinfo=timezone.utc)
        reference_time = now or utcnow()
        return (
            existing_dedupe_key == candidate_dedupe_key
            and existing_generated_at >= reference_time - self.cooldown
        )
