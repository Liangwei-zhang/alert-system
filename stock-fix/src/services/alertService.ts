import { Alert, StockAnalysis } from '../types';

const DEDUP_WINDOW_MS = 24 * 60 * 60 * 1000; // 24h

class AlertService {
  private alerts: Alert[]   = [];
  private maxAlerts         = 100;
  private counter           = 0;
  /** 每次状态变更后调用，通知 React 同步 state（Bug3修复） */
  private onChange: (() => void) | null = null;

  setOnChange(cb: () => void): void {
    this.onChange = cb;
  }

  private notify(): void {
    this.onChange?.();
  }

  createAlert(
    analysis: StockAnalysis,
    type: 'buy' | 'sell' | 'top' | 'bottom',
    signal: { signal: boolean; level: 'high' | 'medium' | 'low' | null; score: number; reasons: string[] },
  ): Alert | null {
    if (!signal.signal || !signal.level) return null;

    const now = Date.now();
    const pri: Record<string, number> = { high: 3, medium: 2, low: 1 };

    // Bug2修复：原代码缺少 24h 时间窗口，同类信号永久不再触发
    const dup = this.alerts.some(
      a =>
        a.symbol === analysis.symbol &&
        a.type   === type &&
        pri[a.level] >= pri[signal.level!] &&
        now - a.timestamp < DEDUP_WINDOW_MS,
    );
    if (dup) return null;

    const icons: Record<string, string> = { buy: '🟢', sell: '🔴', top: '🔺', bottom: '🔻' };
    const typeLabel: Record<string, string> = { buy: '买入', sell: '卖出', top: '顶部预警', bottom: '底部预警' };
    const lvLabel: Record<string, string>   = { high: '高级', medium: '中级', low: '低级' };

    const alert: Alert = {
      id:        `alert_${now}_${++this.counter}`,
      symbol:    analysis.symbol,
      type,
      level:     signal.level,
      price:     analysis.price,
      score:     signal.score,
      reasons:   signal.reasons,
      timestamp: now,
      read:      false,
      message:   `${icons[type]} ${analysis.symbol} ${typeLabel[type]}信号 (${lvLabel[signal.level]})\n价格: $${analysis.price.toFixed(2)}\n强度: ${signal.score}/100`,
    };

    this.alerts.unshift(alert);
    if (this.alerts.length > this.maxAlerts) this.alerts.length = this.maxAlerts;
    // 不 notify() 此处 — 批量预警在 updateUI 结束后统一通知一次
    return alert;
  }

  /** 批量创建完后调用一次，触发 React 重渲染 */
  flush(): void { this.notify(); }

  getAlerts():       Alert[]  { return this.alerts; }
  getUnreadCount():  number   { return this.alerts.filter(a => !a.read).length; }

  markAsRead(id: string): void {
    const a = this.alerts.find(x => x.id === id);
    if (a) { a.read = true; this.notify(); }
  }

  markAllAsRead(): void {
    this.alerts.forEach(a => { a.read = true; });
    this.notify();
  }

  clearAlerts(): void {
    this.alerts = [];
    this.notify();
  }

  removeAlert(id: string): void {
    this.alerts = this.alerts.filter(a => a.id !== id);
    this.notify();
  }
}

export const alertService = new AlertService();
