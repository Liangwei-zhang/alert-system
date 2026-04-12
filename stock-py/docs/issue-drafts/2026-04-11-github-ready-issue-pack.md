# GitHub Ready Issue Pack

这份文件用于把当前 `docs/issue-drafts/` 下的拆分稿进一步压缩成可直接贴到 GitHub 的标题与正文。

## 01

### Title

深化稳定版 `/platform` 市场工作台

### Body

#### 背景

当前稳定版 `/platform` 已具备稳定工作台壳层、符号路由、watchlist / portfolio / trades 接入和管理员会话能力，但“市场观察与图表工作台”仍然偏浅。

#### 目标

在不引入并行 `/next/*` UI 的前提下，把 `/platform` 深化为可用的市场工作台。

#### 范围

- 加入标准 OHLCV / K 线主图能力
- 串起 symbol search -> 图表 -> watchlist -> 当前价格 / 最近走势
- 增强准实时刷新能力，优先轮询兜底
- 补齐 watchlist 的最小可用交互，如排序、手动 pin、批量清理

#### 验收

- 用户能在 `/platform` 完成 symbol 搜索 -> 打开图表 -> 加入 watchlist -> 查看当前价格与最近走势
- 图表能叠加至少一类已有策略或信号水位，不是纯静态图
- 页面兼容桌面和移动宽度
- 不新增 `/next/*` 或第二套桌面 UI

## 02

### Title

把信号、Scanner、回测与校准视图收口到 `/platform`

### Body

#### 背景

当前仓库已经有 signal metadata、signal quality、signal results、scanner observability、strategy health、calibration snapshots / proposal / activate 等能力，但产品上仍主要停留在 admin 治理面。

#### 目标

把这些能力在稳定版 `/platform` 上做成策略情报面板，而不是继续只停留在 admin。

#### 范围

- signal timeline / signal detail 可视化
- scanner live decision 观察面板
- backtest runs / strategy health 基础可视化
- calibration active snapshot / proposal 阅读入口

#### 验收

- `/platform` 能直接查看最近信号、信号解释、score breakdown、exit metadata、calibration version
- `/platform` 能查看 scanner live decisions、backtests、strategy health、active calibration 与 proposal 概况
- 信息架构仍保持“策略工作台”，不是新的 admin 控制台

## 03

### Title

补齐 `/platform` 的预警、持仓与执行闭环

### Body

#### 背景

当前 `/platform` 已有 shared watchlist、portfolio、trade lookup 与 app trade execution 等基础，但从策略决策到执行确认的工作流还不够紧密。

#### 目标

让 `/platform` 承担“策略 -> 预警 -> 人工确认 -> 持仓跟踪”的单一工作台职责。

#### 范围

- 展示最近 alerts / notifications 与待处理动作
- 补齐 confirm / ignore / adjust 等快速入口
- 增强 portfolio / holdings / trade timeline 可视化
- 增加最小可用的 P&L 区块

#### 验收

- 平台端能从 signal / alert 直接进入执行或忽略动作
- 平台端能查看持仓概览、最近交易记录和至少一类收益变化视图
- 相关上下文在刷新后能恢复到正确的 symbol / section

## 04

### Title

完善稳定版 `/app` 订阅端体验

### Body

#### 背景

当前 `/app` 已有 auth、watchlist、notifications、离线草稿等基础入口，但交互深度仍偏轻。

#### 目标

在不改变纯 HTML/JS 路线的前提下，把 `/app` 推进到可持续使用的订阅端界面。

#### 范围

- 完善验证码登录、会话恢复、错误提示与状态反馈
- 补强资产总览、watchlist、持仓、通知中心展示深度
- 补齐 WebPush 注册/解绑的用户流程
- 优化表单保存、本地草稿与同步动作一致性

#### 验收

- 用户能完成登录、恢复会话、查看资产概览、维护 watchlist、管理通知的完整闭环
- WebPush 状态和失败提示对非技术用户可理解

## 05

### Title

强化稳定版 `/admin` 的运营与治理可视化

### Body

#### 背景

当前 `/admin` 已具备 operators、distribution、tasks、runtime、analytics、acceptance、calibrations 等能力，但部分场景仍更像 API console。

#### 目标

让 `/admin` 更清晰承担“用户 / 推送 / 治理 / 监控”职责，并减少日常运维对手动 API 调用的依赖。

#### 范围

- 增强 operators / users / task center / distribution 的可视化与反馈
- 补强 runtime / alerts / audit / acceptance 的组织方式
- 明确 admin 与 platform 的职责边界
- 优化 admin API console，但不让它变成主交互

#### 验收

- 常用 operators / tasks / runtime / acceptance 工作流不依赖手动拼 API 请求
- admin 中各能力域边界更清晰，说明与入口组织更贴近真实产品职责

## 06

### Title

生产硬化与高可用证据沉淀

### Body

#### 背景

当前仓库已具备 compose-first 交付、load baseline、cutover rehearsal、K8s baseline 与 PgBouncer / Kafka / ClickHouse / MinIO 等骨架，但距离“有证据地证明可交付、可回滚、可扩容”仍有距离。

#### 目标

把现有工具链与运行时能力进一步产品化，形成稳定的高可用与交付证据。

#### 范围

- 继续打磨 load baseline / cutover / threshold calibration 流程
- 强化 compose-first 交付下的运行时监控、告警与回滚证据
- 推进读路径缓存、notification fanout、scanner 分桶 / 分片中的至少一项进入可验证实现
- 沉淀关键运行结论对应的自动化或半自动化产物

#### 验收

- baseline、cutover、runtime evidence 有清晰目录、命令和验收产物
- 至少一项容量/缓存相关能力进入可验证实现
- 关键高可用结论可通过 runbook / report / QA 命令复现