export interface StockData {
  symbol: string;
  name: string;
  price: number;
  close: number;
  change: number;
  changePercent: number;
  volume: number;
  open: number;
  high: number;
  low: number;
  timestamp: number;
}

export interface TechnicalIndicators {
  ma5: number;
  ma10: number;
  ma20: number;
  ma60: number;
  macdDif: number;
  macdDea: number;
  macdHistogram: number;
  kdjK: number;
  kdjD: number;
  kdjJ: number;
  rsi6: number;
  rsi12: number;
  rsi24: number;
  bollUp: number;
  bollMb: number;
  bollDn: number;
}

export interface SignalResult {
  signal: boolean;
  level: 'high' | 'medium' | 'low' | null;
  score: number;
  reasons: string[];
}

export interface PredictionResult {
  type: 'top' | 'bottom' | 'neutral';
  probability: number;
  signals: string[];
  recommendation: string;
}

export interface Alert {
  id: string;
  symbol: string;
  type: 'buy' | 'sell' | 'top' | 'bottom';
  level: 'high' | 'medium' | 'low';
  price: number;
  score: number;
  reasons: string[];
  timestamp: number;
  read: boolean;
  message: string;
}

export interface KLineData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface StockAnalysis {
  symbol: string;
  price: number;
  indicators: TechnicalIndicators;
  buySignal: SignalResult;
  sellSignal: SignalResult;
  prediction: PredictionResult;
}
