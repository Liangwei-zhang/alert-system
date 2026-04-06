/**
 * Offline Data Service for Stock Py Subscription H5
 * Provides cached stock data for US, Canadian, and Crypto symbols
 */

const OFFLINE_DB_NAME = 'stockpy-offline-db';
const OFFLINE_DB_VERSION = 1;
const CACHE_EXPIRY_HOURS = 24;

class OfflineStockService {
  constructor() {
    this.db = null;
    this.preloadedSymbols = this.getPreloadedSymbols();
  }

  // Preloaded symbol dataset - US, Canadian, and Crypto
  getPreloadedSymbols() {
    return {
      // US Stocks - Top by market cap
      us: [
        { symbol: 'AAPL', name: 'Apple Inc.', sector: 'Technology' },
        { symbol: 'MSFT', name: 'Microsoft Corporation', sector: 'Technology' },
        { symbol: 'GOOGL', name: 'Alphabet Inc.', sector: 'Technology' },
        { symbol: 'AMZN', name: 'Amazon.com Inc.', sector: 'Consumer' },
        { symbol: 'NVDA', name: 'NVIDIA Corporation', sector: 'Technology' },
        { symbol: 'META', name: 'Meta Platforms Inc.', sector: 'Technology' },
        { symbol: 'TSLA', name: 'Tesla Inc.', sector: 'Automotive' },
        { symbol: 'BRK.B', name: 'Berkshire Hathaway', sector: 'Financial' },
        { symbol: 'UNH', name: 'UnitedHealth Group', sector: 'Healthcare' },
        { symbol: 'JNJ', name: 'Johnson & Johnson', sector: 'Healthcare' },
        { symbol: 'V', name: 'Visa Inc.', sector: 'Financial' },
        { symbol: 'XOM', name: 'Exxon Mobil Corporation', sector: 'Energy' },
        { symbol: 'JPM', name: 'JPMorgan Chase & Co.', sector: 'Financial' },
        { symbol: 'WMT', name: 'Walmart Inc.', sector: 'Retail' },
        { symbol: 'MA', name: 'Mastercard Inc.', sector: 'Financial' },
        { symbol: 'PG', name: 'Procter & Gamble', sector: 'Consumer' },
        { symbol: 'HD', name: 'Home Depot Inc.', sector: 'Retail' },
        { symbol: 'CVX', name: 'Chevron Corporation', sector: 'Energy' },
        { symbol: 'LLY', name: 'Eli Lilly and Company', sector: 'Healthcare' },
        { symbol: 'ABBV', name: 'AbbVie Inc.', sector: 'Healthcare' },
        { symbol: 'MRK', name: 'Merck & Co. Inc.', sector: 'Healthcare' },
        { symbol: 'PFE', name: 'Pfizer Inc.', sector: 'Healthcare' },
        { symbol: 'KO', name: 'Coca-Cola Company', sector: 'Consumer' },
        { symbol: 'PEP', name: 'PepsiCo Inc.', sector: 'Consumer' },
        { symbol: 'COST', name: 'Costco Wholesale', sector: 'Retail' },
        { symbol: 'AVGO', name: 'Broadcom Inc.', sector: 'Technology' },
        { symbol: 'TMO', name: 'Thermo Fisher Scientific', sector: 'Healthcare' },
        { symbol: 'MCD', name: 'McDonalds Corporation', sector: 'Consumer' },
        { symbol: 'CSCO', name: 'Cisco Systems Inc.', sector: 'Technology' },
        { symbol: 'ACN', name: 'Accenture plc', sector: 'Technology' },
        { symbol: 'ABT', name: 'Abbott Laboratories', sector: 'Healthcare' },
        { symbol: 'DHR', name: 'Danaher Corporation', sector: 'Healthcare' },
        { symbol: 'NKE', name: 'Nike Inc.', sector: 'Consumer' },
        { symbol: 'ADBE', name: 'Adobe Inc.', sector: 'Technology' },
        { symbol: 'CRM', name: 'Salesforce Inc.', sector: 'Technology' },
        { symbol: 'NFLX', name: 'Netflix Inc.', sector: 'Entertainment' },
        { symbol: 'AMD', name: 'Advanced Micro Devices', sector: 'Technology' },
        { symbol: 'INTC', name: 'Intel Corporation', sector: 'Technology' },
        { symbol: 'DIS', name: 'Walt Disney Company', sector: 'Entertainment' },
        { symbol: 'VZ', name: 'Verizon Communications', sector: 'Telecom' },
        { symbol: 'T', name: 'AT&T Inc.', sector: 'Telecom' },
        { symbol: 'IBM', name: 'IBM Corporation', sector: 'Technology' },
        { symbol: 'QCOM', name: 'Qualcomm Inc.', sector: 'Technology' },
        { symbol: 'TXN', name: 'Texas Instruments', sector: 'Technology' },
        { symbol: 'CMCSA', name: 'Comcast Corporation', sector: 'Entertainment' },
        { symbol: 'BA', name: 'Boeing Company', sector: 'Industrial' },
        { symbol: 'CAT', name: 'Caterpillar Inc.', sector: 'Industrial' },
        { symbol: 'GE', name: 'General Electric', sector: 'Industrial' },
        { symbol: 'MMM', name: '3M Company', sector: 'Industrial' },
        { symbol: 'HON', name: 'Honeywell International', sector: 'Industrial' },
        { symbol: 'UNP', name: 'Union Pacific', sector: 'Transportation' }
      ],
      // Canadian Stocks - Top by market cap
      ca: [
        { symbol: 'RY', name: 'Royal Bank of Canada', sector: 'Financial' },
        { symbol: 'TD', name: 'Toronto-Dominion Bank', sector: 'Financial' },
        { symbol: 'ENB', name: 'Enbridge Inc.', sector: 'Energy' },
        { symbol: 'CNQ', name: 'Canadian Natural Resources', sector: 'Energy' },
        { symbol: 'SU', name: 'Suncor Energy Inc.', sector: 'Energy' },
        { symbol: 'BMO', name: 'Bank of Montreal', sector: 'Financial' },
        { symbol: 'BNS', name: 'Bank of Nova Scotia', sector: 'Financial' },
        { symbol: 'MG', name: 'Magna International', sector: 'Automotive' },
        { symbol: 'CP', name: 'Canadian Pacific Kansas City', sector: 'Transportation' },
        { symbol: 'CNR', name: 'Canadian National Railway', sector: 'Transportation' },
        { symbol: 'TRI', name: 'Thomson Reuters Corp', sector: 'Media' },
        { symbol: 'ATD', name: 'Alimentation Couche-Tard', sector: 'Retail' },
        { symbol: 'SLF', name: 'Sun Life Financial', sector: 'Financial' },
        { symbol: 'MFC', name: 'Manulife Financial', sector: 'Financial' },
        { symbol: 'PWO', name: 'Power Corporation of Canada', sector: 'Financial' },
        { symbol: 'CVE', name: 'Cenovus Energy Inc.', sector: 'Energy' },
        { symbol: 'IMO', name: 'Imperial Oil Limited', sector: 'Energy' },
        { symbol: 'WPM', name: 'Wheaton Precious Metals', sector: 'Materials' },
        { symbol: 'AEM', name: 'Agnico Eagle Mines', sector: 'Materials' },
        { symbol: 'G', name: 'Franco-Nevada Corporation', sector: 'Materials' },
        { symbol: 'FNV', name: 'Franco-Nevada Corp', sector: 'Materials' },
        { symbol: 'K', name: 'Kinross Gold Corporation', sector: 'Materials' },
        { symbol: 'GIL', name: 'Gildan Activewear', sector: 'Consumer' },
        { symbol: 'CCO', name: 'Cameco Corporation', sector: 'Energy' },
        { symbol: 'CAR', name: 'Canada Goose Holdings', sector: 'Consumer' },
        { symbol: 'L', name: 'Loblaw Companies', sector: 'Retail' },
        { symbol: 'MRU', name: 'Metro Inc.', sector: 'Retail' },
        { symbol: 'SJR', name: 'Shaw Communications', sector: 'Telecom' },
        { symbol: 'TECK', name: 'Teck Resources Limited', sector: 'Materials' },
        { symbol: 'NTR', name: 'Nutrien Ltd.', sector: 'Materials' }
      ],
      // Digital Currencies
      crypto: [
        { symbol: 'BTC', name: 'Bitcoin', category: 'Cryptocurrency' },
        { symbol: 'ETH', name: 'Ethereum', category: 'Cryptocurrency' },
        { symbol: 'BNB', name: 'Binance Coin', category: 'Cryptocurrency' },
        { symbol: 'XRP', name: 'Ripple', category: 'Cryptocurrency' },
        { symbol: 'SOL', name: 'Solana', category: 'Cryptocurrency' },
        { symbol: 'ADA', name: 'Cardano', category: 'Cryptocurrency' },
        { symbol: 'DOGE', name: 'Dogecoin', category: 'Cryptocurrency' },
        { symbol: 'DOT', name: 'Polkadot', category: 'Cryptocurrency' },
        { symbol: 'MATIC', name: 'Polygon', category: 'Cryptocurrency' },
        { symbol: 'AVAX', name: 'Avalanche', category: 'Cryptocurrency' },
        { symbol: 'LINK', name: 'Chainlink', category: 'Cryptocurrency' },
        { symbol: 'UNI', name: 'Uniswap', category: 'Cryptocurrency' },
        { symbol: 'ATOM', name: 'Cosmos', category: 'Cryptocurrency' },
        { symbol: 'LTC', name: 'Litecoin', category: 'Cryptocurrency' },
        { symbol: 'XLM', name: 'Stellar', category: 'Cryptocurrency' },
        { symbol: 'ALGO', name: 'Algorand', category: 'Cryptocurrency' },
        { symbol: 'VET', name: 'VeChain', category: 'Cryptocurrency' },
        { symbol: 'FIL', name: 'Filecoin', category: 'Cryptocurrency' },
        { symbol: 'NEAR', name: 'NEAR Protocol', category: 'Cryptocurrency' },
        { symbol: 'APT', name: 'Aptos', category: 'Cryptocurrency' },
        { symbol: 'ARB', name: 'Arbitrum', category: 'Cryptocurrency' },
        { symbol: 'OP', name: 'Optimism', category: 'Cryptocurrency' },
        { symbol: 'SHIB', name: 'Shiba Inu', category: 'Cryptocurrency' },
        { symbol: 'PEPE', name: 'Pepe', category: 'Cryptocurrency' },
        { symbol: 'USDT', name: 'Tether', category: 'Stablecoin' },
        { symbol: 'USDC', name: 'USD Coin', category: 'Stablecoin' }
      ]
    };
  }

  // Initialize IndexedDB
  async initDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(OFFLINE_DB_NAME, OFFLINE_DB_VERSION);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve(this.db);
      };
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // Stock data store
        if (!db.objectStoreNames.contains('stocks')) {
          const stockStore = db.createObjectStore('stocks', { keyPath: 'symbol' });
          stockStore.createIndex('timestamp', 'timestamp', { unique: false });
        }
        
        // Cache metadata store
        if (!db.objectStoreNames.contains('metadata')) {
          db.createObjectStore('metadata', { keyPath: 'key' });
        }
      };
    });
  }

  // Check if we're online
  isOnline() {
    return navigator.onLine;
  }

  // Get cached stock data
  async getCachedStock(symbol) {
    if (!this.db) await this.initDB();
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['stocks'], 'readonly');
      const store = transaction.objectStore('stocks');
      const request = store.get(symbol.toUpperCase());
      
      request.onsuccess = () => {
        const data = request.result;
        if (!data) {
          resolve(null);
          return;
        }
        
        // Check if cache is expired
        const cacheAge = Date.now() - data.timestamp;
        const expiryMs = CACHE_EXPIRY_HOURS * 60 * 60 * 1000;
        
        if (cacheAge > expiryMs) {
          resolve(null); // Cache expired
        } else {
          resolve(data);
        }
      };
      
      request.onerror = () => reject(request.error);
    });
  }

  // Cache stock data
  async cacheStock(stockData) {
    if (!this.db) await this.initDB();
    
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['stocks'], 'readwrite');
      const store = transaction.objectStore('stocks');
      
      const data = {
        ...stockData,
        symbol: stockData.symbol.toUpperCase(),
        timestamp: Date.now()
      };
      
      const request = store.put(data);
      request.onsuccess = () => resolve(data);
      request.onerror = () => reject(request.error);
    });
  }

  // Get multiple cached stocks
  async getCachedStocks(symbols) {
    const results = {};
    for (const symbol of symbols) {
      const cached = await this.getCachedStock(symbol);
      if (cached) {
        results[symbol] = cached;
      }
    }
    return results;
  }

  // Search symbols (offline)
  searchSymbols(query, category = 'all') {
    const q = query.toLowerCase();
    let results = [];
    
    const categories = category === 'all' 
      ? ['us', 'ca', 'crypto'] 
      : [category];
    
    for (const cat of categories) {
      const symbols = this.preloadedSymbols[cat] || [];
      const matches = symbols.filter(s => 
        s.symbol.toLowerCase().includes(q) || 
        (s.name && s.name.toLowerCase().includes(q))
      );
      results = results.concat(matches.map(s => ({ ...s, category: cat })));
    }
    
    return results;
  }

  // Get preloaded data for display (offline mode)
  getPreloadedData(symbols) {
    const results = [];
    const now = Date.now();
    
    for (const sym of symbols) {
      // Check if it's a known symbol
      for (const cat of ['us', 'ca', 'crypto']) {
        const found = this.preloadedSymbols[cat].find(s => s.symbol === sym);
        if (found) {
          results.push({
            ...found,
            price: this.generateMockPrice(sym),
            change: (Math.random() * 6 - 3).toFixed(2),
            changePercent: (Math.random() * 6 - 3).toFixed(2),
            timestamp: now,
            isOfflineData: true
          });
          break;
        }
      }
    }
    
    return results;
  }

  // Generate mock price for offline demo
  generateMockPrice(symbol) {
    const basePrices = {
      'AAPL': 175.50, 'MSFT': 380.25, 'GOOGL': 140.75, 'AMZN': 178.30, 'NVDA': 495.80,
      'META': 485.60, 'TSLA': 175.20, 'BTC': 43250.00, 'ETH': 2285.50, 'RBC': 98.50,
      'TD': 78.25, 'RY': 125.80
    };
    
    if (basePrices[symbol]) {
      return basePrices[symbol] + (Math.random() * 4 - 2);
    }
    
    // Random base price for unknown symbols
    return (Math.random() * 200 + 10);
  }

  // Get all preloaded symbols for a category
  getAllSymbols(category = 'all') {
    if (category === 'all') {
      return {
        us: this.preloadedSymbols.us.map(s => ({ ...s, category: 'US' })),
        ca: this.preloadedSymbols.ca.map(s => ({ ...s, category: 'Canada' })),
        crypto: this.preloadedSymbols.crypto.map(s => ({ ...s, category: 'Crypto' }))
      };
    }
    return this.preloadedSymbols[category].map(s => ({ ...s, category }));
  }

  // Initialize offline support
  async initialize() {
    await this.initDB();
    
    // Listen for online/offline events
    window.addEventListener('online', () => {
      console.log('Connection restored');
      document.dispatchEvent(new CustomEvent('stockpy-online'));
    });
    
    window.addEventListener('offline', () => {
      console.log('Working offline');
      document.dispatchEvent(new CustomEvent('stockpy-offline'));
    });
    
    return this;
  }
}

// Export singleton instance
const offlineService = new OfflineStockService();

// Auto-initialize
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => offlineService.initialize());
} else {
  offlineService.initialize();
}

// Make available globally
window.OfflineStockService = OfflineStockService;
window.offlineService = offlineService;