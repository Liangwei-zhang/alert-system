from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Protocol

from infra.core.config import get_settings
from infra.observability.external_operation_metrics import record_external_operation


class ObjectStorageBackend(Protocol):
    async def put_bytes(self, key: str, payload: bytes) -> str: ...

    async def get_object(self, key: str) -> bytes | None: ...

    async def delete_object(self, key: str) -> bool: ...

    async def ping(self) -> dict[str, str]: ...


class LocalObjectStorageBackend:
    def __init__(self, root_path: str | None = None) -> None:
        self.root = Path(root_path or get_settings().object_storage_root)

    def _resolve_path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        root = self.root.resolve()
        if not str(candidate).startswith(str(root)):
            raise ValueError("Object key escapes the configured storage root")
        return candidate

    async def put_bytes(self, key: str, payload: bytes) -> str:
        path = self._resolve_path(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, payload)
        return str(path)

    async def get_object(self, key: str) -> bytes | None:
        path = self._resolve_path(key)
        if not path.exists():
            return None
        return await asyncio.to_thread(path.read_bytes)

    async def delete_object(self, key: str) -> bool:
        path = self._resolve_path(key)
        if not path.exists():
            return False
        await asyncio.to_thread(path.unlink)
        return True

    async def ping(self) -> dict[str, str]:
        await asyncio.to_thread(self.root.mkdir, parents=True, exist_ok=True)
        return {"ok": "true", "backend": "local", "root": str(self.root)}


class S3ObjectStorageBackend:
    def __init__(
        self,
        *,
        bucket: str | None = None,
        prefix: str | None = None,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        force_path_style: bool | None = None,
        client_factory=None,
    ) -> None:
        settings = get_settings()
        self.bucket = str(bucket or settings.object_storage_bucket).strip()
        self.prefix = str(prefix if prefix is not None else settings.object_storage_prefix).strip(
            "/"
        )
        self.endpoint_url = str(
            endpoint_url if endpoint_url is not None else settings.object_storage_endpoint_url
        ).strip()
        self.region_name = str(
            region_name if region_name is not None else settings.object_storage_region
        ).strip()
        self.access_key_id = str(
            access_key_id if access_key_id is not None else settings.object_storage_access_key_id
        ).strip()
        self.secret_access_key = str(
            secret_access_key
            if secret_access_key is not None
            else settings.object_storage_secret_access_key
        ).strip()
        self.force_path_style = (
            settings.object_storage_force_path_style
            if force_path_style is None
            else bool(force_path_style)
        )
        self._client_factory = client_factory
        self._client = None

    def _normalize_key(self, key: str) -> str:
        normalized = str(key or "").lstrip("/")
        if not normalized:
            raise ValueError("Object key is required")
        if self.prefix:
            return f"{self.prefix}/{normalized}"
        return normalized

    def _build_client(self):
        if self._client_factory is not None:
            return self._client_factory()
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("S3 object storage backend requires boto3 to be installed") from exc

        session = boto3.session.Session()
        return session.client(
            "s3",
            endpoint_url=self.endpoint_url or None,
            region_name=self.region_name or None,
            aws_access_key_id=self.access_key_id or None,
            aws_secret_access_key=self.secret_access_key or None,
            config=Config(s3={"addressing_style": "path"}) if self.force_path_style else None,
        )

    def _get_client(self):
        if self._client is None:
            self._client = self._build_client()
        return self._client

    async def put_bytes(self, key: str, payload: bytes) -> str:
        object_key = self._normalize_key(key)
        started_at = perf_counter()

        def _put() -> None:
            self._get_client().put_object(Bucket=self.bucket, Key=object_key, Body=payload)

        try:
            await asyncio.to_thread(_put)
        except Exception as exc:
            await self._record_operation(
                object_key,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                latency_ms=(perf_counter() - started_at) * 1000,
            )
            raise
        await self._record_operation(
            object_key,
            success=True,
            latency_ms=(perf_counter() - started_at) * 1000,
        )
        return object_key

    async def get_object(self, key: str) -> bytes | None:
        object_key = self._normalize_key(key)

        def _get() -> bytes | None:
            client = self._get_client()
            try:
                response = client.get_object(Bucket=self.bucket, Key=object_key)
            except Exception as exc:
                error_code = getattr(exc, "response", {}).get("Error", {}).get("Code")
                if error_code in {"404", "NoSuchKey", "NotFound"}:
                    return None
                raise

            body = response["Body"]
            try:
                return body.read()
            finally:
                close = getattr(body, "close", None)
                if callable(close):
                    close()

        return await asyncio.to_thread(_get)

    async def delete_object(self, key: str) -> bool:
        object_key = self._normalize_key(key)

        def _delete() -> bool:
            client = self._get_client()
            try:
                client.head_object(Bucket=self.bucket, Key=object_key)
            except Exception as exc:
                error_code = getattr(exc, "response", {}).get("Error", {}).get("Code")
                if error_code in {"404", "NoSuchKey", "NotFound"}:
                    return False
                raise
            client.delete_object(Bucket=self.bucket, Key=object_key)
            return True

        return await asyncio.to_thread(_delete)

    async def ping(self) -> dict[str, str]:
        def _ping() -> None:
            self._get_client().head_bucket(Bucket=self.bucket)

        await asyncio.to_thread(_ping)
        return {"ok": "true", "backend": "s3", "bucket": self.bucket}

    async def _record_operation(
        self,
        object_key: str,
        *,
        success: bool,
        latency_ms: float,
        error: str | None = None,
    ) -> None:
        components = ["object_storage"]
        if object_key.startswith("retention-archive/") or object_key.startswith(
            "analytics-archive/"
        ):
            components.append("object_storage_archive")
        for component in components:
            await record_external_operation(
                component,
                "put_bytes",
                success=success,
                error=error,
                latency_ms=latency_ms,
            )


class ObjectStorageClient:
    def __init__(
        self,
        root_path: str | None = None,
        *,
        backend: str | None = None,
        backend_impl: ObjectStorageBackend | None = None,
    ) -> None:
        selected_backend = str(backend or get_settings().object_storage_backend).strip().lower()
        if backend_impl is not None:
            self.backend = selected_backend
            self.impl = backend_impl
        elif selected_backend == "s3":
            self.backend = "s3"
            self.impl = S3ObjectStorageBackend()
        else:
            self.backend = "local"
            self.impl = LocalObjectStorageBackend(root_path=root_path)

    async def put_json(self, key: str, payload: dict) -> str:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return await self.put_bytes(key, body)

    async def put_bytes(self, key: str, payload: bytes) -> str:
        return await self.impl.put_bytes(key, payload)

    async def get_object(self, key: str) -> bytes | None:
        return await self.impl.get_object(key)

    async def delete_object(self, key: str) -> bool:
        return await self.impl.delete_object(key)

    async def ping(self) -> dict[str, str]:
        return await self.impl.ping()


@lru_cache(maxsize=1)
def get_object_storage_client() -> ObjectStorageClient:
    return ObjectStorageClient()
