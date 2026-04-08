window.adminDemoData = {
    operator: {
        name: "Lin Vega",
        role: "superadmin",
        shift: "APAC operations",
        scopes: ["runtime", "analytics", "distribution", "users", "audit"]
    },
    dashboard: {
        metrics: [
            {
                label: "Active operators",
                value: "18",
                delta: "+3 this week",
                tone: "positive",
                icon: "shield-check"
            },
            {
                label: "Pending follow-ups",
                value: "42",
                delta: "12 overdue receipts",
                tone: "warning",
                icon: "mail-warning"
            },
            {
                label: "Unhealthy components",
                value: "3",
                delta: "scanner-consumer, backtest-pool, kafka-lag",
                tone: "negative",
                icon: "triangle-alert"
            },
            {
                label: "Stale rankings",
                value: "7h",
                delta: "refresh window exceeded",
                tone: "brand",
                icon: "flask-conical"
            },
            {
                label: "Signal throughput",
                value: "1,284/h",
                delta: "+11% vs yesterday",
                tone: "positive",
                icon: "radio"
            },
            {
                label: "AI backlog",
                value: "9",
                delta: "2 delayed analyses waiting reconcile",
                tone: "warning",
                icon: "bot"
            }
        ],
        routes: [
            {
                title: "Users & operators",
                copy: "Filter platform users, bulk update plans, and maintain operator scopes used by X-Operator-ID workflows.",
                endpoint: "/v1/admin/users + /v1/admin/operators",
                href: "people.html",
                tag: "action"
            },
            {
                title: "Communications",
                copy: "Send manual broadcasts, work receipts, recover outbox jobs, and claim or expire manual trade tasks.",
                endpoint: "/v1/admin/distribution + /v1/admin/tasks",
                href: "communications.html",
                tag: "action"
            },
            {
                title: "Signal intelligence",
                copy: "Track analytics, signal generation velocity, scanner decisions, and data anomalies in one screen.",
                endpoint: "/v1/admin/analytics + /v1/admin/scanner + /v1/admin/anomalies",
                href: "intelligence.html",
                tag: "read"
            },
            {
                title: "Runtime & compliance",
                copy: "Monitor component health, audit events, active alerts, and deployment acceptance checkpoints.",
                endpoint: "/v1/admin/runtime + /v1/admin/audit + /v1/admin/acceptance",
                href: "runtime.html",
                tag: "read"
            },
            {
                title: "Backtests & agents",
                copy: "Inspect run history, strategy rankings, and delayed AI analyses before triggering corrective actions.",
                endpoint: "/v1/admin/backtests + /v1/admin/tradingagents",
                href: "experiments.html",
                tag: "mixed"
            },
            {
                title: "Signal stats detail",
                copy: "Quantify signal output, decision quality, and downstream workload generation by timeframe and symbol.",
                endpoint: "/v1/admin/signal-stats",
                href: "intelligence.html#signal-stats",
                tag: "read"
            }
        ],
        attention: [
            {
                title: "Receipt escalations are climbing",
                copy: "12 receipts crossed their acknowledgement deadline after the overnight push campaign. Delivery failures are concentrated in push channel retries.",
                tone: "warning",
                meta: ["tasks/receipts", "operators required"]
            },
            {
                title: "Backtest ranking freshness is below target",
                copy: "Latest ranking snapshot is 7 hours old, which will put strategy health views out of SLA before the US open.",
                tone: "danger",
                meta: ["backtests/runs", "refresh needed"]
            },
            {
                title: "Runtime coverage recovered",
                copy: "Worker heartbeat coverage is back to 96% after restarting the market-data ingress pool.",
                tone: "success",
                meta: ["runtime/components", "healthy"]
            }
        ],
        timeline: [
            {
                time: "07:42 UTC",
                title: "Operator 18 claimed 6 trade tasks",
                copy: "Manual trade confirmations were split between APAC and EU desks after a spike in delayed execution receipts.",
                tags: ["tasks/trades", "claim"]
            },
            {
                time: "06:55 UTC",
                title: "Manual distribution queued for suspended-plan cleanup",
                copy: "Broadcast targeted 214 users across email and push with acknowledgement required before plan downgrade.",
                tags: ["distribution/manual-message", "campaign"]
            },
            {
                time: "05:10 UTC",
                title: "Scanner suppression rate breached warning threshold",
                copy: "Liquidity and spread filters removed 38% of candidate decisions during the overnight run.",
                tags: ["scanner/observability", "warning"]
            },
            {
                time: "02:34 UTC",
                title: "Acceptance snapshot refreshed",
                copy: "Contract tests and load proofs were exported to the readiness report ahead of internal sign-off.",
                tags: ["acceptance/report", "qa"]
            }
        ],
        quickActions: [
            {
                title: "Queue manual message",
                endpoint: "POST /v1/admin/distribution/manual-message",
                description: "Broadcast product, billing, or incident communication to a filtered user cohort."
            },
            {
                title: "Escalate overdue receipts",
                endpoint: "POST /v1/admin/tasks/receipts/escalate-overdue",
                description: "Push acknowledgement misses into manual follow-up before churn or compliance risk grows."
            },
            {
                title: "Refresh backtest rankings",
                endpoint: "POST /v1/admin/backtests/runs",
                description: "Rebuild stale ranking windows when strategy health or release reviews need fresh evidence."
            },
            {
                title: "Reconcile delayed analyses",
                endpoint: "POST /v1/admin/tradingagents/reconcile-delayed",
                description: "Retry delayed AI analyses and surface the final action back into operator workflows."
            }
        ]
    },
    people: {
        metrics: [
            { label: "Platform users", value: "12,401", delta: "+4.1%", tone: "positive" },
            { label: "Enterprise plans", value: "241", delta: "18 high-touch accounts", tone: "brand" },
            { label: "Suspended accounts", value: "86", delta: "14 need review", tone: "warning" },
            { label: "Active operators", value: "18", delta: "5 admin / 9 operator / 4 viewer", tone: "brand" }
        ],
        users: [
            {
                id: 1041,
                name: "Alice Smith",
                email: "alice@example.com",
                plan: "pro-trader",
                status: "active",
                capital: "$128,400",
                currency: "USD",
                locale: "en-US / America/New_York",
                lastLogin: "2026-04-06 07:10",
                subscription: "manual.message ack pending"
            },
            {
                id: 1187,
                name: "Bob Jones",
                email: "bob.j@example.com",
                plan: "basic",
                status: "active",
                capital: "$34,900",
                currency: "USD",
                locale: "en-GB / Europe/London",
                lastLogin: "2026-04-05 19:42",
                subscription: "healthy"
            },
            {
                id: 2092,
                name: "Charlie Davis",
                email: "charlie.d@sandbox.co",
                plan: "enterprise",
                status: "suspended",
                capital: "$0",
                currency: "USD",
                locale: "en-SG / Asia/Singapore",
                lastLogin: "2026-03-29 11:05",
                subscription: "needs reactivation"
            },
            {
                id: 2338,
                name: "Mira Chen",
                email: "mira.chen@example.com",
                plan: "pro-trader",
                status: "active",
                capital: "$412,200",
                currency: "USD",
                locale: "zh-CN / Asia/Shanghai",
                lastLogin: "2026-04-06 06:55",
                subscription: "enterprise upsell candidate"
            },
            {
                id: 2781,
                name: "Noah Patel",
                email: "noah.patel@example.com",
                plan: "starter",
                status: "inactive",
                capital: "$8,200",
                currency: "USD",
                locale: "en-IN / Asia/Kolkata",
                lastLogin: "2026-03-18 09:21",
                subscription: "churn prevention cohort"
            }
        ],
        operators: [
            {
                userId: 7,
                name: "Lin Vega",
                email: "lin.vega@stockpy.internal",
                role: "admin",
                scopes: ["runtime", "analytics", "distribution", "users", "audit"],
                active: true,
                lastAction: "2026-04-06 07:42"
            },
            {
                userId: 12,
                name: "Jordan Kline",
                email: "jordan.kline@stockpy.internal",
                role: "operator",
                scopes: ["distribution", "tasks", "users"],
                active: true,
                lastAction: "2026-04-06 07:18"
            },
            {
                userId: 18,
                name: "Priya Shah",
                email: "priya.shah@stockpy.internal",
                role: "operator",
                scopes: ["tasks", "audit"],
                active: true,
                lastAction: "2026-04-06 07:42"
            },
            {
                userId: 24,
                name: "Leo Anders",
                email: "leo.anders@stockpy.internal",
                role: "viewer",
                scopes: ["analytics", "runtime"],
                active: false,
                lastAction: "2026-04-03 22:12"
            }
        ],
        bulkPayload: {
            user_ids: [1041, 1187, 2781],
            plan: "pro-trader",
            is_active: true
        },
        operatorPayload: {
            role: "operator",
            scopes: ["distribution", "tasks", "users"],
            is_active: true
        }
    },
    communications: {
        composerPayload: {
            user_ids: [1041, 2338, 2781],
            emails: ["79343654@qq.com"],
            title: "Plan cleanup acknowledgement",
            body: "Your subscription configuration changed after a failed billing recovery. Please acknowledge before market open.",
            channels: ["email", "push"],
            notification_type: "manual.billing-follow-up",
            ack_required: true,
            ack_deadline_at: "2026-04-06T12:30:00Z",
            metadata: {
                cohort: "billing-recovery",
                source: "admin-console"
            }
        },
        receipts: [
            {
                id: "rcp_8812",
                userId: 1041,
                notificationId: "notif_34091",
                channel: "push",
                delivery: "failed",
                followUp: "escalated",
                ackRequired: true,
                deadline: "11:30 UTC",
                overdue: true,
                level: 2
            },
            {
                id: "rcp_8813",
                userId: 2338,
                notificationId: "notif_34091",
                channel: "email",
                delivery: "delivered",
                followUp: "claimed",
                ackRequired: true,
                deadline: "12:30 UTC",
                overdue: false,
                level: 1
            },
            {
                id: "rcp_8814",
                userId: 2781,
                notificationId: "notif_34091",
                channel: "push",
                delivery: "retrying",
                followUp: "none",
                ackRequired: true,
                deadline: "12:30 UTC",
                overdue: false,
                level: 0
            }
        ],
        outbox: [
            {
                id: "out_5501",
                notificationId: "notif_34091",
                userId: 1041,
                channel: "push",
                status: "failed",
                lastError: "expo gateway timeout",
                createdAt: "07:11 UTC"
            },
            {
                id: "out_5502",
                notificationId: "notif_34091",
                userId: 2338,
                channel: "email",
                status: "sent",
                lastError: null,
                createdAt: "07:11 UTC"
            },
            {
                id: "out_5503",
                notificationId: "notif_33988",
                userId: 1187,
                channel: "email",
                status: "claimed",
                lastError: "stale worker reservation",
                createdAt: "06:52 UTC"
            }
        ],
        trades: [
            {
                id: "trade_4018",
                userId: 1041,
                symbol: "NVDA",
                action: "buy",
                status: "pending_confirmation",
                suggestedAmount: "$18,200",
                expiresAt: "08:20 UTC",
                operator: "Priya Shah",
                expired: false
            },
            {
                id: "trade_4019",
                userId: 2338,
                symbol: "MSFT",
                action: "sell",
                status: "claimed",
                suggestedAmount: "$44,180",
                expiresAt: "08:10 UTC",
                operator: "Jordan Kline",
                expired: false
            },
            {
                id: "trade_4021",
                userId: 2781,
                symbol: "TSLA",
                action: "buy",
                status: "pending_confirmation",
                suggestedAmount: "$6,980",
                expiresAt: "06:45 UTC",
                operator: "unclaimed",
                expired: true
            }
        ]
    },
    intelligence: {
        analytics: [
            {
                label: "24h revenue at risk",
                value: "$18.4K",
                delta: "driven by suspended enterprise accounts",
                tone: "warning"
            },
            {
                label: "Distribution latency",
                value: "84s",
                delta: "p95 end-to-end notification latency",
                tone: "brand"
            },
            {
                label: "Strategy win rate",
                value: "61.2%",
                delta: "+2.8 pts over 7d window",
                tone: "positive"
            },
            {
                label: "Agent turnaround",
                value: "3m 42s",
                delta: "2 delayed jobs over SLA",
                tone: "warning"
            }
        ],
        distribution: [
            { label: "Email delivered", value: 84 },
            { label: "Push delivered", value: 62 },
            { label: "Manual follow-up", value: 18 },
            { label: "Suppressed", value: 11 }
        ],
        strategies: [
            { rank: 1, name: "Momentum Alpha 30m", score: 0.82, degradation: 0.04, symbols: 22 },
            { rank: 2, name: "Mean Revert QQQ 1h", score: 0.77, degradation: 0.08, symbols: 11 },
            { rank: 3, name: "Breakout SFP 4h", score: 0.72, degradation: 0.11, symbols: 18 },
            { rank: 4, name: "Liquidity Sweep Daily", score: 0.69, degradation: 0.13, symbols: 9 }
        ],
        agents: [
            { name: "Delayed analyses", value: "2", endpoint: "/v1/admin/tradingagents/reconcile-delayed" },
            { name: "Completed today", value: "61", endpoint: "/v1/admin/tradingagents/analyses" },
            { name: "Manual triggers", value: "9", endpoint: "/v1/admin/tradingagents/analyses" }
        ],
        signalStats: [
            { label: "Signals generated", value: "1,284", tone: "brand" },
            { label: "Strong buy ratio", value: "24%", tone: "positive" },
            { label: "Suppressed", value: "38%", tone: "warning" },
            { label: "Validation flagged", value: "7%", tone: "negative" }
        ],
        scannerRuns: [
            {
                runId: "scan_9921",
                startedAt: "07:20 UTC",
                universe: "US equities / 182 symbols",
                emitted: 34,
                suppressed: 16,
                skipped: 9,
                status: "completed"
            },
            {
                runId: "scan_9920",
                startedAt: "06:20 UTC",
                universe: "US equities / 182 symbols",
                emitted: 28,
                suppressed: 21,
                skipped: 7,
                status: "completed"
            },
            {
                runId: "scan_9919",
                startedAt: "05:20 UTC",
                universe: "US equities / 182 symbols",
                emitted: 19,
                suppressed: 27,
                skipped: 12,
                status: "warning"
            }
        ],
        decisions: [
            { symbol: "NVDA", status: "emitted", reason: "SFP + FVG confirmed", confidence: "0.86" },
            { symbol: "AMD", status: "suppressed", reason: "Spread above threshold", confidence: "0.44" },
            { symbol: "TSLA", status: "skipped", reason: "No valid structure shift", confidence: "0.31" },
            { symbol: "MSFT", status: "emitted", reason: "Chooch + liquidity sweep", confidence: "0.78" }
        ],
        anomalies: [
            { symbol: "TSM", severity: "critical", issue: "Gap in OHLCV candle set", source: "alphavantage-proxy", observedAt: "06:42 UTC" },
            { symbol: "BABA", severity: "warning", issue: "Volume spike outside tolerance", source: "bulk-import", observedAt: "06:11 UTC" },
            { symbol: "QQQ", severity: "error", issue: "Duplicate bar timestamps", source: "ohlcv-import", observedAt: "05:48 UTC" }
        ]
    },
    runtime: {
        metrics: [
            { label: "Component coverage", value: "96%", delta: "24 / 25 expected nodes reporting", tone: "positive" },
            { label: "Kafka lag", value: "450 msg", delta: "event pipeline consumer warning", tone: "warning" },
            { label: "Redis hit rate", value: "98.5%", delta: "within target", tone: "positive" },
            { label: "P99 API latency", value: "42ms", delta: "stable over 1h", tone: "brand" }
        ],
        components: [
            {
                name: "scheduler-main",
                kind: "scheduler",
                health: "healthy",
                status: "running",
                lastSeen: "07:44 UTC",
                copy: "Cron-style orchestration for retention, cold storage, and periodic analytics snapshots."
            },
            {
                name: "worker-market-data-1",
                kind: "worker",
                health: "healthy",
                status: "running",
                lastSeen: "07:44 UTC",
                copy: "Ingesting OHLCV batches and repairing transient import gaps."
            },
            {
                name: "worker-backtest-pool",
                kind: "worker",
                health: "stale",
                status: "running",
                lastSeen: "07:31 UTC",
                copy: "CPU pressure is delaying ranking refresh jobs past desired freshness budget."
            },
            {
                name: "worker-event-pipeline",
                kind: "worker",
                health: "error",
                status: "degraded",
                lastSeen: "07:40 UTC",
                copy: "Outbox consumer lag and retries are inflating receipt escalation volume."
            }
        ],
        alerts: [
            {
                title: "Runtime alert: worker heartbeat stale",
                copy: "Backtest pool missed two heartbeat windows while strategy refresh was executing 28 windows in parallel.",
                tone: "danger",
                meta: ["runtime/alerts", "worker-backtest-pool"]
            },
            {
                title: "Platform alert: broker lag rising",
                copy: "Kafka lag crossed 400 messages. Delivery retries should be monitored before the next manual campaign.",
                tone: "warning",
                meta: ["runtime/metrics", "broker"]
            },
            {
                title: "Acceptance snapshot current",
                copy: "Contract tests, load proofs, and OpenAPI manifests were refreshed 42 minutes ago.",
                tone: "success",
                meta: ["acceptance/status", "qa"]
            }
        ],
        audit: [
            {
                timestamp: "07:42 UTC",
                entity: "trade_task",
                action: "claimed",
                source: "admin-api",
                operator: "18",
                requestId: "req_9b12f4"
            },
            {
                timestamp: "07:13 UTC",
                entity: "operator",
                action: "role.updated",
                source: "admin-api",
                operator: "7",
                requestId: "req_7d32c8"
            },
            {
                timestamp: "06:55 UTC",
                entity: "notification",
                action: "manual_message.queued",
                source: "admin-api",
                operator: "12",
                requestId: "req_6afc19"
            },
            {
                timestamp: "05:04 UTC",
                entity: "acceptance_report",
                action: "snapshot.refreshed",
                source: "qa-pipeline",
                operator: "system",
                requestId: "req_1c83de"
            }
        ],
        acceptance: {
            status: "ready-with-observations",
            updatedAt: "2026-04-06 07:02 UTC",
            items: [
                { label: "OpenAPI snapshots exported", state: "done" },
                { label: "Contract suite clean", state: "done" },
                { label: "Load evidence attached", state: "done" },
                { label: "Backtest freshness within SLA", state: "attention" },
                { label: "Runtime alerts below threshold", state: "attention" }
            ]
        }
    },
    experiments: {
        metrics: [
            { label: "Backtest runs today", value: "38", delta: "+6 manual refreshes", tone: "brand" },
            { label: "Completed successfully", value: "31", delta: "81.5% success rate", tone: "positive" },
            { label: "Delayed analyses", value: "2", delta: "reconcile recommended", tone: "warning" },
            { label: "Ranking leaders", value: "4", delta: "covering 22 symbols max", tone: "brand" }
        ],
        backtests: [
            {
                id: 881,
                strategy: "Momentum Alpha",
                timeframe: "30m",
                symbol: "NVDA",
                window: "90d",
                status: "completed",
                score: "0.82",
                updatedAt: "07:05 UTC"
            },
            {
                id: 882,
                strategy: "Mean Revert QQQ",
                timeframe: "1h",
                symbol: "QQQ",
                window: "180d",
                status: "running",
                score: "-",
                updatedAt: "07:28 UTC"
            },
            {
                id: 883,
                strategy: "Liquidity Sweep",
                timeframe: "4h",
                symbol: "MSFT",
                window: "90d",
                status: "failed",
                score: "-",
                updatedAt: "06:49 UTC"
            }
        ],
        rankings: [
            { rank: 1, strategy: "Momentum Alpha", timeframe: "30m", score: "0.82", degradation: "0.04", symbols: 22 },
            { rank: 2, strategy: "Mean Revert QQQ", timeframe: "1h", score: "0.77", degradation: "0.08", symbols: 11 },
            { rank: 3, strategy: "Breakout SFP", timeframe: "4h", score: "0.72", degradation: "0.11", symbols: 18 }
        ],
        refreshPayload: {
            symbols: ["NVDA", "MSFT", "QQQ"],
            strategy_names: ["Momentum Alpha", "Mean Revert QQQ"],
            windows: [24, 72, 168],
            timeframe: "30m"
        },
        analyses: [
            {
                requestId: "ta_5102",
                symbol: "NVDA",
                trigger: "scanner",
                status: "completed",
                finalAction: "buy",
                latency: "2m 14s"
            },
            {
                requestId: "ta_5103",
                symbol: "TSLA",
                trigger: "manual",
                status: "delayed",
                finalAction: "pending",
                latency: "7m 54s"
            },
            {
                requestId: "ta_5104",
                symbol: "AAPL",
                trigger: "scheduled",
                status: "completed",
                finalAction: "hold",
                latency: "3m 09s"
            }
        ]
    }
};
