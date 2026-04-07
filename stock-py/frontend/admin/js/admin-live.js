(function () {
    const STORAGE_KEYS = {
        baseUrl: "admin_api_url",
        token: "admin_api_token",
        operatorId: "admin_operator_id"
    };

    const LEGACY_KEYS = {
        token: "stockpy.ui.admin-token",
        operatorId: "stockpy.ui.admin-operator-id"
    };

    function getQueryParam(name) {
        try {
            const params = new URLSearchParams(window.location.search || "");
            return params.get(name) || "";
        } catch (_err) {
            return "";
        }
    }

    function defaultBaseUrl() {
        if (window.location.port === "8001") {
            return window.location.origin;
        }
        const host = window.location.hostname || "localhost";
        return `${window.location.protocol}//${host}:8001`;
    }

    function normalizeBaseUrl(value) {
        const raw = String(value || "").trim();
        if (!raw) return "";
        return raw.replace(/\/+$/, "");
    }

    function normalizeOperatorId(value) {
        return String(value || "").trim();
    }

    function escapeHtml(value) {
        return String(value || "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    let currentBaseUrl = normalizeBaseUrl(
        getQueryParam("admin_api_base_url") ||
            localStorage.getItem(STORAGE_KEYS.baseUrl) ||
            defaultBaseUrl()
    );

    const defaultPermanentToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYWRtaW4iLCJpc19hZG1pbiI6dHJ1ZSwic2NvcGVzIjpbIioiXSwidHlwZSI6ImFjY2VzcyIsInBsYW4iOiJlbnRlcnByaXNlIiwic3ViIjoiOTk5OTkiLCJpYXQiOjE3NzU1OTg1MzIsImV4cCI6NDkyOTE5ODUzMn0.Ekn7fSIHWkHuzB6Y8lyW6_DPSpGTrhCv3Z0xA_lvGps";
    const defaultPermanentOperator = "99999";

    // Auto-migrate from the old invalid token if found
    if (localStorage.getItem(STORAGE_KEYS.token) && localStorage.getItem(STORAGE_KEYS.token).includes("ZYuEey")) {
        localStorage.removeItem(STORAGE_KEYS.token);
    }
    if (localStorage.getItem(LEGACY_KEYS.token) && localStorage.getItem(LEGACY_KEYS.token).includes("ZYuEey")) {
        localStorage.removeItem(LEGACY_KEYS.token);
    }
    if (localStorage.getItem(STORAGE_KEYS.operatorId) === "admin-operator") {
        localStorage.removeItem(STORAGE_KEYS.operatorId);
    }
    
    // Unconditionally seed the localstorage with the long-lived token
    if (!localStorage.getItem(STORAGE_KEYS.token) || localStorage.getItem(STORAGE_KEYS.token).length < 20) {
        localStorage.setItem(STORAGE_KEYS.token, defaultPermanentToken);
        localStorage.setItem(STORAGE_KEYS.operatorId, defaultPermanentOperator);
    }

    let currentToken = String(
        localStorage.getItem(STORAGE_KEYS.token) ||
            localStorage.getItem(LEGACY_KEYS.token) ||
            defaultPermanentToken
    ).trim();
    let currentOperatorId = normalizeOperatorId(
        localStorage.getItem(STORAGE_KEYS.operatorId) ||
            localStorage.getItem(LEGACY_KEYS.operatorId) ||
            defaultPermanentOperator
    );

    function setBaseUrl(value) {
        const normalized = normalizeBaseUrl(value);
        if (!normalized) return currentBaseUrl;
        currentBaseUrl = normalized;
        localStorage.setItem(STORAGE_KEYS.baseUrl, currentBaseUrl);
        return currentBaseUrl;
    }

    function setToken(value) {
        currentToken = String(value || "").trim();
        if (currentToken) {
            localStorage.setItem(STORAGE_KEYS.token, currentToken);
        } else {
            localStorage.removeItem(STORAGE_KEYS.token);
        }
        return currentToken;
    }

    function setOperatorId(value) {
        currentOperatorId = normalizeOperatorId(value);
        if (currentOperatorId) {
            localStorage.setItem(STORAGE_KEYS.operatorId, currentOperatorId);
        } else {
            localStorage.removeItem(STORAGE_KEYS.operatorId);
        }
        return currentOperatorId;
    }

    async function request(path, options) {
        const opts = options || {};
        const method = String(opts.method || "GET").toUpperCase();
        const rawPath = String(path || "").trim();
        if (!rawPath) {
            throw new Error("API 路径不能为空");
        }

        const normalizedPath = rawPath.startsWith("/") ? rawPath : `/${rawPath}`;
        const url = `${currentBaseUrl}${normalizedPath}`;

        const headers = new Headers(opts.headers || {});
        if (!headers.has("Accept")) {
            headers.set("Accept", "application/json");
        }
        const hasBody =
            opts.body !== undefined &&
            opts.body !== null &&
            method !== "GET" &&
            method !== "HEAD";
        if (hasBody && !(opts.body instanceof FormData) && !headers.has("Content-Type")) {
            headers.set("Content-Type", "application/json");
        }
        if (currentToken && !headers.has("Authorization")) {
            headers.set("Authorization", `Bearer ${currentToken}`);
        }

        const explicitOperatorId = normalizeOperatorId(opts.operatorId);
        const operatorId = explicitOperatorId || (opts.operatorRequired ? currentOperatorId : "");
        if (operatorId && !headers.has("X-Operator-ID")) {
            headers.set("X-Operator-ID", operatorId);
        }

        const response = await fetch(url, {
            method,
            headers,
            body: hasBody ? opts.body : undefined
        });

        let payload = null;
        const contentType = response.headers.get("content-type") || "";
        if (response.status !== 204) {
            if (contentType.includes("application/json")) {
                payload = await response.json();
            } else {
                payload = await response.text();
            }
        }

        if (!response.ok) {
            let message = `HTTP ${response.status}`;
            if (payload && typeof payload === "object") {
                message = payload.message || payload.detail || payload.code || message;
            } else if (typeof payload === "string" && payload.trim()) {
                message = payload.trim();
            }
            const error = new Error(message);
            error.status = response.status;
            error.payload = payload;
            error.url = url;
            throw error;
        }

        return payload;
    }

    async function safeRequest(path, options) {
        try {
            const data = await request(path, options);
            return { ok: true, data };
        } catch (error) {
            return { ok: false, error };
        }
    }

    window.AdminAPI = {
        ...(window.AdminAPI || {}),
        getBaseUrl: function () {
            return currentBaseUrl;
        },
        setBaseUrl,
        getToken: function () {
            return currentToken;
        },
        setToken,
        getOperatorId: function () {
            return currentOperatorId;
        },
        setOperatorId,
        request,
        safeRequest
    };

    function ensurePanelStyles() {
        if (document.getElementById("admin-live-panel-style")) {
            return;
        }

        const style = document.createElement("style");
        style.id = "admin-live-panel-style";
        style.textContent = `
            #admin-live-panel {
                position: fixed;
                top: 12px;
                right: 12px;
                z-index: 9999;
                width: min(460px, calc(100vw - 24px));
                max-height: calc(100vh - 24px);
                overflow: auto;
                background: rgba(14, 42, 93, 0.96);
                color: #f7f9ff;
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 12px;
                padding: 10px;
                box-shadow: 0 14px 34px rgba(0, 0, 0, 0.35);
            }

            .admin-live-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 8px;
                margin-bottom: 8px;
            }

            .admin-live-title {
                font-size: 13px;
                font-weight: 700;
            }

            .admin-live-hint {
                font-size: 12px;
                opacity: 0.86;
            }

            .admin-live-fields {
                display: grid;
                grid-template-columns: 2fr 2fr 1fr;
                gap: 8px;
                align-items: center;
            }

            .admin-live-input {
                height: 34px;
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.22);
                background: rgba(10, 18, 35, 0.75);
                color: #f7f9ff;
                padding: 0 10px;
                width: 100%;
                min-width: 0;
            }

            .admin-live-actions {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 8px;
                margin-top: 8px;
            }

            .admin-live-btn {
                height: 34px;
                padding: 0 10px;
                border-radius: 8px;
                border: 0;
                color: #fff;
                cursor: pointer;
                white-space: nowrap;
            }

            #admin-live-save {
                background: #175cd3;
            }

            #admin-live-ping {
                background: #f06a3d;
            }

            #admin-live-hide {
                background: rgba(255, 255, 255, 0.16);
            }

            #admin-live-status {
                font-size: 12px;
                opacity: 0.88;
                margin-top: 8px;
                min-height: 16px;
            }

            #admin-live-launcher {
                position: fixed;
                top: 12px;
                right: 12px;
                z-index: 9998;
                height: 36px;
                border: 0;
                border-radius: 8px;
                padding: 0 12px;
                color: #fff;
                background: rgba(14, 42, 93, 0.96);
                box-shadow: 0 10px 24px rgba(0, 0, 0, 0.35);
                cursor: pointer;
                font-size: 12px;
                white-space: nowrap;
                align-items: center;
                display: none;
            }

            #admin-live-launcher[data-tone="error"] {
                background: rgba(185, 28, 28, 0.94);
            }

            #admin-live-launcher[data-tone="warn"] {
                background: rgba(180, 83, 9, 0.94);
            }

            @media (max-width: 760px) {
                .admin-live-fields {
                    grid-template-columns: 1fr;
                }

                .admin-live-actions {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }

                #admin-live-hide {
                    grid-column: 1 / -1;
                }
            }
        `;
        document.head.appendChild(style);
    }

    function setupConnectionPanel() {
        if (document.getElementById("admin-live-panel")) {
            return;
        }

        ensurePanelStyles();

        const panel = document.createElement("div");
        panel.id = "admin-live-panel";

        panel.innerHTML = `
            <div class="admin-live-header">
                <strong class="admin-live-title">管理端实时连接</strong>
                <span class="admin-live-hint">Bearer + X-Operator-ID</span>
            </div>
            <div class="admin-live-fields">
                <input id="admin-live-url" class="admin-live-input" type="text" value="${escapeHtml(currentBaseUrl)}" placeholder="API 地址">
                <input id="admin-live-token" class="admin-live-input" type="password" value="${escapeHtml(currentToken)}" placeholder="Bearer 令牌">
                <input id="admin-live-operator" class="admin-live-input" type="text" value="${escapeHtml(currentOperatorId)}" placeholder="操作员 ID">
            </div>
            <div class="admin-live-actions">
                <button id="admin-live-save" class="admin-live-btn" type="button">确定</button>
                <button id="admin-live-ping" class="admin-live-btn" type="button">连通测试</button>
                <button id="admin-live-hide" class="admin-live-btn" type="button">关闭</button>
            </div>
            <div id="admin-live-status">未连接</div>
        `;

        const launcher = document.createElement("button");
        launcher.id = "admin-live-launcher";
        launcher.type = "button";
        launcher.textContent = "连接失效，点击修复";

        document.body.appendChild(panel);
        document.body.appendChild(launcher);

        const urlInput = document.getElementById("admin-live-url");
        const tokenInput = document.getElementById("admin-live-token");
        const operatorInput = document.getElementById("admin-live-operator");
        const statusNode = document.getElementById("admin-live-status");
        const hideButton = document.getElementById("admin-live-hide");
        const saveButton = document.getElementById("admin-live-save");
        const pingButton = document.getElementById("admin-live-ping");

        let connectionInvalid = false;

        function showPanel() {
            panel.style.display = "block";
            launcher.style.display = "none";
        }

        function hidePanel() {
            panel.style.display = "none";
            if (connectionInvalid) {
                launcher.style.display = "inline-flex";
            } else {
                launcher.style.display = "none";
            }
        }

        function markConnectionInvalid(tone) {
            connectionInvalid = true;
            launcher.style.display = "inline-flex";
            launcher.textContent = "连接失效，点击修复";
            launcher.dataset.tone = tone || "error";
        }

        function markConnectionHealthy() {
            connectionInvalid = false;
            launcher.style.display = "none";
            launcher.removeAttribute("data-tone");
            launcher.textContent = "连接失效，点击修复";
            panel.style.display = "none";
        }

        panel.style.display = "none";

        hideButton.addEventListener("click", function () {
            hidePanel();
        });

        launcher.addEventListener("click", function () {
            showPanel();
        });

        function setStatus(text, tone) {
            if (!statusNode) return;
            statusNode.textContent = text;
            if (tone === "ok") statusNode.style.color = "#4ade80";
            else if (tone === "warn") statusNode.style.color = "#fbbf24";
            else if (tone === "error") statusNode.style.color = "#f87171";
            else statusNode.style.color = "#dbeafe";
        }

        async function validateConnection(openPanelOnInvalid) {
            if (!window.AdminAPI.getToken()) {
                setStatus("连接失效：未设置 Bearer Token。", "warn");
                markConnectionInvalid("warn");
                if (openPanelOnInvalid) {
                    showPanel();
                }
                return false;
            }

            setStatus("正在验证连接状态...", "warn");
            const result = await safeRequest("/v1/admin/acceptance/status", { method: "GET" });
            if (result.ok) {
                setStatus("连接正常，已自动隐藏连接面板。", "ok");
                markConnectionHealthy();
                return true;
            }

            setStatus(`连接失效：${result.error.message}`, "error");
            markConnectionInvalid("error");
            if (openPanelOnInvalid) {
                showPanel();
            }
            return false;
        }

        saveButton.addEventListener("click", async function () {
            setBaseUrl(urlInput.value);
            setToken(tokenInput.value);
            setOperatorId(operatorInput.value);
            setStatus("设置已保存，正在验证连接...", "warn");
            await validateConnection(true);
        });

        pingButton.addEventListener("click", async function () {
            setBaseUrl(urlInput.value);
            setToken(tokenInput.value);
            setOperatorId(operatorInput.value);
            await validateConnection(true);
        });

        validateConnection(false);
    }

    document.addEventListener("DOMContentLoaded", function () {
        setupConnectionPanel();
    });
})();
