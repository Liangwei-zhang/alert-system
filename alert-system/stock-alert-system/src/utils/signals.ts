import { StockData, SignalResult } from '../types';
import { calculateAllIndicators, getPreviousIndicators, getAverageVolume } from './indicators';

export function detectBuySignal(data: StockData[]): SignalResult {
  if (data.length < 2) {
    return { signal: false, level: null, score: 0, reasons: [] };
  }

  const latest = calculateAllIndicators(data);
  const prev = getPreviousIndicators(data, 1);
  const currentData = data[data.length - 1];
  const avgVolume = getAverageVolume(data);

  let score = 0;
  const reasons: string[] = [];

  if (latest.macdDif > latest.macdDea && prev.macdDif <= prev.macdDea) {
    score += 20;
    reasons.push('MACD金叉');
    if (latest.macdDif > 0) {
      score += 10;
      reasons.push('MACD零轴上方金叉');
    }
  }

  if (latest.kdjK > latest.kdjD && prev.kdjK <= prev.kdjD && latest.kdjK < 50) {
    score += 20;
    reasons.push('KDJ低位金叉');
    if (latest.kdjK < 20) {
      score += 10;
      reasons.push('KDJ超卖区反弹');
    }
  }

  if (prev.rsi24 < 30 && latest.rsi24 > prev.rsi24) {
    score += 15;
    reasons.push('RSI超卖反弹');
  }

  if (latest.ma5 > latest.ma10 && prev.ma5 <= prev.ma10) {
    score += 15;
    reasons.push('MA5上穿MA10');
  }

  if (latest.ma20 > 0 && currentData.close > latest.ma20 && data[data.length - 2].close <= prev.ma20) {
    score += 10;
    reasons.push('股价突破20日均线');
  }

  if (currentData.volume > avgVolume * 1.5) {
    score += 15;
    reasons.push('成交量放大');
  }

  const prevData = data[data.length - 2];
  if (prevData.close < prev.bollDn && currentData.close > latest.bollDn && latest.bollDn > 0) {
    score += 10;
    reasons.push('布林带下轨反弹');
  }

  let level: 'high' | 'medium' | 'low' | null = null;
  let signal = false;

  if (score >= 60 && reasons.length >= 3) {
    level = 'high';
    signal = true;
  } else if (score >= 40 && reasons.length >= 2) {
    level = 'medium';
    signal = true;
  } else if (score >= 20) {
    level = 'low';
    signal = true;
  }

  return { signal, level, score, reasons };
}

export function detectSellSignal(data: StockData[]): SignalResult {
  if (data.length < 2) {
    return { signal: false, level: null, score: 0, reasons: [] };
  }

  const latest = calculateAllIndicators(data);
  const prev = getPreviousIndicators(data, 1);
  const currentData = data[data.length - 1];
  const prevData = data[data.length - 2];
  const avgVolume = getAverageVolume(data);

  let score = 0;
  const reasons: string[] = [];

  if (latest.macdDif < latest.macdDea && prev.macdDif >= prev.macdDea) {
    score += 20;
    reasons.push('MACD死叉');
    if (latest.macdDif < 0) {
      score += 10;
      reasons.push('MACD零轴下方死叉');
    }
  }

  if (latest.kdjK < latest.kdjD && prev.kdjK >= prev.kdjD && latest.kdjK > 50) {
    score += 20;
    reasons.push('KDJ高位死叉');
    if (latest.kdjK > 80) {
      score += 10;
      reasons.push('KDJ超买区回落');
    }
  }

  if (prev.rsi24 > 70 && latest.rsi24 < prev.rsi24) {
    score += 15;
    reasons.push('RSI超买回落');
  }

  if (latest.ma5 < latest.ma10 && prev.ma5 >= prev.ma10) {
    score += 15;
    reasons.push('MA5下穿MA10');
  }

  if (latest.ma20 > 0 && currentData.close < latest.ma20 && data[data.length - 2].close >= prev.ma20) {
    score += 10;
    reasons.push('股价跌破20日均线');
  }

  if (currentData.volume < avgVolume * 0.7) {
    score += 10;
    reasons.push('成交量萎缩');
  }

  if (currentData.volume > avgVolume * 2 && currentData.close < data[data.length - 2].close) {
    score += 15;
    reasons.push('顶部放量');
  }

  if (prevData.close > prev.bollUp && currentData.close < latest.bollUp && latest.bollUp > 0) {
    score += 10;
    reasons.push('布林带上轨回落');
  }

  let level: 'high' | 'medium' | 'low' | null = null;
  let signal = false;

  if (score >= 60 && reasons.length >= 3) {
    level = 'high';
    signal = true;
  } else if (score >= 40 && reasons.length >= 2) {
    level = 'medium';
    signal = true;
  } else if (score >= 20) {
    level = 'low';
    signal = true;
  }

  return { signal, level, score, reasons };
}
