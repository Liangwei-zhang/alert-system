# 平台組執行手冊

> 狀態（2026-04-04）：公共 infra 主體已落地。本文仍保留部分 target-state 清單；若列出的測試或部署文件在 repo 中不存在，應視為待補項。已刪除的 `apps/public_api/dependencies.py` 不再是當前結構的一部分。

## 1. 目標

平台組負責把 Python 倉庫的公共地基一次搭正。其他組不能自己重寫基礎設施。

平台組交付物如果不穩，後面所有 domain 都會返工。

## 2. 平台組責任邊界

平台組負責：

- 倉庫初始化
- Python 依賴管理
- FastAPI app skeleton
- DB engine / session / UoW
- Settings / context / errors / logging
- Event bus / outbox 基礎實現
- Redis / Kafka / ClickHouse 客戶端基礎封裝
- Docker / K8s / CI/CD / migration 基礎線
- metrics / tracing / health

平台組不負責：

- 具體業務規則
- 具體 watchlist / portfolio / notification / scanner 內容
- 第三方 provider 的業務決策

## 3. 第一批必建文件

```text
pyproject.toml
README.md
.env.example
Makefile
alembic.ini
docker-compose.local.yml
apps/public_api/main.py
apps/admin_api/main.py
apps/admin_api/dependencies.py
apps/scheduler/main.py
infra/core/config.py
infra/core/context.py
infra/core/errors.py
infra/core/logging.py
infra/core/pagination.py
infra/security/auth.py
infra/security/token_signer.py
infra/security/idempotency.py
infra/db/models/base.py
infra/db/repository_base.py
infra/db/session.py
infra/db/uow.py
infra/events/outbox.py
infra/events/bus.py
infra/cache/redis_client.py
infra/cache/rate_limit.py
infra/http/http_client.py
infra/observability/metrics.py
infra/observability/tracing.py
infra/storage/object_storage.py
tests/unit/platform/
tests/integration/platform/
```

## 4. 類與函數清單

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/core/config.py` | `Settings` | `model_config`, `from_env()` 或 `BaseSettings` 配置 |
| `infra/core/config.py` | `get_settings()` | 回傳單例 settings |
| `infra/core/context.py` | `RequestContext` | `request_id`, `trace_id`, `user_id`, `operator_id`, `ip`, `user_agent` |
| `infra/core/context.py` | `build_request_context()` | 從 FastAPI request 組裝 context |
| `infra/core/errors.py` | `AppError` | `code`, `message`, `status_code`, `details` |
| `infra/core/errors.py` | `to_error_response()` | 統一錯誤輸出 |
| `infra/core/logging.py` | `configure_logging()` | JSON logger、request_id 綁定 |
| `infra/core/pagination.py` | `CursorPage` | `items`, `next_cursor` |
| `infra/core/pagination.py` | `encode_cursor()` | cursor encode |
| `infra/core/pagination.py` | `decode_cursor()` | cursor decode |
| `infra/security/auth.py` | `CurrentUser` | `user_id`, `plan`, `scopes`, `is_admin` |
| `infra/security/auth.py` | `require_user()` | public API auth dependency |
| `infra/security/auth.py` | `require_admin()` | admin API auth dependency |
| `infra/security/token_signer.py` | `TokenSigner` | `sign()`, `verify()` |
| `infra/security/idempotency.py` | `IdempotencyService` | `acquire()`, `store_result()`, `replay()` |
| `infra/db/models/base.py` | `Base` | SQLAlchemy declarative base |
| `infra/db/models/base.py` | `TimestampMixin` | `created_at`, `updated_at` |
| `infra/db/repository_base.py` | `BaseRepository` | `add()`, `delete()`, `flush()`, `refresh()` |
| `infra/db/session.py` | `build_engine()` | async engine 建立 |
| `infra/db/session.py` | `build_session_factory()` | sessionmaker 建立 |
| `infra/db/session.py` | `get_db_session()` | FastAPI dependency |
| `infra/db/uow.py` | `AsyncUnitOfWork` | `__aenter__`, `__aexit__`, `commit()`, `rollback()`, `flush()` |
| `infra/events/outbox.py` | `OutboxEvent` | event 實體 |
| `infra/events/outbox.py` | `OutboxPublisher` | `publish_after_commit()`, `publish_batch_after_commit()` |
| `infra/events/bus.py` | `EventBus` | `publish()`, `publish_batch()` |
| `infra/cache/redis_client.py` | `get_redis()` | Redis 單例客戶端 |
| `infra/cache/rate_limit.py` | `RedisRateLimiter` | `hit()`, `remaining()`, `reset_at()` |
| `infra/http/http_client.py` | `HttpClientFactory` | `get_internal_client()`, `get_external_client()` |
| `infra/observability/metrics.py` | `MetricsRegistry` | `counter()`, `histogram()`, `gauge()` |
| `infra/observability/tracing.py` | `configure_tracing()` | OTel 初始化 |
| `infra/storage/object_storage.py` | `ObjectStorageClient` | `put_json()`, `put_bytes()`, `get_object()`, `delete_object()` |
| `apps/admin_api/dependencies.py` | `get_*_service()` | admin domain service 裝配 |

## 5. 主程序文件要求

### 5.1 `apps/public_api/main.py`

必須完成：

- 建立 FastAPI app
- 掛載全局 exception handler
- 掛載 request context middleware
- 掛載 metrics endpoint
- 掛載 health router
- 預留 domain routers 的 import 位置

### 5.2 `apps/admin_api/main.py`

必須完成：

- 與 `public_api` 同樣的公共 middleware
- admin only 的 auth dependency 配置
- admin router 掛載點

### 5.3 `apps/scheduler/main.py`

必須完成：

- APScheduler 啟動入口
- 任務註冊方式
- graceful shutdown
- heartbeat 上報

## 6. 本地開發標準

平台組需要先保證以下命令成立：

```bash
make install
make lint
make test
make run-public-api
make run-admin-api
make run-scheduler
make migrate
```

如果這些命令還不能跑，不允許其他組大量開始寫業務代碼。

## 7. CI/CD 標準

平台組必須提供：

- PR lint
- PR unit test
- PR integration test
- OpenAPI snapshot check
- Alembic migration check
- Docker build check

## 8. K8s 與部署交付

平台組至少提供：

- public-api deployment
- admin-api deployment
- worker deployment template
- HPA sample
- ConfigMap / Secret 模板
- Prometheus scrape config
- Grafana dashboard baseline

## 9. 驗收標準

平台組完成的判準：

- 其他組不需要自己建立 DB session、logging、settings、redis client
- 任何 domain 都可以透過 `dependencies.py` 正常裝配 service
- `make migrate && make test && make run-public-api` 可在新環境跑通
- 任何 service 錯誤都會輸出統一 JSON error response

## 10. 與其他組的交接點

平台組交給帳戶組 / 通知組 / 訊號組的內容：

- `Settings`
- `RequestContext`
- `AppError`
- `BaseRepository`
- `AsyncUnitOfWork`
- `OutboxPublisher`
- `EventBus`
- `get_db_session()`
- `get_*_service()` 寫法模板

沒有這些交付，其他組不要開始寫正式業務域。