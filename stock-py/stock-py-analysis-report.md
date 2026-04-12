# stock-py 项目全面分析报告

> 分析日期：2026-04-11 | 代码版本：最新 zip 快照 | 审查范围：699 个文件，138 MB

---

## 一、项目架构总览

### 1.1 整体定位

`stock-py` 是一套面向 **股票订阅与预警** 场景、定位支撑 **百万日活** 的独立 Python 主系统，已完成从旧 Node/混合栈的迁移。系统分三个对外面：

| 端 | 入口 | 职责 |
|---|---|---|
| 订阅端 `/app` | `frontend/app` | 用户认证、watchlist/portfolio/现金录入、接收预警 |
| 桌面端 `/platform` | `frontend/platform` | 策略核心：候选标的、回测、参数维护、交易执行 |
| 管理端 `/admin` | `frontend/admin` | 用户治理、推送、操作员、审计、运行监控 |

### 1.2 技术栈

```
FastAPI (async/await) + Python 3.13
PostgreSQL + asyncpg + SQLAlchemy 2.0 async + PgBouncer
Redis（缓存 / 限流 / Streams broker）
Kafka（可切换，lazy import）
ClickHouse（analytics，本地 JSONL / 真实 backend 可切换）
MinIO / S3-compatible（cold storage）
APScheduler + 13 个专用 async worker
Docker Compose + Nginx + K8s baseline
```

### 1.3 目录结构评分

| 层 | 实现质量 | 说明 |
|---|---|---|
| `apps/` 双 API + Workers | ✅ 优秀 | 职责单一，lifespan 管理规范 |
| `domains/` DDD 分层 | ✅ 优秀 | service/repository/schema 三层清晰 |
| `infra/` 基础设施 | ✅ 优秀 | db/cache/events/security/observability 分明 |
| `tests/` 多层测试 | ✅ 良好 | unit + integration + contract + e2e + load，64 个 unit 文件 |
| `ops/` 运维工具链 | ✅ 良好 | compose + K8s + load/cutover/backup 齐备 |
| `frontend/` 三端 Shell | ⚠️ 中等 | 纯 HTML，逻辑密集，单文件过大（index.html 146KB） |

---

## 二、亮点：已做对的事

### 2.1 Durable Outbox 事件模式

`infra/events/outbox.py` 实现了标准的 **Transactional Outbox Pattern**：事件在同一 DB 事务内持久化，由 `event_pipeline/worker.py` 异步 relay 到 Redis Streams 或 Kafka，保证 at-least-once 语义。Dead-letter / replay CLI 也已实现（`python -m infra.events.outbox stats`）。

### 2.2 PgBouncer Transaction Pooling 适配

`infra/db/session.py` 的 `build_engine()` 在检测到 `database_pool_mode == "pgbouncer"` 时自动切换为 `NullPool`，并禁用 prepared statement cache，完全符合 PgBouncer transaction mode 要求，避免了"prepared statement does not exist"这一常见陷阱。

### 2.3 Cache Fill Lock 防击穿

`infra/cache/fill_lock.py` 用 Redis Lua 脚本实现了带 TTL 续期的 mutex 锁，有效防止缓存击穿（thundering herd），且通过 Lua 的原子性保证 token 校验与 DEL 的竞争安全。

### 2.4 文件型 Secret 注入

`infra/core/config.py` 实现了 `FileBackedEnvSettingsSource`，支持 `*_FILE` 环境变量指向 Docker secret 文件，对 K8s/Compose secret 挂载开箱即用。

### 2.5 校准驱动的策略引擎

`domains/signals/` 已实现 `CalibrationService` + `StrategySelector` + `MarketRegimeDetector` + `ExitLevelCalculator` 四层分离，评分器已支持从上游传入 `calibration_snapshot` 来动态调整各因子权重，比早期的硬编码 if-else 有质的提升。

### 2.6 全链路可观测性

- 自实现的轻量 Prometheus 兼容 metrics 注册表（无外部依赖）
- 每次请求携带 `X-Request-ID`
- `/metrics?format=prometheus` 与 `/metrics?format=json` 双出口
- Admin runtime 监控输出 broker lag、PgBouncer、Redis 内存水位、ClickHouse 写入失败率

### 2.7 契约测试 + OpenAPI Snapshot

`tests/contract/` 用 OpenAPI snapshot 做 breaking change 检测，配合 `make cutover-openapi-diff` 在发布前做 diff，工程化成熟度较高。

---

## 三、问题清单（按严重程度）

### 🔴 高危

#### P0-1：生产默认 Secret Key 未强制校验

```python
# infra/core/config.py
secret_key: str = Field(default="change-me-in-production", ...)
debug: bool = Field(default=True, ...)
allowed_origins: list[str] = Field(default_factory=lambda: ["*"], ...)
```

三个高危默认值同时存在：弱 secret key、debug 模式开启（暴露 /docs）、CORS 全开。生产环境若忘记覆盖任意一项，均为严重安全漏洞。

**修复**：在启动时对 `ENVIRONMENT=production` 做强制 assert，任意一项未覆盖就拒绝启动。

```python
@model_validator(mode="after")
def validate_production_safety(self) -> "Settings":
    if self.environment == "production":
        assert self.secret_key != "change-me-in-production", "SECRET_KEY must be set in production"
        assert not self.debug, "DEBUG must be False in production"
        assert "*" not in self.allowed_origins, "ALLOWED_ORIGINS must not contain wildcard in production"
    return self
```

#### P0-2：`kafka-python` 是同步库，在 async 路径中使用

`infra/events/broker.py` 的 `KafkaEventBroker` 通过 lazy import 使用了 `kafka-python`（同步 API）。在 async FastAPI worker 里调用会阻塞事件循环，高负载下会导致请求积压。

**修复**：改用 `aiokafka`（完整 asyncio 支持）替换 `kafka-python`。

---

### 🟠 中危

#### P1-1：`UoW` 和 `Session` 对具体缓存实现强耦合

`infra/db/session.py` 和 `infra/db/uow.py` 各自硬编码了 5 个 cache apply 函数调用。每新增一类缓存，需同时修改两个文件，且两者逻辑高度重复，容易出现不一致。

**修复**：引入缓存操作注册表（Registry）：

```python
# infra/cache/registry.py
_POST_COMMIT_HANDLERS: list[tuple[Callable, Callable]] = []

def register_cache_handler(pop_fn, apply_fn):
    _POST_COMMIT_HANDLERS.append((pop_fn, apply_fn))
```

UoW 只需遍历注册表执行，无需感知具体缓存类型。

#### P1-2：`pyproject.toml` 与 `requirements.txt` 双轨不一致

`pyproject.toml` 中 `dependencies = []` 为空，实际依赖全在 `requirements.txt`。这会导致 `pip install -e .` 无法安装任何依赖，工具链（如 dependabot、`pip install .`）行为不符预期。

**修复**：将 `requirements.txt` 的内容迁移到 `pyproject.toml` 的 `dependencies`，或明确文档化只用 requirements.txt，删除空的 `dependencies = []`。

#### P1-3：`celery` 和 `websockets` 作为幽灵依赖

`requirements.txt` 中包含 `celery==5.3.6` 和 `websockets==12.0`，但全项目代码中无任何 `from celery` 或 `import websockets` 引用。这增加了镜像体积（Celery 是重量级依赖），且可能引入安全面。

**修复**：直接从 `requirements.txt` 删除 `celery` 和 `websockets`。

#### P1-4：`pywebpush` 和 `py-vapid` 采用宽松 `>=` 锁定

```
pywebpush>=0.1.0
py-vapid>=1.8.0
```

这两个包处理 WebPush 加密，安全敏感。宽松的 `>=` 锁定在 CI 不同时间安装会得到不同版本，且可能在 major 升级时引入 breaking change。

**修复**：锁定到具体已测试版本（如 `pywebpush==2.0.0`），或统一使用 `pip-compile` 生成锁文件。

#### P1-5：`domains/signals/` 等文件存在 CRLF 换行符

`domains/signals/calibration_service.py`、`strategy_selector.py`、`exit_level_calculator.py` 等文件使用 Windows CRLF 换行，与项目其余文件（LF）不一致。这会导致 `black`/`isort` 格式化结果不稳定，在 Linux/Mac 上 `git diff` 中出现大量无意义变更。

**修复**：
```bash
git config core.autocrlf false
find domains/signals -name "*.py" -exec sed -i 's/\r//' {} \;
```
并在 `.gitattributes` 中统一声明 `*.py text eol=lf`。

#### P1-6：多个 domain 包缺少 `__init__.py`

```
domains/          # 无 __init__.py
domains/auth/     # 无 __init__.py
domains/account/  # 无 __init__.py
domains/portfolio/ # 无 __init__.py
... (共 7 个)
```

项目通过 pytest 的 `--import-mode=importlib` 绕过了这个问题，但在非 pytest 运行时（如直接 `python -m` 或 IDE 导入），导包路径可能异常。

**修复**：为所有 domain 目录补充空的 `__init__.py`。

---

### 🟡 低危 / 改善建议

#### P2-1：CI 缺少静态类型检查和安全扫描

`.github/workflows/qa.yml` 只运行 `make lint`（black + isort）和 `make qa-ci`，缺少：
- `mypy` 类型检查（`pyproject.toml` 中已配置但 CI 不运行）
- `bandit` 安全扫描
- `safety check` 依赖漏洞扫描

且 `pyproject.toml` 中 `disallow_untyped_defs = false`，降低了类型安全强度。

#### P2-2：Admin API `GET /metrics` 依赖 DB Session

```python
# apps/admin_api/main.py
async def metrics_endpoint(
    ...
    db: AsyncSession = Depends(get_db_session),  # metrics 端点打 DB？
):
```

metrics 端点被监控系统高频拉取，注入 DB session 会在 DB 负载高时导致监控端点本身变慢，产生虚假的"全局不可用"假象。

**修复**：将 runtime metrics 的 DB 查询改为后台异步缓存刷新，metrics endpoint 只读缓存。

#### P2-3：`backtest/service.py` 存在潜在 N+1

```python
for symbol in (symbols or await self._list_symbols())
```

在未传入 symbols 时，先全量拉取 symbol 列表，再对每个 symbol 执行操作。若 symbol 数量大，会产生大量串行 DB 查询。建议在 `_list_symbols()` 加分批处理并用 `asyncio.gather` 并发执行。

#### P2-4：`HistogramMetric` 使用内存 deque，重启后丢失

自实现的 metrics 注册表将 histogram samples 存在 `deque(maxlen=2048)` 中，服务重启后数据归零，不适合追踪重启期间的 SLO 趋势。建议接入 Prometheus push gateway 或使用 `prometheus-client` 替换。

---

## 四、QA 全面检查

### 4.1 测试覆盖分析

| 测试层 | 文件数 | 覆盖范围 | 健康状态 |
|---|---|---|---|
| `tests/unit/` | 64 文件，8154 行 | 所有 domain + infra | ✅ 良好 |
| `tests/integration/` | 11 文件 | admin routers、trades、notifications | ✅ 良好 |
| `tests/contract/` | 2 文件 | OpenAPI snapshot | ✅ 已有基础 |
| `tests/e2e/` | 7 文件 | 主要用户流 | ✅ 良好 |
| `tests/load/` | Locust scenarios | auth/trade/notification | ⚠️ 只验证 import，不跑实际 load |

### 4.2 QA 缺口

| 缺口 | 风险 | 建议 |
|---|---|---|
| Signal engine 回测闭环无自动化验证 | 高 | `run_live_strategy_goal_benchmark.py` 加入 CI gate |
| `infra/events/broker.py` KafkaEventBroker 无集成测试 | 中 | 用 `kafka-python-embedded` 或 testcontainers 覆盖 |
| 三端 HTML/JS 无任何前端测试 | 中 | 加 Playwright e2e 覆盖关键路径 |
| Worker 的幂等性（重复消费同一事件）未测试 | 中 | 为 outbox relay worker 补充重复消费测试 |
| CRLF 文件的 `make lint` 通过但 black 可能静默跳过 | 低 | 加 `grep -r $'\r' domains/` 到 lint |

### 4.3 Smoke Test 验证

`run_platform_workbench_smoke.py` 和 `run_platform_workbench_interaction_smoke.cjs` 覆盖了：
- `admin-auth` send-code → verify → refresh → logout 完整鉴权流
- platform 首屏路由、reload restore、JS 标记验证
- 只读数据链路（search / watchlist / portfolio）

**发现**：smoke 脚本有 `--timeout` 参数但 `Makefile` 中 `PLATFORM_SMOKE_TIMEOUT` 没有默认值，若未设置会导致参数传递异常。建议在 Makefile 加：

```makefile
PLATFORM_SMOKE_TIMEOUT ?= 30
```

### 4.4 负载测试基准

Locust scenarios 覆盖 `auth_read`、`trade_action`、`notification_read`、`tradingagents_submit`，结构合理。主要问题：CI 中只验证 import（`make test-load-import`），没有在 staging 跑实际压测的自动触发机制。

---

## 五、优化建议（按优先级）

### 5.1 安全加固（立即）

```
1. 添加生产环境启动校验 validator（见 P0-1）
2. 删除 celery、websockets 依赖
3. 将 pywebpush、py-vapid 锁定到具体版本
4. 在 CI 加 bandit -r apps/ domains/ infra/ 安全扫描
5. 在 CI 加 safety check
```

### 5.2 代码质量（本周）

```
1. 修复 CRLF 换行问题（git 配置 + sed 批量处理）
2. 补全 7 个缺失的 __init__.py
3. 将 pyproject.toml dependencies 与 requirements.txt 对齐
4. 引入缓存操作注册表，解耦 UoW/Session 与具体缓存实现
5. 在 CI 中启用 mypy（可先从 --ignore-missing-imports 开始渐进引入）
```

### 5.3 性能优化（本月）

```
1. 替换 kafka-python → aiokafka（解除 async 阻塞风险）
2. Admin /metrics 端点改为读取后台缓存，去除 DB 依赖
3. backtest/service.py 的 symbol 遍历改为分批并发
4. 评估 HistogramMetric 是否需要接入外部 Prometheus
```

### 5.4 可测试性（本月）

```
1. 将 run_live_strategy_goal_benchmark.py 加入 CI，作为策略质量 gate
2. 为 KafkaEventBroker 补充集成测试
3. 为三端 HTML 加 Playwright 冒烟测试
4. 为 outbox worker 补充重复消费幂等性测试
5. 修复 PLATFORM_SMOKE_TIMEOUT 默认值缺失
```

---

## 六、下一步开发建议

> 基于 `docs/POST_MIGRATION_V2_PLAN.md` 和代码审查，按优先级从高到低排列。

### Phase 1：策略引擎闭环（最高优先级，2-3 周）

当前 `StrategySelector.select()` 虽已支持 ranking 输入，但 ranking 反馈回路尚未自动化。

**具体目标**：

**1.1 策略权重自动回写**

基于回测结果，自动更新 `calibration_snapshot` 的 `strategy_weights`，让下次信号评分能利用历史胜率数据：

```
domains/analytics/backtest/service.py → 计算胜率
↓
domains/signals/calibration_proposal_service.py → 生成新 calibration snapshot
↓
admin API /v1/admin/calibrations/apply → 持久化并广播
↓
CalibrationService 在下次评分时使用新权重
```

**1.2 评分因子版本化**

在 `CalibrationSnapshot` 中加入 `effective_from` 时间戳，支持历史回溯和 A/B 比对，避免权重变更后无法归因。

**1.3 策略选择可解释性 API**

在 platform 桌面端暴露 `GET /v1/signals/{id}/strategy-breakdown`，返回当前信号用哪个策略、为什么、权重是多少，让用户能理解系统决策。

---

### Phase 2：服务端退出位所有权收口（2 周）

当前 `ExitLevelCalculator` 已能基于 ATR 计算退出位，但 `desktop_signal_service.py` 在 ingest 时优先使用桌面端传入值，服务端计算只作为 fallback。

**具体目标**：

**2.1 明确所有权分层**

```
桌面端传入 stop_loss/tp → 作为"用户偏好"存入 extra_payload
服务端 ExitLevelCalculator → 生成"系统建议"存入 analysis
前端展示时：用户偏好覆盖系统建议，但两者均可查看和比对
```

**2.2 退出位质量追踪**

在 `domains/analytics/` 新增 exit quality read model：追踪历史信号的实际退出价与建议退出位的偏差，为后续 ATR 乘数校准提供数据。

**2.3 动态 ATR 乘数**

将 `ExitLevelCalculator.DEFAULT_ATR_MULTIPLIERS` 从硬编码字典迁移到 `CalibrationSnapshot`，允许通过 admin 接口动态调整不同市场状态下的止损倍数。

---

### Phase 3：市场状态细化（1-2 周）

当前 `MarketRegimeDetector` 将市场分为 `trend / volatile / range` 三态，对策略选择和退出位调整已足够，但对以下场景不够精确：

**具体目标**：

**3.1 增加细分状态**

```python
# 新增状态
"trend_strong"     # 强势趋势（momentum > 0.8 且 trend > 0.7）
"trend_weak"       # 弱趋势（逐步衰减）
"volatile_up"      # 上行波动（区别于下行）
"volatile_down"    # 下行波动
"range_tight"      # 窄幅震荡（波动率极低）
```

**3.2 状态持续时间感知**

在 `MarketRegimeAssessment` 中加入 `regime_duration_bars` 字段，让策略选择能感知"这个状态已持续多久"，避免在趋势末期仍选择趋势追踪策略。

---

### Phase 4：Platform 桌面端 UI 能力补全（3-4 周）

当前 `/platform` 已实现：symbol search、watchlist/portfolio、trade lookup、admin-auth 鉴权。

待补全：

| 功能 | 对应后端 API | 优先级 |
|---|---|---|
| 回测结果可视化（胜率、排名、equity curve） | `/v1/admin/backtests/*` | 高 |
| 信号评分分解展示 | 需新增 API（见 Phase 1.3） | 高 |
| 策略参数调整面板（买入条件、ATR 乘数） | `/v1/admin/calibrations/*` | 中 |
| 实时扫描结果流 | `/v1/admin/scanner/*` | 中 |
| 退出位对比视图（系统建议 vs 用户设置） | 需新增 API（见 Phase 2.1） | 中 |

---

### Phase 5：容量与部署演进（持续）

**5.1 Compose → K8s 迁移路径**

当前 `ops/k8s/base/` 已有 K8s baseline，但默认交付面仍是 Compose。建议：

```
1. 先在 staging 用 K8s 跑 load baseline，对比 Compose 性能
2. 关键 worker（event_pipeline、notification_orchestrator）先迁入 K8s
3. 用 HPA 验证 worker 水平扩展效果
4. Public API 最后迁入（需处理 session affinity）
```

**5.2 Redis 内存分区**

当前 Redis 同时承载缓存、fill lock、broker 协调键、session，`volatile-ttl` 策略已是正确选择，但建议：
- 将 broker-相关 key 独立到专用 Redis 实例（或 Redis Cluster 的专用 slot range）
- 避免缓存被驱逐时影响 Streams 消费进度

**5.3 ClickHouse 写入失败率告警**

Admin runtime 已监控 ClickHouse 写入失败率，建议在 `/v1/admin/runtime/alerts` 中加入自动阈值触发，而不仅靠人工轮询。

---

## 七、总结评分

| 维度 | 评分 | 说明 |
|---|---|---|
| 架构设计 | 9/10 | DDD 分层清晰，事件模式成熟 |
| 安全性 | 6/10 | 默认值存在高危隐患，需立即修复 |
| 代码质量 | 8/10 | 整体规范，CRLF / 幽灵依赖等小问题 |
| 测试覆盖 | 8/10 | 多层测试体系完善，缺少 Playwright 和策略 CI gate |
| 可观测性 | 8/10 | metrics + request tracing 完善，histogram 不持久 |
| 性能设计 | 8/10 | async 全链路，PgBouncer 适配正确，Kafka 同步库需替换 |
| 策略引擎 | 7/10 | 已有 calibration 框架，反馈回路尚未闭合 |
| 运维工具链 | 9/10 | load/cutover/backup/K8s 工具链完整 |

**综合评分：7.9 / 10**

项目已具备 production-ready 的工程骨架，核心安全问题（默认 SECRET_KEY / CORS 全开）需立即处理，策略闭环是最高价值的下一步开发方向。
