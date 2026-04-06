from __future__ import annotations

import base64
import json
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

ItemT = TypeVar("ItemT")


class CursorPage(BaseModel, Generic[ItemT]):
    items: list[ItemT] = Field(default_factory=list)
    next_cursor: str | None = None


def encode_cursor(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("utf-8")


def decode_cursor(cursor: str) -> dict[str, Any]:
    decoded = base64.urlsafe_b64decode(cursor.encode("utf-8"))
    payload = json.loads(decoded.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Cursor payload must be an object")
    return payload
