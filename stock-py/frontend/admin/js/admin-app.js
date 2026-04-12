(function () {
    const data = window.adminDemoData || {};
    const ADMIN_UI_BUILD = "2026-04-07-r2";
    const adminRoute = (path = "") => path ? `/admin/${path}` : "/admin/";
    const pages = {
        dashboard: {
            title: "Admin control plane",
            eyebrow: "Unified operating view",
            copy: "Map the real admin-api surface into one operator cockpit before wiring live tokens and fetch calls. This frontend shows every major workflow area already present in the backend.",
            ctas: [
                { label: "Open people desk", href: adminRoute("people"), icon: "users" },
                { label: "Review active alerts", href: adminRoute("runtime"), icon: "shield-alert" },
                { label: "Queue a campaign", href: adminRoute("communications"), icon: "send" }
            ]
        },
        people: {
            title: "People, plans, and scopes",
            eyebrow: "Users + operators",
            copy: "Expose the actual `/v1/admin/users` and `/v1/admin/operators` workflows as edit-ready front-end modules, including bulk updates and scope-aware operator management.",
            ctas: [
                { label: "Bulk update users", endpoint: "POST /v1/admin/users/bulk", icon: "users" },
                { label: "Upsert operator", endpoint: "PUT /v1/admin/operators/{user_id}", icon: "shield-check" }
            ]
        },
        communications: {
            title: "Campaigns, receipts, and trade tasks",
            eyebrow: "Delivery operations",
            copy: "Surface the manual distribution and task-center endpoints so operations staff can send campaigns, work failed receipts, recover outbox jobs, and handle manual trade follow-ups.",
            ctas: [
                { label: "Manual message", endpoint: "POST /v1/admin/distribution/manual-message", icon: "megaphone" },
                { label: "Escalate receipts", endpoint: "POST /v1/admin/tasks/receipts/escalate-overdue", icon: "siren" }
            ]
        },
        intelligence: {
            title: "Signal intelligence and data quality",
            eyebrow: "Analytics + scanner",
            copy: "Blend analytics, signal stats, scanner runs, anomalies, and AI agent metrics into a single operational analysis workspace.",
            ctas: [
                { label: "Open strategy health", endpoint: "GET /v1/admin/analytics/strategy-health", icon: "line-chart" },
                { label: "Inspect scanner run", endpoint: "GET /v1/admin/scanner/runs/{run_id}", icon: "scan-search" }
            ]
        },
        runtime: {
            title: "Runtime, audit, and readiness",
            eyebrow: "Observability + compliance",
            copy: "Expose component health, runtime stats, alerts, audit logs, and acceptance evidence in a layout tuned for operators who need to decide fast.",
            ctas: [
                { label: "Fetch runtime health", endpoint: "GET /v1/admin/runtime/health", icon: "heart-pulse" },
                { label: "Export acceptance report", endpoint: "GET /v1/admin/acceptance/report", icon: "clipboard-check" }
            ]
        },
        experiments: {
            title: "Backtests and AI agent recovery",
            eyebrow: "Experimentation control",
            copy: "Give the backtest and trading-agent surfaces real front-end modules now so delayed analyses and stale rankings are visible before live API integration lands.",
            ctas: [
                { label: "Trigger refresh", endpoint: "POST /v1/admin/backtests/runs", icon: "flask-conical" },
                { label: "Reconcile delayed", endpoint: "POST /v1/admin/tradingagents/reconcile-delayed", icon: "bot" }
            ]
        },
        api: {
            title: "全量 API 控制台",
            eyebrow: "API Explorer",
            copy: "执行任意管理端接口",
            ctas: []
        }
    };

    const navigation = [
        {
            label: "Command",
            items: [
                { page: "dashboard", title: "Overview", href: adminRoute(), icon: "layout-dashboard" },
                { page: "people", title: "People desk", href: adminRoute("people"), icon: "users" },
                { page: "communications", title: "Delivery ops", href: adminRoute("communications"), icon: "send" },
                { page: "intelligence", title: "Intelligence", href: adminRoute("intelligence"), icon: "activity" },
                { page: "experiments", title: "Experiments", href: adminRoute("experiments"), icon: "flask-conical" },
                { page: "runtime", title: "Runtime & audit", href: adminRoute("runtime"), icon: "shield-alert" },
                { page: "api", title: "API Console", href: adminRoute("api"), icon: "terminal" }
            ]
        }
    ];

    const state = {
        page: document.body.getAttribute("data-page") || "dashboard",
        subnavObserver: null
    };

    function icon(name) {
        return `<i data-lucide="${name}" aria-hidden="true"></i>`;
    }

    function clsTone(tone) {
        if (tone === "positive") return "tone-positive";
        if (tone === "warning") return "tone-warning";
        if (tone === "negative") return "tone-negative";
        return "tone-brand";
    }

    function chipClass(value) {
        const normalized = String(value || "").toLowerCase();
        if (["healthy", "done", "active", "completed", "success", "delivered"].includes(normalized)) {
            return "chip chip--success";
        }
        if (["warning", "attention", "retrying", "pending_confirmation", "delayed", "claimed"].includes(normalized)) {
            return "chip chip--warning";
        }
        if (["danger", "error", "failed", "suspended", "overdue", "inactive", "stale"].includes(normalized)) {
            return "chip chip--danger";
        }
        return "chip chip--brand";
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function adminEndpointCatalog() {
        if (!window.AdminAPI || !Array.isArray(window.AdminAPI.endpointCatalog)) {
            return [];
        }
        return window.AdminAPI.endpointCatalog.filter(
            (item) => item && typeof item.method === "string" && typeof item.path === "string"
        );
    }

    function adminEndpointFamily(path) {
        const parts = String(path || "")
            .split("/")
            .filter(Boolean);
        if (parts.length >= 3) {
            return parts[2];
        }
        return parts[0] || "misc";
    }

    function buildAdminCapabilityDomains() {
        const grouped = new Map();
        adminEndpointCatalog().forEach((item) => {
            const family = adminEndpointFamily(item.path);
            const key = String(family || "misc").toLowerCase();
            if (!grouped.has(key)) {
                grouped.set(key, {
                    family,
                    total: 0,
                    writeCount: 0,
                    methods: { GET: 0, POST: 0, PUT: 0, PATCH: 0, DELETE: 0 }
                });
            }
            const entry = grouped.get(key);
            const method = String(item.method || "GET").toUpperCase();
            entry.total += 1;
            if (Object.prototype.hasOwnProperty.call(entry.methods, method)) {
                entry.methods[method] += 1;
            }
            if (method !== "GET") {
                entry.writeCount += 1;
            }
        });
        return [...grouped.values()].sort((left, right) => left.family.localeCompare(right.family));
    }

    function renderMethodMix(methods) {
        return ["GET", "POST", "PUT", "PATCH", "DELETE"]
            .filter((method) => Number(methods[method] || 0) > 0)
            .map((method) => `${method} ${methods[method]}`)
            .join(" | ");
    }

    function renderAdminCapabilityCoverage() {
        const rows = buildAdminCapabilityDomains();
        if (rows.length === 0) {
            return `<div class="empty-state">未检测到后端端点目录。请稍后刷新页面重试。</div>`;
        }

        const totalEndpoints = rows.reduce((sum, row) => sum + row.total, 0);

        return `
            <div class="toolbar-split" style="margin-top:1rem;">
                <div class="helper-text">后端已实现 <strong>${totalEndpoints}</strong> 个管理端接口，覆盖 <strong>${rows.length}</strong> 个能力域。</div>
                <button type="button" class="btn btn--secondary btn--compact" data-open-api-console="all">打开全量 API 控制台</button>
            </div>
            <div class="table-wrap" style="margin-top:0.75rem;">
                <table class="table table--compact">
                    <thead>
                        <tr>
                            <th>能力域</th>
                            <th>方法分布</th>
                            <th>写操作</th>
                            <th>快捷入口</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows.map((row) => `
                            <tr>
                                <td><span class="endpoint-badge">${escapeHtml(row.family)}</span></td>
                                <td><span class="mono">${escapeHtml(renderMethodMix(row.methods))}</span></td>
                                <td>${escapeHtml(row.writeCount)}/${escapeHtml(row.total)}</td>
                                <td>
                                    <button type="button" class="btn btn--ghost btn--compact" data-admin-console-filter="${escapeHtml(row.family)}">筛选到该域</button>
                                </td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        `;
    }

    function renderSidebar() {
        const container = document.getElementById("sidebar");
        if (!container) return;
        container.className = "sidebar";
        container.innerHTML = `
            <div class="sidebar__brand">
                <div class="sidebar__brand-mark">${icon("shield-check")}</div>
                <div>
                    <div class="sidebar__eyebrow">Stock-Py</div>
                    <div class="sidebar__title">Admin frontend</div>
                </div>
            </div>
            ${navigation.map((group) => `
                <section>
                    <div class="nav-list">
                        ${group.items.map((item) => {
                            const isActive = item.page === state.page;
                            return `
                            <div class="${isActive ? 'nav-item-container is-active' : 'nav-item-container'}">
                                <a class="nav-link ${isActive ? "is-active" : ""}" href="${item.href}">
                                    <span>${icon(item.icon)}</span>
                                    <span class="nav-link__label">${escapeHtml(item.title)}</span>
                                </a>
                                ${isActive ? `<div id="sidebar-submenu-host" class="sidebar-submenu"><div class="sidebar-submenu__empty">正在加载二级菜单...</div></div>` : ""}
                            </div>
                            `;
                        }).join("")}
                    </div>
                </section>
            `).join("")}
            <div class="sidebar__footer">
                <div class="sidebar__footer-top">
                    <div>
                        <div class="sidebar__footer-name">${escapeHtml(data.operator?.name || "Active operator")}</div>
                        <div class="sidebar__footer-copy">${escapeHtml(data.operator?.role || "admin")}</div>
                    </div>
                    <span class="badge">${escapeHtml(data.operator?.shift || "operations")}</span>
                </div>
                <div class="sidebar__footer-copy">Scopes: ${(data.operator?.scopes || []).map((scope) => escapeHtml(scope)).join(", ")}</div>
                <div class="sidebar__footer-copy sidebar__footer-copy--build">UI版本 ${escapeHtml(ADMIN_UI_BUILD)}</div>
            </div>
        `;
    }

    function renderMobileNav() {
        const container = document.getElementById("mobile-nav");
        if (!container) return;
        container.className = "mobile-nav";
        container.innerHTML = navigation.flatMap((group) => group.items).map((item) => `
            <a class="mobile-nav__link ${item.page === state.page ? "is-active" : ""}" href="${item.href}">
                <span>${icon(item.icon)}</span>
                <span>${escapeHtml(item.title)}</span>
            </a>
        `).join("");
    }

    function renderTopbar() {
        const container = document.getElementById("topbar");
        const page = pages[state.page];
        if (!container || !page) return;
        container.className = "topbar";
        container.innerHTML = `
            <div class="topbar__cluster">
                <div>
                    <h2>${escapeHtml(page.title)}</h2>
                    <div class="helper-text">当前是稳定版管理端，可直接切到平台端或订阅端查看联动体验。</div>
                </div>
            </div>
            <div class="topbar__search">
                ${icon("search")}
                <input id="topbar-endpoint-search" type="text" placeholder="输入能力域、路由或方法，快速筛选 API 控制台">
                <button id="topbar-endpoint-search-btn" class="btn btn--ghost btn--compact" type="button">筛选 API</button>
            </div>
            <div class="topbar__actions">
                <a class="btn btn--primary btn--compact" href="/platform/">平台端</a>
                <a class="btn btn--ghost btn--compact" href="/app/">订阅端</a>
            </div>
        `;
    }

    function renderHero() {
        const page = pages[state.page];
        return `
            <section class="hero">
                <h1 class="hero__title">${escapeHtml(page.title)}</h1>
                <div class="hero__meta">
                    ${page.ctas.map((cta) => {
                        const attrs = cta.href
                            ? `href="${cta.href}"`
                            : `href="#" data-demo-action="${escapeHtml(cta.label)}" data-demo-endpoint="${escapeHtml(cta.endpoint || "")}"`;
                        return `<a class="btn btn--primary" ${attrs}>${icon(cta.icon)} <span>${escapeHtml(cta.label)}</span></a>`;
                    }).join("")}
                </div>
            </section>
        `;
    }

    function metricCards(items) {
        return `
            <section class="metric-grid">
                ${items.map((item) => `
                    <article class="metric-card">
                        <div class="metric-card__header">
                            <div>
                                <div class="metric-card__label">${escapeHtml(item.label)}</div>
                                <div class="metric-card__value">${escapeHtml(item.value)}</div>
                            </div>
                            <span class="badge">${icon(item.icon || "sparkles")}</span>
                        </div>
                        <div class="metric-card__delta ${clsTone(item.tone)}">${escapeHtml(item.delta)}</div>
                    </article>
                `).join("")}
            </section>
        `;
    }

    function panelHeader(eyebrow, title, copy, toolbarHtml) {
        return `
            <div class="panel__header">
                <div>
                    <h3 class="panel__title">${escapeHtml(title)}</h3>
                </div>
                ${toolbarHtml ? `<div class="panel__toolbar">${toolbarHtml}</div>` : ""}
            </div>
        `;
    }

    function renderRouteCards(items) {
        return items.map((item) => `
            <a class="route-card" href="${item.href}">
                <div class="route-card__top">
                    <div>
                        <strong>${escapeHtml(item.title)}</strong>
                    </div>
                    <span class="chip chip--brand">${escapeHtml(item.tag)}</span>
                </div>
                <div class="alert-item__meta">
                    <span class="endpoint-badge">${escapeHtml(item.endpoint)}</span>
                </div>
            </a>
        `).join("");
    }

    function renderAlerts(items) {
        return items.map((item) => `
            <article class="alert-item">
                <span class="alert-item__marker alert-item__marker--${item.tone === "danger" ? "danger" : item.tone === "warning" ? "warning" : "success"}"></span>
                <div>
                    <div class="alert-item__title">${escapeHtml(item.title)}</div>
                    <div class="alert-item__copy">${escapeHtml(item.copy)}</div>
                    <div class="alert-item__meta">${(item.meta || []).map((meta) => `<span class="chip">${escapeHtml(meta)}</span>`).join("")}</div>
                </div>
            </article>
        `).join("");
    }

    function renderTimeline(items) {
        return items.map((item) => `
            <article class="timeline__item">
                <div class="timeline__top">
                    <strong>${escapeHtml(item.title)}</strong>
                    <span class="chip">${escapeHtml(item.time)}</span>
                </div>
                <div class="timeline__copy">${escapeHtml(item.copy)}</div>
                <div class="alert-item__meta">${(item.tags || []).map((tag) => `<span class="endpoint-badge">${escapeHtml(tag)}</span>`).join("")}</div>
            </article>
        `).join("");
    }

    function renderForm(fields) {
        return fields.map((field) => {
            if (field.type === "checkboxes") {
                return `
                    <div class="form-field form-field--full">
                        <div class="form-label">${escapeHtml(field.label)}</div>
                        <div class="check-row">
                            ${field.options.map((option) => `
                                <label class="check-pill">
                                    <input type="checkbox" name="${field.name}" value="${escapeHtml(option.value)}" ${option.checked ? "checked" : ""}>
                                    <span>${escapeHtml(option.label)}</span>
                                </label>
                            `).join("")}
                        </div>
                    </div>
                `;
            }
            if (field.type === "textarea") {
                return `
                    <label class="form-field ${field.full ? "form-field--full" : ""}">
                        <span class="form-label">${escapeHtml(field.label)}</span>
                        <textarea class="textarea" name="${field.name}" ${field.rows ? `rows="${field.rows}"` : ""}>${escapeHtml(field.value || "")}</textarea>
                    </label>
                `;
            }
            if (field.type === "select") {
                return `
                    <label class="form-field ${field.full ? "form-field--full" : ""}">
                        <span class="form-label">${escapeHtml(field.label)}</span>
                        <select class="select" name="${field.name}">
                            ${field.options.map((option) => `<option value="${escapeHtml(option.value)}" ${option.value === field.value ? "selected" : ""}>${escapeHtml(option.label)}</option>`).join("")}
                        </select>
                    </label>
                `;
            }
            return `
                <label class="form-field ${field.full ? "form-field--full" : ""}">
                    <span class="form-label">${escapeHtml(field.label)}</span>
                    <input class="input" type="${field.type || "text"}" name="${field.name}" value="${escapeHtml(field.value || "")}" ${field.placeholder ? `placeholder="${escapeHtml(field.placeholder)}"` : ""}>
                </label>
            `;
        }).join("");
    }

    function renderCodeBlock(payload) {
        return `<pre class="code-block">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>`;
    }

    function slugifyToken(value) {
        return String(value || "")
            .toLowerCase()
            .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-")
            .replace(/^-+|-+$/g, "")
            .slice(0, 42);
    }

    function inferModuleFunction(panel) {
        const title = String(panel.querySelector(".panel__title")?.textContent || "").trim();
        const endpointText = [...panel.querySelectorAll(".endpoint-badge")]
            .map((node) => String(node.textContent || ""))
            .join(" ")
            .toUpperCase();

        const hasWriteEndpoint = /(POST|PUT|PATCH|DELETE)/.test(endpointText);
        const hasReadEndpoint = /GET/.test(endpointText);
        const writeHint = /(action|payload|composer|builder|refresh|reconcile|workflow|queue|mutation|launch|trigger|triage)/i.test(title);
        const monitorHint = /(health|overview|runtime|audit|stats|log|board|ranking|observability|intelligence|anomal|report)/i.test(title);

        if (hasWriteEndpoint && hasReadEndpoint) return "读写协同";
        if (hasWriteEndpoint || writeHint) return "执行操作";
        if (hasReadEndpoint || monitorHint) return "监控查询";
        return "综合概览";
    }

    function collectPageModules(root) {
        const panels = [...root.querySelectorAll(".layout-grid .panel")];
        return panels
            .map((panel, index) => {
                const titleNode = panel.querySelector(".panel__title");
                const title = String(titleNode?.textContent || "").trim();
                if (!title) return null;

                const functionType = inferModuleFunction(panel);
                const id =
                    panel.id ||
                    `module-${state.page}-${slugifyToken(title) || "section"}-${index + 1}`;

                panel.id = id;
                panel.dataset.moduleFunction = functionType;

                return {
                    id,
                    title,
                    functionType,
                };
            })
            .filter(Boolean);
    }

    function buildSubnavMarkup(modules) {
        if (!modules || modules.length === 0) return "";
        return `
            <div class="sidebar-submenu__items">
                ${modules
                    .map(
                        (item) => `
                            <button type="button" class="sidebar-submenu__item" data-module-target="${escapeHtml(item.id)}">
                                ${escapeHtml(item.title)}
                            </button>
                        `
                    )
                    .join("")}
            </div>
        `;
    }

    function setSubnavActive(targetId) {
        const id = String(targetId || "").trim();
        document.querySelectorAll("#sidebar-submenu-host .sidebar-submenu__item").forEach((button) => {
            const buttonTarget = button.getAttribute("data-module-target") || "";
            button.classList.toggle("is-active", id !== "" && buttonTarget === id);
        });
    }

    function mountSecondaryMenu(root) {
        if (state.subnavObserver) {
            state.subnavObserver.disconnect();
            state.subnavObserver = null;
        }

        const host = document.getElementById("sidebar-submenu-host");
        if (!host) {
            return;
        }

        const modules = collectPageModules(root);
        if (modules.length < 2) {
            host.innerHTML = `<div class="sidebar-submenu__empty">当前页面模块较少，无需二级菜单。</div>`;
            return;
        }

        host.innerHTML = buildSubnavMarkup(modules);

        const firstTarget = modules[0]?.id;
        if (firstTarget) {
            setSubnavActive(firstTarget);
        }

        const targets = modules
            .map((item) => document.getElementById(item.id))
            .filter(Boolean);
        if (targets.length === 0) {
            return;
        }

        const observer = new IntersectionObserver(
            (entries) => {
                const visible = entries
                    .filter((entry) => entry.isIntersecting)
                    .sort((left, right) => right.intersectionRatio - left.intersectionRatio);
                if (visible[0] && visible[0].target && visible[0].target.id) {
                    setSubnavActive(visible[0].target.id);
                }
            },
            {
                rootMargin: "-34% 0px -56% 0px",
                threshold: [0.05, 0.2, 0.4],
            }
        );

        targets.forEach((node) => observer.observe(node));
        state.subnavObserver = observer;
    }

    function renderDashboard() {
        const source = data.dashboard;
        const endpointCount = adminEndpointCatalog().length;
        return `
            ${metricCards(source.metrics)}
            <section class="layout-grid">
                <article class="panel panel--span-7">
                    ${panelHeader(
                        "Route coverage",
                        "Backend capability matrix",
                        "Each card maps to a real route family already present in apps/admin_api/routers.",
                        `<span class="endpoint-badge">目录 ${endpointCount} 条路由</span>`
                    )}
                    <div class="route-grid">${renderRouteCards(source.routes)}</div>
                    ${renderAdminCapabilityCoverage()}
                </article>
                <article class="panel panel--span-5">
                    ${panelHeader("Risk board", "Where operators need to look first", "Condensed view of the routes and states most likely to require human intervention before market sessions.")}
                    <div class="alert-list">${renderAlerts(source.attention)}</div>
                </article>
                <article class="panel panel--span-7">
                    ${panelHeader("Activity timeline", "What changed across the admin surface", "Use this as the backbone for a future live feed of audit, distribution, and runtime state changes.", `<span class="endpoint-badge">/v1/admin/audit</span>`) }
                    <div class="timeline">${renderTimeline(source.timeline)}</div>
                </article>
                <article class="panel panel--span-5">
                    ${panelHeader("Quick launch", "Action studio", "These launchers correspond to mutation endpoints. Right now they show request intent and front-end readiness.")}
                    <div class="card-list">
                        ${source.quickActions.map((item) => `
                            <article class="command-card">
                                <div class="command-card__top">
                                    <strong>${escapeHtml(item.title)}</strong>
                                    <span class="endpoint-badge">${escapeHtml(item.endpoint)}</span>
                                </div>
                                <div class="command-card__copy">${escapeHtml(item.description)}</div>
                                <div class="button-row" style="margin-top:0.9rem;">
                                    <button class="btn btn--primary" data-demo-action="${escapeHtml(item.title)}" data-demo-endpoint="${escapeHtml(item.endpoint)}">Preview action</button>
                                </div>
                            </article>
                        `).join("")}
                    </div>
                </article>
            </section>
        `;
    }

    function renderPeople() {
        const source = data.people;
        return `
            ${metricCards(source.metrics.map((item) => ({ ...item, icon: "users" })))}
            <section class="layout-grid">
                <article class="panel panel--span-8">
                    ${panelHeader("Users", "Subscriber command desk", "Expose the `/v1/admin/users` read + write surfaces with filters, bulk actions, and enough context to triage plan or activation changes.", `<span class="endpoint-badge">GET /v1/admin/users</span><span class="endpoint-badge">POST /v1/admin/users/bulk</span>`) }
                    <div class="table-wrap">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>User</th>
                                    <th>Plan</th>
                                    <th>Status</th>
                                    <th>Capital</th>
                                    <th>Locale</th>
                                    <th>Last login</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${source.users.map((user) => `
                                    <tr>
                                        <td>
                                            <div class="table__primary">#${escapeHtml(user.id)} ${escapeHtml(user.name)}</div>
                                            <div class="table__secondary">${escapeHtml(user.email)}<br>${escapeHtml(user.subscription)}</div>
                                        </td>
                                        <td><span class="chip chip--brand">${escapeHtml(user.plan)}</span></td>
                                        <td><span class="${chipClass(user.status)}">${escapeHtml(user.status)}</span></td>
                                        <td>${escapeHtml(user.capital)} ${escapeHtml(user.currency)}</td>
                                        <td>${escapeHtml(user.locale)}</td>
                                        <td>${escapeHtml(user.lastLogin)}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                </article>
                <article class="panel panel--span-4">
                    ${panelHeader("Bulk mutation", "Prepare user update payload", "This form mirrors the payload shape for bulk plan or activation changes. It stays front-end only for now.")}
                    <form class="form-grid demo-form" data-demo-endpoint="POST /v1/admin/users/bulk" data-demo-target="people-bulk-preview">
                        ${renderForm([
                            { label: "User IDs", name: "user_ids", full: true, value: source.bulkPayload.user_ids.join(", ") },
                            { label: "Plan", name: "plan", value: source.bulkPayload.plan },
                            { label: "Set active", name: "is_active", type: "select", value: String(source.bulkPayload.is_active), options: [{ label: "true", value: "true" }, { label: "false", value: "false" }] }
                        ])}
                        <div class="button-row form-field form-field--full">
                            <button class="btn btn--primary" type="submit">Preview payload</button>
                        </div>
                    </form>
                    <div id="people-bulk-preview">${renderCodeBlock(source.bulkPayload)}</div>
                </article>
                <article class="panel panel--span-7">
                    ${panelHeader("Operators", "Access scope matrix", "This maps directly to `/v1/admin/operators`, including role and scopes needed by operator-protected workflows.", `<span class="endpoint-badge">GET /v1/admin/operators</span><span class="endpoint-badge">PUT /v1/admin/operators/{user_id}</span>`) }
                    <div class="table-wrap">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Operator</th>
                                    <th>Role</th>
                                    <th>Scopes</th>
                                    <th>Active</th>
                                    <th>Last action</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${source.operators.map((operator) => `
                                    <tr>
                                        <td>
                                            <div class="table__primary">#${escapeHtml(operator.userId)} ${escapeHtml(operator.name)}</div>
                                            <div class="table__secondary">${escapeHtml(operator.email)}</div>
                                        </td>
                                        <td><span class="chip chip--brand">${escapeHtml(operator.role)}</span></td>
                                        <td>${operator.scopes.map((scope) => `<span class="chip">${escapeHtml(scope)}</span>`).join(" ")}</td>
                                        <td><span class="${chipClass(operator.active ? "active" : "inactive")}">${operator.active ? "active" : "inactive"}</span></td>
                                        <td>${escapeHtml(operator.lastAction)}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                </article>
                <article class="panel panel--span-5">
                    ${panelHeader("Operator payload", "Scope-aware edit form", "Front-end shape for upserting operator role, scopes, and activation state. Also useful for testing token + X-Operator-ID flows.")}
                    <form class="form-grid demo-form" data-demo-endpoint="PUT /v1/admin/operators/{user_id}" data-demo-target="people-operator-preview">
                        ${renderForm([
                            { label: "User ID", name: "user_id", value: "12" },
                            { label: "Role", name: "role", type: "select", value: source.operatorPayload.role, options: [{ label: "viewer", value: "viewer" }, { label: "operator", value: "operator" }, { label: "admin", value: "admin" }] },
                            { label: "Active", name: "is_active", type: "select", value: String(source.operatorPayload.is_active), options: [{ label: "true", value: "true" }, { label: "false", value: "false" }] },
                            { label: "Scopes", name: "scopes", full: true, value: source.operatorPayload.scopes.join(", ") }
                        ])}
                        <div class="button-row form-field form-field--full">
                            <button class="btn btn--primary" type="submit">Preview payload</button>
                            <button class="btn btn--secondary" type="button" data-demo-action="Operator login flow" data-demo-copy="Admin-auth, operator scopes, and token persistence were already added server-side; this UI is ready to sit on top of them.">Review auth flow</button>
                        </div>
                    </form>
                    <div id="people-operator-preview">${renderCodeBlock(source.operatorPayload)}</div>
                </article>
            </section>
        `;
    }

    function renderCommunications() {
        const source = data.communications;
        return `
            ${metricCards([
                { label: "Campaign cohort", value: String(source.composerPayload.user_ids.length), delta: "target users in current draft", tone: "brand", icon: "megaphone" },
                { label: "Escalated receipts", value: "12", delta: "manual follow-up required", tone: "warning", icon: "siren" },
                { label: "Failed outbox jobs", value: "4", delta: "2 are stale claims", tone: "negative", icon: "mail" },
                { label: "Pending trade tasks", value: "9", delta: "3 are expired", tone: "warning", icon: "briefcase" }
            ])}
            <section class="layout-grid">
                <article class="panel panel--span-7">
                    ${panelHeader("Manual distribution", "Campaign composer", "This mirrors the request body for `/v1/admin/distribution/manual-message`, including channels, acknowledgement deadlines, and metadata.", `<span class="endpoint-badge">POST /v1/admin/distribution/manual-message</span>`) }
                    <form class="form-grid demo-form" data-demo-endpoint="POST /v1/admin/distribution/manual-message" data-demo-target="communications-composer-preview">
                        ${renderForm([
                            { label: "User IDs (comma-separated)", name: "user_ids", full: true, value: source.composerPayload.user_ids?.join(", ") || "" },
                            { label: "Emails (comma-separated)", name: "emails", full: true, value: "" },
                            { label: "Notification type", name: "notification_type", value: source.composerPayload.notification_type },
                            { label: "Ack deadline", name: "ack_deadline_at", type: "datetime-local", value: "2026-04-06T12:30" },
                            {
                                label: "Channels",
                                name: "channels",
                                type: "checkboxes",
                                options: [
                                    { label: "Email", value: "email", checked: true },
                                    { label: "Push", value: "push", checked: true }
                                ]
                            },
                            { label: "Title", name: "title", full: true, value: source.composerPayload.title },
                            { label: "Body", name: "body", type: "textarea", full: true, rows: 5, value: source.composerPayload.body },
                            { label: "Metadata JSON", name: "metadata", type: "textarea", full: true, rows: 6, value: JSON.stringify(source.composerPayload.metadata, null, 2) }
                        ])}
                        <div class="button-row form-field form-field--full">
                            <button class="btn btn--primary" type="submit">Preview payload</button>
                            <button class="btn btn--secondary" type="button" data-demo-action="Queue manual campaign" data-demo-endpoint="POST /v1/admin/distribution/manual-message">Simulate queue</button>
                        </div>
                    </form>
                    <div id="communications-composer-preview">${renderCodeBlock(source.composerPayload)}</div>
                </article>
                <article class="panel panel--span-5">
                    ${panelHeader("Receipt queue", "Follow-up triage", "The action surface here should eventually call claim, ack, resolve, and overdue escalation endpoints.", `<span class="endpoint-badge">/v1/admin/tasks/receipts*</span>`) }
                    <div class="table-wrap">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Receipt</th>
                                    <th>Delivery</th>
                                    <th>Follow-up</th>
                                    <th>Escalation</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${source.receipts.map((item) => `
                                    <tr>
                                        <td>
                                            <div class="table__primary">${escapeHtml(item.id)}</div>
                                            <div class="table__secondary">user ${escapeHtml(item.userId)} · ${escapeHtml(item.notificationId)}<br>deadline ${escapeHtml(item.deadline)}</div>
                                        </td>
                                        <td><span class="${chipClass(item.delivery)}">${escapeHtml(item.delivery)}</span></td>
                                        <td><span class="${chipClass(item.followUp)}">${escapeHtml(item.followUp)}</span></td>
                                        <td>
                                            <div class="data-stack">
                                                <span class="chip ${item.overdue ? "chip--danger" : "chip--warning"}">level ${escapeHtml(item.level)}</span>
                                                <button class="btn btn--ghost" data-demo-action="Receipt action" data-demo-endpoint="POST /v1/admin/tasks/receipts/${escapeHtml(item.id)}/claim">Claim</button>
                                            </div>
                                        </td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                </article>
                <article class="panel panel--span-6">
                    ${panelHeader("Outbox recovery", "Retry and requeue workspace", "Use this module for `/retry`, `/release-stale`, and `/requeue` flows when message delivery drifts or workers keep stale claims.", `<span class="endpoint-badge">/v1/admin/tasks/outbox*</span>`) }
                    <div class="table-wrap">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Outbox ID</th>
                                    <th>Channel</th>
                                    <th>Status</th>
                                    <th>Last error</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${source.outbox.map((item) => `
                                    <tr>
                                        <td>
                                            <div class="table__primary">${escapeHtml(item.id)}</div>
                                            <div class="table__secondary">${escapeHtml(item.notificationId)} · user ${escapeHtml(item.userId)}</div>
                                        </td>
                                        <td><span class="chip">${escapeHtml(item.channel)}</span></td>
                                        <td><span class="${chipClass(item.status)}">${escapeHtml(item.status)}</span></td>
                                        <td>${escapeHtml(item.lastError || "-")}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                    <div class="button-row" style="margin-top:1rem;">
                        <button class="btn btn--secondary" data-demo-action="Retry outbox jobs" data-demo-endpoint="POST /v1/admin/tasks/outbox/retry">Retry selected</button>
                        <button class="btn btn--ghost" data-demo-action="Release stale claims" data-demo-endpoint="POST /v1/admin/tasks/outbox/release-stale">Release stale</button>
                        <button class="btn btn--ghost" data-demo-action="Requeue outbox item" data-demo-endpoint="POST /v1/admin/tasks/outbox/{id}/requeue">Requeue one</button>
                    </div>
                </article>
                <article class="panel panel--span-6">
                    ${panelHeader("Trade task center", "Manual trade workflow", "These actions map to claim and expire endpoints for trade tasks that require human confirmation.", `<span class="endpoint-badge">/v1/admin/tasks/trades*</span>`) }
                    <div class="table-wrap">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Trade task</th>
                                    <th>Status</th>
                                    <th>Suggested amount</th>
                                    <th>Operator</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${source.trades.map((item) => `
                                    <tr>
                                        <td>
                                            <div class="table__primary">${escapeHtml(item.id)} · ${escapeHtml(item.symbol)} ${escapeHtml(item.action)}</div>
                                            <div class="table__secondary">user ${escapeHtml(item.userId)} · expires ${escapeHtml(item.expiresAt)}</div>
                                        </td>
                                        <td><span class="${chipClass(item.expired ? "expired" : item.status)}">${item.expired ? "expired" : escapeHtml(item.status)}</span></td>
                                        <td>${escapeHtml(item.suggestedAmount)}</td>
                                        <td>${escapeHtml(item.operator)}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                    <div class="button-row" style="margin-top:1rem;">
                        <button class="btn btn--primary" data-demo-action="Claim trade tasks" data-demo-endpoint="POST /v1/admin/tasks/trades/claim">Claim tasks</button>
                        <button class="btn btn--secondary" data-demo-action="Expire trade tasks" data-demo-endpoint="POST /v1/admin/tasks/trades/expire">Expire overdue</button>
                    </div>
                </article>
            </section>
        `;
    }

    function renderIntelligence() {
        const source = data.intelligence;
        return `
            ${metricCards(source.analytics.map((item) => ({ ...item, icon: "activity" })))}
            <section class="layout-grid">
                <article class="panel panel--span-4">
                    ${panelHeader("Distribution", "Channel outcome mix", "Snapshot of `/v1/admin/analytics/distribution` rendered as simple density bars.", `<span class="endpoint-badge">GET /v1/admin/analytics/distribution</span>`) }
                    <div class="meter-list">
                        ${source.distribution.map((item) => `
                            <div class="meter-card">
                                <div class="meter__row"><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong></div>
                                <div class="meter__bar"><div class="meter__fill" style="width:${Math.min(Number(item.value), 100)}%"></div></div>
                            </div>
                        `).join("")}
                    </div>
                </article>
                <article class="panel panel--span-4">
                    ${panelHeader("Strategy health", "Current ranking leaders", "Top strategies from the strategy health and latest ranking views.", `<span class="endpoint-badge">GET /v1/admin/analytics/strategy-health</span>`) }
                    <div class="card-list">
                        ${source.strategies.map((item) => `
                            <article class="list-card">
                                <div class="list-card__top">
                                    <strong>#${escapeHtml(item.rank)} ${escapeHtml(item.name)}</strong>
                                    <span class="chip chip--brand">score ${escapeHtml(item.score)}</span>
                                </div>
                                <div class="list-card__copy">degradation ${escapeHtml(item.degradation)} · ${escapeHtml(item.symbols)} symbols covered</div>
                            </article>
                        `).join("")}
                    </div>
                </article>
                <article class="panel panel--span-4">
                    ${panelHeader("Trading agents", "Turnaround snapshot", "Compact cards derived from `/v1/admin/analytics/tradingagents` and analysis list endpoints.", `<span class="endpoint-badge">GET /v1/admin/tradingagents/analyses</span>`) }
                    <div class="card-list">
                        ${source.agents.map((item) => `
                            <article class="list-card">
                                <div class="list-card__top">
                                    <strong>${escapeHtml(item.name)}</strong>
                                    <span class="badge">${escapeHtml(item.value)}</span>
                                </div>
                                <div class="list-card__copy">${escapeHtml(item.endpoint)}</div>
                            </article>
                        `).join("")}
                    </div>
                </article>
                <article class="panel panel--span-5" id="signal-stats">
                    ${panelHeader("Signal stats", "Volume and quality checks", "Make `/v1/admin/signal-stats` visible as an at-a-glance module instead of a raw JSON endpoint.", `<span class="endpoint-badge">GET /v1/admin/signal-stats/summary</span><span class="endpoint-badge">GET /v1/admin/signal-stats/quality</span>`) }
                    <div class="stat-rail">
                        ${source.signalStats.map((item) => `
                            <div class="stat-rail__item">
                                <span class="stat-rail__label">${escapeHtml(item.label)}</span>
                                <span class="stat-rail__value ${clsTone(item.tone)}">${escapeHtml(item.value)}</span>
                            </div>
                        `).join("")}
                    </div>
                    <div class="card-list">
                        ${(source.signalQuality || []).map((item) => `
                            <article class="list-card">
                                <div class="list-card__top">
                                    <strong>${escapeHtml(item.label)}</strong>
                                    <span class="badge">${escapeHtml(item.value)}</span>
                                </div>
                                <div class="list-card__copy">${escapeHtml(item.detail)}</div>
                            </article>
                        `).join("")}
                    </div>
                </article>
                <article class="panel panel--span-5">
                    ${panelHeader("Signal results", "Live signal vs trade baseline", "A first comparable baseline for signal-to-trade outcomes using window + symbol alignment instead of hard foreign-key joins.", `<span class="endpoint-badge">GET /v1/admin/analytics/signal-results</span>`) }
                    <div class="card-list">
                        ${(source.signalResults || []).map((item) => `
                            <article class="list-card">
                                <div class="list-card__top">
                                    <strong>${escapeHtml(item.label)}</strong>
                                    <span class="badge">${escapeHtml(item.value)}</span>
                                </div>
                                <div class="list-card__copy">${escapeHtml(item.detail)}</div>
                            </article>
                        `).join("")}
                    </div>
                </article>
                <article class="panel panel--span-4">
                    ${panelHeader("Calibration", "Snapshot versions", "Reviewed calibration snapshots stored in Postgres and loaded into scanner runtime through the active version lookup.", `<span class="endpoint-badge">GET /v1/admin/calibrations/active</span><span class="endpoint-badge">GET /v1/admin/calibrations</span>`) }
                    <div class="card-list">
                        ${(source.calibrationSnapshots || []).map((item) => `
                            <article class="list-card">
                                <div class="list-card__top">
                                    <strong>${escapeHtml(item.version)}</strong>
                                    <span class="${chipClass(item.status)}">${escapeHtml(item.status)}</span>
                                </div>
                                <div class="list-card__copy">${escapeHtml(item.source)} · ${escapeHtml(item.effectiveAt)}</div>
                                <div class="list-card__copy">${escapeHtml(item.detail)}</div>
                                <div class="list-card__copy">${escapeHtml(item.note)}</div>
                            </article>
                        `).join("")}
                    </div>
                </article>
                <article class="panel panel--span-4">
                    ${panelHeader("Proposal", "Next calibration review", "A generated proposal built from current strategy-health and signal-result baselines so operators can review before creating the next snapshot.", `<span class="endpoint-badge">GET /v1/admin/calibrations/proposal</span>`) }
                    <div class="card-list">
                        ${(source.calibrationProposal || []).map((item) => `
                            <article class="list-card">
                                <div class="list-card__top">
                                    <strong>${escapeHtml(item.label)}</strong>
                                    <span class="badge">${escapeHtml(item.value)}</span>
                                </div>
                                <div class="list-card__copy">${escapeHtml(item.detail)}</div>
                            </article>
                        `).join("")}
                    </div>
                </article>
                <article class="panel panel--span-7">
                    ${panelHeader("Scanner runs", "Decision volume by run", "This table is designed to map cleanly to observability and run-detail endpoints.", `<span class="endpoint-badge">GET /v1/admin/scanner/observability</span>`) }
                    <div class="table-wrap">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Run</th>
                                    <th>Status</th>
                                    <th>Emitted</th>
                                    <th>Suppressed</th>
                                    <th>Skipped</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${source.scannerRuns.map((run) => `
                                    <tr>
                                        <td>
                                            <div class="table__primary">${escapeHtml(run.runId)}</div>
                                            <div class="table__secondary">${escapeHtml(run.startedAt)} · ${escapeHtml(run.universe)}</div>
                                        </td>
                                        <td><span class="${chipClass(run.status)}">${escapeHtml(run.status)}</span></td>
                                        <td>${escapeHtml(run.emitted)}</td>
                                        <td>${escapeHtml(run.suppressed)}</td>
                                        <td>${escapeHtml(run.skipped)}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                </article>
                <article class="panel panel--span-6">
                    ${panelHeader("Live decision log", "Recent signal decisions", "A leaner surface for the paginated live-decision endpoint.", `<span class="endpoint-badge">GET /v1/admin/scanner/live-decision</span>`) }
                    <div class="card-list">
                        ${source.decisions.map((item) => `
                            <article class="list-card">
                                <div class="list-card__top">
                                    <strong>${escapeHtml(item.symbol)}</strong>
                                    <span class="${chipClass(item.status)}">${escapeHtml(item.status)}</span>
                                </div>
                                <div class="list-card__copy">${escapeHtml(item.reason)} · confidence ${escapeHtml(item.confidence)}</div>
                            </article>
                        `).join("")}
                    </div>
                </article>
                <article class="panel panel--span-6">
                    ${panelHeader("Market data anomalies", "Data quality queue", "Bring `/v1/admin/anomalies/ohlcv` forward so operators can see what will poison analytics or signal generation.", `<span class="endpoint-badge">GET /v1/admin/anomalies/ohlcv</span>`) }
                    <div class="table-wrap">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Symbol</th>
                                    <th>Severity</th>
                                    <th>Issue</th>
                                    <th>Observed</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${source.anomalies.map((item) => `
                                    <tr>
                                        <td><span class="table__primary">${escapeHtml(item.symbol)}</span></td>
                                        <td><span class="${chipClass(item.severity)}">${escapeHtml(item.severity)}</span></td>
                                        <td>
                                            <div class="table__primary">${escapeHtml(item.issue)}</div>
                                            <div class="table__secondary">${escapeHtml(item.source)}</div>
                                        </td>
                                        <td>${escapeHtml(item.observedAt)}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                </article>
            </section>
        `;
    }

    function renderRuntime() {
        const source = data.runtime;
        return `
            ${metricCards(source.metrics.map((item) => ({ ...item, icon: "shield-alert" })))}
            <section class="layout-grid">
                <article class="panel panel--span-7">
                    ${panelHeader("Runtime components", "Health board", "This board is designed for `/v1/admin/runtime/components`, with enough density to keep worker and scheduler health scannable.", `<span class="endpoint-badge">GET /v1/admin/runtime/components</span>`) }
                    <div class="card-list">
                        ${source.components.map((component) => `
                            <article class="health-card">
                                <div class="health-card__top">
                                    <div>
                                        <strong>${escapeHtml(component.name)}</strong>
                                        <div class="health-card__copy">${escapeHtml(component.kind)} · ${escapeHtml(component.lastSeen)}</div>
                                    </div>
                                    <span class="${chipClass(component.health)}">${escapeHtml(component.health)}</span>
                                </div>
                                <div class="health-card__copy">${escapeHtml(component.copy)}</div>
                                <div class="alert-item__meta">
                                    <span class="chip">${escapeHtml(component.status)}</span>
                                    <button class="btn btn--ghost" data-demo-action="Inspect component" data-demo-endpoint="GET /v1/admin/runtime/components/${escapeHtml(component.kind)}/${escapeHtml(component.name)}">Open detail</button>
                                </div>
                            </article>
                        `).join("")}
                    </div>
                </article>
                <article class="panel panel--span-5">
                    ${panelHeader("Active alerts", "What can block release or response", "Direct UI match for runtime and platform alert payloads.", `<span class="endpoint-badge">GET /v1/admin/runtime/alerts</span>`) }
                    <div class="alert-list">${renderAlerts(source.alerts)}</div>
                </article>
                <article class="panel panel--span-7">
                    ${panelHeader("Audit log", "Operator traceability", "This table maps to the filterable audit event list and should become a live log once connected.", `<span class="endpoint-badge">GET /v1/admin/audit</span>`) }
                    <div class="table-wrap">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Timestamp</th>
                                    <th>Entity</th>
                                    <th>Action</th>
                                    <th>Source</th>
                                    <th>Request ID</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${source.audit.map((item) => `
                                    <tr>
                                        <td>${escapeHtml(item.timestamp)}</td>
                                        <td>${escapeHtml(item.entity)}</td>
                                        <td>${escapeHtml(item.action)}</td>
                                        <td>${escapeHtml(item.source)} · op ${escapeHtml(item.operator)}</td>
                                        <td><span class="endpoint-badge">${escapeHtml(item.requestId)}</span></td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                </article>
                <article class="panel panel--span-5">
                    ${panelHeader("Acceptance", "Release readiness", "The deployment readiness report becomes useful only when it is visible next to runtime truth, not hidden in raw JSON.", `<span class="endpoint-badge">GET /v1/admin/acceptance/report</span>`) }
                    <div class="inline-note">Current status: <strong>${escapeHtml(source.acceptance.status)}</strong>. Last updated ${escapeHtml(source.acceptance.updatedAt)}.</div>
                    <div class="card-list" style="margin-top:1rem;">
                        ${source.acceptance.items.map((item) => `
                            <article class="list-card">
                                <div class="list-card__top">
                                    <strong>${escapeHtml(item.label)}</strong>
                                    <span class="${chipClass(item.state)}">${escapeHtml(item.state)}</span>
                                </div>
                            </article>
                        `).join("")}
                    </div>
                    <div class="button-row" style="margin-top:1rem;">
                        <button class="btn btn--primary" data-demo-action="Export readiness report" data-demo-endpoint="GET /v1/admin/acceptance/report">Preview report export</button>
                    </div>
                </article>
            </section>
        `;
    }

    function renderExperiments() {
        const source = data.experiments;
        return `
            ${metricCards(source.metrics.map((item) => ({ ...item, icon: "flask-conical" })))}
            <section class="layout-grid">
                <article class="panel panel--span-7">
                    ${panelHeader("Backtest runs", "Execution history", "This surface is intentionally action-adjacent so stale or failed runs are obvious before a refresh is fired.", `<span class="endpoint-badge">GET /v1/admin/backtests/runs</span>`) }
                    <div class="table-wrap">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Run</th>
                                    <th>Status</th>
                                    <th>Window</th>
                                    <th>Score</th>
                                    <th>Updated</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${source.backtests.map((item) => `
                                    <tr>
                                        <td>
                                            <div class="table__primary">#${escapeHtml(item.id)} ${escapeHtml(item.strategy)}</div>
                                            <div class="table__secondary">${escapeHtml(item.symbol)} · ${escapeHtml(item.timeframe)}</div>
                                        </td>
                                        <td><span class="${chipClass(item.status)}">${escapeHtml(item.status)}</span></td>
                                        <td>${escapeHtml(item.window)}</td>
                                        <td>${escapeHtml(item.score)}</td>
                                        <td>${escapeHtml(item.updatedAt)}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                </article>
                <article class="panel panel--span-5">
                    ${panelHeader("Latest rankings", "Top-performing strategies", "A compact rendering of the latest ranking payload used by operators and release reviewers.", `<span class="endpoint-badge">GET /v1/admin/backtests/rankings/latest</span>`) }
                    <div class="card-list">
                        ${source.rankings.map((item) => `
                            <article class="list-card">
                                <div class="list-card__top">
                                    <strong>#${escapeHtml(item.rank)} ${escapeHtml(item.strategy)}</strong>
                                    <span class="chip chip--brand">${escapeHtml(item.score)}</span>
                                </div>
                                <div class="list-card__copy">${escapeHtml(item.timeframe)} · degradation ${escapeHtml(item.degradation)} · ${escapeHtml(item.symbols)} symbols</div>
                            </article>
                        `).join("")}
                    </div>
                </article>
                <article class="panel panel--span-6">
                    ${panelHeader("Trigger refresh", "Backtest request builder", "Payload shape for the mutation endpoint that refreshes stale ranking windows.", `<span class="endpoint-badge">POST /v1/admin/backtests/runs</span>`) }
                    <form class="form-grid demo-form" data-demo-endpoint="POST /v1/admin/backtests/runs" data-demo-target="experiments-refresh-preview">
                        ${renderForm([
                            { label: "Symbols", name: "symbols", full: true, value: source.refreshPayload.symbols.join(", ") },
                            { label: "Strategies", name: "strategy_names", full: true, value: source.refreshPayload.strategy_names.join(", ") },
                            { label: "Windows (hours)", name: "windows", full: true, value: source.refreshPayload.windows.join(", ") },
                            { label: "Timeframe", name: "timeframe", value: source.refreshPayload.timeframe }
                        ])}
                        <div class="button-row form-field form-field--full">
                            <button class="btn btn--primary" type="submit">Preview payload</button>
                            <button class="btn btn--secondary" type="button" data-demo-action="Trigger ranking refresh" data-demo-endpoint="POST /v1/admin/backtests/runs">Simulate refresh</button>
                        </div>
                    </form>
                    <div id="experiments-refresh-preview">${renderCodeBlock(source.refreshPayload)}</div>
                </article>
                <article class="panel panel--span-6">
                    ${panelHeader("Trading agent analyses", "Recovery queue", "Design target for list/detail and delayed reconcile actions in the AI analysis surface.", `<span class="endpoint-badge">GET /v1/admin/tradingagents/analyses</span><span class="endpoint-badge">POST /v1/admin/tradingagents/reconcile-delayed</span>`) }
                    <div class="table-wrap">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Request</th>
                                    <th>Status</th>
                                    <th>Trigger</th>
                                    <th>Final action</th>
                                    <th>Latency</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${source.analyses.map((item) => `
                                    <tr>
                                        <td>${escapeHtml(item.requestId)} · ${escapeHtml(item.symbol)}</td>
                                        <td><span class="${chipClass(item.status)}">${escapeHtml(item.status)}</span></td>
                                        <td>${escapeHtml(item.trigger)}</td>
                                        <td>${escapeHtml(item.finalAction)}</td>
                                        <td>${escapeHtml(item.latency)}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                    <div class="button-row" style="margin-top:1rem;">
                        <button class="btn btn--primary" data-demo-action="Reconcile delayed analyses" data-demo-endpoint="POST /v1/admin/tradingagents/reconcile-delayed">Reconcile delayed</button>
                    </div>
                </article>
            </section>
        `;
    }

    function renderPage() {
        const root = document.getElementById("page-content");
        if (!root) return;
        let content = "";
        if (state.page === "dashboard") content = renderDashboard();
        if (state.page === "people") content = renderPeople();
        if (state.page === "communications") content = renderCommunications();
        if (state.page === "intelligence") content = renderIntelligence();
        if (state.page === "runtime") content = renderRuntime();
        if (state.page === "experiments") content = renderExperiments();
        root.className = "page-shell";
        root.innerHTML = `${renderHero()}${content}`;
        mountSecondaryMenu(root);
    }

    function toast(title, copy) {
        const stack = document.getElementById("toast-stack");
        if (!stack) return;
        const node = document.createElement("div");
        node.className = "toast";
        node.innerHTML = `<div class="toast__title">${escapeHtml(title)}</div><div class="toast__copy">${escapeHtml(copy)}</div>`;
        stack.appendChild(node);
        setTimeout(() => node.remove(), 3200);
    }

    function openApiConsole(keyword) {
        const filterKeyword = String(keyword || "").trim();
        if (window.AdminAPI && typeof window.AdminAPI.focusConsole === "function") {
            window.AdminAPI.focusConsole(filterKeyword, true);
            return true;
        }

        const panel = document.getElementById("admin-api-console");
        if (!panel) {
            return false;
        }
        panel.scrollIntoView({ behavior: "smooth", block: "start" });

        const fallbackFilter = document.getElementById("admin-api-console-filter");
        if (fallbackFilter) {
            fallbackFilter.value = filterKeyword;
            fallbackFilter.dispatchEvent(new Event("input", { bubbles: true }));
            fallbackFilter.focus();
        }
        return true;
    }

    function attachInteractions() {
        const searchInput = document.getElementById("topbar-endpoint-search");
        const searchButton = document.getElementById("topbar-endpoint-search-btn");

        function applyTopbarSearch() {
            const keyword = String(searchInput && searchInput.value ? searchInput.value : "").trim();
            const opened = openApiConsole(keyword);
            if (!opened) {
                toast("API 控制台未就绪", "请稍后重试。页面加载完成后将自动挂载控制台。");
                return;
            }
            if (keyword) {
                toast("已筛选 API 控制台", `关键词：${keyword}`);
            } else {
                toast("已打开 API 控制台", "当前展示所有管理端接口。");
            }
        }

        if (searchButton) {
            searchButton.addEventListener("click", applyTopbarSearch);
        }

        if (searchInput) {
            searchInput.addEventListener("keydown", (event) => {
                if (event.key !== "Enter") return;
                event.preventDefault();
                applyTopbarSearch();
            });
        }

        document.addEventListener("click", (event) => {
            const moduleButton = event.target.closest("[data-module-target]");
            if (moduleButton) {
                event.preventDefault();
                const targetId = moduleButton.getAttribute("data-module-target") || "";
                const target = document.getElementById(targetId);
                if (!target) {
                    return;
                }
                target.scrollIntoView({ behavior: "smooth", block: "start" });
                setSubnavActive(targetId);
                return;
            }

            const trigger = event.target.closest("[data-admin-console-filter], [data-open-api-console]");
            if (!trigger) return;
            event.preventDefault();
            const family = trigger.getAttribute("data-admin-console-filter") || "";
            const isOpenAll = trigger.hasAttribute("data-open-api-console");
            const opened = openApiConsole(isOpenAll ? "" : family);
            if (!opened) {
                toast("API 控制台未就绪", "请稍后重试。页面加载完成后将自动挂载控制台。");
                return;
            }
            if (!isOpenAll && family) {
                toast("已定位后端能力域", `当前筛选：${family}`);
            }
        });

        document.addEventListener("click", (event) => {
            const button = event.target.closest("[data-demo-action]");
            if (!button) return;
            event.preventDefault();
            const action = button.getAttribute("data-demo-action") || "Preview action";
            const endpoint = button.getAttribute("data-demo-endpoint");
            const copy = button.getAttribute("data-demo-copy") || (endpoint ? `This frontend module is ready to call ${endpoint} once the demo data layer is replaced with real fetch wiring.` : "This interaction is currently front-end only, but the UI shape is ready.");
            toast(action, copy);
        });

        document.querySelectorAll(".demo-form").forEach((form) => {
            form.addEventListener("submit", (event) => {
                event.preventDefault();
                const endpoint = form.getAttribute("data-demo-endpoint") || "";
                const targetId = form.getAttribute("data-demo-target");
                const fields = new FormData(form);
                const payload = {};
                for (const [key, value] of fields.entries()) {
                    if (payload[key] !== undefined) {
                        if (!Array.isArray(payload[key])) payload[key] = [payload[key]];
                        payload[key].push(value);
                    } else {
                        payload[key] = value;
                    }
                }
                const target = targetId ? document.getElementById(targetId) : null;
                if (target) {
                    target.innerHTML = renderCodeBlock(payload);
                }
                toast("Payload ready", endpoint ? `Prepared a front-end request body for ${endpoint}.` : "Prepared a request body preview.");
            });
        });
    }

    async function boot() {
        if (window.AdminAPI && window.AdminAPI.getToken()) {
            if (window.AdminAPI.fetchPageData) {
                try {
                    await window.AdminAPI.fetchPageData(state.page, data);
                } catch (e) {
                    console.error("Failed to load live data, using demo fallback", e);
                }
            }
        }
        renderSidebar();
        renderMobileNav();
        renderTopbar();
        renderPage();
        attachInteractions();
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    boot();
})();
