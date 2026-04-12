(function () {
    if (!window.AdminAPI) return;

    const api = window.AdminAPI;

    const ARRAY_STRING_FIELDS = new Set([
        "scopes",
        "symbols",
        "strategy_names",
        "channels",
        "emails",
        "outbox_ids",
        "trade_ids"
    ]);
    const ARRAY_INT_FIELDS = new Set(["user_ids", "windows"]);
    const BOOLEAN_FIELDS = new Set([
        "is_active",
        "ack_required",
        "overdue_only",
        "expired_only",
        "claimed_only",
        "suppressed"
    ]);
    const INTEGER_FIELDS = new Set([
        "limit",
        "offset",
        "window_hours",
        "decision_limit",
        "older_than_minutes",
        "user_id",
        "claimed_by_operator_id",
        "run_id",
        "bucket_id",
        "delayed_threshold_minutes"
    ]);
    const JSON_FIELDS = new Set(["metadata", "extra"]);

    const OPERATOR_REQUIRED_PATHS = new Set([
        "/v1/admin/distribution/manual-message",
        "/v1/admin/tasks/trades/claim"
    ]);

    function endpoint(method, path, opts) {
        return {
            method,
            path,
            operatorRequired: Boolean(opts && opts.operatorRequired),
            queryTemplate: (opts && opts.queryTemplate) || {},
            bodyTemplate: (opts && opts.bodyTemplate) || null,
            requiresBody: Boolean(opts && opts.requiresBody)
        };
    }

    const ALL_ENDPOINTS = [
        endpoint("GET", "/v1/admin/acceptance/status"),
        endpoint("GET", "/v1/admin/acceptance/report"),
        endpoint("GET", "/v1/admin/operators"),
        endpoint("PUT", "/v1/admin/operators/{user_id}", {
            requiresBody: true,
            bodyTemplate: { role: "operator", scopes: ["tasks"], is_active: true }
        }),
        endpoint("GET", "/v1/admin/signal-stats/summary", { queryTemplate: { window_hours: 24 } }),
        endpoint("GET", "/v1/admin/signal-stats/quality", { queryTemplate: { window_hours: 24 } }),
        endpoint("GET", "/v1/admin/signal-stats"),
        endpoint("GET", "/v1/admin/scanner"),
        endpoint("GET", "/v1/admin/scanner/observability"),
        endpoint("GET", "/v1/admin/scanner/runs/{run_id}"),
        endpoint("GET", "/v1/admin/scanner/live-decision"),
        endpoint("GET", "/v1/admin/runtime/components"),
        endpoint("GET", "/v1/admin/runtime/stats"),
        endpoint("GET", "/v1/admin/runtime/health"),
        endpoint("GET", "/v1/admin/runtime/metrics"),
        endpoint("GET", "/v1/admin/runtime/alerts"),
        endpoint("GET", "/v1/admin/runtime/components/{component_kind}/{component_name}"),
        endpoint("GET", "/v1/admin/tradingagents/analyses"),
        endpoint("GET", "/v1/admin/tradingagents/analyses/{request_id}"),
        endpoint("POST", "/v1/admin/tradingagents/reconcile-delayed"),
        endpoint("GET", "/v1/admin/tradingagents/stats"),
        endpoint("GET", "/v1/admin/audit"),
        endpoint("GET", "/v1/admin/analytics/overview", { queryTemplate: { window_hours: 24 } }),
        endpoint("GET", "/v1/admin/analytics/distribution", { queryTemplate: { window_hours: 24 } }),
        endpoint("GET", "/v1/admin/analytics/signal-results", { queryTemplate: { window_hours: 24 } }),
        endpoint("GET", "/v1/admin/analytics/strategy-health", { queryTemplate: { window_hours: 168 } }),
        endpoint("GET", "/v1/admin/analytics/tradingagents", { queryTemplate: { window_hours: 24 } }),
        endpoint("GET", "/v1/admin/calibrations"),
        endpoint("GET", "/v1/admin/calibrations/active"),
        endpoint("GET", "/v1/admin/calibrations/proposal", {
            queryTemplate: { signal_window_hours: 24, ranking_window_hours: 168 }
        }),
        endpoint("POST", "/v1/admin/calibrations/proposal/apply", {
            requiresBody: true,
            bodyTemplate: {
                signal_window_hours: 24,
                ranking_window_hours: 168,
                activate: false,
                version: "signals-v2-proposal-20260411-r1",
                notes: "Reviewed in admin console and staged for operator validation"
            }
        }),
        endpoint("POST", "/v1/admin/calibrations/{snapshot_id}/activate"),
        endpoint("POST", "/v1/admin/calibrations", {
            requiresBody: true,
            bodyTemplate: {
                version: "signals-v2-review-20260411",
                source: "manual_review",
                activate: false,
                derived_from: "backtest:30d-ranking + live:24h-results",
                sample_size: 128,
                strategy_weights: {
                    trend_continuation: 1.08,
                    mean_reversion: 0.97
                },
                score_multipliers: {
                    confidence: 1.04,
                    liquidity_penalty: 1.1
                }
            }
        }),
        endpoint("GET", "/v1/admin/users"),
        endpoint("GET", "/v1/admin/users/{user_id}"),
        endpoint("PUT", "/v1/admin/users/{user_id}", {
            requiresBody: true,
            bodyTemplate: { plan: "pro-trader", is_active: true }
        }),
        endpoint("POST", "/v1/admin/users/bulk", {
            requiresBody: true,
            bodyTemplate: { user_ids: [1], plan: "pro-trader", is_active: true }
        }),
        endpoint("GET", "/v1/admin/backtests"),
        endpoint("GET", "/v1/admin/backtests/runs"),
        endpoint("GET", "/v1/admin/backtests/runs/{run_id}"),
        endpoint("GET", "/v1/admin/backtests/rankings/latest"),
        endpoint("POST", "/v1/admin/backtests/runs", {
            requiresBody: true,
            bodyTemplate: {
                symbols: ["NVDA", "MSFT"],
                strategy_names: ["Momentum Alpha"],
                windows: [24, 72],
                timeframe: "1d"
            }
        }),
        endpoint("POST", "/v1/admin/distribution/manual-message", {
            operatorRequired: true,
            requiresBody: true,
            bodyTemplate: {
                user_ids: [1],
                title: "Manual campaign",
                body: "Message body",
                channels: ["email"],
                notification_type: "manual.message",
                ack_required: false,
                metadata: { source: "admin-console" }
            }
        }),
        endpoint("GET", "/v1/admin/anomalies/ohlcv"),
        endpoint("GET", "/v1/admin/tasks"),
        endpoint("GET", "/v1/admin/tasks/receipts"),
        endpoint("POST", "/v1/admin/tasks/receipts/escalate-overdue"),
        endpoint("POST", "/v1/admin/tasks/receipts/ack", {
            requiresBody: true,
            bodyTemplate: { receipt_id: "" }
        }),
        endpoint("POST", "/v1/admin/tasks/receipts/{receipt_id}/claim"),
        endpoint("POST", "/v1/admin/tasks/receipts/{receipt_id}/resolve"),
        endpoint("POST", "/v1/admin/tasks/emails/claim"),
        endpoint("POST", "/v1/admin/tasks/emails/retry", {
            requiresBody: true,
            bodyTemplate: { outbox_ids: [""] }
        }),
        endpoint("GET", "/v1/admin/tasks/trades"),
        endpoint("POST", "/v1/admin/tasks/trades/claim", {
            operatorRequired: true,
            requiresBody: true,
            bodyTemplate: {}
        }),
        endpoint("POST", "/v1/admin/tasks/trades/expire", {
            requiresBody: true,
            bodyTemplate: {}
        }),
        endpoint("GET", "/v1/admin/tasks/outbox"),
        endpoint("POST", "/v1/admin/tasks/outbox/retry", {
            requiresBody: true,
            bodyTemplate: { outbox_ids: [""] }
        }),
        endpoint("POST", "/v1/admin/tasks/outbox/release-stale"),
        endpoint("POST", "/v1/admin/tasks/outbox/{outbox_id}/requeue")
    ];

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function formatDate(value) {
        if (!value) return "N/A";
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) {
            return String(value);
        }
        return parsed.toLocaleString();
    }

    function formatMoney(value) {
        const parsed = Number(value);
        if (!Number.isFinite(parsed)) return "0";
        return parsed.toLocaleString(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
        });
    }

    function parseEndpoint(raw) {
        const text = String(raw || "").trim();
        const match = text.match(/^(GET|POST|PUT|DELETE|PATCH)\s+([^\s]+)$/i);
        if (!match) return null;
        return {
            method: match[1].toUpperCase(),
            path: match[2].replace(/[<].*$/, "")
        };
    }

    function splitList(value) {
        return String(value || "")
            .split(/[\n,，;；]+/)
            .map((item) => item.trim())
            .filter(Boolean);
    }

    function coerceScalar(key, value) {
        const trimmed = String(value ?? "").trim();
        if (!trimmed) return "";

        if (BOOLEAN_FIELDS.has(key)) {
            if (trimmed === "true") return true;
            if (trimmed === "false") return false;
        }
        if (INTEGER_FIELDS.has(key)) {
            const parsedInt = Number(trimmed);
            return Number.isFinite(parsedInt) ? parsedInt : trimmed;
        }
        if (JSON_FIELDS.has(key)) {
            try {
                return JSON.parse(trimmed);
            } catch (_err) {
                return trimmed;
            }
        }
        if (key === "ack_deadline_at" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(trimmed)) {
            const parsedDate = new Date(trimmed);
            if (!Number.isNaN(parsedDate.getTime())) {
                return parsedDate.toISOString();
            }
        }
        if (trimmed === "true") return true;
        if (trimmed === "false") return false;
        return trimmed;
    }

    function normalizePayload(payload) {
        const result = {};
        Object.entries(payload || {}).forEach(([key, rawValue]) => {
            if (rawValue === undefined || rawValue === null) return;

            if (ARRAY_STRING_FIELDS.has(key)) {
                const items = Array.isArray(rawValue)
                    ? rawValue.flatMap((item) => splitList(item))
                    : splitList(rawValue);
                if (items.length > 0) {
                    result[key] = items;
                }
                return;
            }

            if (ARRAY_INT_FIELDS.has(key)) {
                const items = (Array.isArray(rawValue)
                    ? rawValue.flatMap((item) => splitList(item))
                    : splitList(rawValue)
                )
                    .map((item) => Number(item))
                    .filter((item) => Number.isFinite(item));
                if (items.length > 0) {
                    result[key] = items;
                }
                return;
            }

            if (Array.isArray(rawValue)) {
                const coerced = rawValue
                    .map((item) => coerceScalar(key, item))
                    .filter((item) => item !== "");
                if (coerced.length > 0) {
                    result[key] = coerced;
                }
                return;
            }

            const coerced = coerceScalar(key, rawValue);
            if (coerced !== "") {
                result[key] = coerced;
            }
        });
        return result;
    }

    function formToPayload(form) {
        const formData = new FormData(form);
        const payload = {};
        for (const [key, value] of formData.entries()) {
            if (payload[key] !== undefined) {
                if (!Array.isArray(payload[key])) {
                    payload[key] = [payload[key]];
                }
                payload[key].push(value);
            } else {
                payload[key] = value;
            }
        }
        return normalizePayload(payload);
    }

    function pathTemplateToRegex(pathTemplate) {
        const escaped = pathTemplate.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        return new RegExp(`^${escaped.replace(/\\\{[^}]+\\\}/g, "[^/]+")}$`);
    }

    function findEndpointSpec(method, path) {
        const normalizedMethod = String(method || "").toUpperCase();
        const normalizedPath = String(path || "").trim();
        return (
            ALL_ENDPOINTS.find((item) => item.method === normalizedMethod && item.path === normalizedPath) ||
            ALL_ENDPOINTS.find(
                (item) => item.method === normalizedMethod && pathTemplateToRegex(item.path).test(normalizedPath)
            ) ||
            endpoint(normalizedMethod, normalizedPath)
        );
    }

    function buildQueryString(params) {
        const query = new URLSearchParams();
        Object.entries(params || {}).forEach(([key, rawValue]) => {
            if (rawValue === undefined || rawValue === null || rawValue === "") return;
            if (Array.isArray(rawValue)) {
                rawValue.forEach((item) => {
                    if (item !== undefined && item !== null && item !== "") {
                        query.append(key, String(item));
                    }
                });
                return;
            }
            query.set(key, String(rawValue));
        });
        const text = query.toString();
        return text ? `?${text}` : "";
    }

    function resolvePath(pathTemplate, payload) {
        let path = pathTemplate;
        const body = { ...(payload || {}) };
        const pathParams = [...String(pathTemplate).matchAll(/\{([^}]+)\}/g)].map((match) => match[1]);

        pathParams.forEach((param) => {
            let value = body[param];
            if (value === undefined || value === null || value === "") {
                const alias = {
                    id: ["outbox_id", "receipt_id", "user_id", "run_id", "request_id"],
                    outbox_id: ["id"],
                    user_id: ["id"],
                    run_id: ["id"],
                    request_id: ["id"],
                    component_kind: ["kind"],
                    component_name: ["name"]
                };
                const aliases = alias[param] || [];
                aliases.forEach((key) => {
                    if (value === undefined && body[key] !== undefined && body[key] !== "") {
                        value = body[key];
                        delete body[key];
                    }
                });
            }
            if (value === undefined || value === null || value === "") {
                const prompted = window.prompt(`请填写路径参数 ${param} 的值`, "");
                if (!prompted) {
                    throw new Error(`缺少路径参数：${param}`);
                }
                value = prompted;
            }
            delete body[param];
            path = path.replace(`{${param}}`, encodeURIComponent(String(value)));
        });

        return { path, body };
    }

    async function requestSafe(path, options) {
        try {
            return await api.request(path, options);
        } catch (error) {
            console.warn(`Failed request: ${options && options.method ? options.method : "GET"} ${path}`, error);
            return null;
        }
    }

    function renderPayload(targetId, payload, isError) {
        if (!targetId) return;
        const target = document.getElementById(targetId);
        if (!target) return;
        const color = isError ? "#f87171" : "#eaf0ff";
        target.innerHTML = `<pre class="code-block" style="color:${color};">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>`;
    }

    function pushToast(title, copy) {
        const stack = document.getElementById("toast-stack");
        if (!stack) {
            console.info(title, copy);
            return;
        }
        const toast = document.createElement("div");
        toast.className = "toast";
        toast.innerHTML = `<div class="toast__title">${escapeHtml(title)}</div><div class="toast__copy">${escapeHtml(copy)}</div>`;
        stack.appendChild(toast);
        setTimeout(() => toast.remove(), 3200);
    }

    async function executeSpec(spec, payload, targetId) {
        const resolved = resolvePath(spec.path, payload);
        let path = resolved.path;
        let body = resolved.body;

        const method = spec.method.toUpperCase();
        const options = {
            method,
            operatorRequired: Boolean(spec.operatorRequired || OPERATOR_REQUIRED_PATHS.has(spec.path))
        };

        if (method === "GET" || method === "DELETE") {
            path += buildQueryString(body);
        } else {
            options.body = JSON.stringify(body || {});
        }

        try {
            const response = await api.request(path, options);
            renderPayload(targetId, response, false);
            pushToast("API 请求成功", `${method} ${path}`);
            return response;
        } catch (error) {
            const payloadError = {
                message: error.message,
                status: error.status,
                path,
                details: error.payload || null
            };
            renderPayload(targetId, payloadError, true);
            pushToast("API 请求失败", `${method} ${path}`);
            throw error;
        }
    }

    function parseJsonOrEmpty(text, label) {
        const raw = String(text || "").trim();
        if (!raw) return {};
        try {
            return JSON.parse(raw);
        } catch (_err) {
            throw new Error(`${label} 必须是合法 JSON`);
        }
    }

    async function loadPeople(dataObj) {
        const [users, operators, enterpriseUsers, inactiveUsers] = await Promise.all([
            requestSafe("/v1/admin/users?limit=50"),
            requestSafe("/v1/admin/operators?limit=50"),
            requestSafe("/v1/admin/users?limit=1&plan=enterprise"),
            requestSafe("/v1/admin/users?limit=1&is_active=false")
        ]);

        if (users && Array.isArray(users.data) && dataObj.people) {
            dataObj.people.users = users.data.map((item) => ({
                id: item.id,
                name: item.name || "Unknown",
                email: item.email,
                subscription: item.subscription_status || "n/a",
                plan: item.plan || "unknown",
                status: item.is_active ? "active" : "inactive",
                capital: formatMoney(item.total_capital),
                currency: item.currency || "USD",
                locale: [item.locale, item.timezone].filter(Boolean).join(" / "),
                lastLogin: formatDate(item.last_login_at)
            }));
            dataObj.people.metrics[0].value = String(users.total || users.data.length || 0);
            dataObj.people.metrics[0].delta = `${users.has_more ? "Paginated" : "Live"} user list`;
        }

        if (operators && Array.isArray(operators.data) && dataObj.people) {
            dataObj.people.operators = operators.data.map((item) => ({
                userId: item.user_id,
                name: item.name || "Unknown",
                email: item.email || "",
                role: item.role || "viewer",
                scopes: item.scopes || [],
                active: Boolean(item.is_active),
                lastAction: formatDate(item.last_action_at)
            }));
            dataObj.people.metrics[3].value = String(operators.total || operators.data.length || 0);
            dataObj.people.metrics[3].delta = "live operators";
        }

        if (enterpriseUsers && dataObj.people) {
            dataObj.people.metrics[1].value = String(enterpriseUsers.total || 0);
            dataObj.people.metrics[1].delta = "enterprise plans";
        }

        if (inactiveUsers && dataObj.people) {
            dataObj.people.metrics[2].value = String(inactiveUsers.total || 0);
            dataObj.people.metrics[2].delta = "inactive users";
        }
    }

    async function loadCommunications(dataObj) {
        const [receipts, outbox, trades] = await Promise.all([
            requestSafe("/v1/admin/tasks/receipts?limit=25"),
            requestSafe("/v1/admin/tasks/outbox?limit=25"),
            requestSafe("/v1/admin/tasks/trades?limit=25")
        ]);

        if (receipts && Array.isArray(receipts.data) && dataObj.communications) {
            dataObj.communications.receipts = receipts.data.map((item) => ({
                id: item.id,
                userId: item.user_id,
                notificationId: item.notification_id,
                channel: item.last_delivery_channel || "unknown",
                delivery: item.last_delivery_status || "pending",
                followUp: item.manual_follow_up_status || "none",
                ackRequired: Boolean(item.ack_required),
                deadline: formatDate(item.ack_deadline_at),
                overdue: Boolean(item.overdue),
                level: item.escalation_level || 0
            }));
        }

        if (outbox && Array.isArray(outbox.data) && dataObj.communications) {
            dataObj.communications.outbox = outbox.data.map((item) => ({
                id: item.id,
                notificationId: item.notification_id || "n/a",
                userId: item.user_id,
                channel: item.channel,
                status: item.status,
                lastError: item.last_error || null,
                createdAt: formatDate(item.created_at)
            }));
        }

        if (trades && Array.isArray(trades.data) && dataObj.communications) {
            dataObj.communications.trades = trades.data.map((item) => ({
                id: item.id,
                userId: item.user_id,
                symbol: item.symbol,
                action: item.action,
                status: item.status,
                suggestedAmount: `$${formatMoney(item.suggested_amount)}`,
                expiresAt: formatDate(item.expires_at),
                operator: item.claimed_by_operator_id || "unclaimed",
                expired: Boolean(item.is_expired)
            }));
        }
    }

    async function loadIntelligence(dataObj) {
        const [overview, distribution, signalResults, strategyHealth, tradingMetrics, signalSummary, signalQuality, activeCalibration, calibrationHistory, calibrationProposal, observability, anomalies] = await Promise.all([
            requestSafe("/v1/admin/analytics/overview?window_hours=24"),
            requestSafe("/v1/admin/analytics/distribution?window_hours=24"),
            requestSafe("/v1/admin/analytics/signal-results?window_hours=24"),
            requestSafe("/v1/admin/analytics/strategy-health?window_hours=168"),
            requestSafe("/v1/admin/analytics/tradingagents?window_hours=24"),
            requestSafe("/v1/admin/signal-stats/summary?window_hours=24"),
            requestSafe("/v1/admin/signal-stats/quality?window_hours=24"),
            requestSafe("/v1/admin/calibrations/active"),
            requestSafe("/v1/admin/calibrations?limit=5"),
            requestSafe("/v1/admin/calibrations/proposal?signal_window_hours=24&ranking_window_hours=168"),
            requestSafe("/v1/admin/scanner/observability?limit=10&decision_limit=10"),
            requestSafe("/v1/admin/anomalies/ohlcv?limit=10")
        ]);

        if (!dataObj.intelligence) return;

        if (overview) {
            dataObj.intelligence.analytics = [
                {
                    label: "Signals generated",
                    value: String(overview.generated_signals || 0),
                    delta: `${overview.window_hours || 24}h overview`,
                    tone: "brand"
                },
                {
                    label: "Trade actions",
                    value: String(overview.trade_actions || 0),
                    delta: "from analytics overview",
                    tone: "positive"
                },
                {
                    label: "Notification requests",
                    value: String(overview.notification_requests || 0),
                    delta: `${overview.delivered_notifications || 0} delivered`,
                    tone: "warning"
                },
                {
                    label: "Terminal AI outcomes",
                    value: String(overview.tradingagents_terminals || 0),
                    delta: formatDate(overview.latest_event_at),
                    tone: "brand"
                }
            ];
        }

        if (distribution && Array.isArray(distribution.channels)) {
            dataObj.intelligence.distribution = distribution.channels.map((item) => ({
                label: `${String(item.channel || "channel").toUpperCase()} delivered`,
                value: Number(item.delivered || 0)
            }));
        }

        if (strategyHealth && Array.isArray(strategyHealth.strategies)) {
            dataObj.intelligence.strategies = strategyHealth.strategies.slice(0, 6).map((item) => ({
                rank: item.rank,
                name: item.strategy_name,
                score: Number(item.score || 0).toFixed(2),
                degradation: Number(item.degradation || 0).toFixed(2),
                symbols: item.symbols_covered || 0
            }));
        }

        if (tradingMetrics) {
            dataObj.intelligence.agents = [
                {
                    name: "Open analyses",
                    value: String(tradingMetrics.open_total || 0),
                    endpoint: "/v1/admin/tradingagents/analyses"
                },
                {
                    name: "Completed",
                    value: String(tradingMetrics.completed_total || 0),
                    endpoint: "/v1/admin/tradingagents/stats"
                },
                {
                    name: "Success rate",
                    value: `${Number(tradingMetrics.success_rate || 0).toFixed(2)}%`,
                    endpoint: "/v1/admin/analytics/tradingagents"
                }
            ];
        }

        if (signalSummary || signalQuality) {
            const totalSignals = Number((signalSummary && signalSummary.total_signals) || (signalQuality && signalQuality.total_signals) || 0);
            const strategyCoverage = totalSignals > 0
                ? `${Math.round((Number(signalQuality && signalQuality.signals_with_strategy_selection || 0) / totalSignals) * 100)}%`
                : "0%";
            const exitCoverage = totalSignals > 0
                ? `${Math.round((Number(signalQuality && signalQuality.signals_with_exit_levels || 0) / totalSignals) * 100)}%`
                : "0%";
            const calibrationCoverage = totalSignals > 0
                ? `${Math.round((Number(signalQuality && signalQuality.signals_with_calibration_version || 0) / totalSignals) * 100)}%`
                : "0%";
            const topStrategy = signalQuality && Array.isArray(signalQuality.top_strategies) && signalQuality.top_strategies[0]
                ? signalQuality.top_strategies[0]
                : null;
            const topExitSource = signalQuality && Array.isArray(signalQuality.exit_level_sources) && signalQuality.exit_level_sources[0]
                ? signalQuality.exit_level_sources[0]
                : null;
            const topCalibration = signalQuality && Array.isArray(signalQuality.calibration_versions) && signalQuality.calibration_versions[0]
                ? signalQuality.calibration_versions[0]
                : null;
            const topRegime = signalQuality && Array.isArray(signalQuality.market_regimes) && signalQuality.market_regimes[0]
                ? signalQuality.market_regimes[0]
                : null;

            dataObj.intelligence.signalStats = [
                { label: "Signals generated", value: String(totalSignals || 0), tone: "brand" },
                {
                    label: "Strategy metadata",
                    value: strategyCoverage,
                    tone: "positive"
                },
                {
                    label: "Exit metadata",
                    value: exitCoverage,
                    tone: "warning"
                },
                {
                    label: "Calibration tagged",
                    value: calibrationCoverage,
                    tone: "brand"
                }
            ];

            dataObj.intelligence.signalQuality = [
                {
                    label: "Top strategy",
                    value: topStrategy ? `${topStrategy.key} · ${topStrategy.count}` : "n/a",
                    detail: topStrategy ? "Current leader in strategy selection coverage." : "Waiting for strategy selection metadata."
                },
                {
                    label: "Exit source",
                    value: topExitSource ? `${topExitSource.key} · ${topExitSource.count}` : "n/a",
                    detail: topExitSource ? "Primary exit-level ownership in recent signals." : "Waiting for exit-level metadata."
                },
                {
                    label: "Calibration version",
                    value: topCalibration ? `${topCalibration.key} · ${topCalibration.count}` : "n/a",
                    detail: topCalibration ? "Most common live calibration tag in the recent window." : "No calibration version tagged yet."
                },
                {
                    label: "Dominant regime",
                    value: topRegime ? `${topRegime.key} · ${topRegime.count}` : "n/a",
                    detail: topRegime ? "Most common market regime or detail in the recent window." : "Waiting for regime detail metadata."
                }
            ];
        }

        if (signalResults) {
            dataObj.intelligence.signalResults = [
                {
                    label: "Signal / trade ratio",
                    value: `${Number(signalResults.trade_action_rate || 0).toFixed(2)}%`,
                    detail: `${signalResults.total_trade_actions || 0} trade actions vs ${signalResults.total_signals || 0} live signals in-window.`
                },
                {
                    label: "Executed trade ratio",
                    value: `${Number(signalResults.executed_trade_rate || 0).toFixed(2)}%`,
                    detail: `${(signalResults.confirmed_trades || 0) + (signalResults.adjusted_trades || 0)} executed trades across confirmed + adjusted.`
                },
                {
                    label: "Symbol overlap",
                    value: `${signalResults.overlapping_symbols || 0}/${signalResults.unique_signal_symbols || 0}`,
                    detail: `${signalResults.unique_trade_symbols || 0} trade symbols and ${signalResults.unique_signal_symbols || 0} signal symbols are currently comparable by symbol.`
                },
                {
                    label: "Top alignment",
                    value: signalResults.symbol_alignment && signalResults.symbol_alignment[0]
                        ? `${signalResults.symbol_alignment[0].symbol} · ${Number(signalResults.symbol_alignment[0].execution_rate || 0).toFixed(2)}%`
                        : "n/a",
                    detail: signalResults.symbol_alignment && signalResults.symbol_alignment[0]
                        ? `${signalResults.symbol_alignment[0].signals_generated} signals vs ${signalResults.symbol_alignment[0].trade_actions} trade actions for the leading overlapping symbol.`
                        : "No overlapping signal/trade symbols in the current window."
                }
            ];
        }

        const activeCalibrationItem = activeCalibration && activeCalibration.data
            ? activeCalibration.data
            : null;
        const calibrationItems = calibrationHistory && Array.isArray(calibrationHistory.data)
            ? calibrationHistory.data
            : [];

        if (activeCalibrationItem || calibrationItems.length > 0) {
            const rows = calibrationItems.length > 0
                ? calibrationItems
                : [activeCalibrationItem];
            dataObj.intelligence.calibrationSnapshots = rows.slice(0, 4).map((item) => {
                const strategyAdjustments = Object.values(item.strategy_weights || {}).filter((value) => Math.abs(Number(value || 0) - 1) >= 0.01).length;
                const scoreAdjustments = Object.values(item.score_multipliers || {}).filter((value) => Math.abs(Number(value || 0) - 1) >= 0.01).length;
                return {
                    version: item.version,
                    status: item.is_active ? "active" : "stored",
                    source: item.source || "snapshot",
                    effectiveAt: formatDate(item.effective_at || item.created_at),
                    detail: `${strategyAdjustments} strategy weights, ${scoreAdjustments} score multipliers adjusted${item.derived_from ? ` · ${item.derived_from}` : ""}`,
                    note: item.notes || (item.is_active
                        ? "Current active snapshot loaded by the scanner runtime."
                        : "Stored snapshot available for review, rollback, or later activation.")
                };
            });
        }

        if (calibrationProposal) {
            const topStrategyDelta = Array.isArray(calibrationProposal.strategy_weights) && calibrationProposal.strategy_weights[0]
                ? calibrationProposal.strategy_weights[0]
                : null;
            const topScoreDelta = Array.isArray(calibrationProposal.score_multipliers) && calibrationProposal.score_multipliers[0]
                ? calibrationProposal.score_multipliers[0]
                : null;
            dataObj.intelligence.calibrationProposal = [
                {
                    label: "Proposed version",
                    value: calibrationProposal.proposed_version || "n/a",
                    detail: `Active ${calibrationProposal.current_version || "n/a"} · ${calibrationProposal.summary && calibrationProposal.summary.total_signals || 0} live signals reviewed.`
                },
                {
                    label: "Top strategy delta",
                    value: topStrategyDelta
                        ? `${topStrategyDelta.key} · ${Number(topStrategyDelta.proposed_value || 0).toFixed(2)}`
                        : "n/a",
                    detail: topStrategyDelta
                        ? `${topStrategyDelta.delta >= 0 ? "+" : ""}${Number(topStrategyDelta.delta || 0).toFixed(2)} from current weight.`
                        : "No strategy adjustment suggested yet."
                },
                {
                    label: "Top score delta",
                    value: topScoreDelta
                        ? `${topScoreDelta.key} · ${Number(topScoreDelta.proposed_value || 0).toFixed(2)}`
                        : "n/a",
                    detail: topScoreDelta
                        ? `${topScoreDelta.delta >= 0 ? "+" : ""}${Number(topScoreDelta.delta || 0).toFixed(2)} from current multiplier.`
                        : "No score multiplier adjustment suggested yet."
                },
                {
                    label: "Executed trade rate",
                    value: calibrationProposal.summary
                        ? `${Number(calibrationProposal.summary.executed_trade_rate || 0).toFixed(2)}%`
                        : "0.00%",
                    detail: calibrationProposal.summary
                        ? `${calibrationProposal.summary.total_trade_actions || 0} trade actions and ${calibrationProposal.summary.overlapping_symbols || 0} overlapping symbols informed the proposal.`
                        : "Proposal summary unavailable."
                }
            ];
        }

        if (observability && Array.isArray(observability.runs)) {
            dataObj.intelligence.scannerRuns = observability.runs.map((item) => ({
                runId: String(item.id),
                startedAt: formatDate(item.started_at),
                universe: `bucket ${item.bucket_id}`,
                emitted: item.emitted_count,
                suppressed: item.suppressed_count,
                skipped: Math.max((item.scanned_count || 0) - (item.emitted_count || 0) - (item.suppressed_count || 0), 0),
                status: item.status
            }));
            dataObj.intelligence.decisions = (observability.recent_decisions || []).map((item) => ({
                symbol: item.symbol,
                status: item.decision,
                reason: item.reason,
                confidence: item.score !== null && item.score !== undefined ? Number(item.score).toFixed(2) : "n/a"
            }));
        }

        if (anomalies && Array.isArray(anomalies.data)) {
            dataObj.intelligence.anomalies = anomalies.data.map((item) => ({
                symbol: item.symbol,
                severity: item.severity,
                issue: item.anomaly_code,
                source: item.source || "unknown",
                observedAt: formatDate(item.quarantined_at)
            }));
        }
    }

    async function loadRuntime(dataObj) {
        const [components, health, alerts, audit, acceptance] = await Promise.all([
            requestSafe("/v1/admin/runtime/components"),
            requestSafe("/v1/admin/runtime/health"),
            requestSafe("/v1/admin/runtime/alerts"),
            requestSafe("/v1/admin/audit?limit=20"),
            requestSafe("/v1/admin/acceptance/report")
        ]);

        if (!dataObj.runtime) return;

        if (health && health.summary) {
            const unhealthy = Number(health.summary.error || 0) + Number(health.summary.stale || 0) + Number(health.summary.missing || 0);
            dataObj.runtime.metrics = [
                {
                    label: "Component coverage",
                    value: `${Number(health.coverage_percent || 0).toFixed(2)}%`,
                    delta: `${health.reporting_components || 0} / ${health.expected_components || 0} expected`,
                    tone: health.status === "healthy" ? "positive" : "warning"
                },
                {
                    label: "Unhealthy components",
                    value: String(unhealthy),
                    delta: `status ${health.status || "unknown"}`,
                    tone: unhealthy > 0 ? "negative" : "positive"
                },
                {
                    label: "Stale components",
                    value: String(health.summary.stale || 0),
                    delta: String(health.summary.missing || 0) + " missing",
                    tone: Number(health.summary.stale || 0) > 0 ? "warning" : "positive"
                },
                {
                    label: "Error components",
                    value: String(health.summary.error || 0),
                    delta: "runtime health board",
                    tone: Number(health.summary.error || 0) > 0 ? "negative" : "positive"
                }
            ];
        }

        if (components && Array.isArray(components.components)) {
            dataObj.runtime.components = components.components.map((item) => ({
                name: item.component_name,
                kind: item.component_kind,
                health: item.health,
                status: item.status,
                lastSeen: formatDate(item.last_heartbeat_at),
                copy: `host ${item.host || "n/a"} · heartbeat ${item.heartbeat_count || 0}`
            }));
        }

        if (alerts && Array.isArray(alerts.alerts)) {
            dataObj.runtime.alerts = alerts.alerts.map((item) => ({
                title: `${item.severity.toUpperCase()} · ${item.component}`,
                copy: item.summary,
                tone: item.severity === "critical" ? "danger" : item.severity === "warning" ? "warning" : "success",
                meta: [
                    item.observed_value !== null && item.observed_value !== undefined
                        ? `observed=${item.observed_value}`
                        : "observed=n/a",
                    item.threshold !== null && item.threshold !== undefined
                        ? `threshold=${item.threshold}`
                        : "threshold=n/a"
                ]
            }));
        }

        if (audit && Array.isArray(audit.data)) {
            dataObj.runtime.audit = audit.data.map((item) => ({
                timestamp: formatDate(item.occurred_at),
                entity: item.entity || "unknown",
                action: item.action || "unknown",
                source: item.source || "unknown",
                operator: item.headers && item.headers.operator_id ? item.headers.operator_id : "n/a",
                requestId: item.request_id || "n/a"
            }));
        }

        if (acceptance && acceptance.status) {
            dataObj.runtime.acceptance = {
                status: acceptance.status.acceptance_ready ? "ready" : "needs-attention",
                updatedAt: formatDate(acceptance.openapi_snapshots && acceptance.openapi_snapshots[0] ? acceptance.openapi_snapshots[0].updated_at : null),
                items: [
                    {
                        label: "QA workflow",
                        state: acceptance.status.qa_workflow_ready ? "done" : "attention"
                    },
                    {
                        label: "Public OpenAPI snapshot",
                        state: acceptance.status.public_openapi_snapshot_ready ? "done" : "attention"
                    },
                    {
                        label: "Admin OpenAPI snapshot",
                        state: acceptance.status.admin_openapi_snapshot_ready ? "done" : "attention"
                    },
                    {
                        label: "Reviewed load reports",
                        state: Number(acceptance.status.reviewed_load_reports || 0) > 0 ? "done" : "attention"
                    },
                    {
                        label: "Reviewed cutover reports",
                        state: Number(acceptance.status.reviewed_cutover_reports || 0) > 0 ? "done" : "attention"
                    }
                ]
            };
        }
    }

    async function loadExperiments(dataObj) {
        const [runs, rankings, analyses] = await Promise.all([
            requestSafe("/v1/admin/backtests/runs?limit=25"),
            requestSafe("/v1/admin/backtests/rankings/latest?limit=10"),
            requestSafe("/v1/admin/tradingagents/analyses?limit=20")
        ]);

        if (!dataObj.experiments) return;

        if (runs && Array.isArray(runs.data)) {
            dataObj.experiments.backtests = runs.data.map((item) => ({
                id: item.id,
                strategy: item.strategy_name,
                timeframe: item.timeframe,
                symbol: item.symbol || "-",
                window: `${item.window_days || 0}d`,
                status: item.status,
                score: item.metrics && item.metrics.score !== undefined ? Number(item.metrics.score).toFixed(2) : "-",
                updatedAt: formatDate(item.completed_at || item.started_at)
            }));
        }

        if (rankings && Array.isArray(rankings.data)) {
            dataObj.experiments.rankings = rankings.data.map((item) => ({
                rank: item.rank,
                strategy: item.strategy_name,
                timeframe: item.timeframe,
                score: Number(item.score || 0).toFixed(2),
                degradation: Number(item.degradation || 0).toFixed(2),
                symbols: item.symbols_covered || 0
            }));
        }

        if (analyses && Array.isArray(analyses.data)) {
            dataObj.experiments.analyses = analyses.data.map((item) => ({
                requestId: item.request_id,
                symbol: item.ticker,
                status: item.tradingagents_status,
                trigger: item.trigger_type,
                finalAction: item.final_action || "n/a",
                latency: item.completed_at && item.submitted_at
                    ? `${Math.max(Math.round((new Date(item.completed_at).getTime() - new Date(item.submitted_at).getTime()) / 1000), 0)}s`
                    : "n/a"
            }));
        }

        dataObj.experiments.metrics = [
            {
                label: "Backtest runs",
                value: String(runs && runs.total ? runs.total : dataObj.experiments.backtests.length),
                delta: "live total",
                tone: "brand"
            },
            {
                label: "Latest rankings",
                value: String(rankings && rankings.data ? rankings.data.length : 0),
                delta: rankings && rankings.as_of_date ? formatDate(rankings.as_of_date) : "no rankings",
                tone: "positive"
            },
            {
                label: "Open analyses",
                value: String(
                    (analyses && analyses.data ? analyses.data : []).filter((item) =>
                        ["pending", "submitted", "running"].includes(String(item.tradingagents_status || ""))
                    ).length
                ),
                delta: "tradingagents queue",
                tone: "warning"
            },
            {
                label: "Completed analyses",
                value: String(
                    (analyses && analyses.data ? analyses.data : []).filter(
                        (item) => String(item.tradingagents_status || "") === "completed"
                    ).length
                ),
                delta: "terminal states",
                tone: "positive"
            }
        ];
    }

    async function loadDashboard(dataObj) {
        const [operators, pendingReceipts, health, rankings, signalSummary, tradingStats, audit, alerts] = await Promise.all([
            requestSafe("/v1/admin/operators?limit=1"),
            requestSafe("/v1/admin/tasks/receipts?follow_up_status=pending&limit=1"),
            requestSafe("/v1/admin/runtime/health"),
            requestSafe("/v1/admin/backtests/rankings/latest?limit=1"),
            requestSafe("/v1/admin/signal-stats/summary?window_hours=24"),
            requestSafe("/v1/admin/tradingagents/stats"),
            requestSafe("/v1/admin/audit?limit=4"),
            requestSafe("/v1/admin/runtime/alerts")
        ]);

        if (!dataObj.dashboard || !Array.isArray(dataObj.dashboard.metrics)) return;

        const staleComponents = health && health.summary
            ? Number(health.summary.error || 0) + Number(health.summary.stale || 0) + Number(health.summary.missing || 0)
            : 0;
        const rankingAge = rankings && rankings.as_of_date
            ? Math.max((Date.now() - new Date(rankings.as_of_date).getTime()) / 3600000, 0)
            : null;

        dataObj.dashboard.metrics = [
            {
                label: "Active operators",
                value: String(operators && operators.total ? operators.total : 0),
                delta: "live operator directory",
                tone: "positive",
                icon: "shield-check"
            },
            {
                label: "Pending follow-ups",
                value: String(pendingReceipts && pendingReceipts.total ? pendingReceipts.total : 0),
                delta: "manual receipt follow-up",
                tone: "warning",
                icon: "mail-warning"
            },
            {
                label: "Unhealthy components",
                value: String(staleComponents),
                delta: health ? `runtime ${health.status}` : "runtime unavailable",
                tone: staleComponents > 0 ? "negative" : "positive",
                icon: "triangle-alert"
            },
            {
                label: "Stale rankings",
                value: rankingAge === null ? "n/a" : `${rankingAge.toFixed(1)}h`,
                delta: rankings && rankings.as_of_date ? formatDate(rankings.as_of_date) : "no ranking snapshot",
                tone: rankingAge !== null && rankingAge > 4 ? "warning" : "brand",
                icon: "flask-conical"
            },
            {
                label: "Signal throughput",
                value: `${signalSummary && signalSummary.total_signals ? signalSummary.total_signals : 0}/24h`,
                delta: signalSummary ? `${signalSummary.active_signals || 0} active` : "no signal summary",
                tone: "positive",
                icon: "radio"
            },
            {
                label: "AI backlog",
                value: String(tradingStats && tradingStats.open_total ? tradingStats.open_total : 0),
                delta: tradingStats ? `${tradingStats.completed_total || 0} completed` : "stats unavailable",
                tone: "warning",
                icon: "bot"
            }
        ];

        if (audit && Array.isArray(audit.data)) {
            dataObj.dashboard.timeline = audit.data.map((item) => ({
                time: formatDate(item.occurred_at),
                title: `${item.entity || "entity"} ${item.action || "action"}`,
                copy: item.source || "admin-api",
                tags: [item.topic || "ops.audit", item.request_id || "request-id:n/a"]
            }));
        }

        if (alerts && Array.isArray(alerts.alerts)) {
            dataObj.dashboard.attention = alerts.alerts.slice(0, 3).map((item) => ({
                title: `${item.severity.toUpperCase()} · ${item.component}`,
                copy: item.summary,
                tone: item.severity === "critical" ? "danger" : item.severity === "warning" ? "warning" : "success",
                meta: [
                    item.observed_value !== null && item.observed_value !== undefined
                        ? `observed=${item.observed_value}`
                        : "observed=n/a",
                    item.threshold !== null && item.threshold !== undefined
                        ? `threshold=${item.threshold}`
                        : "threshold=n/a"
                ]
            }));
        }
    }

    async function fetchPageData(page, dataObj) {
        if (!page || !dataObj) return;
        const pageName = String(page);
        if (pageName === "dashboard") await loadDashboard(dataObj);
        if (pageName === "people") await loadPeople(dataObj);
        if (pageName === "communications") await loadCommunications(dataObj);
        if (pageName === "intelligence") await loadIntelligence(dataObj);
        if (pageName === "runtime") await loadRuntime(dataObj);
        if (pageName === "experiments") await loadExperiments(dataObj);
    }

    function endpointFamily(path) {
        const parts = String(path || "")
            .split("/")
            .filter(Boolean);
        if (parts.length >= 3) {
            return parts[2];
        }
        return parts[0] || "misc";
    }

    function endpointKey(spec) {
        return `${spec.method} ${spec.path}`;
    }

    function methodChipClass(method) {
        const normalized = String(method || "").toUpperCase();
        if (normalized === "GET") return "chip chip--brand";
        if (normalized === "POST") return "chip chip--success";
        if (normalized === "PUT" || normalized === "PATCH") return "chip chip--warning";
        return "chip chip--danger";
    }

    function mountApiConsole() {
        const root = document.getElementById("page-content");
        if (!root || document.getElementById("admin-api-console")) return;
        
        // Only mount on the dedicated API page
        if (document.body.getAttribute("data-page") !== "api") return;

        const endpointOptions = ALL_ENDPOINTS
            .slice()
            .sort((left, right) => endpointKey(left).localeCompare(endpointKey(right)));

        const panel = document.createElement("section");
        panel.id = "admin-api-console";
        panel.className = "panel panel--span-12";
        panel.innerHTML = `
            <div class="panel__header">
                <div>
                    <h3 class="panel__title">执行任意管理端接口</h3>
                </div>
                <div class="panel__toolbar">
                    <span class="endpoint-badge">覆盖：${ALL_ENDPOINTS.length} 个端点</span>
                </div>
            </div>
            <div class="form-grid">
                <label class="form-field form-field--full">
                    <span class="form-label">接口筛选</span>
                    <input id="admin-api-console-filter" class="input" type="text" placeholder="搜索方法、路径或能力域（如 users、tasks、runtime）">
                </label>
                <label class="form-field form-field--full">
                    <span class="form-label">接口</span>
                    <select id="admin-api-console-endpoint" class="select"></select>
                </label>
                <label class="form-field">
                    <span class="form-label">路径参数 JSON</span>
                    <textarea id="admin-api-console-path" class="textarea" rows="6">{}</textarea>
                </label>
                <label class="form-field">
                    <span class="form-label">查询参数 JSON</span>
                    <textarea id="admin-api-console-query" class="textarea" rows="6">{}</textarea>
                </label>
                <label class="form-field form-field--full">
                    <span class="form-label">请求体 JSON</span>
                    <textarea id="admin-api-console-body" class="textarea" rows="8">{}</textarea>
                </label>
                <div class="button-row form-field form-field--full">
                    <button id="admin-api-console-run" type="button" class="btn btn--primary">执行接口</button>
                    <button id="admin-api-console-reset" type="button" class="btn btn--secondary">重置模板</button>
                    <span id="admin-api-console-meta" class="endpoint-badge">未选择接口</span>
                </div>
            </div>
            <div id="admin-api-console-result" class="code-block" style="margin-top:1rem;">选择一个接口后点击“执行接口”。</div>
            <div style="margin-top:1rem;">
                <div class="toolbar-split" style="margin-bottom:0.65rem;">
                    <div class="form-label" style="margin:0;">后端能力矩阵（可执行）</div>
                    <span id="admin-api-console-coverage" class="endpoint-badge">-</span>
                </div>
                <div class="table-wrap">
                    <table class="table table--compact">
                        <thead>
                            <tr>
                                <th>能力域</th>
                                <th>方法</th>
                                <th>路径</th>
                                <th>需请求体</th>
                                <th>需操作员</th>
                                <th>快捷</th>
                            </tr>
                        </thead>
                        <tbody id="admin-api-console-matrix-body"></tbody>
                    </table>
                </div>
            </div>
        `;
        root.appendChild(panel);

        const select = document.getElementById("admin-api-console-endpoint");
        const filterNode = document.getElementById("admin-api-console-filter");
        const pathNode = document.getElementById("admin-api-console-path");
        const queryNode = document.getElementById("admin-api-console-query");
        const bodyNode = document.getElementById("admin-api-console-body");
        const metaNode = document.getElementById("admin-api-console-meta");
        const resultNode = document.getElementById("admin-api-console-result");
        const coverageNode = document.getElementById("admin-api-console-coverage");
        const matrixBody = document.getElementById("admin-api-console-matrix-body");

        function currentSpec() {
            const key = String(select.value || "");
            return endpointOptions.find((item) => endpointKey(item) === key) || null;
        }

        function getFilteredEndpoints() {
            const keyword = String(filterNode.value || "").trim().toLowerCase();
            if (!keyword) return endpointOptions;
            return endpointOptions.filter((item) => {
                const haystack = [
                    item.method,
                    item.path,
                    endpointFamily(item.path),
                    item.operatorRequired ? "operator" : "",
                    item.requiresBody ? "body" : "",
                ]
                    .join(" ")
                    .toLowerCase();
                return haystack.includes(keyword);
            });
        }

        function renderEndpointSelect(endpoints) {
            const previous = String(select.value || "");
            select.innerHTML = "";

            endpoints.forEach((item) => {
                const option = document.createElement("option");
                option.value = endpointKey(item);
                option.textContent = endpointKey(item);
                select.appendChild(option);
            });

            if (endpoints.length === 0) {
                select.disabled = true;
                metaNode.textContent = "筛选结果为空";
                return;
            }

            select.disabled = false;
            if (endpoints.some((item) => endpointKey(item) === previous)) {
                select.value = previous;
            } else {
                select.value = endpointKey(endpoints[0]);
            }
        }

        function renderEndpointMatrix(endpoints) {
            const keyword = String(filterNode.value || "").trim();
            const families = [...new Set(endpoints.map((item) => endpointFamily(item.path)))].sort();
            coverageNode.textContent = `已展示 ${endpoints.length}/${endpointOptions.length} 个端点 · 能力域 ${families.length} 个${keyword ? ` · 关键词：${keyword}` : ""}`;

            if (endpoints.length === 0) {
                matrixBody.innerHTML = `
                    <tr>
                        <td colspan="6">
                            <div class="empty-state">当前筛选没有匹配端点，请修改关键词。</div>
                        </td>
                    </tr>
                `;
                return;
            }

            matrixBody.innerHTML = endpoints
                .map(
                    (item) => `
                        <tr>
                            <td><span class="endpoint-badge">${escapeHtml(endpointFamily(item.path))}</span></td>
                            <td><span class="${methodChipClass(item.method)}">${escapeHtml(item.method)}</span></td>
                            <td><span class="mono">${escapeHtml(item.path)}</span></td>
                            <td>${item.requiresBody ? "是" : "否"}</td>
                            <td>${item.operatorRequired ? "是" : "否"}</td>
                            <td>
                                <button
                                    type="button"
                                    class="btn btn--ghost btn--compact"
                                    data-admin-console-select="${escapeHtml(endpointKey(item))}"
                                >
                                    套用
                                </button>
                            </td>
                        </tr>
                    `
                )
                .join("");
        }

        function applyFilterAndRefresh() {
            const filtered = getFilteredEndpoints();
            renderEndpointSelect(filtered);
            renderEndpointMatrix(filtered);
            setTemplates();
        }

        function setEndpointByKey(rawKey) {
            const key = String(rawKey || "").trim();
            if (!key) {
                return false;
            }

            if (!endpointOptions.some((item) => endpointKey(item) === key)) {
                return false;
            }

            const hasOption = Array.from(select.options).some((option) => option.value === key);
            if (select.disabled || !hasOption) {
                filterNode.value = "";
                applyFilterAndRefresh();
            }

            select.value = key;
            if (select.value !== key) {
                return false;
            }
            setTemplates();
            return true;
        }

        function setTemplates() {
            const spec = currentSpec();
            if (!spec) {
                pathNode.value = "{}";
                queryNode.value = "{}";
                bodyNode.value = "{}";
                bodyNode.disabled = true;
                resultNode.textContent = "当前筛选没有可执行端点，请调整筛选条件。";
                return;
            }
            const pathParams = {};
            [...spec.path.matchAll(/\{([^}]+)\}/g)].forEach((match) => {
                pathParams[match[1]] = "";
            });
            pathNode.value = JSON.stringify(pathParams, null, 2);
            queryNode.value = JSON.stringify(spec.queryTemplate || {}, null, 2);
            bodyNode.value = JSON.stringify(spec.bodyTemplate || {}, null, 2);
            bodyNode.disabled = spec.method === "GET" || spec.method === "DELETE";
            metaNode.textContent = spec.operatorRequired
                ? "需要 X-Operator-ID 请求头"
                : "操作员 ID 可选";
            resultNode.textContent = `就绪：${spec.method} ${spec.path}`;
        }

        select.addEventListener("change", setTemplates);
        filterNode.addEventListener("input", applyFilterAndRefresh);

        matrixBody.addEventListener("click", function (event) {
            const button = event.target.closest("[data-admin-console-select]");
            if (!button) return;
            event.preventDefault();
            const key = button.getAttribute("data-admin-console-select") || "";
            if (!setEndpointByKey(key)) {
                return;
            }
            metaNode.textContent = `已套用 ${key}`;
            pathNode.focus();
        });

        document.getElementById("admin-api-console-reset").addEventListener("click", setTemplates);

        document.getElementById("admin-api-console-run").addEventListener("click", async function () {
            const spec = currentSpec();
            const startedAt = performance.now();
            try {
                if (!spec) {
                    throw new Error("当前筛选没有可执行端点，请调整筛选条件");
                }
                const rawPathParams = parseJsonOrEmpty(pathNode.value, "路径参数 JSON");
                const rawQuery = parseJsonOrEmpty(queryNode.value, "查询参数 JSON");
                const rawBody = parseJsonOrEmpty(bodyNode.value, "请求体 JSON");

                let path = spec.path;
                Object.entries(rawPathParams).forEach(([key, value]) => {
                    path = path.replace(`{${key}}`, encodeURIComponent(String(value || "")));
                });
                if (path.includes("{")) {
                    throw new Error("一个或多个路径参数缺失");
                }

                path += buildQueryString(normalizePayload(rawQuery));

                const options = {
                    method: spec.method,
                    operatorRequired: Boolean(spec.operatorRequired)
                };
                if (spec.method !== "GET" && spec.method !== "DELETE") {
                    options.body = JSON.stringify(normalizePayload(rawBody));
                }

                metaNode.textContent = `执行中：${spec.method} ${spec.path}`;
                resultNode.textContent = `${spec.method} ${path} ...`;
                const payload = await api.request(path, options);
                resultNode.innerHTML = `<pre class="code-block">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>`;
                metaNode.textContent = `执行成功 · ${Math.max(Math.round(performance.now() - startedAt), 0)}ms`;
            } catch (error) {
                resultNode.innerHTML = `<pre class="code-block" style="color:#f87171;">${escapeHtml(JSON.stringify({ message: error.message, details: error.payload || null }, null, 2))}</pre>`;
                metaNode.textContent = `执行失败 · ${Math.max(Math.round(performance.now() - startedAt), 0)}ms`;
            }
        });

        api.focusConsole = function (keyword, shouldScroll) {
            filterNode.value = String(keyword || "").trim();
            applyFilterAndRefresh();
            if (shouldScroll) {
                panel.scrollIntoView({ behavior: "smooth", block: "start" });
            }
            if (!select.disabled) {
                select.focus();
            }
        };

        api.selectConsoleEndpoint = function (key, shouldScroll) {
            const applied = setEndpointByKey(key);
            if (shouldScroll) {
                panel.scrollIntoView({ behavior: "smooth", block: "start" });
            }
            if (applied && !select.disabled) {
                select.focus();
            }
            return applied;
        };

        applyFilterAndRefresh();
    }

    function wireActions() {
        if (window.AdminAPI.__actionsWired) return;
        window.AdminAPI.__actionsWired = true;

        document.addEventListener(
            "submit",
            async function (event) {
                const form = event.target.closest(".demo-form");
                if (!form) return;

                if (!api.getToken()) {
                    return;
                }

                const parsed = parseEndpoint(form.getAttribute("data-demo-endpoint") || "");
                if (!parsed) return;

                event.preventDefault();
                event.stopImmediatePropagation();

                const spec = findEndpointSpec(parsed.method, parsed.path);
                const executionSpec = {
                    ...spec,
                    path: parsed.path.includes("{") ? spec.path : parsed.path
                };
                const payload = formToPayload(form);
                const targetId = form.getAttribute("data-demo-target") || "";

                try {
                    await executeSpec(executionSpec, payload, targetId);
                } catch (_error) {
                    // executeSpec already renders errors
                }
            },
            true
        );

        document.addEventListener(
            "click",
            async function (event) {
                const button = event.target.closest("[data-demo-action]");
                if (!button) return;

                if (!api.getToken()) {
                    return;
                }

                const parsed = parseEndpoint(button.getAttribute("data-demo-endpoint") || "");
                if (!parsed) return;

                const spec = findEndpointSpec(parsed.method, parsed.path);
                const executionSpec = {
                    ...spec,
                    path: parsed.path.includes("{") ? spec.path : parsed.path
                };

                if (executionSpec.requiresBody && !executionSpec.bodyTemplate) {
                    pushToast(
                        "需要请求体",
                        `${executionSpec.method} ${executionSpec.path} 需要请求体，请使用页面表单或全量 API 控制台。`
                    );
                    return;
                }

                const shouldProceed = window.confirm(
                    `现在执行 ${executionSpec.method} ${executionSpec.path} 吗？`
                );
                if (!shouldProceed) {
                    return;
                }

                event.preventDefault();
                event.stopImmediatePropagation();

                const payload = normalizePayload(executionSpec.bodyTemplate || {});

                try {
                    await executeSpec(executionSpec, payload, "");
                } catch (_error) {
                    // executeSpec already renders errors via toast
                }
            },
            true
        );
    }

    window.AdminAPI.fetchPageData = fetchPageData;
    window.AdminAPI.wireActions = wireActions;
    window.AdminAPI.endpointCatalog = ALL_ENDPOINTS;

    document.addEventListener("DOMContentLoaded", function () {
        wireActions();
        mountApiConsole();
    });
})();
