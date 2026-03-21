import { StockData, PredictionResult } from '../types';
import { calculateAllIndicators, calculateMACD } from './indicators';

function findLocalLows(data: StockData[], lookback: number = 20): StockData[] {
  if (data.length < 3) return [];
  const recentData = data.slice(-lookback);
  const lows: StockData[] = [];

  for (let i = 1; i < recentData.length - 1; i++) {
    if (
      recentData[i].low < recentData[i - 1].low &&
      recentData[i].low < recentData[i + 1].low
    ) {
      lows.push(recentData[i]);
    }
  }

  return lows;
}

function findLocalHighs(data: StockData[], lookback: number = 20): StockData[] {
  if (data.length < 3) return [];
  const recentData = data.slice(-lookback);
  const highs: StockData[] = [];

  for (let i = 1; i < recentData.length - 1; i++) {
    if (
      recentData[i].high > recentData[i - 1].high &&
      recentData[i].high > recentData[i + 1].high
    ) {
      highs.push(recentData[i]);
    }
  }

  return highs;
}

function detectBullishDivergence(data: StockData[]): boolean {
  if (data.length < 20) return false;

  const lows = findLocalLows(data, 20);
  if (lows.length < 2) return false;

  const low1 = lows[lows.length - 2];
  const low2 = lows[lows.length - 1];

  if (low2.low >= low1.low) return false;

  const low1Idx = data.findIndex((d) => d.timestamp === low1.timestamp);
  const low2Idx = data.findIndex((d) => d.timestamp === low2.timestamp);

  if (low1Idx === -1 || low2Idx === -1) return false;

  const prices1 = data.slice(Math.max(0, low1Idx - 10), low1Idx + 1).map((d) => d.close);
  const prices2 = data.slice(Math.max(0, low2Idx - 10), low2Idx + 1).map((d) => d.close);

  if (prices1.length < 5 || prices2.length < 5) return false;

  const macd1 = calculateMACD(prices1);
  const macd2 = calculateMACD(prices2);

  const macdLow1 = Math.min(...macd1.dif);
  const macdLow2 = Math.min(...macd2.dif);

  return macdLow2 > macdLow1;
}

function detectBearishDivergence(data: StockData[]): boolean {
  if (data.length < 20) return false;

  const highs = findLocalHighs(data, 20);
  if (highs.length < 2) return false;

  const high1 = highs[highs.length - 2];
  const high2 = highs[highs.length - 1];

  if (high2.high <= high1.high) return false;

  const high1Idx = data.findIndex((d) => d.timestamp === high1.timestamp);
  const high2Idx = data.findIndex((d) => d.timestamp === high2.timestamp);

  if (high1Idx === -1 || high2Idx === -1) return false;

  const prices1 = data.slice(Math.max(0, high1Idx - 10), high1Idx + 1).map((d) => d.close);
  const prices2 = data.slice(Math.max(0, high2Idx - 10), high2Idx + 1).map((d) => d.close);

  if (prices1.length < 5 || prices2.length < 5) return false;

  const macd1 = calculateMACD(prices1);
  const macd2 = calculateMACD(prices2);

  const macdHigh1 = Math.max(...macd1.dif);
  const macdHigh2 = Math.max(...macd2.dif);

  return macdHigh2 < macdHigh1;
}

export function predictTopBottom(data: StockData[]): PredictionResult {
  if (data.length < 20) {
    return {
      type: 'neutral',
      probability: 0,
      signals: [],
      recommendation: '数据不足，无法预测',
    };
  }

  const signals: string[] = [];
  let topScore = 0;
  let bottomScore = 0;

  const latest = calculateAllIndicators(data);
  const currentData = data[data.length - 1];

  if (detectBullishDivergence(data)) {
    signals.push('MACD底背离');
    bottomScore += 30;
  }

  if (detectBearishDivergence(data)) {
    signals.push('MACD顶背离');
    topScore += 30;
  }

  if (latest.rsi24 > 80) {
    signals.push('RSI严重超买');
    topScore += 20;
  } else if (latest.rsi24 < 20) {
    signals.push('RSI严重超卖');
    bottomScore += 20;
  }

  if (latest.bollUp > 0 && currentData.close > latest.bollUp) {
    signals.push('突破布林带上轨');
    topScore += 15;
  } else if (latest.bollDn > 0 && currentData.close < latest.bollDn) {
    signals.push('跌破布林带下轨');
    bottomScore += 15;
  }

  if (latest.kdjJ > 100) {
    signals.push('KDJ严重超买');
    topScore += 10;
  } else if (latest.kdjJ < 0) {
    signals.push('KDJ严重超卖');
    bottomScore += 10;
  }

  if (topScore > bottomScore && topScore >= 50) {
    return {
      type: 'top',
      probability: Math.min(topScore / 100, 0.95),
      signals,
      recommendation: '可能接近顶部，建议逐步减仓或观望',
    };
  } else if (bottomScore > topScore && bottomScore >= 50) {
    return {
      type: 'bottom',
      probability: Math.min(bottomScore / 100, 0.95),
      signals,
      recommendation: '可能接近底部，建议分批建仓或加仓',
    };
  }

  return {
    type: 'neutral',
    probability: 0,
    signals: [],
    recommendation: '未检测到明显顶底信号，保持观察',
  };
}
