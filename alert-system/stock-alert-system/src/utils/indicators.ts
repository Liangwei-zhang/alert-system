import { StockData, TechnicalIndicators } from '../types';

export function calculateEMA(prices: number[], period: number): number[] {
  if (prices.length === 0) return [];
  const k = 2 / (period + 1);
  const ema: number[] = [prices[0]];
  for (let i = 1; i < prices.length; i++) {
    ema.push(prices[i] * k + ema[i - 1] * (1 - k));
  }
  return ema;
}

export function calculateSMA(prices: number[], period: number): number[] {
  const sma: number[] = [];
  for (let i = 0; i < prices.length; i++) {
    if (i < period - 1) {
      sma.push(0);
    } else {
      const sum = prices.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
      sma.push(sum / period);
    }
  }
  return sma;
}

export function calculateMACD(prices: number[]) {
  if (prices.length < 26) {
    return { dif: [0], dea: [0], histogram: [0] };
  }
  const ema12 = calculateEMA(prices, 12);
  const ema26 = calculateEMA(prices, 26);
  const dif = ema12.map((v, i) => v - ema26[i]);
  const dea = calculateEMA(dif, 9);
  const histogram = dif.map((v, i) => (v - dea[i]) * 2);
  return { dif, dea, histogram };
}

export function calculateKDJ(
  highs: number[],
  lows: number[],
  closes: number[],
  period: number = 9
): { k: number[]; d: number[]; j: number[] } {
  const k: number[] = [50];
  const d: number[] = [50];

  for (let i = 1; i < closes.length; i++) {
    const startIdx = Math.max(0, i - period + 1);
    const recentHighs = highs.slice(startIdx, i + 1);
    const recentLows = lows.slice(startIdx, i + 1);
    const hn = Math.max(...recentHighs);
    const ln = Math.min(...recentLows);
    const rsv = hn === ln ? 50 : ((closes[i] - ln) / (hn - ln)) * 100;

    k.push(k[i - 1] * (2 / 3) + rsv * (1 / 3));
    d.push(d[i - 1] * (2 / 3) + k[i] * (1 / 3));
  }

  const j = k.map((v, i) => 3 * v - 2 * d[i]);
  return { k, d, j };
}

export function calculateRSI(prices: number[], period: number = 14): number[] {
  const changes = prices.map((p, i) => (i === 0 ? 0 : p - prices[i - 1]));
  const gains = changes.map((c) => (c > 0 ? c : 0));
  const losses = changes.map((c) => (c < 0 ? -c : 0));

  const rsi: number[] = [];
  let avgGain = 0;
  let avgLoss = 0;

  for (let i = 0; i < prices.length; i++) {
    if (i < period) {
      rsi.push(50);
      avgGain += gains[i] / period;
      avgLoss += losses[i] / period;
    } else {
      avgGain = (avgGain * (period - 1) + gains[i]) / period;
      avgLoss = (avgLoss * (period - 1) + losses[i]) / period;
      const rs = avgGain / (avgLoss || 1);
      rsi.push(100 - 100 / (1 + rs));
    }
  }

  return rsi;
}

export function calculateBollingerBands(
  prices: number[],
  period: number = 20,
  stdDev: number = 2
): { upper: number; middle: number; lower: number }[] {
  const result: { upper: number; middle: number; lower: number }[] = [];

  for (let i = 0; i < prices.length; i++) {
    if (i < period - 1) {
      result.push({ upper: 0, middle: 0, lower: 0 });
    } else {
      const recentPrices = prices.slice(i - period + 1, i + 1);
      const sma = recentPrices.reduce((a, b) => a + b, 0) / period;
      const variance =
        recentPrices.reduce((sum, p) => sum + Math.pow(p - sma, 2), 0) / period;
      const std = Math.sqrt(variance);
      result.push({
        upper: sma + stdDev * std,
        middle: sma,
        lower: sma - stdDev * std,
      });
    }
  }

  return result;
}

export function calculateAllIndicators(data: StockData[]): TechnicalIndicators {
  const prices = data.map((d) => d.close);
  const highs = data.map((d) => d.high);
  const lows = data.map((d) => d.low);

  const latest = data.length - 1;
  if (latest < 0) {
    return {
      ma5: 0, ma10: 0, ma20: 0, ma60: 0,
      macdDif: 0, macdDea: 0, macdHistogram: 0,
      kdjK: 50, kdjD: 50, kdjJ: 50,
      rsi6: 50, rsi12: 50, rsi24: 50,
      bollUp: 0, bollMb: 0, bollDn: 0,
    };
  }

  const ma5Arr = calculateSMA(prices, 5);
  const ma10Arr = calculateSMA(prices, 10);
  const ma20Arr = calculateSMA(prices, 20);
  const ma60Arr = calculateSMA(prices, 60);
  const macd = calculateMACD(prices);
  const kdj = calculateKDJ(highs, lows, prices);
  const rsi6Arr = calculateRSI(prices, 6);
  const rsi12Arr = calculateRSI(prices, 12);
  const rsi24Arr = calculateRSI(prices, 24);
  const boll = calculateBollingerBands(prices);

  return {
    ma5: ma5Arr[latest] || 0,
    ma10: ma10Arr[latest] || 0,
    ma20: ma20Arr[latest] || 0,
    ma60: ma60Arr[latest] || 0,
    macdDif: macd.dif[latest] || 0,
    macdDea: macd.dea[latest] || 0,
    macdHistogram: macd.histogram[latest] || 0,
    kdjK: kdj.k[latest] || 50,
    kdjD: kdj.d[latest] || 50,
    kdjJ: kdj.j[latest] || 50,
    rsi6: rsi6Arr[latest] || 50,
    rsi12: rsi12Arr[latest] || 50,
    rsi24: rsi24Arr[latest] || 50,
    bollUp: boll[latest]?.upper || 0,
    bollMb: boll[latest]?.middle || 0,
    bollDn: boll[latest]?.lower || 0,
  };
}

export function getPreviousIndicators(data: StockData[], offset: number = 1): TechnicalIndicators {
  if (data.length <= offset) {
    return calculateAllIndicators(data);
  }
  return calculateAllIndicators(data.slice(0, data.length - offset));
}

export function getAverageVolume(data: StockData[], period: number = 5): number {
  if (data.length < period) {
    return data.reduce((sum, d) => sum + d.volume, 0) / (data.length || 1);
  }
  const recentVolumes = data.slice(-period).map((d) => d.volume);
  return recentVolumes.reduce((a, b) => a + b, 0) / period;
}
