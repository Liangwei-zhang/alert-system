import { StockData, TechnicalIndicators, StockAnalysis, SignalResult, PredictionResult } from '../types';
import { calculateAllIndicators } from '../utils/indicators';
import { detectBuySignal, detectSellSignal } from '../utils/signals';
import { predictTopBottom } from '../utils/prediction';
import { stockService } from './stockService';

class IndicatorService {
  analyzeStock(symbol: string): StockAnalysis | null {
    const history = stockService.getStockHistory(symbol);
    if (history.length === 0) {
      return null;
    }

    const currentPrice = history[history.length - 1].price;
    const indicators = calculateAllIndicators(history);
    const buySignal = detectBuySignal(history);
    const sellSignal = detectSellSignal(history);
    const prediction = predictTopBottom(history);

    return {
      symbol,
      price: currentPrice,
      indicators,
      buySignal,
      sellSignal,
      prediction,
    };
  }

  getIndicators(symbol: string): TechnicalIndicators | null {
    const history = stockService.getStockHistory(symbol);
    if (history.length === 0) {
      return null;
    }
    return calculateAllIndicators(history);
  }

  getBuySignal(symbol: string): SignalResult {
    const history = stockService.getStockHistory(symbol);
    if (history.length === 0) {
      return { signal: false, level: null, score: 0, reasons: [] };
    }
    return detectBuySignal(history);
  }

  getSellSignal(symbol: string): SignalResult {
    const history = stockService.getStockHistory(symbol);
    if (history.length === 0) {
      return { signal: false, level: null, score: 0, reasons: [] };
    }
    return detectSellSignal(history);
  }

  getPrediction(symbol: string): PredictionResult {
    const history = stockService.getStockHistory(symbol);
    if (history.length === 0) {
      return { type: 'neutral', probability: 0, signals: [], recommendation: '数据不足，无法预测' };
    }
    return predictTopBottom(history);
  }

  analyzeAllStocks(symbols: string[]): Map<string, StockAnalysis> {
    const results = new Map<string, StockAnalysis>();
    symbols.forEach((symbol) => {
      const analysis = this.analyzeStock(symbol);
      if (analysis) {
        results.set(symbol, analysis);
      }
    });
    return results;
  }
}

export const indicatorService = new IndicatorService();
