function createPlatformDeckMarketState() {
    return {
        signalWatchlist: [],
        deskWatchlistEntries: [],
        marketFocusEntry: null,
        watchSort: 'priority',
        marketSearch: {
            query: '',
            assetType: '',
            results: [],
            loading: false,
            error: '',
            lastQuery: '',
            resultsVisible: false,
        },
        marketChart: {
            symbol: '',
            name: '',
            assetType: '',
            source: 'yahoo',
            period: '3mo',
            bars: [],
            quote: {
                latest_at: null,
                latest_close: 0,
                previous_close: 0,
                change: 0,
                change_pct: 0,
                session_open: 0,
                session_high: 0,
                session_low: 0,
                session_volume: 0,
            },
            loading: false,
            error: '',
            lastLoadedAt: '',
        },
    };
}

function createPlatformDeckMarketModule() {
    return {
        normalizeMarketSymbol(symbol) {
            return String(symbol || '').trim().toUpperCase();
        },

        marketQueryPlaceholder() {
            return '输入 AAPL、NVDA、BTC 等代码';
        },

        sanitizeDeskWatchlistEntries(entries) {
            const rows = Array.isArray(entries) ? entries : [];
            const seen = new Set();
            return rows
                .map((item) => {
                    const symbol = this.normalizeMarketSymbol(item && item.symbol);
                    if (!symbol) {
                        return null;
                    }
                    const assetType = String(item && item.assetType || '').trim().toLowerCase();
                    const marketDataSource = this.guessMarketDataSource(symbol, assetType || null, item && item.marketDataSource);
                    return {
                        symbol,
                        name: String(item && item.name || symbol).trim() || symbol,
                        assetType,
                        marketDataSource,
                        latestPrice: this.toNumber(item && item.latestPrice),
                        changePct: this.toNumber(item && item.changePct),
                        updatedAt: String(item && item.updatedAt || item && item.pinnedAt || '').trim(),
                        pinnedAt: String(item && item.pinnedAt || item && item.updatedAt || '').trim() || new Date().toISOString(),
                    };
                })
                .filter((item) => {
                    if (!item) {
                        return false;
                    }
                    const key = item.symbol;
                    if (seen.has(key)) {
                        return false;
                    }
                    seen.add(key);
                    return true;
                });
        },

        persistDeskWatchlistEntries() {
            localStorage.setItem(
                this.storageKeys.deskWatchlist,
                JSON.stringify(this.deskWatchlistEntries)
            );
        },

        restoreDeskWatchlistEntries(routeSymbol = '') {
            const storedEntries = this.parseStoredJson(
                localStorage.getItem(this.storageKeys.deskWatchlist),
                []
            );
            this.deskWatchlistEntries = this.sanitizeDeskWatchlistEntries(storedEntries);
            const normalizedRouteSymbol = this.normalizeMarketSymbol(routeSymbol);
            if (normalizedRouteSymbol) {
                this.marketSearch.query = normalizedRouteSymbol;
                this.marketFocusEntry = this.createDeskWatchlistItem({
                    symbol: normalizedRouteSymbol,
                    name: normalizedRouteSymbol,
                    assetType: '',
                    pinnedAt: new Date().toISOString(),
                }, { transient: true });
            }
            this.rebuildMarketWatchlist();
            if (!this.selectedSymbol && normalizedRouteSymbol) {
                this.selectedSymbol = normalizedRouteSymbol;
            }
            if (!this.selectedSymbol && this.watchlist.length) {
                this.selectedSymbol = this.watchlist[0].symbol;
            }
        },

        guessMarketDataSource(symbol, assetType = null, explicitSource = '') {
            const provided = String(explicitSource || '').trim().toLowerCase();
            if (provided === 'yahoo' || provided === 'binance') {
                return provided;
            }
            const normalizedSymbol = this.normalizeMarketSymbol(symbol);
            const normalizedAssetType = String(assetType || '').trim().toLowerCase();
            if (normalizedAssetType === 'crypto' || normalizedSymbol.endsWith('USDT')) {
                return 'binance';
            }
            return 'yahoo';
        },

        createDeskWatchlistItem(entry, options = {}) {
            const symbol = this.normalizeMarketSymbol(entry && entry.symbol);
            const latestPrice = this.toNumber(entry && entry.latestPrice);
            const changePct = this.toNumber(entry && entry.changePct);
            const assetType = String(entry && entry.assetType || '').trim().toLowerCase();
            const quoteName = String(entry && entry.name || symbol).trim() || symbol;
            const transient = Boolean(options.transient);
            return {
                id: `${transient ? 'focus' : 'desk'}:${symbol}`,
                symbol,
                strategyCode: 'manual_watch',
                strategy: transient ? '图表聚焦' : '手动关注',
                signalType: 'manual_watch',
                status: transient ? 'focus_only' : 'desk_watch',
                entryPrice: latestPrice,
                stopLoss: 0,
                takeProfit1: 0,
                takeProfit2: 0,
                takeProfit3: 0,
                riskReward: 0,
                atrValue: 0,
                atrMultiplier: 0,
                atrLabel: latestPrice > 0 ? '市场快照' : '等待报价',
                target1Pct: changePct,
                confidence: 0,
                probability: 0,
                generatedAt: entry && entry.updatedAt || entry && entry.pinnedAt || null,
                indicators: {},
                strategySelection: {},
                selectionSource: 'manual',
                sourceStrategy: 'manual_watch',
                selectionRank: 0,
                rankingScore: 0,
                combinedScore: 0,
                signalFitScore: 0,
                regimeBias: 0,
                degradationPenalty: 0,
                strategyWeight: 0,
                selectionStable: false,
                marketRegime: 'range',
                marketRegimeDetail: 'range',
                calibrationVersion: '--',
                exitLevels: {},
                exitLevelSource: 'unavailable',
                exitAtrValue: 0,
                exitAtrMultiplier: 0,
                scoreBreakdown: {},
                manualPinned: !transient,
                transient,
                quoteName,
                assetType,
                marketDataSource: this.guessMarketDataSource(symbol, assetType, entry && entry.marketDataSource),
                raw: entry || {},
            };
        },

        compareWatchlistItems(left, right) {
            const sortMode = String(this.watchSort || 'priority').trim().toLowerCase();
            if (sortMode === 'symbol') {
                return String(left.symbol || '').localeCompare(String(right.symbol || ''));
            }
            if (sortMode === 'price') {
                const delta = this.toNumber(right.entryPrice) - this.toNumber(left.entryPrice);
                if (Math.abs(delta) > 0.0001) {
                    return delta;
                }
                return String(left.symbol || '').localeCompare(String(right.symbol || ''));
            }
            if (sortMode === 'confidence') {
                const delta = this.toNumber(right.confidence) - this.toNumber(left.confidence);
                if (Math.abs(delta) > 0.0001) {
                    return delta;
                }
                return String(left.symbol || '').localeCompare(String(right.symbol || ''));
            }

            const leftAlert = this.isAlertSignal(left) ? 1 : 0;
            const rightAlert = this.isAlertSignal(right) ? 1 : 0;
            if (leftAlert !== rightAlert) {
                return rightAlert - leftAlert;
            }

            const leftManual = left.manualPinned || left.transient ? 1 : 0;
            const rightManual = right.manualPinned || right.transient ? 1 : 0;
            if (leftManual !== rightManual) {
                return leftManual - rightManual;
            }

            const confidenceDelta = this.toNumber(right.confidence) - this.toNumber(left.confidence);
            if (Math.abs(confidenceDelta) > 0.0001) {
                return confidenceDelta;
            }

            const changeDelta = this.toNumber(right.target1Pct) - this.toNumber(left.target1Pct);
            if (Math.abs(changeDelta) > 0.0001) {
                return changeDelta;
            }

            return String(left.symbol || '').localeCompare(String(right.symbol || ''));
        },

        rebuildMarketWatchlist() {
            const serverRows = Array.isArray(this.signalWatchlist) ? this.signalWatchlist : [];
            const seen = new Set(serverRows.map((item) => String(item.symbol || '').trim().toUpperCase()));
            const manualRows = this.deskWatchlistEntries
                .filter((entry) => !seen.has(entry.symbol))
                .map((entry) => this.createDeskWatchlistItem(entry));
            this.watchlist = [...serverRows, ...manualRows].sort((left, right) => this.compareWatchlistItems(left, right));
            if (!this.watchlist.length) {
                if (!this.marketFocusEntry || this.marketFocusEntry.symbol !== this.selectedSymbol) {
                    this.selectedSymbol = '';
                }
                return;
            }
            if (!this.selectedSymbol) {
                this.selectedSymbol = this.watchlist[0].symbol;
                return;
            }
            const activeSymbol = this.normalizeMarketSymbol(this.selectedSymbol);
            if (this.watchlist.some((item) => item.symbol === activeSymbol)) {
                return;
            }
            if (this.marketFocusEntry && this.marketFocusEntry.symbol === activeSymbol) {
                return;
            }
            this.selectedSymbol = this.watchlist[0].symbol;
        },

        selectedSymbolPinned() {
            const symbol = this.normalizeMarketSymbol(this.selectedSymbol || this.marketChart.symbol);
            if (!symbol) {
                return false;
            }
            return this.deskWatchlistEntries.some((entry) => entry.symbol === symbol);
        },

        deskPinnedCount() {
            return this.deskWatchlistEntries.length;
        },

        upsertDeskWatchlistEntry(entry) {
            const symbol = this.normalizeMarketSymbol(entry && entry.symbol);
            if (!symbol) {
                return false;
            }
            const normalizedEntry = this.sanitizeDeskWatchlistEntries([{ ...entry, symbol }])[0];
            if (!normalizedEntry) {
                return false;
            }
            const existingIndex = this.deskWatchlistEntries.findIndex((item) => item.symbol === symbol);
            if (existingIndex >= 0) {
                this.deskWatchlistEntries.splice(existingIndex, 1, {
                    ...this.deskWatchlistEntries[existingIndex],
                    ...normalizedEntry,
                    pinnedAt: this.deskWatchlistEntries[existingIndex].pinnedAt || normalizedEntry.pinnedAt,
                });
            } else {
                this.deskWatchlistEntries.unshift(normalizedEntry);
            }
            this.persistDeskWatchlistEntries();
            this.rebuildMarketWatchlist();
            return true;
        },

        removeDeskWatchlistSymbol(symbol) {
            const normalizedSymbol = this.normalizeMarketSymbol(symbol);
            if (!normalizedSymbol) {
                return false;
            }
            const nextEntries = this.deskWatchlistEntries.filter((entry) => entry.symbol !== normalizedSymbol);
            if (nextEntries.length === this.deskWatchlistEntries.length) {
                return false;
            }
            this.deskWatchlistEntries = nextEntries;
            this.persistDeskWatchlistEntries();
            this.rebuildMarketWatchlist();
            return true;
        },

        clearDeskWatchlist() {
            this.deskWatchlistEntries = [];
            localStorage.removeItem(this.storageKeys.deskWatchlist);
            this.rebuildMarketWatchlist();
            this.log('info', '已清空桌面盯盘清单。');
        },

        activeMarketSignal() {
            const symbol = this.normalizeMarketSymbol(this.selectedSymbol || this.marketChart.symbol);
            if (!symbol) {
                return null;
            }
            const watched = this.watchlist.find((item) => item.symbol === symbol);
            if (watched) {
                return watched;
            }
            if (this.marketFocusEntry && this.marketFocusEntry.symbol === symbol) {
                return this.marketFocusEntry;
            }
            return null;
        },

        marketSearchResultMeta(item) {
            const exchange = String(item && item.exchange || '').trim();
            const assetType = String(item && item.asset_type || '').trim();
            return [exchange, assetType].filter(Boolean).join(' · ') || '可打开图表';
        },

        async searchMarketSymbols() {
            const query = this.normalizeMarketSymbol(this.marketSearch.query);
            if (!query) {
                this.marketSearch.results = [];
                this.marketSearch.error = '请输入代码再搜索。';
                this.marketSearch.resultsVisible = false;
                return;
            }
            this.marketSearch.loading = true;
            this.marketSearch.error = '';
            this.marketSearch.lastQuery = query;
            this.marketSearch.resultsVisible = true;
            try {
                const searchParams = new URLSearchParams({
                    q: query,
                    limit: '8',
                });
                if (this.marketSearch.assetType) {
                    searchParams.set('type', this.marketSearch.assetType);
                }
                const payload = await this.publicApiRequest(`/v1/search/symbols?${searchParams.toString()}`);
                this.marketSearch.results = Array.isArray(payload && payload.items)
                    ? payload.items.map((item) => ({
                        ...item,
                        symbol: this.normalizeMarketSymbol(item.symbol),
                    }))
                    : [];
                if (!this.marketSearch.results.length) {
                    this.marketSearch.error = `没有检索到 ${query}，可以直接打开图表。`;
                }
            } catch (error) {
                this.marketSearch.results = [];
                this.marketSearch.error = error.message || '搜索失败';
            } finally {
                this.marketSearch.loading = false;
            }
        },

        syncMarketQuoteIntoEntries(symbol, payload) {
            const normalizedSymbol = this.normalizeMarketSymbol(symbol);
            if (!normalizedSymbol) {
                return;
            }
            const latestPrice = this.toNumber(payload && payload.quote && payload.quote.latest_close);
            const changePct = this.toNumber(payload && payload.quote && payload.quote.change_pct);
            const updatedAt = String(
                payload && payload.quote && payload.quote.latest_at
                || payload && payload.bars && payload.bars.length && payload.bars[payload.bars.length - 1].date
                || new Date().toISOString()
            ).trim();
            let changed = false;
            this.deskWatchlistEntries = this.deskWatchlistEntries.map((entry) => {
                if (entry.symbol !== normalizedSymbol) {
                    return entry;
                }
                changed = true;
                return {
                    ...entry,
                    name: entry.name || payload.name || normalizedSymbol,
                    assetType: entry.assetType || payload.asset_type || '',
                    marketDataSource: payload.source || entry.marketDataSource,
                    latestPrice,
                    changePct,
                    updatedAt,
                };
            });
            if (changed) {
                this.persistDeskWatchlistEntries();
            }
            if (this.marketFocusEntry && this.marketFocusEntry.symbol === normalizedSymbol) {
                this.marketFocusEntry = this.createDeskWatchlistItem({
                    symbol: normalizedSymbol,
                    name: payload.name || this.marketFocusEntry.quoteName || normalizedSymbol,
                    assetType: payload.asset_type || this.marketFocusEntry.assetType,
                    marketDataSource: payload.source || this.marketFocusEntry.marketDataSource,
                    latestPrice,
                    changePct,
                    updatedAt,
                    pinnedAt: updatedAt,
                }, { transient: true });
            }
            this.rebuildMarketWatchlist();
        },

        async loadMarketChartForSymbol(symbol, options = {}) {
            const normalizedSymbol = this.normalizeMarketSymbol(symbol);
            if (!normalizedSymbol) {
                return false;
            }
            const selected = this.activeMarketSignal();
            const resolvedAssetType = String(
                options.assetType
                || this.marketChart.assetType
                || (selected && selected.assetType)
                || ''
            ).trim().toLowerCase();
            const resolvedSource = this.guessMarketDataSource(
                normalizedSymbol,
                resolvedAssetType,
                options.source || this.marketChart.source
            );
            const resolvedPeriod = String(options.period || this.marketChart.period || '3mo').trim() || '3mo';

            this.marketChart.loading = true;
            this.marketChart.error = '';
            try {
                const params = new URLSearchParams({
                    period: resolvedPeriod,
                    source: resolvedSource,
                });
                if (resolvedAssetType) {
                    params.set('asset_type', resolvedAssetType);
                }
                const payload = await this.publicApiRequest(`/v1/market/chart/${encodeURIComponent(normalizedSymbol)}?${params.toString()}`);
                this.marketChart = {
                    ...this.marketChart,
                    symbol: normalizedSymbol,
                    name: String(
                        options.name
                        || (selected && selected.quoteName)
                        || normalizedSymbol
                    ).trim() || normalizedSymbol,
                    assetType: String(payload && payload.asset_type || resolvedAssetType).trim().toLowerCase(),
                    source: String(payload && payload.source || resolvedSource).trim() || resolvedSource,
                    period: String(payload && payload.period || resolvedPeriod).trim() || resolvedPeriod,
                    bars: Array.isArray(payload && payload.bars) ? payload.bars : [],
                    quote: payload && payload.quote ? payload.quote : this.marketChart.quote,
                    loading: false,
                    error: '',
                    lastLoadedAt: new Date().toISOString(),
                };
                this.syncMarketQuoteIntoEntries(normalizedSymbol, {
                    ...payload,
                    name: this.marketChart.name,
                });
                return true;
            } catch (error) {
                this.marketChart.loading = false;
                this.marketChart.error = error.message || '图表加载失败';
                if (options.throwOnError !== false) {
                    throw error;
                }
                return false;
            }
        },

        async loadSelectedMarketChart(options = {}) {
            const symbol = this.normalizeMarketSymbol(this.selectedSymbol || this.marketChart.symbol);
            if (!symbol) {
                return false;
            }
            return this.loadMarketChartForSymbol(symbol, options);
        },

        async openMarketSymbol(itemOrSymbol, options = {}) {
            const item = typeof itemOrSymbol === 'string'
                ? { symbol: itemOrSymbol }
                : (itemOrSymbol || {});
            const symbol = this.normalizeMarketSymbol(item.symbol || this.marketSearch.query);
            if (!symbol) {
                return;
            }
            const assetType = String(item.asset_type || item.assetType || '').trim().toLowerCase();
            const name = String(item.name || symbol).trim() || symbol;
            this.selectedSymbol = symbol;
            this.executionContextSource = String(options.source || 'market-workbench').trim() || 'market-workbench';
            this.executionContextUpdatedAt = new Date().toISOString();
            this.marketSearch.query = symbol;
            this.marketSearch.resultsVisible = false;
            this.marketFocusEntry = this.createDeskWatchlistItem({
                symbol,
                name,
                assetType,
                marketDataSource: this.guessMarketDataSource(symbol, assetType),
                pinnedAt: new Date().toISOString(),
            }, { transient: true });
            await this.loadMarketChartForSymbol(symbol, {
                assetType,
                name,
                source: options.sourceType,
                period: options.period || this.marketChart.period,
                throwOnError: false,
            });
            if (options.focusSection !== false && typeof this.focusSection === 'function') {
                this.focusSection('market-workbench-panel', 'signals', {
                    userInitiated: options.userInitiated !== false,
                });
            }
        },

        pinSelectedSymbolToDeskWatchlist() {
            const signal = this.activeMarketSignal();
            const symbol = this.normalizeMarketSymbol(
                this.selectedSymbol
                || this.marketChart.symbol
                || (signal && signal.symbol)
            );
            if (!symbol) {
                return;
            }
            const entry = {
                symbol,
                name: this.marketChart.name || (signal && signal.quoteName) || symbol,
                assetType: this.marketChart.assetType || (signal && signal.assetType) || '',
                marketDataSource: this.marketChart.source || (signal && signal.marketDataSource) || this.guessMarketDataSource(symbol),
                latestPrice: this.toNumber(this.marketChart.quote && this.marketChart.quote.latest_close),
                changePct: this.toNumber(this.marketChart.quote && this.marketChart.quote.change_pct),
                updatedAt: String(this.marketChart.quote && this.marketChart.quote.latest_at || new Date().toISOString()).trim(),
                pinnedAt: new Date().toISOString(),
            };
            if (this.upsertDeskWatchlistEntry(entry)) {
                this.log('ok', `${symbol} 已加入桌面盯盘。`);
            }
        },

        unpinSelectedSymbolFromDeskWatchlist() {
            const symbol = this.normalizeMarketSymbol(this.selectedSymbol || this.marketChart.symbol);
            if (!symbol) {
                return;
            }
            if (this.removeDeskWatchlistSymbol(symbol)) {
                this.log('info', `${symbol} 已从桌面盯盘移除。`);
            }
        },

        marketChartHasData() {
            return Array.isArray(this.marketChart.bars) && this.marketChart.bars.length > 1;
        },

        marketChartPriceBounds() {
            if (!this.marketChartHasData()) {
                return { min: 0, max: 1, range: 1 };
            }
            const lows = this.marketChart.bars.map((item) => this.toNumber(item.low));
            const highs = this.marketChart.bars.map((item) => this.toNumber(item.high));
            let min = Math.min(...lows);
            let max = Math.max(...highs);
            if (!Number.isFinite(min) || !Number.isFinite(max)) {
                return { min: 0, max: 1, range: 1 };
            }
            if (Math.abs(max - min) < 0.0001) {
                max += 1;
                min = Math.max(0, min - 1);
            }
            const padding = (max - min) * 0.08;
            return {
                min: Math.max(0, min - padding),
                max: max + padding,
                range: (max - min) + padding * 2,
            };
        },

        marketChartScaleY(value, bounds, areaTop, areaHeight) {
            const numericValue = this.toNumber(value);
            const ratio = bounds.range > 0
                ? (bounds.max - numericValue) / bounds.range
                : 0.5;
            return areaTop + ratio * areaHeight;
        },

        marketChartGridLines() {
            const bounds = this.marketChartPriceBounds();
            const areaTop = 16;
            const areaHeight = 188;
            return Array.from({ length: 4 }, (_, index) => {
                const ratio = index / 3;
                const value = bounds.max - bounds.range * ratio;
                return {
                    id: `grid-${index}`,
                    y: areaTop + areaHeight * ratio,
                    label: this.toFixed(value, value >= 100 ? 1 : 2),
                };
            });
        },

        marketChartCandles() {
            if (!this.marketChartHasData()) {
                return [];
            }
            const areaTop = 16;
            const areaHeight = 188;
            const width = 720;
            const bounds = this.marketChartPriceBounds();
            const bars = this.marketChart.bars;
            const slot = width / Math.max(bars.length, 1);
            const bodyWidth = Math.max(3, Math.min(12, slot * 0.58));
            return bars.map((bar, index) => {
                const open = this.toNumber(bar.open);
                const close = this.toNumber(bar.close);
                const high = this.toNumber(bar.high);
                const low = this.toNumber(bar.low);
                const xCenter = slot * index + slot / 2;
                const openY = this.marketChartScaleY(open, bounds, areaTop, areaHeight);
                const closeY = this.marketChartScaleY(close, bounds, areaTop, areaHeight);
                return {
                    id: `${bar.date}-${index}`,
                    xCenter,
                    wickTop: this.marketChartScaleY(high, bounds, areaTop, areaHeight),
                    wickBottom: this.marketChartScaleY(low, bounds, areaTop, areaHeight),
                    bodyX: xCenter - bodyWidth / 2,
                    bodyY: Math.min(openY, closeY),
                    bodyHeight: Math.max(1.25, Math.abs(openY - closeY)),
                    bodyWidth,
                    bullish: close >= open,
                };
            });
        },

        marketChartVolumeBars() {
            if (!this.marketChartHasData()) {
                return [];
            }
            const width = 720;
            const areaTop = 228;
            const areaHeight = 56;
            const slot = width / Math.max(this.marketChart.bars.length, 1);
            const bodyWidth = Math.max(2, Math.min(10, slot * 0.52));
            const maxVolume = Math.max(...this.marketChart.bars.map((item) => Number(item.volume || 0)), 1);
            return this.marketChart.bars.map((bar, index) => {
                const volume = Number(bar.volume || 0);
                const height = (volume / maxVolume) * areaHeight;
                const bullish = this.toNumber(bar.close) >= this.toNumber(bar.open);
                return {
                    id: `volume-${bar.date}-${index}`,
                    x: slot * index + slot / 2 - bodyWidth / 2,
                    y: areaTop + areaHeight - height,
                    width: bodyWidth,
                    height,
                    bullish,
                };
            });
        },

        marketChartTimeLabels() {
            if (!this.marketChartHasData()) {
                return [];
            }
            const bars = this.marketChart.bars;
            const width = 720;
            const indexes = Array.from(new Set([
                0,
                Math.floor((bars.length - 1) / 3),
                Math.floor(((bars.length - 1) * 2) / 3),
                bars.length - 1,
            ])).filter((index) => index >= 0 && index < bars.length);
            return indexes.map((index) => ({
                id: `label-${index}`,
                x: (width / Math.max(bars.length, 1)) * index + 8,
                label: this.formatDateShort(bars[index].date),
            }));
        },

        marketChartOverlayLines() {
            const signal = this.activeMarketSignal();
            if (!signal || !this.marketChartHasData()) {
                return [];
            }
            const bounds = this.marketChartPriceBounds();
            const areaTop = 16;
            const areaHeight = 188;
            return [
                { id: 'entry', label: 'Entry', value: this.toNumber(signal.entryPrice), color: '#0f766e' },
                { id: 'stop', label: 'Stop', value: this.toNumber(signal.stopLoss), color: '#ef4444' },
                { id: 'tp1', label: 'TP1', value: this.toNumber(signal.takeProfit1), color: '#f59e0b' },
            ]
                .filter((item) => item.value > 0)
                .map((item) => ({
                    ...item,
                    y: this.marketChartScaleY(item.value, bounds, areaTop, areaHeight),
                    valueLabel: this.toFixed(item.value, item.value >= 100 ? 1 : 2),
                }));
        },

        marketChartLastLabel() {
            if (!this.marketChart.lastLoadedAt) {
                return '--';
            }
            return this.formatDateTime(this.marketChart.lastLoadedAt);
        },

        marketQuoteDirectionClass() {
            const change = this.toNumber(this.marketChart.quote && this.marketChart.quote.change);
            if (change > 0.0001) {
                return 'text-mint';
            }
            if (change < -0.0001) {
                return 'text-coral';
            }
            return 'text-ink/65';
        },

        marketQuoteDirectionBadgeClass() {
            const change = this.toNumber(this.marketChart.quote && this.marketChart.quote.change);
            if (change > 0.0001) {
                return 'border-mint/25 bg-mint/10 text-mint';
            }
            if (change < -0.0001) {
                return 'border-coral/25 bg-coral/10 text-coral';
            }
            return 'border-ink/15 bg-white/85 text-ink/70';
        },

        marketSourceLabel() {
            const source = String(this.marketChart.source || '').trim().toLowerCase();
            if (source === 'binance') {
                return 'Binance';
            }
            return 'Yahoo';
        },

        formatDateShort(value) {
            if (!value) {
                return '--';
            }
            const date = value instanceof Date ? value : new Date(value);
            if (Number.isNaN(date.getTime())) {
                return '--';
            }
            return `${date.getUTCMonth() + 1}/${date.getUTCDate()}`;
        },
    };
}

window.PlatformDeckMarket = {
    createState: createPlatformDeckMarketState,
    createModule: createPlatformDeckMarketModule,
};