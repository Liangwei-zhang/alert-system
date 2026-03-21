/**
 * stockService.ts  ── 动态自选股 + 三级数据优先级
 *
 * 优先级：真实数据(Yahoo Finance) > IndexedDB缓存 > 模拟数据
 *
 * 初始化流程：
 *   1. 从 IndexedDB 加载 watchlist（默认 3 只）
 *   2. 每个 symbol：先读 DB 历史 → 后台拉 Yahoo 真实历史替换
 *   3. 每 20s updateStocks()：拉真实报价 → 失败则模拟 tick
 *   4. 新数据实时写入 DB，保留 6 个月
 */

import { StockData, KLineData, WatchlistItem, SymbolMeta, DataSource } from '../types';
import {
  getWatchlist, upsertWatchlistItem, removeWatchlistItem,
  getHistory, saveHistory, clearSymbolHistory, pruneOldHistory,
  SIX_MONTHS_MS,
} from './storageService';
import { getSymbolInfo, POPULAR_ASSETS } from './searchService';

// ─── Yahoo Finance ────────────────────────────────────────────────────────────

const PROXY = 'https://api.allorigins.win/raw?url=';
const YAHOO = 'https://query1.finance.yahoo.com/v8/finance/chart';

function fetchTO(url: string, ms = 8000): Promise<Response> {
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), ms);
  return fetch(url, { signal: c.signal }).finally(() => clearTimeout(t));
}

async function fetchYahooHistory(symbol: string, name: string): Promise<StockData[]> {
  const raw = `${YAHOO}/${symbol}?interval=1d&range=6mo&includePrePost=false`;
  const res = await fetchTO(`${PROXY}${encodeURIComponent(raw)}`, 10000);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json = await res.json();
  const r    = json?.chart?.result?.[0];
  if (!r) throw new Error('empty response');

  const ts: number[]  = r.timestamp ?? [];
  const q              = r.indicators?.quote?.[0] ?? {};
  const opens          = q.open   as (number | null)[];
  const highs          = q.high   as (number | null)[];
  const lows           = q.low    as (number | null)[];
  const closes         = q.close  as (number | null)[];
  const vols           = q.volume as (number | null)[];

  const data: StockData[] = [];
  for (let i = 0; i < ts.length; i++) {
    const c = closes[i]; if (!c || isNaN(c)) continue;
    const prev = data[data.length - 1];
    const chg  = prev ? c - prev.close : 0;
    data.push({
      symbol, name,
      price: c, close: c,
      change: chg, changePercent: prev ? (chg / prev.close) * 100 : 0,
      volume: vols[i] || 0,
      open: opens[i] || c, high: highs[i] || c, low: lows[i] || c,
      timestamp: ts[i] * 1000,
    });
  }
  if (data.length < 20) throw new Error('insufficient data');
  return data;
}

async function fetchYahooQuote(symbol: string): Promise<
  { price: number; change: number; changePercent: number; volume: number } | null
> {
  try {
    const raw = `${YAHOO}/${symbol}?interval=1m&range=1d&includePrePost=false`;
    const res = await fetchTO(`${PROXY}${encodeURIComponent(raw)}`, 6000);
    if (!res.ok) return null;
    const json = await res.json();
    const meta = json?.chart?.result?.[0]?.meta as Record<string, unknown> | undefined;
    if (!meta) return null;
    const price = meta.regularMarketPrice as number;
    if (!price || isNaN(price)) return null;
    const prev  = (meta.chartPreviousClose ?? meta.previousClose ?? price) as number;
    const chg   = price - prev;
    return { price, change: chg, changePercent: prev ? (chg / prev) * 100 : 0,
      volume: (meta.regularMarketVolume ?? 0) as number };
  } catch { return null; }
}

// ─── 模拟数据 ─────────────────────────────────────────────────────────────────

function genSimulated(symbol: string, name: string, basePrice = 100, vol = 0.02, days = 120): StockData[] {
  const data: StockData[] = [];
  let price = basePrice * (0.9 + Math.random() * 0.2);
  const now  = Date.now(), dayMs = 86400000;
  let tDir = 1, tDown = 5 + Math.floor(Math.random() * 10);

  for (let i = days; i >= 0; i--) {
    const ts  = now - i * dayMs;
    const dow = new Date(ts).getDay();
    if (dow === 0 || dow === 6) continue;
    if (--tDown <= 0) { tDir = Math.random() > 0.45 ? 1 : -1; tDown = 5 + Math.floor(Math.random() * 10); }
    const o  = price * (1 + (Math.random() - 0.5) * 0.01);
    const c  = Math.max(0.01, o + tDir * vol * price * 0.4 + (Math.random() - 0.5) * vol * price);
    const h  = Math.max(o, c) * (1 + Math.random() * 0.015);
    const l  = Math.min(o, c) * (1 - Math.random() * 0.015);
    const pr = data[data.length - 1];
    const chg = pr ? c - pr.close : 0;
    data.push({ symbol, name, price: c, close: c,
      change: chg, changePercent: pr ? (chg / pr.close) * 100 : 0,
      volume: basePrice * 1e6 * (0.5 + Math.random() * 1.5) * 0.0001,
      open: o, high: h, low: l, timestamp: ts });
    price = c;
  }
  return data;
}

function simTick(last: StockData, vol = 0.02): StockData {
  const chg   = (Math.random() - 0.5) * 2 * vol * last.price + (Math.random() > 0.5 ? 1 : -1) * last.price * vol * 0.3;
  const price = Math.max(0.01, last.price + chg);
  return {
    ...last,
    price, close: price,
    change: price - last.price,
    changePercent: ((price - last.price) / last.price) * 100,
    open:   last.price,
    high:   Math.max(last.price, price) * (1 + Math.random() * 0.005),
    low:    Math.min(last.price, price) * (1 - Math.random() * 0.005),
    timestamp: Date.now(),
  };
}

// ─── 资产基础价格估算（期货/指数没有 basePrice 时用于模拟）────────────────────

const BASE_PRICES: Record<string, number> = {
  'GC=F': 2400, 'SI=F': 30, 'CL=F': 75, 'BZ=F': 80,
  'NG=F': 2.5,  'HG=F': 4.5, 'PL=F': 1000,
  '^GSPC': 5400, '^DJI': 39000, '^IXIC': 17000, '^VIX': 18,
  'GLD': 220, 'SLV': 27, 'USO': 75,
  'SPY': 540, 'QQQ': 440, 'IWM': 205, 'TLT': 94,
};

const BASE_VOLS: Record<string, number> = {
  'GC=F': 0.01, 'SI=F': 0.025, 'CL=F': 0.025, 'BZ=F': 0.025,
  'NG=F': 0.04, 'HG=F': 0.02, 'PL=F': 0.015,
  '^GSPC': 0.012, '^DJI': 0.012, '^IXIC': 0.015, '^VIX': 0.08,
};

// ─── StockService ─────────────────────────────────────────────────────────────

class StockService {
  private watchlist  = new Map<string, WatchlistItem>();
  private data       = new Map<string, StockData[]>();
  private meta       = new Map<string, SymbolMeta>();
  private initialized = false;

  // ── 初始化 ────────────────────────────────────────────────────────────────

  async init(): Promise<void> {
    if (this.initialized) return;
    this.initialized = true;

    // 1. 从 DB 加载自选股列表
    let stored = await getWatchlist();

    // 首次使用：写入默认 3 只股票
    if (!stored.length) {
      const defaults: WatchlistItem[] = [
        { symbol: 'AAPL', name: '苹果公司',  addedAt: Date.now(), assetType: 'equity',  exchange: 'NMS' },
        { symbol: 'TSLA', name: '特斯拉',    addedAt: Date.now(), assetType: 'equity',  exchange: 'NMS' },
        { symbol: 'MSFT', name: '微软公司',  addedAt: Date.now(), assetType: 'equity',  exchange: 'NMS' },
      ];
      for (const d of defaults) await upsertWatchlistItem(d);
      stored = defaults;
    }

    // 2. 注册到内存（立即可用）
    for (const item of stored) {
      this.watchlist.set(item.symbol, item);
      this.meta.set(item.symbol, { source: 'simulated', lastUpdated: 0 });
    }

    // 3. 逐个加载历史数据（DB → 模拟）
    for (const item of stored) {
      await this._loadSymbolData(item);
    }

    // 4. 后台拉真实历史（不阻塞 UI）
    this._refreshAllHistories();

    // 5. 定期清理过期数据
    setTimeout(() => pruneOldHistory(), 5000);
  }

  // ── 内部：加载单个 symbol 数据（DB > 模拟）────────────────────────────────

  private async _loadSymbolData(item: WatchlistItem): Promise<void> {
    // 先尝试 DB
    const dbData = await getHistory(item.symbol, item.name);
    if (dbData.length >= 10) {
      this.data.set(item.symbol, dbData.slice(-120));
      this.meta.set(item.symbol, { source: 'database', lastUpdated: dbData[dbData.length - 1].timestamp });
      return;
    }
    // 回退：模拟
    const base = BASE_PRICES[item.symbol] ?? 100;
    const vol  = BASE_VOLS[item.symbol]   ?? 0.02;
    const sim  = genSimulated(item.symbol, item.name, base, vol);
    this.data.set(item.symbol, sim);
    this.meta.set(item.symbol, { source: 'simulated', lastUpdated: Date.now() });
  }

  // ── 内部：后台拉真实历史 ──────────────────────────────────────────────────

  private async _refreshAllHistories(): Promise<void> {
    for (const item of this.watchlist.values()) {
      await this._fetchRealHistory(item);
      await new Promise(r => setTimeout(r, 300)); // 避免请求风暴
    }
  }

  private async _fetchRealHistory(item: WatchlistItem): Promise<void> {
    try {
      const hist = await fetchYahooHistory(item.symbol, item.name);
      this.data.set(item.symbol, hist.slice(-120));
      this.meta.set(item.symbol, { source: 'real', lastUpdated: Date.now() });
      await saveHistory(hist);
      console.info(`✅ ${item.symbol} 真实历史已加载 (${hist.length} 根)`);
    } catch (e) {
      console.warn(`⚠️ ${item.symbol} 真实历史加载失败`, e);
    }
  }

  // ── 公开：更新报价（每 20s 调用）────────────────────────────────────────────

  async updateStocks(): Promise<void> {
    const symbols = Array.from(this.watchlist.keys());
    await Promise.allSettled(symbols.map(s => this._updateSymbol(s)));
  }

  private async _updateSymbol(symbol: string): Promise<void> {
    const item = this.watchlist.get(symbol);
    if (!item) return;
    const cur  = this.data.get(symbol) ?? [];

    const quote = await fetchYahooQuote(symbol);
    if (quote) {
      const prev = cur[cur.length - 1];
      const entry: StockData = {
        symbol, name: item.name,
        price: quote.price, close: quote.price,
        change: quote.change, changePercent: quote.changePercent,
        volume: quote.volume || prev?.volume || 0,
        open:   prev?.open ?? quote.price,
        high:   prev ? Math.max(prev.high, quote.price) : quote.price,
        low:    prev ? Math.min(prev.low,  quote.price) : quote.price,
        timestamp: Date.now(),
      };
      const updated = cur.length > 0 ? [...cur.slice(0, -1), entry] : [entry];
      this.data.set(symbol, updated.slice(-120));
      this.meta.set(symbol, { source: 'real', lastUpdated: Date.now() });
      // 异步写 DB，不阻塞
      saveHistory([entry]).catch(() => {});
    } else {
      // 模拟 tick
      if (cur.length > 0) {
        const vol  = BASE_VOLS[symbol] ?? 0.02;
        const next = simTick(cur[cur.length - 1], vol);
        this.data.set(symbol, [...cur.slice(0, -1), next].slice(-120));
        // 如果已有真实数据，保持 source 不变；否则标为 simulated
        if (this.meta.get(symbol)?.source !== 'real') {
          this.meta.set(symbol, { source: this.meta.get(symbol)?.source ?? 'simulated', lastUpdated: Date.now() });
        }
      }
    }
  }

  // ── 公开：添加 symbol ────────────────────────────────────────────────────

  async addSymbol(item: WatchlistItem): Promise<void> {
    if (this.watchlist.has(item.symbol)) return; // 已存在

    this.watchlist.set(item.symbol, item);
    this.meta.set(item.symbol, { source: 'simulated', lastUpdated: 0 });

    // 先用模拟数据填充，保证立即显示
    const base = BASE_PRICES[item.symbol] ?? 100;
    const vol  = BASE_VOLS[item.symbol]   ?? 0.02;
    this.data.set(item.symbol, genSimulated(item.symbol, item.name, base, vol));

    // 持久化到 DB
    await upsertWatchlistItem(item);

    // 后台加载真实历史
    await this._loadSymbolData(item);    // DB > simulated
    this._fetchRealHistory(item);        // real (background)
  }

  // ── 公开：移除 symbol ────────────────────────────────────────────────────

  async removeSymbol(symbol: string): Promise<void> {
    this.watchlist.delete(symbol);
    this.data.delete(symbol);
    this.meta.delete(symbol);
    await removeWatchlistItem(symbol);
    // DB 历史数据保留（可选择保留或清除）
    // await clearSymbolHistory(symbol);
  }

  // ── 只读访问 ─────────────────────────────────────────────────────────────

  getWatchlist(): WatchlistItem[] {
    return Array.from(this.watchlist.values()).sort((a, b) => a.addedAt - b.addedAt);
  }

  getStocks(): StockData[] {
    return this.getWatchlist()
      .map(item => {
        const d = this.data.get(item.symbol);
        return d?.length ? d[d.length - 1] : null;
      })
      .filter((d): d is StockData => d !== null);
  }

  getStockHistory(symbol: string): StockData[] {
    return this.data.get(symbol) ?? [];
  }

  getKLineData(symbol: string): KLineData[] {
    return this.getStockHistory(symbol).map(d => ({
      time: Math.floor(d.timestamp / 1000),
      open: d.open, high: d.high, low: d.low, close: d.price, volume: d.volume,
    }));
  }

  getSymbolMeta(symbol: string): SymbolMeta {
    return this.meta.get(symbol) ?? { source: 'simulated', lastUpdated: 0 };
  }

  getAvailableStocks(): string[] {
    return Array.from(this.watchlist.keys());
  }

  hasSymbol(symbol: string): boolean {
    return this.watchlist.has(symbol);
  }

  isInitialized(): boolean { return this.initialized; }
}

export const stockService = new StockService();
