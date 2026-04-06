from __future__ import annotations

import json
from html import escape
from typing import Literal

SurfaceName = Literal["app", "platform", "admin"]

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
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
                    <p>Pure HTML plus Python surfaces served directly from FastAPI.</p>
                </div>
            </div>
            <nav class=\"nav-row\">__NAV__</nav>
        </header>

        <section class=\"hero\">
            <div class=\"hero-card\">
                <div class=\"hero-copy\">
                    <span class=\"hero-kicker\">No Node build pipeline</span>
                    <h2>__HERO_TITLE__</h2>
                    <p>__HERO_COPY__</p>
                </div>
                <div class=\"hero-grid\">
                    <div class=\"hero-stat\">
                        <strong>/app</strong>
                        <span>Subscriber login, dashboard, notifications, watchlist, and portfolio.</span>
                    </div>
                    <div class=\"hero-stat\">
                        <strong>/platform</strong>
                        <span>Search, research workflows, and trade lookup against live public endpoints.</span>
                    </div>
                    <div class=\"hero-stat\">
                        <strong>/admin</strong>
                        <span>Analytics, runtime, and acceptance evidence driven by admin APIs.</span>
                    </div>
                </div>
            </div>

            <aside class=\"hero-aside\">
                <h3>Runtime Notes</h3>
                <ul>
                    <li>Default API targets use the current host, which works behind nginx and compose.</li>
                    <li>If you open the public API directly, change the admin base URL in the page before loading admin data.</li>
                    <li>Subscriber and platform reuse the same bearer session from `/v1/auth/*`.</li>
                    <li>Admin keeps explicit bearer token entry because there is no dedicated admin login route yet.</li>
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
        adminToken: "stockpy.ui.admin-token"
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

    function setAdminToken(token) {
        const normalized = String(token || "").trim();
        if (normalized) {
            localStorage.setItem(storageKeys.adminToken, normalized);
        } else {
            localStorage.removeItem(storageKeys.adminToken);
        }
        return normalized;
    }

    function requireAccessToken() {
        const token = getAccessToken();
        if (!token) {
            throw new Error("Verify a subscriber code first to obtain an access token.");
        }
        return token;
    }

    function requireAdminToken() {
        const token = getAdminToken();
        if (!token) {
            throw new Error("Paste an admin bearer token before loading admin data.");
        }
        return token;
    }

    function renderSearchTable(containerId, items) {
        const node = byId(containerId);
        if (!node) {
            return;
        }
        if (!Array.isArray(items) || items.length === 0) {
            node.innerHTML = '<div class="empty-state">No symbols matched the current query.</div>';
            return;
        }

        const rows = items.map((item) => `
            <tr>
                <td><strong>${escapeHtml(item.symbol)}</strong></td>
                <td>${escapeHtml(item.name || item.name_zh || "")}</td>
                <td>${escapeHtml(item.asset_type || "")}</td>
                <td>${escapeHtml(item.exchange || "")}</td>
                <td><button type="button" class="secondary search-pick" data-symbol="${escapeHtml(item.symbol)}">Use symbol</button></td>
            </tr>
        `).join("");

        node.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Exchange</th>
                        <th>Action</th>
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
            admin_token_present: Boolean(getAdminToken())
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
                    `Saved endpoints. public=${savedPublic} admin=${savedAdmin}`,
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
        getAdminToken,
        getBaseUrl,
        getRefreshToken,
        getStoredUser,
        publicApi,
        readCheckbox,
        readNumber,
        readValue,
        renderJson,
        renderSearchTable,
        renderSessionSnapshot,
        requestJson,
        requireAccessToken,
        requireAdminToken,
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

    const sendCodeForm = ui.byId("send-code-form");
    if (sendCodeForm) {
        sendCodeForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("auth-status", "Sending verification code...");
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
                ui.renderJson("auth-output", payload);
                ui.setStatus("auth-status", payload.message || "Verification code sent.", "success");
            } catch (error) {
                ui.setStatus("auth-status", error.message, "error");
            }
        });
    }

    const verifyForm = ui.byId("verify-form");
    if (verifyForm) {
        if (ui.byId("verify-timezone") && !ui.byId("verify-timezone").value) {
            ui.byId("verify-timezone").value = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
        }
        verifyForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("auth-status", "Verifying code...");
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
                ui.renderJson("auth-output", payload);
                ui.renderSessionSnapshot("session-output");
                ui.setStatus("auth-status", "Subscriber session stored locally.", "success");
            } catch (error) {
                ui.setStatus("auth-status", error.message, "error");
            }
        });
    }

    const refreshButton = ui.byId("refresh-session");
    if (refreshButton) {
        refreshButton.addEventListener("click", async () => {
            ui.setStatus("auth-status", "Refreshing session...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/auth/refresh"), {
                    body: { refresh_token: ui.getRefreshToken() }
                });
                ui.setPublicSession(payload);
                ui.renderJson("auth-output", payload);
                ui.renderSessionSnapshot("session-output");
                ui.setStatus("auth-status", "Session refreshed.", "success");
            } catch (error) {
                ui.setStatus("auth-status", error.message, "error");
            }
        });
    }

    const logoutButton = ui.byId("logout-session");
    if (logoutButton) {
        logoutButton.addEventListener("click", async () => {
            ui.setStatus("auth-status", "Signing out...");
            try {
                await ui.requestJson("POST", ui.publicApi("/v1/auth/logout"), {
                    token: ui.requireAccessToken()
                });
                ui.clearPublicSession();
                ui.renderJson("auth-output", { message: "Signed out successfully" });
                ui.renderSessionSnapshot("session-output");
                ui.setStatus("auth-status", "Local session cleared.", "success");
            } catch (error) {
                ui.setStatus("auth-status", error.message, "error");
            }
        });
    }

    const showSessionButton = ui.byId("show-session");
    if (showSessionButton) {
        showSessionButton.addEventListener("click", () => {
            ui.renderSessionSnapshot("session-output");
            ui.setStatus("session-status", "Rendered current browser session snapshot.", "success");
        });
    }

    async function loadProtectedJson(path, outputId, statusId) {
        ui.setStatus(statusId, "Loading...");
        try {
            const payload = await ui.requestJson("GET", ui.publicApi(path), {
                token: ui.requireAccessToken()
            });
            ui.renderJson(outputId, payload);
            ui.setStatus(statusId, "Loaded successfully.", "success");
        } catch (error) {
            ui.setStatus(statusId, error.message, "error");
        }
    }

    const loadProfileButton = ui.byId("load-profile");
    if (loadProfileButton) {
        loadProfileButton.addEventListener("click", () => {
            loadProtectedJson("/v1/account/profile", "account-output", "account-status");
        });
    }

    const loadDashboardButton = ui.byId("load-dashboard");
    if (loadDashboardButton) {
        loadDashboardButton.addEventListener("click", () => {
            loadProtectedJson("/v1/account/dashboard", "dashboard-output", "account-status");
        });
    }

    const loadNotificationsButton = ui.byId("load-notifications");
    if (loadNotificationsButton) {
        loadNotificationsButton.addEventListener("click", () => {
            loadProtectedJson("/v1/notifications", "notifications-output", "notifications-status");
        });
    }

    const markAllReadButton = ui.byId("mark-all-read");
    if (markAllReadButton) {
        markAllReadButton.addEventListener("click", async () => {
            ui.setStatus("notifications-status", "Marking all notifications as read...");
            try {
                const payload = await ui.requestJson("PUT", ui.publicApi("/v1/notifications/read-all"), {
                    token: ui.requireAccessToken()
                });
                ui.renderJson("notifications-output", payload);
                ui.setStatus("notifications-status", payload.message || "All notifications marked as read.", "success");
            } catch (error) {
                ui.setStatus("notifications-status", error.message, "error");
            }
        });
    }

    const markReadButton = ui.byId("mark-notification-read");
    if (markReadButton) {
        markReadButton.addEventListener("click", async () => {
            ui.setStatus("notifications-status", "Marking notification as read...");
            try {
                const notificationId = ui.readValue("notification-id");
                const payload = await ui.requestJson(
                    "PUT",
                    ui.publicApi(`/v1/notifications/${encodeURIComponent(notificationId)}/read`),
                    { token: ui.requireAccessToken() }
                );
                ui.renderJson("notifications-output", payload);
                ui.setStatus("notifications-status", payload.message || "Notification marked as read.", "success");
            } catch (error) {
                ui.setStatus("notifications-status", error.message, "error");
            }
        });
    }

    const ackButton = ui.byId("ack-notification");
    if (ackButton) {
        ackButton.addEventListener("click", async () => {
            ui.setStatus("notifications-status", "Acknowledging notification...");
            try {
                const notificationId = ui.readValue("notification-id");
                const payload = await ui.requestJson(
                    "PUT",
                    ui.publicApi(`/v1/notifications/${encodeURIComponent(notificationId)}/ack`),
                    { token: ui.requireAccessToken() }
                );
                ui.renderJson("notifications-output", payload);
                ui.setStatus("notifications-status", payload.message || "Notification acknowledged.", "success");
            } catch (error) {
                ui.setStatus("notifications-status", error.message, "error");
            }
        });
    }

    const loadWatchlistButton = ui.byId("load-watchlist");
    if (loadWatchlistButton) {
        loadWatchlistButton.addEventListener("click", () => {
            loadProtectedJson("/v1/watchlist", "watchlist-output", "watchlist-status");
        });
    }

    const createWatchlistForm = ui.byId("create-watchlist-form");
    if (createWatchlistForm) {
        createWatchlistForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("watchlist-status", "Creating watchlist item...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/watchlist"), {
                    token: ui.requireAccessToken(),
                    body: {
                        symbol: ui.readValue("watchlist-symbol"),
                        min_score: ui.readNumber("watchlist-score", 65),
                        notify: ui.readCheckbox("watchlist-notify")
                    }
                });
                ui.renderJson("watchlist-output", payload);
                ui.setStatus("watchlist-status", `Created watchlist item for ${payload.symbol || ui.readValue("watchlist-symbol")}.`, "success");
            } catch (error) {
                ui.setStatus("watchlist-status", error.message, "error");
            }
        });
    }

    const loadPortfolioButton = ui.byId("load-portfolio");
    if (loadPortfolioButton) {
        loadPortfolioButton.addEventListener("click", () => {
            loadProtectedJson("/v1/portfolio", "portfolio-output", "portfolio-status");
        });
    }

    const createPortfolioForm = ui.byId("create-portfolio-form");
    if (createPortfolioForm) {
        createPortfolioForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("portfolio-status", "Creating portfolio position...");
            try {
                const payload = await ui.requestJson("POST", ui.publicApi("/v1/portfolio"), {
                    token: ui.requireAccessToken(),
                    body: {
                        symbol: ui.readValue("portfolio-symbol"),
                        shares: ui.readNumber("portfolio-shares", 1),
                        avg_cost: ui.readNumber("portfolio-cost", 1),
                        target_profit: ui.readNumber("portfolio-target", 0.15),
                        stop_loss: ui.readNumber("portfolio-stop", 0.08),
                        notify: ui.readCheckbox("portfolio-notify"),
                        notes: ui.readValue("portfolio-notes") || null
                    }
                });
                ui.renderJson("portfolio-output", payload);
                ui.setStatus("portfolio-status", `Created position for ${payload.symbol || ui.readValue("portfolio-symbol")}.`, "success");
            } catch (error) {
                ui.setStatus("portfolio-status", error.message, "error");
            }
        });
    }

    ui.renderSessionSnapshot("session-output");
});
"""

_PLATFORM_SCRIPT = """
window.addEventListener("DOMContentLoaded", () => {
    const ui = window.stockPyUi;

    const searchForm = ui.byId("symbol-search-form");
    if (searchForm) {
        searchForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("search-status", "Searching symbols...");
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
                ui.setStatus("search-status", `Loaded ${(payload.items || []).length} search results.`, "success");
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
            ui.setStatus("platform-watchlist-status", `Selected ${symbol} for the watchlist form.`, "success");
        });
    }

    const showPlatformSessionButton = ui.byId("show-platform-session");
    if (showPlatformSessionButton) {
        showPlatformSessionButton.addEventListener("click", () => {
            ui.renderSessionSnapshot("platform-session-output");
            ui.setStatus("platform-session-status", "Rendered shared public session snapshot.", "success");
        });
    }

    const clearPlatformSessionButton = ui.byId("clear-platform-session");
    if (clearPlatformSessionButton) {
        clearPlatformSessionButton.addEventListener("click", () => {
            ui.clearPublicSession();
            ui.renderSessionSnapshot("platform-session-output");
            ui.setStatus("platform-session-status", "Cleared shared public session tokens.", "success");
        });
    }

    async function loadProtectedJson(path, outputId, statusId) {
        ui.setStatus(statusId, "Loading...");
        try {
            const payload = await ui.requestJson("GET", ui.publicApi(path), {
                token: ui.requireAccessToken()
            });
            ui.renderJson(outputId, payload);
            ui.setStatus(statusId, "Loaded successfully.", "success");
        } catch (error) {
            ui.setStatus(statusId, error.message, "error");
        }
    }

    const addWatchlistForm = ui.byId("platform-watchlist-form");
    if (addWatchlistForm) {
        addWatchlistForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("platform-watchlist-status", "Creating watchlist item...");
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
                ui.setStatus("platform-watchlist-status", `Queued ${payload.symbol || ui.readValue("platform-watchlist-symbol")} into the watchlist.`, "success");
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

    const appTradeForm = ui.byId("app-trade-form");
    if (appTradeForm) {
        appTradeForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("trade-status", "Loading authenticated trade info...");
            try {
                const tradeId = ui.readValue("app-trade-id");
                const payload = await ui.requestJson(
                    "GET",
                    ui.publicApi(`/v1/trades/${encodeURIComponent(tradeId)}/app-info`),
                    { token: ui.requireAccessToken() }
                );
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", `Loaded app trade info for ${tradeId}.`, "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    const publicTradeForm = ui.byId("public-trade-form");
    if (publicTradeForm) {
        publicTradeForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            ui.setStatus("trade-status", "Loading public trade info...");
            try {
                const tradeId = ui.readValue("public-trade-id");
                const token = ui.readValue("public-trade-token");
                const params = new URLSearchParams({ t: token });
                const payload = await ui.requestJson(
                    "GET",
                    `${ui.publicApi(`/v1/trades/${encodeURIComponent(tradeId)}/info`)}?${params.toString()}`
                );
                ui.renderJson("trade-output", payload);
                ui.setStatus("trade-status", `Loaded public trade info for ${tradeId}.`, "success");
            } catch (error) {
                ui.setStatus("trade-status", error.message, "error");
            }
        });
    }

    ui.renderSessionSnapshot("platform-session-output");
});
"""

_ADMIN_SCRIPT = """
window.addEventListener("DOMContentLoaded", () => {
    const ui = window.stockPyUi;

    if (ui.byId("admin-token")) {
        ui.byId("admin-token").value = ui.getAdminToken();
    }

    const saveTokenButton = ui.byId("save-admin-token");
    if (saveTokenButton) {
        saveTokenButton.addEventListener("click", () => {
            const token = ui.setAdminToken(ui.readValue("admin-token"));
            ui.renderSessionSnapshot("admin-session-output");
            ui.setStatus(
                "admin-auth-status",
                token ? `Stored admin bearer token (${token.length} chars).` : "Cleared admin bearer token.",
                "success"
            );
        });
    }

    const clearTokenButton = ui.byId("clear-admin-token");
    if (clearTokenButton) {
        clearTokenButton.addEventListener("click", () => {
            ui.setAdminToken("");
            if (ui.byId("admin-token")) {
                ui.byId("admin-token").value = "";
            }
            ui.renderSessionSnapshot("admin-session-output");
            ui.setStatus("admin-auth-status", "Cleared admin bearer token.", "success");
        });
    }

    const showAdminSessionButton = ui.byId("show-admin-session");
    if (showAdminSessionButton) {
        showAdminSessionButton.addEventListener("click", () => {
            ui.renderSessionSnapshot("admin-session-output");
            ui.setStatus("admin-session-status", "Rendered current UI endpoint and token state.", "success");
        });
    }

    function readWindowHours() {
        return ui.readNumber("admin-window-hours", 24);
    }

    async function loadAdminJson(path, outputId, statusId) {
        ui.setStatus(statusId, "Loading...");
        try {
            const payload = await ui.requestJson("GET", ui.adminApi(path), {
                token: ui.requireAdminToken()
            });
            ui.renderJson(outputId, payload);
            ui.setStatus(statusId, "Loaded successfully.", "success");
        } catch (error) {
            ui.setStatus(statusId, error.message, "error");
        }
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
            <h2>Endpoint Wiring</h2>
            <p class=\"panel-copy\">This shell is rendered by Python. Update endpoints here when you access public-api directly instead of through nginx.</p>
        </div>
        <span class=\"pill\">HTML + Python</span>
    </div>
    <div class=\"field-grid\">
        <label>
            Public API base URL
            <input id=\"public-api-base\" type=\"url\" placeholder=\"http://localhost:8000\">
        </label>
        <label>
            Admin API base URL
            <input id=\"admin-api-base\" type=\"url\" placeholder=\"http://localhost:8080\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"save-base-urls\">Save endpoints</button>
    </div>
    <div class=\"status\" id=\"base-url-status\"></div>
</section>
"""

_APP_BODY = _BASE_CONNECTION_PANEL + """
<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>Subscriber Session</h2>
            <p class=\"panel-copy\">Request a verification code, exchange it for bearer tokens, and reuse that session across `/app` and `/platform`.</p>
        </div>
        <span class=\"pill\">/v1/auth/*</span>
    </div>
    <form id=\"send-code-form\">
        <div class=\"field-grid single\">
            <label>
                Email
                <input id=\"auth-email\" type=\"email\" placeholder=\"user@example.com\" required>
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\">Send code</button>
        </div>
    </form>
    <form id=\"verify-form\">
        <div class=\"field-grid\">
            <label>
                Verify email
                <input id=\"verify-email\" type=\"email\" placeholder=\"user@example.com\" required>
            </label>
            <label>
                6-digit code
                <input id=\"verify-code\" type=\"text\" maxlength=\"6\" placeholder=\"123456\" required>
            </label>
            <label>
                Locale
                <input id=\"verify-locale\" type=\"text\" placeholder=\"zh-TW\">
            </label>
            <label>
                Timezone
                <input id=\"verify-timezone\" type=\"text\" placeholder=\"Asia/Taipei\">
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\">Verify and store session</button>
            <button type=\"button\" class=\"secondary\" id=\"refresh-session\">Refresh token</button>
            <button type=\"button\" class=\"ghost\" id=\"logout-session\">Logout</button>
        </div>
    </form>
    <div class=\"status\" id=\"auth-status\"></div>
    <pre class=\"json-output\" id=\"auth-output\"></pre>
</section>

<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>Stored Browser State</h2>
            <p class=\"panel-copy\">Useful when you want to confirm which base URLs and tokens are currently cached locally.</p>
        </div>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"show-session\">Show current session</button>
    </div>
    <div class=\"status\" id=\"session-status\"></div>
    <pre class=\"json-output\" id=\"session-output\"></pre>
</section>

<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>Account</h2>
            <p class=\"panel-copy\">Direct access to subscriber profile and dashboard endpoints.</p>
        </div>
        <span class=\"pill\">/v1/account/*</span>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-profile\">Load profile</button>
        <button type=\"button\" class=\"secondary\" id=\"load-dashboard\">Load dashboard</button>
    </div>
    <div class=\"status\" id=\"account-status\"></div>
    <pre class=\"json-output\" id=\"account-output\"></pre>
    <pre class=\"json-output\" id=\"dashboard-output\"></pre>
</section>

<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>Notifications</h2>
            <p class=\"panel-copy\">List notifications, mark everything read, or acknowledge specific receipts by notification ID.</p>
        </div>
        <span class=\"pill\">/v1/notifications/*</span>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-notifications\">Load notifications</button>
        <button type=\"button\" class=\"secondary\" id=\"mark-all-read\">Mark all read</button>
    </div>
    <div class=\"field-grid single\">
        <label>
            Notification ID
            <input id=\"notification-id\" type=\"text\" placeholder=\"notification-123\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"mark-notification-read\">Mark selected read</button>
        <button type=\"button\" class=\"ghost\" id=\"ack-notification\">Acknowledge selected</button>
    </div>
    <div class=\"status\" id=\"notifications-status\"></div>
    <pre class=\"json-output\" id=\"notifications-output\"></pre>
</section>

<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>Watchlist Intake</h2>
            <p class=\"panel-copy\">Create new watchlist rows without any frontend build step.</p>
        </div>
        <span class=\"pill\">/v1/watchlist</span>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"load-watchlist\">Load current watchlist</button>
    </div>
    <form id=\"create-watchlist-form\">
        <div class=\"field-grid\">
            <label>
                Symbol
                <input id=\"watchlist-symbol\" type=\"text\" placeholder=\"AAPL\" required>
            </label>
            <label>
                Minimum score
                <input id=\"watchlist-score\" type=\"number\" min=\"0\" max=\"100\" value=\"65\">
            </label>
        </div>
        <label class=\"inline-check\">
            <input id=\"watchlist-notify\" type=\"checkbox\" checked>
            Notify me when this symbol triggers
        </label>
        <div class=\"button-row\">
            <button type=\"submit\">Create watchlist item</button>
        </div>
    </form>
    <div class=\"status\" id=\"watchlist-status\"></div>
    <pre class=\"json-output\" id=\"watchlist-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>Portfolio Intake</h2>
            <p class=\"panel-copy\">Add positions using plain forms against the existing portfolio API.</p>
        </div>
        <span class=\"pill\">/v1/portfolio</span>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"load-portfolio\">Load current portfolio</button>
    </div>
    <form id=\"create-portfolio-form\">
        <div class=\"field-grid\">
            <label>
                Symbol
                <input id=\"portfolio-symbol\" type=\"text\" placeholder=\"AAPL\" required>
            </label>
            <label>
                Shares
                <input id=\"portfolio-shares\" type=\"number\" min=\"1\" value=\"10\">
            </label>
            <label>
                Average cost
                <input id=\"portfolio-cost\" type=\"number\" step=\"0.01\" min=\"0.01\" value=\"150\">
            </label>
            <label>
                Target profit
                <input id=\"portfolio-target\" type=\"number\" step=\"0.01\" min=\"0.01\" max=\"1\" value=\"0.15\">
            </label>
            <label>
                Stop loss
                <input id=\"portfolio-stop\" type=\"number\" step=\"0.01\" min=\"0.01\" max=\"1\" value=\"0.08\">
            </label>
            <label>
                Notes
                <input id=\"portfolio-notes\" type=\"text\" placeholder=\"Why this position exists\">
            </label>
        </div>
        <label class=\"inline-check\">
            <input id=\"portfolio-notify\" type=\"checkbox\" checked>
            Notify on profit or stop-loss thresholds
        </label>
        <div class=\"button-row\">
            <button type=\"submit\">Create position</button>
        </div>
    </form>
    <div class=\"status\" id=\"portfolio-status\"></div>
    <pre class=\"json-output\" id=\"portfolio-output\"></pre>
</section>
"""

_PLATFORM_BODY = _BASE_CONNECTION_PANEL + """
<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>Shared Session Snapshot</h2>
            <p class=\"panel-copy\">`/platform` reuses the same subscriber bearer tokens stored from `/app`.</p>
        </div>
        <span class=\"pill\">Token reuse</span>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" class=\"secondary\" id=\"show-platform-session\">Show current session</button>
        <button type=\"button\" class=\"ghost\" id=\"clear-platform-session\">Clear public session</button>
    </div>
    <div class=\"status\" id=\"platform-session-status\"></div>
    <pre class=\"json-output\" id=\"platform-session-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>Symbol Search</h2>
            <p class=\"panel-copy\">Search live public symbols, then push the chosen ticker into the watchlist form below.</p>
        </div>
        <span class=\"pill\">/v1/search/symbols</span>
    </div>
    <form id=\"symbol-search-form\">
        <div class=\"field-grid\">
            <label>
                Query
                <input id=\"search-query\" type=\"text\" placeholder=\"AAPL or Taiwan Semiconductor\" required>
            </label>
            <label>
                Asset type
                <input id=\"search-type\" type=\"text\" placeholder=\"stock, etf, crypto\">
            </label>
            <label>
                Limit
                <input id=\"search-limit\" type=\"number\" min=\"1\" max=\"50\" value=\"20\">
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\">Search symbols</button>
        </div>
    </form>
    <div class=\"status\" id=\"search-status\"></div>
    <div class=\"table-wrap\" id=\"search-results\"><div class=\"empty-state\">Search results will render here.</div></div>
    <pre class=\"json-output\" id=\"search-output\"></pre>
</section>

<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>Watchlist and Portfolio</h2>
            <p class=\"panel-copy\">Operate the shared research watchlist and portfolio surfaces from one place.</p>
        </div>
        <span class=\"pill\">Subscriber API</span>
    </div>
    <form id=\"platform-watchlist-form\">
        <div class=\"field-grid\">
            <label>
                Symbol
                <input id=\"platform-watchlist-symbol\" type=\"text\" placeholder=\"AAPL\" required>
            </label>
            <label>
                Minimum score
                <input id=\"platform-watchlist-score\" type=\"number\" min=\"0\" max=\"100\" value=\"70\">
            </label>
        </div>
        <label class=\"inline-check\">
            <input id=\"platform-watchlist-notify\" type=\"checkbox\" checked>
            Notify when this symbol becomes actionable
        </label>
        <div class=\"button-row\">
            <button type=\"submit\">Add to watchlist</button>
            <button type=\"button\" class=\"secondary\" id=\"platform-load-watchlist\">Load watchlist</button>
            <button type=\"button\" class=\"ghost\" id=\"platform-load-portfolio\">Load portfolio</button>
        </div>
    </form>
    <div class=\"status\" id=\"platform-watchlist-status\"></div>
    <pre class=\"json-output\" id=\"platform-watchlist-output\"></pre>
    <div class=\"status\" id=\"platform-portfolio-status\"></div>
    <pre class=\"json-output\" id=\"platform-portfolio-output\"></pre>
</section>

<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>Trade Lookup</h2>
            <p class=\"panel-copy\">Use the authenticated app endpoint or a public link token to inspect a trade without any JS framework.</p>
        </div>
        <span class=\"pill\">/v1/trades/*</span>
    </div>
    <form id=\"app-trade-form\">
        <div class=\"field-grid single\">
            <label>
                Trade ID for authenticated app-info
                <input id=\"app-trade-id\" type=\"text\" placeholder=\"trade-123\" required>
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\">Load app trade info</button>
        </div>
    </form>
    <form id=\"public-trade-form\">
        <div class=\"field-grid\">
            <label>
                Public trade ID
                <input id=\"public-trade-id\" type=\"text\" placeholder=\"trade-123\" required>
            </label>
            <label>
                Public link token
                <input id=\"public-trade-token\" type=\"text\" placeholder=\"token-123\" required>
            </label>
        </div>
        <div class=\"button-row\">
            <button type=\"submit\" class=\"secondary\">Load public trade info</button>
        </div>
    </form>
    <div class=\"status\" id=\"trade-status\"></div>
    <pre class=\"json-output\" id=\"trade-output\"></pre>
</section>
"""

_ADMIN_BODY = _BASE_CONNECTION_PANEL + """
<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>Admin Bearer Token</h2>
            <p class=\"panel-copy\">The admin shell is intentionally explicit about auth because there is still no dedicated admin login route in the backend.</p>
        </div>
        <span class=\"pill\">Bearer only</span>
    </div>
    <div class=\"field-grid single\">
        <label>
            Admin access token
            <textarea id=\"admin-token\" placeholder=\"Paste a bearer token here\"></textarea>
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"save-admin-token\">Save token</button>
        <button type=\"button\" class=\"secondary\" id=\"show-admin-session\">Show admin session</button>
        <button type=\"button\" class=\"ghost\" id=\"clear-admin-token\">Clear token</button>
    </div>
    <div class=\"status\" id=\"admin-auth-status\"></div>
    <div class=\"status\" id=\"admin-session-status\"></div>
    <pre class=\"json-output\" id=\"admin-session-output\"></pre>
</section>

<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>Analytics</h2>
            <p class=\"panel-copy\">Overview, distribution, strategy health, and TradingAgents read models.</p>
        </div>
        <span class=\"pill\">/v1/admin/analytics/*</span>
    </div>
    <div class=\"field-grid single\">
        <label>
            Window hours
            <input id=\"admin-window-hours\" type=\"number\" min=\"1\" max=\"720\" value=\"24\">
        </label>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-overview\">Load overview</button>
        <button type=\"button\" class=\"secondary\" id=\"load-distribution\">Load distribution</button>
        <button type=\"button\" class=\"secondary\" id=\"load-strategy-health\">Load strategy health</button>
        <button type=\"button\" class=\"ghost\" id=\"load-tradingagents\">Load TradingAgents</button>
    </div>
    <div class=\"status\" id=\"admin-analytics-status\"></div>
    <pre class=\"json-output\" id=\"admin-analytics-output\"></pre>
</section>

<section class=\"panel\">
    <div class=\"panel-header\">
        <div>
            <h2>Runtime</h2>
            <p class=\"panel-copy\">Inspect component health, runtime metrics, and current alert state from the admin API.</p>
        </div>
        <span class=\"pill\">/v1/admin/runtime/*</span>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-runtime-health\">Load health</button>
        <button type=\"button\" class=\"secondary\" id=\"load-runtime-metrics\">Load metrics</button>
        <button type=\"button\" class=\"ghost\" id=\"load-runtime-alerts\">Load alerts</button>
    </div>
    <div class=\"status\" id=\"admin-runtime-status\"></div>
    <pre class=\"json-output\" id=\"admin-runtime-output\"></pre>
</section>

<section class=\"panel wide\">
    <div class=\"panel-header\">
        <div>
            <h2>Acceptance and Release Evidence</h2>
            <p class=\"panel-copy\">Pull the readiness report and the artifact inventory that backs cutover and OpenAPI validation.</p>
        </div>
        <span class=\"pill\">/v1/admin/acceptance/*</span>
    </div>
    <div class=\"button-row\">
        <button type=\"button\" id=\"load-acceptance-status\">Load acceptance status</button>
        <button type=\"button\" class=\"secondary\" id=\"load-acceptance-report\">Load acceptance report</button>
    </div>
    <div class=\"status\" id=\"admin-acceptance-status\"></div>
    <pre class=\"json-output\" id=\"admin-acceptance-output\"></pre>
</section>
"""

_PAGE_META = {
    "app": {
        "title": "StockPy App",
        "hero_title": "Subscriber workflows stay inside stock-py now.",
        "hero_copy": "This route is served directly by Python and talks to the same public API used by the mobile subscriber surface. It keeps verification-code login, dashboard reads, notifications, watchlist intake, and portfolio capture without a Node toolchain.",
        "body": _APP_BODY,
        "script": _APP_SCRIPT,
    },
    "platform": {
        "title": "StockPy Platform",
        "hero_title": "Research and trade lookup without a frontend workspace.",
        "hero_copy": "The platform surface runs as a plain HTML control room over public endpoints. Search symbols, inspect trades, and reuse the subscriber bearer session directly from the browser.",
        "body": _PLATFORM_BODY,
        "script": _PLATFORM_SCRIPT,
    },
    "admin": {
        "title": "StockPy Admin",
        "hero_title": "Admin analytics and runtime control on the same deployment baseline.",
        "hero_copy": "This is a pure HTML shell for the admin API. It intentionally keeps bearer-token entry explicit while the backend still lacks a dedicated admin login route.",
        "body": _ADMIN_BODY,
        "script": _ADMIN_SCRIPT,
    },
}


def _render_nav(surface: SurfaceName) -> str:
    items = [
        ("app", "/app", "Subscriber"),
        ("platform", "/platform", "Platform"),
        ("admin", "/admin", "Admin"),
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