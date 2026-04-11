const platformDeckConstants = window.PlatformDeckConstants || {};
const platformDeckUtils = window.PlatformDeckUtils || {};
const platformDeckTradingAgents = window.PlatformDeckTradingAgents || {};
const platformDeckWorkspace = window.PlatformDeckWorkspace || {};

function platformDeck() {
    const tradingAgentsState = platformDeckTradingAgents.createState
        ? platformDeckTradingAgents.createState(platformDeckConstants)
        : {};
    const tradingAgentsModule = platformDeckTradingAgents.createModule
        ? platformDeckTradingAgents.createModule(platformDeckUtils)
        : {};
    const workspaceState = platformDeckWorkspace.createState
        ? platformDeckWorkspace.createState()
        : {};
    const workspaceModule = platformDeckWorkspace.createModule
        ? platformDeckWorkspace.createModule()
        : {};

    return {
        storageKeys: { ...(platformDeckConstants.storageKeys || {}) },
        nowLabel: '--:--:-- UTC',
        lastUpdatedLabel: '--',
        loading: false,
        statusMessage: '等待同步',
        statusType: 'info',
        watchFilter: 'all',
        selectedSymbol: '',
        isRunningBacktest: false,
        workspaceModes: (platformDeckConstants.workspaceModes || []).map((item) => ({ ...item })),
        config: { ...(platformDeckConstants.defaultConfig || {}) },
        runForm: { ...(platformDeckConstants.defaultRunForm || {}) },
        adminAuth: {
            email: '',
            verifyEmail: '',
            code: '',
            locale: 'zh-CN',
            timezone: 'UTC',
            refreshToken: '',
            session: null,
            devCode: '',
            tokenSource: 'none',
            lastVerifiedAt: '',
            sending: false,
            verifying: false,
            refreshing: false,
            loggingOut: false,
            statusMessage: '等待管理员登录',
            statusType: 'info'
        },
        ...workspaceState,
        ...tradingAgentsState,
        summary: {
            active_signals: 0,
            triggered_signals: 0,
            avg_confidence: 0,
            avg_probability: 0
        },
        scannerSummary: {
            total_decisions: 0,
            emitted_decisions: 0,
            suppressed_decisions: 0,
            skipped_decisions: 0,
            total_runs: 0,
            running_runs: 0
        },
        watchlist: [],
        signalTape: [],
        funnelStages: (platformDeckConstants.defaultFunnelStages || []).map((item) => ({ ...item })),
        strategyRules: (platformDeckConstants.strategyRules || []).map((item) => ({ ...item })),
        strategyMix: [],
        rankings: [],
        strategyHealth: [],
        backtestRuns: [],
        consoleLines: [],
        refreshHandle: null,

        init() {
            this.loadConfig();
            this.updateClock();
            setInterval(() => this.updateClock(), 1000);
            this.log('info', '平台初始化完成，准备加载策略数据。');
            const bootPromise = this.adminAuth.refreshToken && !this.config.token
                ? this.refreshAdminSession({ silent: true, reload: false, keepStatus: true })
                : Promise.resolve(false);
            Promise.resolve(bootPromise).finally(() => {
                this.loadAll();
            });
            this.refreshHandle = setInterval(() => this.loadAll({ silent: true }), 45000);
            this.tradingAgentsPollHandle = setInterval(() => {
                this.pollPendingTradingAgentsRuns();
            }, 8000);
            this.$nextTick(() => {
                this.ensureActiveSectionVisible();
                this.registerDesktopObserver();
                if (window.lucide) {
                    window.lucide.createIcons();
                }
            });
        },

        defaultBaseUrl() {
            if (window.location.port === '8001') {
                return window.location.origin;
            }
            const host = window.location.hostname || 'localhost';
            return `${window.location.protocol}//${host}:8001`;
        },

        defaultPublicBaseUrl() {
            if (window.location.port === '8001') {
                const host = window.location.hostname || 'localhost';
                return `${window.location.protocol}//${host}:8000`;
            }
            if (window.location.origin && window.location.origin !== 'null') {
                return window.location.origin;
            }
            const host = window.location.hostname || 'localhost';
            return `${window.location.protocol}//${host}:8000`;
        },

        normalizeBaseUrl: platformDeckUtils.normalizeBaseUrl,

        parseWindowHours: platformDeckUtils.parseWindowHours,

        parseStoredJson(value, fallback = null) {
            const text = String(value || '').trim();
            if (!text) {
                return fallback;
            }
            try {
                return JSON.parse(text);
            } catch (error) {
                return fallback;
            }
        },

        loadConfig() {
            const params = new URLSearchParams(window.location.search || '');
            const queryBase = params.get('admin_api_base_url') || '';
            const queryPublicBase = params.get('public_api_base_url') || '';
            const queryToken = params.get('admin_api_token') || '';
            const routeMode = String(params.get('mode') || '').trim().toLowerCase();
            const routeSection = String(params.get('section') || '').trim();
            const routeSymbol = String(params.get('symbol') || '').trim().toUpperCase();
            const browserLocale = String(window.navigator && window.navigator.language || 'zh-CN').trim() || 'zh-CN';
            const browserTimezone = String(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC').trim() || 'UTC';
            const storedSession = this.parseStoredJson(localStorage.getItem(this.storageKeys.adminSession), null);
            const storedWorkspaceMode = localStorage.getItem(this.storageKeys.workspaceMode);
            const storedWorkspaceSection = localStorage.getItem(this.storageKeys.workspaceSection);
            this.config.baseUrl = this.normalizeBaseUrl(
                queryBase || localStorage.getItem(this.storageKeys.baseUrl) || this.defaultBaseUrl()
            );
            this.config.publicBaseUrl = this.normalizeBaseUrl(
                queryPublicBase || localStorage.getItem(this.storageKeys.publicBaseUrl) || this.defaultPublicBaseUrl()
            );
            this.config.token = String(
                queryToken ||
                localStorage.getItem(this.storageKeys.token) ||
                localStorage.getItem(this.storageKeys.legacyToken) ||
                ''
            ).trim();
            this.config.timeframe = String(
                localStorage.getItem(this.storageKeys.timeframe) || '1d'
            ).trim() || '1d';
            this.config.windowHours = this.parseWindowHours(
                localStorage.getItem(this.storageKeys.windowHours) || 168
            );
            this.adminAuth.email = String(localStorage.getItem(this.storageKeys.adminAuthEmail) || '').trim();
            this.adminAuth.verifyEmail = this.adminAuth.email;
            this.adminAuth.locale = String(localStorage.getItem(this.storageKeys.adminLocale) || browserLocale).trim() || browserLocale;
            this.adminAuth.timezone = String(localStorage.getItem(this.storageKeys.adminTimezone) || browserTimezone).trim() || browserTimezone;
            this.adminAuth.refreshToken = String(localStorage.getItem(this.storageKeys.adminRefreshToken) || '').trim();
            this.adminAuth.session = storedSession;
            this.adminAuth.tokenSource = String(
                localStorage.getItem(this.storageKeys.adminTokenSource)
                || (this.config.token ? 'manual' : (this.adminAuth.refreshToken ? 'admin-auth' : 'none'))
            ).trim() || 'none';
            this.adminAuth.lastVerifiedAt = String(localStorage.getItem(this.storageKeys.adminVerifiedAt) || '').trim();
            this.adminAuth.statusType = this.adminSessionReady() ? 'ok' : 'info';
            this.adminAuth.statusMessage = this.adminSessionReady()
                ? '已恢复策略会话。'
                : (this.config.token ? '已加载令牌，等待同步。' : '等待管理员登录');
            this.tradingAgentsIncludeFullPayload = localStorage.getItem(this.storageKeys.taIncludeFullPayload) === 'true';
            this.workspaceMode = this.normalizeWorkspaceMode(
                routeMode || storedWorkspaceMode || 'overview'
            );
            this.activeDesktopSectionId = String(
                routeSection || storedWorkspaceSection || 'trading-agents-panel'
            ).trim() || 'trading-agents-panel';
            this.selectedSymbol = routeSymbol;
            this.workspacePinned = Boolean(routeMode || routeSection || routeSymbol || storedWorkspaceMode || storedWorkspaceSection);
            this.workspaceAutoRouted = false;
        },

        saveConfig() {
            this.config.baseUrl = this.normalizeBaseUrl(this.config.baseUrl || this.defaultBaseUrl());
            this.config.publicBaseUrl = this.normalizeBaseUrl(this.config.publicBaseUrl || this.defaultPublicBaseUrl());
            this.config.token = String(this.config.token || '').trim();
            this.config.timeframe = String(this.config.timeframe || '1d').trim() || '1d';
            this.config.windowHours = this.parseWindowHours(this.config.windowHours);

            localStorage.setItem(this.storageKeys.baseUrl, this.config.baseUrl);
            localStorage.setItem(this.storageKeys.publicBaseUrl, this.config.publicBaseUrl);
            localStorage.setItem(this.storageKeys.timeframe, this.config.timeframe);
            localStorage.setItem(this.storageKeys.windowHours, String(this.config.windowHours));
            localStorage.setItem(
                this.storageKeys.taIncludeFullPayload,
                this.tradingAgentsIncludeFullPayload ? 'true' : 'false'
            );
            if (this.config.token) {
                localStorage.setItem(this.storageKeys.token, this.config.token);
                if (!this.adminAuth.session && this.adminAuth.tokenSource !== 'admin-auth') {
                    this.adminAuth.tokenSource = 'manual';
                }
            } else {
                localStorage.removeItem(this.storageKeys.token);
                if (!this.adminAuth.refreshToken) {
                    this.adminAuth.tokenSource = 'none';
                }
            }
            this.persistAdminAuthState();
            this.log('ok', '连接配置已保存。');
        },

        persistAdminAuthState() {
            const email = String(this.adminAuth.email || '').trim();
            const refreshToken = String(this.adminAuth.refreshToken || '').trim();
            const locale = String(this.adminAuth.locale || '').trim();
            const timezone = String(this.adminAuth.timezone || '').trim();
            const tokenSource = String(this.adminAuth.tokenSource || 'none').trim() || 'none';
            const lastVerifiedAt = String(this.adminAuth.lastVerifiedAt || '').trim();

            if (email) {
                localStorage.setItem(this.storageKeys.adminAuthEmail, email);
            } else {
                localStorage.removeItem(this.storageKeys.adminAuthEmail);
            }

            if (refreshToken) {
                localStorage.setItem(this.storageKeys.adminRefreshToken, refreshToken);
            } else {
                localStorage.removeItem(this.storageKeys.adminRefreshToken);
            }

            if (locale) {
                localStorage.setItem(this.storageKeys.adminLocale, locale);
            } else {
                localStorage.removeItem(this.storageKeys.adminLocale);
            }

            if (timezone) {
                localStorage.setItem(this.storageKeys.adminTimezone, timezone);
            } else {
                localStorage.removeItem(this.storageKeys.adminTimezone);
            }

            if (this.adminAuth.session) {
                localStorage.setItem(this.storageKeys.adminSession, JSON.stringify(this.adminAuth.session));
            } else {
                localStorage.removeItem(this.storageKeys.adminSession);
            }

            if (lastVerifiedAt) {
                localStorage.setItem(this.storageKeys.adminVerifiedAt, lastVerifiedAt);
            } else {
                localStorage.removeItem(this.storageKeys.adminVerifiedAt);
            }

            if (tokenSource && tokenSource !== 'none') {
                localStorage.setItem(this.storageKeys.adminTokenSource, tokenSource);
            } else {
                localStorage.removeItem(this.storageKeys.adminTokenSource);
            }
        },

        adminSessionReady() {
            return Boolean(
                this.config.token
                && this.adminAuth.session
                && this.adminAuth.session.user
                && this.adminAuth.session.admin
            );
        },

        currentAdminUser() {
            return this.adminAuth.session && this.adminAuth.session.user
                ? this.adminAuth.session.user
                : null;
        },

        currentAdminContext() {
            return this.adminAuth.session && this.adminAuth.session.admin
                ? this.adminAuth.session.admin
                : null;
        },

        adminActionBusy() {
            return Boolean(
                this.adminAuth.sending
                || this.adminAuth.verifying
                || this.adminAuth.refreshing
                || this.adminAuth.loggingOut
            );
        },

        adminSessionBadgeLabel() {
            if (this.adminSessionReady()) {
                return `${this.adminSessionRoleLabel()} 已连接`;
            }
            if (this.config.token && this.adminAuth.tokenSource === 'manual') {
                return '手动令牌已载入';
            }
            if (this.adminAuth.refreshToken) {
                return '会话待恢复';
            }
            return '未登录策略会话';
        },

        adminSessionBadgeClass() {
            if (this.adminSessionReady()) {
                return 'border-mint/35 bg-mint/10 text-mint';
            }
            if (this.adminAuth.statusType === 'warn') {
                return 'border-coral/35 bg-coral/10 text-coral';
            }
            if (this.config.token || this.adminAuth.refreshToken) {
                return 'border-sun/35 bg-sun/10 text-sun';
            }
            return 'border-ink/15 bg-white/80 text-ink/70';
        },

        adminSessionEmail() {
            const user = this.currentAdminUser();
            if (user && user.email) {
                return user.email;
            }
            return String(this.adminAuth.email || this.adminAuth.verifyEmail || '--').trim() || '--';
        },

        adminSessionRoleLabel() {
            const admin = this.currentAdminContext();
            const role = String(admin && admin.role || '').trim().toLowerCase();
            const mapping = {
                admin: '管理员',
                operator: '操作员',
                viewer: '观察员'
            };
            if (role) {
                return mapping[role] || role;
            }
            return this.adminAuth.tokenSource === 'manual' && this.config.token ? '手动令牌' : '未验证';
        },

        adminTokenSourceLabel() {
            const mapping = {
                'admin-auth': '来源 验证码会话',
                manual: '来源 手贴令牌',
                none: '来源 --'
            };
            return mapping[String(this.adminAuth.tokenSource || 'none').trim().toLowerCase()] || '来源 --';
        },

        adminSessionScopeLabel() {
            const admin = this.currentAdminContext();
            const scopes = Array.isArray(admin && admin.scopes) ? admin.scopes : [];
            if (scopes.length) {
                return `权限 ${scopes.slice(0, 3).join(', ')}${scopes.length > 3 ? '…' : ''}`;
            }
            if (this.adminAuth.refreshToken) {
                return '刷新令牌已保存';
            }
            return '权限待建立';
        },

        adminSessionVerifiedAtLabel() {
            if (!this.adminAuth.lastVerifiedAt) {
                return '最近验证 --';
            }
            return `最近验证 ${this.formatDateTime(this.adminAuth.lastVerifiedAt)}`;
        },

        markAdminAuthStatus(type, message) {
            this.adminAuth.statusType = String(type || 'info').trim() || 'info';
            this.adminAuth.statusMessage = String(message || '').trim() || '等待管理员登录';
        },

        persistAdminSession(payload, options = {}) {
            const user = payload && payload.user && typeof payload.user === 'object'
                ? { ...payload.user }
                : null;
            const admin = payload && payload.admin && typeof payload.admin === 'object'
                ? { ...payload.admin }
                : null;
            this.config.token = String(payload && payload.access_token || '').trim();
            this.adminAuth.refreshToken = String(payload && payload.refresh_token || '').trim();
            this.adminAuth.session = user || admin ? { user, admin } : null;
            this.adminAuth.email = String(user && user.email || this.adminAuth.verifyEmail || this.adminAuth.email || '').trim();
            this.adminAuth.verifyEmail = this.adminAuth.email;
            this.adminAuth.tokenSource = String(options.tokenSource || 'admin-auth').trim() || 'admin-auth';
            this.adminAuth.lastVerifiedAt = new Date().toISOString();
            if (options.clearCode !== false) {
                this.adminAuth.code = '';
            }
            if (options.clearDevCode !== false) {
                this.adminAuth.devCode = '';
            }
            if (this.config.token) {
                localStorage.setItem(this.storageKeys.token, this.config.token);
            }
            this.persistAdminAuthState();
            this.markAdminAuthStatus('ok', options.message || '策略权限会话已保存。');
        },

        clearLiveData() {
            this.summary = {
                active_signals: 0,
                triggered_signals: 0,
                avg_confidence: 0,
                avg_probability: 0
            };
            this.scannerSummary = {
                total_decisions: 0,
                emitted_decisions: 0,
                suppressed_decisions: 0,
                skipped_decisions: 0,
                total_runs: 0,
                running_runs: 0
            };
            this.watchlist = [];
            this.signalTape = [];
            this.funnelStages = (platformDeckConstants.defaultFunnelStages || []).map((item) => ({ ...item }));
            this.strategyMix = [];
            this.rankings = [];
            this.strategyHealth = [];
            this.backtestRuns = [];
            this.tradingAgentsRuns = [];
            this.tradingAgentsActiveRequestId = '';
            this.selectedSymbol = '';
            this.executionContextSource = '';
            this.executionContextUpdatedAt = '';
            this.workspaceAutoRouted = false;
            this.lastUpdatedLabel = '--';
        },

        clearAdminSession(options = {}) {
            const preserveEmail = options.preserveEmail !== false;
            const keepToken = Boolean(options.keepToken);
            const preservedEmail = preserveEmail
                ? String(this.adminAuth.email || this.adminAuth.verifyEmail || '').trim()
                : '';

            if (!keepToken) {
                this.config.token = '';
                localStorage.removeItem(this.storageKeys.token);
            }

            this.adminAuth.session = null;
            this.adminAuth.refreshToken = '';
            this.adminAuth.devCode = '';
            this.adminAuth.code = '';
            this.adminAuth.email = preservedEmail;
            this.adminAuth.verifyEmail = preservedEmail;
            this.adminAuth.lastVerifiedAt = '';
            this.adminAuth.tokenSource = keepToken && this.config.token ? 'manual' : 'none';
            if (options.resetData !== false) {
                this.clearLiveData();
            }
            this.persistAdminAuthState();
        },

        async sendAdminCode() {
            const email = String(this.adminAuth.email || '').trim();
            if (!email) {
                this.markAdminAuthStatus('warn', '请先填写管理员邮箱。');
                return;
            }

            this.adminAuth.sending = true;
            this.markAdminAuthStatus('info', '正在发送管理验证码...');

            try {
                const payload = await this.publicApiRequest('/v1/admin-auth/send-code', {
                    method: 'POST',
                    body: { email }
                });
                this.adminAuth.email = email;
                this.adminAuth.verifyEmail = email;
                this.adminAuth.devCode = String(payload && payload.dev_code || '').trim();
                if (this.adminAuth.devCode) {
                    this.adminAuth.code = this.adminAuth.devCode;
                }
                this.persistAdminAuthState();
                this.markAdminAuthStatus('ok', payload && payload.message ? payload.message : '管理验证码已发送。');
                this.log('ok', `管理验证码已发送至 ${email}。`);
            } catch (error) {
                this.markAdminAuthStatus('warn', error.message || '发送管理验证码失败。');
                this.log('warn', `发送管理验证码失败: ${error.message || '未知错误'}`);
            } finally {
                this.adminAuth.sending = false;
            }
        },

        async verifyAdminCode() {
            const email = String(this.adminAuth.verifyEmail || this.adminAuth.email || '').trim();
            const code = String(this.adminAuth.code || '').trim();
            if (!email) {
                this.markAdminAuthStatus('warn', '请先填写验证邮箱。');
                return;
            }
            if (!/^\d{6}$/.test(code)) {
                this.markAdminAuthStatus('warn', '验证码应为 6 位数字。');
                return;
            }

            this.adminAuth.verifying = true;
            this.markAdminAuthStatus('info', '正在验证管理验证码...');

            try {
                const payload = await this.publicApiRequest('/v1/admin-auth/verify', {
                    method: 'POST',
                    body: {
                        email,
                        code,
                        locale: this.adminAuth.locale || null,
                        timezone: this.adminAuth.timezone || null
                    }
                });
                this.persistAdminSession(payload, {
                    tokenSource: 'admin-auth',
                    message: '策略权限会话已建立，正在同步数据。'
                });
                this.log('ok', `管理员 ${email} 已完成策略会话验证。`);
                await this.loadAll({ silent: true, skipSessionRestore: true });
                this.applyWorkspaceFirstScreenState({ force: true });
            } catch (error) {
                this.markAdminAuthStatus('warn', error.message || '验证管理验证码失败。');
                this.log('warn', `验证管理验证码失败: ${error.message || '未知错误'}`);
            } finally {
                this.adminAuth.verifying = false;
            }
        },

        async refreshAdminSession(options = {}) {
            const silent = Boolean(options.silent);
            const reload = options.reload !== false;
            const keepStatus = Boolean(options.keepStatus);
            if (!this.adminAuth.refreshToken) {
                if (!silent) {
                    this.markAdminAuthStatus('warn', '请先完成管理员验证码验证。');
                }
                return false;
            }
            if (this.adminAuth.refreshing) {
                return false;
            }

            this.adminAuth.refreshing = true;
            if (!silent) {
                this.markAdminAuthStatus('info', '正在刷新策略会话...');
            }

            try {
                const payload = await this.publicApiRequest('/v1/admin-auth/refresh', {
                    method: 'POST',
                    body: { refresh_token: this.adminAuth.refreshToken }
                });
                this.persistAdminSession(payload, {
                    tokenSource: 'admin-auth',
                    message: silent && keepStatus ? this.adminAuth.statusMessage : '策略权限会话已刷新。',
                    clearDevCode: false
                });
                if (!silent) {
                    this.log('ok', '策略权限会话已刷新。');
                }
                if (reload) {
                    await this.loadAll({ silent: true, skipSessionRestore: true, authRetried: true });
                }
                return true;
            } catch (error) {
                if (!silent) {
                    this.markAdminAuthStatus('warn', error.message || '刷新策略会话失败。');
                    this.log('warn', `刷新策略会话失败: ${error.message || '未知错误'}`);
                }
                return false;
            } finally {
                this.adminAuth.refreshing = false;
            }
        },

        async logoutAdminSession() {
            if (this.adminAuth.loggingOut) {
                return;
            }

            const hasSessionMaterial = Boolean(this.config.token || this.adminAuth.refreshToken);
            if (!hasSessionMaterial) {
                this.clearAdminSession({ preserveEmail: true, resetData: true });
                this.markAdminAuthStatus('info', '本地策略会话已清空。');
                return;
            }

            this.adminAuth.loggingOut = true;
            this.markAdminAuthStatus('info', '正在退出策略会话...');

            try {
                await this.publicApiRequestWithStatus('/v1/admin-auth/logout', {
                    method: 'POST',
                    body: { refresh_token: this.adminAuth.refreshToken || null },
                    includeAuth: true,
                    expectedStatuses: [200, 401]
                });
            } catch (error) {
                this.log('warn', `退出策略会话时返回异常: ${error.message || '未知错误'}`);
            } finally {
                this.clearAdminSession({ preserveEmail: true, resetData: true });
                this.markAdminAuthStatus('info', '已退出策略会话。');
                this.statusMessage = '请先完成管理员登录或填写 Bearer Token';
                this.statusType = 'warn';
                this.log('ok', '策略权限会话已退出并清空本地缓存。');
                this.adminAuth.loggingOut = false;
            }
        },

        errorRequiresSessionRecovery(error) {
            return Boolean(
                error
                && platformDeckUtils.isSessionRevokedError(error.payload, error.status)
            );
        },

        ...workspaceModule,

        async apiRequest(path, options = {}) {
            const normalizedPath = String(path || '').startsWith('/') ? String(path) : `/${String(path || '')}`;
            const url = `${this.config.baseUrl}${normalizedPath}`;
            const hasBody = options.body !== undefined && options.body !== null;
            const headers = new Headers(options.headers || {});
            if (!headers.has('Accept')) {
                headers.set('Accept', 'application/json');
            }
            if (hasBody && !headers.has('Content-Type')) {
                headers.set('Content-Type', 'application/json');
            }
            if (this.config.token && !headers.has('Authorization')) {
                headers.set('Authorization', `Bearer ${this.config.token}`);
            }

            const response = await fetch(url, {
                method: String(options.method || 'GET').toUpperCase(),
                headers,
                body: hasBody ? JSON.stringify(options.body) : undefined
            });

            const contentType = response.headers.get('content-type') || '';
            let payload = null;
            if (response.status !== 204) {
                payload = contentType.includes('application/json')
                    ? await response.json()
                    : await response.text();
            }

            if (!response.ok) {
                if (platformDeckUtils.isSessionRevokedError(payload, response.status)) {
                    this.markAdminAuthStatus('warn', '策略会话已失效，请刷新会话或重新验证验证码。');
                }
                const error = new Error(this.readErrorMessage(payload, response.status));
                error.status = response.status;
                error.payload = payload;
                throw error;
            }

            return payload;
        },

        async publicApiRequest(path, options = {}) {
            const normalizedPath = String(path || '').startsWith('/') ? String(path) : `/${String(path || '')}`;
            const baseUrl = this.normalizeBaseUrl(this.config.publicBaseUrl || this.defaultPublicBaseUrl());
            if (!baseUrl) {
                throw new Error('请先配置 Public API 地址');
            }
            const url = `${baseUrl}${normalizedPath}`;
            const hasBody = options.body !== undefined && options.body !== null;
            const headers = new Headers(options.headers || {});
            if (!headers.has('Accept')) {
                headers.set('Accept', 'application/json');
            }
            if (hasBody && !headers.has('Content-Type')) {
                headers.set('Content-Type', 'application/json');
            }
            if (options.includeAuth && this.config.token && !headers.has('Authorization')) {
                headers.set('Authorization', `Bearer ${this.config.token}`);
            }

            const response = await fetch(url, {
                method: String(options.method || 'GET').toUpperCase(),
                headers,
                body: hasBody ? JSON.stringify(options.body) : undefined
            });

            const contentType = response.headers.get('content-type') || '';
            let payload = null;
            if (response.status !== 204) {
                payload = contentType.includes('application/json')
                    ? await response.json()
                    : await response.text();
            }

            if (!response.ok) {
                if (platformDeckUtils.isSessionRevokedError(payload, response.status)) {
                    this.markAdminAuthStatus('warn', '策略会话已失效，请刷新会话或重新验证验证码。');
                }
                const error = new Error(this.readErrorMessage(payload, response.status));
                error.status = response.status;
                error.payload = payload;
                throw error;
            }

            return payload;
        },

        async publicApiRequestWithStatus(path, options = {}) {
            const normalizedPath = String(path || '').startsWith('/') ? String(path) : `/${String(path || '')}`;
            const baseUrl = this.normalizeBaseUrl(this.config.publicBaseUrl || this.defaultPublicBaseUrl());
            if (!baseUrl) {
                throw new Error('请先配置 Public API 地址');
            }
            const url = `${baseUrl}${normalizedPath}`;
            const hasBody = options.body !== undefined && options.body !== null;
            const headers = new Headers(options.headers || {});
            if (!headers.has('Accept')) {
                headers.set('Accept', 'application/json');
            }
            if (hasBody && !headers.has('Content-Type')) {
                headers.set('Content-Type', 'application/json');
            }
            if (options.includeAuth && this.config.token && !headers.has('Authorization')) {
                headers.set('Authorization', `Bearer ${this.config.token}`);
            }

            const response = await fetch(url, {
                method: String(options.method || 'GET').toUpperCase(),
                headers,
                body: hasBody ? JSON.stringify(options.body) : undefined
            });

            const contentType = response.headers.get('content-type') || '';
            let payload = null;
            if (response.status !== 204) {
                payload = contentType.includes('application/json')
                    ? await response.json()
                    : await response.text();
            }

            const expectedStatuses = Array.isArray(options.expectedStatuses)
                ? new Set(options.expectedStatuses)
                : new Set();
            if (!response.ok && !expectedStatuses.has(response.status)) {
                if (platformDeckUtils.isSessionRevokedError(payload, response.status)) {
                    this.markAdminAuthStatus('warn', '策略会话已失效，请刷新会话或重新验证验证码。');
                }
                const error = new Error(this.readErrorMessage(payload, response.status));
                error.status = response.status;
                error.payload = payload;
                throw error;
            }

            return {
                status: response.status,
                payload
            };
        },

        readErrorMessage: platformDeckUtils.readErrorMessage,

        async loadAll(options = {}) {
            const silent = Boolean(options.silent);
            const skipSessionRestore = Boolean(options.skipSessionRestore);
            if (!this.config.baseUrl) {
                this.statusMessage = '请先配置 Admin API 地址';
                this.statusType = 'warn';
                return;
            }
            if (!this.config.token) {
                if (!skipSessionRestore && this.adminAuth.refreshToken) {
                    const restored = await this.refreshAdminSession({ silent: true, reload: false, keepStatus: true });
                    if (restored && this.config.token) {
                        return this.loadAll({ ...options, skipSessionRestore: true });
                    }
                }
                this.statusMessage = this.adminAuth.refreshToken
                    ? '策略会话待恢复，请刷新会话或重新验证。'
                    : '请先完成管理员登录或填写 Bearer Token';
                this.statusType = 'warn';
                if (!silent) {
                    this.log('warn', this.adminAuth.refreshToken
                        ? '未恢复策略会话，跳过实时数据拉取。'
                        : '未检测到 Token，跳过实时数据拉取。');
                }
                return;
            }

            if (!silent) {
                this.loading = true;
            }
            this.statusMessage = '正在同步策略与回测数据...';
            this.statusType = 'info';

            try {
                const [summaryRes, signalsRes, scannerRes, rankingsRes, healthRes, runsRes, analysesRes] = await Promise.all([
                    this.apiRequest(`/v1/admin/signal-stats/summary?window_hours=${this.config.windowHours}`),
                    this.apiRequest('/v1/admin/signal-stats?limit=40'),
                    this.apiRequest('/v1/admin/scanner/observability?limit=8&decision_limit=30'),
                    this.apiRequest(`/v1/admin/backtests/rankings/latest?timeframe=${encodeURIComponent(this.config.timeframe)}&limit=8`),
                    this.apiRequest(`/v1/admin/analytics/strategy-health?window_hours=${this.config.windowHours}`),
                    this.apiRequest(`/v1/admin/backtests/runs?limit=12&timeframe=${encodeURIComponent(this.config.timeframe)}`),
                    this.apiRequest('/v1/admin/tradingagents/analyses?limit=16')
                ]);

                this.consumeSummary(summaryRes);
                this.consumeSignals(signalsRes);
                this.consumeScanner(scannerRes);
                this.consumeRankings(rankingsRes);
                this.consumeHealth(healthRes);
                this.consumeRuns(runsRes);
                this.consumeTradingAgentsAnalyses(analysesRes);
                this.applyWorkspaceFirstScreenState({ scroll: !silent });

                this.lastUpdatedLabel = this.formatDateTime(new Date().toISOString());
                this.statusMessage = '实时数据同步成功';
                this.statusType = 'ok';
                if (this.adminSessionReady()) {
                    this.markAdminAuthStatus('ok', '策略权限会话在线，桌面端已同步到最新数据。');
                }
                this.log('ok', `同步成功: 信号 ${this.watchlist.length} 条，判定 ${this.signalTape.length} 条，排名 ${this.rankings.length} 条。`);
            } catch (error) {
                if (!options.authRetried && !skipSessionRestore && this.errorRequiresSessionRecovery(error) && this.adminAuth.refreshToken) {
                    const restored = await this.refreshAdminSession({ silent: true, reload: false, keepStatus: true });
                    if (restored && this.config.token) {
                        this.log('info', '检测到策略会话失效，已自动刷新会话后重试同步。');
                        return this.loadAll({ ...options, authRetried: true, skipSessionRestore: true });
                    }
                }
                this.statusMessage = `同步失败: ${error.message || '未知错误'}`;
                this.statusType = 'warn';
                if (this.errorRequiresSessionRecovery(error)) {
                    this.markAdminAuthStatus('warn', '策略会话已失效，请刷新会话或重新验证验证码。');
                }
                this.log('warn', `同步失败: ${error.message || '未知错误'}`);
            } finally {
                this.loading = false;
                this.$nextTick(() => {
                    if (window.lucide) {
                        window.lucide.createIcons();
                    }
                });
            }
        },

        consumeSummary(payload) {
            this.summary = {
                ...this.summary,
                ...(payload || {})
            };
        },

        consumeSignals(payload) {
            const rows = Array.isArray(payload && payload.data) ? payload.data : [];
            this.watchlist = rows.map((item) => {
                const signalType = this.normalizeSignalType(item.signal_type);
                const strategyCode = this.resolveStrategyCode(item.indicators);
                return {
                    id: Number(item.id || 0),
                    symbol: String(item.symbol || '').toUpperCase(),
                    strategyCode,
                    strategy: this.strategyLabel(strategyCode),
                    signalType,
                    status: String(item.status || ''),
                    entryPrice: this.toNumber(item.entry_price),
                    stopLoss: this.toNumber(item.stop_loss),
                    takeProfit1: this.toNumber(item.take_profit_1),
                    takeProfit2: this.toNumber(item.take_profit_2),
                    takeProfit3: this.toNumber(item.take_profit_3),
                    riskReward: this.toNumber(item.risk_reward_ratio),
                    atrValue: this.toNumber(item.atr_value),
                    atrMultiplier: this.toNumber(item.atr_multiplier),
                    atrLabel: this.toNumber(item.atr_value) > 0 ? `ATR ${this.toFixed(item.atr_value, 2)}` : 'ATR --',
                    target1Pct: this.computeTarget1Pct(item),
                    confidence: this.toNumber(item.confidence),
                    probability: this.toNumber(item.probability),
                    generatedAt: item.generated_at,
                    indicators: item.indicators && typeof item.indicators === 'object' && !Array.isArray(item.indicators)
                        ? item.indicators
                        : {},
                    raw: item
                };
            });

            if (!this.watchlist.length) {
                this.selectedSymbol = '';
                this.executionContextSource = '';
                this.executionContextUpdatedAt = '';
            } else if (!this.selectedSymbol || !this.watchlist.some((item) => item.symbol === this.selectedSymbol)) {
                this.selectedSymbol = this.watchlist[0].symbol;
            }
            if (this.selectedSymbol && !this.executionContextUpdatedAt) {
                this.executionContextSource = this.executionContextSource || 'auto-sync';
                this.executionContextUpdatedAt = new Date().toISOString();
            }
            this.rebuildStrategyMix();
        },

        consumeScanner(payload) {
            const summary = payload && payload.summary ? payload.summary : {};
            this.scannerSummary = {
                ...this.scannerSummary,
                ...summary
            };
            const decisions = Array.isArray(payload && payload.recent_decisions)
                ? payload.recent_decisions
                : [];
            this.signalTape = decisions.map((item) => {
                const signalType = this.normalizeSignalType(item.signal_type);
                return {
                    id: Number(item.id || 0),
                    symbol: String(item.symbol || '').toUpperCase(),
                    action: this.signalTypeLabel(signalType),
                    decision: String(item.decision || ''),
                    decisionLabel: this.decisionLabel(item.decision, Boolean(item.suppressed)),
                    reason: String(item.reason || '无说明'),
                    scoreLabel: item.score !== null && item.score !== undefined
                        ? `${this.toFixed(item.score, 0)} 分`
                        : '--',
                    suppressed: Boolean(item.suppressed),
                    queue: Boolean(item.suppressed) ? '已抑制' : '已发射',
                    dedupeKey: item.dedupe_key ? String(item.dedupe_key) : '--',
                    time: this.formatTime(item.created_at),
                    createdAt: item.created_at
                };
            });
            this.updateFunnel();
        },

        consumeRankings(payload) {
            const rows = Array.isArray(payload && payload.data) ? payload.data : [];
            this.rankings = rows.map((item) => ({
                ...item,
                score: this.toNumber(item.score),
                degradation: this.toNumber(item.degradation),
                symbols_covered: Number(item.symbols_covered || 0),
                rank: Number(item.rank || 0)
            }));
        },

        consumeHealth(payload) {
            const rows = Array.isArray(payload && payload.strategies) ? payload.strategies : [];
            this.strategyHealth = rows.map((item) => ({
                ...item,
                score: this.toNumber(item.score),
                degradation: this.toNumber(item.degradation),
                symbols_covered: Number(item.symbols_covered || 0),
                signals_generated: Number(item.signals_generated || 0),
                stable: Boolean(item.stable)
            }));
        },

        consumeRuns(payload) {
            this.backtestRuns = Array.isArray(payload && payload.data) ? payload.data : [];
        },

        ...tradingAgentsModule,

        selectedSignal() {
            if (!this.selectedSymbol) {
                return null;
            }
            return this.watchlist.find((item) => item.symbol === this.selectedSymbol) || null;
        },

        filteredWatchlist() {
            if (this.watchFilter === 'alert') {
                return this.watchlist.filter((item) => this.isAlertSignal(item));
            }
            return this.watchlist;
        },

        filteredTape() {
            if (!this.selectedSymbol) {
                return this.signalTape;
            }
            const scoped = this.signalTape.filter((item) => item.symbol === this.selectedSymbol);
            return scoped.length ? scoped : this.signalTape;
        },

        isAlertSignal(item) {
            return ['active', 'triggered'].includes(String(item.status || '').toLowerCase());
        },

        resolveStrategyCode(indicators) {
            if (indicators && typeof indicators === 'object' && !Array.isArray(indicators) && indicators.strategy) {
                return String(indicators.strategy).toLowerCase();
            }
            return 'unknown';
        },

        rebuildStrategyMix() {
            const counter = {};
            this.watchlist.forEach((item) => {
                const key = this.strategyLabel(item.strategyCode);
                counter[key] = (counter[key] || 0) + 1;
            });
            const total = this.watchlist.length || 1;
            this.strategyMix = Object.entries(counter)
                .map(([name, count]) => ({
                    name,
                    count,
                    ratio: this.percent(count, total)
                }))
                .sort((a, b) => b.count - a.count)
                .slice(0, 6);
        },

        updateFunnel() {
            const totalDecisions = Number(this.scannerSummary.total_decisions || 0);
            const emitted = Number(this.scannerSummary.emitted_decisions || 0);
            const suppressed = Number(this.scannerSummary.suppressed_decisions || 0);
            const runningRuns = Number(this.scannerSummary.running_runs || 0);
            const totalRuns = Number(this.scannerSummary.total_runs || 0);
            const fissionInput = emitted + suppressed;
            const decisionBase = Math.max(1, totalDecisions);
            const runBase = Math.max(1, totalRuns);

            this.funnelStages = [
                {
                    name: '扫描判定总量',
                    value: this.formatInt(totalDecisions),
                    progress: this.percent(totalDecisions, decisionBase)
                },
                {
                    name: '进入通知裂变',
                    value: this.formatInt(fissionInput),
                    progress: this.percent(fissionInput, decisionBase)
                },
                {
                    name: '发出信号事件',
                    value: this.formatInt(emitted),
                    progress: this.percent(emitted, decisionBase)
                },
                {
                    name: '运行中任务',
                    value: this.formatInt(runningRuns),
                    progress: this.percent(runningRuns, runBase)
                }
            ];
        },

        async triggerBacktestRefresh() {
            if (this.isRunningBacktest) {
                return;
            }
            this.isRunningBacktest = true;
            this.statusMessage = '正在触发回测刷新...';
            this.statusType = 'info';
            try {
                const payload = this.buildRunPayload();
                const symbolText = Array.isArray(payload.symbols) && payload.symbols.length
                    ? `${payload.symbols.slice(0, 4).join(',')}${payload.symbols.length > 4 ? ',...' : ''}`
                    : 'ALL';
                const strategyText = Array.isArray(payload.strategy_names) && payload.strategy_names.length
                    ? `${payload.strategy_names.slice(0, 3).join(',')}${payload.strategy_names.length > 3 ? ',...' : ''}`
                    : 'ALL';
                const result = await this.apiRequest('/v1/admin/backtests/runs', {
                    method: 'POST',
                    body: payload
                });
                this.log('ok', `回测刷新已提交 run_id=${result.run_id} symbols=${symbolText} strategies=${strategyText} rankings=${result.ranking_count}`);
                await this.loadAll({ silent: true });
                this.statusMessage = '回测刷新完成';
                this.statusType = 'ok';
            } catch (error) {
                this.statusMessage = `回测刷新失败: ${error.message || '未知错误'}`;
                this.statusType = 'warn';
                this.log('warn', `回测触发失败: ${error.message || '未知错误'}`);
            } finally {
                this.isRunningBacktest = false;
            }
        },

        buildRunPayload() {
            const payload = {
                timeframe: String(this.config.timeframe || '1d').trim() || '1d'
            };
            const symbols = this.parseCsvStrings(this.runForm.symbols).map((item) => item.toUpperCase());
            const strategies = this.parseCsvStrings(this.runForm.strategyNames);
            const windows = this.parseCsvInts(this.runForm.windows);

            if (symbols.length) {
                payload.symbols = symbols;
            }
            if (strategies.length) {
                payload.strategy_names = strategies;
            }
            if (windows.length) {
                payload.windows = windows;
            }
            return payload;
        },

        parseCsvStrings: platformDeckUtils.parseCsvStrings,

        parseCsvInts: platformDeckUtils.parseCsvInts,

        topStrategy() {
            return this.rankings.length ? this.rankings[0] : null;
        },

        statusBadgeClass() {
            if (this.statusType === 'ok') {
                return 'border-mint/30 bg-mint/10 text-mint';
            }
            if (this.statusType === 'warn') {
                return 'border-sun/40 bg-sun/10 text-sun';
            }
            return 'border-tide/30 bg-tide/10 text-tide';
        },

        strategyAdvice: platformDeckUtils.strategyAdvice,

        ruleClass: platformDeckUtils.ruleClass,

        normalizeSignalType: platformDeckUtils.normalizeSignalType,

        signalTypeLabel: platformDeckUtils.signalTypeLabel,

        statusLabel: platformDeckUtils.statusLabel,

        strategyLabel: platformDeckUtils.strategyLabel,

        decisionLabel: platformDeckUtils.decisionLabel,

        decisionClass: platformDeckUtils.decisionClass,

        computeTarget1Pct: platformDeckUtils.computeTarget1Pct,

        updateClock() {
            this.nowLabel = new Date().toISOString().slice(11, 19) + ' UTC';
        },

        percent: platformDeckUtils.percent,

        toNumber: platformDeckUtils.toNumber,

        toFixed: platformDeckUtils.toFixedNumber,

        formatInt: platformDeckUtils.formatInt,

        formatPct: platformDeckUtils.formatPct,

        formatDateTime: platformDeckUtils.formatDateTime,

        formatTime: platformDeckUtils.formatTime,

        log(level, text) {
            const line = {
                id: `${Date.now()}-${Math.random()}`,
                time: `[${new Date().toISOString().slice(11, 19)}]`,
                level,
                text: ` ${text}`
            };
            this.consoleLines = [line, ...this.consoleLines].slice(0, 140);
        }
    };
}

window.platformDeck = platformDeck;

document.addEventListener('DOMContentLoaded', () => {
    if (window.lucide) {
        window.lucide.createIcons();
    }
});
