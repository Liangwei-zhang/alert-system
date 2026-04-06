# stock vs stock-py 历史迁移对照表

更新时间：2026-04-06

## 1. 说明

这份文档对比的是两个仓库在迁移阶段的实际状态。

它是历史对照材料，不再定义 `stock-py` 的现行产品边界；当前方向以 `stock-py` 独立运行、独立部署、独立 UI 为准。

- 原项目：`/home/nico/.openclaw/workspace-main/stock`
- 当前独立主系统仓库：`/home/nico/.openclaw/workspace-main/stock-py`

结论不是“有没有文档写到 target state”，而是“当前仓库里是否已经存在等价实现”。

状态定义：

- `已迁移`：`stock-py` 中已有明确对应实现，可运行，且不是纯占位。
- `部分迁移`：主链路或底层能力已存在，但管理面、运维面、部署面或完整接口面还未对齐。
- `未迁移`：`stock-py` 中没有明确等价实现，或只有目标文档没有实际交付。
- `不在迁移范围`：历史方案里不打算迁到 Python 仓库，但这一定义不再代表当前产品方向。

## 2. 总体结论

| 范围 | 结论 |
|---|---|
| 核心服务端业务 | 大部分已迁移 |
| Public API 主链路 | 大部分已迁移，legacy sidecar proxy / relay surface 也已补齐 |
| Admin API | analytics、TradingAgents、runtime、tasks、scanner、backtests、signal stats、anomalies、users、audit、acceptance、operators、distribution 已迁移，深度 runtime 指标也已补齐，剩余缺口主要在更完整的运维面硬化 |
| Worker / 异步链路 | 主要 worker 已迁移，scheduler 已补任务注册编排，retention 分区级维护与 runtime 深度指标已对齐 |
| 数据平面 | 本地可运行方案已落地，且真 ClickHouse / Kafka / S3 backend 与 compose scaffold 已补齐，但仍缺更生产化的高可用与运维硬化 |
| 部署与运维 | QA / cutover 工具、Docker Compose、root Dockerfile、Nginx scaffold、DLQ/replay、本地 rehearsal bootstrap、K8s batch baseline 与离线 render/schema validation 已补强，但真实集群 rollout 仍未完成 |
| 三端 UI | 已迁移为 Python 直出 HTML 路由，当前重点转为功能覆盖深度 |

一句话结论：

- `stock` 的核心后端能力已经基本迁到 `stock-py`。
- `stock` 作为完整产品和完整运维体系，单机 production baseline 已补到 compose + VM 目标形态，repo 内剩余重点已收敛到真实环境 rehearsal 结果沉淀、真实集群 rollout 与更高等级 HA 演进，而不是基础 deploy parity。
- `stock-py` 已经把三端 UI 收回到本仓库内；前端相关后续工作重点转为功能覆盖、认证体验与部署细节，而不是 workspace 归属。

## 3. Public API 对照

### 3.1 已迁移或基本迁移的 Public API

| 原 stock 功能 | stock 原位置 | stock-py 对应 | 状态 | 差异 / 说明 |
|---|---|---|---|---|
| 邮箱验证码登录、session、refresh、logout | `server/routes/auth.ts`，挂载于 `/api/auth` | `apps/public_api/routers/auth.py`，挂载于 `/v1/auth` | 已迁移 | 路由前缀从 `/api/*` 变为 `/v1/*` |
| 账户 profile / dashboard / start-subscription | `server/routes/account.ts` | `apps/public_api/routers/account.py` | 已迁移 | Python 端已有 targeted integration coverage |
| watchlist CRUD | `server/routes/watchlist.ts` | `apps/public_api/routers/watchlist.py` | 已迁移 | 主链路已在 Python public API 中 |
| portfolio CRUD | `server/routes/portfolio.ts` | `apps/public_api/routers/portfolio.py` | 已迁移 | 主链路已迁移 |
| symbol search | `server/routes/search.ts` | `apps/public_api/routers/search.py` | 已迁移 | 原实现用 pg_trgm + cache，Python 端也已有搜索域实现 |
| notifications 列表 / 已读 / ack | `server/routes/notification.ts` | `apps/public_api/routers/notifications.py` | 已迁移 | API shape 有调整，但能力对等 |
| push subscription / push device 管理 | `server/routes/notification.ts` 下的 `/push-subscriptions` | `apps/public_api/routers/notifications.py` 下的 `/push-devices` | 已迁移 | 命名从 `push-subscriptions` 改为 `push-devices` |
| trade info / confirm / ignore / adjust | `server/routes/trade.ts`，挂载于 `/api/trade` | `apps/public_api/routers/trades.py`，挂载于 `/v1/trades` | 已迁移 | 路由命名从单数变为复数，功能已对齐 |
| desktop signal ingest | `server/routes/signalIngest.ts`，挂载于 `/api/signals` | `apps/public_api/routers/signal_ingest.py`，挂载于 `/v1/internal/signals/*` | 已迁移 | Python 端路径改为 internal 路由风格 |
| TradingAgents webhook / internal hooks | `server/routes/tradingAgentsWebhook.ts`，挂载于 `/internal/integrations/tradingagents` | `apps/public_api/routers/tradingagents_submit.py`、`apps/public_api/routers/tradingagents_webhook.py` | 已迁移 | Python 端分成 submit + webhook 两个 router |
| health / metrics | `server/routes/health.ts`、`/api/monitoring/metrics` | `infra/http/health.py` + public/admin app 的 `/metrics` | 部分迁移 | Python 有 `/health` 与 `/metrics`，但没有原样的 internal monitoring route surface |

### 3.2 Public API 中已补齐的 sidecar 能力

| 原 stock 功能 | stock 原位置 | stock-py 对应 | 状态 | 缺口 |
|---|---|---|---|---|
| Yahoo proxy | `server/api.ts` 中 `/api/yahoo/:symbol` | `apps/public_api/routers/sidecars.py` 中 `GET /api/yahoo/{symbol}` | 已迁移 | 走 `infra/market_data/data_source.py` 的 Yahoo data source，受 internal sidecar secret 保护 |
| Binance proxy | `server/api.ts` 中 `/api/binance/*` | `apps/public_api/routers/sidecars.py` 中 `GET /api/binance/{symbol}` | 已迁移 | 走 `infra/market_data/data_source.py` 的 Binance data source，受 internal sidecar secret 保护 |
| desktop bridge alerts | `server/api.ts` 中 `/alerts` | `apps/public_api/routers/sidecars.py` 中 `POST /alerts` | 已迁移 | 复用 notifications / receipts / outbox data plane，把 bridge alert 排入 push / email 分发链路 |
| Telegram relay | `server/api.ts` 中 `/api/telegram` | `apps/public_api/routers/sidecars.py` 中 `POST /api/telegram` | 已迁移 | 通过 Telegram Bot HTTP relay 转发消息，受 internal sidecar secret 保护 |

### 3.3 Public API 中尚未对齐的功能

| 原 stock 功能 | stock 原位置 | stock-py 对应 | 状态 | 缺口 |
|---|---|---|---|---|
| internal monitoring stats / metrics / reset | `server/routes/monitoring.ts`，挂载于 `/api/monitoring/*` | `apps/public_api/routers/monitoring.py` | 已迁移 | 已补齐 `/api/monitoring/stats`、`/metrics`、`/reset`，并兼容 bearer / internal sidecar secret 鉴权 |

## 4. Admin API 对照

### 4.1 已迁移的 Admin 能力

| 原 stock 功能 | stock 原位置 | stock-py 对应 | 状态 | 说明 |
|---|---|---|---|---|
| admin overview | `GET /admin-api/overview` | `GET /v1/admin/analytics/overview` in `apps/admin_api/routers/analytics.py` | 已迁移 | 已纳入 analytics read model |
| distribution metrics | `GET /admin-api/distribution` | `GET /v1/admin/analytics/distribution` | 已迁移 | Python 端已提供 distribution read model |
| strategy health | `GET /admin-api/strategy-health` | `GET /v1/admin/analytics/strategy-health` | 已迁移 | Python 端已有对应 admin read model |
| TradingAgents analyses | `GET /admin-api/tradingagents/analyses` | `GET /v1/admin/tradingagents/analyses` | 已迁移 | list + detail 已存在 |
| TradingAgents delayed reconcile | TradingAgents admin 操作面 | `POST /v1/admin/tradingagents/reconcile-delayed` | 已迁移 | stats 端点也已存在 |

### 4.2 部分迁移的 Admin 能力

| 原 stock 功能 | stock 原位置 | stock-py 对应 | 状态 | 缺口 |
|---|---|---|---|---|
| receipt follow-up 底层能力 | `/admin-api/tasks/receipts/*` | `domains/notifications/receipt_service.py` + `domains/notifications/repository.py` + `apps/admin_api/routers/tasks.py` | 已迁移 | 已补齐 receipts list / escalate / claim / resolve admin route |
| OHLCV anomalies 数据能力 | `GET /admin-api/anomalies/ohlcv` | `infra/db/models/market_data.py` + quality/import services | 已迁移 | Python 已提供 `GET /v1/admin/anomalies/ohlcv`，支持 symbol / timeframe / severity / code / source filters |
| backtest refresh 能力 | `/admin-api/backtests/runs*` 与 scheduler | `apps/workers/backtest/worker.py` + `apps/admin_api/routers/backtests.py` | 已迁移 | Python 已补齐 backtest run 列表 / 详情 / 手动触发 API |
| 运营审计事件 | `/admin-api/audit` | `infra/events/outbox.py` + `apps/admin_api/routers/audit.py` | 已迁移 | Python 已提供 `GET /v1/admin/audit`，支持 entity / action / source / status / request_id filters |

### 4.3 Admin API 细项状态

这些在 `stock` 中存在明确管理接口，以下为当前 `stock-py` 对照状态：

| 原 stock 功能 | stock 原路径 | stock-py 状态 | 说明 |
|---|---|---|---|
| signal stats summary | `/admin-api/signal-stats/summary` | 已迁移 | Python 已提供 `GET /v1/admin/signal-stats/summary` |
| signal stats list | `/admin-api/signal-stats` | 已迁移 | Python 已提供 `GET /v1/admin/signal-stats`，支持 status / type / symbol / validation filters |
| live decision view | `/admin-api/live-decision` | 已迁移 | Python 已提供 `GET /v1/admin/scanner/live-decision`，支持 symbol / decision / suppressed filters |
| backtest runs list | `/admin-api/backtests/runs` | 已迁移 | Python 已提供 `GET /v1/admin/backtests/runs`，支持 status / strategy / timeframe / symbol filters |
| backtest run detail | `/admin-api/backtests/runs/:id` | 已迁移 | Python 已提供 `GET /v1/admin/backtests/runs/{run_id}` |
| create backtest run | `POST /admin-api/backtests/runs` | 已迁移 | Python 已提供 `POST /v1/admin/backtests/runs` 触发 ranking refresh |
| users list | `/admin-api/users` | 已迁移 | Python 已提供 `GET /v1/admin/users`，支持 query / plan / is_active filters |
| user detail | `/admin-api/users/:id` | 已迁移 | Python 已提供 `GET /v1/admin/users/{user_id}` |
| user update | `PUT /admin-api/users/:id` | 已迁移 | Python 已提供 `PUT /v1/admin/users/{user_id}`，支持 plan / profile / capital 调整 |
| users bulk update | `POST /admin-api/users/bulk` | 已迁移 | Python 已提供 `POST /v1/admin/users/bulk`，支持批量 plan / active 状态更新 |
| scanner observability | `/admin-api/scanner/observability` | 已迁移 | Python 已提供 `GET /v1/admin/scanner/observability` 与 `GET /v1/admin/scanner/runs/{run_id}` |
| tasks center root | `/admin-api/tasks` | 已迁移 | Python 已有 receipts / emails / outbox / trades claim / expire task center root |
| receipts task list | `/admin-api/tasks/receipts` | 已迁移 | 已支持 follow-up / delivery / overdue filters |
| receipts ack | `/admin-api/tasks/receipts/ack` | 已迁移 | Python 提供 `POST /v1/admin/tasks/receipts/ack` |
| receipts escalate | `/admin-api/tasks/receipts/escalate` | 已迁移 | Python 提供 `POST /v1/admin/tasks/receipts/escalate-overdue` |
| receipts claim | `/admin-api/tasks/receipts/claim` | 已迁移 | Python 提供 `POST /v1/admin/tasks/receipts/{receipt_id}/claim` |
| receipts follow-up | `/admin-api/tasks/receipts/follow-up` | 已迁移 | Python 提供 `POST /v1/admin/tasks/receipts/{receipt_id}/resolve` |
| outbox task list | `/admin-api/tasks/outbox` | 已迁移 | 已支持 channel / status / user / notification filters |
| emails claim | `/admin-api/tasks/emails/claim` | 已迁移 | Python 提供 `POST /v1/admin/tasks/emails/claim`，支持批量 claim pending email tasks |
| trades claim | `/admin-api/tasks/trades/claim` | 已迁移 | Python 已提供 `POST /v1/admin/tasks/trades/claim`，要求 active operator 並持久化 claim 資訊 |
| emails retry | `/admin-api/tasks/emails/retry` | 已迁移 | Python 提供 `POST /v1/admin/tasks/emails/retry`，支持批量 email retry |
| outbox retry | `/admin-api/tasks/outbox/retry` | 已迁移 | Python 同时提供单条 `POST /v1/admin/tasks/outbox/{outbox_id}/requeue` 与批量 `POST /v1/admin/tasks/outbox/retry` |
| outbox release-stale | `/admin-api/tasks/outbox/release-stale` | 已迁移 | Python 提供 `POST /v1/admin/tasks/outbox/release-stale`，支持按 channel 释放 stale processing tasks |
| trades expire | `/admin-api/tasks/trades/expire` | 已迁移 | Python 已提供 `POST /v1/admin/tasks/trades/expire`，支持按 trade_ids 或 expirable sweep 批量过期 |
| operators list | `/admin-api/operators` | 已迁移 | Python 已提供 `GET /v1/admin/operators`，支持 query / role / is_active filters |
| operator role update | `PUT /admin-api/operators/:id` | 已迁移 | Python 已提供 `PUT /v1/admin/operators/{user_id}`，支持 role / scopes / is_active upsert |
| audit log list | `/admin-api/audit` | 已迁移 | Python 已提供 `GET /v1/admin/audit` |
| acceptance status | `/admin-api/acceptance/status` | 已迁移 | Python 已提供 `GET /v1/admin/acceptance/status`，汇总 QA / runbook / snapshot / report readiness |
| acceptance report | `/admin-api/acceptance/report` | 已迁移 | Python 已提供 `GET /v1/admin/acceptance/report`，暴露 acceptance artifact 与最新 report 视图 |
| runtime monitoring stats | `/admin-api/monitoring/runtime/stats` | 已迁移 | Python 已提供 `GET /v1/admin/runtime/stats`，汇总 expected coverage、heartbeat 与年龄分布 |
| runtime monitoring health | `/admin-api/monitoring/runtime/health` | 已迁移 | Python 已提供 `GET /v1/admin/runtime/health`，返回整体 health 与 missing / stale / error components |
| runtime monitoring metrics | `/admin-api/monitoring/runtime/metrics` | 已迁移 | Python 已提供 `GET /v1/admin/runtime/metrics`，返回可直接用于运营面板的聚合指标点 |
| distribution manual message | `POST /admin-api/distribution/manual-message` | 已迁移 | Python 已提供 `POST /v1/admin/distribution/manual-message`，复用 notifications / receipts / outbox data plane |

## 5. Worker / Scheduler / 后台进程对照

| 原 stock 运行单元 | stock 原位置 | stock-py 对应 | 状态 | 差异 / 缺口 |
|---|---|---|---|---|
| public API | `server/api.ts` | `apps/public_api/main.py` | 已迁移 | Python public API 已成型 |
| admin API | `server/admin-api.ts` | `apps/admin_api/main.py` | 已迁移 | 但 admin surface 缺口很大 |
| scanner worker | `server/scanner/index.ts` | `apps/workers/scanner/worker.py` | 已迁移 | Python 端已变成独立 worker |
| email worker | `server/email-worker.ts` | `apps/workers/email_dispatch/worker.py` | 已迁移 | Python 端为更细的 dispatch worker |
| message worker | `server/message-worker.ts` | `apps/workers/notification_orchestrator/worker.py` + `apps/workers/push_dispatch/worker.py` + `apps/workers/email_dispatch/worker.py` | 部分迁移 | 核心链路已拆分迁移，但缺原 admin task center / outbox console / runtime worker observability |
| receipt escalation worker | `server/receipt-escalation-worker.ts` | `apps/workers/receipt_escalation/worker.py` | 已迁移 | 核心逻辑已在 Python 中 |
| TradingAgents polling worker | `server/tradingagents-polling-worker.ts` | `apps/workers/tradingagents_bridge/worker.py` | 已迁移 | Python 端采用 repository + gateway + mapper 结构 |
| market-data worker | 原 `stock` 中由 scanner / import-history / services 承担 | `apps/workers/market_data/worker.py` | 已迁移 | Python 端把行情导入与质量校验独立出来 |
| backtest refresh | 原 admin-api + service scheduler | `apps/workers/backtest/worker.py` + `apps/admin_api/routers/backtests.py` | 已迁移 | 后台刷新能力与 admin trigger/read 面均已落地 |
| scheduler | 原 `startBacktestRefreshScheduler()` 等 | `apps/scheduler/main.py` | 已迁移 | 现在已注册 heartbeat、event relay/dispatch、TradingAgents polling、market-data、scanner、retention、push/email dispatch、receipt escalation、backtest、cold storage 等周期任务 |
| retention worker | `server/retention-worker.ts` | `apps/workers/retention/worker.py` + `domains/notifications/retention_service.py` + `domains/notifications/partition_archive_service.py` | 已迁移 | 已覆盖 receipt archive、terminal `message_outbox` cleanup，以及 `notifications` / `message_receipts_archive` / published `event_outbox` 月分区归档与清理 |
| import-history 工具 | `server/import-history.ts` | 无直接等价 CLI | 部分迁移 | 市场数据导入能力在 worker/service 中存在，但原脚本级入口未对齐 |

## 6. 数据平面与领域能力对照

### 6.1 已迁移的底层能力

| 能力 | stock-py 状态 | 说明 |
|---|---|---|
| Alembic migration scaffold | 已迁移 | Python 已有 Alembic 与多条 revision |
| SQLAlchemy async session / UoW | 已迁移 | 已在 `infra/db/*` 中落地 |
| request context / logging / metrics / tracing | 已迁移 | `infra/core/*`、`infra/observability/*` 已存在 |
| durable outbox + event pipeline | 已迁移 | `infra/events/outbox.py` + `apps/workers/event_pipeline/worker.py` |
| Redis-backed session / account / trade / push-device cache | 已迁移 | 热路径缓存已在 Python 中落地 |
| notification receipts archive 模型 | 已迁移 | `message_receipts_archive` 已进入模型与 migration |
| TradingAgents repository / gateway / projection | 已迁移 | 主链路已存在 |
| market-data / quality / scanner snapshot | 已迁移 | 对应 Python domain + worker 已存在 |

### 6.2 部分迁移或未完成的底层能力

| 能力 | stock 原现状 | stock-py 状态 | 缺口 |
|---|---|---|---|
| analytics backend | 原 `stock` 仍以 PostgreSQL + 报表服务为主 | 部分迁移 | Python 已有 JSONL + local object storage facade，但不是真 ClickHouse / Kafka / S3 |
| distribution console data plane | 原 `stock` 依赖 `message_outbox`、`message_receipts`、`push_subscriptions` 与 admin console | 已迁移 | Python 已具备底层表、worker、analytics distribution metrics，与 admin manual-message command surface |
| runtime heartbeat / worker health 面板 | 原 `stock` 有 runtime heartbeat + admin monitoring router | 已迁移 | Python 已有 Redis-backed runtime registry + `/v1/admin/runtime/components*` / `stats` / `health` / `metrics` / `alerts`，并补上 broker lag、PgBouncer、Redis、ClickHouse、object storage archive 等运维指标 |
| retention maintenance | 原 `stock` 有 `retentionMaintenance.ts` 负责 queue/outbox/archive 清理与分区维护 | 已迁移 | Python 已有 retention worker 处理 receipt archive、terminal outbox、published event_outbox cleanup，以及 `notifications` / `message_receipts_archive` / published `event_outbox` 月分区归档 |

## 7. QA / Cutover / 运维交付对照

| 能力 | stock 原现状 | stock-py 状态 | 结论 |
|---|---|---|---|
| 单元测试 | Node/Vitest | Python/pytest | 已迁移 |
| OpenAPI contract snapshot | 原仓库未见同等清晰 Python-style contract baseline | 已有 `tests/contract/*` 与 snapshot | 已迁移，且更系统 |
| e2e / targeted integration | 原仓库有后端与部署测试 | Python 已有 e2e 与 targeted integration | 已迁移，但 integration 仍在逐域补齐 |
| load scaffold | 原 `stock` 有 read-path benchmark | Python 已有 Locust scaffold + compose-backed baseline entry | 已迁移，形态改变 |
| load artifact bootstrap | 原仓库 benchmark 输出到 `logs/benchmarks/` | Python 有 `make load-report-init`、`make load-baseline` | 已迁移，且更标准化 |
| cutover rehearsal artifact | 原仓库 runbook 分散 | Python 有 `make cutover-report-init`、`make cutover-openapi-diff` | 已迁移为工具化能力 |
| 真实 staging baseline / rehearsal 记录 | 原项目仍需人工执行 | Python 侧工具已备齐，且可自动 bootstrap fixture、采集 evidence bundle、输出 threshold 建议 | 进行中 |

## 8. 部署与环境对照

| 原 stock 能力 | stock 原位置 | stock-py 状态 | 结论 |
|---|---|---|---|
| Dockerfile | `ops/Dockerfile` | 根目录 `Dockerfile` 已存在 | 已迁移 |
| Nginx Dockerfile | `ops/Dockerfile.nginx` | 未提供独立 Dockerfile，compose 走官方 Nginx 镜像 + `ops/nginx/default.conf` | 部分迁移 |
| docker-compose.yml | `ops/docker-compose.yml` | `ops/docker-compose.yml` 已存在 | 已迁移 |
| nginx.conf | `ops/nginx.conf` | `ops/nginx/default.conf` 已存在 | 已迁移 |
| PM2 ecosystem | `ops/ecosystem.config.js` | `ops/ecosystem.config.js` 已存在 | 已迁移 |
| PostgreSQL tuning config | `ops/postgresql.conf.tuning` | `ops/postgresql.conf.tuning` 已存在 | 已迁移 |
| K8s/HPA/Prometheus/Grafana baseline | 原 `stock` 也未完全体现为 K8s 成品，但部署栈更完整 | `ops/k8s/base/*` 已存在，且已补 batch CronJob 与离线 render/schema validation | 已迁移 |

说明：

- `stock-py` 当前 `ops/` 已包含 compose、Nginx、PgBouncer、ClickHouse、MinIO、reports 与 runbooks。
- 当前剩余缺口主要是 K8s / HA 的真实 rollout 与真实环境演练沉淀，而不是 repo 内 deploy / cutover / batch / DLQ 工具链本身。

## 9. 前端 / 客户端面

| 原 stock 能力 | stock 原位置 | stock-py 状态 | 结论 |
|---|---|---|---|
| `/app` H5 订阅端 | `src/MobileApp.tsx` 及相关页面 | `apps/public_api/routers/ui.py` + `apps/public_api/ui_shell.py` | 已迁移为纯 HTML + Python shell |
| `/platform` 桌面研究台 | `src/App.tsx` | `apps/public_api/routers/ui.py` + `apps/public_api/ui_shell.py` | 已迁移为纯 HTML + Python shell |
| `/admin` 管理前端 | `src/AdminApp.tsx` | `apps/public_api/routers/ui.py` + `apps/public_api/ui_shell.py` | 已迁移为纯 HTML + Python shell |

说明：

- 按历史 Python 迁移方案，React 前端三端原本没有进入 Python repo。
- 当前 `stock-py` 已经把三端入口收回到 Python 服务本身，并以纯 HTML shell 的形式提供；这解决了 repo 归属问题，但不代表已经达到旧 UI 的全部功能深度。

## 10. 仍未完成的关键缺口清单

下面这部分是最适合继续拆成后续任务的清单。

### 10.1 高优先级缺口

1. 在真实 staging / canary 环境执行 load baseline、cutover rehearsal，并把 reviewed artifact 沉淀到 `ops/reports/*`。
2. 把本地生成的 runtime threshold 建议转成真实环境 PrometheusRule / override，并用真实流量回看一轮。
3. 在真实上游与真实数据量下完成 shadow read / dual-write / rollback 验证。
4. 继续补齐 `/app`、`/platform`、`/admin` 纯 HTML shell 的功能覆盖、验收脚本与部署细节，避免只停留在 API 操作台层级。

### 10.2 中优先级缺口

1. 把 `ops/k8s/base/*` 投到真实集群做一次完整 rollout / rollback 演练，验证 secret、Ingress、ServiceMonitor 与 CronJob 调度。
2. 把 compose 验证过的 ClickHouse / Kafka / object-storage data plane 参数，映射到真实托管或多节点拓扑。
3. 继续补齐更细的运营审计、补偿與容量觀測面，避免 admin parity 停留在 route 對齊。

### 10.3 生产化缺口

1. 把当前单机 compose baseline 提升到真实 HA 拓扑。
2. 为 broker / storage / analytics 外部依赖补齐故障演练与容量回放。
3. 做真实 staging load baseline、canary / rollback rehearsal、shadow read / dual-write parity 验证。

## 11. 最终结论

可以把当前迁移状态概括为：

- `stock-py` 已完成 `stock` 大部分核心后端业务功能迁移。
- `stock-py` 已补齐 legacy public sidecar surface，包括 Yahoo / Binance proxy、bridge alerts 与 Telegram relay。
- `stock-py` 已完成 `stock` 核心 admin 运营后台的主要 route parity，包括 users、audit、acceptance、operators、distribution 与 tasks center 主链路。
- `stock-py` 已补齐 scheduler 编排、retention 分区维护、runtime 深度指标、DLQ/replay、batch CronJob baseline 与 compose + VM 单机部署基线。
- `stock-py` 仍待真实环境的 production-grade data plane 与切流验证收口。

因此，当前不能说“`stock` 的所有功能都已迁移完成”。

更准确的表述是：

- 核心服务端业务：`大部分完成`
- 完整产品与运营体系：`大部分完成，剩真实环境收口`
- 生产化与切流：`仍待真实环境验证`