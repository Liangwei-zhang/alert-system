from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.admin_api.main import app as admin_app
from apps.public_api.main import app
from infra.db.session import get_db_session
from infra.security.auth import CurrentUser, require_admin, require_user
from tests.helpers.app_client import AdminApiClient, PublicApiClient


@pytest.fixture
def public_api_client() -> PublicApiClient:
    dummy_session = SimpleNamespace(info={})

    async def override_db_session() -> SimpleNamespace:
        return dummy_session

    app.dependency_overrides[get_db_session] = override_db_session
    client = PublicApiClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()


@pytest.fixture
def authenticated_public_api_client(public_api_client: PublicApiClient) -> PublicApiClient:
    async def override_require_user() -> CurrentUser:
        return CurrentUser(user_id=42, plan="pro", scopes=["app"], is_admin=False)

    app.dependency_overrides[require_user] = override_require_user
    return public_api_client.auth_as_user()


@pytest.fixture
def admin_api_client() -> AdminApiClient:
    dummy_session = SimpleNamespace(info={})

    async def override_db_session() -> SimpleNamespace:
        return dummy_session

    admin_app.dependency_overrides[get_db_session] = override_db_session
    client = AdminApiClient(admin_app)
    try:
        yield client
    finally:
        client.close()
        admin_app.dependency_overrides.clear()


@pytest.fixture
def authenticated_admin_api_client(admin_api_client: AdminApiClient) -> AdminApiClient:
    async def override_require_admin() -> CurrentUser:
        return CurrentUser(user_id=1, plan="enterprise", scopes=["admin"], is_admin=True)

    admin_app.dependency_overrides[require_admin] = override_require_admin
    return admin_api_client.auth_as_admin()
