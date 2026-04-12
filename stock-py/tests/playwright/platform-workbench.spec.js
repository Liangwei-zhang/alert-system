const { test, expect } = require('@playwright/test');

const ADMIN_BASE_URL = 'http://127.0.0.1:4011';
const PUBLIC_BASE_URL = 'http://127.0.0.1:4012';
const PLATFORM_URL = `http://127.0.0.1:4173/frontend/platform/index.html?admin_api_base_url=${encodeURIComponent(ADMIN_BASE_URL)}&public_api_base_url=${encodeURIComponent(PUBLIC_BASE_URL)}&admin_api_token=dev-token`;

const appliedCalibrationSnapshot = {
    id: 13,
    version: 'signals-v2-proposal-20260413',
    source: 'proposal_review',
    strategy_weights: { trend_continuation: 1.1, volatility_breakout: 1.01 },
    score_multipliers: { confidence: 1.06, quality: 1.02 },
    atr_multipliers: { trend_strong_up: 1.68, volatile_breakout: 1.82, range_balanced: 1.74 },
    derived_from: 'run-24; signal_results:2026-04-12T00:00:00Z',
    sample_size: 2,
    is_active: true,
    effective_from: '2026-04-13T10:12:00Z',
    effective_at: '2026-04-13T10:12:00Z',
    notes: 'Fixture proposal; operator approved',
    created_at: '2026-04-13T10:12:00Z',
    updated_at: '2026-04-13T10:12:00Z',
};

function buildBars(basePrice) {
    const bars = [];
    let price = basePrice;
    for (let index = 0; index < 40; index += 1) {
        const drift = 0.7 + ((index % 5) * 0.04);
        const open = Number((price - 0.2).toFixed(4));
        const close = Number((price + drift).toFixed(4));
        const high = Number((close + 0.35).toFixed(4));
        const low = Number((open - 0.28).toFixed(4));
        bars.push({
            timestamp: new Date(Date.UTC(2026, 3, 1 + index)).toISOString(),
            open,
            high,
            low,
            close,
            volume: 1_000_000 + (index * 10_000),
        });
        price = close;
    }
    return bars;
}

function buildEquitySeries(values, startDay = 10) {
    return values.map((equity, index) => ({
        timestamp: new Date(Date.UTC(2026, 3, startDay + index)).toISOString(),
        equity,
        drawdown_percent: index === 0 ? 0 : Math.max(0, Number((((Math.max(...values.slice(0, index + 1)) - equity) / Math.max(...values.slice(0, index + 1))) * 100).toFixed(4))),
    }));
}

const adminPayloads = {
    '/v1/admin/signal-stats/summary': {
        active_signals: 2,
        triggered_signals: 1,
        avg_confidence: 78.4,
        avg_probability: 0.67,
    },
    '/v1/admin/signal-stats': {
        data: [
            {
                id: 101,
                symbol: 'AAPL',
                signal_type: 'buy',
                status: 'active',
                entry_price: 102.25,
                stop_loss: 97.15,
                take_profit_1: 109.05,
                take_profit_2: 110.75,
                take_profit_3: 114.15,
                risk_reward_ratio: 2.4,
                atr_value: 3.4,
                atr_multiplier: 1.5,
                confidence: 82.0,
                probability: 0.71,
                generated_at: '2026-04-12T09:30:00Z',
                indicators: {
                    strategy_window: '1d',
                    market_regime: 'trend',
                    market_regime_detail: 'trend_strong_up',
                    regime_duration_bars: 15,
                    regime_metrics: { trend_strength: 0.92, momentum_score: 0.88 },
                    regime_reasons: ['strong-trend-threshold', 'volume-confirmed'],
                    calibration_version: 'signals-v2-feedback-20260412T093000Z-r24',
                    calibration_snapshot: {
                        version: 'signals-v2-feedback-20260412T093000Z-r24',
                        source: 'backtest_feedback_loop',
                        effective_from: '2026-04-12T09:30:00Z',
                        atr_multipliers: {
                            trend_strong_up: 1.5,
                            trend: 1.45,
                            default: 1.35,
                        },
                    },
                    strategy_selection: {
                        strategy: 'trend_continuation',
                        source: 'ranking',
                        source_strategy: 'trend_following',
                        rank: 1,
                        ranking_score: 18.2,
                        combined_score: 24.1,
                        signal_fit_score: 8.1,
                        regime_bias: 3.0,
                        degradation_penalty: 0.2,
                        stable: true,
                        market_regime_detail: 'trend_strong_up',
                        regime_duration_bars: 15,
                        strategy_weight: 1.08,
                        calibration_version: 'signals-v2-feedback-20260412T093000Z-r24',
                        regime_metrics: { trend_strength: 0.92, momentum_score: 0.88 },
                        regime_reasons: ['strong-trend-threshold', 'volume-confirmed'],
                    },
                    strategy_candidates: [
                        {
                            strategy: 'trend_continuation',
                            source: 'ranking',
                            source_strategy: 'trend_following',
                            rank: 1,
                            ranking_score: 18.2,
                            combined_score: 24.1,
                            signal_fit_score: 8.1,
                            regime_bias: 3.0,
                            degradation_penalty: 0.2,
                            stable: true,
                            market_regime_detail: 'trend_strong_up',
                            regime_duration_bars: 15,
                            strategy_weight: 1.08,
                            calibration_version: 'signals-v2-feedback-20260412T093000Z-r24',
                        },
                        {
                            strategy: 'volatility_breakout',
                            source: 'ranking',
                            source_strategy: 'breakout',
                            rank: 2,
                            ranking_score: 14.6,
                            combined_score: 17.9,
                            signal_fit_score: 6.3,
                            regime_bias: 0.8,
                            degradation_penalty: 1.4,
                            stable: true,
                            market_regime_detail: 'trend_strong_up',
                            regime_duration_bars: 15,
                            strategy_weight: 1.0,
                            calibration_version: 'signals-v2-feedback-20260412T093000Z-r24',
                        },
                    ],
                    exit_levels: {
                        source: 'server_default',
                        atr_value: 3.4,
                        atr_multiplier: 1.5,
                        atr_multiplier_key: 'trend_strong_up',
                        atr_multiplier_source: 'calibration_snapshot',
                        client_levels: {},
                        server_levels: {
                            stop_loss: 97.15,
                            take_profit_1: 109.05,
                            take_profit_2: 110.75,
                            take_profit_3: 114.15,
                        },
                    },
                    score_breakdown: {
                        base_score: 32,
                        signal_bias: 4,
                        confidence_points: 8.2,
                        probability_points: 7.1,
                        risk_reward_points: 4.8,
                        volume_bonus: 1.4,
                        trend_bonus: 1.2,
                        reversal_bonus: 0,
                        quality_bonus: 2.1,
                        stale_penalty: 0,
                        liquidity_penalty: 0.4,
                        selected_score: 87,
                    },
                },
            },
            {
                id: 102,
                symbol: 'MSFT',
                signal_type: 'buy',
                status: 'triggered',
                entry_price: 214.8,
                stop_loss: 205.5,
                take_profit_1: 229.2,
                take_profit_2: 235.8,
                take_profit_3: 247.1,
                risk_reward_ratio: 2.8,
                atr_value: 5.2,
                atr_multiplier: 1.85,
                confidence: 76.0,
                probability: 0.64,
                generated_at: '2026-04-13T10:00:00Z',
                indicators: {
                    strategy_window: '1d',
                    market_regime: 'volatile',
                    market_regime_detail: 'volatile_breakout',
                    regime_duration_bars: 8,
                    regime_metrics: { volatility_score: 0.91, momentum_score: 0.63 },
                    regime_reasons: ['volatility-expansion', 'breakout-follow-through'],
                    calibration_version: 'signals-v2-manual-20260413T100000Z-r08',
                    calibration_snapshot: {
                        version: 'signals-v2-manual-20260413T100000Z-r08',
                        source: 'manual_review',
                        effective_from: '2026-04-13T10:00:00Z',
                        atr_multipliers: {
                            volatile_breakout: 1.85,
                            volatile: 1.75,
                            default: 1.45,
                        },
                    },
                    strategy_selection: {
                        strategy: 'volatility_breakout',
                        source: 'ranking',
                        source_strategy: 'breakout',
                        rank: 1,
                        ranking_score: 17.4,
                        combined_score: 22.2,
                        signal_fit_score: 7.2,
                        regime_bias: 3.5,
                        degradation_penalty: 0.6,
                        stable: true,
                        market_regime_detail: 'volatile_breakout',
                        regime_duration_bars: 8,
                        strategy_weight: 1.03,
                        calibration_version: 'signals-v2-manual-20260413T100000Z-r08',
                        regime_metrics: { volatility_score: 0.91, momentum_score: 0.63 },
                        regime_reasons: ['volatility-expansion', 'breakout-follow-through'],
                    },
                    strategy_candidates: [
                        {
                            strategy: 'volatility_breakout',
                            source: 'ranking',
                            source_strategy: 'breakout',
                            rank: 1,
                            ranking_score: 17.4,
                            combined_score: 22.2,
                            signal_fit_score: 7.2,
                            regime_bias: 3.5,
                            degradation_penalty: 0.6,
                            stable: true,
                            market_regime_detail: 'volatile_breakout',
                            regime_duration_bars: 8,
                            strategy_weight: 1.03,
                            calibration_version: 'signals-v2-manual-20260413T100000Z-r08',
                        },
                        {
                            strategy: 'trend_continuation',
                            source: 'ranking',
                            source_strategy: 'trend_following',
                            rank: 2,
                            ranking_score: 13.8,
                            combined_score: 16.4,
                            signal_fit_score: 5.7,
                            regime_bias: -0.4,
                            degradation_penalty: 1.8,
                            stable: false,
                            market_regime_detail: 'volatile_breakout',
                            regime_duration_bars: 8,
                            strategy_weight: 0.98,
                            calibration_version: 'signals-v2-manual-20260413T100000Z-r08',
                        },
                    ],
                    exit_levels: {
                        source: 'client',
                        atr_value: 5.2,
                        atr_multiplier: 1.85,
                        atr_multiplier_key: 'volatile_breakout',
                        atr_multiplier_source: 'client',
                        client_levels: {
                            stop_loss: 205.5,
                            take_profit_1: 229.2,
                            take_profit_2: 235.8,
                            take_profit_3: 247.1,
                        },
                        server_levels: {
                            stop_loss: 205.18,
                            take_profit_1: 222.6,
                            take_profit_2: 227.8,
                            take_profit_3: 240.8,
                        },
                    },
                    score_breakdown: {
                        base_score: 32,
                        signal_bias: 3,
                        confidence_points: 7.6,
                        probability_points: 6.4,
                        risk_reward_points: 5.2,
                        volume_bonus: 2.0,
                        trend_bonus: 1.0,
                        reversal_bonus: 0,
                        quality_bonus: 2.4,
                        stale_penalty: 0,
                        liquidity_penalty: 0.5,
                        selected_score: 79,
                    },
                },
            },
        ],
    },
    '/v1/admin/scanner/observability': {
        summary: {
            total_decisions: 14,
            emitted_decisions: 9,
            suppressed_decisions: 3,
            skipped_decisions: 2,
            total_runs: 4,
            running_runs: 1,
        },
        recent_decisions: [
            {
                id: 1,
                symbol: 'AAPL',
                signal_type: 'buy',
                decision: 'emitted',
                reason: 'Trend continuation setup confirmed.',
                score: 87,
                suppressed: false,
                dedupe_key: 'AAPL-buy-1',
                created_at: '2026-04-12T09:30:00Z',
            },
            {
                id: 2,
                symbol: 'MSFT',
                signal_type: 'buy',
                decision: 'emitted',
                reason: 'Volatility breakout confirmed.',
                score: 79,
                suppressed: false,
                dedupe_key: 'MSFT-buy-1',
                created_at: '2026-04-13T10:00:00Z',
            },
        ],
    },
    '/v1/admin/backtests/rankings/latest': {
        data: [
            {
                strategy_name: 'breakout',
                rank: 1,
                score: 1.34,
                degradation: 1.2,
                symbols_covered: 6,
                timeframe: '1d',
                top_symbols: [{ symbol: 'MSFT', score: 1.34 }],
                evidence: { stable: true, best_window_days: 90 },
            },
            {
                strategy_name: 'trend_following',
                rank: 2,
                score: 1.12,
                degradation: 0.8,
                symbols_covered: 8,
                timeframe: '1d',
                top_symbols: [{ symbol: 'AAPL', score: 1.12 }],
                evidence: { stable: true, best_window_days: 90 },
            },
        ],
    },
    '/v1/admin/analytics/strategy-health': {
        window_hours: 168,
        refreshed_at: '2026-04-13T10:05:00Z',
        strategies: [
            {
                strategy_name: 'breakout',
                rank: 1,
                score: 1.34,
                degradation: 1.2,
                symbols_covered: 6,
                signals_generated: 1,
                stable: true,
                top_symbols: [{ symbol: 'MSFT', score: 1.34 }],
                evidence: { stable: true },
            },
            {
                strategy_name: 'trend_following',
                rank: 2,
                score: 1.12,
                degradation: 0.8,
                symbols_covered: 8,
                signals_generated: 1,
                stable: true,
                top_symbols: [{ symbol: 'AAPL', score: 1.12 }],
                evidence: { stable: true },
            },
        ],
    },
    '/v1/admin/backtests/runs': {
        data: [
            {
                id: 31,
                strategy_name: 'breakout',
                symbol: 'MSFT',
                timeframe: '1d',
                window_days: 90,
                status: 'completed',
                started_at: '2026-04-13T08:00:00Z',
            },
        ],
    },
    '/v1/admin/tradingagents/analyses': {
        data: [],
    },
    '/v1/admin/calibrations/active': {
        data: {
            id: 12,
            version: 'signals-v2-feedback-20260412T093000Z-r24',
            source: 'backtest_feedback_loop',
            strategy_weights: { trend_continuation: 1.08, volatility_breakout: 1.03 },
            score_multipliers: { confidence: 1.04 },
            atr_multipliers: { trend_strong_up: 1.5, volatile_breakout: 1.85, default: 1.4 },
            derived_from: 'run-24',
            sample_size: 248,
            is_active: true,
            effective_from: '2026-04-12T09:30:00Z',
            effective_at: '2026-04-12T09:30:00Z',
            notes: 'Fixture calibration',
            created_at: '2026-04-12T09:30:00Z',
            updated_at: '2026-04-12T09:31:00Z',
        },
    },
    '/v1/admin/calibrations/proposal': {
        generated_at: '2026-04-13T10:06:00Z',
        signal_window_hours: 24,
        ranking_window_hours: 168,
        current_version: 'signals-v2-feedback-20260412T093000Z-r24',
        proposed_version: 'signals-v2-proposal-20260413',
        strategy_health_refreshed_at: '2026-04-13T10:05:00Z',
        signal_generated_after: '2026-04-12T00:00:00Z',
        summary: {
            total_signals: 2,
            total_trade_actions: 2,
            trade_action_rate: 100.0,
            executed_trade_rate: 100.0,
            overlapping_symbols: 2,
            active_calibration_version: 'signals-v2-feedback-20260412T093000Z-r24',
        },
        strategy_weights: [
            {
                key: 'trend_continuation',
                current_value: 1.08,
                proposed_value: 1.1,
                delta: 0.02,
                reasons: ['Rank 1 adds +0.04 support.'],
            },
            {
                key: 'volatility_breakout',
                current_value: 1.03,
                proposed_value: 1.01,
                delta: -0.02,
                reasons: ['Live share stays close to neutral.'],
            },
        ],
        score_multipliers: [
            {
                key: 'confidence',
                current_value: 1.04,
                proposed_value: 1.06,
                delta: 0.02,
                reasons: ['Healthy executed-trade rate allows a modest positive bias.'],
            },
            {
                key: 'quality',
                current_value: 1.0,
                proposed_value: 1.02,
                delta: 0.02,
                reasons: ['Trend-dominant conditions keep quality bias slightly positive.'],
            },
        ],
        atr_multipliers: [
            {
                key: 'trend_strong_up',
                current_value: 1.5,
                proposed_value: 1.68,
                delta: 0.18,
                reasons: ['Trend-dominant live regime gives trend exits more room.'],
            },
            {
                key: 'volatile_breakout',
                current_value: 1.85,
                proposed_value: 1.82,
                delta: -0.03,
                reasons: ['Volatile sample remains small, so breakout ATR stays close to current.'],
            },
        ],
        notes: [
            '2 live signals and 2 trade actions fed this proposal.',
            'Top strategy health ranking currently favors trend_continuation.',
        ],
        snapshot_payload: {
            version: 'signals-v2-proposal-20260413',
            source: 'proposal',
            effective_from: '2026-04-13T10:06:00Z',
            strategy_weights: { trend_continuation: 1.1, volatility_breakout: 1.01 },
            score_multipliers: { confidence: 1.06, quality: 1.02 },
            atr_multipliers: { trend_strong_up: 1.68, volatile_breakout: 1.82, range_balanced: 1.74 },
            derived_from: 'run-24; signal_results:2026-04-12T00:00:00Z',
            sample_size: 2,
            notes: 'Fixture proposal',
        },
    },
    '/v1/admin/analytics/exit-quality': {
        window_hours: 168,
        generated_after: '2026-04-06T00:00:00Z',
        total_signals: 2,
        exits_available: 2,
        calibrated_exit_count: 1,
        client_exit_count: 1,
        avg_risk_reward_ratio: 2.6,
        avg_atr_multiplier: 1.68,
        avg_stop_distance_pct: 4.23,
        avg_tp1_distance_pct: 8.77,
        exit_sources: [
            { key: 'client', count: 1 },
            { key: 'server_default', count: 1 },
        ],
        atr_multiplier_sources: [
            { key: 'calibration_snapshot', count: 1 },
            { key: 'client', count: 1 },
        ],
        market_regimes: [
            { key: 'trend_strong_up', count: 1 },
            { key: 'volatile_breakout', count: 1 },
        ],
        top_symbols: [
            { key: 'AAPL', count: 1 },
            { key: 'MSFT', count: 1 },
        ],
    },
};

const publicPayloads = {
    '/v1/signals/101/strategy-breakdown': {
        signal_id: 101,
        symbol: 'AAPL',
        signal_type: 'buy',
        strategy_window: '1d',
        market_regime: 'trend',
        market_regime_detail: 'trend_strong_up',
        regime_duration_bars: 15,
        regime_metrics: { trend_strength: 0.92, momentum_score: 0.88 },
        regime_reasons: ['strong-trend-threshold', 'volume-confirmed'],
        calibration_version: 'signals-v2-feedback-20260412T093000Z-r24',
        calibration_source: 'backtest_feedback_loop',
        calibration_effective_from: '2026-04-12T09:30:00Z',
        selected_strategy: 'trend_continuation',
        selection_source: 'ranking',
        source_strategy: 'trend_following',
        selected_candidate: {
            strategy: 'trend_continuation',
            source: 'ranking',
            source_strategy: 'trend_following',
            rank: 1,
            ranking_score: 18.2,
            combined_score: 24.1,
            signal_fit_score: 8.1,
            regime_bias: 3.0,
            degradation_penalty: 0.2,
            stable: true,
            market_regime_detail: 'trend_strong_up',
            regime_duration_bars: 15,
            strategy_weight: 1.08,
            calibration_version: 'signals-v2-feedback-20260412T093000Z-r24',
        },
        candidates: adminPayloads['/v1/admin/signal-stats'].data[0].indicators.strategy_candidates,
        alert_decision: {
            publish_allowed: true,
            suppressed_reasons: [],
        },
        generated_at: '2026-04-12T09:30:00Z',
    },
    '/v1/signals/102/strategy-breakdown': {
        signal_id: 102,
        symbol: 'MSFT',
        signal_type: 'buy',
        strategy_window: '1d',
        market_regime: 'volatile',
        market_regime_detail: 'volatile_breakout',
        regime_duration_bars: 8,
        regime_metrics: { volatility_score: 0.91, momentum_score: 0.63 },
        regime_reasons: ['volatility-expansion', 'breakout-follow-through'],
        calibration_version: 'signals-v2-manual-20260413T100000Z-r08',
        calibration_source: 'manual_review',
        calibration_effective_from: '2026-04-13T10:00:00Z',
        selected_strategy: 'volatility_breakout',
        selection_source: 'ranking',
        source_strategy: 'breakout',
        selected_candidate: {
            strategy: 'volatility_breakout',
            source: 'ranking',
            source_strategy: 'breakout',
            rank: 1,
            ranking_score: 17.4,
            combined_score: 22.2,
            signal_fit_score: 7.2,
            regime_bias: 3.5,
            degradation_penalty: 0.6,
            stable: true,
            market_regime_detail: 'volatile_breakout',
            regime_duration_bars: 8,
            strategy_weight: 1.03,
            calibration_version: 'signals-v2-manual-20260413T100000Z-r08',
        },
        candidates: adminPayloads['/v1/admin/signal-stats'].data[1].indicators.strategy_candidates,
        alert_decision: {
            publish_allowed: true,
            suppressed_reasons: [],
        },
        generated_at: '2026-04-13T10:00:00Z',
    },
};

function jsonResponse(route, payload) {
    return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(payload),
    });
}

function resolveAdminPayload(url) {
    if (url.pathname === '/v1/admin/backtests/equity-curve') {
        const symbol = String(url.searchParams.get('symbol') || '').trim().toUpperCase();
        if (symbol === 'MSFT') {
            return {
                symbol: 'MSFT',
                strategy_name: 'breakout',
                timeframe: '1d',
                window_days: 90,
                metrics: {
                    total_return_percent: 8.6,
                    max_drawdown_percent: 4.9,
                    trade_count: 2,
                    win_rate: 50.0,
                    avg_trade_return_percent: 4.3,
                    sharpe_ratio: 0.91,
                    samples: 40,
                },
                trades: [
                    { entry_index: 20, exit_index: 28, entry_price: 214.8, exit_price: 228.1, return_percent: 6.19 },
                    { entry_index: 31, exit_index: 39, entry_price: 229.4, exit_price: 234.7, return_percent: 2.31 },
                ],
                equity_points: [1.0, 1.02, 1.01, 1.05, 1.086],
                equity_series: buildEquitySeries([1.0, 1.02, 1.01, 1.05, 1.086], 14),
            };
        }
        return {
            symbol: 'AAPL',
            strategy_name: 'trend_following',
            timeframe: '1d',
            window_days: 90,
            metrics: {
                total_return_percent: 14.2,
                max_drawdown_percent: 3.8,
                trade_count: 3,
                win_rate: 66.7,
                avg_trade_return_percent: 4.73,
                sharpe_ratio: 1.24,
                samples: 40,
            },
            trades: [
                { entry_index: 20, exit_index: 26, entry_price: 102.25, exit_price: 108.9, return_percent: 6.5 },
                { entry_index: 28, exit_index: 33, entry_price: 109.2, exit_price: 114.0, return_percent: 4.4 },
                { entry_index: 35, exit_index: 39, entry_price: 114.3, exit_price: 118.2, return_percent: 3.4 },
            ],
            equity_points: [1.0, 1.03, 1.07, 1.11, 1.142],
            equity_series: buildEquitySeries([1.0, 1.03, 1.07, 1.11, 1.142], 10),
        };
    }
    const payload = adminPayloads[url.pathname];
    if (!payload) {
        throw new Error(`Unhandled admin request: ${url.pathname}`);
    }
    return payload;
}

function resolvePublicPayload(url) {
    if (url.pathname.startsWith('/v1/market/chart/AAPL')) {
        return {
            symbol: 'AAPL',
            asset_type: 'stock',
            source: 'fixture.market',
            period: url.searchParams.get('period') || '3mo',
            bars: buildBars(95),
            quote: {
                latest_close: 122.4,
                change_pct: 2.31,
                session_high: 123.1,
                session_low: 118.2,
                session_volume: 5_480_000,
            },
        };
    }
    if (url.pathname.startsWith('/v1/market/chart/MSFT')) {
        return {
            symbol: 'MSFT',
            asset_type: 'stock',
            source: 'fixture.market',
            period: url.searchParams.get('period') || '3mo',
            bars: buildBars(206),
            quote: {
                latest_close: 247.1,
                change_pct: 1.87,
                session_high: 248.4,
                session_low: 238.7,
                session_volume: 4_160_000,
            },
        };
    }
    const payload = publicPayloads[url.pathname];
    if (!payload) {
        throw new Error(`Unhandled public request: ${url.pathname}`);
    }
    return payload;
}

test.beforeEach(async ({ page }) => {
    await page.route(`${ADMIN_BASE_URL}/**`, async (route) => {
        const url = new URL(route.request().url());
        if (route.request().method() === 'POST' && url.pathname === '/v1/admin/calibrations/proposal/apply') {
            await jsonResponse(route, appliedCalibrationSnapshot);
            return;
        }
        await jsonResponse(route, resolveAdminPayload(url));
    });

    await page.route(`${PUBLIC_BASE_URL}/**`, async (route) => {
        const url = new URL(route.request().url());
        await jsonResponse(route, resolvePublicPayload(url));
    });
});

test('renders strategy breakdown, calibration telemetry, and exit-quality widgets', async ({ page }) => {
    await page.goto(PLATFORM_URL, { waitUntil: 'networkidle' });

    await expect(page.locator('#backtest-panel')).toContainText('Strategy Breakdown');
    await expect(page.locator('#backtest-panel')).toContainText('Equity Curve');
    await expect(page.locator('#backtest-panel')).toContainText('Total Return');
    await expect(page.locator('#backtest-panel')).toContainText('14.20%');
    await expect(page.locator('#backtest-panel')).toContainText('Calibration Proposal');
    await expect(page.locator('#backtest-panel')).toContainText('AAPL · 趋势延续');
    await expect(page.locator('#backtest-panel')).toContainText('signals-v2-feedback-20260412T093000Z-r24 → signals-v2-proposal-20260413');
    await expect(page.locator('#exit-desk-panel')).toContainText('Calibration Snapshot');
    await expect(page.locator('#exit-desk-panel')).toContainText('反馈闭环');
    await expect(page.locator('#exit-desk-panel')).toContainText('Client vs Server Exits');
    await expect(page.locator('#health-panel')).toContainText('退出位读模型');
    await expect(page.locator('#health-panel')).toContainText('AAPL · 1');
});

test('applies the reviewed calibration proposal from the platform workbench', async ({ page }) => {
    await page.goto(PLATFORM_URL, { waitUntil: 'networkidle' });

    await page.getByRole('button', { name: '研究台', exact: true }).click();
    await page.locator('#calibration-proposal-apply-button').scrollIntoViewIfNeeded();
    await page.locator('#calibration-proposal-apply-button').click();

    await expect(page.locator('#backtest-panel')).toContainText('已创建并激活校准快照 signals-v2-proposal-20260413');
});

test('refreshes selected strategy breakdown when the focused signal changes', async ({ page }) => {
    await page.goto(PLATFORM_URL, { waitUntil: 'networkidle' });

    await page.locator('#watchlist-panel').getByRole('button', { name: /MSFT/ }).click();

    await expect(page.locator('#backtest-panel')).toContainText('MSFT · 波动突破');
    await expect(page.locator('#backtest-panel')).toContainText('8.60%');
    await expect(page.locator('#backtest-panel')).toContainText('生效 2026-04-13 10:00:00');
    await expect(page.locator('#exit-desk-panel')).toContainText('高波动突破');
    await expect(page.locator('#exit-desk-panel')).toContainText('手动校准');
    await expect(page.locator('#health-panel')).toContainText('MSFT · 1');
});