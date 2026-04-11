from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_experiment_config(
    *,
    symbols: list[str],
    strategy_names: list[str],
    windows: tuple[int, ...],
    timeframe: str,
    experiment_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = dict(experiment_context or {})
    dataset = context.pop("dataset", None)
    config: dict[str, Any] = {
        "timeframe": timeframe,
        "windows": list(windows),
        "strategy_names": list(strategy_names),
        "universe": {
            "count": len(symbols),
            "symbols": list(symbols),
        },
    }
    if isinstance(dataset, dict) and dataset:
        config["dataset"] = dataset
    execution = {key: value for key, value in context.items() if value not in (None, "", [], {})}
    if execution:
        config["execution"] = execution
    return config


def build_dataset_fingerprint(
    *,
    symbols: list[str],
    windows: tuple[int, ...],
    timeframe: str,
    experiment_context: dict[str, Any] | None = None,
) -> str:
    dataset_context = None
    if isinstance(experiment_context, dict):
        dataset = experiment_context.get("dataset")
        if isinstance(dataset, dict) and dataset:
            dataset_context = dataset
    payload = {
        "dataset": dataset_context,
        "symbols": sorted({symbol.strip().upper() for symbol in symbols if symbol.strip()}),
        "timeframe": timeframe.strip().lower(),
        "windows": [int(window) for window in windows],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_run_key(*, experiment_name: str, timeframe: str, started_at: datetime) -> str:
    slug = _slugify(experiment_name)
    return f"{slug}:{timeframe.strip().lower()}:{started_at.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def build_artifact_manifest(
    *,
    run_id: int,
    timeframe: str,
    rankings_as_of: datetime | None = None,
    ranking_count: int | None = None,
    extra_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = [
        {
            "type": "database",
            "name": "backtest_run",
            "locator": {
                "id": int(run_id),
                "table": "backtest_runs",
            },
        }
    ]
    if rankings_as_of is not None:
        entries.append(
            {
                "type": "database",
                "name": "strategy_rankings",
                "locator": {
                    "as_of_date": rankings_as_of.astimezone(timezone.utc).isoformat(),
                    "count": int(ranking_count or 0),
                    "table": "strategy_rankings",
                    "timeframe": timeframe.strip().lower(),
                },
            }
        )
    for entry in extra_entries or []:
        if isinstance(entry, dict) and entry:
            entries.append(entry)
    return {"entries": entries}


def capture_code_version(repo_root: str | Path | None = None) -> str | None:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[3]
    sha = _run_git_command(root, ["rev-parse", "--short=12", "HEAD"])
    if not sha:
        return None
    branch = _run_git_command(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    dirty = bool(_run_git_command(root, ["status", "--porcelain"]))
    prefix = f"{branch}@" if branch else ""
    suffix = "+dirty" if dirty else ""
    return f"{prefix}{sha}{suffix}"


def _run_git_command(repo_root: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    output = result.stdout.strip()
    return output or None


def _slugify(value: str) -> str:
    parts = re.split(r"[^a-zA-Z0-9]+", value.strip().lower())
    slug = "-".join(part for part in parts if part)
    return slug or "backtest-ranking-refresh"