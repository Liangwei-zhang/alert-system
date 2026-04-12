# Issue 01: 深化稳定版 `/platform` 市场工作台

## 背景

当前稳定版 `/platform` 已有工作台壳层、符号路由、search/watchlist/portfolio/trades 接入与 admin-auth 能力，但“市场观察与图表工作台”仍不够深，距离桌面级策略入口还有明显差距。

## 目标

在不引入并行新 UI 的前提下，把现有 `/platform` 深化为可用的市场工作台。

## 范围

- 在现有 `frontend/platform` 基础上加入标准 OHLCV / K 线主图能力
- 把 symbol search、watchlist、quote detail、chart context 串成同一个工作流
- 加入更稳定的实时或准实时报价刷新机制
- 补齐 watchlist 的分组、批量操作、排序或其它最小可用交互

## 建议实现边界

- 优先复用现有 sidecar / market-data 能力，不先重做数据源
- 可新增 `apps/public_api/routers/chart_data.py` 之类的薄接口
- 实时能力优先考虑“轮询兜底 + WebSocket 增强”，避免先把产品可用性绑死在 WebSocket-only 路径
- 保持稳定版纯 HTML/JS 交付，不引入 Node build pipeline

## 涉及区域

- `frontend/platform/index.html`
- `frontend/platform/js/platform-deck.js`
- `frontend/platform/js/platform-deck-workspace.js`
- `apps/public_api/routers/ui.py`
- 可能新增：`apps/public_api/routers/chart_data.py`
- 可能新增：`apps/public_api/routers/ws.py`

## 验收标准

- 用户能在 `/platform` 里完成 symbol 搜索 -> 打开图表 -> 加入 watchlist -> 查看当前价格与最近走势 的闭环
- 图表能叠加至少一类已有策略信息或信号标记，不是纯静态 K 线
- 页面在桌面端与常见移动端宽度下都可正常渲染
- 不新增 `/next/*` 或第二套平行桌面 UI
- 新增或改动的前端与接口有对应 smoke / unit / route 测试

## 非目标

- 不在这条 issue 内做完整策略分析面板
- 不在这条 issue 内做自动交易执行
- 不在这条 issue 内引入前端框架或 npm 构建系统
