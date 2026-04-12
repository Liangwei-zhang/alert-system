# Issue 03: 补齐 `/platform` 的预警、持仓与执行闭环

## 背景

当前稳定版 `/platform` 已有 shared watchlist / portfolio / trade lookup / app trade execution 等基础，但从策略决策到执行确认的工作流仍不够紧密，持仓分析深度也偏浅。

## 目标

让 `/platform` 真正承担“策略 -> 预警 -> 人工确认 -> 持仓跟踪”的单一工作台职责。

## 范围

- 在平台端展示最近 alerts / notifications 与待处理交易动作
- 补齐 confirm / ignore / adjust 等快速执行入口
- 增强 portfolio 概览与 holdings / trade timeline 可视化
- 增加最小可用的 P&L / 收益跟踪区块

## 建议实现边界

- 复用现有 `portfolio`、`trades`、`notifications` 路由，不平行造新模型
- 若需要新增计算，优先补 `domains/portfolio` 下的薄服务，而不是新建一套 analytics 子系统
- 平台端操作要面向 desk workflow，避免照搬 admin task center 风格

## 涉及区域

- `frontend/platform/index.html`
- `frontend/platform/js/platform-deck.js`
- `frontend/platform/js/platform-deck-workspace.js`
- 可能新增：`domains/portfolio/pnl_service.py`
- 现有后端接口：
  - public `portfolio` / `trades` / `notifications`
  - admin `tasks/trades` 仅作为高权限补充路径

## 验收标准

- 平台端能从 signal/alert 直接进入执行或忽略动作
- 平台端能查看持仓概览、最近交易记录与至少一类收益变化视图
- 相关操作在刷新后仍能恢复到正确的 symbol / section 上下文
- 不把这些流程拆去 `/admin` 完成

## 非目标

- 不实现全自动下单引擎
- 不在这条 issue 内完成完整多账户资金分析
