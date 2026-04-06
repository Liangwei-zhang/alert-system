from __future__ import annotations

import argparse
import asyncio

from infra.observability.runtime_monitoring import get_runtime_component


async def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime component health probe")
    parser.add_argument("--kind", required=True, help="Runtime component kind")
    parser.add_argument("--name", required=True, help="Runtime component name")
    parser.add_argument(
        "--max-age-seconds",
        type=float,
        default=90.0,
        help="Maximum acceptable heartbeat age in seconds",
    )
    parser.add_argument(
        "--allow-health",
        action="append",
        default=["healthy"],
        help="Allowed computed health values",
    )
    args = parser.parse_args()

    component = await get_runtime_component(args.kind, args.name)
    if component is None:
        return 1
    if str(component.get("health") or "unknown") not in {
        item.strip().lower() for item in args.allow_health if item.strip()
    }:
        return 1
    age_seconds = component.get("age_seconds")
    if age_seconds is not None and float(age_seconds) > max(float(args.max_age_seconds), 1.0):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
