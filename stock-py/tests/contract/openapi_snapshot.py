from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infra.core.openapi_artifacts import build_openapi_manifest

SNAPSHOT_DIR = Path(__file__).with_name("snapshots")


def load_snapshot(file_name: str) -> dict[str, Any]:
    return json.loads((SNAPSHOT_DIR / file_name).read_text(encoding="utf-8"))


def assert_manifest_matches_snapshot(app: FastAPI, file_name: str) -> None:
    actual = build_openapi_manifest(app)
    expected = load_snapshot(file_name)
    if actual != expected:
        expected_json = json.dumps(expected, indent=2, sort_keys=True)
        actual_json = json.dumps(actual, indent=2, sort_keys=True)
        raise AssertionError(
            "OpenAPI snapshot mismatch for "
            f"{file_name}\nEXPECTED:\n{expected_json}\nACTUAL:\n{actual_json}"
        )
