"""
Request ID builder for TradingAgents.
"""

import hashlib
import re
from datetime import datetime
from typing import Optional


class RequestIdBuilder:
    """Builds unique request IDs for TradingAgents submissions."""

    @staticmethod
    def _slug(value: object, *, fallback: str, max_len: int) -> str:
        raw = str(value or "").strip().lower()
        if not raw:
            raw = fallback
        normalized = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
        return (normalized or fallback)[:max_len]

    @staticmethod
    def _stable_suffix(seed: str, size: int = 8) -> str:
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:size]

    @staticmethod
    def build(
        ticker: str,
        analysis_date: datetime,
        trigger_type: str,
        trigger_context: Optional[dict] = None,
    ) -> str:
        """
        Build a stable request ID with the integration-guide format.

        Format: <source>:<trigger-type>:<business-key>:<analysis-date>:<run-id>
        Example: scanner:candidate:nvda:2026-04-08:scanner-run-1842
        """
        ticker_key = RequestIdBuilder._slug(ticker, fallback="unknown", max_len=16)
        analysis_day = analysis_date.strftime("%Y-%m-%d")
        context = trigger_context or {}

        source = RequestIdBuilder._slug(
            context.get("source") if isinstance(context, dict) else None,
            fallback="scanner",
            max_len=20,
        )
        trigger = RequestIdBuilder._slug(
            trigger_type,
            fallback="candidate",
            max_len=20,
        )
        run_id_raw = ""
        if isinstance(context, dict):
            run_id_raw = str(context.get("run_id") or context.get("runId") or "")
        run_id = RequestIdBuilder._slug(run_id_raw, fallback="", max_len=24)
        if not run_id:
            run_id = RequestIdBuilder._stable_suffix(
                f"{source}:{trigger}:{ticker_key}:{analysis_day}:{context}"
            )

        return f"{source}:{trigger}:{ticker_key}:{analysis_day}:{run_id}"

    @staticmethod
    def build_from_components(
        ticker: str,
        analysis_date: datetime,
        selected_analysts: Optional[list] = None,
        trigger_type: str = "scanner",
        trigger_context: Optional[dict] = None,
    ) -> str:
        """Build a stable request ID including selected analysts context."""
        context = dict(trigger_context or {})
        analysts = sorted(str(item).strip().lower() for item in (selected_analysts or []) if item)
        if analysts:
            context.setdefault("analysts", analysts)
        return RequestIdBuilder.build(
            ticker=ticker,
            analysis_date=analysis_date,
            trigger_type=trigger_type,
            trigger_context=context,
        )

    @staticmethod
    def parse(request_id: str) -> dict:
        """Parse a request ID into components."""
        if not request_id.startswith("TA-"):
            parts = request_id.split(":")
            if len(parts) != 5:
                raise ValueError(f"Invalid request ID format: {request_id}")
            source, trigger, business_key, date_str, run_id = parts
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError(f"Invalid request ID date: {request_id}") from exc
            return {
                "source": source,
                "trigger_type": trigger,
                "business_key": business_key,
                "date": date_str,
                "run_id": run_id,
                "is_valid": bool(source and trigger and business_key and run_id),
                "format": "integration-v1",
            }

        parts = request_id[3:].split("-", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid request ID format: {request_id}")

        date_str, hash_suffix = parts

        return {
            "date": date_str,
            "hash": hash_suffix,
            "is_valid": len(hash_suffix) >= 8,
            "format": "legacy",
        }
