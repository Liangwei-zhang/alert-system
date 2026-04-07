(function () {
    const EXACT_TRANSLATIONS = {
        "Admin Control Plane | Stock-Py": "管理控制台 | Stock-Py",
        "People Desk | Stock-Py Admin": "人员工作台 | Stock-Py 管理端",
        "Delivery Ops | Stock-Py Admin": "分发运营 | Stock-Py 管理端",
        "Intelligence | Stock-Py Admin": "智能分析 | Stock-Py 管理端",
        "Runtime & Audit | Stock-Py Admin": "运行时与审计 | Stock-Py 管理端",
        "Experiments | Stock-Py Admin": "实验与回测 | Stock-Py 管理端",

        "Admin frontend": "管理端前台",
        "Static control plane aligned to real admin-api capabilities.": "与真实 admin-api 能力对齐的静态控制台。",
        "Active operator": "当前操作员",
        "operations": "运营",
        "Scopes:": "权限范围：",

        "Admin control plane": "管理控制台",
        "Unified operating view": "统一运营视图",
        "Map the real admin-api surface into one operator cockpit before wiring live tokens and fetch calls. This frontend shows every major workflow area already present in the backend.": "在接入真实 token 与 fetch 调用前，将真实 admin-api 能力整合到一个运营驾驶舱。本前端已覆盖后端现有主要工作流。",
        "Open people desk": "打开人员工作台",
        "Review active alerts": "查看活动告警",
        "Queue a campaign": "发起活动推送",

        "People, plans, and scopes": "人员、套餐与权限范围",
        "Users + operators": "用户 + 操作员",
        "Expose the actual `/v1/admin/users` and `/v1/admin/operators` workflows as edit-ready front-end modules, including bulk updates and scope-aware operator management.": "将 `/v1/admin/users` 与 `/v1/admin/operators` 的真实流程做成可编辑前端模块，支持批量更新和权限范围化操作员管理。",
        "Bulk update users": "批量更新用户",
        "Upsert operator": "新增或更新操作员",

        "Campaigns, receipts, and trade tasks": "活动推送、回执与交易任务",
        "Delivery operations": "分发运营",
        "Surface the manual distribution and task-center endpoints so operations staff can send campaigns, work failed receipts, recover outbox jobs, and handle manual trade follow-ups.": "展示手动分发与任务中心接口，便于运营同学发送活动、处理失败回执、恢复发件箱任务并跟进人工交易任务。",
        "Manual message": "手动消息",
        "Escalate receipts": "升级回执",

        "Signal intelligence and data quality": "信号洞察与数据质量",
        "Analytics + scanner": "分析 + 扫描器",
        "Blend analytics, signal stats, scanner runs, anomalies, and AI agent metrics into a single operational analysis workspace.": "将分析、信号统计、扫描运行、异常与 AI 代理指标融合到一个运营分析工作区。",
        "Open strategy health": "打开策略健康度",
        "Inspect scanner run": "查看扫描运行",

        "Runtime, audit, and readiness": "运行时、审计与就绪度",
        "Observability + compliance": "可观测性 + 合规",
        "Expose component health, runtime stats, alerts, audit logs, and acceptance evidence in a layout tuned for operators who need to decide fast.": "以更适合快速决策的布局展示组件健康、运行统计、告警、审计日志和验收证据。",
        "Fetch runtime health": "获取运行时健康度",
        "Export acceptance report": "导出验收报告",

        "Backtests and AI agent recovery": "回测与 AI 代理恢复",
        "Experimentation control": "实验控制",
        "Give the backtest and trading-agent surfaces real front-end modules now so delayed analyses and stale rankings are visible before live API integration lands.": "先为回测与交易代理能力提供真实前端模块，在接入实时 API 前即可看到延迟分析与过期排名。",
        "Trigger refresh": "触发刷新",

        "Command": "指挥",
        "Overview": "总览",
        "Route matrix and risk board": "路由矩阵与风险看板",
        "People desk": "人员工作台",
        "Users, plans, operators": "用户、套餐、操作员",
        "Delivery ops": "分发运营",
        "Campaigns, receipts, trade tasks": "活动、回执、交易任务",
        "Signals": "信号",
        "Intelligence": "智能分析",
        "Analytics, scanner, anomalies": "分析、扫描器、异常",
        "Experiments": "实验",
        "Backtests and AI recovery": "回测与 AI 恢复",
        "Governance": "治理",
        "Runtime & audit": "运行时与审计",
        "Health, alerts, readiness": "健康度、告警、就绪度",

        "Admin workspace": "管理工作区",
        "Search route, symbol, user, operator, or request ID": "搜索路由、标的、用户、操作员或请求 ID",
        "Demo data mode": "演示数据模式",
        "Connect live API": "连接实时 API",
        "Preview auth flow": "预览认证流程",
        "This frontend is ready to swap demo data for real bearer-token based fetch calls.": "当前前端已可由演示数据切换为基于 Bearer Token 的真实 fetch 调用。",

        "Route coverage": "路由覆盖",
        "Backend capability matrix": "后端能力矩阵",
        "Each card maps to a real route family already present in apps/admin_api/routers.": "每张卡片都映射到 apps/admin_api/routers 中已存在的真实路由族。",
        "Risk board": "风险看板",
        "Where operators need to look first": "操作员优先关注点",
        "Condensed view of the routes and states most likely to require human intervention before market sessions.": "浓缩展示开盘前最可能需要人工干预的路由与状态。",
        "Activity timeline": "活动时间线",
        "What changed across the admin surface": "管理面变化概览",
        "Use this as the backbone for a future live feed of audit, distribution, and runtime state changes.": "可作为后续接入审计、分发与运行时状态实时流的骨架。",
        "Quick launch": "快捷启动",
        "Action studio": "操作工作台",
        "These launchers correspond to mutation endpoints. Right now they show request intent and front-end readiness.": "这些快捷入口对应写操作接口，当前用于展示请求意图和前端就绪度。",
        "Preview action": "预览操作",

        "Users": "用户",
        "Subscriber command desk": "订阅用户指挥台",
        "Expose the `/v1/admin/users` read + write surfaces with filters, bulk actions, and enough context to triage plan or activation changes.": "以可筛选、可批量操作并带上下文信息的方式展示 `/v1/admin/users` 读写能力，便于分诊套餐或激活状态变更。",
        "User": "用户",
        "Plan": "套餐",
        "Status": "状态",
        "Capital": "资金",
        "Locale": "地区",
        "Last login": "最后登录",

        "Bulk mutation": "批量变更",
        "Prepare user update payload": "准备用户更新负载",
        "This form mirrors the payload shape for bulk plan or activation changes. It stays front-end only for now.": "此表单对应批量套餐或激活状态变更的负载结构，当前仅用于前端演示。",
        "User IDs": "用户 ID",
        "Set active": "设置激活",
        "Preview payload": "预览负载",

        "Operators": "操作员",
        "Access scope matrix": "权限范围矩阵",
        "This maps directly to `/v1/admin/operators`, including role and scopes needed by operator-protected workflows.": "该模块直接映射 `/v1/admin/operators`，覆盖角色与受操作员保护工作流所需权限范围。",
        "Operator": "操作员",
        "Role": "角色",
        "Active": "激活",
        "Last action": "最后操作",

        "Operator payload": "操作员负载",
        "Scope-aware edit form": "权限范围编辑表单",
        "Front-end shape for upserting operator role, scopes, and activation state. Also useful for testing token + X-Operator-ID flows.": "用于新增/更新操作员角色、权限范围和激活状态的前端结构，也可用于测试 token + X-Operator-ID 流程。",
        "User ID": "用户 ID",
        "Review auth flow": "查看认证流程",
        "Operator login flow": "操作员登录流程",
        "Admin-auth, operator scopes, and token persistence were already added server-side; this UI is ready to sit on top of them.": "服务端已支持管理认证、操作员权限和 token 持久化；该界面已可直接承接。",

        "Campaign cohort": "活动人群",
        "target users in current draft": "当前草稿目标用户",
        "Escalated receipts": "已升级回执",
        "manual follow-up required": "需要人工跟进",
        "Failed outbox jobs": "失败发件箱任务",
        "2 are stale claims": "其中 2 条为过期认领",
        "Pending trade tasks": "待处理交易任务",
        "3 are expired": "其中 3 条已过期",

        "Manual distribution": "手动分发",
        "Campaign composer": "活动编辑器",
        "This mirrors the request body for `/v1/admin/distribution/manual-message`, including channels, acknowledgement deadlines, and metadata.": "该模块对应 `/v1/admin/distribution/manual-message` 请求体，包含渠道、确认截止时间和元数据。",
        "Notification type": "通知类型",
        "Ack deadline": "确认截止时间",
        "Channels": "渠道",
        "Email": "邮件",
        "Push": "推送",
        "Title": "标题",
        "Body": "正文",
        "Metadata JSON": "元数据 JSON",
        "Queue manual campaign": "入队手动活动",
        "Simulate queue": "模拟入队",

        "Receipt queue": "回执队列",
        "Follow-up triage": "跟进分诊",
        "The action surface here should eventually call claim, ack, resolve, and overdue escalation endpoints.": "这里的操作面最终会调用认领、确认、解决和逾期升级等接口。",
        "Receipt": "回执",
        "Delivery": "投递",
        "Follow-up": "跟进",
        "Escalation": "升级",
        "level": "等级",
        "Receipt action": "回执操作",
        "Claim": "认领",

        "Outbox recovery": "发件箱恢复",
        "Retry and requeue workspace": "重试与重新入队工作区",
        "Use this module for `/retry`, `/release-stale`, and `/requeue` flows when message delivery drifts or workers keep stale claims.": "当消息投递漂移或 Worker 保留过期认领时，使用此模块处理 `/retry`、`/release-stale` 与 `/requeue` 流程。",
        "Outbox ID": "发件箱 ID",
        "Channel": "渠道",
        "Last error": "最后错误",
        "Retry outbox jobs": "重试发件箱任务",
        "Retry selected": "重试选中",
        "Release stale claims": "释放过期认领",
        "Release stale": "释放过期",
        "Requeue outbox item": "发件箱项重新入队",
        "Requeue one": "重新入队一条",

        "Trade task center": "交易任务中心",
        "Manual trade workflow": "人工交易工作流",
        "These actions map to claim and expire endpoints for trade tasks that require human confirmation.": "这些操作映射到需要人工确认的交易任务认领与过期接口。",
        "Trade task": "交易任务",
        "Suggested amount": "建议金额",
        "Claim trade tasks": "认领交易任务",
        "Claim tasks": "认领任务",
        "Expire trade tasks": "使交易任务过期",
        "Expire overdue": "过期逾期任务",

        "Distribution": "分发",
        "Channel outcome mix": "渠道结果分布",
        "Snapshot of `/v1/admin/analytics/distribution` rendered as simple density bars.": "将 `/v1/admin/analytics/distribution` 快照渲染为简易密度条。",
        "Strategy health": "策略健康度",
        "Current ranking leaders": "当前排名领先策略",
        "Top strategies from the strategy health and latest ranking views.": "来自策略健康度与最新排名视图的头部策略。",
        "Trading agents": "交易代理",
        "Turnaround snapshot": "周转快照",
        "Compact cards derived from `/v1/admin/analytics/tradingagents` and analysis list endpoints.": "基于 `/v1/admin/analytics/tradingagents` 与分析列表接口的紧凑卡片。",
        "Signal stats": "信号统计",
        "Volume and quality checks": "量级与质量检查",
        "Make `/v1/admin/signal-stats` visible as an at-a-glance module instead of a raw JSON endpoint.": "将 `/v1/admin/signal-stats` 从原始 JSON 接口升级为可一眼查看的模块。",
        "Scanner runs": "扫描运行",
        "Decision volume by run": "按运行统计决策量",
        "This table is designed to map cleanly to observability and run-detail endpoints.": "该表设计用于清晰映射可观测性与运行详情接口。",
        "Run": "运行",
        "Emitted": "已发出",
        "Suppressed": "已抑制",
        "Skipped": "已跳过",
        "Live decision log": "实时决策日志",
        "Recent signal decisions": "近期信号决策",
        "A leaner surface for the paginated live-decision endpoint.": "分页 live-decision 接口的轻量展示面。",
        "Market data anomalies": "行情数据异常",
        "Data quality queue": "数据质量队列",
        "Bring `/v1/admin/anomalies/ohlcv` forward so operators can see what will poison analytics or signal generation.": "前置展示 `/v1/admin/anomalies/ohlcv`，让操作员看到会污染分析或信号生成的问题。",
        "Symbol": "标的",
        "Severity": "严重度",
        "Issue": "问题",
        "Observed": "观测时间",

        "Runtime components": "运行时组件",
        "Health board": "健康看板",
        "This board is designed for `/v1/admin/runtime/components`, with enough density to keep worker and scheduler health scannable.": "该看板面向 `/v1/admin/runtime/components` 设计，信息密度足够以便快速扫描 worker 与 scheduler 健康状态。",
        "Inspect component": "查看组件",
        "Open detail": "打开详情",
        "Active alerts": "活动告警",
        "What can block release or response": "可能阻塞发布或响应的问题",
        "Direct UI match for runtime and platform alert payloads.": "与运行时及平台告警负载直接对应的 UI。",
        "Audit log": "审计日志",
        "Operator traceability": "操作员可追溯性",
        "This table maps to the filterable audit event list and should become a live log once connected.": "该表对应可筛选审计事件列表，接入后应成为实时日志。",
        "Timestamp": "时间戳",
        "Entity": "实体",
        "Action": "动作",
        "Source": "来源",
        "Request ID": "请求 ID",

        "Acceptance": "验收",
        "Release readiness": "发布就绪度",
        "The deployment readiness report becomes useful only when it is visible next to runtime truth, not hidden in raw JSON.": "部署就绪报告只有与运行时真实状态并排展示才有价值，不应隐藏在原始 JSON 中。",
        "Current status:": "当前状态：",
        "Last updated": "最后更新",
        "Export readiness report": "导出就绪报告",
        "Preview report export": "预览报告导出",

        "Backtest runs": "回测运行",
        "Execution history": "执行历史",
        "This surface is intentionally action-adjacent so stale or failed runs are obvious before a refresh is fired.": "该界面刻意贴近操作入口，便于在触发刷新前识别过期或失败运行。",
        "Window": "窗口",
        "Score": "得分",
        "Updated": "更新时间",
        "Latest rankings": "最新排名",
        "Top-performing strategies": "表现最佳策略",
        "A compact rendering of the latest ranking payload used by operators and release reviewers.": "为操作员与发布评审提供的最新排名负载紧凑展示。",
        "Backtest request builder": "回测请求构造器",
        "Payload shape for the mutation endpoint that refreshes stale ranking windows.": "用于刷新过期排名窗口的写接口负载结构。",
        "Symbols": "标的列表",
        "Strategies": "策略列表",
        "Windows (hours)": "窗口（小时）",
        "Timeframe": "时间周期",
        "Trigger ranking refresh": "触发排名刷新",
        "Simulate refresh": "模拟刷新",
        "Trading agent analyses": "交易代理分析",
        "Recovery queue": "恢复队列",
        "Design target for list/detail and delayed reconcile actions in the AI analysis surface.": "AI 分析界面中列表/详情与延迟对账动作的设计目标。",
        "Request": "请求",
        "Trigger": "触发方式",
        "Final action": "最终动作",
        "Latency": "延迟",

        "Payload ready": "负载已就绪",
        "Prepared a request body preview.": "已生成请求体预览。",
        "This interaction is currently front-end only, but the UI shape is ready.": "该交互当前仅前端演示，但 UI 结构已就绪。",

        "API request succeeded": "API 请求成功",
        "API request failed": "API 请求失败",
        "Body required": "需要请求体",
        "No endpoint selected": "未选择接口",
        "Select an endpoint and click Run Endpoint.": "选择一个接口后点击“执行接口”。",
        "Run Endpoint": "执行接口",
        "Reset Template": "重置模板",
        "Operator ID optional": "可选操作员 ID",
        "Requires X-Operator-ID header": "需要 X-Operator-ID 请求头",
        "Path Params JSON": "路径参数 JSON",
        "Query JSON": "查询参数 JSON",
        "Body JSON": "请求体 JSON",
        "Endpoint": "接口",
        "Full API Console": "全量 API 控制台",
        "Execute Any Admin Endpoint": "执行任意管理端接口",
        "This console exposes all current /v1/admin routes with method, path params, query, and body JSON controls.": "该控制台开放当前全部 /v1/admin 路由，支持方法、路径参数、查询参数与请求体 JSON 控制。",
        "One or more path params are missing": "一个或多个路径参数缺失",
        "Path params JSON must be valid JSON": "路径参数 JSON 必须是合法 JSON",
        "Query JSON must be valid JSON": "查询参数 JSON 必须是合法 JSON",
        "Body JSON must be valid JSON": "请求体 JSON 必须是合法 JSON",

        "Admin Live Connection": "管理端实时连接",
        "Bearer + X-Operator-ID": "Bearer + X-Operator-ID",
        "API URL": "API 地址",
        "Bearer Token": "Bearer 令牌",
        "Operator ID": "操作员 ID",
        "Not connected": "未连接",

        "Unknown": "未知",
        "n/a": "无",
        "N/A": "无",
        "none": "无",
        "unclaimed": "未认领",

        "Active operators": "活跃操作员",
        "Pending follow-ups": "待跟进项",
        "Unhealthy components": "异常组件",
        "Stale rankings": "过期排名",
        "Signal throughput": "信号吞吐",
        "AI backlog": "AI 积压",
        "+3 this week": "本周 +3",
        "12 overdue receipts": "12 条逾期回执",
        "refresh window exceeded": "刷新窗口已超时",
        "+11% vs yesterday": "较昨日 +11%",
        "2 delayed analyses waiting reconcile": "2 条延迟分析待对账",

        "Users & operators": "用户与操作员",
        "Filter platform users, bulk update plans, and maintain operator scopes used by X-Operator-ID workflows.": "筛选平台用户、批量更新套餐，并维护 X-Operator-ID 工作流所需操作员权限范围。",
        "Communications": "通信分发",
        "Send manual broadcasts, work receipts, recover outbox jobs, and claim or expire manual trade tasks.": "发送手动广播、处理回执、恢复发件箱任务，并认领或过期人工交易任务。",
        "Signal intelligence": "信号洞察",
        "Track analytics, signal generation velocity, scanner decisions, and data anomalies in one screen.": "在同一屏追踪分析、信号生成速度、扫描决策和数据异常。",
        "Runtime & compliance": "运行时与合规",
        "Monitor component health, audit events, active alerts, and deployment acceptance checkpoints.": "监控组件健康、审计事件、活动告警和部署验收检查点。",
        "Backtests & agents": "回测与代理",
        "Inspect run history, strategy rankings, and delayed AI analyses before triggering corrective actions.": "在触发纠偏操作前查看运行历史、策略排名和延迟 AI 分析。",
        "Signal stats detail": "信号统计详情",
        "Quantify signal output, decision quality, and downstream workload generation by timeframe and symbol.": "按时间周期和标的量化信号产出、决策质量与下游工作负载。",

        "Receipt escalations are climbing": "回执升级数量持续上升",
        "12 receipts crossed their acknowledgement deadline after the overnight push campaign. Delivery failures are concentrated in push channel retries.": "夜间推送活动后有 12 条回执超过确认截止时间，投递失败主要集中在推送渠道重试。",
        "Backtest ranking freshness is below target": "回测排名新鲜度低于目标",
        "Latest ranking snapshot is 7 hours old, which will put strategy health views out of SLA before the US open.": "最新排名快照已过 7 小时，可能在美股开盘前导致策略健康视图超出 SLA。",
        "Runtime coverage recovered": "运行时覆盖率已恢复",
        "Worker heartbeat coverage is back to 96% after restarting the market-data ingress pool.": "重启市场数据入口池后，Worker 心跳覆盖率恢复至 96%。",

        "Operator 18 claimed 6 trade tasks": "操作员 18 认领了 6 个交易任务",
        "Manual trade confirmations were split between APAC and EU desks after a spike in delayed execution receipts.": "延迟执行回执激增后，人工交易确认由 APAC 与 EU 团队分流处理。",
        "Manual distribution queued for suspended-plan cleanup": "停用套餐清理的手动分发已入队",
        "Broadcast targeted 214 users across email and push with acknowledgement required before plan downgrade.": "该广播覆盖 214 位用户（邮件+推送），要求在套餐降级前完成确认。",
        "Scanner suppression rate breached warning threshold": "扫描器抑制率突破预警阈值",
        "Liquidity and spread filters removed 38% of candidate decisions during the overnight run.": "夜间运行期间，流动性与价差过滤器剔除了 38% 的候选决策。",
        "Acceptance snapshot refreshed": "验收快照已刷新",
        "Contract tests and load proofs were exported to the readiness report ahead of internal sign-off.": "在内部签署前，契约测试与压测证明已导出到就绪报告。",

        "Queue manual message": "入队手动消息",
        "Broadcast product, billing, or incident communication to a filtered user cohort.": "向筛选后的用户群广播产品、计费或事故通知。",
        "Escalate overdue receipts": "升级逾期回执",
        "Push acknowledgement misses into manual follow-up before churn or compliance risk grows.": "在流失或合规风险扩大前，将未确认项推进到人工跟进。",
        "Refresh backtest rankings": "刷新回测排名",
        "Rebuild stale ranking windows when strategy health or release reviews need fresh evidence.": "当策略健康或发布评审需要最新证据时，重建过期排名窗口。",
        "Reconcile delayed analyses": "对账延迟分析",
        "Retry delayed AI analyses and surface the final action back into operator workflows.": "重试延迟 AI 分析，并将最终动作回写到操作员工作流。",

        "Platform users": "平台用户",
        "Enterprise plans": "企业套餐",
        "18 high-touch accounts": "18 个重点账户",
        "Suspended accounts": "停用账户",
        "14 need review": "14 个待复核",
        "5 admin / 9 operator / 4 viewer": "5 管理员 / 9 操作员 / 4 查看者",

        "manual.message ack pending": "manual.message 待确认",
        "healthy": "健康",
        "needs reactivation": "需重新激活",
        "enterprise upsell candidate": "企业升级候选",
        "churn prevention cohort": "防流失人群",

        "Plan cleanup acknowledgement": "套餐清理确认",
        "Your subscription configuration changed after a failed billing recovery. Please acknowledge before market open.": "计费恢复失败后，您的订阅配置已变更，请在开盘前完成确认。",

        "24h revenue at risk": "24 小时风险收入",
        "driven by suspended enterprise accounts": "主要由停用企业账户驱动",
        "Distribution latency": "分发延迟",
        "p95 end-to-end notification latency": "端到端通知延迟 P95",
        "Strategy win rate": "策略胜率",
        "+2.8 pts over 7d window": "7 日窗口 +2.8 个百分点",
        "Agent turnaround": "代理周转时间",
        "2 delayed jobs over SLA": "2 个任务超出 SLA",

        "Email delivered": "邮件已送达",
        "Push delivered": "推送已送达",
        "Manual follow-up": "人工跟进",

        "Delayed analyses": "延迟分析",
        "Completed today": "今日完成",
        "Manual triggers": "手动触发",

        "Signals generated": "已生成信号",
        "Strong buy ratio": "强买比例",
        "Validation flagged": "校验标记",

        "Gap in OHLCV candle set": "OHLCV K 线集合存在缺口",
        "Volume spike outside tolerance": "成交量尖峰超出容差",
        "Duplicate bar timestamps": "K 线时间戳重复",

        "Component coverage": "组件覆盖率",
        "24 / 25 expected nodes reporting": "25 个预期节点中 24 个已上报",
        "Kafka lag": "Kafka 积压",
        "event pipeline consumer warning": "事件管道消费者预警",
        "Redis hit rate": "Redis 命中率",
        "within target": "处于目标范围",
        "P99 API latency": "API 延迟 P99",
        "stable over 1h": "近 1 小时稳定",

        "running": "运行中",
        "stale": "过期",
        "degraded": "降级",

        "Cron-style orchestration for retention, cold storage, and periodic analytics snapshots.": "用于保留、冷存储与周期分析快照的类 Cron 编排。",
        "Ingesting OHLCV batches and repairing transient import gaps.": "正在摄取 OHLCV 批次并修复瞬时导入缺口。",
        "CPU pressure is delaying ranking refresh jobs past desired freshness budget.": "CPU 压力导致排名刷新任务延迟，超出目标新鲜度预算。",
        "Outbox consumer lag and retries are inflating receipt escalation volume.": "发件箱消费者积压与重试导致回执升级量上升。",

        "Runtime alert: worker heartbeat stale": "运行时告警：Worker 心跳过期",
        "Backtest pool missed two heartbeat windows while strategy refresh was executing 28 windows in parallel.": "策略刷新并行执行 28 个窗口时，回测池错过了两个心跳窗口。",
        "Platform alert: broker lag rising": "平台告警：Broker 积压上升",
        "Kafka lag crossed 400 messages. Delivery retries should be monitored before the next manual campaign.": "Kafka 积压超过 400 条消息。下一次手动活动前应重点监控投递重试。",
        "Acceptance snapshot current": "验收快照为最新",
        "Contract tests, load proofs, and OpenAPI manifests were refreshed 42 minutes ago.": "契约测试、压测证明与 OpenAPI 清单已于 42 分钟前刷新。",

        "OpenAPI snapshots exported": "OpenAPI 快照已导出",
        "Contract suite clean": "契约测试套件通过",
        "Load evidence attached": "压测证据已附加",
        "Backtest freshness within SLA": "回测新鲜度在 SLA 内",
        "Runtime alerts below threshold": "运行时告警低于阈值",
        "ready-with-observations": "就绪（含观察项）",

        "Backtest runs today": "今日回测运行",
        "+6 manual refreshes": "+6 次手动刷新",
        "Completed successfully": "成功完成",
        "81.5% success rate": "成功率 81.5%",
        "Ranking leaders": "排名领先策略",
        "covering 22 symbols max": "最多覆盖 22 个标的",

        "Open analyses": "进行中分析",
        "Completed analyses": "已完成分析",
        "terminal states": "终态数量",
        "live total": "实时总数",
        "tradingagents queue": "tradingagents 队列",
        "no rankings": "无排名",
        "no ranking snapshot": "无排名快照",
        "runtime unavailable": "运行时不可用",
        "stats unavailable": "统计不可用",
        "no signal summary": "无信号摘要",
        "live operator directory": "实时操作员目录",
        "manual receipt follow-up": "人工回执跟进",

        "Reconcile delayed": "对账延迟项",
        "pending": "待处理",
        "completed": "已完成",
        "failed": "失败",
        "warning": "告警",
        "error": "错误",
        "critical": "严重",
        "success": "成功",
        "delivered": "已送达",
        "retrying": "重试中",
        "claimed": "已认领",
        "escalated": "已升级",
        "inactive": "停用",
        "suspended": "已停用",
        "delayed": "延迟",
        "ready": "就绪",
        "done": "完成",
        "attention": "关注",
        "buy": "买入",
        "sell": "卖出",
        "hold": "持有"
    };

    const WORD_TRANSLATIONS = {
        active: "活跃",
        inactive: "停用",
        suspended: "已停用",
        healthy: "健康",
        warning: "告警",
        error: "错误",
        failed: "失败",
        stale: "过期",
        degraded: "降级",
        completed: "已完成",
        pending: "待处理",
        delayed: "延迟",
        claimed: "已认领",
        success: "成功",
        delivered: "已送达",
        retrying: "重试中",
        expired: "已过期",
        running: "运行中",
        none: "无"
    };

    const REGEX_TRANSLATIONS = [
        [/^(\d+)h overview$/i, "$1 小时概览"],
        [/^(\d+) delivered$/i, "已送达 $1"],
        [/^coverage:\s*(\d+) endpoints$/i, "覆盖：$1 个端点"],
        [/^Ready:\s*(GET|POST|PUT|DELETE|PATCH)\s+(.+)$/i, "就绪：$1 $2"],
        [/^runtime\s+(.+)$/i, "运行时 $1"],
        [/^host\s+(.+)\s+·\s+heartbeat\s+(\d+)$/i, "主机 $1 · 心跳 $2"],
        [/^bucket\s+(.+)$/i, "分桶 $1"],
        [/^score\s+(.+)$/i, "得分 $1"],
        [/^confidence\s+(.+)$/i, "置信度 $1"],
        [/^degradation\s+(.+)\s+·\s+(.+) symbols covered$/i, "退化 $1 · 覆盖 $2 个标的"],
        [/^(.+)\s+·\s+degradation\s+(.+)\s+·\s+(.+) symbols$/i, "$1 · 退化 $2 · $3 个标的"],
        [/^user\s+(\d+)\s+·\s+(.+)$/i, "用户 $1 · $2"],
        [/^user\s+(\d+)$/i, "用户 $1"],
        [/^deadline\s+(.+)$/i, "截止 $1"],
        [/^expires\s+(.+)$/i, "到期 $1"],
        [/^This frontend module is ready to call\s+(.+)\s+once the demo data layer is replaced with real fetch wiring\.$/i, "该前端模块已就绪，替换演示数据层为真实 fetch 后即可调用 $1。"],
        [/^Prepared a front-end request body for\s+(.+)\.$/i, "已为 $1 生成前端请求体。"],
        [/^Execute\s+(GET|POST|PUT|DELETE|PATCH)\s+(.+)\s+now\?$/i, "立即执行 $1 $2 吗？"]
    ];

    const TRANSLATABLE_ATTRIBUTES = ["placeholder", "title", "aria-label", "value"];
    const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "CODE", "PRE"]);

    function looksLikeRawJson(text) {
        const trimmed = String(text || "").trim();
        if (!trimmed) return false;
        if ((trimmed.startsWith("{") && trimmed.endsWith("}")) || (trimmed.startsWith("[") && trimmed.endsWith("]"))) {
            return true;
        }
        return /"[A-Za-z0-9_]+"\s*:/.test(trimmed);
    }

    function shouldSkip(text) {
        const trimmed = String(text || "").trim();
        if (!trimmed) return true;
        if (/^(GET|POST|PUT|DELETE|PATCH)\s+\/v1\//.test(trimmed)) return true;
        if (/^\/v1\//.test(trimmed)) return true;
        if (looksLikeRawJson(trimmed)) return true;
        return false;
    }

    function translateCoreText(core) {
        if (!core) return core;

        if (EXACT_TRANSLATIONS[core]) {
            return EXACT_TRANSLATIONS[core];
        }

        let translated = core;
        REGEX_TRANSLATIONS.forEach(([pattern, replacement]) => {
            translated = translated.replace(pattern, replacement);
        });

        if (translated !== core) {
            return translated;
        }

        if (/^[A-Za-z0-9_.-]+$/.test(core)) {
            const lower = core.toLowerCase();
            if (WORD_TRANSLATIONS[lower]) {
                return WORD_TRANSLATIONS[lower];
            }
        }

        return core;
    }

    function translateText(text) {
        const raw = String(text || "");
        const match = raw.match(/^(\s*)([\s\S]*?)(\s*)$/);
        if (!match) return raw;

        const prefix = match[1] || "";
        const core = match[2] || "";
        const suffix = match[3] || "";

        if (shouldSkip(core)) {
            return raw;
        }

        const translatedCore = translateCoreText(core);
        return `${prefix}${translatedCore}${suffix}`;
    }

    function translateTextNode(node) {
        if (!node || node.nodeType !== Node.TEXT_NODE) return;
        const before = node.nodeValue || "";
        const after = translateText(before);
        if (after !== before) {
            node.nodeValue = after;
        }
    }

    function shouldTranslateValueAttribute(element) {
        if (!element) return false;
        const tag = element.tagName;
        if (tag === "INPUT") {
            const type = String(element.getAttribute("type") || "text").toLowerCase();
            return ["button", "submit", "reset"].includes(type);
        }
        if (tag === "OPTION") return true;
        return false;
    }

    function translateAttributes(element) {
        TRANSLATABLE_ATTRIBUTES.forEach((attr) => {
            if (!element.hasAttribute(attr)) return;
            if (attr === "value" && !shouldTranslateValueAttribute(element)) return;
            const before = element.getAttribute(attr) || "";
            const after = translateText(before);
            if (after !== before) {
                element.setAttribute(attr, after);
            }
        });
    }

    function translateElement(element) {
        if (!element || element.nodeType !== Node.ELEMENT_NODE) return;
        if (SKIP_TAGS.has(element.tagName)) return;

        translateAttributes(element);

        element.childNodes.forEach((child) => {
            if (child.nodeType === Node.TEXT_NODE) {
                translateTextNode(child);
            } else if (child.nodeType === Node.ELEMENT_NODE) {
                translateElement(child);
            }
        });
    }

    function translateDocument() {
        document.title = translateText(document.title);
        if (document.body) {
            translateElement(document.body);
        }
    }

    function watchMutations() {
        if (!document.body) return;

        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === "characterData") {
                    translateTextNode(mutation.target);
                    return;
                }

                if (mutation.type === "childList") {
                    mutation.addedNodes.forEach((node) => {
                        if (node.nodeType === Node.TEXT_NODE) {
                            translateTextNode(node);
                        } else if (node.nodeType === Node.ELEMENT_NODE) {
                            translateElement(node);
                        }
                    });
                }
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true
        });
    }

    function init() {
        translateDocument();
        watchMutations();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
