from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient


class _BaseApiClient:
    def __init__(self, app: FastAPI) -> None:
        self._client = TestClient(app)
        self._headers: dict[str, str] = {}

    def get(self, path: str, **kwargs: Any):
        return self._client.get(
            path, headers=self._merge_headers(kwargs.pop("headers", None)), **kwargs
        )

    def post(self, path: str, **kwargs: Any):
        return self._client.post(
            path, headers=self._merge_headers(kwargs.pop("headers", None)), **kwargs
        )

    def put(self, path: str, **kwargs: Any):
        return self._client.put(
            path, headers=self._merge_headers(kwargs.pop("headers", None)), **kwargs
        )

    def delete(self, path: str, **kwargs: Any):
        return self._client.delete(
            path, headers=self._merge_headers(kwargs.pop("headers", None)), **kwargs
        )

    def close(self) -> None:
        self._client.close()

    def _merge_headers(self, headers: Mapping[str, str] | None) -> dict[str, str]:
        merged = dict(self._headers)
        if headers:
            merged.update(headers)
        return merged


class PublicApiClient(_BaseApiClient):
    def __init__(self, app: FastAPI | None = None) -> None:
        if app is None:
            from apps.public_api.main import app as public_app

            app = public_app
        super().__init__(app)

    def auth_as_user(self, token: str = "test-user-token") -> "PublicApiClient":
        self._headers["Authorization"] = f"Bearer {token}"
        return self


class AdminApiClient(_BaseApiClient):
    def __init__(self, app: FastAPI | None = None) -> None:
        if app is None:
            from apps.admin_api.main import app as admin_app

            app = admin_app
        super().__init__(app)

    def auth_as_admin(self, token: str = "test-admin-token") -> "AdminApiClient":
        self._headers["Authorization"] = f"Bearer {token}"
        return self
