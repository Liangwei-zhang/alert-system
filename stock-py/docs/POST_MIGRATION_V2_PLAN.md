# stock-py 后期开发计划 V2

状态：2026-04-11

这份文档是基于当前 `stock-py` 仓库真实代码状态收敛出来的实施版设计，不再沿用 `todo.md` 中那份过度铺开的目标态草案。

核心原则只有一条：先沿着现有仓库已经跑通的主链路演进，而不是为了“设计完整”去引入第二套运行模型。

## 1. 当前系统边界

### 1.1 运行时边界

当前系统不是前后端分离微服务，也不是以 Celery 为主的任务平台，而是：

- `apps/public_api/main.py`：Public API 与三端静态 UI 入口
- `apps/admin_api/main.py`：高权限管理与运行时治理接口
- `apps/scheduler/main.py`：周期调度入口
- `apps/workers/*`：scanner、market_data、event_pipeline、notification、retention、tradingagents_bridge、analytics_sink、cold_storage 等专用 worker
- `ops/docker-compose.yml`：默认交付面

### 1.2 UI 边界

当前稳定版 UI 只有三套：

- `/app` → `frontend/app`
- `/platform` → `frontend/platform`
- `/admin` → `frontend/admin`

这些页面由 `apps/public_api/routers/ui.py` 直接托管静态 HTML / JS，不再存在并行的 `/next/*` 桌面 UI 路由，也不应再围绕旧的“并行新版 UI”做设计。

### 1.3 部署边界

当前默认交付面仍然是：

- `docker compose + nginx + VM`
- 本地/预发的 load baseline、cutover rehearsal、backup/restore 已有工具链
- K8s baseline 存在，但当前不是默认交付面

因此后续容量与运维设计必须优先贴合 compose-first 的现状，而不是直接按 K8s-first 组织项目。

## 2. 已验证的真实瓶颈

这些问题都能在当前代码里直接看到，不是抽象猜测。

### 2.1 策略选择仍以启发式为主

`domains/signals/live_strategy_engine.py` 里的 `select_strategy()` 仍然以 ranking 兜底加固定阈值分支为主：

- `dislocation >= 0.03` → `mean_reversion`
- `momentum >= 0.65` → `trend_continuation`
- `volatility >= 0.75` → `volatility_breakout`
- 其他 → `range_rotation`

这意味着当前策略引擎的核心问题不是“没有代码”，而是：

- 缺少明确的可替换策略接口
- 缺少服务端统一的策略解释层
- 缺少基于历史结果的权重回写

### 2.2 候选信号评分仍是固定线性组合

`score_candidate()` 当前仍然是固定加权打分：

- 固定 base score
- confidence / probability / risk_reward 固定换算
- volume / trend / reversal / quality 固定 bonus
- stale_data / low_liquidity 固定 penalty

问题不在“线性模型一定错”，而在于：

- 这些权重没有版本化
- 没有按市场状态分层
- 没有用回测/成交结果做闭环校准

### 2.3 退出位主要依赖外部传入

`domains/signals/desktop_signal_service.py` 在 ingest 时直接持久化：

- `stop_loss`
- `take_profit_1`
- `take_profit_2`
- `take_profit_3`

虽然 `analysis` 里已有 `atr_value`、`atr_multiplier` 等字段，但当前服务端仍未形成稳定的“服务端退出位计算责任”。

这会带来两个问题：

- 桌面端和服务端对退出逻辑的所有权不清晰
- 无法对历史退出质量做可解释校准

### 2.4 市场状态推断过薄

`_infer_market_regime()` 当前基本只把市场分成：

- `volatile`
- `trend`
- `range`

这对第一阶段是够用的，但对后续的策略选择、退出位调整、回测归因都不够细。

### 2.5 300 万日活还停留在“可扩展骨架”而非“已落地承载”

仓库已经有：

- PgBouncer
- Redis
- Kafka
- ClickHouse
- MinIO
- load / cutover / backup / restore 工具链

但这不等于已经证明能承载 300 万日活。当前更准确的说法应该是：

- 仓库已经具备向高并发架构演进的骨架
- 还没有把读缓存、fanout、scanner 分片、读副本和压测基线产品化

## 3. V2 设计原则

V2 不走“大爆炸重构”，而采用最小可演进策略。

### 3.1 保留现有主链路

以下链路不应在第一阶段推倒重来：

- `LiveStrategyEngine` 仍作为信号构建协调者存在
- `DesktopSignalService` 仍负责 ingest / dedupe / outbox publish
- `signals` 的现有 schema字段继续保留
- `scanner`、`backtest`、`analytics`、`notifications` 仍沿既有 worker 链路运行

### 3.2 服务端逐步接管策略解释与退出责任

不是一夜之间把桌面端变成“只显示，不计算”，而是分两步：

- 第一步：服务端在输入存在时兼容外部传入，同时能在缺省情况下自行补算退出位
- 第二步：服务端成为退出位和策略解释的权威来源，桌面端只负责展示和人工覆盖

### 3.3 先做可解释的规则化升级，再做复杂模型

在没有稳定结果闭环前，不建议直接引入：

- HMM
- LightGBM
- 黑盒 ML 排序器
- WebSocket-first 超大在线架构

第一阶段更合理的是：

- 可解释规则
- 有版本号的权重
- 有边界的回写校准
- 可回放的信号结果数据集

### 3.4 容量建设基于现有技术栈推进

容量扩展的默认路线必须基于当前栈：

- FastAPI
- APScheduler + 专用 workers
- PostgreSQL + PgBouncer
- Redis
- Kafka
- ClickHouse
- MinIO
- Compose-first 交付面

## 4. 目标模块结构

V2 不建议一次性拆出几十个新文件，先控制在少量关键模块内。

### 4.1 第一阶段建议新增模块

建议新增：

```text
domains/signals/
├── live_strategy_engine.py          # 保留协调者角色
├── strategy_selector.py             # 策略选择与 ranking/heuristic 适配
├── market_regime.py                 # 市场状态识别
├── exit_level_calculator.py         # 服务端退出位计算
├── calibration_service.py           # 权重校准与快照产出
└── strategy_profiles.py             # 4 个现有策略的规则配置
```

### 4.2 角色拆分

#### `live_strategy_engine.py`

保留它作为总协调器，职责变成：

- 读取 snapshot/context
- 调用 `StrategySelector`
- 调用 `ExitLevelCalculator`
- 组装 `SignalCandidate`
- 回填 `analysis` 中的解释字段

#### `strategy_selector.py`

负责：

- ranking 结果归一化
- heuristic 策略规则适配
- 策略得分合并
- 输出统一的 `strategy_selection` 结果

这里不直接上“投票器大框架”，先把当前 4 个策略和 ranking 路径结构化。

#### `market_regime.py`

负责：

- 用当前已有输入先做增强版 regime 分类
- 仍然保持规则驱动
- 输出带解释的 regime 结果

第一版建议只扩到：

- `trend_up`
- `trend_down`
- `range`
- `volatile`
- `breakout_candidate`

不建议第一版就做 6 到 8 种复杂状态和 HMM。

#### `exit_level_calculator.py`

负责：

- 依据 `entry_price`、`atr_value`、`atr_multiplier`、`market_regime`、`risk_reward_ratio` 计算默认退出位
- 当请求显式传入 stop/tp 时保留兼容
- 输出退出位来源，例如：`client`、`server_default`、`server_adjusted`

第一阶段只算：

- `stop_loss`
- `take_profit_1`
- `take_profit_2`
- `take_profit_3`

先不做真正的自动平仓执行引擎。

#### `calibration_service.py`

负责：

- 基于 backtest / trades / analytics 结果生成每日校准快照
- 输出“建议权重”而不是直接在线学习
- 允许人工审阅后再生效

## 5. 分阶段实施路线图

### 5.1 Phase 0：基线与可观测性补强（1 周）

目标：在不改变行为的前提下，把现有信号链路的输入、输出和结果闭环补齐。

工作内容：

- 标准化 `analysis.strategy_selection` 的字段结构
- 为候选信号保留 score breakdown
- 为退出位保留来源标记
- 梳理 signal → trade → result 的最小结果数据集
- 明确 backtest 结果与 live signal 结果的可比较字段

交付物：

- 统一的 strategy metadata 结构
- 信号结果基线报表
- 第一版“信号质量对账”查询口径

### 5.2 Phase 1：最小可演进的策略引擎重构（2 周）

目标：把当前 `LiveStrategyEngine` 从“大函数”改成“协调器 + 几个稳定接口”。

工作内容：

- 抽出 `StrategySelector`
- 抽出 `MarketRegimeDetector`
- 把现有 4 个策略逻辑收口到 `strategy_profiles.py`
- 保留 ranking 归一化路径
- 保证 `SignalCandidate` 输出结构不变

这一步的关键不是“多策略多优雅”，而是：

- 当前行为尽量零回归
- 后续新增策略时不再改 300 行大函数

交付物：

- `domains/signals/strategy_selector.py`
- `domains/signals/market_regime.py`
- 简化后的 `domains/signals/live_strategy_engine.py`
- 对应 unit / integration tests

### 5.3 Phase 2：服务端退出位计算（2 周）

目标：服务端开始对退出位负责，但不破坏现有桌面端输入链路。

工作内容：

- 实现 `ExitLevelCalculator`
- 支持基于 ATR 的默认退出位
- 允许按 market regime 调整 multiplier
- 当客户端已传 stop/tp 时保留兼容
- 当客户端未传时由服务端补算
- 在 `analysis` 中写入退出位来源和解释

建议第一版只做“生成退出位”，不做自动交易触发。

交付物：

- `domains/signals/exit_level_calculator.py`
- `DesktopSignalService` / `LiveStrategyEngine` 的兼容接入
- 新的 integration tests

### 5.4 Phase 3：权重校准闭环（2 周）

目标：让策略选择和候选评分不再完全靠固定常量。

工作内容：

- 基于历史 trade / backtest 结果生成 daily calibration snapshot
- 为策略选择提供 bounded weight adjustment
- 为 score_candidate 提供 bounded score adjustment
- 将校准结果版本化
- 先人工审核生效，再考虑自动生效

建议约束：

- 单日调整幅度不超过 10%
- 所有权重保留最小值，避免单次异常把某策略打成 0
- 没有足够样本的策略不参与回写

交付物：

- `domains/signals/calibration_service.py`
- 校准快照存储方案
- admin analytics 可查看的校准版本信息

### 5.5 Phase 4：容量加固（3 到 4 周）

目标：在当前技术栈上把高并发骨架真正落到可运行能力，而不是直接跳向全新架构。

优先顺序：

1. 读路径缓存
2. notification fanout 分层与 Kafka 分区
3. scanner 分桶 / 分片
4. PgBouncer / Redis / Kafka 阈值治理
5. load baseline 扩展
6. 读副本与更细的 analytics 下沉

#### 读路径缓存

优先缓存：

- session / auth context
- watchlist
- portfolio summary
- notification list summary

原则：

- write-through 或 write-invalidate
- 不先做复杂三级缓存框架
- 先把命中率最高、读频最高的对象做稳

#### notification fanout

在现有 outbox + broker 链路基础上增强：

- 以 Kafka partition 做 fanout 并行
- 按用户层级 / 通道限速做 dispatch 策略
- 把 push、email、receipt escalation 的 backlog 指标接进 runtime monitoring

#### scanner 分桶 / 分片

先基于现有 worker 体系做：

- watchlist 命中 symbol 高优先级
- 流动性高的 symbol 高频扫描
- 低优先级 symbol 低频扫描
- 后续再引入 worker shard，不在第一阶段同时引入 coordinator 大重构

### 5.6 Phase 5：产品面收口（2 到 3 周）

目标：让 platform 真正成为策略核心的唯一工作台。

工作内容：

- `/platform` 明确展示 strategy selection、market regime、exit level source、calibration version
- `/admin` 只保留治理、审计、runtime、distribution、acceptance 等主责
- 把高权限策略能力逐步从“admin 产品叙事”迁回“platform 核心叙事”

## 6. 300 万日活的现实推进方式

这部分不能写成“已经可以承载 300 万”，更合理的说法是“按以下顺序推进到能证明承载 300 万”。

### 6.1 先证明 10 万到 30 万级压测能力

在当前仓库阶段，更合理的容量里程碑是：

- 第一档：10 万级模拟活跃用户链路验证
- 第二档：30 万级扇出与缓存命中验证
- 第三档：100 万级读压力与推送链路验证
- 第四档：再讨论 300 万 DAU 的正式容量签核

### 6.2 当前栈下的扩展顺序

建议顺序：

1. 静态 UI 走 nginx / CDN
2. API 读热点走 Redis
3. PostgreSQL 通过 PgBouncer 治理连接
4. fanout 走 Kafka 分区扩展
5. scanner 做 bucket 和 shard
6. analytics 下沉到 ClickHouse
7. 最后才考虑 WebSocket 常连体系

### 6.3 当前阶段明确不做

以下内容可以保留为长期选项，但不应进入第一版实施计划：

- Celery 迁移
- HMM regime detector
- LightGBM / 黑盒模型排序
- WebSocket-first 架构
- React/Vue 前端重写
- K8s-first 交付切换

## 7. 推荐的数据与存储策略

### 7.1 不破坏现有信号表结构

继续保留当前核心字段：

- `stop_loss`
- `take_profit_1`
- `take_profit_2`
- `take_profit_3`
- `strategy_window`
- `market_regime`
- `analysis`

新增信息优先放入：

- `analysis.strategy_selection`
- `analysis.exit_levels`
- `analysis.score_breakdown`
- `analysis.calibration_version`

Phase 3 已开始后，引入专门的 `signal_calibration_snapshots` 表来承载“人工审核后可激活”的每日快照；运行时仍只读取 active snapshot，不做在线学习。

### 7.2 校准结果先做快照，不直接做在线学习

建议先用：

- 每日快照
- 有版本号
- 可回滚
- 可人工审阅

而不是让 live traffic 直接在线改权重。

## 8. 成功标准

这份 V2 计划完成后，应该能回答四个问题：

1. 当前每个 signal 是怎么选出策略的？
2. 当前 stop_loss / take_profit 是谁算的？
3. 当前权重有没有依据历史结果做校准？
4. 当前容量结论是来自工具链和压测结果，还是口头估算？

如果这四个问题仍然答不清，说明 V2 还没有真正落地。

## 9. 下一步实施建议

如果要开始编码，建议顺序不要跳：

1. 先做 Phase 0，把信号解释、退出位来源、score breakdown 标准化
2. 再做 Phase 1，把 `LiveStrategyEngine` 拆成最小可演进结构
3. 再做 Phase 2，让服务端能补算退出位

也就是说，下一步最合理的工程任务不是“上复杂模型”，而是：

- 先把 `LiveStrategyEngine` 抽出稳定接口
- 再把退出位逻辑收回服务端
- 再把校准闭环接上

这才是和当前 `stock-py` 仓库最贴合的后续路线。
