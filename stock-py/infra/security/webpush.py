from __future__ import annotations

from functools import lru_cache

from py_vapid import Vapid, Vapid01


def normalize_vapid_private_key(value: str) -> str:
    return str(value or "").replace("\\n", "\n").strip()


@lru_cache(maxsize=4)
def load_vapid_private_key(value: str) -> Vapid01:
    normalized = normalize_vapid_private_key(value)
    if not normalized:
        raise ValueError("Web Push private key is not configured")
    if "-----BEGIN" in normalized:
        return Vapid.from_pem(normalized.encode("utf8"))
    return Vapid.from_string(normalized)