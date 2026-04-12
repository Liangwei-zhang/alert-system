# stock-py UI / Product Surface Issue 拆分清单

这份清单用于替代“大而全”的单条设计 issue，把当前仓库真实边界下的后续产品面开发拆成一组可执行 issue。

拆分原则：

- 以当前稳定版三端为前提：`/app`、`/platform`、`/admin`
- 不再引入并行 `/next/*` 新桌面 UI
- 优先复用现有 public/admin API 与 worker 链路
- 先做功能覆盖深度，不做脱离当前仓库的大重构

建议提交顺序：

1. `2026-04-11-01-platform-market-workbench.md`
2. `2026-04-11-02-platform-signal-intelligence.md`
3. `2026-04-11-03-platform-alerts-portfolio-execution.md`
4. `2026-04-11-04-subscriber-surface-polish.md`
5. `2026-04-11-05-admin-ops-visualization.md`
6. `2026-04-11-06-production-hardening.md`

依赖关系：

- Issue 01 是 `/platform` 深化的基础 issue
- Issue 02 和 Issue 03 都依赖 Issue 01 的工作台深化与图表/符号上下文能力
- Issue 04 和 Issue 05 可并行推进，但应复用同一套稳定 HTML/JS 模式
- Issue 06 放在前三到五项完成后执行，用于把产品面能力沉淀为可交付能力

与当前仓库状态的对应：

- `/platform` 已经具备稳定工作台、admin-auth、signal metadata、tradingagents workbench 等基础，不是从零开始
- `/admin` 已经有 operators、distribution、tasks、runtime、analytics、calibration 等治理面板，不应重新定义为策略产品中心
- `/app` 已经具备 auth / watchlist / notifications 的基础壳层，应继续补交互深度，而不是重做端形态
