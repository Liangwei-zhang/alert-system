"""
股票智能预警系统 - 完整示例代码
演示了核心功能的集成使用
"""

import pandas as pd
import numpy as np
import talib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json


class TechnicalIndicators:
    """技术指标计算引擎"""

    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """计算所有技术指标"""

        # 移动平均线
        for period in [5, 10, 20, 60]:
            df[f'MA{period}'] = talib.SMA(df['close'].values, timeperiod=period)

        # MACD
        df['MACD_DIF'], df['MACD_DEA'], df['MACD_histogram'] = talib.MACD(
            df['close'].values,
            fastperiod=12,
            slowperiod=26,
            signalperiod=9
        )

        # KDJ
        df['KDJ_K'], df['KDJ_D'] = talib.STOCH(
            df['high'].values,
            df['low'].values,
            df['close'].values,
            fastk_period=9,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0
        )
        df['KDJ_J'] = 3 * df['KDJ_K'] - 2 * df['KDJ_D']

        # RSI
        df['RSI6'] = talib.RSI(df['close'].values, timeperiod=6)
        df['RSI12'] = talib.RSI(df['close'].values, timeperiod=12)
        df['RSI14'] = talib.RSI(df['close'].values, timeperiod=14)

        # 布林带
        df['BOLL_UP'], df['BOLL_MB'], df['BOLL_DN'] = talib.BBANDS(
            df['close'].values,
            timeperiod=20,
            nbdevup=2,
            nbdevdn=2,
            matype=0
        )

        return df


class SignalDetector:
    """买卖信号检测器"""

    @staticmethod
    def detect_buy_signal(df: pd.DataFrame) -> dict:
        """检测买入信号"""
        if len(df) < 2:
            return {'signal': False}

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        reasons = []
        score = 0

        # MACD金叉
        if (latest['MACD_DIF'] > latest['MACD_DEA'] and
                prev['MACD_DIF'] <= prev['MACD_DEA']):
            reasons.append("MACD金叉")
            score += 20
            if latest['MACD_DIF'] > 0:
                reasons.append("MACD零轴上方金叉")
                score += 10

        # KDJ低位金叉
        if (latest['KDJ_K'] > latest['KDJ_D'] and
                prev['KDJ_K'] <= prev['KDJ_D'] and
                latest['KDJ_K'] < 50):
            reasons.append("KDJ低位金叉")
            score += 20
            if latest['KDJ_K'] < 20:
                reasons.append("KDJ超卖区反弹")
                score += 10

        # RSI超卖反弹
        if prev['RSI14'] < 30 and latest['RSI14'] > prev['RSI14']:
            reasons.append("RSI超卖反弹")
            score += 15

        # 均线金叉
        if (latest['MA5'] > latest['MA10'] and
                prev['MA5'] <= prev['MA10']):
            reasons.append("MA5上穿MA10")
            score += 15

        # 价格站上均线
        if latest['close'] > latest['MA20'] and prev['close'] <= prev['MA20']:
            reasons.append("股价突破20日均线")
            score += 10

        # 成交量放大
        if 'volume' in df.columns:
            avg_volume = df['volume'].rolling(window=5).mean().iloc[-1]
            if latest['volume'] > avg_volume * 1.5:
                reasons.append("成交量放大")
                score += 15

        # 布林带下轨反弹
        if prev['close'] < prev['BOLL_DN'] and latest['close'] > latest['BOLL_DN']:
            reasons.append("布林带下轨反弹")
            score += 10

        # 判断信号级别
        if score >= 60 and len(reasons) >= 3:
            level = 'high'
            signal = True
        elif score >= 40 and len(reasons) >= 2:
            level = 'medium'
            signal = True
        elif score >= 20:
            level = 'low'
            signal = True
        else:
            level = None
            signal = False

        return {
            'signal': signal,
            'level': level,
            'reasons': reasons,
            'score': score,
            'price': latest['close'],
            'timestamp': latest.name if hasattr(latest, 'name') else None
        }

    @staticmethod
    def detect_sell_signal(df: pd.DataFrame) -> dict:
        """检测卖出信号"""
        if len(df) < 2:
            return {'signal': False}

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        reasons = []
        score = 0

        # MACD死叉
        if (latest['MACD_DIF'] < latest['MACD_DEA'] and
                prev['MACD_DIF'] >= prev['MACD_DEA']):
            reasons.append("MACD死叉")
            score += 20
            if latest['MACD_DIF'] < 0:
                reasons.append("MACD零轴下方死叉")
                score += 10

        # KDJ高位死叉
        if (latest['KDJ_K'] < latest['KDJ_D'] and
                prev['KDJ_K'] >= prev['KDJ_D'] and
                latest['KDJ_K'] > 50):
            reasons.append("KDJ高位死叉")
            score += 20
            if latest['KDJ_K'] > 80:
                reasons.append("KDJ超买区回落")
                score += 10

        # RSI超买回落
        if prev['RSI14'] > 70 and latest['RSI14'] < prev['RSI14']:
            reasons.append("RSI超买回落")
            score += 15

        # 均线死叉
        if (latest['MA5'] < latest['MA10'] and
                prev['MA5'] >= prev['MA10']):
            reasons.append("MA5下穿MA10")
            score += 15

        # 价格跌破均线
        if latest['close'] < latest['MA20'] and prev['close'] >= prev['MA20']:
            reasons.append("股价跌破20日均线")
            score += 10

        # 成交量萎缩或顶部放量
        if 'volume' in df.columns:
            avg_volume = df['volume'].rolling(window=5).mean().iloc[-1]
            if latest['volume'] < avg_volume * 0.7:
                reasons.append("成交量萎缩")
                score += 10
            elif latest['volume'] > avg_volume * 2 and latest['close'] < prev['close']:
                reasons.append("顶部放量")
                score += 15

        # 布林带上轨回落
        if prev['close'] > prev['BOLL_UP'] and latest['close'] < latest['BOLL_UP']:
            reasons.append("布林带上轨回落")
            score += 10

        # 判断信号级别
        if score >= 60 and len(reasons) >= 3:
            level = 'high'
            signal = True
        elif score >= 40 and len(reasons) >= 2:
            level = 'medium'
            signal = True
        elif score >= 20:
            level = 'low'
            signal = True
        else:
            level = None
            signal = False

        return {
            'signal': signal,
            'level': level,
            'reasons': reasons,
            'score': score,
            'price': latest['close'],
            'timestamp': latest.name if hasattr(latest, 'name') else None
        }


class TopBottomPredictor:
    """顶底预测器"""

    @staticmethod
    def detect_bullish_divergence(df: pd.DataFrame, lookback: int = 20) -> bool:
        """检测底背离"""
        if len(df) < lookback:
            return False

        recent_data = df.tail(lookback)
        price_lows = recent_data.nsmallest(2, 'low').sort_index()

        if len(price_lows) < 2:
            return False

        low1_idx = price_lows.index[0]
        low2_idx = price_lows.index[1]

        if low2_idx <= low1_idx:
            return False

        # 价格创新低但MACD不创新低
        if (price_lows.iloc[1]['low'] < price_lows.iloc[0]['low'] and
                df.loc[low2_idx, 'MACD_DIF'] > df.loc[low1_idx, 'MACD_DIF']):
            return True

        return False

    @staticmethod
    def detect_bearish_divergence(df: pd.DataFrame, lookback: int = 20) -> bool:
        """检测顶背离"""
        if len(df) < lookback:
            return False

        recent_data = df.tail(lookback)
        price_highs = recent_data.nlargest(2, 'high').sort_index()

        if len(price_highs) < 2:
            return False

        high1_idx = price_highs.index[0]
        high2_idx = price_highs.index[1]

        if high2_idx <= high1_idx:
            return False

        # 价格创新高但MACD不创新高
        if (price_highs.iloc[1]['high'] > price_highs.iloc[0]['high'] and
                df.loc[high2_idx, 'MACD_DIF'] < df.loc[high1_idx, 'MACD_DIF']):
            return True

        return False

    @staticmethod
    def predict_top_bottom(df: pd.DataFrame) -> dict:
        """综合预测顶底"""
        signals = []
        top_score = 0
        bottom_score = 0

        latest = df.iloc[-1]

        # 背离检测
        if TopBottomPredictor.detect_bullish_divergence(df):
            signals.append("MACD底背离")
            bottom_score += 30

        if TopBottomPredictor.detect_bearish_divergence(df):
            signals.append("MACD顶背离")
            top_score += 30

        # 超买超卖
        if latest['RSI14'] > 80:
            signals.append("RSI严重超买(>80)")
            top_score += 20
        elif latest['RSI14'] < 20:
            signals.append("RSI严重超卖(<20)")
            bottom_score += 20

        # 布林带极端位置
        if latest['close'] > latest['BOLL_UP']:
            signals.append("价格突破布林带上轨")
            top_score += 15
        elif latest['close'] < latest['BOLL_DN']:
            signals.append("价格跌破布林带下轨")
            bottom_score += 15

        # KDJ极端值
        if latest['KDJ_J'] > 100:
            signals.append("KDJ_J严重超买(>100)")
            top_score += 10
        elif latest['KDJ_J'] < 0:
            signals.append("KDJ_J严重超卖(<0)")
            bottom_score += 10

        # 判断类型和概率
        if top_score > bottom_score and top_score >= 50:
            prediction_type = 'top'
            probability = min(top_score / 100, 0.95)
            recommendation = "可能接近顶部，建议逐步减仓或观望"
        elif bottom_score > top_score and bottom_score >= 50:
            prediction_type = 'bottom'
            probability = min(bottom_score / 100, 0.95)
            recommendation = "可能接近底部，建议分批建仓或加仓"
        else:
            prediction_type = 'neutral'
            probability = 0
            recommendation = "未检测到明显顶底信号，保持观察"

        return {
            'type': prediction_type,
            'probability': round(probability, 2),
            'signals': signals,
            'top_score': round(top_score, 2),
            'bottom_score': round(bottom_score, 2),
            'recommendation': recommendation
        }


class StockAlertSystem:
    """股票预警系统主类"""

    def __init__(self):
        self.indicator_engine = TechnicalIndicators()
        self.signal_detector = SignalDetector()
        self.top_bottom_predictor = TopBottomPredictor()
        self.monitored_stocks = []

    def add_stock(self, symbol: str, data: pd.DataFrame):
        """添加监控股票"""
        self.monitored_stocks.append({
            'symbol': symbol,
            'data': data
        })

    def analyze_stock(self, symbol: str, data: pd.DataFrame) -> dict:
        """分析单只股票"""

        # 计算所有技术指标
        data = self.indicator_engine.calculate_all_indicators(data)

        # 检测买卖信号
        buy_signal = self.signal_detector.detect_buy_signal(data)
        sell_signal = self.signal_detector.detect_sell_signal(data)

        # 预测顶底
        top_bottom = self.top_bottom_predictor.predict_top_bottom(data)

        # 获取最新数据
        latest = data.iloc[-1]

        result = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'price': latest['close'],
            'indicators': {
                'MA5': latest['MA5'],
                'MA10': latest['MA10'],
                'MA20': latest['MA20'],
                'MACD_DIF': latest['MACD_DIF'],
                'MACD_DEA': latest['MACD_DEA'],
                'KDJ_K': latest['KDJ_K'],
                'KDJ_D': latest['KDJ_D'],
                'KDJ_J': latest['KDJ_J'],
                'RSI14': latest['RSI14'],
                'BOLL_UP': latest['BOLL_UP'],
                'BOLL_MB': latest['BOLL_MB'],
                'BOLL_DN': latest['BOLL_DN']
            },
            'buy_signal': buy_signal,
            'sell_signal': sell_signal,
            'top_bottom_prediction': top_bottom
        }

        return result

    def generate_alert(self, analysis_result: dict) -> Optional[dict]:
        """生成预警"""
        alerts = []

        symbol = analysis_result['symbol']
        buy_signal = analysis_result['buy_signal']
        sell_signal = analysis_result['sell_signal']
        top_bottom = analysis_result['top_bottom_prediction']

        # 买入预警
        if buy_signal['signal']:
            alerts.append({
                'type': 'buy',
                'level': buy_signal['level'],
                'symbol': symbol,
                'price': analysis_result['price'],
                'score': buy_signal['score'],
                'reasons': buy_signal['reasons'],
                'message': f"🟢 {symbol} 买入信号 ({buy_signal['level'].upper()})\n"
                           f"价格: ${analysis_result['price']:.2f}\n"
                           f"信号强度: {buy_signal['score']}/100\n"
                           f"触发条件:\n" + "\n".join([f"✅ {r}" for r in buy_signal['reasons']])
            })

        # 卖出预警
        if sell_signal['signal']:
            alerts.append({
                'type': 'sell',
                'level': sell_signal['level'],
                'symbol': symbol,
                'price': analysis_result['price'],
                'score': sell_signal['score'],
                'reasons': sell_signal['reasons'],
                'message': f"🔴 {symbol} 卖出信号 ({sell_signal['level'].upper()})\n"
                           f"价格: ${analysis_result['price']:.2f}\n"
                           f"信号强度: {sell_signal['score']}/100\n"
                           f"触发条件:\n" + "\n".join([f"✅ {r}" for r in sell_signal['reasons']])
            })

        # 顶底预警
        if top_bottom['type'] != 'neutral':
            icon = "🔺" if top_bottom['type'] == 'top' else "🔻"
            alerts.append({
                'type': top_bottom['type'],
                'level': 'high' if top_bottom['probability'] > 0.7 else 'medium',
                'symbol': symbol,
                'price': analysis_result['price'],
                'probability': top_bottom['probability'],
                'signals': top_bottom['signals'],
                'message': f"{icon} {symbol} {top_bottom['type'].upper()}预警\n"
                           f"概率: {top_bottom['probability'] * 100:.0f}%\n"
                           f"信号:\n" + "\n".join([f"• {s}" for s in top_bottom['signals']]) +
                           f"\n\n建议: {top_bottom['recommendation']}"
            })

        return alerts if alerts else None

    def scan_all_stocks(self) -> List[dict]:
        """扫描所有监控的股票"""
        all_alerts = []

        for stock in self.monitored_stocks:
            analysis = self.analyze_stock(stock['symbol'], stock['data'])
            alerts = self.generate_alert(analysis)

            if alerts:
                all_alerts.extend(alerts)

        return all_alerts


# ============= 使用示例 =============

def main():
    """主函数示例"""

    # 创建预警系统实例
    alert_system = StockAlertSystem()

    # 模拟股票数据（实际使用时从API获取）
    # 这里用随机数据演示
    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')

    # 模拟AAPL数据
    np.random.seed(42)
    aapl_data = pd.DataFrame({
        'date': dates,
        'open': 150 + np.cumsum(np.random.randn(100) * 2),
        'high': 152 + np.cumsum(np.random.randn(100) * 2),
        'low': 148 + np.cumsum(np.random.randn(100) * 2),
        'close': 150 + np.cumsum(np.random.randn(100) * 2),
        'volume': np.random.randint(1000000, 5000000, 100)
    })
    aapl_data.set_index('date', inplace=True)

    # 模拟TSLA数据
    np.random.seed(43)
    tsla_data = pd.DataFrame({
        'date': dates,
        'open': 200 + np.cumsum(np.random.randn(100) * 3),
        'high': 203 + np.cumsum(np.random.randn(100) * 3),
        'low': 197 + np.cumsum(np.random.randn(100) * 3),
        'close': 200 + np.cumsum(np.random.randn(100) * 3),
        'volume': np.random.randint(2000000, 8000000, 100)
    })
    tsla_data.set_index('date', inplace=True)

    # 模拟MSFT数据
    np.random.seed(44)
    msft_data = pd.DataFrame({
        'date': dates,
        'open': 300 + np.cumsum(np.random.randn(100) * 2),
        'high': 302 + np.cumsum(np.random.randn(100) * 2),
        'low': 298 + np.cumsum(np.random.randn(100) * 2),
        'close': 300 + np.cumsum(np.random.randn(100) * 2),
        'volume': np.random.randint(1500000, 6000000, 100)
    })
    msft_data.set_index('date', inplace=True)

    # 添加监控股票
    alert_system.add_stock('AAPL', aapl_data)
    alert_system.add_stock('TSLA', tsla_data)
    alert_system.add_stock('MSFT', msft_data)

    # 扫描所有股票
    print("=" * 60)
    print("股票智能预警系统 - 实时扫描")
    print("=" * 60)

    alerts = alert_system.scan_all_stocks()

    if alerts:
        print(f"\n检测到 {len(alerts)} 个预警信号:\n")
        for i, alert in enumerate(alerts, 1):
            print(f"\n【预警 #{i}】")
            print(alert['message'])
            print("-" * 60)
    else:
        print("\n✓ 当前无预警信号")

    # 详细分析单只股票
    print("\n" + "=" * 60)
    print("AAPL 详细分析")
    print("=" * 60)

    aapl_analysis = alert_system.analyze_stock('AAPL', aapl_data)

    print(f"\n当前价格: ${aapl_analysis['price']:.2f}")
    print("\n技术指标:")
    for key, value in aapl_analysis['indicators'].items():
        print(f"  {key}: {value:.2f}")

    print(f"\n买入信号: {'是' if aapl_analysis['buy_signal']['signal'] else '否'}")
    if aapl_analysis['buy_signal']['signal']:
        print(f"  级别: {aapl_analysis['buy_signal']['level']}")
        print(f"  评分: {aapl_analysis['buy_signal']['score']}/100")

    print(f"\n卖出信号: {'是' if aapl_analysis['sell_signal']['signal'] else '否'}")
    if aapl_analysis['sell_signal']['signal']:
        print(f"  级别: {aapl_analysis['sell_signal']['level']}")
        print(f"  评分: {aapl_analysis['sell_signal']['score']}/100")

    print(f"\n顶底预测: {aapl_analysis['top_bottom_prediction']['type']}")
    if aapl_analysis['top_bottom_prediction']['type'] != 'neutral':
        print(f"  概率: {aapl_analysis['top_bottom_prediction']['probability'] * 100:.0f}%")
        print(f"  建议: {aapl_analysis['top_bottom_prediction']['recommendation']}")


if __name__ == "__main__":
    main()
