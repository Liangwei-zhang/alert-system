const platformDeckConstants = window.PlatformDeckConstants || {};
const platformDeckUtils = window.PlatformDeckUtils || {};
const platformDeckMarket = window.PlatformDeckMarket || {};
const platformDeckTradingAgents = window.PlatformDeckTradingAgents || {};
const platformDeckWorkspace = window.PlatformDeckWorkspace || {};

function platformDeck() {
    const tradingAgentsState = platformDeckTradingAgents.createState
        ? platformDeckTradingAgents.createState(platformDeckConstants)
        : {};
    const tradingAgentsModule = platformDeckTradingAgents.createModule
        ? platformDeckTradingAgents.createModule(platformDeckUtils)
        : {};
    const marketState = platformDeckMarket.createState
        ? platformDeckMarket.createState()
        : {};
    const marketModule = platformDeckMarket.createModule
        ? platformDeckMarket.createModule()
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
        ...marketState,
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
        backtestEquityCurve: null,
        backtestEquityCurveLoading: false,
        backtestEquityCurveError: '',
        backtestEquityCurveKey: '',
        activeCalibrationSnapshot: null,
        calibrationProposalData: null,
        calibrationProposalLoading: false,
        calibrationProposalError: '',
        calibrationApplyLoading: false,
        calibrationApplyError: '',
        calibrationApplySuccess: '',
        calibrationProposalForm: {
            signalWindowHours: 24,
            rankingWindowHours: 24 * 7,
            version: '',
            activate: true,
            notes: ''
        },
        exitQualityMetrics: {
            window_hours: 0,
            generated_after: '',
            total_signals: 0,
            exits_available: 0,
            calibrated_exit_count: 0,
            client_exit_count: 0,
            avg_risk_reward_ratio: 0,
            avg_atr_multiplier: 0,
            avg_stop_distance_pct: 0,
            avg_tp1_distance_pct: 0,
            exit_sources: [],
            atr_multiplier_sources: [],
            market_regimes: [],
            top_symbols: []
        },
        strategyBreakdownData: null,
        strategyBreakdownSignalId: 0,
        strategyBreakdownLoading: false,
        strategyBreakdownError: '',
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
                this.loadSelectedMarketChart({ silent: true, throwOnError: false });
            });
            this.refreshHandle = setInterval(() => this.loadAll({ silent: true }), 45000);
            this.marketRefreshHandle = setInterval(() => {
                this.loadSelectedMarketChart({ silent: true, throwOnError: false });
            }, 60000);
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
            this.restoreDeskWatchlistEntries(routeSymbol);
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
            this.backtestEquityCurve = null;
            this.backtestEquityCurveLoading = false;
            this.backtestEquityCurveError = '';
            this.backtestEquityCurveKey = '';
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
    ...marketModule,

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

                const [calibrationRes, exitQualityRes, proposalRes] = await Promise.allSettled([
                    this.apiRequest('/v1/admin/calibrations/active'),
                    this.apiRequest(`/v1/admin/analytics/exit-quality?window_hours=${this.config.windowHours}`),
                    this.loadCalibrationProposal({ silent: true })
                ]);

                if (calibrationRes.status === 'fulfilled') {
                    this.consumeActiveCalibration(calibrationRes.value);
                } else {
                    this.activeCalibrationSnapshot = null;
                    this.log('warn', `活跃校准快照同步失败: ${calibrationRes.reason && calibrationRes.reason.message ? calibrationRes.reason.message : '未知错误'}`);
                }

                if (exitQualityRes.status === 'fulfilled') {
                    this.consumeExitQuality(exitQualityRes.value);
                } else {
                    this.exitQualityMetrics = this.emptyExitQualityMetrics();
                    this.log('warn', `退出位读模型同步失败: ${exitQualityRes.reason && exitQualityRes.reason.message ? exitQualityRes.reason.message : '未知错误'}`);
                }

                if (proposalRes.status !== 'fulfilled') {
                    this.log('warn', `校准建议同步失败: ${proposalRes.reason && proposalRes.reason.message ? proposalRes.reason.message : '未知错误'}`);
                }

                await this.loadSelectedMarketChart({ silent: true, throwOnError: false });
                await this.loadSelectedStrategyBreakdown({ silent: true, throwOnError: false });
                await this.loadSelectedBacktestEquity({ silent: true, throwOnError: false });
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

        parseSignalMetadata(item) {
            const payload = item && item.indicators && typeof item.indicators === 'object' && !Array.isArray(item.indicators)
                ? item.indicators
                : {};
            const strategySelection = item && item.strategy_selection && typeof item.strategy_selection === 'object' && !Array.isArray(item.strategy_selection)
                ? item.strategy_selection
                : (payload.strategy_selection
                && typeof payload.strategy_selection === 'object'
                && !Array.isArray(payload.strategy_selection)
                ? payload.strategy_selection
                : {});
            const exitLevels = item && item.exit_levels && typeof item.exit_levels === 'object' && !Array.isArray(item.exit_levels)
                ? item.exit_levels
                : (payload.exit_levels
                && typeof payload.exit_levels === 'object'
                && !Array.isArray(payload.exit_levels)
                ? payload.exit_levels
                : {});
            const scoreBreakdown = item && item.score_breakdown && typeof item.score_breakdown === 'object' && !Array.isArray(item.score_breakdown)
                ? item.score_breakdown
                : (payload.score_breakdown
                && typeof payload.score_breakdown === 'object'
                && !Array.isArray(payload.score_breakdown)
                ? payload.score_breakdown
                : {});
            const calibrationSnapshot = payload.calibration_snapshot
                && typeof payload.calibration_snapshot === 'object'
                && !Array.isArray(payload.calibration_snapshot)
                ? payload.calibration_snapshot
                : {};
            const strategyCandidates = Array.isArray(payload.strategy_candidates)
                ? payload.strategy_candidates.filter((candidate) => candidate && typeof candidate === 'object' && !Array.isArray(candidate))
                : [];
            const strategyWindow = String(item && item.strategy_window || payload.strategy_window || '').trim();
            const marketRegime = String(item && item.market_regime || payload.market_regime || '').trim();
            const marketRegimeDetail = String(
                item && item.market_regime_detail
                || payload.market_regime_detail
                || strategySelection.market_regime_detail
                || marketRegime
                || ''
            ).trim();
            const calibrationVersion = String(
                item && item.calibration_version
                || payload.calibration_version
                || strategySelection.calibration_version
                || calibrationSnapshot.version
                || scoreBreakdown.calibration_version
                || ''
            ).trim();
            const regimeMetrics = strategySelection.regime_metrics
                && typeof strategySelection.regime_metrics === 'object'
                && !Array.isArray(strategySelection.regime_metrics)
                ? strategySelection.regime_metrics
                : (payload.regime_metrics
                && typeof payload.regime_metrics === 'object'
                && !Array.isArray(payload.regime_metrics)
                ? payload.regime_metrics
                : {});
            const regimeReasons = Array.isArray(strategySelection.regime_reasons)
                ? strategySelection.regime_reasons
                : (Array.isArray(payload.regime_reasons) ? payload.regime_reasons : []);
            return {
                payload,
                strategySelection,
                strategyCandidates,
                exitLevels,
                scoreBreakdown,
                strategyWindow,
                marketRegime,
                marketRegimeDetail,
                regimeMetrics,
                regimeReasons,
                calibrationSnapshot,
                calibrationVersion
            };
        },

        strategySelectionSourceLabel(source) {
            const normalized = String(source || '').trim().toLowerCase();
            const mapping = {
                ranking: '排名归一化',
                heuristic: '规则推断',
                fallback: '兼容回退',
                manual: '手动覆盖'
            };
            return mapping[normalized] || '服务端选择';
        },

        exitLevelSourceLabel(source) {
            const normalized = String(source || '').trim().toLowerCase();
            const mapping = {
                client: '客户端传入',
                server_default: '服务端 ATR 默认',
                server_adjusted: '服务端动态调整',
                unavailable: '退出位待补'
            };
            return mapping[normalized] || '退出位待补';
        },

        atrMultiplierSourceLabel(source) {
            const normalized = String(source || '').trim().toLowerCase();
            const mapping = {
                calibration_snapshot: '校准快照',
                client: '客户端',
                default: '默认回退'
            };
            return mapping[normalized] || (normalized ? normalized.replaceAll('_', ' ') : '--');
        },

        calibrationSourceLabel(source) {
            const normalized = String(source || '').trim().toLowerCase();
            const mapping = {
                backtest_feedback_loop: '反馈闭环',
                proposal_review: '提案应用',
                manual_review: '手动校准',
                historical_import: '历史导入'
            };
            return mapping[normalized] || (normalized ? normalized.replaceAll('_', ' ') : '--');
        },

        marketRegimeDetailLabel(value) {
            const normalized = String(value || '').trim().toLowerCase();
            const mapping = {
                trend: '趋势',
                trend_up: '趋势上行',
                trend_down: '趋势下行',
                trend_strong_up: '强趋势上行',
                trend_strong_down: '强趋势下行',
                range: '区间震荡',
                range_tight: '窄幅区间',
                range_balanced: '平衡区间',
                range_wide: '宽幅区间',
                volatile: '高波动',
                volatile_breakout: '高波动突破',
                volatile_reversal: '高波动反转',
                breakout_candidate: '突破候选',
                default: '默认'
            };
            return mapping[normalized] || (normalized ? normalized.replaceAll('_', ' ') : '--');
        },

        signalRegimeLabel(signal) {
            if (!signal) {
                return '--';
            }
            return this.marketRegimeDetailLabel(signal.marketRegimeDetail || signal.marketRegime);
        },

        signalStrategyNarrative(signal) {
            if (!signal) {
                return '等待信号元数据';
            }
            const selectionSource = this.strategySelectionSourceLabel(signal.selectionSource);
            const rankText = signal.selectionRank > 0 ? `排行 #${this.formatInt(signal.selectionRank)}` : '无排行输入';
            const fitText = signal.signalFitScore > 0
                ? `适配 ${this.toFixed(signal.signalFitScore, 1)}`
                : '适配待补';
            const weightText = signal.strategyWeight > 0
                ? `权重 ${this.toFixed(signal.strategyWeight, 2)}`
                : '权重默认';
            return `${selectionSource} · ${rankText} · ${fitText} · ${weightText}`;
        },

        exitLevelNarrative(signal) {
            if (!signal) {
                return '等待退出位数据';
            }
            const sourceLabel = this.exitLevelSourceLabel(signal.exitLevelSource);
            const atrText = signal.exitAtrValue > 0
                ? `ATR ${this.toFixed(signal.exitAtrValue, 2)} x ${this.toFixed(signal.exitAtrMultiplier, 2)}`
                : 'ATR 待补';
            const atrSourceText = signal.exitAtrMultiplierSource
                ? `${this.atrMultiplierSourceLabel(signal.exitAtrMultiplierSource)}${signal.exitAtrMultiplierKey ? ' · ' + signal.exitAtrMultiplierKey : ''}`
                : 'ATR 来源待补';
            return `${sourceLabel} · ${atrText} · ${atrSourceText}`;
        },

        exitFormulaSummary(signal) {
            if (!signal) {
                return '等待退出公式';
            }
            const normalizedSignalType = String(signal.signalType || '').trim().toLowerCase();
            if (!normalizedSignalType) {
                return '等待退出公式';
            }
            const isLong = normalizedSignalType.startsWith('buy');
            const stopOperator = isLong ? '-' : '+';
            const targetOperator = isLong ? '+' : '-';
            const atrMultiplier = signal.exitAtrMultiplier > 0
                ? signal.exitAtrMultiplier
                : signal.atrMultiplier;
            const tp3Multiplier = Math.max(
                4.0,
                this.toNumber(signal.riskReward) * Math.max(atrMultiplier, 0)
            ) || 4.0;
            return `SL = P ${stopOperator} ATR x ${this.toFixed(atrMultiplier || 0, 2)} · TP1 = P ${targetOperator} ATR x 1.50 · TP2 = P ${targetOperator} ATR x 2.50 · TP3 = P ${targetOperator} ATR x ${this.toFixed(tp3Multiplier, 2)}`;
        },

        selectedScoreBreakdownCards(signal) {
            if (!signal || !signal.scoreBreakdown || !Object.keys(signal.scoreBreakdown).length) {
                return [];
            }
            const scoreBreakdown = signal.scoreBreakdown;
            const bonusTotal = this.toNumber(scoreBreakdown.volume_bonus)
                + this.toNumber(scoreBreakdown.trend_bonus)
                + this.toNumber(scoreBreakdown.reversal_bonus)
                + this.toNumber(scoreBreakdown.quality_bonus);
            const penaltyTotal = this.toNumber(scoreBreakdown.stale_penalty)
                + this.toNumber(scoreBreakdown.liquidity_penalty);
            return [
                {
                    id: 'base',
                    label: '基础分',
                    value: `${this.toFixed(scoreBreakdown.base_score, 1)} + ${this.toFixed(scoreBreakdown.signal_bias, 1)}`,
                    meta: '基础分 + 方向偏置'
                },
                {
                    id: 'probability',
                    label: '置信 / 概率',
                    value: `${this.toFixed(scoreBreakdown.confidence_points, 1)} / ${this.toFixed(scoreBreakdown.probability_points, 1)}`,
                    meta: 'confidence 与 probability 贡献'
                },
                {
                    id: 'risk-reward',
                    label: 'RR / 奖励项',
                    value: `${this.toFixed(scoreBreakdown.risk_reward_points, 1)} / ${this.toFixed(bonusTotal, 1)}`,
                    meta: 'RR 与量能/趋势/质量奖励'
                },
                {
                    id: 'penalty',
                    label: '惩罚项 / 总分',
                    value: `${this.toFixed(penaltyTotal, 1)} / ${this.toFixed(scoreBreakdown.selected_score || scoreBreakdown.clamped_total, 0)}`,
                    meta: 'stale、流动性惩罚与最终分数'
                }
            ];
        },

        emptyExitQualityMetrics() {
            return {
                window_hours: this.parseWindowHours(this.config.windowHours || 168),
                generated_after: '',
                total_signals: 0,
                exits_available: 0,
                calibrated_exit_count: 0,
                client_exit_count: 0,
                avg_risk_reward_ratio: 0,
                avg_atr_multiplier: 0,
                avg_stop_distance_pct: 0,
                avg_tp1_distance_pct: 0,
                exit_sources: [],
                atr_multiplier_sources: [],
                market_regimes: [],
                top_symbols: []
            };
        },

        emptyCalibrationProposal() {
            return {
                generated_at: '',
                signal_window_hours: 24,
                ranking_window_hours: 24 * 7,
                current_version: '--',
                proposed_version: '--',
                strategy_health_refreshed_at: '',
                signal_generated_after: '',
                summary: {
                    total_signals: 0,
                    total_trade_actions: 0,
                    trade_action_rate: 0,
                    executed_trade_rate: 0,
                    overlapping_symbols: 0,
                    active_calibration_version: '--'
                },
                strategy_weights: [],
                score_multipliers: [],
                atr_multipliers: [],
                notes: [],
                snapshot_payload: {
                    version: '--',
                    source: 'proposal',
                    effective_from: '',
                    strategy_weights: {},
                    score_multipliers: {},
                    atr_multipliers: {},
                    derived_from: '',
                    sample_size: 0,
                    notes: ''
                }
            };
        },

        normalizeCountBuckets(items) {
            if (!Array.isArray(items)) {
                return [];
            }
            return items
                .filter((item) => item && typeof item === 'object' && !Array.isArray(item))
                .map((item) => ({
                    key: String(item.key || item.symbol || '').trim(),
                    count: Number(item.count || 0)
                }))
                .filter((item) => item.key);
        },

        normalizeProposalAdjustments(items) {
            if (!Array.isArray(items)) {
                return [];
            }
            return items
                .filter((item) => item && typeof item === 'object' && !Array.isArray(item))
                .map((item) => ({
                    key: String(item.key || '').trim(),
                    current_value: this.toNumber(item.current_value),
                    proposed_value: this.toNumber(item.proposed_value),
                    delta: this.toNumber(item.delta),
                    reasons: Array.isArray(item.reasons)
                        ? item.reasons.map((reason) => String(reason || '').trim()).filter(Boolean)
                        : []
                }))
                .filter((item) => item.key);
        },

        normalizeCalibrationSnapshot(snapshot) {
            if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) {
                return null;
            }
            const normalized = {
                version: String(snapshot.version || snapshot.calibration_version || '').trim() || '--',
                source: String(snapshot.source || '').trim() || '--',
                effective_from: String(snapshot.effective_from || snapshot.effective_at || '').trim(),
                effective_at: String(snapshot.effective_at || snapshot.effective_from || '').trim(),
                strategy_weights: snapshot.strategy_weights
                    && typeof snapshot.strategy_weights === 'object'
                    && !Array.isArray(snapshot.strategy_weights)
                    ? { ...snapshot.strategy_weights }
                    : {},
                score_multipliers: snapshot.score_multipliers
                    && typeof snapshot.score_multipliers === 'object'
                    && !Array.isArray(snapshot.score_multipliers)
                    ? { ...snapshot.score_multipliers }
                    : {},
                atr_multipliers: snapshot.atr_multipliers
                    && typeof snapshot.atr_multipliers === 'object'
                    && !Array.isArray(snapshot.atr_multipliers)
                    ? { ...snapshot.atr_multipliers }
                    : {}
            };
            if (
                normalized.version === '--'
                && normalized.source === '--'
                && !normalized.effective_from
                && !Object.keys(normalized.atr_multipliers).length
            ) {
                return null;
            }
            return normalized;
        },

        normalizeCalibrationProposal(payload) {
            if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
                return null;
            }
            const fallback = this.emptyCalibrationProposal();
            const summary = payload.summary && typeof payload.summary === 'object' && !Array.isArray(payload.summary)
                ? payload.summary
                : {};
            const snapshotPayload = payload.snapshot_payload && typeof payload.snapshot_payload === 'object' && !Array.isArray(payload.snapshot_payload)
                ? payload.snapshot_payload
                : {};
            return {
                ...fallback,
                generated_at: String(payload.generated_at || '').trim(),
                signal_window_hours: this.parseWindowHours(payload.signal_window_hours || fallback.signal_window_hours),
                ranking_window_hours: this.parseWindowHours(payload.ranking_window_hours || fallback.ranking_window_hours),
                current_version: String(payload.current_version || fallback.current_version).trim() || '--',
                proposed_version: String(payload.proposed_version || snapshotPayload.version || fallback.proposed_version).trim() || '--',
                strategy_health_refreshed_at: String(payload.strategy_health_refreshed_at || '').trim(),
                signal_generated_after: String(payload.signal_generated_after || '').trim(),
                summary: {
                    total_signals: Number(summary.total_signals || 0),
                    total_trade_actions: Number(summary.total_trade_actions || 0),
                    trade_action_rate: this.toNumber(summary.trade_action_rate),
                    executed_trade_rate: this.toNumber(summary.executed_trade_rate),
                    overlapping_symbols: Number(summary.overlapping_symbols || 0),
                    active_calibration_version: String(summary.active_calibration_version || '--').trim() || '--'
                },
                strategy_weights: this.normalizeProposalAdjustments(payload.strategy_weights),
                score_multipliers: this.normalizeProposalAdjustments(payload.score_multipliers),
                atr_multipliers: this.normalizeProposalAdjustments(payload.atr_multipliers),
                notes: Array.isArray(payload.notes)
                    ? payload.notes.map((item) => String(item || '').trim()).filter(Boolean)
                    : [],
                snapshot_payload: {
                    version: String(snapshotPayload.version || fallback.snapshot_payload.version).trim() || '--',
                    source: String(snapshotPayload.source || fallback.snapshot_payload.source).trim() || 'proposal',
                    effective_from: String(snapshotPayload.effective_from || '').trim(),
                    strategy_weights: snapshotPayload.strategy_weights
                        && typeof snapshotPayload.strategy_weights === 'object'
                        && !Array.isArray(snapshotPayload.strategy_weights)
                        ? { ...snapshotPayload.strategy_weights }
                        : {},
                    score_multipliers: snapshotPayload.score_multipliers
                        && typeof snapshotPayload.score_multipliers === 'object'
                        && !Array.isArray(snapshotPayload.score_multipliers)
                        ? { ...snapshotPayload.score_multipliers }
                        : {},
                    atr_multipliers: snapshotPayload.atr_multipliers
                        && typeof snapshotPayload.atr_multipliers === 'object'
                        && !Array.isArray(snapshotPayload.atr_multipliers)
                        ? { ...snapshotPayload.atr_multipliers }
                        : {},
                    derived_from: String(snapshotPayload.derived_from || '').trim(),
                    sample_size: Number(snapshotPayload.sample_size || 0),
                    notes: String(snapshotPayload.notes || '').trim()
                }
            };
        },

        consumeSignals(payload) {
            const rows = Array.isArray(payload && payload.data) ? payload.data : [];
            this.signalWatchlist = rows.map((item) => {
                const signalType = this.normalizeSignalType(item.signal_type);
                const metadata = this.parseSignalMetadata(item);
                const strategyCode = this.resolveStrategyCode(
                    metadata.payload,
                    metadata.strategySelection,
                );
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
                    indicators: metadata.payload,
                    strategySelection: metadata.strategySelection,
                    selectionSource: String(metadata.strategySelection.source || 'heuristic').trim() || 'heuristic',
                    sourceStrategy: String(
                        metadata.strategySelection.source_strategy
                        || metadata.strategySelection.strategy
                        || strategyCode
                        || 'unknown'
                    ).trim(),
                    selectionRank: Number(metadata.strategySelection.rank || 0),
                    rankingScore: this.toNumber(metadata.strategySelection.ranking_score),
                    combinedScore: this.toNumber(metadata.strategySelection.combined_score),
                    signalFitScore: this.toNumber(metadata.strategySelection.signal_fit_score),
                    regimeBias: this.toNumber(metadata.strategySelection.regime_bias),
                    degradationPenalty: this.toNumber(metadata.strategySelection.degradation_penalty),
                    strategyWeight: this.toNumber(metadata.strategySelection.strategy_weight),
                    selectionStable: Boolean(metadata.strategySelection.stable),
                    marketRegime: metadata.marketRegime || 'range',
                    marketRegimeDetail: metadata.marketRegimeDetail || 'range',
                    regimeDurationBars: Number(
                        metadata.strategySelection.regime_duration_bars
                        || metadata.payload.regime_duration_bars
                        || 0
                    ),
                    regimeMetrics: metadata.regimeMetrics,
                    regimeReasons: metadata.regimeReasons,
                    calibrationVersion: metadata.calibrationVersion || '--',
                    calibrationSnapshot: metadata.calibrationSnapshot,
                    calibrationSource: String(metadata.calibrationSnapshot.source || '').trim(),
                    calibrationEffectiveFrom: String(
                        metadata.calibrationSnapshot.effective_from
                        || metadata.calibrationSnapshot.effective_at
                        || ''
                    ).trim(),
                    exitLevels: metadata.exitLevels,
                    exitLevelSource: String(
                        metadata.exitLevels.source
                        || ((item.stop_loss || item.take_profit_1) ? 'client' : 'unavailable')
                    ).trim() || 'unavailable',
                    exitAtrValue: this.toNumber(
                        metadata.exitLevels.atr_value
                        || metadata.payload.atr_value
                        || item.atr_value
                    ),
                    exitAtrMultiplier: this.toNumber(
                        metadata.exitLevels.atr_multiplier
                        || metadata.payload.atr_multiplier
                        || item.atr_multiplier
                    ),
                    exitAtrMultiplierKey: String(metadata.exitLevels.atr_multiplier_key || '').trim(),
                    exitAtrMultiplierSource: String(metadata.exitLevels.atr_multiplier_source || '').trim(),
                    clientExitLevels: metadata.exitLevels.client_levels
                        && typeof metadata.exitLevels.client_levels === 'object'
                        && !Array.isArray(metadata.exitLevels.client_levels)
                        ? metadata.exitLevels.client_levels
                        : {},
                    serverExitLevels: metadata.exitLevels.server_levels
                        && typeof metadata.exitLevels.server_levels === 'object'
                        && !Array.isArray(metadata.exitLevels.server_levels)
                        ? metadata.exitLevels.server_levels
                        : {},
                    strategyCandidates: metadata.strategyCandidates,
                    scoreBreakdown: metadata.scoreBreakdown,
                    raw: item
                };
            });
            this.rebuildMarketWatchlist();

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

        consumeActiveCalibration(payload) {
            this.activeCalibrationSnapshot = this.normalizeCalibrationSnapshot(payload && payload.data ? payload.data : null);
        },

        consumeCalibrationProposal(payload) {
            this.calibrationProposalData = this.normalizeCalibrationProposal(payload);
        },

        consumeExitQuality(payload) {
            const fallback = this.emptyExitQualityMetrics();
            this.exitQualityMetrics = {
                ...fallback,
                window_hours: this.parseWindowHours(payload && payload.window_hours ? payload.window_hours : fallback.window_hours),
                generated_after: String(payload && payload.generated_after || '').trim(),
                total_signals: Number(payload && payload.total_signals || 0),
                exits_available: Number(payload && payload.exits_available || 0),
                calibrated_exit_count: Number(payload && payload.calibrated_exit_count || 0),
                client_exit_count: Number(payload && payload.client_exit_count || 0),
                avg_risk_reward_ratio: this.toNumber(payload && payload.avg_risk_reward_ratio),
                avg_atr_multiplier: this.toNumber(payload && payload.avg_atr_multiplier),
                avg_stop_distance_pct: this.toNumber(payload && payload.avg_stop_distance_pct),
                avg_tp1_distance_pct: this.toNumber(payload && payload.avg_tp1_distance_pct),
                exit_sources: this.normalizeCountBuckets(payload && payload.exit_sources),
                atr_multiplier_sources: this.normalizeCountBuckets(payload && payload.atr_multiplier_sources),
                market_regimes: this.normalizeCountBuckets(payload && payload.market_regimes),
                top_symbols: this.normalizeCountBuckets(payload && payload.top_symbols)
            };
        },

        proposalSignalWindowHours() {
            return Math.max(1, this.parseWindowHours(this.calibrationProposalForm.signalWindowHours || 24));
        },

        proposalRankingWindowHours() {
            return Math.max(1, this.parseWindowHours(this.calibrationProposalForm.rankingWindowHours || (24 * 7)));
        },

        selectedCalibrationProposal() {
            return this.calibrationProposalData;
        },

        proposalPreviewVersion() {
            const override = String(this.calibrationProposalForm.version || '').trim();
            if (override) {
                return override;
            }
            const proposal = this.selectedCalibrationProposal();
            return proposal ? proposal.proposed_version : '--';
        },

        proposalNotes() {
            const proposal = this.selectedCalibrationProposal();
            if (!proposal) {
                return [];
            }
            const combined = [
                ...(Array.isArray(proposal.notes) ? proposal.notes : []),
                String(proposal.snapshot_payload && proposal.snapshot_payload.notes || '').trim()
            ].filter(Boolean);
            return Array.from(new Set(combined));
        },

        async loadCalibrationProposal(options = {}) {
            const silent = Boolean(options.silent);
            const throwOnError = Boolean(options.throwOnError);
            const signalWindowHours = Math.max(1, this.parseWindowHours(
                options.signalWindowHours || this.calibrationProposalForm.signalWindowHours || 24
            ));
            const rankingWindowHours = Math.max(1, this.parseWindowHours(
                options.rankingWindowHours || this.calibrationProposalForm.rankingWindowHours || (24 * 7)
            ));
            this.calibrationProposalForm.signalWindowHours = signalWindowHours;
            this.calibrationProposalForm.rankingWindowHours = rankingWindowHours;
            this.calibrationProposalLoading = true;
            this.calibrationProposalError = '';

            try {
                const params = new URLSearchParams({
                    signal_window_hours: String(signalWindowHours),
                    ranking_window_hours: String(rankingWindowHours)
                });
                const payload = await this.apiRequest(`/v1/admin/calibrations/proposal?${params.toString()}`);
                this.consumeCalibrationProposal(payload);
                this.calibrationProposalError = '';
                return payload;
            } catch (error) {
                this.calibrationProposalError = `校准建议加载失败: ${error.message || '未知错误'}`;
                if (!silent) {
                    this.log('warn', `校准建议同步失败: ${error.message || '未知错误'}`);
                }
                if (throwOnError) {
                    throw error;
                }
                return null;
            } finally {
                this.calibrationProposalLoading = false;
            }
        },

        async applyCalibrationProposal() {
            if (this.calibrationApplyLoading) {
                return;
            }
            if (!this.selectedCalibrationProposal() && !this.calibrationProposalLoading) {
                await this.loadCalibrationProposal({ silent: true });
            }
            if (!this.selectedCalibrationProposal()) {
                this.calibrationApplyError = '当前没有可应用的校准建议。';
                return;
            }

            this.calibrationApplyLoading = true;
            this.calibrationApplyError = '';
            this.calibrationApplySuccess = '';

            const payload = {
                signal_window_hours: this.proposalSignalWindowHours(),
                ranking_window_hours: this.proposalRankingWindowHours(),
                activate: Boolean(this.calibrationProposalForm.activate)
            };
            const versionOverride = String(this.calibrationProposalForm.version || '').trim();
            const notes = String(this.calibrationProposalForm.notes || '').trim();
            if (versionOverride) {
                payload.version = versionOverride;
            }
            if (notes) {
                payload.notes = notes;
            }

            try {
                const result = await this.apiRequest('/v1/admin/calibrations/proposal/apply', {
                    method: 'POST',
                    body: payload
                });
                this.consumeActiveCalibration({ data: result });
                const appliedVersion = String(result && result.version || this.proposalPreviewVersion()).trim() || '--';
                this.calibrationApplySuccess = `已创建并${payload.activate ? '激活' : '保存'}校准快照 ${appliedVersion}`;
                this.calibrationProposalForm.version = '';
                this.calibrationProposalForm.notes = '';
                this.statusMessage = '校准建议已应用';
                this.statusType = 'ok';
                this.log('ok', `校准建议已应用 version=${appliedVersion} activate=${payload.activate ? 'yes' : 'no'}`);
                await this.loadAll({ silent: true });
            } catch (error) {
                this.calibrationApplyError = `应用校准建议失败: ${error.message || '未知错误'}`;
                this.statusMessage = this.calibrationApplyError;
                this.statusType = 'warn';
                this.log('warn', this.calibrationApplyError);
            } finally {
                this.calibrationApplyLoading = false;
            }
        },

        emptyBacktestEquityCurve() {
            return {
                symbol: '',
                strategy_name: '',
                timeframe: String(this.config.timeframe || '1d').trim() || '1d',
                window_days: 0,
                metrics: {
                    total_return_percent: 0,
                    max_drawdown_percent: 0,
                    trade_count: 0,
                    win_rate: 0,
                    avg_trade_return_percent: 0,
                    sharpe_ratio: 0,
                    samples: 0,
                },
                trades: [],
                equity_points: [],
                equity_series: [],
            };
        },

        normalizeBacktestEquityCurve(payload) {
            const fallback = this.emptyBacktestEquityCurve();
            const metrics = payload && payload.metrics && typeof payload.metrics === 'object'
                ? payload.metrics
                : {};
            const trades = Array.isArray(payload && payload.trades) ? payload.trades : [];
            const series = Array.isArray(payload && payload.equity_series) ? payload.equity_series : [];
            const points = Array.isArray(payload && payload.equity_points) ? payload.equity_points : [];

            return {
                ...fallback,
                symbol: String(payload && payload.symbol || '').trim().toUpperCase(),
                strategy_name: String(payload && payload.strategy_name || '').trim().toLowerCase(),
                timeframe: String(payload && payload.timeframe || fallback.timeframe).trim() || fallback.timeframe,
                window_days: Number(payload && payload.window_days || 0),
                metrics: {
                    total_return_percent: this.toNumber(metrics.total_return_percent),
                    max_drawdown_percent: this.toNumber(metrics.max_drawdown_percent),
                    trade_count: Number(metrics.trade_count || 0),
                    win_rate: this.toNumber(metrics.win_rate),
                    avg_trade_return_percent: this.toNumber(metrics.avg_trade_return_percent),
                    sharpe_ratio: this.toNumber(metrics.sharpe_ratio),
                    samples: Number(metrics.samples || 0),
                },
                trades: trades.map((item) => ({
                    entry_index: Number(item && item.entry_index || 0),
                    exit_index: Number(item && item.exit_index || 0),
                    entry_price: this.toNumber(item && item.entry_price),
                    exit_price: this.toNumber(item && item.exit_price),
                    return_percent: this.toNumber(item && item.return_percent),
                })),
                equity_points: points.map((item) => this.toNumber(item)),
                equity_series: series
                    .map((item, index) => ({
                        id: `equity-${index}-${String(item && item.timestamp || '').trim() || 'na'}`,
                        timestamp: String(item && item.timestamp || '').trim(),
                        equity: this.toNumber(item && item.equity),
                        drawdown_percent: this.toNumber(item && item.drawdown_percent),
                    }))
                    .filter((item) => item.timestamp && item.equity > 0),
            };
        },

        consumeBacktestEquityCurve(payload) {
            this.backtestEquityCurve = this.normalizeBacktestEquityCurve(payload);
        },

        selectedBacktestEquityCurve() {
            const selected = this.selectedSignal();
            if (!selected || !this.backtestEquityCurve) {
                return null;
            }
            if (String(this.backtestEquityCurve.symbol || '').trim().toUpperCase() !== String(selected.symbol || '').trim().toUpperCase()) {
                return null;
            }
            return this.backtestEquityCurve;
        },

        selectedBacktestEquityRequest() {
            const selected = this.selectedSignal();
            if (!selected) {
                return null;
            }

            const summary = typeof this.selectedResearchSummary === 'function'
                ? this.selectedResearchSummary()
                : null;
            const rankingMatch = summary && summary.rankingMatch ? summary.rankingMatch : null;
            const strategyCandidate = this.selectedStrategyCandidate(selected);
            const latestRun = typeof this.selectedBacktestRuns === 'function'
                ? (this.selectedBacktestRuns(1, selected.symbol)[0] || null)
                : null;

            const aliasMap = {
                trend_continuation: 'trend_following',
                'trend-continuation': 'trend_following',
                volatility_breakout: 'breakout',
                'volatility-breakout': 'breakout',
            };
            const strategyCandidates = [
                String(rankingMatch && rankingMatch.strategy_name || '').trim(),
                String(strategyCandidate && (strategyCandidate.source_strategy || strategyCandidate.sourceStrategy) || '').trim(),
                String(strategyCandidate && strategyCandidate.strategy || '').trim(),
                String(selected && selected.sourceStrategy || '').trim(),
                String(selected && selected.strategyCode || '').trim(),
            ];

            let strategyName = '';
            for (const candidate of strategyCandidates) {
                const normalized = String(candidate || '').trim().toLowerCase();
                if (!normalized) {
                    continue;
                }
                strategyName = aliasMap[normalized] || normalized;
                break;
            }
            if (!strategyName) {
                return {
                    symbol: selected.symbol,
                    strategyName: '',
                    windowDays: 0,
                    timeframe: String(this.config.timeframe || '1d').trim() || '1d',
                };
            }

            const windowDays = Math.max(
                20,
                Number((typeof this.rankingBestWindowDays === 'function' ? this.rankingBestWindowDays(rankingMatch) : 0) || 0)
                || Number(latestRun && latestRun.window_days || 0)
                || 90
            );
            const timeframe = String(
                rankingMatch && rankingMatch.timeframe
                || (latestRun && latestRun.timeframe)
                || this.config.timeframe
                || '1d'
            ).trim() || '1d';

            return {
                symbol: selected.symbol,
                strategyName,
                windowDays,
                timeframe,
            };
        },

        async loadSelectedBacktestEquity(options = {}) {
            const silent = Boolean(options.silent);
            const throwOnError = Boolean(options.throwOnError);
            const request = options.request && typeof options.request === 'object'
                ? options.request
                : this.selectedBacktestEquityRequest();

            if (!request || !request.symbol) {
                this.backtestEquityCurve = null;
                this.backtestEquityCurveLoading = false;
                this.backtestEquityCurveError = '';
                this.backtestEquityCurveKey = '';
                return null;
            }

            if (!request.strategyName) {
                this.backtestEquityCurve = null;
                this.backtestEquityCurveLoading = false;
                this.backtestEquityCurveError = '当前聚焦策略还没有可回放的 backtest 策略映射。';
                this.backtestEquityCurveKey = '';
                return null;
            }

            const requestKey = [request.symbol, request.strategyName, request.windowDays, request.timeframe].join('|');
            this.backtestEquityCurveKey = requestKey;
            this.backtestEquityCurveLoading = true;
            this.backtestEquityCurveError = '';

            try {
                const params = new URLSearchParams({
                    symbol: String(request.symbol || '').trim().toUpperCase(),
                    strategy_name: String(request.strategyName || '').trim().toLowerCase(),
                    window_days: String(request.windowDays || 90),
                    timeframe: String(request.timeframe || '1d').trim().toLowerCase(),
                });
                const payload = await this.apiRequest(`/v1/admin/backtests/equity-curve?${params.toString()}`);
                if (this.backtestEquityCurveKey === requestKey) {
                    this.consumeBacktestEquityCurve(payload);
                    this.backtestEquityCurveError = '';
                }
                return payload;
            } catch (error) {
                if (this.backtestEquityCurveKey === requestKey) {
                    this.backtestEquityCurve = null;
                    this.backtestEquityCurveError = `权益曲线加载失败: ${error.message || '未知错误'}`;
                }
                if (!silent) {
                    this.log('warn', `权益曲线同步失败: ${error.message || '未知错误'}`);
                }
                if (throwOnError) {
                    throw error;
                }
                return null;
            } finally {
                if (this.backtestEquityCurveKey === requestKey) {
                    this.backtestEquityCurveLoading = false;
                }
            }
        },

        backtestEquityRange(curve = this.selectedBacktestEquityCurve()) {
            const series = curve && Array.isArray(curve.equity_series) ? curve.equity_series : [];
            if (!series.length) {
                return {
                    min: 0,
                    max: 0,
                    latest: 0,
                    minLabel: 'min --',
                    maxLabel: 'max --',
                    latestLabel: 'latest --',
                };
            }
            const equities = series.map((item) => this.toNumber(item.equity));
            const min = Math.min(...equities);
            const max = Math.max(...equities);
            const latest = equities[equities.length - 1];
            return {
                min,
                max,
                latest,
                minLabel: `min ${this.toFixed(min, 2)}x`,
                maxLabel: `max ${this.toFixed(max, 2)}x`,
                latestLabel: `latest ${this.toFixed(latest, 2)}x`,
            };
        },

        backtestEquitySummaryCards() {
            const curve = this.selectedBacktestEquityCurve();
            if (!curve) {
                return [];
            }
            const metrics = curve.metrics || {};
            const range = this.backtestEquityRange(curve);
            return [
                {
                    id: 'return',
                    label: 'Total Return',
                    value: this.formatPct(metrics.total_return_percent, 2),
                    meta: range.latestLabel,
                },
                {
                    id: 'drawdown',
                    label: 'Max Drawdown',
                    value: this.formatPct(metrics.max_drawdown_percent, 2),
                    meta: range.maxLabel,
                },
                {
                    id: 'win-rate',
                    label: 'Win Rate',
                    value: this.formatPct(metrics.win_rate, 1),
                    meta: `${this.formatInt(metrics.trade_count)} trades`,
                },
                {
                    id: 'sharpe',
                    label: 'Sharpe / Avg Trade',
                    value: `${this.toFixed(metrics.sharpe_ratio, 2)} / ${this.formatPct(metrics.avg_trade_return_percent, 2)}`,
                    meta: `${this.formatInt(metrics.samples)} samples`,
                },
            ];
        },

        backtestEquityPlotPoints(curve = this.selectedBacktestEquityCurve(), width = 640, height = 220, padding = 18) {
            const series = curve && Array.isArray(curve.equity_series) ? curve.equity_series : [];
            if (!series.length) {
                return [];
            }

            const equities = series.map((item) => this.toNumber(item.equity));
            const minEquity = Math.min(...equities);
            const maxEquity = Math.max(...equities);
            const span = maxEquity - minEquity;
            const usableWidth = Math.max(width - (padding * 2), 1);
            const usableHeight = Math.max(height - (padding * 2), 1);
            const lastIndex = Math.max(series.length - 1, 1);

            return series.map((item, index) => {
                const x = series.length === 1
                    ? width / 2
                    : padding + ((usableWidth * index) / lastIndex);
                const normalized = span <= 0.0001 ? 0.5 : ((this.toNumber(item.equity) - minEquity) / span);
                const y = height - padding - (normalized * usableHeight);
                return {
                    id: item.id || `plot-${index}`,
                    x,
                    y,
                    timestamp: item.timestamp,
                    equity: this.toNumber(item.equity),
                    drawdown_percent: this.toNumber(item.drawdown_percent),
                };
            });
        },

        backtestEquityLinePath(curve = this.selectedBacktestEquityCurve(), width = 640, height = 220, padding = 18) {
            const points = this.backtestEquityPlotPoints(curve, width, height, padding);
            if (!points.length) {
                return '';
            }
            return points
                .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
                .join(' ');
        },

        backtestEquityAreaPath(curve = this.selectedBacktestEquityCurve(), width = 640, height = 220, padding = 18) {
            const points = this.backtestEquityPlotPoints(curve, width, height, padding);
            if (!points.length) {
                return '';
            }
            const baseline = (height - padding).toFixed(2);
            const path = points
                .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
                .join(' ');
            return `M ${points[0].x.toFixed(2)} ${baseline} ${path.slice(1)} L ${points[points.length - 1].x.toFixed(2)} ${baseline} Z`;
        },

        backtestEquityPlotMarkers(curve = this.selectedBacktestEquityCurve(), width = 640, height = 220, padding = 18) {
            const points = this.backtestEquityPlotPoints(curve, width, height, padding);
            if (!points.length) {
                return [];
            }
            const indexes = Array.from(new Set([0, Math.floor((points.length - 1) / 2), points.length - 1]));
            return indexes.map((index) => ({
                ...points[index],
                id: `marker-${index}`,
            }));
        },

        backtestEquityRecentTrades(limit = 3, curve = this.selectedBacktestEquityCurve()) {
            const trades = curve && Array.isArray(curve.trades) ? curve.trades : [];
            return trades.slice(-limit).reverse();
        },

        selectedStrategyBreakdown() {
            const signal = this.selectedSignal();
            const signalId = Number(signal && signal.id || 0);
            if (!signalId || signalId !== this.strategyBreakdownSignalId || !this.strategyBreakdownData) {
                return null;
            }
            return this.strategyBreakdownData;
        },

        async loadSelectedStrategyBreakdown(options = {}) {
            const silent = Boolean(options.silent);
            const throwOnError = Boolean(options.throwOnError);
            const signal = options.signal && typeof options.signal === 'object'
                ? options.signal
                : this.selectedSignal();
            const signalId = Number(signal && signal.id || 0);

            if (!signalId) {
                this.strategyBreakdownData = null;
                this.strategyBreakdownSignalId = 0;
                this.strategyBreakdownLoading = false;
                this.strategyBreakdownError = '';
                return null;
            }

            this.strategyBreakdownLoading = true;
            this.strategyBreakdownError = '';

            try {
                const payload = await this.publicApiRequest(`/v1/signals/${signalId}/strategy-breakdown`);
                const selectedSignal = this.selectedSignal();
                if (selectedSignal && Number(selectedSignal.id || 0) === signalId) {
                    this.strategyBreakdownData = payload;
                    this.strategyBreakdownSignalId = signalId;
                    this.strategyBreakdownError = '';
                }
                return payload;
            } catch (error) {
                const selectedSignal = this.selectedSignal();
                if (selectedSignal && Number(selectedSignal.id || 0) === signalId) {
                    this.strategyBreakdownData = null;
                    this.strategyBreakdownSignalId = signalId;
                    this.strategyBreakdownError = `策略拆解加载失败: ${error.message || '未知错误'}`;
                }
                if (!silent) {
                    this.log('warn', `策略拆解同步失败: ${error.message || '未知错误'}`);
                }
                if (throwOnError) {
                    throw error;
                }
                return null;
            } finally {
                const selectedSignal = this.selectedSignal();
                if (!selectedSignal || Number(selectedSignal.id || 0) === signalId) {
                    this.strategyBreakdownLoading = false;
                }
            }
        },

        selectedStrategyCandidate(signal = this.selectedSignal()) {
            const breakdown = this.selectedStrategyBreakdown();
            if (breakdown && breakdown.selected_candidate && typeof breakdown.selected_candidate === 'object') {
                return breakdown.selected_candidate;
            }
            if (signal && signal.strategySelection && typeof signal.strategySelection === 'object') {
                return signal.strategySelection;
            }
            return null;
        },

        selectedStrategyCandidates(signal = this.selectedSignal()) {
            const breakdown = this.selectedStrategyBreakdown();
            if (breakdown && Array.isArray(breakdown.candidates) && breakdown.candidates.length) {
                return breakdown.candidates;
            }
            if (signal && Array.isArray(signal.strategyCandidates) && signal.strategyCandidates.length) {
                return signal.strategyCandidates;
            }
            const selected = this.selectedStrategyCandidate(signal);
            return selected ? [selected] : [];
        },

        selectedRegimeReasons(signal = this.selectedSignal()) {
            const breakdown = this.selectedStrategyBreakdown();
            if (breakdown && Array.isArray(breakdown.regime_reasons) && breakdown.regime_reasons.length) {
                return breakdown.regime_reasons.filter((item) => String(item || '').trim());
            }
            if (signal && Array.isArray(signal.regimeReasons) && signal.regimeReasons.length) {
                return signal.regimeReasons.filter((item) => String(item || '').trim());
            }
            return [];
        },

        selectedCalibrationSnapshot(signal = this.selectedSignal()) {
            const breakdown = this.selectedStrategyBreakdown();
            const signalSnapshot = this.normalizeCalibrationSnapshot(signal && signal.calibrationSnapshot);
            const fallbackSnapshot = signalSnapshot || this.activeCalibrationSnapshot;
            if (!breakdown && !fallbackSnapshot && !(signal && signal.calibrationVersion)) {
                return null;
            }
            return {
                version: String(
                    breakdown && breakdown.calibration_version
                    || (signal && signal.calibrationVersion)
                    || (fallbackSnapshot && fallbackSnapshot.version)
                    || '--'
                ).trim() || '--',
                source: String(
                    breakdown && breakdown.calibration_source
                    || (signal && signal.calibrationSource)
                    || (fallbackSnapshot && fallbackSnapshot.source)
                    || '--'
                ).trim() || '--',
                effectiveFrom: String(
                    breakdown && breakdown.calibration_effective_from
                    || (signal && signal.calibrationEffectiveFrom)
                    || (fallbackSnapshot && (fallbackSnapshot.effective_from || fallbackSnapshot.effective_at))
                    || ''
                ).trim(),
                atr_multipliers: fallbackSnapshot ? fallbackSnapshot.atr_multipliers : {}
            };
        },

        selectedCalibrationAtrEntries(signal = this.selectedSignal()) {
            const snapshot = this.selectedCalibrationSnapshot(signal);
            const atrMultipliers = snapshot && snapshot.atr_multipliers && typeof snapshot.atr_multipliers === 'object'
                ? snapshot.atr_multipliers
                : {};
            const preferredKeys = [
                signal && signal.exitAtrMultiplierKey,
                signal && signal.marketRegimeDetail,
                signal && signal.marketRegime,
                'default'
            ];
            const seen = new Set();
            const entries = [];

            preferredKeys.forEach((key) => {
                const normalizedKey = String(key || '').trim();
                if (!normalizedKey || seen.has(normalizedKey)) {
                    return;
                }
                seen.add(normalizedKey);
                if (atrMultipliers[normalizedKey] === undefined || atrMultipliers[normalizedKey] === null) {
                    return;
                }
                entries.push({
                    key: normalizedKey,
                    label: this.marketRegimeDetailLabel(normalizedKey),
                    value: this.toNumber(atrMultipliers[normalizedKey]),
                    active: normalizedKey === String(signal && signal.exitAtrMultiplierKey || '').trim()
                });
            });

            if (!entries.length && signal && signal.exitAtrMultiplier > 0) {
                entries.push({
                    key: String(signal.exitAtrMultiplierKey || 'current').trim(),
                    label: signal.exitAtrMultiplierKey
                        ? this.marketRegimeDetailLabel(signal.exitAtrMultiplierKey)
                        : '当前 ATR',
                    value: this.toNumber(signal.exitAtrMultiplier),
                    active: true
                });
            }

            return entries;
        },

        metricKeyLabel(key) {
            const normalized = String(key || '').trim().toLowerCase();
            const mapping = {
                trend_strength: '趋势强度',
                momentum_score: '动量分数',
                momentum_raw: '原始动量',
                volatility_score: '波动分数',
                dislocation_pct: '偏离度',
                volume_score: '量能分数',
                bars_in_regime: '状态持续 bars',
                regime_duration_bars: '状态持续 bars'
            };
            return mapping[normalized] || (normalized ? normalized.replaceAll('_', ' ') : '--');
        },

        selectedRegimeMetricCards(signal = this.selectedSignal()) {
            const breakdown = this.selectedStrategyBreakdown();
            const metrics = breakdown && breakdown.regime_metrics && typeof breakdown.regime_metrics === 'object'
                ? breakdown.regime_metrics
                : (signal && signal.regimeMetrics && typeof signal.regimeMetrics === 'object' ? signal.regimeMetrics : {});
            return Object.entries(metrics)
                .filter(([, value]) => value !== null && value !== undefined && value !== '')
                .slice(0, 4)
                .map(([key, value]) => {
                    const numericValue = this.toNumber(value);
                    const isPercent = key.endsWith('_pct');
                    return {
                        id: key,
                        label: this.metricKeyLabel(key),
                        value: isPercent ? this.formatPct(numericValue * 100, 2) : this.toFixed(numericValue, 2),
                        meta: key
                    };
                });
        },

        exitFieldLabel(key) {
            const mapping = {
                stop_loss: 'Stop',
                take_profit_1: 'TP1',
                take_profit_2: 'TP2',
                take_profit_3: 'TP3'
            };
            return mapping[String(key || '').trim()] || '--';
        },

        coerceNullableNumber(value) {
            if (value === null || value === undefined || value === '') {
                return null;
            }
            const numeric = Number(value);
            return Number.isFinite(numeric) ? numeric : null;
        },

        selectedExitComparisonRows(signal = this.selectedSignal()) {
            if (!signal) {
                return [];
            }
            const clientLevels = signal.clientExitLevels && typeof signal.clientExitLevels === 'object'
                ? signal.clientExitLevels
                : {};
            const serverLevels = signal.serverExitLevels && typeof signal.serverExitLevels === 'object'
                ? signal.serverExitLevels
                : {};
            const liveLevels = {
                stop_loss: signal.stopLoss,
                take_profit_1: signal.takeProfit1,
                take_profit_2: signal.takeProfit2,
                take_profit_3: signal.takeProfit3
            };
            return ['stop_loss', 'take_profit_1', 'take_profit_2', 'take_profit_3']
                .map((fieldName) => {
                    const clientValue = this.coerceNullableNumber(clientLevels[fieldName]);
                    const serverValue = this.coerceNullableNumber(serverLevels[fieldName]);
                    const liveValue = this.coerceNullableNumber(liveLevels[fieldName]);
                    if (clientValue === null && serverValue === null && liveValue === null) {
                        return null;
                    }
                    const delta = clientValue !== null && serverValue !== null
                        ? Math.abs(clientValue - serverValue)
                        : null;
                    return {
                        key: fieldName,
                        label: this.exitFieldLabel(fieldName),
                        clientLabel: clientValue !== null ? this.toFixed(clientValue, 4) : '--',
                        serverLabel: serverValue !== null ? this.toFixed(serverValue, 4) : '--',
                        liveLabel: liveValue !== null ? this.toFixed(liveValue, 4) : '--',
                        deltaLabel: delta !== null ? this.toFixed(delta, 4) : '--'
                    };
                })
                .filter(Boolean);
        },

        selectedExitQualityCards() {
            const metrics = this.exitQualityMetrics || this.emptyExitQualityMetrics();
            const coveragePct = metrics.total_signals > 0
                ? this.percent(metrics.exits_available, metrics.total_signals)
                : 0;
            return [
                {
                    id: 'coverage',
                    label: '退出位覆盖',
                    value: `${this.formatInt(metrics.exits_available)} / ${this.formatInt(metrics.total_signals)}`,
                    meta: `覆盖率 ${this.formatPct(coveragePct, 1)}`
                },
                {
                    id: 'source-balance',
                    label: '自动闭环 / 客户端',
                    value: `${this.formatInt(metrics.calibrated_exit_count)} / ${this.formatInt(metrics.client_exit_count)}`,
                    meta: '校准输出 vs 客户端退出位'
                },
                {
                    id: 'avg-rr',
                    label: '平均 RR / ATR',
                    value: `${this.toFixed(metrics.avg_risk_reward_ratio, 2)} / ${this.toFixed(metrics.avg_atr_multiplier, 2)}`,
                    meta: '窗口样本平均风险收益与 ATR 系数'
                },
                {
                    id: 'avg-distance',
                    label: '平均 Stop / TP1 距离',
                    value: `${this.formatPct(metrics.avg_stop_distance_pct, 2)} / ${this.formatPct(metrics.avg_tp1_distance_pct, 2)}`,
                    meta: '相对 entry 的距离占比'
                }
            ];
        },

        calibrationProposalSummaryCards() {
            const proposal = this.selectedCalibrationProposal();
            if (!proposal) {
                return [];
            }
            return [
                {
                    id: 'proposal-version',
                    label: '版本切换',
                    value: `${proposal.current_version} → ${this.proposalPreviewVersion()}`,
                    meta: proposal.generated_at ? `生成 ${this.formatDateTime(proposal.generated_at)}` : '等待生成时间'
                },
                {
                    id: 'proposal-sample',
                    label: '信号 / Trade Actions',
                    value: `${this.formatInt(proposal.summary.total_signals)} / ${this.formatInt(proposal.summary.total_trade_actions)}`,
                    meta: `交集标的 ${this.formatInt(proposal.summary.overlapping_symbols)}`
                },
                {
                    id: 'proposal-rates',
                    label: 'Action / Executed',
                    value: `${this.formatPct(proposal.summary.trade_action_rate, 1)} / ${this.formatPct(proposal.summary.executed_trade_rate, 1)}`,
                    meta: 'signal-results 转化率基线'
                },
                {
                    id: 'proposal-payload',
                    label: 'Payload Blocks',
                    value: `${Object.keys(proposal.snapshot_payload.strategy_weights || {}).length} / ${Object.keys(proposal.snapshot_payload.score_multipliers || {}).length} / ${Object.keys(proposal.snapshot_payload.atr_multipliers || {}).length}`,
                    meta: 'strategy / score / ATR'
                }
            ];
        },

        proposalAdjustmentItems(group, limit = 4) {
            const proposal = this.selectedCalibrationProposal();
            const items = proposal && Array.isArray(proposal[group]) ? proposal[group] : [];
            return items.slice(0, Math.max(0, Number(limit || 0)) || items.length);
        },

        proposalAdjustmentLabel(group, key) {
            const normalizedGroup = String(group || '').trim();
            const normalizedKey = String(key || '').trim();
            if (normalizedGroup === 'strategy_weights') {
                return this.strategyLabel(normalizedKey);
            }
            if (normalizedGroup === 'atr_multipliers') {
                return this.marketRegimeDetailLabel(normalizedKey);
            }
            return this.metricKeyLabel(normalizedKey);
        },

        proposalAdjustmentDeltaLabel(delta) {
            const numeric = this.toNumber(delta);
            return `${numeric > 0 ? '+' : ''}${this.toFixed(numeric, 2)}`;
        },

        proposalAdjustmentDeltaClass(delta) {
            const numeric = this.toNumber(delta);
            if (numeric > 0.001) {
                return 'border-mint/20 bg-mint/10 text-mint';
            }
            if (numeric < -0.001) {
                return 'border-coral/20 bg-coral/10 text-coral';
            }
            return 'border-ink/10 bg-white/85 text-ink/60';
        },

        ...tradingAgentsModule,

        selectedSignal() {
            if (!this.selectedSymbol) {
                return null;
            }
            const selected = this.watchlist.find((item) => item.symbol === this.selectedSymbol) || null;
            if (selected) {
                return selected;
            }
            if (this.marketFocusEntry && this.marketFocusEntry.symbol === this.selectedSymbol) {
                return this.marketFocusEntry;
            }
            return null;
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

        resolveStrategyCode(indicators, strategySelection = null) {
            if (strategySelection && typeof strategySelection === 'object' && strategySelection.strategy) {
                return String(strategySelection.strategy).toLowerCase();
            }
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
