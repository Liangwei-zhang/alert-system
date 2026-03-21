import { Alert, StockAnalysis } from '../types';

class AlertService {
  private alerts: Alert[] = [];
  private maxAlerts = 100;
  private alertIdCounter = 0;

  generateAlertId(): string {
    this.alertIdCounter++;
    return `alert_${Date.now()}_${this.alertIdCounter}`;
  }

  createAlert(
    analysis: StockAnalysis,
    type: 'buy' | 'sell' | 'top' | 'bottom',
    signalResult: { signal: boolean; level: 'high' | 'medium' | 'low' | null; score: number; reasons: string[] }
  ): Alert | null {
    if (!signalResult.signal || !signalResult.level) {
      return null;
    }

    const levelPriority: Record<string, number> = { high: 3, medium: 2, low: 1 };

    const isDuplicate = this.alerts.some(
      (a) =>
        a.symbol === analysis.symbol &&
        a.type === type &&
        levelPriority[a.level] >= levelPriority[signalResult.level!]
    );

    if (isDuplicate) {
      return null;
    }

    const typeLabels: Record<string, string> = { buy: '买入', sell: '卖出', top: '顶部预警', bottom: '底部预警' };
    const levelLabels: Record<string, string> = { high: '高级', medium: '中级', low: '低级' };
    const typeIcons: Record<string, string> = { buy: '🟢', sell: '🔴', top: '🔺', bottom: '🔻' };

    const alert: Alert = {
      id: this.generateAlertId(),
      symbol: analysis.symbol,
      type,
      level: signalResult.level,
      price: analysis.price,
      score: signalResult.score,
      reasons: signalResult.reasons,
      timestamp: Date.now(),
      read: false,
      message: `${typeIcons[type]} ${analysis.symbol} ${typeLabels[type]}信号 (${levelLabels[signalResult.level]})\n价格: $${analysis.price.toFixed(2)}\n信号强度: ${signalResult.score}/100\n触发条件:\n${signalResult.reasons.map((r) => `✅ ${r}`).join('\n')}`,
    };

    this.alerts.unshift(alert);

    if (this.alerts.length > this.maxAlerts) {
      this.alerts = this.alerts.slice(0, this.maxAlerts);
    }

    return alert;
  }

  getAlerts(): Alert[] {
    return this.alerts;
  }

  getUnreadAlerts(): Alert[] {
    return this.alerts.filter((a) => !a.read);
  }

  getUnreadCount(): number {
    return this.alerts.filter((a) => !a.read).length;
  }

  markAsRead(alertId: string): void {
    const alert = this.alerts.find((a) => a.id === alertId);
    if (alert) {
      alert.read = true;
    }
  }

  markAllAsRead(): void {
    this.alerts.forEach((a) => {
      a.read = true;
    });
  }

  clearAlerts(): void {
    this.alerts = [];
  }

  removeAlert(alertId: string): void {
    this.alerts = this.alerts.filter((a) => a.id !== alertId);
  }

  getAlertsBySymbol(symbol: string): Alert[] {
    return this.alerts.filter((a) => a.symbol === symbol);
  }

  getRecentAlerts(count: number = 10): Alert[] {
    return this.alerts.slice(0, count);
  }
}

export const alertService = new AlertService();
