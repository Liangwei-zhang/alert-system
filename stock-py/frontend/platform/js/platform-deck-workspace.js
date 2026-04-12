function createPlatformDeckWorkspaceState() {
    return {
        workspaceMode: 'overview',
        activeDesktopSectionId: 'trading-agents-panel',
        desktopObserver: null,
        commandPaletteOpen: false,
        commandPaletteQuery: '',
        commandPaletteActiveIndex: 0,
        executionContextSource: '',
        executionContextUpdatedAt: '',
        workspacePinned: false,
        workspaceAutoRouted: false,
    };
}

function createPlatformDeckWorkspaceModule() {
    return {
        normalizeWorkspaceMode(value) {
            const normalized = String(value || '').trim().toLowerCase();
            if (this.workspaceModes.some((item) => item.key === normalized)) {
                return normalized;
            }
            return 'overview';
        },

        setWorkspaceMode(mode, options = {}) {
            const preserveScroll = Boolean(options.preserveScroll);
            const userInitiated = options.userInitiated !== false;
            this.workspaceMode = this.normalizeWorkspaceMode(mode);
            localStorage.setItem(this.storageKeys.workspaceMode, this.workspaceMode);
            if (userInitiated) {
                this.workspacePinned = true;
            }
            this.ensureActiveSectionVisible();
            if (!preserveScroll) {
                this.$nextTick(() => {
                    const element = document.getElementById(this.activeDesktopSectionId);
                    if (element) {
                        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                });
            }
        },

        setActiveDesktopSection(sectionId, options = {}) {
            const userInitiated = options.userInitiated !== false;
            this.activeDesktopSectionId = String(sectionId || '').trim() || 'trading-agents-panel';
            localStorage.setItem(this.storageKeys.workspaceSection, this.activeDesktopSectionId);
            if (userInitiated) {
                {
                    id: 'open-market-workbench',
                    group: '动作',
                    label: '打开市场工作台',
                    meta: this.marketChart && this.marketChart.symbol
                        ? `${this.marketChart.symbol} · 查看图表与报价快照。`
                        : '搜索标的、查看图表并整理桌面盯盘。',
                    hint: '信号',
                    search: 'market chart watchlist search 市场 图表 盯盘',
                    run: () => this.focusSection('market-workbench-panel', 'signals')
                this.workspacePinned = true;
            }
        },

        focusSymbol(symbol, options = {}) {
            const normalizedSymbol = String(symbol || '').trim().toUpperCase();
            if (!normalizedSymbol) {
                return;
            }
            this.selectedSymbol = normalizedSymbol;
            this.executionContextSource = String(options.source || this.executionContextSource || 'workspace').trim() || 'workspace';
            this.executionContextUpdatedAt = new Date().toISOString();
            if (typeof this.loadSelectedMarketChart === 'function') {
                this.loadSelectedMarketChart({ silent: true, throwOnError: false });
            }
            if (options.sectionId || options.mode) {
                this.focusSection(options.sectionId || 'decision-tape-panel', options.mode || null, {
                    userInitiated: options.userInitiated !== false,
                });
            }
        },

        findWatchlistSignal(symbol) {
            const normalizedSymbol = String(symbol || '').trim().toUpperCase();
            if (!normalizedSymbol) {
                return null;
            }
            return this.watchlist.find((item) => item.symbol === normalizedSymbol) || null;
        },

        latestDecisionForSymbol(symbol = this.selectedSymbol) {
            const normalizedSymbol = String(symbol || '').trim().toUpperCase();
            if (!normalizedSymbol) {
                return null;
            }
            return this.signalTape.find((item) => item.symbol === normalizedSymbol) || null;
        },

        executionContextSourceLabel(source = this.executionContextSource) {
            const normalized = String(source || '').trim().toLowerCase();
            const mapping = {
                'auto-sync': '自动聚焦',
                watchlist: '盯盘雷达',
                'market-workbench': '市场工作台',
                'decision-tape': '判定流',
                'command-palette': '命令面板',
                'quick-action': '快捷动作',
                'workspace-relay': '工作区接力',
                'execution-handoff': '执行接力',
                'research-handoff': '研究接力',
                workspace: '桌面工作台'
            };
            return mapping[normalized] || '桌面工作台';
        },

        focusDesktopAccess(targetRef = '') {
            const accessPanel = document.getElementById('desktop-access-panel');
            if (accessPanel) {
                accessPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
            this.$nextTick(() => {
                if (!targetRef || !this.$refs) {
                    return;
                }
                const element = this.$refs[targetRef];
                if (element && typeof element.focus === 'function') {
                    element.focus();
                    if (typeof element.select === 'function') {
                        element.select();
                    }
                }
            });
        },

        mergeCsvFront(existingValue, nextValue) {
            const normalizedNextValue = String(nextValue || '').trim();
            const existingValues = this.parseCsvStrings(existingValue);
            if (!normalizedNextValue) {
                return existingValues.join(', ');
            }

            const seen = new Set([normalizedNextValue.toLowerCase()]);
            const merged = [normalizedNextValue];
            existingValues.forEach((item) => {
                const normalizedItem = String(item || '').trim();
                if (!normalizedItem) {
                    return;
                }
                const key = normalizedItem.toLowerCase();
                if (seen.has(key)) {
                    return;
                }
                seen.add(key);
                merged.push(normalizedItem);
            });
            return merged.join(', ');
        },

        mergeCsvIntsFront(existingValue, nextValues) {
            const candidates = Array.isArray(nextValues) ? nextValues : [nextValues];
            const normalizedNewValues = candidates
                .map((item) => Number.parseInt(String(item || '').trim(), 10))
                .filter((item) => Number.isFinite(item) && item > 0);
            const existingValues = this.parseCsvInts(existingValue);

            if (!normalizedNewValues.length) {
                return existingValues.join(',');
            }

            const seen = new Set(normalizedNewValues);
            const merged = [...normalizedNewValues];
            existingValues.forEach((item) => {
                if (seen.has(item)) {
                    return;
                }
                seen.add(item);
                merged.push(item);
            });
            return merged.join(',');
        },

        backtestPresetStatus(symbol = this.selectedSymbol) {
            const normalizedSymbol = String(symbol || '').trim().toUpperCase();
            if (!normalizedSymbol) {
                return '回测待预填';
            }

            const signal = this.findWatchlistSignal(normalizedSymbol);
            const symbolReady = this.parseCsvStrings(this.runForm.symbols)
                .map((item) => item.toUpperCase())
                .includes(normalizedSymbol);
            const strategyReady = !signal || !signal.strategyCode || signal.strategyCode === 'unknown'
                ? true
                : this.parseCsvStrings(this.runForm.strategyNames)
                    .map((item) => item.toLowerCase())
                    .includes(String(signal.strategyCode).toLowerCase());

            if (symbolReady && strategyReady) {
                return `回测已带入 ${normalizedSymbol}`;
            }
            return `回测待带入 ${normalizedSymbol}`;
        },

        tradingAgentsPresetStatus(symbol = this.selectedSymbol) {
            const normalizedSymbol = String(symbol || '').trim().toUpperCase();
            if (!normalizedSymbol) {
                return 'TradingAgents 待预填';
            }

            const ticker = String(this.tradingAgentsDraft.ticker || '').trim().toUpperCase();
            if (ticker === normalizedSymbol) {
                const triggerType = String(this.tradingAgentsDraft.triggerType || 'manual').trim().toLowerCase();
                return `TradingAgents 已带入 ${normalizedSymbol} · ${triggerType}`;
            }
            return `TradingAgents 待带入 ${normalizedSymbol}`;
        },

        selectedBacktestRuns(limit = 4, symbol = this.selectedSymbol) {
            const normalizedSymbol = String(symbol || '').trim().toUpperCase();
            if (!normalizedSymbol) {
                return [];
            }
            return this.backtestRuns
                .filter((item) => String(item.symbol || '').trim().toUpperCase() === normalizedSymbol)
                .slice(0, limit);
        },

        selectedTradingAgentsRuns(limit = 4, symbol = this.selectedSymbol) {
            const normalizedSymbol = String(symbol || '').trim().toUpperCase();
            if (!normalizedSymbol) {
                return [];
            }
            return this.tradingAgentsRuns
                .filter((item) => String(item.ticker || '').trim().toUpperCase() === normalizedSymbol)
                .slice(0, limit);
        },

        selectedDecisionStats(symbol = this.selectedSymbol) {
            const normalizedSymbol = String(symbol || '').trim().toUpperCase();
            if (!normalizedSymbol) {
                return {
                    total: 0,
                    emitted: 0,
                    suppressed: 0,
                    latest: null,
                };
            }
            const decisions = this.signalTape.filter((item) => item.symbol === normalizedSymbol);
            return {
                total: decisions.length,
                emitted: decisions.filter((item) => !item.suppressed).length,
                suppressed: decisions.filter((item) => Boolean(item.suppressed)).length,
                latest: decisions[0] || null,
            };
        },

        selectedExecutionSummary(symbol = this.selectedSymbol) {
            const signal = this.findWatchlistSignal(symbol);
            if (!signal) {
                return null;
            }
            const stats = this.selectedDecisionStats(signal.symbol);
            const backtests = this.selectedBacktestRuns(12, signal.symbol);
            const analyses = this.selectedTradingAgentsRuns(12, signal.symbol);
            const latestAnalysis = analyses[0] || null;
            return {
                symbol: signal.symbol,
                strategy: signal.strategy,
                statusLabel: this.statusLabel(signal.status),
                decisionCount: stats.total,
                emittedCount: stats.emitted,
                suppressedCount: stats.suppressed,
                backtestCount: backtests.length,
                tradingAgentsCount: analyses.length,
                latestAnalysisLabel: latestAnalysis ? this.tradingAgentsStatusLabel(latestAnalysis.status) : '未提交',
            };
        },

        executionStatusClass(status, kind = 'backtest') {
            if (kind === 'tradingagents') {
                return this.tradingAgentsStatusClass(status);
            }
            const normalized = String(status || '').trim().toLowerCase();
            if (normalized === 'completed') {
                return 'bg-mint/15 text-mint';
            }
            if (normalized === 'failed') {
                return 'bg-coral/15 text-coral';
            }
            if (normalized === 'pending' || normalized === 'running') {
                return 'bg-sun/15 text-sun';
            }
            return 'bg-ink/10 text-ink/70';
        },

        executionItemTimestamp(item) {
            const candidates = item && item.kind === 'tradingagents'
                ? [item.updated_at, item.completed_at, item.submitted_at, item.analysis_date]
                : [item.completed_at, item.started_at];
            for (const candidate of candidates) {
                if (!candidate) {
                    continue;
                }
                const parsed = new Date(candidate);
                if (!Number.isNaN(parsed.getTime())) {
                    return parsed.getTime();
                }
            }
            return 0;
        },

        selectedExecutionItems(limit = 6, symbol = this.selectedSymbol) {
            const backtests = this.selectedBacktestRuns(limit, symbol).map((item) => ({
                id: `backtest-${item.id}`,
                kind: 'backtest',
                title: this.strategyLabel(item.strategy_name),
                meta: `${item.symbol || '--'} · ${item.timeframe || '--'} · ${this.formatInt(item.window_days)}d`,
                detail: `${item.experiment_name || '回测运行'} · ID ${item.id}`,
                status: String(item.status || ''),
                statusLabel: String(item.status || '--'),
                timestampLabel: this.formatDateTime(item.completed_at || item.started_at),
                raw: item,
            }));
            const analyses = this.selectedTradingAgentsRuns(limit, symbol).map((item) => ({
                id: `ta-${item.request_id}`,
                kind: 'tradingagents',
                title: item.final_action
                    ? `TradingAgents · ${this.tradingAgentsActionLabel(item.final_action)}`
                    : 'TradingAgents · 研究任务',
                meta: `${item.ticker || '--'} · ${item.trigger_type || 'manual'} · poll ${this.formatInt(item.poll_count || 0)}`,
                detail: item.request_id,
                status: String(item.status || ''),
                statusLabel: this.tradingAgentsStatusLabel(item.status),
                timestampLabel: this.formatDateTime(item.updated_at || item.submitted_at || item.analysis_date),
                raw: item,
            }));

            return [...analyses, ...backtests]
                .sort((left, right) => this.executionItemTimestamp(right.raw) - this.executionItemTimestamp(left.raw))
                .slice(0, limit);
        },

        focusedConsoleLines(limit = 8, symbol = this.selectedSymbol) {
            const normalizedSymbol = String(symbol || '').trim().toUpperCase();
            if (!normalizedSymbol) {
                return this.consoleLines.slice(0, limit);
            }
            return this.consoleLines
                .filter((item) => String(item.text || '').toUpperCase().includes(normalizedSymbol))
                .slice(0, limit);
        },

        selectedFunnelCards(symbol = this.selectedSymbol) {
            const signal = this.findWatchlistSignal(symbol);
            if (!signal) {
                return [];
            }
            const stats = this.selectedDecisionStats(signal.symbol);
            const backtests = this.selectedBacktestRuns(12, signal.symbol);
            const analyses = this.selectedTradingAgentsRuns(12, signal.symbol);
            const latestBacktest = backtests[0] || null;
            const latestAnalysis = analyses[0] || null;
            const relayReady = Boolean(
                this.executionContextUpdatedAt
                && String(signal.symbol || '').trim().toUpperCase() === String(this.selectedSymbol || '').trim().toUpperCase()
            );

            return [
                {
                    id: 'watch',
                    label: '盯盘',
                    value: this.statusLabel(signal.status),
                    meta: signal.strategy,
                    className: 'bg-tide/10 text-tide'
                },
                {
                    id: 'decision',
                    label: '判定',
                    value: `${this.formatInt(stats.total)} 条`,
                    meta: stats.total
                        ? `发射 ${this.formatInt(stats.emitted)} · 抑制 ${this.formatInt(stats.suppressed)}`
                        : '暂无判定记录',
                    className: stats.emitted
                        ? 'bg-mint/15 text-mint'
                        : (stats.suppressed ? 'bg-coral/15 text-coral' : 'bg-ink/10 text-ink/70')
                },
                {
                    id: 'relay',
                    label: '接力',
                    value: relayReady ? this.executionContextSourceLabel() : '待接力',
                    meta: relayReady ? `更新 ${this.formatTime(this.executionContextUpdatedAt)}` : '等待进入执行或研究台',
                    className: relayReady ? 'bg-coral/15 text-coral' : 'bg-ink/10 text-ink/70'
                },
                {
                    id: 'backtest',
                    label: '回测',
                    value: backtests.length ? `${this.formatInt(backtests.length)} 次` : '0 次',
                    meta: latestBacktest
                        ? `${this.strategyLabel(latestBacktest.strategy_name)} · ${String(latestBacktest.status || '--')}`
                        : this.backtestPresetStatus(signal.symbol),
                    className: latestBacktest
                        ? this.executionStatusClass(latestBacktest.status, 'backtest')
                        : 'bg-ink/10 text-ink/70'
                },
                {
                    id: 'tradingagents',
                    label: 'TradingAgents',
                    value: analyses.length ? `${this.formatInt(analyses.length)} 条` : '0 条',
                    meta: latestAnalysis
                        ? `${this.tradingAgentsStatusLabel(latestAnalysis.status)} · ${latestAnalysis.final_action ? this.tradingAgentsActionLabel(latestAnalysis.final_action) : '等待动作'}`
                        : this.tradingAgentsPresetStatus(signal.symbol),
                    className: latestAnalysis
                        ? this.executionStatusClass(latestAnalysis.status, 'tradingagents')
                        : 'bg-ink/10 text-ink/70'
                }
            ];
        },

        selectedStrategyCode() {
            const selected = this.selectedSignal();
            const strategyCode = String(selected && selected.strategyCode ? selected.strategyCode : '').trim().toLowerCase();
            if (!strategyCode || strategyCode === 'unknown') {
                return '';
            }
            return strategyCode;
        },

        strategyMatchesFocused(strategyName) {
            const focusedStrategy = this.selectedStrategyCode();
            if (!focusedStrategy) {
                return false;
            }
            return String(strategyName || '').trim().toLowerCase() === focusedStrategy;
        },

        extractSymbolList(entries, limit = 0) {
            const rows = Array.isArray(entries) ? entries : [];
            const values = [];
            const seen = new Set();

            rows.forEach((entry) => {
                const candidate = typeof entry === 'string'
                    ? entry
                    : (entry && typeof entry === 'object'
                        ? (entry.symbol || entry.ticker || entry.code || '')
                        : '');
                const normalized = String(candidate || '').trim().toUpperCase();
                if (!normalized || seen.has(normalized)) {
                    return;
                }
                seen.add(normalized);
                values.push(normalized);
            });

            return limit > 0 ? values.slice(0, limit) : values;
        },

        rankingEvidence(item) {
            if (item && item.evidence && typeof item.evidence === 'object' && !Array.isArray(item.evidence)) {
                return item.evidence;
            }
            return {};
        },

        rankingTopSymbols(item, limit = 4) {
            const evidence = this.rankingEvidence(item);
            const values = [];
            const seen = new Set();
            const pushSymbols = (symbols) => {
                this.extractSymbolList(symbols).forEach((symbol) => {
                    if (seen.has(symbol)) {
                        return;
                    }
                    seen.add(symbol);
                    values.push(symbol);
                });
            };

            pushSymbols(evidence.top_symbols);
            if (evidence.windows && typeof evidence.windows === 'object') {
                Object.values(evidence.windows).forEach((windowPayload) => {
                    if (!windowPayload || typeof windowPayload !== 'object') {
                        return;
                    }
                    pushSymbols(windowPayload.top_symbols);
                });
            }

            return limit > 0 ? values.slice(0, limit) : values;
        },

        healthTopSymbols(item, limit = 4) {
            return this.extractSymbolList(item && item.top_symbols, limit);
        },

        topSymbolsLabel(entries, limit = 3) {
            const symbols = Array.isArray(entries) ? entries : this.extractSymbolList(entries);
            if (!symbols.length) {
                return '无重点标的';
            }
            const visible = symbols.slice(0, limit).join(', ');
            return symbols.length > limit ? `${visible}, ...` : visible;
        },

        rankingMentionsSymbol(item, symbol = this.selectedSymbol) {
            const normalizedSymbol = String(symbol || '').trim().toUpperCase();
            if (!normalizedSymbol) {
                return false;
            }
            return this.rankingTopSymbols(item, 12).includes(normalizedSymbol);
        },

        healthMentionsSymbol(item, symbol = this.selectedSymbol) {
            const normalizedSymbol = String(symbol || '').trim().toUpperCase();
            if (!normalizedSymbol) {
                return false;
            }
            return this.healthTopSymbols(item, 12).includes(normalizedSymbol);
        },

        rankingBestWindowLabel(item) {
            const evidence = this.rankingEvidence(item);
            return evidence.best_window_days ? `${this.formatInt(evidence.best_window_days)}d` : '--';
        },

        rankingBestWindowDays(item) {
            const evidence = this.rankingEvidence(item);
            const value = Number.parseInt(String(evidence.best_window_days || '').trim(), 10);
            return Number.isFinite(value) && value > 0 ? value : 0;
        },

        rankingStabilityLabel(item) {
            const evidence = this.rankingEvidence(item);
            if (typeof evidence.stable === 'boolean') {
                return evidence.stable ? '稳定' : '波动';
            }
            if (!item) {
                return '--';
            }
            return item.degradation < 5 ? '稳定' : '波动';
        },

        researchRankingPriority(item) {
            let score = 0;
            if (this.strategyMatchesFocused(item && item.strategy_name)) {
                score += 4;
            }
            if (this.rankingMentionsSymbol(item)) {
                score += 2;
            }
            const evidence = this.rankingEvidence(item);
            if (evidence.stable === true) {
                score += 1;
            }
            return score;
        },

        researchHealthPriority(item) {
            let score = 0;
            if (this.strategyMatchesFocused(item && item.strategy_name)) {
                score += 4;
            }
            if (this.healthMentionsSymbol(item)) {
                score += 2;
            }
            if (item && item.stable) {
                score += 1;
            }
            return score;
        },

        researchRankingItems() {
            return [...this.rankings].sort((left, right) => {
                const delta = this.researchRankingPriority(right) - this.researchRankingPriority(left);
                if (delta !== 0) {
                    return delta;
                }
                return Number(left.rank || 0) - Number(right.rank || 0);
            });
        },

        researchHealthItems() {
            return [...this.strategyHealth].sort((left, right) => {
                const delta = this.researchHealthPriority(right) - this.researchHealthPriority(left);
                if (delta !== 0) {
                    return delta;
                }
                return Number(left.rank || 0) - Number(right.rank || 0);
            });
        },

        researchRankingCardClass(item) {
            if (this.strategyMatchesFocused(item && item.strategy_name)) {
                return 'ring-2 ring-sun/30 border-sun/25 bg-sun/5';
            }
            if (this.rankingMentionsSymbol(item)) {
                return 'ring-2 ring-coral/25 border-coral/20 bg-coral/5';
            }
            return '';
        },

        researchHealthCardClass(item) {
            if (this.strategyMatchesFocused(item && item.strategy_name)) {
                return 'ring-2 ring-sun/30 border-sun/25 bg-sun/5';
            }
            if (this.healthMentionsSymbol(item)) {
                return 'ring-2 ring-coral/25 border-coral/20 bg-coral/5';
            }
            return '';
        },

        selectedResearchSummary() {
            const selected = this.selectedSignal();
            if (!selected) {
                return null;
            }

            const rankingMatch = this.researchRankingItems().find((item) => (
                this.strategyMatchesFocused(item && item.strategy_name)
                || this.rankingMentionsSymbol(item, selected.symbol)
            )) || null;
            const healthMatch = this.researchHealthItems().find((item) => (
                this.strategyMatchesFocused(item && item.strategy_name)
                || this.healthMentionsSymbol(item, selected.symbol)
            )) || null;
            const topSymbols = healthMatch
                ? this.healthTopSymbols(healthMatch)
                : this.rankingTopSymbols(rankingMatch);

            return {
                symbol: selected.symbol,
                strategyLabel: selected.strategy,
                signalStatus: this.statusLabel(selected.status),
                backtestStatus: this.backtestPresetStatus(selected.symbol),
                rankingMatch,
                healthMatch,
                bestWindowLabel: this.rankingBestWindowLabel(rankingMatch),
                stabilityLabel: healthMatch
                    ? (healthMatch.stable ? '稳定' : '待复核')
                    : this.rankingStabilityLabel(rankingMatch),
                topSymbolsLabel: this.topSymbolsLabel(topSymbols),
                symbolHit: Boolean(
                    (rankingMatch && this.rankingMentionsSymbol(rankingMatch, selected.symbol))
                    || (healthMatch && this.healthMentionsSymbol(healthMatch, selected.symbol))
                )
            };
        },

        rankingPresetApplied(item) {
            if (!item) {
                return false;
            }
            const strategyName = String(item.strategy_name || '').trim().toLowerCase();
            const bestWindow = this.rankingBestWindowDays(item);
            const strategies = this.parseCsvStrings(this.runForm.strategyNames).map((entry) => entry.toLowerCase());
            const windows = this.parseCsvInts(this.runForm.windows);

            if (!strategyName || !strategies.includes(strategyName)) {
                return false;
            }
            if (bestWindow && !windows.includes(bestWindow)) {
                return false;
            }

            const selected = this.selectedSignal();
            if (!selected) {
                return true;
            }

            const symbols = this.parseCsvStrings(this.runForm.symbols).map((entry) => entry.toUpperCase());
            if (symbols.includes(selected.symbol)) {
                return true;
            }
            return this.rankingTopSymbols(item, 12).some((symbol) => symbols.includes(symbol));
        },

        applyRankingBacktestPreset(item, options = {}) {
            if (!item) {
                return false;
            }

            const strategyName = String(item.strategy_name || '').trim().toLowerCase();
            const bestWindow = this.rankingBestWindowDays(item);
            const selected = this.selectedSignal();
            const selectedSymbol = selected ? selected.symbol : '';
            const focusedSymbolMatches = selectedSymbol && (
                this.strategyMatchesFocused(strategyName)
                || this.rankingMentionsSymbol(item, selectedSymbol)
            );
            const candidateSymbols = focusedSymbolMatches
                ? [selectedSymbol]
                : this.rankingTopSymbols(item, options.symbolLimit || 3);

            if (strategyName) {
                this.runForm.strategyNames = this.mergeCsvFront(this.runForm.strategyNames, strategyName);
            }
            if (bestWindow) {
                this.runForm.windows = this.mergeCsvIntsFront(this.runForm.windows, [bestWindow]);
            }
            candidateSymbols.forEach((symbol) => {
                this.runForm.symbols = this.mergeCsvFront(this.runForm.symbols, symbol);
            });

            if (options.focus !== false) {
                this.focusSection('backtest-panel', 'research');
            }

            if (options.announce !== false) {
                const windowLabel = bestWindow ? `${bestWindow}d` : '--';
                const symbolLabel = candidateSymbols.length ? candidateSymbols.join(', ') : '当前候选标的';
                this.announceWorkflowRelay(`已将 ${this.strategyLabel(strategyName || 'unknown')} 的最佳窗口 ${windowLabel} 带入回测表单，标的 ${symbolLabel}。`);
            }

            return true;
        },

        applySelectedResearchPreset() {
            const summary = this.selectedResearchSummary();
            if (!summary || !summary.rankingMatch) {
                return false;
            }
            return this.applyRankingBacktestPreset(summary.rankingMatch, {
                focus: true,
                announce: true,
                symbolLimit: 3
            });
        },

        focusSelectedStrategyHealth(options = {}) {
            const selected = this.selectedSignal();
            if (!selected) {
                return false;
            }
            this.focusSymbol(selected.symbol, { source: 'research-handoff' });
            this.focusSection('health-panel', 'research');
            if (options.announce !== false) {
                this.announceWorkflowRelay(`已将 ${selected.symbol} 带到策略健康视图。`);
            }
            return true;
        },

        announceWorkflowRelay(message) {
            this.statusMessage = message;
            this.statusType = 'info';
            this.log('info', message);
        },

        resolveTradingAgentsTriggerType(source = this.executionContextSource) {
            const normalized = String(source || '').trim().toLowerCase();
            if (!normalized) {
                return 'position_review';
            }
            if (normalized.includes('watchlist') || normalized.includes('decision') || normalized.includes('scanner')) {
                return 'scanner';
            }
            if (normalized.includes('command')) {
                return 'manual';
            }
            return 'position_review';
        },

        primeBacktestForSymbol(symbol = this.selectedSymbol, options = {}) {
            const signal = this.findWatchlistSignal(symbol);
            if (!signal) {
                return false;
            }

            this.focusSymbol(signal.symbol, { source: options.source || 'research-handoff' });
            this.runForm.symbols = this.mergeCsvFront(this.runForm.symbols, signal.symbol);
            if (signal.strategyCode && signal.strategyCode !== 'unknown') {
                this.runForm.strategyNames = this.mergeCsvFront(this.runForm.strategyNames, signal.strategyCode);
            }
            if (options.focus !== false) {
                this.focusSection('backtest-panel', 'research');
            }
            if (options.announce) {
                this.announceWorkflowRelay(`已将 ${signal.symbol} 带入回测上下文。`);
            }
            return true;
        },

        primeTradingAgentsForSymbol(symbol = this.selectedSymbol, options = {}) {
            const signal = this.findWatchlistSignal(symbol);
            if (!signal) {
                return false;
            }

            const source = options.source || 'research-handoff';
            this.focusSymbol(signal.symbol, { source });
            this.tradingAgentsDraft.ticker = signal.symbol;
            this.tradingAgentsDraft.triggerType = options.triggerType || this.resolveTradingAgentsTriggerType(source);
            this.tradingAgentsDraft.source = 'platform-desk';
            if (options.focus !== false) {
                this.focusSection('trading-agents-panel', 'research');
            }
            if (options.announce) {
                this.announceWorkflowRelay(`已将 ${signal.symbol} 带入 TradingAgents 草稿。`);
            }
            return true;
        },

        handoffToExecution(symbol = this.selectedSymbol, options = {}) {
            const signal = this.findWatchlistSignal(symbol);
            if (!signal) {
                return false;
            }

            this.focusSymbol(signal.symbol, {
                source: options.source || 'execution-handoff',
                sectionId: 'exit-desk-panel',
                mode: 'execution'
            });
            if (options.announce) {
                this.announceWorkflowRelay(`已将 ${signal.symbol} 带到执行台。`);
            }
            return true;
        },

        handoffSelectedToBacktest() {
            return this.primeBacktestForSymbol(this.selectedSymbol, {
                source: 'research-handoff',
                focus: true,
                announce: true
            });
        },

        handoffSelectedToTradingAgents() {
            return this.primeTradingAgentsForSymbol(this.selectedSymbol, {
                source: 'execution-handoff',
                focus: true,
                announce: true
            });
        },

        focusSection(sectionId, mode = null, options = {}) {
            const scroll = options.scroll !== false;
            const userInitiated = options.userInitiated !== false;
            if (mode) {
                this.setWorkspaceMode(mode, {
                    preserveScroll: true,
                    userInitiated,
                });
            }
            this.setActiveDesktopSection(sectionId, { userInitiated });
            if (scroll) {
                this.$nextTick(() => {
                    const element = document.getElementById(sectionId);
                    if (element) {
                        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                });
            }
        },

        currentWorkspaceMeta() {
            return this.workspaceModes.find((item) => item.key === this.workspaceMode) || this.workspaceModes[0];
        },

        isSectionVisible(section, mode = this.workspaceMode) {
            if (!section) {
                return false;
            }
            if (mode === 'overview') {
                return true;
            }
            return section.mode === mode;
        },

        workspaceVisibleSections(mode = this.workspaceMode) {
            return this.desktopSections().filter((section) => this.isSectionVisible(section, mode));
        },

        activeSectionMeta() {
            return this.desktopSections().find((section) => section.id === this.activeDesktopSectionId)
                || this.workspaceVisibleSections()[0]
                || this.desktopSections()[0];
        },

        ensureActiveSectionVisible() {
            const active = this.desktopSections().find((section) => section.id === this.activeDesktopSectionId);
            if (active && this.isSectionVisible(active)) {
                return;
            }
            const fallback = this.workspaceVisibleSections()[0];
            if (fallback) {
                this.setActiveDesktopSection(fallback.id);
            }
        },

        sectionVisible(modes) {
            if (this.workspaceMode === 'overview') {
                return true;
            }
            return Array.isArray(modes) && modes.includes(this.workspaceMode);
        },

        sectionChipClass(mode) {
            if (mode === 'signals') {
                return 'bg-tide/10 text-tide';
            }
            if (mode === 'execution') {
                return 'bg-coral/15 text-coral';
            }
            if (mode === 'research') {
                return 'bg-sun/15 text-sun';
            }
            return 'bg-ink/10 text-ink/70';
        },

        workspaceHasAuthMaterial() {
            return Boolean(this.config.token || this.adminAuth.refreshToken);
        },

        workspaceHasLiveData() {
            return Boolean(this.watchlist.length || this.signalTape.length);
        },

        workspaceHasResearchData() {
            return Boolean(this.rankings.length || this.strategyHealth.length || this.tradingAgentsRuns.length);
        },

        workspaceHasExecutionData() {
            return Boolean(this.backtestRuns.length || this.consoleLines.length || Number(this.scannerSummary.total_decisions || 0));
        },

        workspaceHasData() {
            return Boolean(
                this.workspaceHasLiveData()
                || this.workspaceHasResearchData()
                || this.workspaceHasExecutionData()
            );
        },

        preferredDesktopRoute() {
            if (this.watchlist.length) {
                return {
                    mode: 'signals',
                    sectionId: 'watchlist-panel',
                    label: '首屏 盯盘雷达'
                };
            }
            if (this.marketChart && this.marketChart.symbol) {
                return {
                    mode: 'signals',
                    sectionId: 'market-workbench-panel',
                    label: '首屏 市场工作台'
                };
            }
            if (this.signalTape.length) {
                return {
                    mode: 'signals',
                    sectionId: 'decision-tape-panel',
                    label: '首屏 实时判定流'
                };
            }
            if (this.rankings.length) {
                return {
                    mode: 'research',
                    sectionId: 'backtest-panel',
                    label: '首屏 回测与优化'
                };
            }
            if (this.strategyHealth.length) {
                return {
                    mode: 'research',
                    sectionId: 'health-panel',
                    label: '首屏 策略健康'
                };
            }
            if (this.tradingAgentsRuns.length) {
                return {
                    mode: 'research',
                    sectionId: 'trading-agents-panel',
                    label: '首屏 TradingAgents'
                };
            }
            if (this.backtestRuns.length || this.consoleLines.length || Number(this.scannerSummary.total_decisions || 0)) {
                return {
                    mode: 'execution',
                    sectionId: 'ops-log-panel',
                    label: '首屏 执行与日志'
                };
            }
            return {
                mode: 'overview',
                sectionId: 'trading-agents-panel',
                label: '保持总览'
            };
        },

        workspaceWorkbenchDescription() {
            const selected = this.selectedSignal();
            if (!this.workspaceHasAuthMaterial()) {
                return '先完成桌面端验证码登录，再把信号、研究和执行面板全部拉起来。';
            }
            if (!this.workspaceHasData()) {
                return this.loading
                    ? '会话已接通，正在拉取第一屏信号、研究和执行数据。'
                    : '会话已接通，下一步就是拉第一屏数据并自动把你带到最值得看的工作区。';
            }
            if (selected) {
                return `${selected.symbol} 已成为桌面焦点，可以直接接力到执行台、回测和 TradingAgents。`;
            }
            if (this.watchlist.length) {
                return `已同步 ${this.formatInt(this.watchlist.length)} 个盯盘候选，先从雷达里挑一个标的建立桌面焦点。`;
            }
            if (this.marketChart && this.marketChart.symbol) {
                return `${this.marketChart.symbol} 已进入市场工作台，可继续刷新图表、整理桌面盯盘，再接到执行或研究面。`;
            }
            if (this.workspaceHasResearchData()) {
                return '信号面当前偏空，但研究台已有数据，首屏会优先带你进入回测与健康视图。';
            }
            return '桌面工作区已在线，可从命令面板或左侧路由继续深挖。';
        },

        workspaceReadinessBadges() {
            const route = this.preferredDesktopRoute();
            const dataKinds = [
                this.watchlist.length,
                this.signalTape.length,
                this.rankings.length,
                this.strategyHealth.length,
                this.tradingAgentsRuns.length,
                this.backtestRuns.length,
            ].filter((count) => Number(count) > 0).length;

            return [
                this.adminSessionReady()
                    ? `${this.adminSessionRoleLabel()} 会话在线`
                    : (this.config.token
                        ? '已载入访问令牌'
                        : (this.adminAuth.refreshToken ? '等待恢复策略会话' : '等待管理员登录')),
                this.workspaceHasData()
                    ? `已同步 ${this.formatInt(dataKinds)} 类桌面数据`
                    : (this.loading ? '正在拉第一屏数据' : '首屏数据待同步'),
                this.selectedSignal()
                    ? `聚焦 ${this.selectedSignal().symbol}`
                    : (this.watchlist.length ? `待挑 ${this.formatInt(this.watchlist.length)} 个标的` : '暂无聚焦标的'),
                route.label,
            ];
        },

        workspaceLaunchpadCards() {
            const selected = this.selectedSignal();
            const researchReady = this.workspaceHasResearchData();
            const accessCard = this.adminSessionReady()
                ? {
                    id: 'access',
                    eyebrow: 'Access',
                    status: '在线',
                    badgeClass: 'bg-mint/10 text-mint',
                    panelClass: 'border-mint/15 bg-mint/5',
                    title: `${this.adminSessionRoleLabel()} 会话已接通`,
                    body: `${this.adminSessionEmail()} · ${this.adminSessionScopeLabel()} · 可以直接刷新会话或检查连接。`,
                    actionId: 'focus-access',
                    actionLabel: '查看会话台',
                    secondaryActionId: 'refresh-session',
                    secondaryActionLabel: '刷新会话'
                }
                : (this.workspaceHasAuthMaterial()
                    ? {
                        id: 'access',
                        eyebrow: 'Access',
                        status: '待恢复',
                        badgeClass: 'bg-sun/15 text-sun',
                        panelClass: 'border-sun/15 bg-sun/5',
                        title: '会话材料已存在，但还没恢复',
                        body: this.config.token
                            ? '当前已载入访问令牌，可以直接同步，也建议切回验证码会话以获得自动续期。'
                            : '本地已有 refresh token，恢复后就能重新拉起桌面端。',
                        actionId: this.adminAuth.refreshToken && !this.config.token ? 'refresh-session' : 'focus-access',
                        actionLabel: this.adminAuth.refreshToken && !this.config.token ? '恢复会话' : '查看接入台',
                        secondaryActionId: 'focus-access-email',
                        secondaryActionLabel: '改用验证码登录'
                    }
                    : {
                        id: 'access',
                        eyebrow: 'Access',
                        status: '待建立',
                        badgeClass: 'bg-coral/10 text-coral',
                        panelClass: 'border-coral/15 bg-coral/5',
                        title: '先建立桌面端管理员会话',
                        body: '验证码登录完成前，信号、研究和执行面板都只会停在空状态。',
                        actionId: 'focus-access-email',
                        actionLabel: '去登录台',
                        secondaryActionId: 'focus-access-code',
                        secondaryActionLabel: '去验证码区'
                    });

            const syncCard = !this.workspaceHasAuthMaterial()
                ? {
                    id: 'sync',
                    eyebrow: 'Sync',
                    status: '等待会话',
                    badgeClass: 'bg-ink/10 text-ink/70',
                    panelClass: 'border-ink/10 bg-white/75',
                    title: '首屏数据会在登录后自动接入',
                    body: '完成管理员验证后，桌面会自动尝试恢复会话并拉取第一屏数据。',
                    actionId: 'focus-access',
                    actionLabel: '查看接入台',
                    secondaryActionId: '',
                    secondaryActionLabel: ''
                }
                : (this.workspaceHasData()
                    ? {
                        id: 'sync',
                        eyebrow: 'Sync',
                        status: '已在线',
                        badgeClass: 'bg-tide/10 text-tide',
                        panelClass: 'border-tide/15 bg-tide/5',
                        title: '首屏数据已经接通',
                        body: `信号 ${this.formatInt(this.watchlist.length)} · 判定 ${this.formatInt(this.signalTape.length)} · 研究 ${this.formatInt(this.rankings.length + this.strategyHealth.length)}。`,
                        actionId: 'sync-platform',
                        actionLabel: '再次同步',
                        secondaryActionId: 'open-backtest',
                        secondaryActionLabel: researchReady ? '打开研究台' : '查看当前面板'
                    }
                    : {
                        id: 'sync',
                        eyebrow: 'Sync',
                        status: this.loading ? '同步中' : '待拉取',
                        badgeClass: this.loading ? 'bg-tide/10 text-tide' : 'bg-sun/15 text-sun',
                        panelClass: this.loading ? 'border-tide/15 bg-tide/5' : 'border-sun/15 bg-sun/5',
                        title: this.loading ? '正在拉第一屏数据' : '拉起第一屏数据',
                        body: this.loading
                            ? '平台正在同步信号、判定流、研究排名和执行记录。'
                            : '连接和会话已准备好，下一步就是把桌面工作区真正拉活。',
                        actionId: 'sync-platform',
                        actionLabel: this.loading ? '同步中...' : '立即同步',
                        secondaryActionId: 'focus-access',
                        secondaryActionLabel: '检查连接'
                    });

            const focusCard = selected
                ? {
                    id: 'focus',
                    eyebrow: 'Focus',
                    status: '已聚焦',
                    badgeClass: 'bg-coral/10 text-coral',
                    panelClass: 'border-coral/15 bg-coral/5',
                    title: `${selected.symbol} 已进入桌面焦点`,
                    body: `${selected.strategy} · ${this.executionContextSourceLabel()} · 可以直接接力到退出策略、回测或 TradingAgents。`,
                    actionId: 'open-execution',
                    actionLabel: '打开执行台',
                    secondaryActionId: 'prefill-backtest',
                    secondaryActionLabel: '带去回测'
                }
                : (this.watchlist.length
                    ? {
                        id: 'focus',
                        eyebrow: 'Focus',
                        status: '待选择',
                        badgeClass: 'bg-tide/10 text-tide',
                        panelClass: 'border-tide/15 bg-tide/5',
                        title: '挑一个标的开始桌面接力',
                        body: `盯盘雷达里已有 ${this.formatInt(this.watchlist.length)} 个候选，选中后会自动联动判定流、执行台和研究面。`,
                        actionId: 'open-watchlist',
                        actionLabel: '打开盯盘雷达',
                        secondaryActionId: 'open-decision',
                        secondaryActionLabel: '查看判定流'
                    }
                    : (this.marketChart && this.marketChart.symbol
                        ? {
                            id: 'focus',
                            eyebrow: 'Focus',
                            status: '图表在线',
                            badgeClass: 'bg-tide/10 text-tide',
                            panelClass: 'border-tide/15 bg-tide/5',
                            title: `${this.marketChart.symbol} 已进入市场工作台`,
                            body: `${this.marketSourceLabel()} · ${this.marketChart.period} 图表已就绪，可先加入桌面盯盘再继续接力。`,
                            actionId: 'open-market',
                            actionLabel: '打开市场工作台',
                            secondaryActionId: this.selectedSymbolPinned() ? 'open-watchlist' : 'pin-market-symbol',
                            secondaryActionLabel: this.selectedSymbolPinned() ? '查看盯盘清单' : '加入桌面盯盘'
                        }
                        : (researchReady
                            ? {
                                id: 'focus',
                                eyebrow: 'Focus',
                                status: '研究先行',
                                badgeClass: 'bg-sun/15 text-sun',
                                panelClass: 'border-sun/15 bg-sun/5',
                                title: '实时信号为空，先从研究台进入',
                                body: '回测排名或健康卡已在线，首屏会优先引导到研究工作区。',
                                actionId: 'open-backtest',
                                actionLabel: '打开研究台',
                                secondaryActionId: this.strategyHealth.length ? 'open-health' : 'open-tradingagents',
                                secondaryActionLabel: this.strategyHealth.length ? '看策略健康' : '打开 TradingAgents'
                            }
                            : {
                                id: 'focus',
                                eyebrow: 'Focus',
                                status: '等待焦点',
                                badgeClass: 'bg-ink/10 text-ink/70',
                                panelClass: 'border-ink/10 bg-white/75',
                                title: '还没有首个工作台焦点',
                                body: '先同步数据，桌面会根据实时结果自动把你带到最有价值的工作区。',
                                actionId: 'sync-platform',
                                actionLabel: '立即同步',
                                secondaryActionId: 'open-tradingagents',
                                secondaryActionLabel: '先看 TradingAgents'
                            })));

            return [accessCard, syncCard, focusCard];
        },

        panelEmptyState(panelId) {
            const selected = this.selectedSignal();
            const researchReady = this.workspaceHasResearchData();
            const hasAuth = this.workspaceHasAuthMaterial();

            if (panelId === 'watchlist') {
                if (!hasAuth) {
                    return {
                        title: '先完成桌面登录',
                        body: '管理员验证码登录完成后，盯盘候选会成为你的默认首屏入口。',
                        actionId: 'focus-access-email',
                        actionLabel: '去登录台',
                        secondaryActionId: 'focus-access-code',
                        secondaryActionLabel: '去验证码区'
                    };
                }
                if (researchReady) {
                    return {
                        title: '当前没有盯盘候选',
                        body: this.marketChart && this.marketChart.symbol
                            ? '实时候选为空，但市场工作台已在线，可以先看图表并把重点标的加入桌面盯盘。'
                            : '实时候选为空，但研究数据已在线，可以先从回测和健康视图开工。',
                        actionId: this.marketChart && this.marketChart.symbol ? 'open-market' : 'open-backtest',
                        actionLabel: this.marketChart && this.marketChart.symbol ? '打开市场工作台' : '打开研究台',
                        secondaryActionId: 'sync-platform',
                        secondaryActionLabel: '再同步一次'
                    };
                }
                return {
                    title: this.loading ? '正在拉取盯盘候选' : '暂无信号候选',
                    body: this.loading
                        ? '同步完成后，这里会列出可接力到执行台和研究面的标的。'
                        : (this.marketChart && this.marketChart.symbol
                            ? '当前可以先在市场工作台搜索标的、查看走势，再决定是否加入桌面盯盘。'
                            : '确认连接与策略会话后，重新同步即可更新实时候选。'),
                    actionId: this.marketChart && this.marketChart.symbol ? 'open-market' : 'sync-platform',
                    actionLabel: this.loading ? '同步中...' : (this.marketChart && this.marketChart.symbol ? '打开市场工作台' : '立即同步'),
                    secondaryActionId: 'focus-access',
                    secondaryActionLabel: '检查连接'
                };
            }

            if (panelId === 'decision-tape') {
                if (!hasAuth) {
                    return {
                        title: '判定流等待策略会话',
                        body: '先把桌面端会话建立起来，系统才会开始拉实时判定。',
                        actionId: 'focus-access-email',
                        actionLabel: '去登录台',
                        secondaryActionId: 'focus-access',
                        secondaryActionLabel: '检查接入'
                    };
                }
                if (this.watchlist.length) {
                    return {
                        title: '先从盯盘雷达选一个标的',
                        body: '聚焦标的后，这里会切成它的专属判定流，并同步给执行台和研究面。',
                        actionId: 'open-watchlist',
                        actionLabel: '打开盯盘雷达',
                        secondaryActionId: 'sync-platform',
                        secondaryActionLabel: '刷新判定流'
                    };
                }
                if (researchReady) {
                    return {
                        title: '当前没有实时判定',
                        body: '可以先从研究台查看最佳策略和健康度，等实时信号回来后再接回判定流。',
                        actionId: 'open-backtest',
                        actionLabel: '先看研究台',
                        secondaryActionId: 'sync-platform',
                        secondaryActionLabel: '刷新判定流'
                    };
                }
                return {
                    title: '暂无扫描判定数据',
                    body: '系统尚未收到可展示的实时判定，重新同步后再看一眼。',
                    actionId: 'sync-platform',
                    actionLabel: '立即同步',
                    secondaryActionId: 'open-tradingagents',
                    secondaryActionLabel: '先看研究任务'
                };
            }

            if (panelId === 'exit-desk') {
                if (!hasAuth) {
                    return {
                        title: '执行台还没接到策略会话',
                        body: '没有登录态时，退出策略参数和接力上下文都不会建立。',
                        actionId: 'focus-access-email',
                        actionLabel: '去登录台',
                        secondaryActionId: 'focus-access',
                        secondaryActionLabel: '检查接入'
                    };
                }
                if (this.watchlist.length) {
                    return {
                        title: '先聚焦一个标的',
                        body: '执行台会联动止盈止损参数、回测预填和研究接力，所以需要先从盯盘雷达选中一个候选。',
                        actionId: 'open-watchlist',
                        actionLabel: '打开盯盘雷达',
                        secondaryActionId: 'open-decision',
                        secondaryActionLabel: '查看判定流'
                    };
                }
                return {
                    title: '还没有执行焦点',
                    body: researchReady
                        ? '研究数据已在线，可以先从研究台挑一个策略方向，再回执行台。'
                        : '同步出实时候选后，执行台会自动进入接力状态。',
                    actionId: researchReady ? 'open-backtest' : 'sync-platform',
                    actionLabel: researchReady ? '打开研究台' : '立即同步',
                    secondaryActionId: 'open-tradingagents',
                    secondaryActionLabel: '查看 TradingAgents'
                };
            }

            if (panelId === 'backtest') {
                if (!hasAuth) {
                    return {
                        title: '先建立研究访问权限',
                        body: '完成管理员登录后，回测排名和研究面板才会开始同步。',
                        actionId: 'focus-access-email',
                        actionLabel: '去登录台',
                        secondaryActionId: 'focus-access',
                        secondaryActionLabel: '检查接入'
                    };
                }
                if (selected) {
                    return {
                        title: '当前标的还没有命中回测排名',
                        body: `${selected.symbol} 已成为桌面焦点，可以先把它带入回测表单，再触发一轮研究刷新。`,
                        actionId: 'prefill-backtest',
                        actionLabel: '带入当前标的',
                        secondaryActionId: 'trigger-backtest',
                        secondaryActionLabel: '触发回测刷新'
                    };
                }
                if (this.watchlist.length) {
                    return {
                        title: '回测排名暂时为空',
                        body: '先从盯盘雷达选一个标的，再带着它去跑第一轮回测。',
                        actionId: 'open-watchlist',
                        actionLabel: '先选标的',
                        secondaryActionId: 'trigger-backtest',
                        secondaryActionLabel: '直接触发回测'
                    };
                }
                return {
                    title: '暂无回测排名',
                    body: '同步后如果仍为空，可以手动提交回测刷新来补出研究结果。',
                    actionId: 'trigger-backtest',
                    actionLabel: '触发回测刷新',
                    secondaryActionId: 'sync-platform',
                    secondaryActionLabel: '先同步一次'
                };
            }

            if (panelId === 'health') {
                if (!hasAuth) {
                    return {
                        title: '策略健康视图等待登录',
                        body: '完成管理员会话建立后，稳定性和退化数据才会进入桌面。',
                        actionId: 'focus-access-email',
                        actionLabel: '去登录台',
                        secondaryActionId: 'focus-access',
                        secondaryActionLabel: '检查接入'
                    };
                }
                if (this.rankings.length) {
                    return {
                        title: '健康卡还没生成',
                        body: '回测排名已经在线，可以先从研究台判断是否需要补跑健康分析。',
                        actionId: 'open-backtest',
                        actionLabel: '查看回测排名',
                        secondaryActionId: 'sync-platform',
                        secondaryActionLabel: '重新同步'
                    };
                }
                return {
                    title: '暂无策略健康数据',
                    body: '同步完成后，这里会显示稳定性、退化和重点标的。',
                    actionId: 'sync-platform',
                    actionLabel: '立即同步',
                    secondaryActionId: 'open-tradingagents',
                    secondaryActionLabel: '先看 TradingAgents'
                };
            }

            return {
                title: '暂无数据',
                body: '先同步桌面端数据，再回来查看这个面板。',
                actionId: 'sync-platform',
                actionLabel: '立即同步',
                secondaryActionId: 'focus-access',
                secondaryActionLabel: '检查接入'
            };
        },

        runDeskAction(actionId) {
            const selected = this.selectedSignal();
            const normalized = String(actionId || '').trim();
            if (!normalized) {
                return;
            }

            if (normalized === 'focus-access') {
                this.focusDesktopAccess();
                return;
            }
            if (normalized === 'focus-access-email') {
                this.focusDesktopAccess('adminEmailInput');
                return;
            }
            if (normalized === 'focus-access-code') {
                this.focusDesktopAccess(this.adminAuth.verifyEmail ? 'adminCodeInput' : 'adminVerifyEmailInput');
                return;
            }
            if (normalized === 'refresh-session') {
                this.refreshAdminSession();
                return;
            }
            if (normalized === 'sync-platform') {
                this.loadAll();
                return;
            }
            if (normalized === 'open-market') {
                this.focusSection('market-workbench-panel', 'signals');
                return;
            }
            if (normalized === 'pin-market-symbol') {
                if (this.selectedSymbolPinned()) {
                    this.focusSection('watchlist-panel', 'signals');
                    return;
                }
                this.pinSelectedSymbolToDeskWatchlist();
                return;
            }
            if (normalized === 'open-watchlist') {
                this.focusSection('watchlist-panel', 'signals');
                return;
            }
            if (normalized === 'open-decision') {
                this.focusSection('decision-tape-panel', 'signals');
                return;
            }
            if (normalized === 'open-execution') {
                if (selected) {
                    this.handoffToExecution(selected.symbol, { source: 'quick-action', announce: true });
                    return;
                }
                this.focusSection('ops-log-panel', 'execution');
                return;
            }
            if (normalized === 'prefill-backtest') {
                if (selected) {
                    this.handoffSelectedToBacktest();
                    return;
                }
                this.focusSection('backtest-panel', 'research');
                return;
            }
            if (normalized === 'trigger-backtest') {
                this.triggerBacktestRefresh();
                return;
            }
            if (normalized === 'open-backtest') {
                this.focusSection('backtest-panel', 'research');
                return;
            }
            if (normalized === 'open-health') {
                this.focusSection('health-panel', 'research');
                return;
            }
            if (normalized === 'open-tradingagents') {
                this.focusSection('trading-agents-panel', 'research');
                return;
            }
        },

        applyWorkspaceFirstScreenState(options = {}) {
            if (!this.workspaceHasData()) {
                return false;
            }

            const force = Boolean(options.force);
            const defaultLanding = this.workspaceMode === 'overview' && this.activeDesktopSectionId === 'trading-agents-panel';
            if (!force) {
                if (this.workspaceAutoRouted && !defaultLanding) {
                    return false;
                }
                if (this.workspacePinned && !defaultLanding) {
                    return false;
                }
            }

            const route = this.preferredDesktopRoute();
            if (!route || !route.mode || !route.sectionId) {
                return false;
            }

            const changed = this.workspaceMode !== route.mode || this.activeDesktopSectionId !== route.sectionId;
            if (!changed && this.workspaceAutoRouted && !force) {
                return false;
            }

            this.setWorkspaceMode(route.mode, {
                preserveScroll: true,
                userInitiated: false,
            });
            this.setActiveDesktopSection(route.sectionId, { userInitiated: false });
            this.workspaceAutoRouted = true;

            if (options.scroll !== false) {
                this.$nextTick(() => {
                    const element = document.getElementById(route.sectionId);
                    if (element) {
                        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                });
            }
            return true;
        },

        workspaceQuickActions() {
            const selected = this.selectedSignal();
            const topStrategy = this.topStrategy();
            const pendingRuns = this.pendingTradingAgentsRunsCount();

            return [
                selected
                    ? {
                        id: 'selected-signal',
                        label: `${selected.symbol} 退出策略`,
                        meta: `${selected.status || '观察中'} · 直接查看止盈止损参数`,
                        sectionId: 'exit-desk-panel',
                        mode: 'execution'
                    }
                    : {
                        id: 'select-signal',
                        label: '挑选观察标的',
                        meta: this.marketChart && this.marketChart.symbol
                            ? `${this.marketChart.symbol} 图表在线 · 进入市场工作台`
                            : `${this.formatInt(this.watchlist.length)} 个候选 · 进入盯盘雷达`,
                        sectionId: this.marketChart && this.marketChart.symbol ? 'market-workbench-panel' : 'watchlist-panel',
                        mode: 'signals'
                    },
                {
                    id: 'market-workbench',
                    label: this.marketChart && this.marketChart.symbol ? `${this.marketChart.symbol} 市场工作台` : '市场工作台',
                    meta: this.marketChartHasData()
                        ? `${this.marketSourceLabel()} · ${this.marketChart.period} OHLCV 图表`
                        : '搜索标的、打开图表并整理桌面盯盘',
                    sectionId: 'market-workbench-panel',
                    mode: 'signals'
                },
                {
                    id: 'tradingagents',
                    label: pendingRuns ? '跟进待完成分析' : 'TradingAgents 分析台',
                    meta: pendingRuns ? `${this.formatInt(pendingRuns)} 个运行中任务` : '提交新的研究任务',
                    sectionId: 'trading-agents-panel',
                    mode: 'research'
                },
                {
                    id: 'top-strategy',
                    label: selected ? `${selected.symbol} 研究台` : (topStrategy ? this.strategyLabel(topStrategy.strategy_name) : '查看回测排名'),
                    meta: selected
                        ? `${selected.strategy} · 聚焦回测排名和策略健康`
                        : (topStrategy ? `分数 ${this.toFixed(topStrategy.score, 2)} · 打开回测与优化` : '等待回测刷新'),
                    sectionId: 'backtest-panel',
                    mode: 'research'
                },
                {
                    id: 'ops-log',
                    label: '执行与日志',
                    meta: this.consoleLines.length
                        ? `最近 ${this.formatInt(this.consoleLines.length)} 条控制台日志`
                        : `${this.formatInt(this.backtestRuns.length)} 条运行记录`,
                    sectionId: 'ops-log-panel',
                    mode: 'execution'
                }
            ];
        },

        workspaceCommandItems() {
            const selected = this.selectedSignal();
            const pendingRuns = this.pendingTradingAgentsRunsCount();
            const researchSummary = selected ? this.selectedResearchSummary() : null;
            const workspaceCommands = this.workspaceModes.map((mode, index) => ({
                id: `workspace-${mode.key}`,
                group: '工作区',
                label: `切换到 ${mode.label}`,
                meta: mode.description,
                hint: `Alt+${index + 1}`,
                search: `${mode.key} ${mode.label} ${mode.description}`,
                run: () => this.setWorkspaceMode(mode.key)
            }));
            const panelCommands = this.desktopSections().map((section) => ({
                id: `panel-${section.id}`,
                group: '面板',
                label: section.label,
                meta: section.meta,
                hint: section.modeLabel,
                search: `${section.label} ${section.mode} ${section.meta}`,
                run: () => this.focusSection(section.id, section.mode)
            }));
            const actionCommands = [
                {
                    id: 'refresh-platform',
                    group: '动作',
                    label: '立即刷新平台',
                    meta: '重新拉取策略、判定和回测数据。',
                    hint: 'Shift+R',
                    search: 'refresh sync reload load 平台 刷新',
                    run: () => this.loadAll()
                },
                {
                    id: 'backtest-refresh',
                    group: '动作',
                    label: '触发回测刷新',
                    meta: `当前周期 ${this.config.timeframe || '1d'} · 直接提交后台回测任务。`,
                    hint: '研究',
                    search: 'backtest research 排名 回测',
                    run: () => this.triggerBacktestRefresh()
                },
                {
                    id: 'sync-tradingagents',
                    group: '动作',
                    label: '同步 TradingAgents 列表',
                    meta: `${this.formatInt(this.tradingAgentsRuns.length)} 条任务 · 主动同步分析列表。`,
                    hint: '研究',
                    search: 'tradingagents sync 分析 列表',
                    run: () => this.refreshTradingAgentsAnalyses()
                },
                {
                    id: 'poll-tradingagents',
                    group: '动作',
                    label: '轮询运行中 TradingAgents',
                    meta: `${this.formatInt(pendingRuns)} 个待完成任务 · 立即轮询一次。`,
                    hint: '研究',
                    search: 'tradingagents poll 轮询 运行中',
                    run: () => this.pollPendingTradingAgentsRuns(true)
                }
            ];

            if (selected) {
                const selectedActions = [
                    {
                        id: 'selected-ranking-preset',
                        group: '动作',
                        label: `带入最佳窗口: ${selected.symbol}`,
                        meta: researchSummary && researchSummary.rankingMatch
                            ? `${researchSummary.strategyLabel} · 最佳窗口 ${researchSummary.bestWindowLabel}`
                            : '将研究台命中的最佳窗口带回回测表单。',
                        hint: '研究',
                        search: `${selected.symbol} best window preset research 回测 最佳窗口`,
                        run: () => this.applySelectedResearchPreset()
                    },
                    {
                        id: 'selected-health',
                        group: '动作',
                        label: `查看 ${selected.symbol} 策略健康`,
                        meta: `${selected.strategy} · 高亮研究台中的健康卡。`,
                        hint: '研究',
                        search: `${selected.symbol} health strategy 研究 健康`,
                        run: () => this.focusSelectedStrategyHealth()
                    },
                    {
                        id: 'selected-tradingagents',
                        group: '动作',
                        label: `交给 TradingAgents: ${selected.symbol}`,
                        meta: `${selected.strategy} · 预填研究草稿并切到分析台。`,
                        hint: '研究',
                        search: `${selected.symbol} tradingagents 研究 分析`,
                        run: () => this.handoffSelectedToTradingAgents()
                    },
                    {
                        id: 'selected-backtest',
                        group: '动作',
                        label: `预填回测: ${selected.symbol}`,
                        meta: `${selected.strategy} · 带着当前标的和策略进入回测面板。`,
                        hint: '研究',
                        search: `${selected.symbol} backtest 回测 研究`,
                        run: () => this.handoffSelectedToBacktest()
                    },
                    {
                        id: 'selected-exit-desk',
                        group: '动作',
                        label: `查看 ${selected.symbol} 退出策略`,
                        meta: `${selected.strategy} · 带着当前聚焦标的切到执行台。`,
                        hint: '执行',
                        search: `${selected.symbol} exit execution 退出策略 执行台`,
                        run: () => this.handoffToExecution(selected.symbol, { source: 'command-palette', announce: true })
                    }
                ];

                actionCommands.unshift(...selectedActions.filter((item) => {
                    if (item.id !== 'selected-ranking-preset') {
                        return true;
                    }
                    return Boolean(researchSummary && researchSummary.rankingMatch);
                }));
            }

            const symbolCommands = this.watchlist.slice(0, 8).map((item) => ({
                id: `symbol-${item.symbol}`,
                group: '标的',
                label: `聚焦 ${item.symbol}`,
                meta: `${item.strategy} · ${item.status || '监控中'} · 打开信号判定流。`,
                hint: '信号',
                search: `${item.symbol} ${item.strategy} ${item.status || ''} signal signals`,
                run: () => this.focusSymbol(item.symbol, {
                    sectionId: 'decision-tape-panel',
                    mode: 'signals',
                    source: 'command-palette'
                })
            }));

            return [...actionCommands, ...workspaceCommands, ...panelCommands, ...symbolCommands];
        },

        filteredCommandPaletteItems() {
            const items = this.workspaceCommandItems();
            const query = String(this.commandPaletteQuery || '').trim().toLowerCase();
            if (!query) {
                return items;
            }
            return items.filter((item) => [item.group, item.label, item.meta, item.hint, item.search]
                .filter(Boolean)
                .join(' ')
                .toLowerCase()
                .includes(query));
        },

        openCommandPalette(initialQuery = '') {
            this.commandPaletteOpen = true;
            this.commandPaletteQuery = String(initialQuery || '').trim();
            this.commandPaletteActiveIndex = 0;
            this.$nextTick(() => {
                if (this.$refs && this.$refs.commandPaletteInput) {
                    this.$refs.commandPaletteInput.focus();
                    this.$refs.commandPaletteInput.select();
                }
            });
        },

        closeCommandPalette() {
            this.commandPaletteOpen = false;
            this.commandPaletteQuery = '';
            this.commandPaletteActiveIndex = 0;
        },

        syncCommandPaletteSelection() {
            const items = this.filteredCommandPaletteItems();
            if (!items.length) {
                this.commandPaletteActiveIndex = 0;
                return;
            }
            this.commandPaletteActiveIndex = Math.max(0, Math.min(this.commandPaletteActiveIndex, items.length - 1));
        },

        commandPaletteMove(step) {
            const items = this.filteredCommandPaletteItems();
            if (!items.length) {
                this.commandPaletteActiveIndex = 0;
                return;
            }
            const total = items.length;
            this.commandPaletteActiveIndex = (this.commandPaletteActiveIndex + step + total) % total;
        },

        runCommandPaletteItem(item) {
            if (!item || typeof item.run !== 'function') {
                return;
            }
            this.closeCommandPalette();
            item.run();
        },

        runActiveCommandPaletteItem() {
            const items = this.filteredCommandPaletteItems();
            if (!items.length) {
                return;
            }
            this.runCommandPaletteItem(items[this.commandPaletteActiveIndex]);
        },

        isEditableTarget(target) {
            if (!target || typeof target.closest !== 'function') {
                return false;
            }
            return Boolean(target.closest('input, textarea, select, [contenteditable="true"]'));
        },

        handleGlobalKeydown(event) {
            const key = String(event.key || '').toLowerCase();
            const shortcutKey = event.ctrlKey || event.metaKey;

            if (shortcutKey && key === 'k') {
                event.preventDefault();
                if (this.commandPaletteOpen) {
                    this.closeCommandPalette();
                } else {
                    this.openCommandPalette();
                }
                return;
            }

            if (this.commandPaletteOpen) {
                if (key === 'escape') {
                    event.preventDefault();
                    this.closeCommandPalette();
                    return;
                }
                if (key === 'arrowdown') {
                    event.preventDefault();
                    this.commandPaletteMove(1);
                    return;
                }
                if (key === 'arrowup') {
                    event.preventDefault();
                    this.commandPaletteMove(-1);
                    return;
                }
                if (key === 'enter') {
                    event.preventDefault();
                    this.runActiveCommandPaletteItem();
                }
                return;
            }

            if (this.isEditableTarget(event.target)) {
                return;
            }

            if (!event.altKey && !shortcutKey && key === '/') {
                event.preventDefault();
                this.openCommandPalette();
                return;
            }

            if (event.altKey && !shortcutKey) {
                if (key === '1') {
                    event.preventDefault();
                    this.setWorkspaceMode('overview');
                    return;
                }
                if (key === '2') {
                    event.preventDefault();
                    this.setWorkspaceMode('signals');
                    return;
                }
                if (key === '3') {
                    event.preventDefault();
                    this.setWorkspaceMode('execution');
                    return;
                }
                if (key === '4') {
                    event.preventDefault();
                    this.setWorkspaceMode('research');
                    return;
                }
            }

            if (event.shiftKey && !event.altKey && !shortcutKey && key === 'r') {
                event.preventDefault();
                this.loadAll();
            }
        },

        registerDesktopObserver() {
            if (typeof window === 'undefined' || typeof window.IntersectionObserver === 'undefined') {
                return;
            }
            if (this.desktopObserver) {
                this.desktopObserver.disconnect();
            }

            this.desktopObserver = new IntersectionObserver((entries) => {
                const visibleEntry = entries
                    .filter((entry) => entry.isIntersecting)
                    .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
                if (!visibleEntry || !visibleEntry.target || !visibleEntry.target.id) {
                    return;
                }

                const section = this.desktopSections().find((item) => item.id === visibleEntry.target.id);
                if (!this.isSectionVisible(section)) {
                    return;
                }

                this.setActiveDesktopSection(visibleEntry.target.id);
            }, {
                rootMargin: '-18% 0px -55% 0px',
                threshold: [0.15, 0.35, 0.6]
            });

            this.desktopSections().forEach((section) => {
                const element = document.getElementById(section.id);
                if (element) {
                    this.desktopObserver.observe(element);
                }
            });
        },

        desktopSections() {
            return [
                {
                    id: 'market-workbench-panel',
                    label: '市场工作台',
                    mode: 'signals',
                    modeLabel: '信号',
                    meta: this.marketChartHasData()
                        ? `${this.marketChart.symbol} · ${this.marketSourceLabel()} · ${this.marketChart.period} OHLCV`
                        : `${this.formatInt(this.deskPinnedCount())} 个手动盯盘 · 搜索与图表主屏`
                },
                {
                    id: 'trading-agents-panel',
                    label: 'TradingAgents 分析台',
                    mode: 'research',
                    modeLabel: '研究',
                    meta: `${this.formatInt(this.tradingAgentsRuns.length)} 个任务 · 异步分析与结果收敛`
                },
                {
                    id: 'watchlist-panel',
                    label: '盯盘雷达',
                    mode: 'signals',
                    modeLabel: '信号',
                    meta: `${this.formatInt(this.watchlist.length)} 个标的 · 快速切换策略候选`
                },
                {
                    id: 'decision-tape-panel',
                    label: '实时判定流',
                    mode: 'signals',
                    modeLabel: '信号',
                    meta: `${this.formatInt(this.signalTape.length)} 条判定 · 聚焦已发射与已抑制`
                },
                {
                    id: 'engine-panel',
                    label: '预警逻辑引擎',
                    mode: 'signals',
                    modeLabel: '信号',
                    meta: `${this.formatInt(this.strategyMix.length)} 个策略分布块 · 解释当前选择偏向`
                },
                {
                    id: 'exit-desk-panel',
                    label: '退出策略工作台',
                    mode: 'execution',
                    modeLabel: '执行',
                    meta: `${this.selectedSignal() ? this.selectedSignal().symbol : '--'} · ${this.executionContextSourceLabel()} -> 观察止盈止损参数`
                },
                {
                    id: 'backtest-panel',
                    label: '回测与优化',
                    mode: 'research',
                    modeLabel: '研究',
                    meta: this.selectedSignal()
                        ? `${this.selectedSignal().symbol} · ${this.selectedSignal().strategy} · 回测研究接力`
                        : `${this.formatInt(this.rankings.length)} 条排名 · 手动触发刷新`
                },
                {
                    id: 'health-panel',
                    label: '策略健康视图',
                    mode: 'research',
                    modeLabel: '研究',
                    meta: this.selectedSignal()
                        ? `${this.selectedSignal().symbol} · ${this.selectedSignal().strategy} · 策略健康接力`
                        : `${this.formatInt(this.strategyHealth.length)} 条健康记录 · 看稳定性与退化`
                },
                {
                    id: 'ops-log-panel',
                    label: '执行与日志',
                    mode: 'execution',
                    modeLabel: '执行',
                    meta: this.selectedSignal()
                        ? `${this.selectedSignal().symbol} · 聚焦执行轨迹与日志`
                        : `${this.formatInt(this.backtestRuns.length)} 条运行记录 · 回测与 scanner 日志`
                },
                {
                    id: 'funnel-panel',
                    label: '分发漏斗',
                    mode: 'execution',
                    modeLabel: '执行',
                    meta: this.selectedSignal()
                        ? `${this.selectedSignal().symbol} · 当前执行漏斗 + 平台全局漏斗`
                        : `${this.formatInt(this.scannerSummary.total_decisions)} 条判定总量 · 观察发射与抑制转化`
                }
            ];
        },
    };
}

window.PlatformDeckWorkspace = {
    createState: createPlatformDeckWorkspaceState,
    createModule: createPlatformDeckWorkspaceModule,
};
