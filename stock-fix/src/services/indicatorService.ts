/**
 * indicatorService.ts
 *
 * Bug-12 修复：per-cycle 分析缓存
 * - analyzeStock 是唯一计算入口，每个 symbol 每个周期只算一次
 * - getBuySignal / getSellSignal / getPrediction 全部委托给 analyzeStock
 *   原本它们各自独立触发完整计算，现在不再重算
 * - invalidateCache() 在每次数据更新前由外部（App.tsx）调用，
 *   确保新周期拿到最新分析结果
 */

import { StockData, TechnicalIndicators, StockAnalysis, SignalResult, PredictionResult } from '../types';
import { calculateAllIndicators } from '../utils/indicators';
import { detectBuySignal, detectSellSignal } from '../utils/signals';
import { predictTopBottom } from '../utils/prediction';
import { stockService } from './stockService';

class IndicatorService {
  // 周期缓存：symbol → 当前周期的分析结果
  private cycleCache = new Map<string, StockAnalysis>();

  /** 由 App.tsx 在每次 updateUI() 前调用，清除上一周期缓存 */
  invalidateCache(): void {
    this.cycleCache.clear();
  }

  /** 核心入口：每个周期每个 symbol 只计算一次，后续调用命中缓存 */
  analyzeStock(symbol: string): StockAnalysis | null {
    // 缓存命中
    const cached = this.cycleCache.get(symbol);
    if (cached) return cached;

    const history = stockService.getStockHistory(symbol);
    if (history.length === 0) return null;

    const indicators = calculateAllIndicators(history);
    const buySignal  = detectBuySignal(history);
    const sellSignal = detectSellSignal(history);
    const prediction = predictTopBottom(history);

    const analysis: StockAnalysis = {
      symbol,
      price: history[history.length - 1].price,
      indicators,
      buySignal,
      sellSignal,
      prediction,
    };

    this.cycleCache.set(symbol, analysis);
    return analysis;
  }

  // ── 以下全部委托给 analyzeStock，不单独计算 ──────────────────────

  getIndicators(symbol: string): TechnicalIndicators | null {
    return this.analyzeStock(symbol)?.indicators ?? null;
  }

  getBuySignal(symbol: string): SignalResult {
    return this.analyzeStock(symbol)?.buySignal
      ?? { signal: false, level: null, score: 0, reasons: [] };
  }

  getSellSignal(symbol: string): SignalResult {
    return this.analyzeStock(symbol)?.sellSignal
      ?? { signal: false, level: null, score: 0, reasons: [] };
  }

  getPrediction(symbol: string): PredictionResult {
    return this.analyzeStock(symbol)?.prediction
      ?? { type: 'neutral', probability: 0, signals: [], recommendation: '数据不足，无法预测' };
  }

  analyzeAllStocks(symbols: string[]): Map<string, StockAnalysis> {
    const results = new Map<string, StockAnalysis>();
    for (const sym of symbols) {
      const a = this.analyzeStock(sym);
      if (a) results.set(sym, a);
    }
    return results;
  }
}

export const indicatorService = new IndicatorService();
