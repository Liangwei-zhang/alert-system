from __future__ import annotations

import json
from html import escape
from typing import Literal

SurfaceName = Literal["app", "platform", "admin"]

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>__TITLE__</title>
    <style>
        :root {
            color-scheme: light;
            --bg: #f3efe5;
            --panel: rgba(255, 252, 247, 0.92);
            --panel-strong: #fffdf8;
            --ink: #182321;
            --muted: #596a67;
            --line: rgba(24, 35, 33, 0.12);
            --accent: #0c7c59;
            --accent-strong: #0a6247;
            --warm: #d99f4f;
            --danger: #a33b2f;
            --shadow: 0 18px 45px rgba(24, 35, 33, 0.08);
            --radius-xl: 28px;
            --radius-lg: 20px;
            --radius-md: 14px;
            --radius-sm: 10px;
        }

        * {
            box-sizing: border-box;
        }

        html {
            min-height: 100%;
            background:
                radial-gradient(circle at top left, rgba(217, 159, 79, 0.28), transparent 28%),
                radial-gradient(circle at top right, rgba(12, 124, 89, 0.18), transparent 32%),
                linear-gradient(180deg, #f8f5ed 0%, var(--bg) 100%);
        }

        body {
            margin: 0;
            min-height: 100dvh;
            color: var(--ink);
            font-family: "Trebuchet MS", "Segoe UI", sans-serif;
        }

        a {
            color: inherit;
        }

        .page-shell {
            max-width: 1320px;
            margin: 0 auto;
            padding: 24px 20px 56px;
        }

        .masthead {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            align-items: center;
            margin-bottom: 20px;
            padding: 18px 22px;
            border-radius: var(--radius-xl);
            background: rgba(255, 253, 248, 0.8);
            border: 1px solid rgba(24, 35, 33, 0.08);
            box-shadow: var(--shadow);
            backdrop-filter: blur(18px);
        }

        .brand-block {
            display: flex;
            gap: 14px;
            align-items: center;
        }

        .brand-mark {
            width: 44px;
            height: 44px;
            border-radius: 14px;
            background: linear-gradient(135deg, var(--accent) 0%, #1d4f91 100%);
            color: #fff;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            letter-spacing: 0.08em;
        }

        .brand-copy h1,
        .panel h2,
        .hero-copy h2 {
            font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
        }

        .brand-copy h1 {
            margin: 0;
            font-size: 1.2rem;
        }

        .brand-copy p {
            margin: 4px 0 0;
            color: var(--muted);
            font-size: 0.94rem;
        }

        .nav-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }

        .nav-chip {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 14px;
            border-radius: 999px;
            text-decoration: none;
            background: rgba(255, 255, 255, 0.6);
            border: 1px solid rgba(24, 35, 33, 0.08);
            color: var(--muted);
            transition: transform 160ms ease, background 160ms ease, color 160ms ease;
        }

        .nav-chip:hover {
            transform: translateY(-1px);
            color: var(--ink);
        }

        .nav-chip.active {
            background: var(--ink);
            color: #fdfbf7;
            border-color: transparent;
        }

        .hero {
            display: grid;
            grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.95fr);
            gap: 18px;
            margin-bottom: 18px;
        }

        .hero-card,
        .hero-aside,
        .panel {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: var(--radius-xl);
            box-shadow: var(--shadow);
            backdrop-filter: blur(18px);
        }

        .hero-card {
            position: relative;
            overflow: hidden;
            padding: 32px;
        }

        .hero-card::after {
            content: "";
            position: absolute;
            inset: auto -10% -28% 44%;
            height: 180px;
            background: radial-gradient(circle, rgba(217, 159, 79, 0.22), transparent 70%);
            pointer-events: none;
        }

        .hero-kicker {
            display: inline-flex;
            padding: 6px 10px;
            border-radius: 999px;
            background: rgba(12, 124, 89, 0.1);
            color: var(--accent-strong);
            font-size: 0.8rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .hero-copy h2 {
            margin: 14px 0 10px;
            font-size: clamp(2rem, 4vw, 3.3rem);
            line-height: 1.02;
        }

        .hero-copy p {
            max-width: 64ch;
            margin: 0;
            color: var(--muted);
            line-height: 1.7;
        }

        .hero-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin-top: 22px;
        }

        .hero-stat {
            padding: 14px;
            border-radius: var(--radius-md);
            background: rgba(255, 255, 255, 0.6);
            border: 1px solid rgba(24, 35, 33, 0.08);
        }

        .hero-stat strong {
            display: block;
            font-size: 1.15rem;
        }

        .hero-stat span {
            display: block;
            margin-top: 4px;
            color: var(--muted);
            font-size: 0.88rem;
        }

        .hero-aside {
            padding: 26px 24px;
        }

        .hero-aside h3 {
            margin: 0 0 12px;
            font-size: 1rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--muted);
        }

        .hero-aside ul {
            margin: 0;
            padding-left: 18px;
            color: var(--muted);
            line-height: 1.7;
        }

        .surface-grid {
            display: grid;
            grid-template-columns: repeat(12, minmax(0, 1fr));
            gap: 18px;
        }

        .panel {
            padding: 22px;
            grid-column: span 6;
        }

        .panel.wide {
            grid-column: span 12;
        }

        .panel.tall {
            min-height: 100%;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: flex-start;
            margin-bottom: 14px;
        }

        .panel-header h2 {
            margin: 0;
            font-size: 1.45rem;
        }

        .pill {
            display: inline-flex;
            align-items: center;
            padding: 6px 10px;
            border-radius: 999px;
            background: rgba(12, 124, 89, 0.1);
            color: var(--accent-strong);
            font-size: 0.8rem;
        }

        .panel-copy,
        .panel-note,
        .helper {
            color: var(--muted);
            line-height: 1.6;
            font-size: 0.94rem;
        }

        .field-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
            margin: 14px 0;
        }

        .field-grid.single {
            grid-template-columns: minmax(0, 1fr);
        }

        label {
            display: flex;
            flex-direction: column;
            gap: 6px;
            color: var(--muted);
            font-size: 0.86rem;
        }

        input,
        textarea,
        select {
            width: 100%;
            border: 1px solid rgba(24, 35, 33, 0.12);
            border-radius: var(--radius-sm);
            padding: 12px 14px;
            color: var(--ink);
            background: rgba(255, 255, 255, 0.72);
            font: inherit;
        }

        textarea {
            min-height: 112px;
            resize: vertical;
        }

        .inline-check {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            font-size: 0.92rem;
            color: var(--ink);
        }

        .inline-check input {
            width: auto;
            margin: 0;
        }

        .button-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 14px;
        }

        button {
            border: none;
            border-radius: 999px;
            padding: 11px 16px;
            background: var(--accent);
            color: #fff;
            font: inherit;
            cursor: pointer;
            transition: transform 160ms ease, background 160ms ease;
        }

        button:hover {
            transform: translateY(-1px);
            background: var(--accent-strong);
        }

        button.secondary {
            background: rgba(24, 35, 33, 0.08);
            color: var(--ink);
        }

        button.ghost {
            background: transparent;
            color: var(--muted);
            border: 1px solid rgba(24, 35, 33, 0.12);
        }

        .status {
            min-height: 24px;
            margin-top: 12px;
            font-size: 0.92rem;
            color: var(--muted);
        }

        .status[data-tone=\"success\"] {
            color: var(--accent-strong);
        }

        .status[data-tone=\"error\"] {
            color: var(--danger);
        }

        .json-output {
            margin-top: 14px;
            min-height: 180px;
            max-height: 420px;
            overflow: auto;
            padding: 14px;
            border-radius: var(--radius-md);
            background: #f8f4ed;
            border: 1px solid rgba(24, 35, 33, 0.08);
            color: #203533;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
            font-size: 0.85rem;
            line-height: 1.6;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .table-wrap {
            margin-top: 14px;
            overflow: auto;
            border-radius: var(--radius-md);
            border: 1px solid rgba(24, 35, 33, 0.08);
            background: rgba(255, 255, 255, 0.7);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            min-width: 540px;
        }

        th,
        td {
            padding: 12px 14px;
            border-bottom: 1px solid rgba(24, 35, 33, 0.08);
            text-align: left;
            font-size: 0.92rem;
            vertical-align: top;
        }

        th {
            background: rgba(24, 35, 33, 0.04);
            color: var(--muted);
            font-weight: 600;
        }

        .empty-state {
            padding: 18px;
            color: var(--muted);
        }

        .token-note {
            margin-top: 10px;
            color: var(--muted);
            font-size: 0.9rem;
        }

        @media (max-width: 1100px) {
            .hero {
                grid-template-columns: minmax(0, 1fr);
            }

            .panel {
                grid-column: span 12;
            }
        }

        @media (max-width: 720px) {
            .page-shell {
                padding: 16px 14px 34px;
            }

            .masthead {
                flex-direction: column;
                align-items: stretch;
            }

            .hero-card,
            .hero-aside,
            .panel {
                padding: 18px;
            }

            .field-grid,
            .hero-grid {
                grid-template-columns: minmax(0, 1fr);
            }

            .nav-row,
            .button-row {
                flex-direction: column;
            }

            .nav-chip,
            button {
                justify-content: center;
            }
        }
    </style>
</head>
<body data-surface=\"__SURFACE__\">
    <div class=\"page-shell\">
        <header class=\"masthead\">
            <div class=\"brand-block\">
                <div class=\"brand-mark\">SP</div>
                <div class=\"brand-copy\">
                    <h1>__BRAND__</h1>
                    <p>订阅端、桌面端与管理端的统一入口。</p>
                </div>
            </div>
            <nav class=\"nav-row\">__NAV__</nav>
        </header>

        <section class=\"hero\">
            <div class=\"hero-card\">
                <div class=\"hero-copy\">
                    <span class=\"hero-kicker\">股票订阅系统三端入口</span>
                    <h2>__HERO_TITLE__</h2>
                    <p>__HERO_COPY__</p>
                </div>
                <div class=\"hero-grid\">
                    <div class=\"hero-stat\">
                        <strong>/app</strong>
                        <span>邮箱登录、本地草稿、订阅股票、持仓与一键开始订阅。</span>
                    </div>
                    <div class=\"hero-stat\">
                        <strong>/platform</strong>
                        <span>桌面监控核心，承载研究、信号判断与交易查询。</span>
                    </div>
                    <div class=\"hero-stat\">
                        <strong>/admin</strong>
                        <span>内部运营与风控控制面，负责用户、任务与验收。</span>
                    </div>
                </div>
            </div>

            <aside class=\"hero-aside\">
                <h3>产品说明</h3>
                <ul>
                    <li>`/app` 以离线优先为目标，大部分录入先保存在当前浏览器。</li>
                    <li>`/platform` 是监控与信号核心，用于处理观察列表、策略与预警分发。</li>
                    <li>`/admin` 是内部控制面，用于运营、风控、审计与任务回补。</li>
                    <li>三端页面都由 Python 直接提供，不依赖额外前端构建流程。</li>
                </ul>
            </aside>
        </section>

        <main class=\"surface-grid\">__BODY__</main>
    </div>

    <script>
        const pageConfig = __PAGE_CONFIG__;
__COMMON_SCRIPT__
__PAGE_SCRIPT__
    </script>
</body>
</html>
"""

_COMMON_SCRIPT = """
const stockPyUi = (() => {
    const storageKeys = {
        publicBase: "stockpy.ui.public-base",
        adminBase: "stockpy.ui.admin-base",
        accessToken: "stockpy.ui.access-token",
        refreshToken: "stockpy.ui.refresh-token",
        user: "stockpy.ui.user",
        adminToken: "stockpy.ui.admin-token",
        adminRefreshToken: "stockpy.ui.admin-refresh-token",
        adminUser: "stockpy.ui.admin-user",
        adminContext: "stockpy.ui.admin-context",
        adminOperatorId: "stockpy.ui.admin-operator-id"
    };

    function byId(id) {
        return document.getElementById(id);
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function normalizeBaseUrl(value) {
        return String(value ?? "").trim().replace(/\\/+$/, "");
    }

    function fallbackBaseUrl(kind) {
        const configured = kind === "admin" ? pageConfig.adminApiBaseUrl : pageConfig.publicApiBaseUrl;
        return normalizeBaseUrl(configured) || window.location.origin;
    }

    function getBaseUrl(kind) {
        const key = kind === "admin" ? storageKeys.adminBase : storageKeys.publicBase;
        return normalizeBaseUrl(localStorage.getItem(key)) || fallbackBaseUrl(kind);
    }

    function setBaseUrl(kind, value) {
        const key = kind === "admin" ? storageKeys.adminBase : storageKeys.publicBase;
        const normalized = normalizeBaseUrl(value);
        if (normalized) {
            localStorage.setItem(key, normalized);
        } else {
            localStorage.removeItem(key);
        }
        return getBaseUrl(kind);
    }

    function publicApi(path) {
        return getBaseUrl("public") + path;
    }

    function adminApi(path) {
        return getBaseUrl("admin") + path;
    }

    async function requestJson(method, url, options = {}) {
        const headers = new Headers(options.headers || {});
        if (options.body !== undefined) {
            headers.set("Content-Type", "application/json");
        }
        if (options.token) {
            headers.set("Authorization", `Bearer ${options.token}`);
        }
        if (options.operatorId) {
            headers.set("X-Operator-ID", String(options.operatorId));
        }

        const response = await fetch(url, {
            method,
            headers,
            body: options.body !== undefined ? JSON.stringify(options.body) : undefined
        });

        const raw = await response.text();
        let payload = null;
        if (raw) {
            try {
                payload = JSON.parse(raw);
            } catch (_error) {
                payload = raw;
            }
        }

        if (!response.ok) {
            const detail = payload && typeof payload === "object"
                ? payload.detail || payload.message || JSON.stringify(payload)
                : raw || `Request failed (${response.status})`;
            throw new Error(detail);
        }

        return payload;
    }

    function renderJson(id, payload) {
        const node = byId(id);
        if (!node) {
            return;
        }
        if (payload === undefined || payload === null || payload === "") {
            node.textContent = "";
            return;
        }
        node.textContent = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
    }

    function setStatus(id, message, tone = "info") {
        const node = byId(id);
        if (!node) {
            return;
        }
        node.dataset.tone = tone;
        node.textContent = message || "";
    }

    function readValue(id) {
        const node = byId(id);
        return node ? node.value.trim() : "";
    }

    function readNumber(id, fallback) {
        const raw = readValue(id);
        if (!raw) {
            return fallback;
        }
        const parsed = Number(raw);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function readCheckbox(id) {
        const node = byId(id);
        return Boolean(node && node.checked);
    }

    function getAccessToken() {
        return localStorage.getItem(storageKeys.accessToken) || "";
    }

    function getRefreshToken() {
        return localStorage.getItem(storageKeys.refreshToken) || "";
    }

    function getStoredUser() {
        const raw = localStorage.getItem(storageKeys.user);
        if (!raw) {
            return null;
        }
        try {
            return JSON.parse(raw);
        } catch (_error) {
            return null;
        }
    }

    function setPublicSession(sessionPayload) {
        if (!sessionPayload || !sessionPayload.access_token || !sessionPayload.refresh_token) {
            return;
        }
        localStorage.setItem(storageKeys.accessToken, sessionPayload.access_token);
        localStorage.setItem(storageKeys.refreshToken, sessionPayload.refresh_token);
        if (sessionPayload.user) {
            localStorage.setItem(storageKeys.user, JSON.stringify(sessionPayload.user));
        }
    }

    function clearPublicSession() {
        localStorage.removeItem(storageKeys.accessToken);
        localStorage.removeItem(storageKeys.refreshToken);
        localStorage.removeItem(storageKeys.user);
    }

    function getAdminToken() {
        return localStorage.getItem(storageKeys.adminToken) || "";
    }

    function getAdminRefreshToken() {
        return localStorage.getItem(storageKeys.adminRefreshToken) || "";
    }

    function getAdminStoredUser() {
        const raw = localStorage.getItem(storageKeys.adminUser);
        if (!raw) {
            return null;
        }
        try {
            return JSON.parse(raw);
        } catch (_error) {
            return null;
        }
    }

    function getAdminContext() {
        const raw = localStorage.getItem(storageKeys.adminContext);
        if (!raw) {
            return null;
        }
        try {
            return JSON.parse(raw);
        } catch (_error) {
            return null;
        }
    }

    function getAdminOperatorId() {
        const stored = String(localStorage.getItem(storageKeys.adminOperatorId) || "").trim();
        if (stored) {
            return stored;
        }
        const user = getAdminStoredUser();
        if (user && user.id !== undefined && user.id !== null) {
            return String(user.id);
        }
        return "";
    }

    function setAdminToken(token) {
        const normalized = String(token || "").trim();
        if (normalized) {
            localStorage.setItem(storageKeys.adminToken, normalized);
        } else {
            localStorage.removeItem(storageKeys.adminToken);
        }
        return normalized;
    }

    function setAdminOperatorId(value) {
        const normalized = String(value || "").trim();
        if (normalized) {
            localStorage.setItem(storageKeys.adminOperatorId, normalized);
        } else {
            localStorage.removeItem(storageKeys.adminOperatorId);
        }
        return getAdminOperatorId();
    }

    function setAdminSession(sessionPayload) {
        if (!sessionPayload || !sessionPayload.access_token) {
            return;
        }
        localStorage.setItem(storageKeys.adminToken, sessionPayload.access_token);
        if (sessionPayload.refresh_token) {
            localStorage.setItem(storageKeys.adminRefreshToken, sessionPayload.refresh_token);
        } else {
            localStorage.removeItem(storageKeys.adminRefreshToken);
        }
        if (sessionPayload.user) {
            localStorage.setItem(storageKeys.adminUser, JSON.stringify(sessionPayload.user));
            if (sessionPayload.user.id !== undefined && sessionPayload.user.id !== null) {
                localStorage.setItem(storageKeys.adminOperatorId, String(sessionPayload.user.id));
            }
        }
        if (sessionPayload.admin) {
            localStorage.setItem(storageKeys.adminContext, JSON.stringify(sessionPayload.admin));
        }
    }

    function clearAdminSession() {
        localStorage.removeItem(storageKeys.adminToken);
        localStorage.removeItem(storageKeys.adminRefreshToken);
        localStorage.removeItem(storageKeys.adminUser);
        localStorage.removeItem(storageKeys.adminContext);
        localStorage.removeItem(storageKeys.adminOperatorId);
    }

    function requireAccessToken() {
        const token = getAccessToken();
        if (!token) {
            throw new Error("请先验证用户验证码以获取访问令牌。");
        }
        return token;
    }

    function requireAdminToken() {
        const token = getAdminToken();
        if (!token) {
            throw new Error("请先以管理员操作员身份登录，或粘贴管理 Bearer Token。");
        }
        return token;
    }

    function requireAdminOperatorId() {
        const operatorId = getAdminOperatorId();
        if (!operatorId) {
            throw new Error("此操作必须提供管理员操作员 ID。请先登录，或填写操作员 ID 覆盖值。");
        }
        return operatorId;
    }

    function renderSearchTable(containerId, items) {
        const node = byId(containerId);
        if (!node) {
            return;
        }
        if (!Array.isArray(items) || items.length === 0) {
            node.innerHTML = '<div class="empty-state">当前搜索词没有匹配到任何标的。</div>';
            return;
        }

        const rows = items.map((item) => `
            <tr>
                <td><strong>${escapeHtml(item.symbol)}</strong></td>
                <td>${escapeHtml(item.name || item.name_zh || "")}</td>
                <td>${escapeHtml(item.asset_type || "")}</td>
                <td>${escapeHtml(item.exchange || "")}</td>
                <td><button type="button" class="secondary search-pick" data-symbol="${escapeHtml(item.symbol)}">使用代码</button></td>
            </tr>
        `).join("");

        node.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>代码</th>
                        <th>名称</th>
                        <th>类型</th>
                        <th>交易所</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `;
    }

    function renderSessionSnapshot(targetId) {
        renderJson(targetId, {
            public_api_base_url: getBaseUrl("public"),
            admin_api_base_url: getBaseUrl("admin"),
            access_token_present: Boolean(getAccessToken()),
            refresh_token_present: Boolean(getRefreshToken()),
            stored_user: getStoredUser(),
            admin_token_present: Boolean(getAdminToken()),
            admin_refresh_token_present: Boolean(getAdminRefreshToken()),
            stored_admin_user: getAdminStoredUser(),
            stored_admin_context: getAdminContext(),
            admin_operator_id: getAdminOperatorId()
        });
    }

    function bindBaseForm() {
        const publicInput = byId("public-api-base");
        const adminInput = byId("admin-api-base");
        const saveButton = byId("save-base-urls");

        if (publicInput) {
            publicInput.value = getBaseUrl("public");
        }
        if (adminInput) {
            adminInput.value = getBaseUrl("admin");
        }

        if (saveButton) {
            saveButton.addEventListener("click", () => {
                const savedPublic = setBaseUrl("public", publicInput ? publicInput.value : "");
                const savedAdmin = setBaseUrl("admin", adminInput ? adminInput.value : "");
                setStatus(
                    "base-url-status",
                    `接口地址已保存。Public=${savedPublic} Admin=${savedAdmin}`,
                    "success"
                );
                renderSessionSnapshot("session-output");
                renderSessionSnapshot("platform-session-output");
                renderSessionSnapshot("admin-session-output");
            });
        }
    }

    return {
        adminApi,
        bindBaseForm,
        byId,
        clearPublicSession,
        escapeHtml,
        getAccessToken,
        getAdminContext,
        getAdminOperatorId,
        getAdminRefreshToken,
        getAdminStoredUser,
        getAdminToken,
        getBaseUrl,
        getRefreshToken,
        getStoredUser,
        publicApi,
        readCheckbox,
        readNumber,
        readValue,
        clearAdminSession,
        renderJson,
        renderSearchTable,
        renderSessionSnapshot,
        requestJson,
        requireAccessToken,
        requireAdminOperatorId,
        requireAdminToken,
        setAdminSession,
        setAdminOperatorId,
        setAdminToken,
        setPublicSession,
        setStatus
    };
})();

window.stockPyUi = stockPyUi;
window.addEventListener("DOMContentLoaded", () => stockPyUi.bindBaseForm());
"""

_APP_SCRIPT = """
window.addEventListener("DOMContentLoaded", () => {
    const ui = window.stockPyUi;

    const draftStorageKey = "stockpy.ui.subscriber-draft";
    const defaultCash = 0;

    function numberOrZero(value) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : 0;
    }

    function roundMoney(value) {
        return Math.round((numberOrZero(value) + Number.EPSILON) * 100) / 100;
    }

    function roundRatio(value) {
        return Math.round((numberOrZero(value) + Number.EPSILON) * 10000) / 10000;
    }

    function formatNumber(value) {
        return new Intl.NumberFormat("zh-CN", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
        }).format(numberOrZero(value));
    }

    function formatDateTime(value) {
        if (!value) {
            return "未记录";
        }
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) {
            return String(value);
        }
        return new Intl.DateTimeFormat("zh-CN", {
            dateStyle: "medium",
            timeStyle: "short"
        }).format(parsed);
    }

    function normalizeSymbol(value) {
        return String(value || "").trim().toUpperCase();
    }

    function defaultDraft() {
        return {
            cash: defaultCash,
            currency: "USD",
            allowEmptyPortfolio: false,
            watchlist: [],
            portfolio: [],
            remoteSummary: null,
            lastSavedAt: null,
            lastSyncResponse: null
        };
    }

    function sanitizeWatchlistItem(item) {
        const symbol = normalizeSymbol(item && item.symbol);
        if (!symbol) {
            return null;
        }
        const score = Math.max(0, Math.min(100, Math.round(numberOrZero(item && item.min_score) || 65)));
        return {
            symbol,
            min_score: score,
            notify: item && item.notify !== undefined ? Boolean(item.notify) : true
        };
    }

    function sanitizePortfolioItem(item) {
        const symbol = normalizeSymbol(item && item.symbol);
        const shares = Math.floor(numberOrZero(item && item.shares));
        const avgCost = roundMoney(item && item.avg_cost);
        if (!symbol || shares <= 0 || avgCost <= 0) {
            return null;
        }
        const targetProfit = Math.min(1, Math.max(0.01, roundRatio(item && item.target_profit ? item.target_profit : 0.15)));
        const stopLoss = Math.min(1, Math.max(0.01, roundRatio(item && item.stop_loss ? item.stop_loss : 0.08)));
        return {
            symbol,
            shares,
            avg_cost: avgCost,
            target_profit: targetProfit,
            stop_loss: stopLoss,
            notify: item && item.notify !== undefined ? Boolean(item.notify) : true,
            notes: String((item && item.notes) || "").trim() || null
        };
    }

    function sanitizeDraft(raw) {
        const base = defaultDraft();
        const source = raw && typeof raw === "object" ? raw : {};

        const watchlistMap = new Map();
        const rawWatchlist = Array.isArray(source.watchlist) ? source.watchlist : [];
        rawWatchlist.forEach((item) => {
            const normalized = sanitizeWatchlistItem(item);
            if (normalized) {
                watchlistMap.set(normalized.symbol, normalized);
            }
        });

        const portfolioMap = new Map();
        const rawPortfolio = Array.isArray(source.portfolio) ? source.portfolio : [];
        rawPortfolio.forEach((item) => {
            const normalized = sanitizePortfolioItem(item);
            if (normalized) {
                portfolioMap.set(normalized.symbol, normalized);
            }
        });

        return {
            cash: Math.max(0, roundMoney(source.cash)),
            currency: String(source.currency || base.currency).trim().toUpperCase() || base.currency,
            allowEmptyPortfolio: Boolean(source.allowEmptyPortfolio),
            watchlist: Array.from(watchlistMap.values()).sort((left, right) => left.symbol.localeCompare(right.symbol)),
            portfolio: Array.from(portfolioMap.values()).sort((left, right) => left.symbol.localeCompare(right.symbol)),
            remoteSummary: source.remoteSummary && typeof source.remoteSummary === "object" ? source.remoteSummary : null,
            lastSavedAt: source.lastSavedAt || null,
            lastSyncResponse: source.lastSyncResponse && typeof source.lastSyncResponse === "object" ? source.lastSyncResponse : null
        };
    }

    function loadDraft() {
        try {
            const raw = localStorage.getItem(draftStorageKey);
            return sanitizeDraft(raw ? JSON.parse(raw) : null);
        } catch (_error) {
            return defaultDraft();
        }
    }

    let draft = loadDraft();

    function portfolioCostBasis() {
        return roundMoney(draft.portfolio.reduce((sum, item) => sum + (numberOrZero(item.shares) * numberOrZero(item.avg_cost)), 0));
    }

    function estimatedTotalCapital() {
        return roundMoney(numberOrZero(draft.cash) + portfolioCostBasis());
    }

    function validationMessages() {
        const errors = [];
        if (draft.watchlist.length === 0) {
            errors.push("请至少添加 1 只订阅股票。");
        }
        if (estimatedTotalCapital() <= 0) {
            errors.push("现金与持仓成本合计必须大于 0。");
        }
        if (draft.portfolio.length === 0 && !draft.allowEmptyPortfolio) {
            errors.push("当前没有持仓时，请勾选“我当前是空仓”。");
        }
        return errors;
    }

    function setHtml(id, html) {
        const node = ui.byId(id);
        if (node) {
            node.innerHTML = html;
        }
    }

    function syncInputsFromDraft() {
        const cashInput = ui.byId("draft-cash-input");
        if (cashInput) {
            cashInput.value = draft.cash ? String(draft.cash) : "0";
        }
        const currencyInput = ui.byId("draft-currency-input");
        if (currencyInput) {
            currencyInput.value = draft.currency || "USD";
        }
        const allowEmptyInput = ui.byId("draft-allow-empty-portfolio");
        if (allowEmptyInput) {
            allowEmptyInput.checked = Boolean(draft.allowEmptyPortfolio);
        }
        const storedUser = ui.getStoredUser();
        if (storedUser && storedUser.email) {
            const authEmail = ui.byId("auth-email");
            const verifyEmail = ui.byId("verify-email");
            if (authEmail && !authEmail.value) {
                authEmail.value = storedUser.email;
            }
            if (verifyEmail && !verifyEmail.value) {
                verifyEmail.value = storedUser.email;
            }
        }
        const timezoneInput = ui.byId("verify-timezone");
        if (timezoneInput && !timezoneInput.value) {
            timezoneInput.value = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
        }
    }

    function renderSessionPanel() {
        const user = ui.getStoredUser();
        const remoteSummary = draft.remoteSummary || {};
        if (!user && !remoteSummary.email) {
            setHtml("subscriber-session-panel", '<div class="empty-state">登录后，这里会显示当前账号、套餐和最近一次云端同步状态。</div>');
            return;
        }

        const rows = [
            ["当前账号", user && user.email ? user.email : (remoteSummary.email || "未登录")],
            ["套餐", user && user.plan ? user.plan : (remoteSummary.plan || "未获取")],
            ["语言 / 时区", [user && user.locale, user && user.timezone].filter(Boolean).join(" / ") || [remoteSummary.locale, remoteSummary.timezone].filter(Boolean).join(" / ") || "未设置"],
            ["登录状态", ui.getAccessToken() ? "已保存登录令牌" : "未登录"],
            ["云端订阅状态", remoteSummary.subscriptionStatus || "未读取"],
            ["最近云端同步", formatDateTime(remoteSummary.lastSyncedAt)]
        ];

        const checklist = remoteSummary.checklist;
        const checklistHtml = checklist
            ? `
                <table>
                    <thead>
                        <tr>
                            <th>云端检查项</th>
                            <th>值</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td>已配置资金</td><td>${checklist.has_capital ? "是" : "否"}</td></tr>
                        <tr><td>云端订阅股票</td><td>${ui.escapeHtml(checklist.watchlist_count)}</td></tr>
                        <tr><td>云端持仓</td><td>${ui.escapeHtml(checklist.portfolio_count)}</td></tr>
                        <tr><td>推送设备</td><td>${ui.escapeHtml(checklist.push_device_count)}</td></tr>
                    </tbody>
                </table>
            `
            : "";

        setHtml(
            "subscriber-session-panel",
            `
                <table>
                    <thead>
                        <tr>
                            <th>项目</th>
                            <th>当前值</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows.map((row) => `<tr><td>${ui.escapeHtml(row[0])}</td><td>${ui.escapeHtml(row[1])}</td></tr>`).join("")}
                    </tbody>
                </table>
                ${checklistHtml}
            `
        );
    }

    function renderSyncNote() {
        const note = ui.byId("draft-sync-note");
        if (!note) {
            return;
        }
        const segments = [];
        if (draft.lastSavedAt) {
            segments.push(`最近保存：${formatDateTime(draft.lastSavedAt)}`);
        }
        if (draft.lastSyncResponse && draft.lastSyncResponse.syncedAt) {
            segments.push(`最近开始订阅：${formatDateTime(draft.lastSyncResponse.syncedAt)}`);
        }
        note.textContent = segments.length
            ? `${segments.join(" | ")} | 浏览器仍会保留离线草稿。`
            : "浏览器会自动保留草稿；只有“开始订阅”时才会把监控快照同步到服务端。";
    }

    function renderSummaryPanel() {
        const errors = validationMessages();
        const summaryRows = [
            ["订阅股票", draft.watchlist.length],
            ["已持仓股票", draft.portfolio.length],
            ["现金", `${formatNumber(draft.cash)} ${ui.escapeHtml(draft.currency)}`],
            ["持仓成本合计", `${formatNumber(portfolioCostBasis())} ${ui.escapeHtml(draft.currency)}`],
            ["估算总资产", `${formatNumber(estimatedTotalCapital())} ${ui.escapeHtml(draft.currency)}`],
            ["空仓启动", draft.allowEmptyPortfolio ? "允许" : "不允许"]
        ];

        const readinessHtml = errors.length
            ? `<div class="empty-state">开始订阅前还需要：${ui.escapeHtml(errors.join("；"))}</div>`
            : '<div class="status" data-tone="success">条件已满足，可以直接开始订阅。</div>';

        setHtml(
            "draft-summary-panel",
            `
                <table>
                    <thead>
                        <tr>
                            <th>草稿项</th>
                            <th>当前值</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${summaryRows.map((row) => `<tr><td>${ui.escapeHtml(row[0])}</td><td>${row[1]}</td></tr>`).join("")}
                    </tbody>
                </table>
                ${readinessHtml}
            `
        );
    }

    function renderWatchlistTable() {
        if (draft.watchlist.length === 0) {
            setHtml("draft-watchlist-table", '<div class="empty-state">还没有订阅股票。加入后，桌面端会把它们作为监控候选列表。</div>');
            return;
        }
        const rows = draft.watchlist.map((item) => `
            <tr>
                <td><strong>${ui.escapeHtml(item.symbol)}</strong></td>
                <td>${ui.escapeHtml(item.min_score)}</td>
                <td>${item.notify ? "开启" : "关闭"}</td>
                <td><button type="button" class="ghost" data-watchlist-remove="${ui.escapeHtml(item.symbol)}">删除</button></td>
            </tr>
        `).join("");
        setHtml(
            "draft-watchlist-table",
            `
                <table>
                    <thead>
                        <tr>
                            <th>代码</th>
                            <th>过滤分数</th>
                            <th>通知</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            `
        );
    }

    function fillPortfolioForm(item) {
        if (!item) {
            return;
        }
        const mapping = {
            "draft-portfolio-symbol": item.symbol,
            "draft-portfolio-shares": item.shares,
            "draft-portfolio-cost": item.avg_cost,
            "draft-portfolio-target": item.target_profit,
            "draft-portfolio-stop": item.stop_loss,
            "draft-portfolio-notes": item.notes || ""
        };
        Object.entries(mapping).forEach(([id, value]) => {
            const node = ui.byId(id);
            if (node) {
                node.value = value;
            }
        });
        const notifyNode = ui.byId("draft-portfolio-notify");
        if (notifyNode) {
            notifyNode.checked = Boolean(item.notify);
        }
        ui.setStatus("portfolio-draft-status", `已将 ${item.symbol} 填回表单，可直接修改后再次保存。`, "success");
    }

    function renderPortfolioTable() {
        if (draft.portfolio.length === 0) {
            setHtml("draft-portfolio-table", '<div class="empty-state">还没有已持仓股票。如果当前空仓，请在开始订阅前勾选“允许空仓启动”。</div>');
            return;
        }
        const rows = draft.portfolio.map((item) => `
            <tr>
                <td><strong>${ui.escapeHtml(item.symbol)}</strong></td>
                <td>${ui.escapeHtml(item.shares)}</td>
                <td>${formatNumber(item.avg_cost)}</td>
                <td>${formatNumber(roundMoney(item.shares * item.avg_cost))}</td>
                <td>${item.notify ? "开启" : "关闭"}</td>
                <td>
                    <button type="button" class="secondary" data-portfolio-edit="${ui.escapeHtml(item.symbol)}">编辑</button>
                    <button type="button" class="ghost" data-portfolio-remove="${ui.escapeHtml(item.symbol)}">删除</button>
                </td>
            </tr>
        `).join("");
        setHtml(
            "draft-portfolio-table",
            `
                <table>
                    <thead>
                        <tr>
                            <th>代码</th>
                            <th>数量</th>
                            <th>均价</th>
                            <th>持仓成本</th>
                            <th>通知</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            `
        );
    }

    function buildSubscriptionPayload() {
        const errors = validationMessages();
        if (errors.length) {
            throw new Error(errors.join("；"));
        }
        return {
            allow_empty_portfolio: draft.portfolio.length === 0 && Boolean(draft.allowEmptyPortfolio),
            account: {
                total_capital: estimatedTotalCapital(),
                currency: draft.currency || "USD"
            },
            watchlist: draft.watchlist.map((item) => ({
                symbol: item.symbol,
                min_score: item.min_score,
                notify: item.notify
            })),
            portfolio: draft.portfolio.map((item) => ({
                symbol: item.symbol,
                shares: item.shares,
                avg_cost: item.avg_cost,
                target_profit: item.target_profit,
                stop_loss: item.stop_loss,
                notify: item.notify,
                notes: item.notes
            }))
        };
    }

    function renderSubscriptionPanel() {
        const errors = validationMessages();
        const payload = {
            allow_empty_portfolio: draft.portfolio.length === 0 && Boolean(draft.allowEmptyPortfolio),
            account: {
                total_capital: estimatedTotalCapital(),
                currency: draft.currency || "USD"
            },
            watchlist: draft.watchlist,
            portfolio: draft.portfolio
        };
        const latestResponse = draft.lastSyncResponse
            ? `
                <h3>最近一次开始订阅结果</h3>
                <pre class="json-output">${ui.escapeHtml(JSON.stringify(draft.lastSyncResponse.response, null, 2))}</pre>
            `
            : "";

        setHtml(
            "subscription-sync-panel",
            `
                <table>
                    <thead>
                        <tr>
                            <th>同步项</th>
                            <th>当前值</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td>现金</td><td>${formatNumber(draft.cash)} ${ui.escapeHtml(draft.currency)}</td></tr>
                        <tr><td>持仓成本</td><td>${formatNumber(portfolioCostBasis())} ${ui.escapeHtml(draft.currency)}</td></tr>
                        <tr><td>估算总资产</td><td>${formatNumber(estimatedTotalCapital())} ${ui.escapeHtml(draft.currency)}</td></tr>
                        <tr><td>订阅股票数</td><td>${ui.escapeHtml(draft.watchlist.length)}</td></tr>
                        <tr><td>持仓数</td><td>${ui.escapeHtml(draft.portfolio.length)}</td></tr>
                    </tbody>
                </table>
                ${errors.length ? `<div class="empty-state">当前还不能开始订阅：${ui.escapeHtml(errors.join("；"))}</div>` : '<div class="status" data-tone="success">已具备开始订阅条件。</div>'}
                <h3>即将同步的请求</h3>
                <pre class="json-output">${ui.escapeHtml(JSON.stringify(payload, null, 2))}</pre>
                ${latestResponse}
            `
        );
    }

    function renderMetric(id, value) {
        const node = ui.byId(id);
        if (node) {
            node.textContent = String(value);
        }
    }

    function renderAll() {
        syncInputsFromDraft();
        renderMetric("draft-watchlist-count", draft.watchlist.length);
        renderMetric("draft-portfolio-count", draft.portfolio.length);
        renderMetric("draft-cash-amount", formatNumber(draft.cash));
        renderMetric("draft-total-assets", formatNumber(estimatedTotalCapital()));
        renderSessionPanel();
        renderSummaryPanel();
        renderWatchlistTable();
        renderPortfolioTable();
        renderSubscriptionPanel();
        renderSyncNote();
    }

    function persistDraft(options = {}) {
        draft = sanitizeDraft(draft);
        draft.lastSavedAt = new Date().toISOString();
        localStorage.setItem(draftStorageKey, JSON.stringify(draft));
        renderAll();
        if (!options.quiet) {
            ui.setStatus(options.statusId || "draft-status", options.message || "草稿已保存到当前浏览器。", options.tone || "success");
        }
    }

    function resetPortfolioForm() {
        const defaults = {
            "draft-portfolio-symbol": "",
            "draft-portfolio-shares": "10",
            "draft-portfolio-cost": "150",
            "draft-portfolio-target": "0.15",
            "draft-portfolio-stop": "0.08",
            "draft-portfolio-notes": ""
        };
        Object.entries(defaults).forEach(([id, value]) => {
            const node = ui.byId(id);
            if (node) {
                node.value = value;
            }
        });
        const notifyNode = ui.byId("draft-portfolio-notify");
        if (notifyNode) {
            notifyNode.checked = true;
        }
    }

    function parseBulkSymbols(raw) {
        const map = new Map();
        String(raw || "")
            .split(/[\\s,，；;]+/)
            .map((item) => normalizeSymbol(item))
            .filter(Boolean)
            .forEach((symbol) => {
                if (!map.has(symbol)) {
                    map.set(symbol, symbol);
                }
            });
        return Array.from(map.values());
    }

    function readRequiredPositiveInteger(id, label) {
        const raw = ui.readValue(id);
        const value = Number(raw);
        if (!Number.isInteger(value) || value <= 0) {
            throw new Error(`${label} 必须是正整数。`);
        }
        return value;
    }

    function readRequiredPositiveNumber(id, label) {
        const raw = ui.readValue(id);
        const value = Number(raw);
        if (!Number.isFinite(value) || value <= 0) {
            throw new Error(`${label} 必须大于 0。`);
        }
        return value;
    }

    async function requestProtected(method, path, options = {}) {
        return await ui.requestJson(method, ui.publicApi(path), {
            token: ui.requireAccessToken(),
            body: options.body
        });
    }

    const sendCodeForm = ui.byId("send-code-form");
    if (sendCodeForm) {
        sendCodeForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("auth-status", "正在发送验证码...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/auth/send-code"), {
                    body: { email: ui.readValue("auth-email") }
                });
                if (payload && payload.dev_code && ui.byId("verify-code")) {
                    ui.byId("verify-code").value = payload.dev_code;
                }
                if (ui.byId("verify-email")) {
                    ui.byId("verify-email").value = ui.readValue("auth-email");
                }
                ui.setStatus("auth-status", payload.message || "验证码已发送。", "success");
            } catch (error) {
                ui.setStatus("auth-status", error.message, "error");
            }
        });
    }

    const verifyForm = ui.byId("verify-form");
    if (verifyForm) {
        verifyForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("auth-status", "正在验证验证码...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/auth/verify"), {
                    body: {
                        email: ui.readValue("verify-email"),
                        code: ui.readValue("verify-code"),
                        locale: ui.readValue("verify-locale") || null,
                        timezone: ui.readValue("verify-timezone") || null
                    }
                });
                ui.setPublicSession(payload);
                renderAll();
                ui.setStatus("auth-status", "登录成功，当前浏览器已保存订阅会话。", "success");
            } catch (error) {
                ui.setStatus("auth-status", error.message, "error");
            }
        });
    }

    const refreshButton = ui.byId("refresh-session");
    if (refreshButton) {
        refreshButton.addEventListener("click", async () => {
            ui.setStatus("auth-status", "正在刷新会话...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/auth/refresh"), {
                    body: { refresh_token: ui.getRefreshToken() }
                });
                ui.setPublicSession(payload);
                renderAll();
                ui.setStatus("auth-status", "登录令牌已刷新。", "success");
            } catch (error) {
                ui.setStatus("auth-status", error.message, "error");
            }
        });
    }

    const logoutButton = ui.byId("logout-session");
    if (logoutButton) {
        logoutButton.addEventListener("click", async () => {
            ui.setStatus("auth-status", "正在退出登录...");
            try {
                await ui.requestJson("POST", ui.publicApi("/v1/auth/logout"), {
                    token: ui.requireAccessToken()
                });
                ui.clearPublicSession();
                renderAll();
                ui.setStatus("auth-status", "已退出登录，本地草稿仍然保留。", "success");
            } catch (error) {
                ui.setStatus("auth-status", error.message, "error");
            }
        });
    }

    const restoreRemoteDraftButton = ui.byId("restore-remote-draft");
    if (restoreRemoteDraftButton) {
        restoreRemoteDraftButton.addEventListener("click", async () => {
            ui.setStatus("auth-status", "正在从云端恢复资料...");
            try {
                const [profile, dashboard, watchlist, portfolio] = await Promise.all([
                    requestProtected("GET", "/v1/account/profile"),
                    requestProtected("GET", "/v1/account/dashboard"),
                    requestProtected("GET", "/v1/watchlist"),
                    requestProtected("GET", "/v1/portfolio")
                ]);
                const cloudPortfolio = Array.isArray(portfolio) ? portfolio : [];
                const costBasis = roundMoney(cloudPortfolio.reduce((sum, item) => sum + numberOrZero(item.total_capital || (item.shares * item.avg_cost)), 0));
                const availableCash = dashboard && dashboard.account && dashboard.account.available_cash !== undefined
                    ? roundMoney(dashboard.account.available_cash)
                    : Math.max(0, roundMoney(numberOrZero(profile && profile.account && profile.account.total_capital) - costBasis));

                draft = sanitizeDraft({
                    ...draft,
                    cash: availableCash,
                    currency: (profile && profile.account && profile.account.currency) || (dashboard && dashboard.account && dashboard.account.currency) || draft.currency,
                    allowEmptyPortfolio: cloudPortfolio.length === 0,
                    watchlist: (Array.isArray(watchlist) ? watchlist : []).map((item) => ({
                        symbol: item.symbol,
                        min_score: item.min_score,
                        notify: item.notify
                    })),
                    portfolio: cloudPortfolio.map((item) => ({
                        symbol: item.symbol,
                        shares: item.shares,
                        avg_cost: item.avg_cost,
                        target_profit: item.target_profit,
                        stop_loss: item.stop_loss,
                        notify: item.notify,
                        notes: item.notes
                    })),
                    remoteSummary: {
                        email: profile && profile.user ? profile.user.email : null,
                        plan: profile && profile.user ? profile.user.plan : null,
                        locale: profile && profile.user ? profile.user.locale : null,
                        timezone: profile && profile.user ? profile.user.timezone : null,
                        subscriptionStatus: dashboard && dashboard.subscription ? dashboard.subscription.status : null,
                        startedAt: dashboard && dashboard.subscription ? dashboard.subscription.started_at : null,
                        lastSyncedAt: dashboard && dashboard.subscription ? dashboard.subscription.last_synced_at : null,
                        lastSyncReason: dashboard && dashboard.subscription ? dashboard.subscription.last_sync_reason : null,
                        checklist: dashboard && dashboard.subscription ? dashboard.subscription.checklist : null,
                        restoredAt: new Date().toISOString()
                    }
                });
                persistDraft({ quiet: true });
                ui.setStatus("auth-status", "已把云端订阅资料恢复到本地草稿。", "success");
            } catch (error) {
                ui.setStatus("auth-status", error.message, "error");
            }
        });
    }

    const saveDraftButton = ui.byId("save-local-draft");
    if (saveDraftButton) {
        saveDraftButton.addEventListener("click", () => {
            persistDraft({ message: "本地订阅草稿已保存。", statusId: "draft-status" });
        });
    }

    const clearDraftButton = ui.byId("clear-local-draft");
    if (clearDraftButton) {
        clearDraftButton.addEventListener("click", () => {
            if (!window.confirm("确定清空当前浏览器里的订阅草稿吗？此操作不会删除云端数据。")) {
                return;
            }
            draft = defaultDraft();
            localStorage.removeItem(draftStorageKey);
            renderAll();
            ui.setStatus("draft-status", "本地订阅草稿已清空。", "success");
        });
    }

    const cashInput = ui.byId("draft-cash-input");
    if (cashInput) {
        cashInput.addEventListener("input", () => {
            draft.cash = Math.max(0, roundMoney(cashInput.value));
            persistDraft({ quiet: true });
        });
    }

    const currencyInput = ui.byId("draft-currency-input");
    if (currencyInput) {
        currencyInput.addEventListener("input", () => {
            draft.currency = String(currencyInput.value || "USD").trim().toUpperCase() || "USD";
            persistDraft({ quiet: true });
        });
    }

    const allowEmptyInput = ui.byId("draft-allow-empty-portfolio");
    if (allowEmptyInput) {
        allowEmptyInput.addEventListener("change", () => {
            draft.allowEmptyPortfolio = Boolean(allowEmptyInput.checked);
            persistDraft({ quiet: true });
        });
    }

    const watchlistForm = ui.byId("draft-watchlist-form");
    if (watchlistForm) {
        watchlistForm.addEventListener("submit", (event) => {
            event.preventDefault();
            try {
                const symbols = parseBulkSymbols(ui.readValue("draft-watchlist-symbols"));
                if (symbols.length === 0) {
                    throw new Error("请至少输入 1 个股票代码。支持逗号、空格或换行分隔。");
                }
                const minScore = Math.max(0, Math.min(100, Math.round(numberOrZero(ui.readValue("draft-watchlist-score")) || 65)));
                const notify = ui.readCheckbox("draft-watchlist-notify");
                const merged = new Map(draft.watchlist.map((item) => [item.symbol, item]));
                symbols.forEach((symbol) => {
                    merged.set(symbol, {
                        symbol,
                        min_score: minScore,
                        notify
                    });
                });
                draft.watchlist = Array.from(merged.values());
                const watchlistInput = ui.byId("draft-watchlist-symbols");
                if (watchlistInput) {
                    watchlistInput.value = "";
                }
                persistDraft({ message: `已加入 ${symbols.length} 只订阅股票。`, statusId: "watchlist-draft-status" });
            } catch (error) {
                ui.setStatus("watchlist-draft-status", error.message, "error");
            }
        });
    }

    const watchlistTable = ui.byId("draft-watchlist-table");
    if (watchlistTable) {
        watchlistTable.addEventListener("click", (event) => {
            const button = event.target.closest("[data-watchlist-remove]");
            if (!button) {
                return;
            }
            const symbol = normalizeSymbol(button.getAttribute("data-watchlist-remove"));
            draft.watchlist = draft.watchlist.filter((item) => item.symbol !== symbol);
            persistDraft({ message: `已从草稿删除 ${symbol}。`, statusId: "watchlist-draft-status" });
        });
    }

    const portfolioForm = ui.byId("draft-portfolio-form");
    if (portfolioForm) {
        portfolioForm.addEventListener("submit", (event) => {
            event.preventDefault();
            try {
                const item = sanitizePortfolioItem({
                    symbol: ui.readValue("draft-portfolio-symbol"),
                    shares: readRequiredPositiveInteger("draft-portfolio-shares", "持股数量"),
                    avg_cost: readRequiredPositiveNumber("draft-portfolio-cost", "持仓均价"),
                    target_profit: readRequiredPositiveNumber("draft-portfolio-target", "止盈目标"),
                    stop_loss: readRequiredPositiveNumber("draft-portfolio-stop", "止损阈值"),
                    notify: ui.readCheckbox("draft-portfolio-notify"),
                    notes: ui.readValue("draft-portfolio-notes")
                });
                if (!item) {
                    throw new Error("请完整填写有效的持仓信息。");
                }
                const merged = new Map(draft.portfolio.map((entry) => [entry.symbol, entry]));
                merged.set(item.symbol, item);
                draft.portfolio = Array.from(merged.values());
                persistDraft({ message: `已保存 ${item.symbol} 的持仓草稿。`, statusId: "portfolio-draft-status" });
                resetPortfolioForm();
            } catch (error) {
                ui.setStatus("portfolio-draft-status", error.message, "error");
            }
        });
    }

    const resetPortfolioButton = ui.byId("reset-portfolio-form");
    if (resetPortfolioButton) {
        resetPortfolioButton.addEventListener("click", () => {
            resetPortfolioForm();
            ui.setStatus("portfolio-draft-status", "持仓表单已重置。", "success");
        });
    }

    const portfolioTable = ui.byId("draft-portfolio-table");
    if (portfolioTable) {
        portfolioTable.addEventListener("click", (event) => {
            const editButton = event.target.closest("[data-portfolio-edit]");
            if (editButton) {
                const symbol = normalizeSymbol(editButton.getAttribute("data-portfolio-edit"));
                const item = draft.portfolio.find((entry) => entry.symbol === symbol);
                fillPortfolioForm(item);
                return;
            }
            const removeButton = event.target.closest("[data-portfolio-remove]");
            if (!removeButton) {
                return;
            }
            const symbol = normalizeSymbol(removeButton.getAttribute("data-portfolio-remove"));
            draft.portfolio = draft.portfolio.filter((item) => item.symbol !== symbol);
            persistDraft({ message: `已从草稿删除 ${symbol} 持仓。`, statusId: "portfolio-draft-status" });
        });
    }

    const startSubscriptionButton = ui.byId("start-subscription-button");
    if (startSubscriptionButton) {
        startSubscriptionButton.addEventListener("click", async () => {
            ui.setStatus("subscription-sync-status", "正在同步订阅快照...");
            try {
                const payload = buildSubscriptionPayload();
                const response = await requestProtected("POST", "/v1/account/start-subscription", { body: payload });
                draft.lastSyncResponse = {
                    syncedAt: new Date().toISOString(),
                    payload,
                    response
                };
                draft.remoteSummary = {
                    ...(draft.remoteSummary || {}),
                    email: (draft.remoteSummary && draft.remoteSummary.email) || (ui.getStoredUser() && ui.getStoredUser().email) || null,
                    plan: (draft.remoteSummary && draft.remoteSummary.plan) || (ui.getStoredUser() && ui.getStoredUser().plan) || null,
                    locale: (draft.remoteSummary && draft.remoteSummary.locale) || (ui.getStoredUser() && ui.getStoredUser().locale) || null,
                    timezone: (draft.remoteSummary && draft.remoteSummary.timezone) || (ui.getStoredUser() && ui.getStoredUser().timezone) || null,
                    subscriptionStatus: response && response.subscription ? response.subscription.status : "active",
                    lastSyncedAt: draft.lastSyncResponse.syncedAt,
                    lastSyncReason: response && response.message ? response.message : "订阅已开始",
                    checklist: response && response.subscription ? response.subscription.checklist : (draft.remoteSummary && draft.remoteSummary.checklist) || null
                };
                persistDraft({ quiet: true });
                ui.setStatus("subscription-sync-status", response.message || "订阅已开始，监控快照已同步。", "success");
            } catch (error) {
                ui.setStatus("subscription-sync-status", error.message, "error");
            }
        });
    }

    resetPortfolioForm();
    renderAll();
});
"""

_PLATFORM_SCRIPT = """
window.addEventListener("DOMContentLoaded", () => {
    const ui = window.stockPyUi;

    function endpoint(method, path, title, options = {}) {
        return {
            key: `${method} ${path}`,
            method,
            path,
            title,
            auth: options.auth || "none",
            notes: options.notes || "",
            pathParams: options.pathParams || null,
            query: options.query || null,
            body: options.body || null
        };
    }

    const PLATFORM_ENDPOINTS = [
        endpoint("POST", "/v1/auth/send-code", "发送用户验证码", {
            notes: "邮箱验证码登录第一步。",
            body: { email: "user@example.com" }
        }),
        endpoint("POST", "/v1/auth/verify", "验证验证码并换取会话", {
            notes: "成功后返回 access_token 与 refresh_token。",
            body: {
                email: "user@example.com",
                code: "123456",
                locale: "zh-CN",
                timezone: "Asia/Shanghai"
            }
        }),
        endpoint("POST", "/v1/auth/refresh", "刷新用户会话", {
            notes: "使用 refresh_token 获取新的 access_token。",
            body: { refresh_token: "paste-refresh-token" }
        }),
        endpoint("POST", "/v1/auth/logout", "退出用户会话", {
            auth: "optional",
            notes: "可携带 Bearer Token 与 refresh_token 一并注销。",
            body: { refresh_token: "paste-refresh-token" }
        }),
        endpoint("GET", "/v1/account/profile", "读取账户资料", {
            auth: "bearer"
        }),
        endpoint("GET", "/v1/account/dashboard", "读取账户仪表盘", {
            auth: "bearer"
        }),
        endpoint("PUT", "/v1/account/profile", "更新账户资料", {
            auth: "bearer",
            body: {
                display_name: "Nico",
                locale: "zh-CN",
                timezone: "Asia/Shanghai"
            }
        }),
        endpoint("POST", "/v1/account/start-subscription", "开始订阅并同步快照", {
            auth: "bearer",
            body: {
                allow_empty_portfolio: false,
                account: {
                    total_capital: 5000,
                    currency: "USD"
                },
                watchlist: [
                    {
                        symbol: "AAPL",
                        min_score: 70,
                        notify: true
                    }
                ],
                portfolio: [
                    {
                        symbol: "AAPL",
                        shares: 10,
                        avg_cost: 150,
                        target_profit: 0.2,
                        stop_loss: 0.08,
                        notify: true,
                        notes: "长期持有"
                    }
                ]
            }
        }),
        endpoint("GET", "/v1/watchlist", "读取观察列表", {
            auth: "bearer"
        }),
        endpoint("POST", "/v1/watchlist", "新增观察项", {
            auth: "bearer",
            body: {
                symbol: "TSLA",
                min_score: 70,
                notify: true
            }
        }),
        endpoint("PUT", "/v1/watchlist/{item_id}", "更新观察项", {
            auth: "bearer",
            pathParams: { item_id: 1 },
            body: {
                min_score: 80,
                notify: false
            }
        }),
        endpoint("DELETE", "/v1/watchlist/{item_id}", "删除观察项", {
            auth: "bearer",
            pathParams: { item_id: 1 }
        }),
        endpoint("GET", "/v1/portfolio", "读取持仓", {
            auth: "bearer"
        }),
        endpoint("POST", "/v1/portfolio", "新增持仓", {
            auth: "bearer",
            body: {
                symbol: "AAPL",
                shares: 10,
                avg_cost: 150,
                target_profit: 0.2,
                stop_loss: 0.08,
                notify: true,
                notes: "逢低建仓"
            }
        }),
        endpoint("PUT", "/v1/portfolio/{item_id}", "更新持仓", {
            auth: "bearer",
            pathParams: { item_id: 1 },
            body: {
                shares: 12,
                avg_cost: 148,
                notify: true,
                notes: "补仓"
            }
        }),
        endpoint("DELETE", "/v1/portfolio/{item_id}", "删除持仓", {
            auth: "bearer",
            pathParams: { item_id: 1 }
        }),
        endpoint("GET", "/v1/search/symbols", "搜索标的", {
            query: {
                q: "AAPL",
                limit: 20,
                type: "stock"
            }
        }),
        endpoint("GET", "/v1/notifications", "拉取通知列表", {
            auth: "bearer",
            query: {
                cursor: "",
                limit: 20
            }
        }),
        endpoint("GET", "/v1/notifications/push-devices", "读取推送设备", {
            auth: "bearer"
        }),
        endpoint("POST", "/v1/notifications/push-devices", "注册推送设备", {
            auth: "bearer",
            body: {
                device_id: "web-device-1",
                platform: "web",
                endpoint: "https://example.push/endpoint",
                p256dh: "base64-public-key",
                auth_secret: "base64-auth-secret"
            }
        }),
        endpoint("DELETE", "/v1/notifications/push-devices/{device_id}", "停用推送设备", {
            auth: "bearer",
            pathParams: { device_id: "web-device-1" }
        }),
        endpoint("POST", "/v1/notifications/push-devices/{device_id}/test", "发送推送测试", {
            auth: "bearer",
            pathParams: { device_id: "web-device-1" }
        }),
        endpoint("PUT", "/v1/notifications/read-all", "全部标记已读", {
            auth: "bearer"
        }),
        endpoint("PUT", "/v1/notifications/{notification_id}/read", "单条标记已读", {
            auth: "bearer",
            pathParams: { notification_id: "notif-123" }
        }),
        endpoint("PUT", "/v1/notifications/{notification_id}/ack", "确认单条通知", {
            auth: "bearer",
            pathParams: { notification_id: "notif-123" }
        }),
        endpoint("GET", "/v1/trades/{trade_id}/info", "读取公开交易信息", {
            auth: "public-token",
            pathParams: { trade_id: "trade-123" },
            query: { t: "token-123" }
        }),
        endpoint("GET", "/v1/trades/{trade_id}/app-info", "读取已登录交易信息", {
            auth: "bearer",
            pathParams: { trade_id: "trade-123" }
        }),
        endpoint("GET", "/v1/trades/{trade_id}/confirm", "读取公开确认页内容", {
            auth: "public-token",
            pathParams: { trade_id: "trade-123" },
            query: {
                action: "accept",
                t: "token-123"
            }
        }),
        endpoint("POST", "/v1/trades/{trade_id}/confirm", "公开确认交易", {
            auth: "public-token",
            pathParams: { trade_id: "trade-123" },
            query: {
                action: "accept",
                t: "token-123"
            }
        }),
        endpoint("POST", "/v1/trades/{trade_id}/ignore", "公开忽略交易", {
            auth: "public-token",
            pathParams: { trade_id: "trade-123" },
            query: { t: "token-123" }
        }),
        endpoint("POST", "/v1/trades/{trade_id}/adjust", "公开调整并确认交易", {
            auth: "public-token",
            pathParams: { trade_id: "trade-123" },
            query: { t: "token-123" },
            body: {
                actual_shares: 10,
                actual_price: 150
            }
        }),
        endpoint("POST", "/v1/trades/{trade_id}/app-confirm", "已登录确认交易", {
            auth: "bearer",
            pathParams: { trade_id: "trade-123" }
        }),
        endpoint("POST", "/v1/trades/{trade_id}/app-ignore", "已登录忽略交易", {
            auth: "bearer",
            pathParams: { trade_id: "trade-123" }
        }),
        endpoint("POST", "/v1/trades/{trade_id}/app-adjust", "已登录调整并确认交易", {
            auth: "bearer",
            pathParams: { trade_id: "trade-123" },
            body: {
                actual_shares: 10,
                actual_price: 150
            }
        })
    ];

    const endpointByKey = new Map(PLATFORM_ENDPOINTS.map((spec) => [spec.key, spec]));

    function authLabel(auth) {
        if (auth === "bearer") {
            return "Bearer";
        }
        if (auth === "public-token") {
            return "公开 Token";
        }
        if (auth === "optional") {
            return "可选 Bearer";
        }
        return "无需认证";
    }

    function scopeLabel(path) {
        const segments = String(path || "").split("/").filter(Boolean);
        if (segments.length < 2) {
            return "misc";
        }
        return segments[1];
    }

    function parseJsonInput(id, label) {
        const raw = ui.readValue(id);
        if (!raw) {
            return null;
        }
        try {
            return JSON.parse(raw);
        } catch (error) {
            throw new Error(`${label} 不是合法 JSON：${error.message}`);
        }
    }

    function parseJsonObjectInput(id, label) {
        const parsed = parseJsonInput(id, label);
        if (parsed === null) {
            return {};
        }
        if (typeof parsed !== "object" || Array.isArray(parsed)) {
            throw new Error(`${label} 必须是 JSON 对象。`);
        }
        return parsed;
    }

    function setJsonField(id, value) {
        const node = ui.byId(id);
        if (!node) {
            return;
        }
        if (value === null || value === undefined) {
            node.value = "";
            return;
        }
        if (typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === 0) {
            node.value = "";
            return;
        }
        node.value = JSON.stringify(value, null, 2);
    }

    function applyPathParams(pathTemplate, params) {
        return pathTemplate.replace(/\\{([^}]+)\\}/g, (_, name) => {
            const value = params[name];
            if (value === undefined || value === null || String(value).trim() === "") {
                throw new Error(`缺少路径参数 ${name}。`);
            }
            return encodeURIComponent(String(value));
        });
    }

    function buildQueryString(params) {
        const searchParams = new URLSearchParams();
        Object.entries(params || {}).forEach(([key, value]) => {
            if (value === undefined || value === null || value === "") {
                return;
            }
            if (Array.isArray(value)) {
                value.forEach((item) => {
                    if (item !== undefined && item !== null && item !== "") {
                        searchParams.append(key, String(item));
                    }
                });
                return;
            }
            searchParams.append(key, String(value));
        });
        return searchParams.toString();
    }

    function populatePlatformEndpointSelect() {
        const select = ui.byId("platform-endpoint-select");
        if (!select) {
            return;
        }
        select.innerHTML = PLATFORM_ENDPOINTS.map(
            (spec) => `<option value="${ui.escapeHtml(spec.key)}">${ui.escapeHtml(spec.key)} - ${ui.escapeHtml(spec.title)}</option>`
        ).join("");
        if (PLATFORM_ENDPOINTS.length > 0) {
            select.value = PLATFORM_ENDPOINTS[0].key;
        }
    }

    function currentEndpointSpec() {
        const selectedKey = ui.readValue("platform-endpoint-select");
        if (!selectedKey) {
            return PLATFORM_ENDPOINTS[0] || null;
        }
        return endpointByKey.get(selectedKey) || PLATFORM_ENDPOINTS[0] || null;
    }

    function fillEndpointConsole(spec) {
        if (!spec) {
            return;
        }
        const select = ui.byId("platform-endpoint-select");
        if (select) {
            select.value = spec.key;
        }
        setJsonField("platform-endpoint-path-params", spec.pathParams);
        setJsonField("platform-endpoint-query-params", spec.query);
        setJsonField("platform-endpoint-body", spec.body);
        setJsonField("platform-endpoint-headers", {});

        const tokenInput = ui.byId("platform-endpoint-token");
        if (tokenInput && !tokenInput.value) {
            if (spec.auth === "bearer") {
                tokenInput.placeholder = "留空则自动使用共享会话 access token";
            } else if (spec.auth === "optional") {
                tokenInput.placeholder = "可选：只在需要时填写 Bearer Token";
            } else {
                tokenInput.placeholder = "默认不需要 Bearer；如需覆盖可手动填写";
            }
        }
        ui.setStatus("platform-endpoint-console-status", `已选择 ${spec.key}。`, "success");
    }

    function renderPlatformEndpointMatrix() {
        const keyword = ui.readValue("platform-endpoint-filter").toLowerCase();
        const filtered = PLATFORM_ENDPOINTS.filter((spec) => {
            const haystack = [
                spec.method,
                spec.path,
                scopeLabel(spec.path),
                authLabel(spec.auth),
                spec.title,
                spec.notes
            ].join(" ").toLowerCase();
            return !keyword || haystack.includes(keyword);
        });

        const matrixNode = ui.byId("platform-endpoint-matrix");
        if (matrixNode) {
            if (!filtered.length) {
                matrixNode.innerHTML = '<div class="empty-state">没有匹配到端点，请调整筛选关键词。</div>';
            } else {
                const rows = filtered.map((spec) => `
                    <tr>
                        <td><strong>${ui.escapeHtml(spec.method)}</strong></td>
                        <td><code>${ui.escapeHtml(spec.path)}</code></td>
                        <td>${ui.escapeHtml(scopeLabel(spec.path))}</td>
                        <td>${ui.escapeHtml(authLabel(spec.auth))}</td>
                        <td>${ui.escapeHtml(spec.title)}</td>
                        <td><button type="button" class="secondary endpoint-pick" data-key="${ui.escapeHtml(spec.key)}">填入调试台</button></td>
                    </tr>
                `).join("");
                matrixNode.innerHTML = `
                    <table>
                        <thead>
                            <tr>
                                <th>方法</th>
                                <th>路径</th>
                                <th>能力域</th>
                                <th>认证</th>
                                <th>说明</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                `;
            }
        }

        const counts = filtered.reduce((acc, spec) => {
            acc[spec.method] = (acc[spec.method] || 0) + 1;
            return acc;
        }, {});
        const methodSummary = ["GET", "POST", "PUT", "PATCH", "DELETE"]
            .filter((method) => counts[method])
            .map((method) => `${method} ${counts[method]}`)
            .join(" | ");

        const summaryInput = ui.byId("platform-endpoint-summary");
        if (summaryInput) {
            summaryInput.value = `${filtered.length}/${PLATFORM_ENDPOINTS.length} 已显示${methodSummary ? ` | ${methodSummary}` : ""}`;
        }

        if (keyword) {
            ui.setStatus("platform-endpoint-status", `已筛选出 ${filtered.length} 个端点。`, "success");
        } else {
            ui.setStatus("platform-endpoint-status", `当前共 ${PLATFORM_ENDPOINTS.length} 个平台端点。`, "success");
        }
    }

    const searchForm = ui.byId("symbol-search-form");
    if (searchForm) {
        searchForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("search-status", "正在搜索标的...");
            try {
                const params = new URLSearchParams({
                    q: ui.readValue("search-query"),
                    limit: String(ui.readNumber("search-limit", 20))
                });
                const type = ui.readValue("search-type");
                if (type) {
                    params.set("type", type);
                }
                const payload = await ui.requestJson("GET", `${ui.publicApi("/v1/search/symbols")}?${params.toString()}`);
                ui.renderJson("search-output", payload);
                ui.renderSearchTable("search-results", payload.items || []);
                ui.setStatus("search-status", `已加载 ${(payload.items || []).length} 条搜索结果。`, "success");
            } catch (error) {
                ui.setStatus("search-status", error.message, "error");
            }
        });
    }

    const searchResults = ui.byId("search-results");
    if (searchResults) {
        searchResults.addEventListener("click", (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement) || !target.classList.contains("search-pick")) {
                return;
            }
            const symbol = target.dataset.symbol || "";
            if (ui.byId("platform-watchlist-symbol")) {
                ui.byId("platform-watchlist-symbol").value = symbol;
            }
            if (ui.byId("app-trade-id") && !ui.byId("app-trade-id").value) {
                ui.byId("app-trade-id").value = symbol;
            }
            ui.setStatus("platform-watchlist-status", `已将 ${symbol} 填入观察列表表单。`, "success");
        });
    }

    const showPlatformSessionButton = ui.byId("show-platform-session");
    if (showPlatformSessionButton) {
        showPlatformSessionButton.addEventListener("click", () => {
            ui.renderSessionSnapshot("platform-session-output");
            ui.setStatus("platform-session-status", "已显示共享公共会话快照。", "success");
        });
    }

    const clearPlatformSessionButton = ui.byId("clear-platform-session");
    if (clearPlatformSessionButton) {
        clearPlatformSessionButton.addEventListener("click", () => {
            ui.clearPublicSession();
            ui.renderSessionSnapshot("platform-session-output");
            ui.setStatus("platform-session-status", "已清除共享公共会话令牌。", "success");
        });
    }

    function readOptionalPositiveInteger(id, label) {
        const raw = ui.readValue(id);
        if (!raw) {
            return null;
        }
        const value = Number(raw);
        if (!Number.isInteger(value) || value <= 0) {
            throw new Error(`${label} 必须是正整数。`);
        }
        return value;
    }

    function readOptionalBooleanSelect(id) {
        const raw = ui.readValue(id);
        if (raw === "true") {
            return true;
        }
        if (raw === "false") {
            return false;
        }
        return null;
    }

    async function requestProtected(method, path, options = {}) {
        return await ui.requestJson(method, ui.publicApi(path), {
            token: ui.requireAccessToken(),
            body: options.body
        });
    }

    async function loadProtectedJson(path, outputId, statusId) {
        ui.setStatus(statusId, "正在加载...");
        try {
            const payload = await requestProtected("GET", path);
            ui.renderJson(outputId, payload);
            ui.setStatus(statusId, "加载成功。", "success");
            return payload;
        } catch (error) {
            ui.setStatus(statusId, error.message, "error");
            return null;
        }
    }

    const addWatchlistForm = ui.byId("platform-watchlist-form");
    if (addWatchlistForm) {
        addWatchlistForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("platform-watchlist-status", "正在创建观察项...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/watchlist"), {
                    token: ui.requireAccessToken(),
                    body: {
                        symbol: ui.readValue("platform-watchlist-symbol"),
                        min_score: ui.readNumber("platform-watchlist-score", 65),
                        notify: ui.readCheckbox("platform-watchlist-notify")
                    }
                });
                ui.renderJson("platform-watchlist-output", payload);
                ui.setStatus("platform-watchlist-status", `已将 ${payload.symbol || ui.readValue("platform-watchlist-symbol")} 加入观察列表。`, "success");
            } catch (error) {
                ui.setStatus("platform-watchlist-status", error.message, "error");
            }
        });
    }

    const loadPlatformWatchlistButton = ui.byId("platform-load-watchlist");
    if (loadPlatformWatchlistButton) {
        loadPlatformWatchlistButton.addEventListener("click", () => {
            loadProtectedJson("/v1/watchlist", "platform-watchlist-output", "platform-watchlist-status");
        });
    }

    const loadPlatformPortfolioButton = ui.byId("platform-load-portfolio");
    if (loadPlatformPortfolioButton) {
        loadPlatformPortfolioButton.addEventListener("click", () => {
            loadProtectedJson("/v1/portfolio", "platform-portfolio-output", "platform-portfolio-status");
        });
    }

    const addPlatformPortfolioForm = ui.byId("platform-portfolio-form");
    if (addPlatformPortfolioForm) {
        addPlatformPortfolioForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("platform-portfolio-status", "正在新增持仓...");
            try {
                const body = {
                    symbol: ui.readValue("platform-portfolio-symbol"),
                    shares: ui.readNumber("platform-portfolio-shares", 1),
                    avg_cost: ui.readNumber("platform-portfolio-avg-cost", 1),
                    target_profit: ui.readNumber("platform-portfolio-target", 0.15),
                    stop_loss: ui.readNumber("platform-portfolio-stop", 0.08),
                    notify: ui.readCheckbox("platform-portfolio-notify")
                };
                const notes = ui.readValue("platform-portfolio-notes");
                if (notes) {
                    body.notes = notes;
                }
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/portfolio"), {
                    token: ui.requireAccessToken(),
                    body
                });
                ui.renderJson("platform-portfolio-output", payload);
                ui.setStatus("platform-portfolio-status", `已新增 ${payload.symbol || body.symbol} 持仓。`, "success");
            } catch (error) {
                ui.setStatus("platform-portfolio-status", error.message, "error");
            }
        });
    }

    const updatePlatformWatchlistForm = ui.byId("platform-update-watchlist-form");
    if (updatePlatformWatchlistForm) {
        updatePlatformWatchlistForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("platform-maintenance-status", "正在更新观察项...");
            try {
                const itemId = readOptionalPositiveInteger("platform-watchlist-item-id", "观察项 ID");
                const body = {};
                const scoreRaw = ui.readValue("platform-watchlist-update-score");
                const notify = readOptionalBooleanSelect("platform-watchlist-update-notify");
                if (scoreRaw) body.min_score = ui.readNumber("platform-watchlist-update-score", 65);
                if (notify !== null) body.notify = notify;
                if (Object.keys(body).length === 0) {
                    throw new Error("提交前至少填写一项观察列表变更。");
                }
                const payload = await requestProtected("PUT", `/v1/watchlist/${itemId}`, { body });
                ui.renderJson("platform-maintenance-output", payload);
                ui.setStatus("platform-maintenance-status", "观察项已更新。", "success");
            } catch (error) {
                ui.setStatus("platform-maintenance-status", error.message, "error");
            }
        });
    }

    const deletePlatformWatchlistButton = ui.byId("platform-delete-watchlist-item");
    if (deletePlatformWatchlistButton) {
        deletePlatformWatchlistButton.addEventListener("click", async () => {
            ui.setStatus("platform-maintenance-status", "正在删除观察项...");
            try {
                const itemId = readOptionalPositiveInteger("platform-watchlist-item-id", "观察项 ID");
                await requestProtected("DELETE", `/v1/watchlist/${itemId}`);
                ui.renderJson("platform-maintenance-output", { message: `已删除观察项 ${itemId}。` });
                ui.setStatus("platform-maintenance-status", "观察项已删除。", "success");
            } catch (error) {
                ui.setStatus("platform-maintenance-status", error.message, "error");
            }
        });
    }

    const updatePlatformPortfolioForm = ui.byId("platform-update-portfolio-form");
    if (updatePlatformPortfolioForm) {
        updatePlatformPortfolioForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("platform-maintenance-status", "正在更新持仓...");
            try {
                const itemId = readOptionalPositiveInteger("platform-portfolio-item-id", "持仓条目 ID");
                const body = {};
                const sharesRaw = ui.readValue("platform-portfolio-update-shares");
                const avgCostRaw = ui.readValue("platform-portfolio-update-cost");
                const targetRaw = ui.readValue("platform-portfolio-update-target");
                const stopRaw = ui.readValue("platform-portfolio-update-stop");
                const notify = readOptionalBooleanSelect("platform-portfolio-update-notify");
                const notes = ui.readValue("platform-portfolio-update-notes");
                if (sharesRaw) body.shares = ui.readNumber("platform-portfolio-update-shares", 1);
                if (avgCostRaw) body.avg_cost = ui.readNumber("platform-portfolio-update-cost", 1);
                if (targetRaw) body.target_profit = ui.readNumber("platform-portfolio-update-target", 0.15);
                if (stopRaw) body.stop_loss = ui.readNumber("platform-portfolio-update-stop", 0.08);
                if (notify !== null) body.notify = notify;
                if (notes) body.notes = notes;
                if (Object.keys(body).length === 0) {
                    throw new Error("提交前至少填写一项持仓变更。");
                }
                const payload = await requestProtected("PUT", `/v1/portfolio/${itemId}`, { body });
                ui.renderJson("platform-maintenance-output", payload);
                ui.setStatus("platform-maintenance-status", "持仓已更新。", "success");
            } catch (error) {
                ui.setStatus("platform-maintenance-status", error.message, "error");
            }
        });
    }

    const deletePlatformPortfolioButton = ui.byId("platform-delete-portfolio-item");
    if (deletePlatformPortfolioButton) {
        deletePlatformPortfolioButton.addEventListener("click", async () => {
            ui.setStatus("platform-maintenance-status", "正在删除持仓...");
            try {
                const itemId = readOptionalPositiveInteger("platform-portfolio-item-id", "持仓条目 ID");
                await requestProtected("DELETE", `/v1/portfolio/${itemId}`);
                ui.renderJson("platform-maintenance-output", { message: `已删除持仓条目 ${itemId}。` });
                ui.setStatus("platform-maintenance-status", "持仓已删除。", "success");
            } catch (error) {
                ui.setStatus("platform-maintenance-status", error.message, "error");
            }
        });
    }

    const appTradeForm = ui.byId("app-trade-form");
    if (appTradeForm) {
        appTradeForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("trade-status", "正在加载已登录交易信息...");
            try {
                const tradeId = ui.readValue("app-trade-id");
                const payload = await requestProtected("GET", `/v1/trades/${encodeURIComponent(tradeId)}/app-info`);
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", `已加载 ${tradeId} 的应用交易信息。`, "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const appConfirmTradeButton = ui.byId("app-confirm-trade");
    if (appConfirmTradeButton) {
        appConfirmTradeButton.addEventListener("click", async () => {
            ui.setStatus("trade-status", "正在确认已登录交易...");
            try {
                const tradeId = ui.readValue("app-trade-id");
                const payload = await requestProtected("POST", `/v1/trades/${encodeURIComponent(tradeId)}/app-confirm`);
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", payload.message || "交易已确认。", "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const appIgnoreTradeButton = ui.byId("app-ignore-trade");
    if (appIgnoreTradeButton) {
        appIgnoreTradeButton.addEventListener("click", async () => {
            ui.setStatus("trade-status", "正在忽略已登录交易...");
            try {
                const tradeId = ui.readValue("app-trade-id");
                const payload = await requestProtected("POST", `/v1/trades/${encodeURIComponent(tradeId)}/app-ignore`);
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", payload.message || "交易已忽略。", "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const appAdjustTradeButton = ui.byId("app-adjust-trade");
    if (appAdjustTradeButton) {
        appAdjustTradeButton.addEventListener("click", async () => {
            ui.setStatus("trade-status", "正在记录已登录交易调整...");
            try {
                const tradeId = ui.readValue("app-trade-id");
                const payload = await requestProtected("POST", `/v1/trades/${encodeURIComponent(tradeId)}/app-adjust`, {
                    body: {
                        actual_shares: ui.readNumber("app-adjust-shares", 1),
                        actual_price: ui.readNumber("app-adjust-price", 1)
                    }
                });
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", payload.message || "交易调整已记录。", "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const publicTradeForm = ui.byId("public-trade-form");
    if (publicTradeForm) {
        publicTradeForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("trade-status", "正在加载公开交易信息...");
            try {
                const tradeId = ui.readValue("public-trade-id");
                const token = ui.readValue("public-trade-token");
                const params = new URLSearchParams({ t: token });
                const payload = await ui.requestJson(
                    "GET",
                    `${ui.publicApi(`/v1/trades/${encodeURIComponent(tradeId)}/info`)}?${params.toString()}`
                );
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", `已加载 ${tradeId} 的公开交易信息。`, "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const publicConfirmTradeButton = ui.byId("public-confirm-trade");
    if (publicConfirmTradeButton) {
        publicConfirmTradeButton.addEventListener("click", async () => {
            ui.setStatus("trade-status", "正在通过公开链接确认交易...");
            try {
                const tradeId = ui.readValue("public-trade-id");
                const token = ui.readValue("public-trade-token");
                const params = new URLSearchParams({ action: "accept", t: token });
                const payload = await ui.requestJson(
                    "POST",
                    `${ui.publicApi(`/v1/trades/${encodeURIComponent(tradeId)}/confirm`)}?${params.toString()}`
                );
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", payload.message || "公开交易已确认。", "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const publicIgnoreTradeButton = ui.byId("public-ignore-trade");
    if (publicIgnoreTradeButton) {
        publicIgnoreTradeButton.addEventListener("click", async () => {
            ui.setStatus("trade-status", "正在通过公开链接忽略交易...");
            try {
                const tradeId = ui.readValue("public-trade-id");
                const token = ui.readValue("public-trade-token");
                const params = new URLSearchParams({ t: token });
                const payload = await ui.requestJson(
                    "POST",
                    `${ui.publicApi(`/v1/trades/${encodeURIComponent(tradeId)}/ignore`)}?${params.toString()}`
                );
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", payload.message || "公开交易已忽略。", "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const publicAdjustTradeButton = ui.byId("public-adjust-trade");
    if (publicAdjustTradeButton) {
        publicAdjustTradeButton.addEventListener("click", async () => {
            ui.setStatus("trade-status", "正在通过公开链接记录调整...");
            try {
                const tradeId = ui.readValue("public-trade-id");
                const token = ui.readValue("public-trade-token");
                const params = new URLSearchParams({ t: token });
                const payload = await ui.requestJson(
                    "POST",
                    `${ui.publicApi(`/v1/trades/${encodeURIComponent(tradeId)}/adjust`)}?${params.toString()}`,
                    {
                        body: {
                            actual_shares: ui.readNumber("public-adjust-shares", 1),
                            actual_price: ui.readNumber("public-adjust-price", 1)
                        }
                    }
                );
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", payload.message || "公开交易调整已记录。", "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const endpointFilterInput = ui.byId("platform-endpoint-filter");
    if (endpointFilterInput) {
        endpointFilterInput.addEventListener("input", () => {
            renderPlatformEndpointMatrix();
        });
    }

    const endpointMatrix = ui.byId("platform-endpoint-matrix");
    if (endpointMatrix) {
        endpointMatrix.addEventListener("click", (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement) || !target.classList.contains("endpoint-pick")) {
                return;
            }
            const key = target.dataset.key || "";
            const spec = endpointByKey.get(key);
            if (!spec) {
                return;
            }
            fillEndpointConsole(spec);
        });
    }

    const endpointSelect = ui.byId("platform-endpoint-select");
    if (endpointSelect) {
        endpointSelect.addEventListener("change", () => {
            fillEndpointConsole(currentEndpointSpec());
        });
    }

    const endpointConsoleForm = ui.byId("platform-endpoint-console-form");
    if (endpointConsoleForm) {
        endpointConsoleForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const spec = currentEndpointSpec();
            if (!spec) {
                return;
            }
            ui.setStatus("platform-endpoint-console-status", `正在请求 ${spec.key} ...`);
            try {
                const pathParams = parseJsonObjectInput("platform-endpoint-path-params", "路径参数");
                const queryParams = parseJsonObjectInput("platform-endpoint-query-params", "查询参数");
                const headers = parseJsonObjectInput("platform-endpoint-headers", "附加请求头");
                const body = parseJsonInput("platform-endpoint-body", "请求体");

                const resolvedPath = applyPathParams(spec.path, pathParams);
                const queryString = buildQueryString(queryParams);
                const url = queryString
                    ? `${ui.publicApi(resolvedPath)}?${queryString}`
                    : ui.publicApi(resolvedPath);

                const manualToken = ui.readValue("platform-endpoint-token");
                const requestOptions = { headers };
                if (spec.auth === "bearer") {
                    requestOptions.token = manualToken || ui.requireAccessToken();
                } else if (manualToken) {
                    requestOptions.token = manualToken;
                }
                if (body !== null) {
                    requestOptions.body = body;
                }

                const payload = await ui.requestJson(spec.method, url, requestOptions);
                ui.renderJson(
                    "platform-endpoint-output",
                    payload === null ? { message: "请求成功（无响应体）。" } : payload
                );
                ui.setStatus("platform-endpoint-console-status", `${spec.key} 请求成功。`, "success");
            } catch (error) {
                ui.setStatus("platform-endpoint-console-status", error.message, "error");
            }
        });
    }

    const resetEndpointConsoleButton = ui.byId("platform-endpoint-reset");
    if (resetEndpointConsoleButton) {
        resetEndpointConsoleButton.addEventListener("click", () => {
            const first = PLATFORM_ENDPOINTS[0] || null;
            if (first) {
                fillEndpointConsole(first);
            }
            const tokenInput = ui.byId("platform-endpoint-token");
            if (tokenInput) {
                tokenInput.value = "";
            }
            ui.renderJson("platform-endpoint-output", "");
            ui.setStatus("platform-endpoint-console-status", "调试台已重置。", "success");
        });
    }

    populatePlatformEndpointSelect();
    renderPlatformEndpointMatrix();
    fillEndpointConsole(currentEndpointSpec());

    ui.renderSessionSnapshot("platform-session-output");
});
"""

_ADMIN_SCRIPT = """
window.addEventListener("DOMContentLoaded", () => {
    const ui = window.stockPyUi;

    function syncAdminSessionFields() {
        if (ui.byId("admin-token")) {
            ui.byId("admin-token").value = ui.getAdminToken();
        }
        if (ui.byId("admin-operator-id")) {
            ui.byId("admin-operator-id").value = ui.getAdminOperatorId();
        }
    }

    function parseCommaSeparated(raw) {
        return String(raw || "")
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean);
    }

    function parsePositiveIntegers(raw) {
        return [...new Set(
            parseCommaSeparated(raw)
                .map((value) => Number(value))
                .filter((value) => Number.isInteger(value) && value > 0)
        )];
    }

    function parsePositiveNumberList(raw, label) {
        return [...new Set(
            parseCommaSeparated(raw)
                .map((value) => Number(value))
                .filter((value) => Number.isFinite(value) && value > 0)
        )];
    }

    function readOptionalPositiveInteger(id, label) {
        const raw = ui.readValue(id);
        if (!raw) {
            return null;
        }
        const value = Number(raw);
        if (!Number.isInteger(value) || value <= 0) {
            throw new Error(`${label} 必须是正整数。`);
        }
        return value;
    }

    function readOptionalBooleanSelect(id) {
        const raw = ui.readValue(id);
        if (raw === "true") {
            return true;
        }
        if (raw === "false") {
            return false;
        }
        return null;
    }

    function buildQueryString(entries) {
        const params = new URLSearchParams();
        for (const [key, value] of entries) {
            if (value !== null && value !== undefined && value !== "") {
                params.set(key, String(value));
            }
        }
        return params.toString();
    }

    function parseOptionalJson(raw, label) {
        if (!String(raw || "").trim()) {
            return null;
        }
        try {
            return JSON.parse(raw);
        } catch (_error) {
            throw new Error(`${label} 必须是有效 JSON。`);
        }
    }

    syncAdminSessionFields();
    if (ui.byId("admin-verify-timezone") && !ui.byId("admin-verify-timezone").value) {
        ui.byId("admin-verify-timezone").value = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    }

    const sendCodeForm = ui.byId("admin-send-code-form");
    if (sendCodeForm) {
        sendCodeForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("admin-auth-status", "正在发送管理验证码...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/admin-auth/send-code"), {
                    body: { email: ui.readValue("admin-auth-email") }
                });
                if (payload && payload.dev_code && ui.byId("admin-verify-code")) {
                    ui.byId("admin-verify-code").value = payload.dev_code;
                }
                if (ui.byId("admin-verify-email")) {
                    ui.byId("admin-verify-email").value = ui.readValue("admin-auth-email");
                }
                ui.renderJson("admin-auth-output", payload);
                ui.setStatus("admin-auth-status", payload.message || "管理验证码已发送。", "success");
            } catch (error) {
                ui.setStatus("admin-auth-status", error.message, "error");
            }
        });
    }

    const verifyForm = ui.byId("admin-verify-form");
    if (verifyForm) {
        verifyForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("admin-auth-status", "正在验证管理验证码...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/admin-auth/verify"), {
                    body: {
                        email: ui.readValue("admin-verify-email"),
                        code: ui.readValue("admin-verify-code"),
                        locale: ui.readValue("admin-verify-locale") || null,
                        timezone: ui.readValue("admin-verify-timezone") || null
                    }
                });
                ui.setAdminSession(payload);
                syncAdminSessionFields();
                ui.renderJson("admin-auth-output", payload);
                ui.renderSessionSnapshot("admin-session-output");
                ui.setStatus("admin-auth-status", "管理会话已保存到本地。", "success");
            } catch (error) {
                ui.setStatus("admin-auth-status", error.message, "error");
            }
        });
    }

    const refreshButton = ui.byId("refresh-admin-session");
    if (refreshButton) {
        refreshButton.addEventListener("click", async () => {
            ui.setStatus("admin-auth-status", "正在刷新管理会话...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/admin-auth/refresh"), {
                    body: { refresh_token: ui.getAdminRefreshToken() }
                });
                ui.setAdminSession(payload);
                syncAdminSessionFields();
                ui.renderJson("admin-auth-output", payload);
                ui.renderSessionSnapshot("admin-session-output");
                ui.setStatus("admin-auth-status", "管理会话已刷新。", "success");
            } catch (error) {
                ui.setStatus("admin-auth-status", error.message, "error");
            }
        });
    }

    const logoutButton = ui.byId("logout-admin-session");
    if (logoutButton) {
        logoutButton.addEventListener("click", async () => {
            ui.setStatus("admin-auth-status", "正在退出管理会话...");
            try {
                await ui.requestJson("POST", ui.publicApi("/v1/admin-auth/logout"), {
                    token: ui.requireAdminToken(),
                    body: { refresh_token: ui.getAdminRefreshToken() || null }
                });
                ui.clearAdminSession();
                syncAdminSessionFields();
                ui.renderJson("admin-auth-output", { message: "已成功退出登录" });
                ui.renderSessionSnapshot("admin-session-output");
                ui.setStatus("admin-auth-status", "管理会话已清除。", "success");
            } catch (error) {
                ui.setStatus("admin-auth-status", error.message, "error");
            }
        });
    }

    const saveTokenButton = ui.byId("save-admin-token");
    if (saveTokenButton) {
        saveTokenButton.addEventListener("click", () => {
            ui.clearAdminSession();
            const token = ui.setAdminToken(ui.readValue("admin-token"));
            const operatorId = ui.setAdminOperatorId(ui.readValue("admin-operator-id"));
            syncAdminSessionFields();
            ui.renderSessionSnapshot("admin-session-output");
            const message = token
                ? `已保存手动管理 Bearer Token（${token.length} 个字符）。${operatorId ? `操作员专用路由将使用操作员 ID ${operatorId}。` : ""}`
                : "已清除管理 Bearer Token。";
            ui.setStatus(
                "admin-auth-status",
                message,
                "success"
            );
        });
    }

    const clearTokenButton = ui.byId("clear-admin-session");
    if (clearTokenButton) {
        clearTokenButton.addEventListener("click", () => {
            ui.clearAdminSession();
            syncAdminSessionFields();
            ui.renderSessionSnapshot("admin-session-output");
            ui.setStatus("admin-auth-status", "已清除缓存的管理会话状态。", "success");
        });
    }

    const showAdminSessionButton = ui.byId("show-admin-session");
    if (showAdminSessionButton) {
        showAdminSessionButton.addEventListener("click", () => {
            ui.renderSessionSnapshot("admin-session-output");
            ui.setStatus("admin-session-status", "已显示当前 UI 的接口地址与令牌状态。", "success");
        });
    }

    function readWindowHours() {
        return ui.readNumber("admin-window-hours", 24);
    }

    async function requestAdmin(method, path, options = {}) {
        return await ui.requestJson(method, ui.adminApi(path), {
            token: ui.requireAdminToken(),
            operatorId: options.operatorRequired
                ? ui.requireAdminOperatorId()
                : options.operatorId,
            body: options.body
        });
    }

    async function loadAdminJson(path, outputId, statusId) {
        ui.setStatus(statusId, "正在加载...");
        try {
            const payload = await requestAdmin("GET", path);
            ui.renderJson(outputId, payload);
            ui.setStatus(statusId, "加载成功。", "success");
        } catch (error) {
            ui.setStatus(statusId, error.message, "error");
        }
    }

    const loadOperatorsButton = ui.byId("load-operators");
    if (loadOperatorsButton) {
        loadOperatorsButton.addEventListener("click", () => {
            const params = new URLSearchParams();
            const query = ui.readValue("admin-operators-query");
            const role = ui.readValue("admin-operators-role");
            const isActive = ui.readValue("admin-operators-active");
            if (query) {
                params.set("query", query);
            }
            if (role) {
                params.set("role", role);
            }
            if (isActive) {
                params.set("is_active", isActive);
            }
            params.set("limit", String(ui.readNumber("admin-operators-limit", 25)));
            loadAdminJson(`/v1/admin/operators?${params.toString()}`, "admin-operators-output", "admin-operators-status");
        });
    }

    const upsertOperatorForm = ui.byId("upsert-operator-form");
    if (upsertOperatorForm) {
        upsertOperatorForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("admin-operators-status", "正在保存操作员权限...");
            try {
                const userId = Number(ui.readValue("admin-operator-user-id"));
                if (!Number.isInteger(userId) || userId <= 0) {
                    throw new Error("操作员用户 ID 必须是正整数。");
                }

                const body = {};
                const role = ui.readValue("admin-operator-role");
                const scopes = parseCommaSeparated(ui.readValue("admin-operator-scopes"));
                const activeState = ui.readValue("admin-operator-is-active");

                if (role) {
                    body.role = role;
                }
                if (scopes.length > 0) {
                    body.scopes = scopes;
                }
                if (activeState === "true" || activeState === "false") {
                    body.is_active = activeState === "true";
                }
                if (Object.keys(body).length === 0) {
                    throw new Error("提交前至少填写一项操作员变更。");
                }

                const payload = await ui.requestJson("PUT", ui.adminApi(`/v1/admin/operators/${userId}`), {
                    token: ui.requireAdminToken(),
                    operatorId: ui.getAdminOperatorId() || undefined,
                    body
                });
                ui.renderJson("admin-operators-output", payload);
                ui.setStatus("admin-operators-status", "操作员权限已更新。", "success");
            } catch (error) {
                ui.setStatus("admin-operators-status", error.message, "error");
            }
        });
    }

    const manualDistributionForm = ui.byId("manual-distribution-form");
    if (manualDistributionForm) {
        manualDistributionForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("admin-distribution-status", "正在排入手动分发...");
            try {
                const userIds = parsePositiveIntegers(ui.readValue("distribution-user-ids"));
                if (userIds.length === 0) {
                    throw new Error("至少提供一个目标用户 ID。");
                }

                const channels = [];
                if (ui.readCheckbox("distribution-channel-email")) {
                    channels.push("email");
                }
                if (ui.readCheckbox("distribution-channel-push")) {
                    channels.push("push");
                }
                if (channels.length === 0) {
                    throw new Error("至少选择一个投递渠道。");
                }

                const payload = await ui.requestJson("POST", ui.adminApi("/v1/admin/distribution/manual-message"), {
                    token: ui.requireAdminToken(),
                    operatorId: ui.requireAdminOperatorId(),
                    body: {
                        user_ids: userIds,
                        title: ui.readValue("distribution-title"),
                        body: ui.readValue("distribution-body"),
                        channels,
                        notification_type: ui.readValue("distribution-type") || "manual.message",
                        ack_required: ui.readCheckbox("distribution-ack-required"),
                        ack_deadline_at: ui.readValue("distribution-ack-deadline") || null,
                        metadata: parseOptionalJson(ui.readValue("distribution-metadata"), "分发元数据")
                    }
                });
                ui.renderJson("admin-distribution-output", payload);
                ui.setStatus("admin-distribution-status", "手动分发已排入队列。", "success");
            } catch (error) {
                ui.setStatus("admin-distribution-status", error.message, "error");
            }
        });
    }

    const loadTaskReceiptsButton = ui.byId("load-task-receipts");
    if (loadTaskReceiptsButton) {
        loadTaskReceiptsButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["follow_up_status", ui.readValue("task-receipts-follow-up-status")],
                ["delivery_status", ui.readValue("task-receipts-delivery-status")],
                ["ack_required", readOptionalBooleanSelect("task-receipts-ack-required")],
                ["overdue_only", ui.readCheckbox("task-receipts-overdue-only") ? true : ""],
                ["user_id", readOptionalPositiveInteger("task-receipts-user-id", "回执用户 ID")],
                ["notification_id", ui.readValue("task-receipts-notification-id")],
                ["limit", ui.readNumber("task-receipts-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/tasks/receipts${query ? `?${query}` : ""}`, "admin-task-receipts-output", "admin-task-receipts-status");
        });
    }

    const escalateTaskReceiptsButton = ui.byId("escalate-task-receipts");
    if (escalateTaskReceiptsButton) {
        escalateTaskReceiptsButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-receipts-status", "正在升级超时回执...");
            try {
                const query = buildQueryString([["limit", ui.readNumber("task-receipts-limit", 25)]]);
                const payload = await requestAdmin("POST", `/v1/admin/tasks/receipts/escalate-overdue?${query}`);
                ui.renderJson("admin-task-receipts-output", payload);
                ui.setStatus("admin-task-receipts-status", "超时回执已处理。", "success");
            } catch (error) {
                ui.setStatus("admin-task-receipts-status", error.message, "error");
            }
        });
    }

    const ackTaskReceiptButton = ui.byId("ack-task-receipt");
    if (ackTaskReceiptButton) {
        ackTaskReceiptButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-receipts-status", "正在确认回执...");
            try {
                const receiptId = ui.readValue("task-receipt-id");
                const payload = await requestAdmin("POST", "/v1/admin/tasks/receipts/ack", {
                    body: { receipt_id: receiptId }
                });
                ui.renderJson("admin-task-receipts-output", payload);
                ui.setStatus("admin-task-receipts-status", payload.message || "回执已确认。", "success");
            } catch (error) {
                ui.setStatus("admin-task-receipts-status", error.message, "error");
            }
        });
    }

    const claimTaskReceiptButton = ui.byId("claim-task-receipt");
    if (claimTaskReceiptButton) {
        claimTaskReceiptButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-receipts-status", "正在领取回执跟进...");
            try {
                const receiptId = ui.readValue("task-receipt-id");
                const payload = await requestAdmin("POST", `/v1/admin/tasks/receipts/${encodeURIComponent(receiptId)}/claim`);
                ui.renderJson("admin-task-receipts-output", payload);
                ui.setStatus("admin-task-receipts-status", payload.message || "回执跟进已领取。", "success");
            } catch (error) {
                ui.setStatus("admin-task-receipts-status", error.message, "error");
            }
        });
    }

    const resolveTaskReceiptButton = ui.byId("resolve-task-receipt");
    if (resolveTaskReceiptButton) {
        resolveTaskReceiptButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-receipts-status", "正在解决回执跟进...");
            try {
                const receiptId = ui.readValue("task-receipt-id");
                const payload = await requestAdmin("POST", `/v1/admin/tasks/receipts/${encodeURIComponent(receiptId)}/resolve`);
                ui.renderJson("admin-task-receipts-output", payload);
                ui.setStatus("admin-task-receipts-status", payload.message || "回执跟进已解决。", "success");
            } catch (error) {
                ui.setStatus("admin-task-receipts-status", error.message, "error");
            }
        });
    }

    const loadTaskOutboxButton = ui.byId("load-task-outbox");
    if (loadTaskOutboxButton) {
        loadTaskOutboxButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["channel", ui.readValue("task-outbox-channel")],
                ["status", ui.readValue("task-outbox-status")],
                ["user_id", readOptionalPositiveInteger("task-outbox-user-id", "发件箱用户 ID")],
                ["notification_id", ui.readValue("task-outbox-notification-id")],
                ["limit", ui.readNumber("task-outbox-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/tasks/outbox${query ? `?${query}` : ""}`, "admin-task-outbox-output", "admin-task-outbox-status");
        });
    }

    const releaseTaskOutboxButton = ui.byId("release-task-outbox");
    if (releaseTaskOutboxButton) {
        releaseTaskOutboxButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-outbox-status", "正在释放陈旧发件箱任务...");
            try {
                const query = buildQueryString([
                    ["channel", ui.readValue("task-outbox-channel")],
                    ["older_than_minutes", ui.readNumber("task-outbox-older-minutes", 15)],
                    ["limit", ui.readNumber("task-outbox-limit", 25)]
                ]);
                const payload = await requestAdmin("POST", `/v1/admin/tasks/outbox/release-stale?${query}`);
                ui.renderJson("admin-task-outbox-output", payload);
                ui.setStatus("admin-task-outbox-status", payload.message || "已释放陈旧发件箱消息。", "success");
            } catch (error) {
                ui.setStatus("admin-task-outbox-status", error.message, "error");
            }
        });
    }

    const requeueTaskOutboxButton = ui.byId("requeue-task-outbox");
    if (requeueTaskOutboxButton) {
        requeueTaskOutboxButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-outbox-status", "正在重新入队发件箱消息...");
            try {
                const outboxId = ui.readValue("task-outbox-id");
                const payload = await requestAdmin("POST", `/v1/admin/tasks/outbox/${encodeURIComponent(outboxId)}/requeue`);
                ui.renderJson("admin-task-outbox-output", payload);
                ui.setStatus("admin-task-outbox-status", payload.message || "发件箱消息已重新入队。", "success");
            } catch (error) {
                ui.setStatus("admin-task-outbox-status", error.message, "error");
            }
        });
    }

    const retryTaskOutboxButton = ui.byId("retry-task-outbox");
    if (retryTaskOutboxButton) {
        retryTaskOutboxButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-outbox-status", "正在重新入队所选发件箱消息...");
            try {
                const outboxIds = parseCommaSeparated(ui.readValue("task-outbox-ids"));
                if (outboxIds.length === 0) {
                    throw new Error("至少提供一个发件箱 ID。");
                }
                const payload = await requestAdmin("POST", "/v1/admin/tasks/outbox/retry", {
                    body: { outbox_ids: outboxIds }
                });
                ui.renderJson("admin-task-outbox-output", payload);
                ui.setStatus("admin-task-outbox-status", payload.message || "发件箱消息已重新入队。", "success");
            } catch (error) {
                ui.setStatus("admin-task-outbox-status", error.message, "error");
            }
        });
    }

    const loadTaskTradesButton = ui.byId("load-task-trades");
    if (loadTaskTradesButton) {
        loadTaskTradesButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["status", ui.readValue("task-trades-status")],
                ["action", ui.readValue("task-trades-action")],
                ["expired_only", ui.readCheckbox("task-trades-expired-only") ? true : ""],
                ["claimed_only", ui.readCheckbox("task-trades-claimed-only") ? true : ""],
                ["claimed_by_operator_id", readOptionalPositiveInteger("task-trades-claimed-by", "领取操作员 ID")],
                ["user_id", readOptionalPositiveInteger("task-trades-user-id", "交易用户 ID")],
                ["symbol", ui.readValue("task-trades-symbol")],
                ["limit", ui.readNumber("task-trades-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/tasks/trades${query ? `?${query}` : ""}`, "admin-task-trades-output", "admin-task-trades-status");
        });
    }

    const claimTaskTradesButton = ui.byId("claim-task-trades");
    if (claimTaskTradesButton) {
        claimTaskTradesButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-trades-status", "正在领取交易任务...");
            try {
                const body = {
                    trade_ids: parseCommaSeparated(ui.readValue("task-trades-ids")) || null,
                    limit: ui.readNumber("task-trades-limit", 25),
                    user_id: readOptionalPositiveInteger("task-trades-user-id", "交易用户 ID"),
                    symbol: ui.readValue("task-trades-symbol") || null
                };
                if (!body.trade_ids || body.trade_ids.length === 0) {
                    body.trade_ids = null;
                }
                const payload = await requestAdmin("POST", "/v1/admin/tasks/trades/claim", {
                    operatorRequired: true,
                    body
                });
                ui.renderJson("admin-task-trades-output", payload);
                ui.setStatus("admin-task-trades-status", payload.message || "交易任务已领取。", "success");
            } catch (error) {
                ui.setStatus("admin-task-trades-status", error.message, "error");
            }
        });
    }

    const expireTaskTradesButton = ui.byId("expire-task-trades");
    if (expireTaskTradesButton) {
        expireTaskTradesButton.addEventListener("click", async () => {
            ui.setStatus("admin-task-trades-status", "正在将交易任务设为过期...");
            try {
                const body = {
                    trade_ids: parseCommaSeparated(ui.readValue("task-trades-ids")) || null,
                    limit: ui.readNumber("task-trades-limit", 25),
                    user_id: readOptionalPositiveInteger("task-trades-user-id", "交易用户 ID"),
                    symbol: ui.readValue("task-trades-symbol") || null
                };
                if (!body.trade_ids || body.trade_ids.length === 0) {
                    body.trade_ids = null;
                }
                const payload = await requestAdmin("POST", "/v1/admin/tasks/trades/expire", {
                    body
                });
                ui.renderJson("admin-task-trades-output", payload);
                ui.setStatus("admin-task-trades-status", payload.message || "交易任务已设为过期。", "success");
            } catch (error) {
                ui.setStatus("admin-task-trades-status", error.message, "error");
            }
        });
    }

    const loadUsersButton = ui.byId("load-admin-users");
    if (loadUsersButton) {
        loadUsersButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["query", ui.readValue("admin-users-query")],
                ["plan", ui.readValue("admin-users-plan")],
                ["is_active", readOptionalBooleanSelect("admin-users-active")],
                ["limit", ui.readNumber("admin-users-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/users${query ? `?${query}` : ""}`, "admin-users-output", "admin-users-status");
        });
    }

    const loadUserDetailButton = ui.byId("load-admin-user-detail");
    if (loadUserDetailButton) {
        loadUserDetailButton.addEventListener("click", () => {
            const userId = readOptionalPositiveInteger("admin-user-id", "用户 ID");
            loadAdminJson(`/v1/admin/users/${userId}`, "admin-users-output", "admin-users-status");
        });
    }

    const updateAdminUserForm = ui.byId("update-admin-user-form");
    if (updateAdminUserForm) {
        updateAdminUserForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("admin-users-status", "正在更新用户...");
            try {
                const userId = readOptionalPositiveInteger("admin-user-id", "用户 ID");
                const body = {};
                const name = ui.readValue("admin-user-name");
                const plan = ui.readValue("admin-user-plan");
                const locale = ui.readValue("admin-user-locale");
                const timezone = ui.readValue("admin-user-timezone");
                const currency = ui.readValue("admin-user-currency");
                const active = readOptionalBooleanSelect("admin-user-is-active");
                const totalCapitalRaw = ui.readValue("admin-user-total-capital");
                const extra = parseOptionalJson(ui.readValue("admin-user-extra"), "用户附加信息");
                if (name) body.name = name;
                if (plan) body.plan = plan;
                if (locale) body.locale = locale;
                if (timezone) body.timezone = timezone;
                if (currency) body.currency = currency;
                if (active !== null) body.is_active = active;
                if (totalCapitalRaw) {
                    const totalCapital = Number(totalCapitalRaw);
                    if (!Number.isFinite(totalCapital) || totalCapital <= 0) {
                        throw new Error("总资金必须是正数。");
                    }
                    body.total_capital = totalCapital;
                }
                if (extra !== null) body.extra = extra;
                if (Object.keys(body).length === 0) {
                    throw new Error("提交前至少填写一项用户变更。");
                }
                const payload = await requestAdmin("PUT", `/v1/admin/users/${userId}`, { body });
                ui.renderJson("admin-users-output", payload);
                ui.setStatus("admin-users-status", "用户已更新。", "success");
            } catch (error) {
                ui.setStatus("admin-users-status", error.message, "error");
            }
        });
    }

    const bulkUpdateUsersForm = ui.byId("bulk-update-users-form");
    if (bulkUpdateUsersForm) {
        bulkUpdateUsersForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("admin-users-status", "正在批量更新用户...");
            try {
                const userIds = parsePositiveIntegers(ui.readValue("admin-bulk-user-ids"));
                if (userIds.length === 0) {
                    throw new Error("批量更新至少需要一个用户 ID。");
                }
                const plan = ui.readValue("admin-bulk-user-plan");
                const isActive = readOptionalBooleanSelect("admin-bulk-user-active");
                if (!plan && isActive === null) {
                    throw new Error("批量更新至少需要套餐或启用状态变更。");
                }
                const body = { user_ids: userIds };
                if (plan) body.plan = plan;
                if (isActive !== null) body.is_active = isActive;
                const payload = await requestAdmin("POST", "/v1/admin/users/bulk", { body });
                ui.renderJson("admin-users-output", payload);
                ui.setStatus("admin-users-status", payload.message || "用户已更新。", "success");
            } catch (error) {
                ui.setStatus("admin-users-status", error.message, "error");
            }
        });
    }

    const loadAuditEventsButton = ui.byId("load-admin-audit");
    if (loadAuditEventsButton) {
        loadAuditEventsButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["entity", ui.readValue("admin-audit-entity")],
                ["entity_id", ui.readValue("admin-audit-entity-id")],
                ["action", ui.readValue("admin-audit-action")],
                ["source", ui.readValue("admin-audit-source")],
                ["status", ui.readValue("admin-audit-status")],
                ["request_id", ui.readValue("admin-audit-request-id")],
                ["limit", ui.readNumber("admin-audit-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/audit${query ? `?${query}` : ""}`, "admin-audit-output", "admin-audit-status");
        });
    }

    const loadScannerObservabilityButton = ui.byId("load-scanner-observability");
    if (loadScannerObservabilityButton) {
        loadScannerObservabilityButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["status", ui.readValue("admin-scanner-status")],
                ["bucket_id", readOptionalPositiveInteger("admin-scanner-bucket-id", "扫描器分桶 ID")],
                ["symbol", ui.readValue("admin-scanner-symbol")],
                ["decision", ui.readValue("admin-scanner-decision")],
                ["limit", ui.readNumber("admin-scanner-limit", 25)],
                ["decision_limit", ui.readNumber("admin-scanner-decision-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/scanner/observability${query ? `?${query}` : ""}`, "admin-scanner-output", "admin-scanner-status-output");
        });
    }

    const loadScannerRunButton = ui.byId("load-scanner-run");
    if (loadScannerRunButton) {
        loadScannerRunButton.addEventListener("click", () => {
            const runId = readOptionalPositiveInteger("admin-scanner-run-id", "扫描器运行 ID");
            const query = buildQueryString([
                ["decision_limit", ui.readNumber("admin-scanner-run-decision-limit", 100)]
            ]);
            loadAdminJson(`/v1/admin/scanner/runs/${runId}${query ? `?${query}` : ""}`, "admin-scanner-output", "admin-scanner-status-output");
        });
    }

    const loadScannerLiveDecisionsButton = ui.byId("load-scanner-live-decisions");
    if (loadScannerLiveDecisionsButton) {
        loadScannerLiveDecisionsButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["symbol", ui.readValue("admin-scanner-live-symbol")],
                ["decision", ui.readValue("admin-scanner-live-decision")],
                ["suppressed", readOptionalBooleanSelect("admin-scanner-live-suppressed")],
                ["limit", ui.readNumber("admin-scanner-live-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/scanner/live-decision${query ? `?${query}` : ""}`, "admin-scanner-output", "admin-scanner-status-output");
        });
    }

    const loadBacktestRunsButton = ui.byId("load-backtest-runs");
    if (loadBacktestRunsButton) {
        loadBacktestRunsButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["status", ui.readValue("admin-backtests-status")],
                ["strategy_name", ui.readValue("admin-backtests-strategy")],
                ["timeframe", ui.readValue("admin-backtests-timeframe")],
                ["symbol", ui.readValue("admin-backtests-symbol")],
                ["limit", ui.readNumber("admin-backtests-limit", 25)]
            ]);
            loadAdminJson(`/v1/admin/backtests/runs${query ? `?${query}` : ""}`, "admin-backtests-output", "admin-backtests-status-output");
        });
    }

    const loadBacktestRunButton = ui.byId("load-backtest-run");
    if (loadBacktestRunButton) {
        loadBacktestRunButton.addEventListener("click", () => {
            const runId = readOptionalPositiveInteger("admin-backtest-run-id", "回测运行 ID");
            loadAdminJson(`/v1/admin/backtests/runs/${runId}`, "admin-backtests-output", "admin-backtests-status-output");
        });
    }

    const loadBacktestRankingsButton = ui.byId("load-backtest-rankings");
    if (loadBacktestRankingsButton) {
        loadBacktestRankingsButton.addEventListener("click", () => {
            const query = buildQueryString([
                ["timeframe", ui.readValue("admin-backtests-rankings-timeframe")],
                ["limit", ui.readNumber("admin-backtests-rankings-limit", 20)]
            ]);
            loadAdminJson(`/v1/admin/backtests/rankings/latest${query ? `?${query}` : ""}`, "admin-backtests-output", "admin-backtests-status-output");
        });
    }

    const triggerBacktestRefreshForm = ui.byId("trigger-backtest-refresh-form");
    if (triggerBacktestRefreshForm) {
        triggerBacktestRefreshForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("admin-backtests-status-output", "正在触发回测刷新...");
            try {
                const symbols = parseCommaSeparated(ui.readValue("admin-backtests-refresh-symbols"));
                const strategyNames = parseCommaSeparated(ui.readValue("admin-backtests-refresh-strategies"));
                const windows = parsePositiveIntegers(ui.readValue("admin-backtests-refresh-windows"));
                const payload = await requestAdmin("POST", "/v1/admin/backtests/runs", {
                    body: {
                        symbols: symbols.length > 0 ? symbols : null,
                        strategy_names: strategyNames.length > 0 ? strategyNames : null,
                        windows: windows.length > 0 ? windows : null,
                        timeframe: ui.readValue("admin-backtests-refresh-timeframe") || "1d"
                    }
                });
                ui.renderJson("admin-backtests-output", payload);
                ui.setStatus("admin-backtests-status-output", "已触发回测刷新。", "success");
            } catch (error) {
                ui.setStatus("admin-backtests-status-output", error.message, "error");
            }
        });
    }

    const overviewButton = ui.byId("load-overview");
    if (overviewButton) {
        overviewButton.addEventListener("click", () => {
            loadAdminJson(`/v1/admin/analytics/overview?window_hours=${readWindowHours()}`, "admin-analytics-output", "admin-analytics-status");
        });
    }

    const distributionButton = ui.byId("load-distribution");
    if (distributionButton) {
        distributionButton.addEventListener("click", () => {
            loadAdminJson(`/v1/admin/analytics/distribution?window_hours=${readWindowHours()}`, "admin-analytics-output", "admin-analytics-status");
        });
    }

    const strategyButton = ui.byId("load-strategy-health");
    if (strategyButton) {
        strategyButton.addEventListener("click", () => {
            loadAdminJson(`/v1/admin/analytics/strategy-health?window_hours=${readWindowHours()}`, "admin-analytics-output", "admin-analytics-status");
        });
    }

    const tradingagentsButton = ui.byId("load-tradingagents");
    if (tradingagentsButton) {
        tradingagentsButton.addEventListener("click", () => {
            loadAdminJson(`/v1/admin/analytics/tradingagents?window_hours=${readWindowHours()}`, "admin-analytics-output", "admin-analytics-status");
        });
    }

    const runtimeHealthButton = ui.byId("load-runtime-health");
    if (runtimeHealthButton) {
        runtimeHealthButton.addEventListener("click", () => {
            loadAdminJson("/v1/admin/runtime/health", "admin-runtime-output", "admin-runtime-status");
        });
    }

    const runtimeMetricsButton = ui.byId("load-runtime-metrics");
    if (runtimeMetricsButton) {
        runtimeMetricsButton.addEventListener("click", () => {
            loadAdminJson("/v1/admin/runtime/metrics", "admin-runtime-output", "admin-runtime-status");
        });
    }

    const runtimeAlertsButton = ui.byId("load-runtime-alerts");
    if (runtimeAlertsButton) {
        runtimeAlertsButton.addEventListener("click", () => {
            loadAdminJson("/v1/admin/runtime/alerts", "admin-runtime-output", "admin-runtime-status");
        });
    }

    const acceptanceStatusButton = ui.byId("load-acceptance-status");
    if (acceptanceStatusButton) {
        acceptanceStatusButton.addEventListener("click", () => {
            loadAdminJson("/v1/admin/acceptance/status", "admin-acceptance-output", "admin-acceptance-status");
        });
    }

    const acceptanceReportButton = ui.byId("load-acceptance-report");
    if (acceptanceReportButton) {
        acceptanceReportButton.addEventListener("click", () => {
            loadAdminJson("/v1/admin/acceptance/report", "admin-acceptance-output", "admin-acceptance-status");
        });
    }

    ui.renderSessionSnapshot("admin-session-output");
});
"""

_BASE_CONNECTION_PANEL = """
<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>接口地址配置</h2>
            <p class=\"panel-copy\">此页面由 Python 直接渲染。如果你不是通过 nginx 访问，而是直连 public-api，请在这里更新接口地址。</p>
        </div>
        <span class=\"pill\">纯 HTML + Python</span>
    </div>
    <div class=\"field-grid\">
        <label>
            Public API 基础地址
            <input id=\"public-api-base\" type=\"url\" placeholder=\"http://localhost:8000\">
        </label>
        <label>
            Admin API 基础地址
            <input id=\"admin-api-base\" type=\"url\" placeholder=\"http://localhost:8080\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"save-base-urls\">保存接口地址</button>
    </div>
    <div class=\"status\" id=\"base-url-status\"></div>
</section>
"""

_APP_BODY = """
<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>订阅登录</h2>
            <p class=\"panel-copy\">普通用户只需要用邮箱验证码登录。登录后，本地草稿可反复修改，只有点击“开始订阅”时才会把关键数据同步到服务端。</p>
        </div>
        <span class=\"pill\">/v1/auth/*</span>
    </div>
    <form id=\"send-code-form\">
        <div class=\"field-grid single\">
            <label>
                邮箱
                <input id=\"auth-email\" type=\"email\" placeholder=\"user@example.com\" required>
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\">发送验证码</button>
        </div>
    </form>
    <form id=\"verify-form\">
        <div class=\"field-grid\">
            <label>
                验证邮箱
                <input id=\"verify-email\" type=\"email\" placeholder=\"user@example.com\" required>
            </label>
            <label>
                6 位验证码
                <input id=\"verify-code\" type=\"text\" maxlength=\"6\" placeholder=\"123456\" required>
            </label>
            <label>
                语言地区
                <input id=\"verify-locale\" type=\"text\" placeholder=\"zh-CN\">
            </label>
            <label>
                时区
                <input id=\"verify-timezone\" type=\"text\" placeholder=\"Asia/Shanghai\">
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\">验证并保存会话</button>
            <button type=\"button\" class=\"secondary\" id=\"refresh-session\">刷新令牌</button>
            <button type=\"button\" class=\"ghost\" id=\"logout-session\">退出登录</button>
        </div>
    </form>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"restore-remote-draft\">从云端恢复资料</button>
    </div>
    <div class=\"status\" id=\"auth-status\"></div>
    <div class=\"table-wrap\" id=\"subscriber-session-panel\"><div class=\"empty-state\">登录后，这里会显示当前账号、方案和最近一次订阅状态。</div></div>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>本地订阅草稿</h2>
            <p class=\"panel-copy\">订阅股票、已持仓和现金会优先保存在本机浏览器。你可以离线整理草稿，准备好后再统一开始订阅。</p>
        </div>
    </div>
    <div class=\"hero-grid\">
        <div class=\"hero-stat\">
            <strong id=\"draft-watchlist-count\">0</strong>
            <span>订阅股票</span>
        </div>
        <div class=\"hero-stat\">
            <strong id=\"draft-portfolio-count\">0</strong>
            <span>已持仓股票</span>
        </div>
        <div class=\"hero-stat\">
            <strong id=\"draft-cash-amount\">0</strong>
            <span>现金</span>
        </div>
        <div class=\"hero-stat\">
            <strong id=\"draft-total-assets\">0</strong>
            <span>估算总资产</span>
        </div>
    </div>
    <p class=\"token-note\" id=\"draft-sync-note\">浏览器会自动保留草稿；只有“开始订阅”时才会把监控快照同步到服务端。</p>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"save-local-draft\">手动保存草稿</button>
        <button type=\"button\" class=\"ghost\" id=\"clear-local-draft\">清空本地草稿</button>
    </div>
    <div class=\"status\" id=\"draft-status\"></div>
    <div class=\"table-wrap\" id=\"draft-summary-panel\"><div class=\"empty-state\">登录后录入订阅股票、持仓和现金，这里会显示同步准备状态。</div></div>
</section>

<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>订阅股票</h2>
            <p class=\"panel-copy\">请输入你希望桌面端持续监控的股票代码。支持用逗号、空格或换行一次录入多只股票。</p>
        </div>
        <span class=\"pill\">本地草稿</span>
    </div>
    <form id=\"draft-watchlist-form\">
        <div class=\"field-grid\">
            <label>
                股票代码
                <textarea id=\"draft-watchlist-symbols\" placeholder=\"AAPL, TSLA, NVDA\" required></textarea>
            </label>
            <label>
                默认过滤分数
                <input id=\"draft-watchlist-score\" type=\"number\" min=\"0\" max=\"100\" value=\"65\">
            </label>
        </div>
        <label class=\"inline-check\">
            <input id=\"draft-watchlist-notify\" type=\"checkbox\" checked>
            新信号触发时通知我
        </label>
        <div class=\"button-row\">
            <button type=\"submit\">加入订阅草稿</button>
        </div>
    </form>
    <div class=\"status\" id=\"watchlist-draft-status\"></div>
    <div class=\"table-wrap\" id=\"draft-watchlist-table\"><div class=\"empty-state\">还没有订阅股票。加入后，桌面端会把它们作为监控候选列表。</div></div>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>已持仓股票</h2>
            <p class=\"panel-copy\">请录入你当前已经持有的股票与成本。系统会将“现金 + 已持仓股票”合并计算为订阅启动时的总资产。</p>
        </div>
        <span class=\"pill\">本地草稿</span>
    </div>
    <form id=\"draft-portfolio-form\">
        <div class=\"field-grid\">
            <label>
                股票代码
                <input id=\"draft-portfolio-symbol\" type=\"text\" placeholder=\"AAPL\" required>
            </label>
            <label>
                持股数量
                <input id=\"draft-portfolio-shares\" type=\"number\" min=\"1\" step=\"1\" value=\"10\" required>
            </label>
            <label>
                持仓均价
                <input id=\"draft-portfolio-cost\" type=\"number\" min=\"0.01\" step=\"0.01\" value=\"150\" required>
            </label>
            <label>
                止盈目标
                <input id=\"draft-portfolio-target\" type=\"number\" min=\"0.01\" max=\"1\" step=\"0.01\" value=\"0.15\">
            </label>
            <label>
                止损阈值
                <input id=\"draft-portfolio-stop\" type=\"number\" min=\"0.01\" max=\"1\" step=\"0.01\" value=\"0.08\">
            </label>
            <label>
                备注
                <input id=\"draft-portfolio-notes\" type=\"text\" placeholder=\"例如：长期持有 / 波段仓位\">
            </label>
        </div>
        <label class=\"inline-check\">
            <input id=\"draft-portfolio-notify\" type=\"checkbox\" checked>
            持仓相关信号也通知我
        </label>
        <div class=\"button-row\">
            <button type=\"submit\">加入或覆盖持仓</button>
            <button type=\"button\" class=\"ghost\" id=\"reset-portfolio-form\">清空表单</button>
        </div>
    </form>
    <div class=\"status\" id=\"portfolio-draft-status\"></div>
    <div class=\"table-wrap\" id=\"draft-portfolio-table\"><div class=\"empty-state\">还没有已持仓股票。如果当前空仓，请在开始订阅前勾选“允许空仓启动”。</div></div>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>现金与开始订阅</h2>
            <p class=\"panel-copy\">这里录入你目前可用的现金。开始订阅时，系统会把“现金 + 已持仓成本 + 订阅股票列表”一起同步为桌面端监控快照。</p>
        </div>
        <span class=\"pill\">POST /v1/account/start-subscription</span>
    </div>
    <div class=\"field-grid\">
        <label>
            可用现金
            <input id=\"draft-cash-input\" type=\"number\" min=\"0\" step=\"0.01\" placeholder=\"50000\" required>
        </label>
        <label>
            币种
            <input id=\"draft-currency-input\" type=\"text\" placeholder=\"USD\" value=\"USD\">
        </label>
    </div>
    <label class=\"inline-check\">
        <input id=\"draft-allow-empty-portfolio\" type=\"checkbox\">
        我当前是空仓，只同步订阅股票和现金
    </label>
    <div class=\"button-row\">
        <button type=\"button\" id=\"start-subscription-button\">开始订阅</button>
    </div>
    <div class=\"status\" id=\"subscription-sync-status\"></div>
    <div class=\"table-wrap\" id=\"subscription-sync-panel\"><div class=\"empty-state\">填写完订阅股票、持仓和现金后，点击“开始订阅”即可把监控快照同步到桌面端。</div></div>
</section>
"""

_PLATFORM_BODY = _BASE_CONNECTION_PANEL + """
<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>共享会话快照</h2>
            <p class=\"panel-copy\">`/platform` 会复用 `/app` 中保存的用户 Bearer 令牌。</p>
        </div>
        <span class=\"pill\">令牌复用</span>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"show-platform-session\">查看当前会话</button>
        <button type=\"button\" class=\"ghost\" id=\"clear-platform-session\">清除公共会话</button>
    </div>
    <div class=\"status\" id=\"platform-session-status\"></div>
    <pre class=\"json-output\" id=\"platform-session-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>标的搜索</h2>
            <p class=\"panel-copy\">搜索公开市场标的，并将选中的代码带入下方观察列表表单。</p>
        </div>
        <span class=\"pill\">/v1/search/symbols</span>
    </div>
    <form id=\"symbol-search-form\">
        <div class=\"field-grid\">
            <label>
                搜索词
                <input id=\"search-query\" type=\"text\" placeholder=\"AAPL 或 台积电\" required>
            </label>
            <label>
                资产类型
                <input id=\"search-type\" type=\"text\" placeholder=\"stock, etf, crypto\">
            </label>
            <label>
                数量上限
                <input id=\"search-limit\" type=\"number\" min=\"1\" max=\"50\" value=\"20\">
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\">搜索标的</button>
        </div>
    </form>
    <div class=\"status\" id=\"search-status\"></div>
    <div class=\"table-wrap\" id=\"search-results\"><div class=\"empty-state\">搜索结果会显示在这里。</div></div>
    <pre class=\"json-output\" id=\"search-output\"></pre>
</section>

<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>观察列表与持仓</h2>
            <p class=\"panel-copy\">在一个界面里操作共享的研究观察列表和持仓。</p>
        </div>
        <span class=\"pill\">用户 API</span>
    </div>
    <form id=\"platform-watchlist-form\">
        <div class=\"field-grid\">
            <label>
                代码
                <input id=\"platform-watchlist-symbol\" type=\"text\" placeholder=\"AAPL\" required>
            </label>
            <label>
                最低分数
                <input id=\"platform-watchlist-score\" type=\"number\" min=\"0\" max=\"100\" value=\"70\">
            </label>
        </div>
        <label class=\"inline-check\">
            <input id=\"platform-watchlist-notify\" type=\"checkbox\" checked>
            该标的变得可执行时通知我
        </label>
        <div class=\"button-row\">
            <button type=\"submit\">加入观察列表</button>
            <button type=\"button\" class=\"secondary\" id=\"platform-load-watchlist\">加载观察列表</button>
            <button type=\"button\" class=\"ghost\" id=\"platform-load-portfolio\">加载持仓</button>
        </div>
    </form>
    <p class=\"panel-note\">如果需要直接建仓，可在这里调用 <code>POST /v1/portfolio</code>。</p>
    <form id=\"platform-portfolio-form\">
        <div class=\"field-grid\">
            <label>
                持仓代码
                <input id=\"platform-portfolio-symbol\" type=\"text\" placeholder=\"AAPL\" required>
            </label>
            <label>
                股数
                <input id=\"platform-portfolio-shares\" type=\"number\" min=\"0.0001\" step=\"0.0001\" value=\"10\">
            </label>
            <label>
                平均成本
                <input id=\"platform-portfolio-avg-cost\" type=\"number\" min=\"0.0001\" step=\"0.0001\" value=\"150\">
            </label>
            <label>
                止盈目标
                <input id=\"platform-portfolio-target\" type=\"number\" step=\"0.0001\" min=\"0\" max=\"1\" value=\"0.15\">
            </label>
            <label>
                止损阈值
                <input id=\"platform-portfolio-stop\" type=\"number\" step=\"0.0001\" min=\"0\" max=\"1\" value=\"0.08\">
            </label>
        </div>
        <label class=\"inline-check\">
            <input id=\"platform-portfolio-notify\" type=\"checkbox\" checked>
            该持仓达到阈值时通知我
        </label>
        <label>
            持仓备注
            <input id=\"platform-portfolio-notes\" type=\"text\" placeholder=\"建仓原因、风控备注等\">
        </label>
        <div class=\"button-row\">
            <button type=\"submit\" class=\"secondary\">新增持仓</button>
        </div>
    </form>
    <div class=\"status\" id=\"platform-watchlist-status\"></div>
    <pre class=\"json-output\" id=\"platform-watchlist-output\"></pre>
    <div class=\"status\" id=\"platform-portfolio-status\"></div>
    <pre class=\"json-output\" id=\"platform-portfolio-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>研究数据维护</h2>
            <p class=\"panel-copy\">在同一个平台控制台里更新或删除观察列表和持仓条目。</p>
        </div>
        <span class=\"pill\">共享用户数据的 PUT/DELETE 接口</span>
    </div>
    <form id=\"platform-update-watchlist-form\">
        <div class=\"field-grid\">
            <label>
                观察项 ID
                <input id=\"platform-watchlist-item-id\" type=\"number\" min=\"1\" placeholder=\"1\" required>
            </label>
            <label>
                新最低分数
                <input id=\"platform-watchlist-update-score\" type=\"number\" min=\"0\" max=\"100\" placeholder=\"80\">
            </label>
            <label>
                通知状态
                <select id=\"platform-watchlist-update-notify\">
                    <option value=\"\">保持当前</option>
                    <option value=\"true\">启用</option>
                    <option value=\"false\">停用</option>
                </select>
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\" class=\"secondary\">更新观察项</button>
            <button type=\"button\" class=\"ghost\" id=\"platform-delete-watchlist-item\">删除观察项</button>
        </div>
    </form>
    <form id=\"platform-update-portfolio-form\">
        <div class=\"field-grid\">
            <label>
                持仓条目 ID
                <input id=\"platform-portfolio-item-id\" type=\"number\" min=\"1\" placeholder=\"1\" required>
            </label>
            <label>
                股数
                <input id=\"platform-portfolio-update-shares\" type=\"number\" min=\"1\" placeholder=\"10\">
            </label>
            <label>
                平均成本
                <input id=\"platform-portfolio-update-cost\" type=\"number\" step=\"0.01\" min=\"0.01\" placeholder=\"150\">
            </label>
            <label>
                止盈目标
                <input id=\"platform-portfolio-update-target\" type=\"number\" step=\"0.01\" min=\"0.01\" max=\"1\" placeholder=\"0.2\">
            </label>
            <label>
                止损阈值
                <input id=\"platform-portfolio-update-stop\" type=\"number\" step=\"0.01\" min=\"0.01\" max=\"1\" placeholder=\"0.08\">
            </label>
            <label>
                通知状态
                <select id=\"platform-portfolio-update-notify\">
                    <option value=\"\">保持当前</option>
                    <option value=\"true\">启用</option>
                    <option value=\"false\">停用</option>
                </select>
            </label>
        </div>
        <label>
            备注
            <input id=\"platform-portfolio-update-notes\" type=\"text\" placeholder=\"更新后的持仓理由\">
        </label>
        <div class=\"button-row\">
            <button type=\"submit\" class=\"secondary\">更新持仓</button>
            <button type=\"button\" class=\"ghost\" id=\"platform-delete-portfolio-item\">删除持仓</button>
        </div>
    </form>
    <div class=\"status\" id=\"platform-maintenance-status\"></div>
    <pre class=\"json-output\" id=\"platform-maintenance-output\"></pre>
</section>

<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>交易查询</h2>
            <p class=\"panel-copy\">使用已登录的 app 接口或公开链接 Token，在无需 JS 框架的情况下查看交易。</p>
        </div>
        <span class=\"pill\">/v1/trades/*</span>
    </div>
    <form id=\"app-trade-form\">
        <div class=\"field-grid single\">
            <label>
                已登录 app-info 的交易 ID
                <input id=\"app-trade-id\" type=\"text\" placeholder=\"trade-123\" required>
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\">加载应用交易信息</button>
            <button type=\"button\" class=\"secondary\" id=\"app-confirm-trade\">确认交易</button>
            <button type=\"button\" class=\"ghost\" id=\"app-ignore-trade\">忽略交易</button>
        </div>
    </form>
    <div class=\"field-grid\">
        <label>
            用于调整的实际股数
            <input id=\"app-adjust-shares\" type=\"number\" min=\"0.0001\" step=\"0.0001\" value=\"10\">
        </label>
        <label>
            用于调整的实际价格
            <input id=\"app-adjust-price\" type=\"number\" min=\"0.0001\" step=\"0.0001\" value=\"150\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"app-adjust-trade\">调整并确认</button>
    </div>
    <form id=\"public-trade-form\">
        <div class=\"field-grid\">
            <label>
                公开交易 ID
                <input id=\"public-trade-id\" type=\"text\" placeholder=\"trade-123\" required>
            </label>
            <label>
                公开链接 Token
                <input id=\"public-trade-token\" type=\"text\" placeholder=\"token-123\" required>
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\" class=\"secondary\">加载公开交易信息</button>
        </div>
    </form>
    <div class=\"field-grid\">
        <label>
            公开调整股数
            <input id=\"public-adjust-shares\" type=\"number\" min=\"0.0001\" step=\"0.0001\" value=\"10\">
        </label>
        <label>
            公开调整价格
            <input id=\"public-adjust-price\" type=\"number\" min=\"0.0001\" step=\"0.0001\" value=\"150\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"public-confirm-trade\">公开确认交易</button>
        <button type=\"button\" class=\"ghost\" id=\"public-ignore-trade\">公开忽略交易</button>
        <button type=\"button\" class=\"secondary\" id=\"public-adjust-trade\">公开调整并确认</button>
    </div>
    <div class=\"status\" id=\"trade-status\"></div>
    <pre class=\"json-output\" id=\"trade-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>平台 API 能力矩阵</h2>
            <p class=\"panel-copy\">按关键字筛选并查看 platform 所覆盖的 public API 功能域、认证方式与调用入口。</p>
        </div>
        <span class=\"pill\">端点覆盖 QA</span>
    </div>
    <div class=\"field-grid\">
        <label>
            筛选关键字
            <input id=\"platform-endpoint-filter\" type=\"text\" placeholder=\"例如：notifications, trades, bearer\">
        </label>
        <label>
            当前统计
            <input id=\"platform-endpoint-summary\" type=\"text\" readonly>
        </label>
    </div>
    <div class=\"table-wrap\" id=\"platform-endpoint-matrix\"><div class=\"empty-state\">正在加载端点矩阵...</div></div>
    <div class=\"status\" id=\"platform-endpoint-status\"></div>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>平台 API 调试台</h2>
            <p class=\"panel-copy\">选中任意端点后可直接填写路径参数、查询参数、请求体和附加请求头，覆盖所有平台能力。</p>
        </div>
        <span class=\"pill\">全量执行入口</span>
    </div>
    <form id=\"platform-endpoint-console-form\">
        <div class=\"field-grid\">
            <label>
                端点
                <select id=\"platform-endpoint-select\"></select>
            </label>
            <label>
                Bearer Token 覆盖（可选）
                <input id=\"platform-endpoint-token\" type=\"text\" placeholder=\"留空时按端点配置自动处理认证\">
            </label>
        </div>
        <div class=\"field-grid\">
            <label>
                路径参数 JSON（可选）
                <textarea id=\"platform-endpoint-path-params\" placeholder='{"item_id": 1}'></textarea>
            </label>
            <label>
                查询参数 JSON（可选）
                <textarea id=\"platform-endpoint-query-params\" placeholder='{"q": "AAPL", "limit": 20}'></textarea>
            </label>
        </div>
        <div class=\"field-grid\">
            <label>
                请求体 JSON（可选）
                <textarea id=\"platform-endpoint-body\" placeholder='{"symbol": "AAPL"}'></textarea>
            </label>
            <label>
                附加请求头 JSON（可选）
                <textarea id=\"platform-endpoint-headers\" placeholder='{"X-Custom-Header": "value"}'></textarea>
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\">执行选中端点</button>
            <button type=\"button\" class=\"secondary\" id=\"platform-endpoint-reset\">重置调试台</button>
        </div>
    </form>
    <div class=\"status\" id=\"platform-endpoint-console-status\"></div>
    <pre class=\"json-output\" id=\"platform-endpoint-output\"></pre>
</section>
"""

_ADMIN_BODY = _BASE_CONNECTION_PANEL + """
<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>管理会话</h2>
            <p class=\"panel-copy\">使用同样的邮箱验证码流程登录活动管理员，然后把 Bearer Token 复用到 admin API；同时保留手动 Token 覆盖，方便调试。</p>
        </div>
        <span class=\"pill\">/v1/admin-auth/*</span>
    </div>
    <form id=\"admin-send-code-form\">
        <div class=\"field-grid single\">
            <label>
                管理员邮箱
                <input id=\"admin-auth-email\" type=\"email\" placeholder=\"admin@example.com\" required>
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\">发送管理验证码</button>
        </div>
    </form>
    <form id=\"admin-verify-form\">
        <div class=\"field-grid\">
            <label>
                验证邮箱
                <input id=\"admin-verify-email\" type=\"email\" placeholder=\"admin@example.com\" required>
            </label>
            <label>
                6 位验证码
                <input id=\"admin-verify-code\" type=\"text\" maxlength=\"6\" placeholder=\"123456\" required>
            </label>
            <label>
                语言地区
                <input id=\"admin-verify-locale\" type=\"text\" placeholder=\"zh-CN\">
            </label>
            <label>
                时区
                <input id=\"admin-verify-timezone\" type=\"text\" placeholder=\"Asia/Shanghai\">
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\">验证并保存管理会话</button>
            <button type=\"button\" class=\"secondary\" id=\"refresh-admin-session\">刷新管理令牌</button>
            <button type=\"button\" class=\"ghost\" id=\"logout-admin-session\">退出管理会话</button>
        </div>
    </form>
    <div class=\"field-grid single\">
        <label>
            手动覆盖管理访问令牌
            <textarea id=\"admin-token\" placeholder=\"在此粘贴 Bearer Token\"></textarea>
        </label>
    </div>
    <div class=\"field-grid single\">
        <label>
            操作员 ID 覆盖
            <input id=\"admin-operator-id\" type=\"number\" min=\"1\" placeholder=\"7\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"save-admin-token\">保存粘贴的令牌</button>
        <button type=\"button\" class=\"secondary\" id=\"show-admin-session\">查看管理会话</button>
        <button type=\"button\" class=\"ghost\" id=\"clear-admin-session\">清除管理会话</button>
    </div>
    <div class=\"status\" id=\"admin-auth-status\"></div>
    <pre class=\"json-output\" id=\"admin-auth-output\"></pre>
    <div class=\"status\" id=\"admin-session-status\"></div>
    <pre class=\"json-output\" id=\"admin-session-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>操作员权限</h2>
            <p class=\"panel-copy\">查看当前管理员操作员，并在 HTML 壳内直接更新角色、范围和启用状态。</p>
        </div>
        <span class=\"pill\">/v1/admin/operators</span>
    </div>
    <div class=\"field-grid\">
        <label>
                查询
                <input id=\"admin-operators-query\" type=\"text\" placeholder=\"邮箱或姓名\">
        </label>
        <label>
            角色筛选
            <select id=\"admin-operators-role\">
                <option value=\"\">任意角色</option>
                <option value=\"viewer\">查看者</option>
                <option value=\"operator\">操作员</option>
                <option value=\"admin\">管理员</option>
            </select>
        </label>
        <label>
            启用状态筛选
            <select id=\"admin-operators-active\">
                <option value=\"\">任意状态</option>
                <option value=\"true\">启用</option>
                <option value=\"false\">停用</option>
            </select>
        </label>
        <label>
            数量上限
            <input id=\"admin-operators-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-operators\">加载操作员</button>
    </div>
    <form id=\"upsert-operator-form\">
        <div class=\"field-grid\">
            <label>
                用户 ID
                <input id=\"admin-operator-user-id\" type=\"number\" min=\"1\" placeholder=\"7\" required>
            </label>
            <label>
                新角色
                <select id=\"admin-operator-role\">
                    <option value=\"\">保持当前</option>
                    <option value=\"viewer\">查看者</option>
                    <option value=\"operator\">操作员</option>
                    <option value=\"admin\">管理员</option>
                </select>
            </label>
            <label>
                启用状态
                <select id=\"admin-operator-is-active\">
                    <option value=\"\">保持当前</option>
                    <option value=\"true\">启用</option>
                    <option value=\"false\">停用</option>
                </select>
            </label>
            <label>
                权限范围
                <input id=\"admin-operator-scopes\" type=\"text\" placeholder=\"runtime, analytics, distribution\">
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\" class=\"secondary\">写入操作员</button>
        </div>
    </form>
    <div class=\"status\" id=\"admin-operators-status\"></div>
    <pre class=\"json-output\" id=\"admin-operators-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>手动分发</h2>
            <p class=\"panel-copy\">使用与管理操作相同的分发数据平面，排入手动邮件或推送通知。</p>
        </div>
        <span class=\"pill\">/v1/admin/distribution/manual-message</span>
    </div>
    <form id=\"manual-distribution-form\">
        <div class=\"field-grid\">
            <label>
                用户 ID 列表
                <input id=\"distribution-user-ids\" type=\"text\" placeholder=\"7, 12, 19\" required>
            </label>
            <label>
                通知类型
                <input id=\"distribution-type\" type=\"text\" placeholder=\"manual.message\" value=\"manual.message\">
            </label>
            <label>
                确认截止时间（可选）
                <input id=\"distribution-ack-deadline\" type=\"text\" placeholder=\"2026-04-06T12:00:00+08:00\">
            </label>
            <label>
                标题
                <input id=\"distribution-title\" type=\"text\" placeholder=\"服务通知\" required>
            </label>
        </div>
        <label>
            正文
            <textarea id=\"distribution-body\" placeholder=\"消息正文\" required></textarea>
        </label>
        <label>
            元数据 JSON（可选）
            <textarea id=\"distribution-metadata\" placeholder='{\"campaign\":\"cutover-check\"}'></textarea>
        </label>
        <div class=\"button-row\">
            <label class=\"inline-check\">
                <input id=\"distribution-channel-email\" type=\"checkbox\" checked>
                邮件
            </label>
            <label class=\"inline-check\">
                <input id=\"distribution-channel-push\" type=\"checkbox\" checked>
                推送
            </label>
            <label class=\"inline-check\">
                <input id=\"distribution-ack-required\" type=\"checkbox\">
                需要确认
            </label>
            <button type=\"submit\">排入手动消息</button>
        </div>
    </form>
    <div class=\"status\" id=\"admin-distribution-status\"></div>
    <pre class=\"json-output\" id=\"admin-distribution-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>任务中心：回执</h2>
            <p class=\"panel-copy\">查看回执跟进状态、升级超时确认，并执行确认、领取和解决操作。</p>
        </div>
        <span class=\"pill\">/v1/admin/tasks/receipts*</span>
    </div>
    <div class=\"field-grid\">
        <label>
            跟进状态
            <select id=\"task-receipts-follow-up-status\">
                <option value=\"\">全部</option>
                <option value=\"none\">无</option>
                <option value=\"pending\">待处理</option>
                <option value=\"claimed\">已领取</option>
                <option value=\"resolved\">已解决</option>
            </select>
        </label>
        <label>
            发送状态
            <select id=\"task-receipts-delivery-status\">
                <option value=\"\">全部</option>
                <option value=\"pending\">待处理</option>
                <option value=\"delivered\">已送达</option>
                <option value=\"failed\">失败</option>
            </select>
        </label>
        <label>
            需要确认
            <select id=\"task-receipts-ack-required\">
                <option value=\"\">全部</option>
                <option value=\"true\">需要</option>
                <option value=\"false\">不需要</option>
            </select>
        </label>
        <label>
            用户 ID
            <input id=\"task-receipts-user-id\" type=\"number\" min=\"1\" placeholder=\"42\">
        </label>
        <label>
            通知 ID
            <input id=\"task-receipts-notification-id\" type=\"text\" placeholder=\"notification-123\">
        </label>
        <label>
            数量上限
            <input id=\"task-receipts-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
    </div>
    <div class=\"button-row\">
        <label class=\"inline-check\">
            <input id=\"task-receipts-overdue-only\" type=\"checkbox\">
            仅超时
        </label>
        <button type=\"button\" id=\"load-task-receipts\">加载回执</button>
        <button type=\"button\" class=\"secondary\" id=\"escalate-task-receipts\">升级超时项</button>
    </div>
    <div class=\"field-grid single\">
        <label>
            用于确认、领取或解决的回执 ID
            <input id=\"task-receipt-id\" type=\"text\" placeholder=\"receipt-123\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"ack-task-receipt\">确认回执</button>
        <button type=\"button\" class=\"secondary\" id=\"claim-task-receipt\">领取跟进</button>
        <button type=\"button\" class=\"ghost\" id=\"resolve-task-receipt\">解决跟进</button>
    </div>
    <div class=\"status\" id=\"admin-task-receipts-status\"></div>
    <pre class=\"json-output\" id=\"admin-task-receipts-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>任务中心：发件箱</h2>
            <p class=\"panel-copy\">查看待投递任务、释放过期 processing 行，并重新入队发件箱记录。</p>
        </div>
        <span class=\"pill\">/v1/admin/tasks/outbox*</span>
    </div>
    <div class=\"field-grid\">
        <label>
            渠道
            <select id=\"task-outbox-channel\">
                <option value=\"\">全部</option>
                <option value=\"email\">邮件</option>
                <option value=\"push\">推送</option>
            </select>
        </label>
        <label>
            状态
            <select id=\"task-outbox-status\">
                <option value=\"\">全部</option>
                <option value=\"pending\">待处理</option>
                <option value=\"processing\">处理中</option>
                <option value=\"delivered\">已送达</option>
                <option value=\"failed\">失败</option>
            </select>
        </label>
        <label>
            用户 ID
            <input id=\"task-outbox-user-id\" type=\"number\" min=\"1\" placeholder=\"42\">
        </label>
        <label>
            通知 ID
            <input id=\"task-outbox-notification-id\" type=\"text\" placeholder=\"notification-123\">
        </label>
        <label>
            数量上限
            <input id=\"task-outbox-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
        <label>
            释放早于此时间（分钟）
            <input id=\"task-outbox-older-minutes\" type=\"number\" min=\"1\" max=\"1440\" value=\"15\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-task-outbox\">加载发件箱</button>
        <button type=\"button\" class=\"secondary\" id=\"release-task-outbox\">释放陈旧任务</button>
    </div>
    <div class=\"field-grid\">
        <label>
            单个发件箱 ID
            <input id=\"task-outbox-id\" type=\"text\" placeholder=\"outbox-123\">
        </label>
        <label>
            多个发件箱 ID
            <input id=\"task-outbox-ids\" type=\"text\" placeholder=\"outbox-1, outbox-2\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"requeue-task-outbox\">单条重新入队</button>
        <button type=\"button\" class=\"ghost\" id=\"retry-task-outbox\">重试所选</button>
    </div>
    <div class=\"status\" id=\"admin-task-outbox-status\"></div>
    <pre class=\"json-output\" id=\"admin-task-outbox-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>任务中心：交易</h2>
            <p class=\"panel-copy\">在当前操作员上下文下查看待处理交易任务，并执行领取或过期操作。</p>
        </div>
        <span class=\"pill\">/v1/admin/tasks/trades*</span>
    </div>
    <div class=\"field-grid\">
        <label>
            状态
            <select id=\"task-trades-status\">
                <option value=\"\">全部</option>
                <option value=\"pending\">待处理</option>
                <option value=\"confirmed\">已确认</option>
                <option value=\"adjusted\">已调整</option>
                <option value=\"ignored\">已忽略</option>
                <option value=\"expired\">已过期</option>
            </select>
        </label>
        <label>
            动作
            <select id=\"task-trades-action\">
                <option value=\"\">全部</option>
                <option value=\"buy\">买入</option>
                <option value=\"sell\">卖出</option>
                <option value=\"add\">加仓</option>
            </select>
        </label>
        <label>
            被哪个操作员领取
            <input id=\"task-trades-claimed-by\" type=\"number\" min=\"1\" placeholder=\"7\">
        </label>
        <label>
            用户 ID
            <input id=\"task-trades-user-id\" type=\"number\" min=\"1\" placeholder=\"42\">
        </label>
        <label>
            代码
            <input id=\"task-trades-symbol\" type=\"text\" placeholder=\"AAPL\">
        </label>
        <label>
            数量上限
            <input id=\"task-trades-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
    </div>
    <div class=\"button-row\">
        <label class=\"inline-check\">
            <input id=\"task-trades-expired-only\" type=\"checkbox\">
            仅已过期
        </label>
        <label class=\"inline-check\">
            <input id=\"task-trades-claimed-only\" type=\"checkbox\">
            仅已领取
        </label>
        <button type=\"button\" id=\"load-task-trades\">加载交易任务</button>
    </div>
    <div class=\"field-grid single\">
        <label>
            批量操作的交易 ID（可选）
            <input id=\"task-trades-ids\" type=\"text\" placeholder=\"trade-1, trade-2\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"claim-task-trades\">领取交易</button>
        <button type=\"button\" class=\"ghost\" id=\"expire-task-trades\">设为过期</button>
    </div>
    <div class=\"status\" id=\"admin-task-trades-status\"></div>
    <pre class=\"json-output\" id=\"admin-task-trades-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>用户</h2>
            <p class=\"panel-copy\">加载用户记录、查看指定用户、更新资料或资金字段，并执行批量套餐或启用状态调整。</p>
        </div>
        <span class=\"pill\">/v1/admin/users*</span>
    </div>
    <div class=\"field-grid\">
        <label>
            查询
            <input id=\"admin-users-query\" type=\"text\" placeholder=\"邮箱或姓名\">
        </label>
        <label>
            套餐
            <input id=\"admin-users-plan\" type=\"text\" placeholder=\"free, pro, enterprise\">
        </label>
        <label>
            启用状态
            <select id=\"admin-users-active\">
                <option value=\"\">全部</option>
                <option value=\"true\">启用</option>
                <option value=\"false\">停用</option>
            </select>
        </label>
        <label>
            数量上限
            <input id=\"admin-users-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-admin-users\">加载用户</button>
    </div>
    <form id=\"update-admin-user-form\">
        <div class=\"field-grid\">
            <label>
                用户 ID
                <input id=\"admin-user-id\" type=\"number\" min=\"1\" placeholder=\"42\" required>
            </label>
            <label>
                姓名
                <input id=\"admin-user-name\" type=\"text\" placeholder=\"张三\">
            </label>
            <label>
                套餐
                <input id=\"admin-user-plan\" type=\"text\" placeholder=\"pro\">
            </label>
            <label>
                语言地区
                <input id=\"admin-user-locale\" type=\"text\" placeholder=\"zh-CN\">
            </label>
            <label>
                时区
                <input id=\"admin-user-timezone\" type=\"text\" placeholder=\"Asia/Shanghai\">
            </label>
            <label>
                币种
                <input id=\"admin-user-currency\" type=\"text\" placeholder=\"USD\">
            </label>
            <label>
                总资金
                <input id=\"admin-user-total-capital\" type=\"number\" step=\"0.01\" min=\"0.01\" placeholder=\"100000\">
            </label>
            <label>
                启用状态
                <select id=\"admin-user-is-active\">
                    <option value=\"\">保持当前</option>
                    <option value=\"true\">启用</option>
                    <option value=\"false\">停用</option>
                </select>
            </label>
        </div>
        <label>
            附加 JSON
            <textarea id=\"admin-user-extra\" placeholder='{"subscription":{"status":"active"}}'></textarea>
        </label>
        <div class=\"button-row\">
            <button type=\"button\" class=\"secondary\" id=\"load-admin-user-detail\">加载用户详情</button>
            <button type=\"submit\">更新用户</button>
        </div>
    </form>
    <form id=\"bulk-update-users-form\">
        <div class=\"field-grid\">
            <label>
                用户 ID 列表
                <input id=\"admin-bulk-user-ids\" type=\"text\" placeholder=\"42, 43, 44\" required>
            </label>
            <label>
                批量套餐
                <input id=\"admin-bulk-user-plan\" type=\"text\" placeholder=\"enterprise\">
            </label>
            <label>
                批量启用状态
                <select id=\"admin-bulk-user-active\">
                    <option value=\"\">不变</option>
                    <option value=\"true\">启用</option>
                    <option value=\"false\">停用</option>
                </select>
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\" class=\"secondary\">批量更新用户</button>
        </div>
    </form>
    <div class=\"status\" id=\"admin-users-status\"></div>
    <pre class=\"json-output\" id=\"admin-users-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>审计轨迹</h2>
            <p class=\"panel-copy\">按实体、动作、来源、请求 ID 或发件箱状态筛选审计事件，查看操作历史。</p>
        </div>
        <span class=\"pill\">/v1/admin/audit</span>
    </div>
    <div class=\"field-grid\">
        <label>
            实体
            <input id=\"admin-audit-entity\" type=\"text\" placeholder=\"trade\">
        </label>
        <label>
            实体 ID
            <input id=\"admin-audit-entity-id\" type=\"text\" placeholder=\"trade-123\">
        </label>
        <label>
            动作
            <input id=\"admin-audit-action\" type=\"text\" placeholder=\"tasks.claimed\">
        </label>
        <label>
            来源
            <input id=\"admin-audit-source\" type=\"text\" placeholder=\"admin-api\">
        </label>
        <label>
            状态
            <select id=\"admin-audit-status\">
                <option value=\"\">全部</option>
                <option value=\"pending\">待处理</option>
                <option value=\"published\">已发布</option>
            </select>
        </label>
        <label>
            请求 ID
            <input id=\"admin-audit-request-id\" type=\"text\" placeholder=\"request-id\">
        </label>
        <label>
            数量上限
            <input id=\"admin-audit-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-admin-audit\">加载审计事件</button>
    </div>
    <div class=\"status\" id=\"admin-audit-status\"></div>
    <pre class=\"json-output\" id=\"admin-audit-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>扫描器</h2>
            <p class=\"panel-copy\">查看扫描器可观测性、加载指定运行，并在管理页面内查询实时决策。</p>
        </div>
        <span class=\"pill\">/v1/admin/scanner/*</span>
    </div>
    <div class=\"field-grid\">
        <label>
            运行状态
            <select id=\"admin-scanner-status\">
                <option value=\"\">全部</option>
                <option value=\"running\">运行中</option>
                <option value=\"completed\">已完成</option>
                <option value=\"failed\">失败</option>
            </select>
        </label>
        <label>
            分桶 ID
            <input id=\"admin-scanner-bucket-id\" type=\"number\" min=\"1\" placeholder=\"12\">
        </label>
        <label>
            代码
            <input id=\"admin-scanner-symbol\" type=\"text\" placeholder=\"AAPL\">
        </label>
        <label>
            决策
            <select id=\"admin-scanner-decision\">
                <option value=\"\">全部</option>
                <option value=\"emitted\">已发出</option>
                <option value=\"suppressed\">已抑制</option>
                <option value=\"skipped\">已跳过</option>
                <option value=\"error\">错误</option>
            </select>
        </label>
        <label>
            运行数量上限
            <input id=\"admin-scanner-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
        <label>
            决策数量上限
            <input id=\"admin-scanner-decision-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-scanner-observability\">加载可观测数据</button>
    </div>
    <div class=\"field-grid\">
        <label>
            运行 ID
            <input id=\"admin-scanner-run-id\" type=\"number\" min=\"1\" placeholder=\"101\">
        </label>
        <label>
            单次运行决策上限
            <input id=\"admin-scanner-run-decision-limit\" type=\"number\" min=\"1\" max=\"500\" value=\"100\">
        </label>
        <label>
            实时代码
            <input id=\"admin-scanner-live-symbol\" type=\"text\" placeholder=\"AAPL\">
        </label>
        <label>
            实时决策
            <select id=\"admin-scanner-live-decision\">
                <option value=\"\">全部</option>
                <option value=\"emitted\">已发出</option>
                <option value=\"suppressed\">已抑制</option>
                <option value=\"skipped\">已跳过</option>
                <option value=\"error\">错误</option>
            </select>
        </label>
        <label>
            已抑制
            <select id=\"admin-scanner-live-suppressed\">
                <option value=\"\">全部</option>
                <option value=\"true\">是</option>
                <option value=\"false\">否</option>
            </select>
        </label>
        <label>
            实时数量上限
            <input id=\"admin-scanner-live-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"load-scanner-run\">加载运行详情</button>
        <button type=\"button\" class=\"ghost\" id=\"load-scanner-live-decisions\">加载实时决策</button>
    </div>
    <div class=\"status\" id=\"admin-scanner-status-output\"></div>
    <pre class=\"json-output\" id=\"admin-scanner-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>回测</h2>
            <p class=\"panel-copy\">查看历史回测运行、最新排名，并直接在管理端触发排名刷新。</p>
        </div>
        <span class=\"pill\">/v1/admin/backtests/*</span>
    </div>
    <div class=\"field-grid\">
        <label>
            运行状态
            <select id=\"admin-backtests-status\">
                <option value=\"\">全部</option>
                <option value=\"pending\">待处理</option>
                <option value=\"running\">运行中</option>
                <option value=\"completed\">已完成</option>
                <option value=\"failed\">失败</option>
            </select>
        </label>
        <label>
            策略
            <input id=\"admin-backtests-strategy\" type=\"text\" placeholder=\"momentum\">
        </label>
        <label>
            周期
            <input id=\"admin-backtests-timeframe\" type=\"text\" placeholder=\"1d\">
        </label>
        <label>
            代码
            <input id=\"admin-backtests-symbol\" type=\"text\" placeholder=\"AAPL\">
        </label>
        <label>
            数量上限
            <input id=\"admin-backtests-limit\" type=\"number\" min=\"1\" max=\"200\" value=\"25\">
        </label>
        <label>
            运行 ID
            <input id=\"admin-backtest-run-id\" type=\"number\" min=\"1\" placeholder=\"18\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-backtest-runs\">加载运行记录</button>
        <button type=\"button\" class=\"secondary\" id=\"load-backtest-run\">加载运行详情</button>
    </div>
    <div class=\"field-grid\">
        <label>
            排名周期
            <input id=\"admin-backtests-rankings-timeframe\" type=\"text\" placeholder=\"1d\">
        </label>
        <label>
            排名数量上限
            <input id=\"admin-backtests-rankings-limit\" type=\"number\" min=\"1\" max=\"100\" value=\"20\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"load-backtest-rankings\">加载最新排名</button>
    </div>
    <form id=\"trigger-backtest-refresh-form\">
        <div class=\"field-grid\">
            <label>
                标的列表
                <input id=\"admin-backtests-refresh-symbols\" type=\"text\" placeholder=\"AAPL, MSFT\">
            </label>
            <label>
                策略名称
                <input id=\"admin-backtests-refresh-strategies\" type=\"text\" placeholder=\"momentum, mean-reversion\">
            </label>
            <label>
                窗口参数
                <input id=\"admin-backtests-refresh-windows\" type=\"text\" placeholder=\"30, 90, 180\">
            </label>
            <label>
                刷新周期
                <input id=\"admin-backtests-refresh-timeframe\" type=\"text\" value=\"1d\">
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\" class=\"ghost\">触发排名刷新</button>
        </div>
    </form>
    <div class=\"status\" id=\"admin-backtests-status-output\"></div>
    <pre class=\"json-output\" id=\"admin-backtests-output\"></pre>
</section>

<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>分析</h2>
            <p class=\"panel-copy\">总览、分发、策略健康度，以及 TradingAgents 读模型。</p>
        </div>
        <span class=\"pill\">/v1/admin/analytics/*</span>
    </div>
    <div class=\"field-grid single\">
        <label>
            时间窗口（小时）
            <input id=\"admin-window-hours\" type=\"number\" min=\"1\" max=\"720\" value=\"24\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-overview\">加载总览</button>
        <button type=\"button\" class=\"secondary\" id=\"load-distribution\">加载分发数据</button>
        <button type=\"button\" class=\"secondary\" id=\"load-strategy-health\">加载策略健康度</button>
        <button type=\"button\" class=\"ghost\" id=\"load-tradingagents\">加载 TradingAgents</button>
    </div>
    <div class=\"status\" id=\"admin-analytics-status\"></div>
    <pre class=\"json-output\" id=\"admin-analytics-output\"></pre>
</section>

<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>运行态</h2>
            <p class=\"panel-copy\">查看 admin API 的组件健康、运行指标与当前告警状态。</p>
        </div>
        <span class=\"pill\">/v1/admin/runtime/*</span>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-runtime-health\">加载健康状态</button>
        <button type=\"button\" class=\"secondary\" id=\"load-runtime-metrics\">加载指标</button>
        <button type=\"button\" class=\"ghost\" id=\"load-runtime-alerts\">加载告警</button>
    </div>
    <div class=\"status\" id=\"admin-runtime-status\"></div>
    <pre class=\"json-output\" id=\"admin-runtime-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>验收与发布证据</h2>
            <p class=\"panel-copy\">拉取就绪度报告与制品清单，用于切换和 OpenAPI 验证。</p>
        </div>
        <span class=\"pill\">/v1/admin/acceptance/*</span>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-acceptance-status\">加载验收状态</button>
        <button type=\"button\" class=\"secondary\" id=\"load-acceptance-report\">加载验收报告</button>
    </div>
    <div class=\"status\" id=\"admin-acceptance-status\"></div>
    <pre class=\"json-output\" id=\"admin-acceptance-output\"></pre>
</section>
"""

_PAGE_META = {
    "app": {
        "title": "订阅端",
        "hero_title": "普通订阅用户现在可以只维护一份离线优先草稿。",
        "hero_copy": "这个路由直接由 Python 提供，面向邮箱验证码登录后的普通订阅用户。用户只需要维护订阅股票、已持仓股票和现金，准备好后再用“开始订阅”把监控快照同步到服务端。",
        "body": _APP_BODY,
        "script": _APP_SCRIPT,
    },
    "platform": {
        "title": "平台端",
        "hero_title": "无需前端工作区，也能完成研究与交易查询。",
        "hero_copy": "平台界面以纯 HTML 控制台的形式运行在 public API 之上。你可以直接在浏览器里搜索标的、查看交易，并复用用户 Bearer 会话。",
        "body": _PLATFORM_BODY,
        "script": _PLATFORM_SCRIPT,
    },
    "admin": {
        "title": "管理端",
        "hero_title": "在同一套部署基线上完成管理分析与运行控制。",
        "hero_copy": "这个纯 HTML 管理壳现已支持活动管理员操作员的邮箱验证码登录、刷新和退出，同时仍保留手动 Bearer Token 覆盖，方便调试与代理验证。",
        "body": _ADMIN_BODY,
        "script": _ADMIN_SCRIPT,
    },
}


def _render_nav(surface: SurfaceName) -> str:
    items = [
        ("app", "/app", "订阅端"),
        ("platform", "/platform", "平台端"),
        ("admin", "/admin", "管理端"),
    ]
    chips: list[str] = []
    for item_surface, href, label in items:
        class_name = "nav-chip active" if item_surface == surface else "nav-chip"
        chips.append(f'<a class="{class_name}" href="{href}">{escape(label)}</a>')
    return "".join(chips)


def render_surface_page(
    *,
    surface: SurfaceName,
    project_name: str,
    public_api_base_url: str | None = None,
    admin_api_base_url: str | None = None,
) -> str:
    meta = _PAGE_META[surface]
    page_config = json.dumps(
        {
            "surface": surface,
            "projectName": project_name,
            "publicApiBaseUrl": public_api_base_url or "",
            "adminApiBaseUrl": admin_api_base_url or "",
        }
    )

    html = _PAGE_TEMPLATE
    replacements = {
        "__TITLE__": escape(f"{project_name} {meta['title']}"),
        "__SURFACE__": escape(surface),
        "__BRAND__": escape(project_name),
        "__NAV__": _render_nav(surface),
        "__HERO_TITLE__": escape(meta["hero_title"]),
        "__HERO_COPY__": escape(meta["hero_copy"]),
        "__BODY__": meta["body"],
        "__PAGE_CONFIG__": page_config,
        "__COMMON_SCRIPT__": _COMMON_SCRIPT,
        "__PAGE_SCRIPT__": meta["script"],
    }
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    return html