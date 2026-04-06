from __future__ import annotations

import os
import sys

REQUIRED_ENV_HELP = {
    "LOAD_TEST_HOST": "target base URL passed to Locust (or export it before `make load-baseline`)",
    "LOAD_TEST_ACCESS_TOKEN": "Bearer token for dashboard / notification / app-trade flows",
    "LOAD_TEST_REFRESH_TOKEN": "refresh token for auth refresh flow",
    "LOAD_TEST_TRADE_ID": "disposable trade fixture id used by trade scenarios",
    "LOAD_TEST_TRADE_TOKEN": "public trade link token for public trade scenario",
}

TRUTHY = {"1", "true", "yes"}


def missing_required_env(host: str | None = None) -> list[str]:
    missing: list[str] = []
    if not host and not os.getenv("LOAD_TEST_HOST"):
        missing.append("LOAD_TEST_HOST")

    for key in (
        "LOAD_TEST_ACCESS_TOKEN",
        "LOAD_TEST_REFRESH_TOKEN",
        "LOAD_TEST_TRADE_ID",
        "LOAD_TEST_TRADE_TOKEN",
    ):
        if not os.getenv(key):
            missing.append(key)

    return missing


def build_error_message(missing: list[str], host: str | None = None) -> str:
    resolved_host = host or os.getenv("LOAD_TEST_HOST") or "<missing>"
    lines = [
        "Missing load-test configuration:",
        *[f"- {key}: {REQUIRED_ENV_HELP[key]}" for key in missing],
        "",
        f"Resolved host: {resolved_host}",
        f"Trade mutations enabled: {os.getenv('LOAD_TEST_ENABLE_TRADE_MUTATIONS', 'false').lower() in TRUTHY}",
        "",
        "Export the required variables first, then run `make load-baseline`.",
    ]
    return "\n".join(lines)


def validate_or_raise(host: str | None = None) -> None:
    missing = missing_required_env(host=host)
    if missing:
        raise RuntimeError(build_error_message(missing, host=host))


def main() -> int:
    try:
        validate_or_raise()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("Load-test environment looks ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
