"""
Request ID builder for TradingAgents.
"""

import hashlib
from datetime import datetime
from typing import Optional


class RequestIdBuilder:
    """Builds unique request IDs for TradingAgents submissions."""

    @staticmethod
    def build(
        ticker: str,
        analysis_date: datetime,
        trigger_type: str,
        trigger_context: Optional[dict] = None,
    ) -> str:
        """
        Build a unique request ID based on request parameters.

        Format: TA-{timestamp}-{hash}
        Example: TA-20240404-abc123def
        """
        ticker_upper = ticker.upper()
        date_str = analysis_date.strftime("%Y%m%d")

        # Create hash from components
        context_str = str(trigger_context) if trigger_context else ""
        hash_input = f"{ticker_upper}:{date_str}:{trigger_type}:{context_str}:{datetime.utcnow().timestamp()}"
        hash_suffix = hashlib.sha256(hash_input.encode()).hexdigest()[:8]

        return f"TA-{date_str}-{hash_suffix}"

    @staticmethod
    def build_from_components(
        ticker: str,
        analysis_date: datetime,
        selected_analysts: Optional[list] = None,
        trigger_type: str = "scanner",
        trigger_context: Optional[dict] = None,
    ) -> str:
        """Build request ID including selected analysts."""
        analysts_str = ",".join(sorted(selected_analysts)) if selected_analysts else ""
        context_str = str(trigger_context) if trigger_context else ""

        hash_input = f"{ticker.upper()}:{analysis_date.isoformat()}:{trigger_type}:{analysts_str}:{context_str}"
        hash_suffix = hashlib.sha256(hash_input.encode()).hexdigest()[:8]

        date_str = analysis_date.strftime("%Y%m%d")
        return f"TA-{date_str}-{hash_suffix}"

    @staticmethod
    def parse(request_id: str) -> dict:
        """Parse a request ID into components."""
        if not request_id.startswith("TA-"):
            raise ValueError(f"Invalid request ID format: {request_id}")

        parts = request_id[3:].split("-", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid request ID format: {request_id}")

        date_str, hash_suffix = parts

        return {"date": date_str, "hash": hash_suffix, "is_valid": len(hash_suffix) == 8}
