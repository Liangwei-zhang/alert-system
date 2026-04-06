from __future__ import annotations

from apps.admin_api.main import app
from tests.contract.openapi_snapshot import assert_manifest_matches_snapshot


def test_admin_api_openapi_snapshot() -> None:
    assert_manifest_matches_snapshot(app, "admin_api_openapi_manifest.json")
