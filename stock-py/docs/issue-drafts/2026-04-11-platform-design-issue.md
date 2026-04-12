# Stock-py 后续开发计划与桌面端详细设计文档

> 备注：这份总稿保留为背景说明。
> 若要提交到 GitHub，优先使用同目录下已拆分的 issue drafts，而不是直接把这份长文作为单条 issue。

基于对仓库的全面分析，以下是针对 `stock-py` 项目的后续开发规划。项目后端已基本完成迁移，三端 UI 已收回 Python 直出 HTML 路由，当前瓶颈集中在桌面端（Platform）的功能覆盖深度。

## 一、现状总结

| 维度 | 当前状态 |
|---|---|
| 核心后端服务 | 已完成（FastAPI async, 12+ domain modules） |
| Public API | 已迁移，含 sidecar/monitoring 兼容面 |
| Admin API | 已迁移（analytics, runtime, tasks, operators 等 20+ router） |
| Workers / Scheduler | 已完成，13 个 worker + APScheduler 编排 |
| 数据平面 | 已完成，PgBouncer + Kafka + ClickHouse + MinIO baseline |
| 部署运维 | 已完成，Docker Compose + K8s baseline + QA/cutover 工具链 |
| 三端 UI | Python 直出 HTML shell，功能覆盖深度不足 |

桌面端（`/platform`）是当前最大瓶颈：目前只是通过 `apps/public_api/routers/ui.py` + `ui_shell.py` 输出的纯 HTML shell，缺乏真正的交互式桌面级体验，例如 K 线图表、实时行情、策略引擎可视化、持仓管理面板等。

## 二、后续开发计划总览

- Phase 1：桌面端 Platform 功能深度覆盖
- Phase 2：订阅端 Subscriber 体验完善
- Phase 3：管理端 Admin 运营面板强化
- Phase 4：生产硬化与高可用

## 三、Phase 1：桌面端（Platform）详细设计

### 1. 架构方案

当前 `/platform` 路由由 `ui.py` 输出纯 HTML，后续方案分为两条路径：

```text
方案 A（推荐）：保持 Python 直出，前端用 Vanilla JS + Web Components
  优势：零编译、与现有 FastAPI 无缝集成、部署简单
  图表：TradingView Lightweight Charts / Apache ECharts
  实时：WebSocket（已有 websockets==12.0 依赖）

方案 B：引入轻量前端框架（如 Alpine.js + htmx）
  优势：渐进增强、服务端驱动、无需 npm 工具链
  适合：已有 HTML shell 基础上渐进式升级
```

### 2. 桌面端功能模块拆分

基于 README 中定义的 Platform 职责：

#### 2.1 股票监控模块

```text
/platform/watchlist          — 实时监控列表
/platform/quote/{symbol}     — 单股实时报价详情
/platform/search             — 全局股票搜索
```

| 功能 | 后端支撑 | 前端需求 | 优先级 |
|---|---|---|---|
| 实时报价面板 | `routers/sidecars.py` (Yahoo/Binance proxy) | WebSocket + 价格闪烁动画 | P0 |
| 监控列表管理 | `routers/watchlist.py` (CRUD) | 拖拽排序、分组、批量操作 | P0 |
| 股票搜索 | `routers/search.py` (pg_trgm) | 即时搜索、历史记录 | P0 |
| K 线图表 | `infra/market_data/` | TradingView Lightweight Charts | P0 |

#### 2.2 核心算法模块

```text
/platform/signals            — 信号生成历史
/platform/scanner            — Scanner 实时决策
/platform/backtest           — 回测运行与结果
/platform/regime             — Market Regime 面板
```

| 功能 | 后端支撑 | 前端需求 | 优先级 |
|---|---|---|---|
| 信号列表与详情 | `domains/signals/*` + admin signal-stats | 时间轴视图、信号标记叠加到 K 线 | P0 |
| Scanner 实时决策 | `admin/scanner/live-decision` | 实时刷新表格、decision 状态着色 | P1 |
| 回测管理 | `admin/backtests/runs` | 触发/查看回测、equity curve 图表 | P1 |
| Strategy Health | `admin/analytics/strategy-health` | 策略胜率/夏普比率可视化 | P1 |

#### 2.3 预警系统模块

```text
/platform/alerts             — 预警触发与确认
/platform/alerts/config      — 预警规则配置
/platform/distribution       — 分发管理
```

| 功能 | 后端支撑 | 前端需求 | 优先级 |
|---|---|---|---|
| 预警列表 | `routers/notifications.py` | 实时推送 + 桌面通知 | P0 |
| 预警确认/忽略 | `routers/trades.py` (confirm/ignore/adjust) | 快速操作面板 | P0 |
| WebPush 管理 | `notifications.py` push-devices | 设备注册/取消 | P1 |
| 手动分发 | `admin/distribution/manual-message` | 消息编辑器 | P2 |

#### 2.4 持仓管理模块

```text
/platform/portfolio          — 持仓展示
/platform/portfolio/trades   — 交易记录
/platform/portfolio/pnl      — 盈亏分析
```

| 功能 | 后端支撑 | 前端需求 | 优先级 |
|---|---|---|---|
| 持仓概览 | `routers/portfolio.py` | 饼图/表格、实时市值计算 | P0 |
| 交易记录 | `routers/trades.py` | 时间线、筛选、导出 | P1 |
| P&L 分析 | `domains/portfolio/*` + `domains/analytics/*` | 折线图、区间收益计算 | P1 |

### 3. 前端技术实现方案

#### 3.1 文件结构

在现有 `ui_shell.py` 基础上扩展：

```text
apps/public_api/
├── ui_shell.py              # 现有 HTML shell 生成器，扩展为模板引擎入口
├── static/                  # 新增静态资源目录
│   ├── css/
│   │   ├── platform.css
│   │   ├── theme-dark.css
│   │   └── theme-light.css
│   ├── js/
│   │   ├── platform/
│   │   │   ├── app.js
│   │   │   ├── watchlist.js
│   │   │   ├── chart.js
│   │   │   ├── signals.js
│   │   │   ├── portfolio.js
│   │   │   └── ws.js
│   │   ├── shared/
│   │   │   ├── api.js
│   │   │   ├── auth.js
│   │   │   └── notify.js
│   │   └── vendor/
│   │       └── lightweight-charts.js
│   └── assets/
│       └── icons/
└── routers/
    └── ui.py                # 现有路由，新增 static file mount
```

#### 3.2 WebSocket 实时数据推送

```python
# 新增 apps/public_api/routers/ws.py
@router.websocket("/ws/quotes")
async def quote_stream(websocket: WebSocket):
    """实时行情推送，复用 infra/market_data/ 数据源"""


@router.websocket("/ws/alerts")
async def alert_stream(websocket: WebSocket):
    """预警实时推送，复用 event_pipeline dispatcher"""
```

#### 3.3 K 线图表集成

```javascript
// static/js/platform/chart.js
// 基于 TradingView Lightweight Charts
// 数据源: GET /api/yahoo/{symbol} (已有 sidecar)
// 信号标记: GET /v1/admin/signal-stats (已有)
// 实时更新: WebSocket /ws/quotes (新增)
```

### 4. 后端补充需求

| 需要新增的后端能力 | 说明 | 涉及文件 |
|---|---|---|
| WebSocket 路由 | 实时行情/预警推送 | `apps/public_api/routers/ws.py` |
| Static file serving | CSS/JS/图片静态资源 | `apps/public_api/main.py` |
| Portfolio P&L 计算 | 基于持仓 + 实时价格的 P&L | `domains/portfolio/pnl_service.py` |
| Admin login route | 当前 admin 仍需手动贴 token | `apps/admin_api/routers/auth.py` |
| Chart data API | OHLCV 历史数据标准接口 | `apps/public_api/routers/chart_data.py` |

## 四、Phase 2：订阅端（Subscriber）体验完善

| 功能 | 当前状态 | 需补齐 |
|---|---|---|
| 登录/注册流程 | 后端已有 `/v1/auth/*` | 前端表单 + 验证码 UI |
| 资产总览 | 后端已有 `/v1/account/dashboard` | 数据可视化面板 |
| Watchlist 管理 | 后端已有 CRUD | 拖拽交互、分组 |
| 通知中心 | 后端已有 notifications API | WebPush 注册流程 UI |

## 五、Phase 3：管理端（Admin）运营面板

| 功能 | 当前状态 | 需补齐 |
|---|---|---|
| Admin 登录 | 需手动贴 bearer token | 独立 admin login route |
| Analytics 面板 | 后端已有 overview/distribution/strategy-health | 图表可视化 |
| Tasks 运营中心 | 后端已有 receipts/emails/outbox/trades | 操作 UI |
| Runtime 监控 | 后端已有 stats/health/metrics/alerts | 仪表盘 |

## 六、Phase 4：生产硬化

| 方向 | 具体内容 |
|---|---|
| 高可用 | Kafka 多节点、PostgreSQL 主从、Redis Sentinel |
| 安全 | HTTPS 强制、CSP headers、CSRF protection |
| 可观测性 | Prometheus + Grafana 完整对接（已有 metrics 出口） |
| CI/CD | 自动化部署流水线、灰度发布 |

## 七、里程碑建议

| 里程碑 | 目标 | 预计周期 |
|---|---|---|
| M1 | Platform 基础骨架：K 线图表 + 实时报价 + Watchlist UI | 3-4 周 |
| M2 | Platform 核心功能：信号面板 + 预警确认 + 持仓展示 | 3-4 周 |
| M3 | Subscriber 端 UI + Admin 登录 | 2-3 周 |
| M4 | Admin 运营面板 + 回测可视化 | 3-4 周 |
| M5 | 生产硬化 + 全平台测试 + 正式发布 | 2-3 周 |

以上设计文档已整理为 issue draft。如需进一步细化某个模块的 API 设计、组件接口或代码实现，可在此基础上继续拆分。