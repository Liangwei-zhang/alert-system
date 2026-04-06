from __future__ import annotations

from apps.public_api.main import app
from tests.contract.openapi_snapshot import assert_manifest_matches_snapshot


def test_public_api_openapi_snapshot() -> None:
    assert_manifest_matches_snapshot(app, "public_api_openapi_manifest.json")
