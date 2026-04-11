const PLATFORM_DECK_STORAGE_KEYS = Object.freeze({
    baseUrl: 'admin_api_url',
    publicBaseUrl: 'public_api_url',
    token: 'admin_api_token',
    legacyToken: 'stockpy.ui.admin-token',
    adminAuthEmail: 'platform_admin_auth_email',
    adminRefreshToken: 'stockpy.ui.admin-refresh-token',
    adminSession: 'platform_admin_session',
    adminTokenSource: 'platform_admin_token_source',
    adminVerifiedAt: 'platform_admin_verified_at',
    adminLocale: 'platform_admin_locale',
    adminTimezone: 'platform_admin_timezone',
    timeframe: 'platform_backtest_timeframe',
    windowHours: 'platform_window_hours',
    taIncludeFullPayload: 'platform_tradingagents_include_full_payload',
    workspaceMode: 'platform_workspace_mode',
    workspaceSection: 'platform_workspace_section'
});

const PLATFORM_DECK_WORKSPACE_MODES = Object.freeze([
    Object.freeze({
        key: 'overview',
        label: '总览',
        description: '保持全部面板，适合日常总览和巡检。'
    }),
    Object.freeze({
        key: 'signals',
        label: '信号台',
        description: '聚焦盯盘雷达、判定流和预警逻辑。'
    }),
    Object.freeze({
        key: 'execution',
        label: '执行台',
        description: '聚焦退出策略、日志和分发漏斗。'
    }),
    Object.freeze({
        key: 'research',
        label: '研究台',
        description: '聚焦 TradingAgents、回测与策略健康。'
    })
]);

const PLATFORM_DECK_DEFAULT_CONFIG = Object.freeze({
    baseUrl: '',
    publicBaseUrl: '',
    token: '',
    timeframe: '1d',
    windowHours: 168
});

const PLATFORM_DECK_DEFAULT_RUN_FORM = Object.freeze({
    symbols: 'AAPL,MSFT,TSLA,NVDA,AMZN',
    strategyNames: 'trend_following,mean_reversion,breakout',
    windows: '30,90,180,365'
});

const PLATFORM_DECK_DEFAULT_FUNNEL_STAGES = Object.freeze([
    Object.freeze({ name: '扫描判定总量', value: '0', progress: 0 }),
    Object.freeze({ name: '进入通知裂变', value: '0', progress: 0 }),
    Object.freeze({ name: '发出信号事件', value: '0', progress: 0 }),
    Object.freeze({ name: '运行中任务', value: '0', progress: 0 })
]);

const PLATFORM_DECK_STRATEGY_RULES = Object.freeze([
    Object.freeze({
        strategy: 'mean_reversion',
        label: '均值回归',
        when: '|dislocation| >= 3%',
        explain: '偏离 20-bar 均值超过 3% 时，优先做反转回归。'
    }),
    Object.freeze({
        strategy: 'trend_continuation',
        label: '趋势延续',
        when: 'momentum >= 0.65',
        explain: '动量分数达到阈值，顺势继续推进。'
    }),
    Object.freeze({
        strategy: 'volatility_breakout',
        label: '波动突破',
        when: 'volatility >= 0.75',
        explain: '波动率放大时切换突破框架，放宽止盈空间。'
    }),
    Object.freeze({
        strategy: 'range_rotation',
        label: '区间轮动',
        when: '其余情况',
        explain: '在趋势不明显时维持区间轮动防守。'
    })
]);

function createPlatformDeckTradingAgentsDraft() {
    return {
        ticker: 'AAPL',
        analysisDate: new Date().toISOString().slice(0, 10),
        triggerType: 'manual',
        source: 'platform',
        runId: '',
        selectedAnalysts: ''
    };
}

window.PlatformDeckConstants = {
    storageKeys: PLATFORM_DECK_STORAGE_KEYS,
    workspaceModes: PLATFORM_DECK_WORKSPACE_MODES,
    defaultConfig: PLATFORM_DECK_DEFAULT_CONFIG,
    defaultRunForm: PLATFORM_DECK_DEFAULT_RUN_FORM,
    defaultFunnelStages: PLATFORM_DECK_DEFAULT_FUNNEL_STAGES,
    strategyRules: PLATFORM_DECK_STRATEGY_RULES,
    createTradingAgentsDraft: createPlatformDeckTradingAgentsDraft
};
