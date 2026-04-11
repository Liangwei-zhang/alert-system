function normalizeBaseUrl(value) {
    return String(value || '').trim().replace(/\/+$/, '');
}

function parseWindowHours(value) {
    const parsed = Number.parseInt(String(value || '').trim(), 10);
    if (!Number.isFinite(parsed) || parsed < 1) {
        return 168;
    }
    return Math.min(8760, parsed);
}

function normalizeTradingAgentsSlug(value, maxLen = 20, fallback = 'na') {
    const raw = String(value || '').trim().toLowerCase();
    const normalized = raw.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    return (normalized || fallback).slice(0, maxLen);
}

function normalizeTradingAgentsAnalysisDate(value) {
    const text = String(value || '').trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
        return text;
    }
    const parsed = new Date(text);
    if (Number.isNaN(parsed.getTime())) {
        return '';
    }
    return parsed.toISOString().slice(0, 10);
}

function buildTradingAgentsRequestId({ ticker, analysisDate, triggerType, source, runId }) {
    const sourcePart = normalizeTradingAgentsSlug(source, 20, 'platform');
    const triggerPart = normalizeTradingAgentsSlug(triggerType, 20, 'manual');
    const tickerPart = normalizeTradingAgentsSlug(ticker, 16, 'unknown');
    const datePart = normalizeTradingAgentsAnalysisDate(analysisDate) || new Date().toISOString().slice(0, 10);
    const generatedRunId = runId || `ui-${Date.now().toString(36)}`;
    const runPart = normalizeTradingAgentsSlug(generatedRunId, 24, 'ui');
    return `${sourcePart}:${triggerPart}:${tickerPart}:${datePart}:${runPart}`;
}

function normalizeTradingAgentsStatus(status, httpStatus = null) {
    const normalized = String(status || '').trim().toLowerCase();
    const mapping = {
        queued: 'pending',
        pending: 'pending',
        submitted: 'submitted',
        running: 'running',
        succeeded: 'completed',
        completed: 'completed',
        failed: 'failed',
        error: 'failed',
        canceled: 'failed',
        cancelled: 'failed',
        timeout: 'timeout'
    };
    if (normalized) {
        return mapping[normalized] || 'running';
    }
    if (httpStatus === 200) {
        return 'completed';
    }
    if (httpStatus === 409) {
        return 'failed';
    }
    if (httpStatus === 202) {
        return 'running';
    }
    return 'running';
}

function tradingAgentsStatusLabel(status) {
    const normalized = normalizeTradingAgentsStatus(status);
    const mapping = {
        pending: '排队中',
        submitted: '已提交',
        running: '运行中',
        completed: '已完成',
        failed: '失败',
        timeout: '超时'
    };
    return mapping[normalized] || normalized || '--';
}

function tradingAgentsStatusClass(status) {
    const normalized = normalizeTradingAgentsStatus(status);
    if (normalized === 'completed') {
        return 'bg-mint/15 text-mint';
    }
    if (normalized === 'failed' || normalized === 'timeout') {
        return 'bg-coral/15 text-coral';
    }
    if (normalized === 'pending' || normalized === 'submitted') {
        return 'bg-sun/15 text-sun';
    }
    return 'bg-tide/12 text-tide';
}

function tradingAgentsActionLabel(action) {
    const normalized = String(action || '').trim().toLowerCase();
    const mapping = {
        buy: '买入',
        sell: '卖出',
        hold: '持有',
        no_action: '不操作',
        add: '加仓',
        reduce: '减仓'
    };
    return mapping[normalized] || normalized || '--';
}

function isTradingAgentsTerminal(status) {
    const normalized = normalizeTradingAgentsStatus(status);
    return normalized === 'completed' || normalized === 'failed' || normalized === 'timeout';
}

function pickFirstText(values) {
    for (const value of values || []) {
        if (typeof value === 'string' && value.trim()) {
            return value.trim();
        }
        if (typeof value === 'number' && Number.isFinite(value)) {
            return String(value);
        }
    }
    return '';
}

function extractTradingAgentsUris(payload) {
    const containers = [
        payload,
        payload && payload.projection,
        payload && payload.result_payload,
        payload && payload.result,
        payload && payload.projection && payload.projection.result_payload
    ];

    let reportUri = '';
    let resultUri = '';

    for (const item of containers) {
        if (!item || typeof item !== 'object') {
            continue;
        }
        reportUri = reportUri || pickFirstText([
            item.report_uri,
            item.report_url,
            item.reportUri
        ]);
        resultUri = resultUri || pickFirstText([
            item.result_uri,
            item.result_url,
            item.resultUri,
            item.storage_uri,
            item.output_uri
        ]);

        if (item.artifacts && typeof item.artifacts === 'object') {
            reportUri = reportUri || pickFirstText([
                item.artifacts.report_uri,
                item.artifacts.report_url
            ]);
            resultUri = resultUri || pickFirstText([
                item.artifacts.result_uri,
                item.artifacts.result_url
            ]);
        }
    }

    return {
        report_uri: reportUri,
        result_uri: resultUri
    };
}

function readErrorCode(payload) {
    if (!payload || typeof payload !== 'object') {
        return '';
    }
    if (typeof payload.code === 'string' && payload.code.trim()) {
        return payload.code.trim();
    }
    if (payload.error && typeof payload.error === 'object') {
        if (typeof payload.error.code === 'string' && payload.error.code.trim()) {
            return payload.error.code.trim();
        }
    }
    return '';
}

function stringifyErrorValue(value) {
    if (typeof value === 'string' && value.trim()) {
        return value.trim();
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
        return String(value);
    }
    if (Array.isArray(value)) {
        const messages = value
            .map((item) => stringifyErrorValue(item))
            .filter(Boolean);
        return messages.join('; ');
    }
    if (value && typeof value === 'object') {
        if (typeof value.message === 'string' && value.message.trim()) {
            return value.message.trim();
        }
        if (typeof value.msg === 'string' && value.msg.trim()) {
            return value.msg.trim();
        }
        if (typeof value.detail === 'string' && value.detail.trim()) {
            return value.detail.trim();
        }
        try {
            return JSON.stringify(value);
        } catch (error) {
            return '';
        }
    }
    return '';
}

function readErrorMessage(payload, status) {
    if (payload && typeof payload === 'object') {
        if (payload.error && typeof payload.error === 'object') {
            return stringifyErrorValue(payload.error.message)
                || stringifyErrorValue(payload.error.detail)
                || stringifyErrorValue(payload.error.code)
                || stringifyErrorValue(payload.message)
                || stringifyErrorValue(payload.detail)
                || stringifyErrorValue(payload.code)
                || `HTTP ${status}`;
        }
        return stringifyErrorValue(payload.message)
            || stringifyErrorValue(payload.detail)
            || stringifyErrorValue(payload.code)
            || `HTTP ${status}`;
    }
    if (typeof payload === 'string' && payload.trim()) {
        return payload.trim();
    }
    return `HTTP ${status}`;
}

function isSessionRevokedError(payload, status) {
    const code = readErrorCode(payload).toLowerCase();
    const message = readErrorMessage(payload, status).toLowerCase();
    if (status === 401) {
        return true;
    }
    if (['session_revoked', 'token_revoked', 'invalid_token', 'token_expired'].includes(code)) {
        return true;
    }
    return message.includes('session is no longer active')
        || message.includes('session_revoked')
        || message.includes('token expired');
}

function parseCsvStrings(value) {
    return String(value || '')
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean);
}

function parseCsvInts(value) {
    return String(value || '')
        .split(',')
        .map((item) => Number.parseInt(item.trim(), 10))
        .filter((item) => Number.isFinite(item) && item > 0);
}

function strategyAdvice(item) {
    if (!item) {
        return '等待策略健康数据。';
    }
    if (item.degradation >= 8) {
        return '退化明显，建议缩窄标的池并下调权重。';
    }
    if (item.degradation >= 5) {
        return '中度退化，建议优先回跑 30/90 天窗口。';
    }
    if (!item.stable) {
        return '稳定性不足，建议增加风险保护阈值。';
    }
    if (item.score < 12) {
        return '收益质量偏弱，建议放入候选策略。';
    }
    return '策略稳定，可保持线上主路由。';
}

function ruleClass(strategy) {
    if (strategy === 'mean_reversion') {
        return 'bg-sun/15 text-sun';
    }
    if (strategy === 'trend_continuation') {
        return 'bg-mint/15 text-mint';
    }
    if (strategy === 'volatility_breakout') {
        return 'bg-coral/15 text-coral';
    }
    return 'bg-tide/12 text-tide';
}

function normalizeSignalType(value) {
    return String(value || '').trim().toLowerCase().replace('-', '_');
}

function signalTypeLabel(value) {
    const normalized = normalizeSignalType(value);
    const mapping = {
        buy: '买入',
        sell: '卖出',
        split_buy: '分批买入',
        split_sell: '分批卖出'
    };
    return mapping[normalized] || '未知方向';
}

function statusLabel(value) {
    const normalized = String(value || '').trim().toLowerCase();
    const mapping = {
        pending: '待触发',
        active: '活跃',
        triggered: '已触发',
        expired: '已过期',
        cancelled: '已取消'
    };
    return mapping[normalized] || normalized || '--';
}

function strategyLabel(value) {
    const normalized = String(value || '').trim().toLowerCase();
    const mapping = {
        mean_reversion: '均值回归',
        trend_continuation: '趋势延续',
        volatility_breakout: '波动突破',
        range_rotation: '区间轮动',
        trend_following: '趋势跟随',
        breakout: '突破策略',
        ranking_refresh: '排行刷新',
        unknown: '未标注'
    };
    return mapping[normalized] || normalized.replaceAll('_', ' ');
}

function decisionLabel(decision, suppressed) {
    if (suppressed) {
        return '已抑制';
    }
    const normalized = String(decision || '').trim().toLowerCase();
    const mapping = {
        emitted: '已发射',
        suppressed: '已抑制',
        skipped: '已跳过',
        error: '异常'
    };
    return mapping[normalized] || '未知';
}

function decisionClass(decision, suppressed) {
    if (suppressed) {
        return 'bg-coral/15 text-coral';
    }
    const normalized = String(decision || '').trim().toLowerCase();
    if (normalized === 'emitted') {
        return 'bg-mint/15 text-mint';
    }
    if (normalized === 'error') {
        return 'bg-coral/15 text-coral';
    }
    return 'bg-ink/10 text-ink/70';
}

function toNumber(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
}

function toFixedNumber(value, digits = 2) {
    return toNumber(value).toFixed(digits);
}

function computeTarget1Pct(rawSignal) {
    const entry = toNumber(rawSignal.entry_price);
    const tp1 = toNumber(rawSignal.take_profit_1);
    if (!(entry > 0) || !(tp1 > 0)) {
        return 0;
    }
    const signalType = normalizeSignalType(rawSignal.signal_type);
    if (signalType.startsWith('sell')) {
        return ((entry / tp1) - 1) * 100;
    }
    return ((tp1 / entry) - 1) * 100;
}

function percent(value, total) {
    const denominator = total > 0 ? total : 1;
    return Math.max(0, Math.min(100, Math.round((Number(value || 0) / denominator) * 100)));
}

function formatInt(value) {
    return Math.round(toNumber(value)).toLocaleString('zh-CN');
}

function formatPct(value, digits = 2) {
    return `${toNumber(value).toFixed(digits)}%`;
}

function formatDateTime(value) {
    if (!value) {
        return '--';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return '--';
    }
    return date.toISOString().replace('T', ' ').slice(0, 19);
}

function formatTime(value) {
    if (!value) {
        return '--:--:--';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return '--:--:--';
    }
    return date.toISOString().slice(11, 19);
}

window.PlatformDeckUtils = {
    normalizeBaseUrl,
    parseWindowHours,
    normalizeTradingAgentsSlug,
    normalizeTradingAgentsAnalysisDate,
    buildTradingAgentsRequestId,
    normalizeTradingAgentsStatus,
    tradingAgentsStatusLabel,
    tradingAgentsStatusClass,
    tradingAgentsActionLabel,
    isTradingAgentsTerminal,
    pickFirstText,
    extractTradingAgentsUris,
    readErrorCode,
    readErrorMessage,
    isSessionRevokedError,
    parseCsvStrings,
    parseCsvInts,
    strategyAdvice,
    ruleClass,
    normalizeSignalType,
    signalTypeLabel,
    statusLabel,
    strategyLabel,
    decisionLabel,
    decisionClass,
    toNumber,
    toFixed: toFixedNumber,
    toFixedNumber,
    computeTarget1Pct,
    percent,
    formatInt,
    formatPct,
    formatDateTime,
    formatTime
};
