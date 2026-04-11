from __future__ import annotations

import json
from typing import Any


def deserialize_portfolio_extra(raw_extra: Any) -> dict[str, Any] | None:
    if raw_extra is None:
        return None
    if isinstance(raw_extra, dict):
        return raw_extra
    if not isinstance(raw_extra, str):
        return None

    payload = raw_extra.strip()
    if not payload:
        return None

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed