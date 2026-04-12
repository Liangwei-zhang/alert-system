# Issue 02: 把信号、Scanner、回测与校准视图收口到 `/platform`

## 背景

当前仓库已经有：

- signal metadata / signal quality / signal results 基线
- scanner observability 与 live decision
- backtests / strategy-health
- calibration snapshot / proposal / apply / activate

这些能力技术上仍主要从 `admin_api` 暴露，但产品上属于桌面端策略核心的一部分。

## 目标

把现有信号、Scanner、回测与校准能力在稳定版 `/platform` 上做成可操作的策略情报面板，而不是继续只停留在 admin 治理面。

## 范围

- 在 `/platform` 中加入 signal timeline / signal detail 可视化
- 加入 scanner live decision 视图或轻量观察面板
- 加入 backtest runs / strategy health 基础可视化
- 加入 calibration version / active snapshot / proposal 的阅读与理解入口

## 建议实现边界

- 第一阶段允许复用现有 `admin_api` 只读接口，通过桌面端已有 admin-auth 能力访问
- 若发现 `/platform` 依赖过多高权限 admin 接口，再逐步抽取 public-facing 只读 facade
- 平台端展示应优先服务“策略判断与迭代”，不要做成新的管理后台

## 涉及区域

- `frontend/platform/index.html`
- `frontend/platform/js/platform-deck.js`
- `frontend/platform/js/platform-deck-workspace.js`
- `frontend/platform/js/platform-deck-tradingagents.js`
- 现有后端接口：
  - `/v1/admin/signal-stats/*`
  - `/v1/admin/scanner/*`
  - `/v1/admin/backtests/*`
  - `/v1/admin/analytics/strategy-health`
  - `/v1/admin/analytics/signal-results`
  - `/v1/admin/calibrations/*`

## 验收标准

- `/platform` 能直接查看最近信号、信号解释、score breakdown、exit metadata、calibration version
- `/platform` 能查看 scanner live decisions 与最近回测 / strategy health 状态
- `/platform` 能查看当前 active calibration 与最新 proposal 概况
- 桌面端页面的信息架构仍以策略工作台为中心，不把运营任务混入主视图
- 覆盖新增 UI 的 smoke / route / integration 验证存在

## 非目标

- 不在这条 issue 内重写现有信号引擎
- 不在这条 issue 内引入复杂回测编辑器
- 不要求第一版就做到 row-level signal-trade exact reconciliation
