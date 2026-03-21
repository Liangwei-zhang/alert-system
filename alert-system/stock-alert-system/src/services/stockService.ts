import { StockData, KLineData } from '../types';

interface StockConfig {
  symbol: string;
  name: string;
  basePrice: number;
  volatility: number;
}

const STOCK_CONFIGS: StockConfig[] = [
  { symbol: 'AAPL', name: '苹果公司', basePrice: 178.5, volatility: 0.02 },
  { symbol: 'TSLA', name: '特斯拉', basePrice: 248.3, volatility: 0.035 },
  { symbol: 'MSFT', name: '微软公司', basePrice: 378.9, volatility: 0.018 },
];

function generateStockData(config: StockConfig, days: number = 120): StockData[] {
  const data: StockData[] = [];
  let currentPrice = config.basePrice * (0.9 + Math.random() * 0.2);
  const now = Date.now();
  const dayMs = 24 * 60 * 60 * 1000;

  for (let i = days; i >= 0; i--) {
    const timestamp = now - i * dayMs;
    const date = new Date(timestamp);
    const dayOfWeek = date.getDay();

    if (dayOfWeek === 0 || dayOfWeek === 6) continue;

    const open = currentPrice * (1 + (Math.random() - 0.5) * 0.01);
    const trend = Math.random() > 0.48 ? 1 : -1;
    const high = Math.max(open, currentPrice) * (1 + Math.random() * 0.015);
    const low = Math.min(open, currentPrice) * (1 - Math.random() * 0.015);
    const close = low + Math.random() * (high - low) * (0.5 + Math.random() * 0.5);
    const volume = config.basePrice * 1000000 * (0.5 + Math.random() * 1.5) * 0.0001;

    const change = i < days ? close - data[data.length - 1]?.close : 0;
    const changePercent = data.length > 0 ? (change / data[data.length - 1]!.close) * 100 : 0;

    data.push({
      symbol: config.symbol,
      name: config.name,
      price: close,
      close,
      change,
      changePercent,
      volume,
      open,
      high,
      low,
      timestamp,
    });

    currentPrice = close;
  }

  return data;
}

function updateStockData(data: StockData[], config: StockConfig): StockData[] {
  if (data.length === 0) return generateStockData(config);

  const lastData = data[data.length - 1];
  const now = Date.now();

  const randomChange = (Math.random() - 0.5) * 2 * config.volatility * lastData.price;
  const trend = Math.random() > 0.5 ? 1 : -1;
  const trendEffect = trend * lastData.price * 0.002;
  const newPrice = Math.max(1, lastData.price + randomChange + trendEffect);

  const open = lastData.price;
  const high = Math.max(open, newPrice) * (1 + Math.random() * 0.005);
  const low = Math.min(open, newPrice) * (1 - Math.random() * 0.005);
  const close = newPrice;
  const change = close - lastData.price;
  const changePercent = (change / lastData.price) * 100;
  const volume = config.basePrice * 1000000 * (0.5 + Math.random() * 1.5) * 0.0001 * (1 + Math.abs(changePercent) * 0.5);

  return [...data.slice(-119), {
    symbol: config.symbol,
    name: config.name,
    price: close,
    close,
    change,
    changePercent,
    volume,
    open,
    high,
    low,
    timestamp: now,
  }];
}

class StockService {
  private stockData: Map<string, StockData[]> = new Map();
  private stockConfigs: Map<string, StockConfig> = new Map();

  constructor() {
    this.initializeStocks();
  }

  private initializeStocks(): void {
    STOCK_CONFIGS.forEach((config) => {
      const data = generateStockData(config);
      this.stockData.set(config.symbol, data);
      this.stockConfigs.set(config.symbol, config);
    });
  }

  getStocks(): StockData[] {
    const stocks: StockData[] = [];
    this.stockData.forEach((data) => {
      if (data.length > 0) {
        stocks.push(data[data.length - 1]);
      }
    });
    return stocks;
  }

  getStock(symbol: string): StockData | null {
    const data = this.stockData.get(symbol);
    return data && data.length > 0 ? data[data.length - 1] : null;
  }

  getStockHistory(symbol: string): StockData[] {
    return this.stockData.get(symbol) || [];
  }

  getKLineData(symbol: string): KLineData[] {
    const history = this.stockData.get(symbol) || [];
    return history.map((d) => ({
      time: Math.floor(d.timestamp / 1000),
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.price,
      volume: d.volume,
    }));
  }

  updateStocks(): void {
    this.stockConfigs.forEach((config, symbol) => {
      const currentData = this.stockData.get(symbol) || [];
      const newData = updateStockData(currentData, config);
      this.stockData.set(symbol, newData);
    });
  }

  getAvailableStocks(): string[] {
    return STOCK_CONFIGS.map((c) => c.symbol);
  }
}

export const stockService = new StockService();
