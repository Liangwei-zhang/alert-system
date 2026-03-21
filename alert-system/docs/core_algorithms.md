# 股票智能预警系统 - 核心算法设计

## 六、核心算法设计

### 6.1 技术指标计算算法

#### 6.1.1 移动平均线（MA）

**算法描述**：
简单移动平均线是最基础的趋势指标，计算N日收盘价的算术平均值。

**计算公式**：
```
MA(N) = (C1 + C2 + C3 + ... + Cn) / N

其中：
- C1, C2, ..., Cn 为最近N日的收盘价
- N 为计算周期（常用：5, 10, 20, 60, 120, 250日）
```

**Python实现**：
```python
import pandas as pd
import numpy as np

def calculate_ma(df: pd.DataFrame, periods: list = [5, 10, 20, 60]) -> pd.DataFrame:
    """
    计算移动平均线

    Args:
        df: DataFrame，包含'close'列
        periods: MA周期列表

    Returns:
        添加了MA列的DataFrame
    """
    for period in periods:
        df[f'MA{period}'] = df['close'].rolling(window=period).mean()

    return df

# 应用示例
# df['MA5'] = df['close'].rolling(window=5).mean()
```

**交易信号**：
- **金叉**：短期均线上穿长期均线（如MA5上穿MA10） → 买入信号
- **死叉**：短期均线下穿长期均线（如MA5下穿MA10） → 卖出信号
- **多头排列**：MA5 > MA10 > MA20 > MA60 → 强势上涨
- **空头排列**：MA5 < MA10 < MA20 < MA60 → 弱势下跌

---

#### 6.1.2 MACD（指数平滑异同移动平均线）

**算法描述**：
MACD是趋势类指标，通过快慢两条EMA的差值来判断买卖时机。

**计算公式**：
```
1. 计算12日EMA（快线）：
   EMA(12) = 前一日EMA(12) × (11/13) + 今日收盘价 × (2/13)

2. 计算26日EMA（慢线）：
   EMA(26) = 前一日EMA(26) × (25/27) + 今日收盘价 × (2/27)

3. 计算DIF（差离值）：
   DIF = EMA(12) - EMA(26)

4. 计算DEA（信号线）：
   DEA = DIF的9日EMA
   DEA = 前一日DEA × (8/10) + 今日DIF × (2/10)

5. 计算MACD柱状图：
   MACD = (DIF - DEA) × 2

通用EMA公式：
EMA(N) = 前一日EMA(N) × (N-1)/(N+1) + 今日收盘价 × 2/(N+1)
初始EMA值 = 第一个收盘价
```

**Python实现**：
```python
def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """计算指数移动平均线"""
    return series.ewm(span=period, adjust=False).mean()

def calculate_macd(df: pd.DataFrame,
                   fast_period: int = 12,
                   slow_period: int = 26,
                   signal_period: int = 9) -> pd.DataFrame:
    """
    计算MACD指标

    Args:
        df: DataFrame，包含'close'列
        fast_period: 快线周期（默认12）
        slow_period: 慢线周期（默认26）
        signal_period: 信号线周期（默认9）

    Returns:
        添加了MACD指标的DataFrame
    """
    # 计算快慢EMA
    df['EMA_fast'] = calculate_ema(df['close'], fast_period)
    df['EMA_slow'] = calculate_ema(df['close'], slow_period)

    # 计算DIF
    df['MACD_DIF'] = df['EMA_fast'] - df['EMA_slow']

    # 计算DEA（信号线）
    df['MACD_DEA'] = calculate_ema(df['MACD_DIF'], signal_period)

    # 计算MACD柱状图
    df['MACD_histogram'] = (df['MACD_DIF'] - df['MACD_DEA']) * 2

    return df

# 使用TA-Lib库（更高效）
import talib

def calculate_macd_talib(df: pd.DataFrame) -> pd.DataFrame:
    """使用TA-Lib计算MACD"""
    df['MACD_DIF'], df['MACD_DEA'], df['MACD_histogram'] = talib.MACD(
        df['close'].values,
        fastperiod=12,
        slowperiod=26,
        signalperiod=9
    )
    return df
```

**交易信号**：
- **金叉**：DIF上穿DEA → 买入信号
- **死叉**：DIF下穿DEA → 卖出信号
- **零轴突破**：
  - DIF从负转正 → 强烈买入
  - DIF从正转负 → 强烈卖出
- **柱状图**：
  - 红柱增长 → 上涨动能增强
  - 绿柱增长 → 下跌动能增强

---

#### 6.1.3 KDJ（随机指标）

**算法描述**：
KDJ是摆动类指标，通过比较收盘价与一定周期内最高最低价的关系，来判断超买超卖。

**计算公式**：
```
1. 计算RSV（未成熟随机值）：
   RSV(N) = (Cn - Ln) / (Hn - Ln) × 100

   其中：
   - Cn：第N日收盘价
   - Ln：N日内最低价
   - Hn：N日内最高价
   - N：通常取9

2. 计算K值：
   今日K值 = 2/3 × 昨日K值 + 1/3 × 今日RSV
   （首日K值取50）

3. 计算D值：
   今日D值 = 2/3 × 昨日D值 + 1/3 × 今日K值
   （首日D值取50）

4. 计算J值：
   J值 = 3 × K值 - 2 × D值
```

**Python实现**：
```python
def calculate_kdj(df: pd.DataFrame, period: int = 9) -> pd.DataFrame:
    """
    计算KDJ指标

    Args:
        df: DataFrame，包含'high', 'low', 'close'列
        period: 计算周期（默认9）

    Returns:
        添加了KDJ指标的DataFrame
    """
    # 计算最低价和最高价
    low_min = df['low'].rolling(window=period).min()
    high_max = df['high'].rolling(window=period).max()

    # 计算RSV
    rsv = (df['close'] - low_min) / (high_max - low_min) * 100

    # 计算K值（使用EMA平滑）
    df['KDJ_K'] = rsv.ewm(alpha=1/3, adjust=False).mean()

    # 计算D值
    df['KDJ_D'] = df['KDJ_K'].ewm(alpha=1/3, adjust=False).mean()

    # 计算J值
    df['KDJ_J'] = 3 * df['KDJ_K'] - 2 * df['KDJ_D']

    return df

# 使用TA-Lib库
def calculate_kdj_talib(df: pd.DataFrame) -> pd.DataFrame:
    """使用TA-Lib计算KDJ"""
    # TA-Lib的STOCH就是KD指标
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
    return df
```

**交易信号**：
- **超买超卖**：
  - K > 80, D > 80 → 超买，考虑卖出
  - K < 20, D < 20 → 超卖，考虑买入
- **金叉死叉**：
  - K线上穿D线 → 买入信号
  - K线下穿D线 → 卖出信号
- **J值预警**：
  - J > 100 → 严重超买
  - J < 0 → 严重超卖

---

#### 6.1.4 RSI（相对强弱指标）

**算法描述**：
RSI通过比较一段时期内上涨幅度和下跌幅度来衡量市场强弱。

**计算公式**：
```
1. 计算涨跌幅：
   上涨幅度 = MAX(今日收盘价 - 昨日收盘价, 0)
   下跌幅度 = MAX(昨日收盘价 - 今日收盘价, 0)

2. 计算平均上涨和下跌（使用SMA或EMA）：
   平均上涨 = SMA(上涨幅度, N)
   平均下跌 = SMA(下跌幅度, N)

3. 计算相对强度RS：
   RS = 平均上涨 / 平均下跌

4. 计算RSI：
   RSI = 100 - (100 / (1 + RS))
   或
   RSI = 100 × 平均上涨 / (平均上涨 + 平均下跌)

常用周期N：6, 12, 24
```

**Python实现**：
```python
def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    计算RSI指标

    Args:
        df: DataFrame，包含'close'列
        period: 计算周期（默认14）

    Returns:
        添加了RSI指标的DataFrame
    """
    # 计算价格变化
    delta = df['close'].diff()

    # 分离上涨和下跌
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # 计算平均上涨和下跌（使用EMA）
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    # 计算RS
    rs = avg_gain / avg_loss

    # 计算RSI
    df[f'RSI{period}'] = 100 - (100 / (1 + rs))

    return df

# 使用TA-Lib库
def calculate_rsi_talib(df: pd.DataFrame, periods: list = [6, 12, 24]) -> pd.DataFrame:
    """使用TA-Lib计算多周期RSI"""
    for period in periods:
        df[f'RSI{period}'] = talib.RSI(df['close'].values, timeperiod=period)
    return df
```

**交易信号**：
- **超买超卖**：
  - RSI > 70 → 超买区域，可能回调
  - RSI < 30 → 超卖区域，可能反弹
  - 极端值：RSI > 80（严重超买），RSI < 20（严重超卖）
- **中轴线**：
  - RSI > 50 → 多头市场
  - RSI < 50 → 空头市场

---

#### 6.1.5 布林带（BOLL）

**算法描述**：
布林带由中轨（移动平均线）和上下轨（标准差带）组成，用于判断价格波动范围。

**计算公式**：
```
1. 计算中轨（MB）：
   MB = N日移动平均线 = MA(N)

2. 计算标准差（MD）：
   MD = sqrt(Σ(Ci - MA)² / N)
   其中Ci为第i日收盘价

3. 计算上轨（UP）和下轨（DN）：
   UP = MB + K × MD
   DN = MB - K × MD

   常用参数：
   - N = 20（计算周期）
   - K = 2（标准差倍数）
```

**Python实现**：
```python
def calculate_bollinger_bands(df: pd.DataFrame,
                               period: int = 20,
                               std_dev: float = 2.0) -> pd.DataFrame:
    """
    计算布林带指标

    Args:
        df: DataFrame，包含'close'列
        period: 计算周期（默认20）
        std_dev: 标准差倍数（默认2）

    Returns:
        添加了布林带指标的DataFrame
    """
    # 计算中轨（移动平均线）
    df['BOLL_MB'] = df['close'].rolling(window=period).mean()

    # 计算标准差
    std = df['close'].rolling(window=period).std()

    # 计算上轨和下轨
    df['BOLL_UP'] = df['BOLL_MB'] + (std_dev * std)
    df['BOLL_DN'] = df['BOLL_MB'] - (std_dev * std)

    # 计算带宽（可选）
    df['BOLL_WIDTH'] = (df['BOLL_UP'] - df['BOLL_DN']) / df['BOLL_MB']

    return df

# 使用TA-Lib库
def calculate_boll_talib(df: pd.DataFrame) -> pd.DataFrame:
    """使用TA-Lib计算布林带"""
    df['BOLL_UP'], df['BOLL_MB'], df['BOLL_DN'] = talib.BBANDS(
        df['close'].values,
        timeperiod=20,
        nbdevup=2,
        nbdevdn=2,
        matype=0
    )
    return df
```

**交易信号**：
- **突破信号**：
  - 价格突破上轨 → 强势，但可能超买
  - 价格跌破下轨 → 弱势，但可能超卖
- **回归信号**：
  - 价格触及上轨后回落 → 卖出信号
  - 价格触及下轨后反弹 → 买入信号
- **收缩扩张**：
  - 带宽收缩 → 波动率降低，可能酝酿大行情
  - 带宽扩张 → 波动率增加，趋势确立

---

### 6.2 趋势判断算法

#### 6.2.1 多均线趋势判断

**算法逻辑**：
```python
def determine_ma_trend(df: pd.DataFrame) -> pd.DataFrame:
    """
    基于多均线判断趋势

    Returns:
        trend: 1(强势上涨), 0.5(上涨), 0(震荡), -0.5(下跌), -1(强势下跌)
    """
    latest = df.iloc[-1]

    # 检查均线排列
    ma5 = latest['MA5']
    ma10 = latest['MA10']
    ma20 = latest['MA20']
    ma60 = latest['MA60']
    close = latest['close']

    # 强势多头：价格 > MA5 > MA10 > MA20 > MA60
    if close > ma5 > ma10 > ma20 > ma60:
        return 1  # 强势上涨

    # 多头：MA5 > MA10 > MA20
    elif ma5 > ma10 > ma20:
        return 0.5  # 上涨

    # 强势空头：价格 < MA5 < MA10 < MA20 < MA60
    elif close < ma5 < ma10 < ma20 < ma60:
        return -1  # 强势下跌

    # 空头：MA5 < MA10 < MA20
    elif ma5 < ma10 < ma20:
        return -0.5  # 下跌

    # 其他情况
    else:
        return 0  # 震荡
```

#### 6.2.2 综合趋势评分模型

**算法逻辑**：结合多个指标给出综合评分（0-100分）

```python
def calculate_trend_score(df: pd.DataFrame) -> dict:
    """
    计算综合趋势评分

    Returns:
        {
            'score': 综合评分（0-100），
            'trend': '强势上涨'|'上涨'|'震荡'|'下跌'|'强势下跌',
            'confidence': 置信度（0-1）
        }
    """
    latest = df.iloc[-1]
    score = 0
    weights = []

    # 1. MACD评分（权重25%）
    macd_score = 0
    if latest['MACD_DIF'] > latest['MACD_DEA']:
        macd_score += 50
        if latest['MACD_DIF'] > 0:
            macd_score += 25
        if latest['MACD_histogram'] > 0:
            macd_score += 25
    score += macd_score * 0.25
    weights.append(0.25)

    # 2. RSI评分（权重20%）
    rsi = latest['RSI14']
    if 30 < rsi < 70:  # 正常区域
        rsi_score = 50 + (rsi - 50)  # 转换为0-100
    elif rsi >= 70:  # 超买
        rsi_score = 100 - (rsi - 70) * 2  # 递减
    else:  # 超卖
        rsi_score = rsi * 1.67  # 递增
    score += rsi_score * 0.20
    weights.append(0.20)

    # 3. KDJ评分（权重15%）
    k = latest['KDJ_K']
    d = latest['KDJ_D']
    kdj_score = 0
    if k > d:
        kdj_score += 50
    kdj_score += min(k, 100) * 0.5
    score += kdj_score * 0.15
    weights.append(0.15)

    # 4. 均线评分（权重25%）
    ma_trend = determine_ma_trend(df)
    ma_score = (ma_trend + 1) * 50  # 转换为0-100
    score += ma_score * 0.25
    weights.append(0.25)

    # 5. 布林带位置评分（权重15%）
    close = latest['close']
    boll_up = latest['BOLL_UP']
    boll_dn = latest['BOLL_DN']
    boll_mb = latest['BOLL_MB']

    # 计算价格在布林带中的相对位置
    if close > boll_up:
        boll_score = 100  # 强势
    elif close < boll_dn:
        boll_score = 0  # 弱势
    else:
        boll_score = ((close - boll_dn) / (boll_up - boll_dn)) * 100
    score += boll_score * 0.15
    weights.append(0.15)

    # 计算置信度（基于指标一致性）
    scores = [macd_score, rsi_score, kdj_score, ma_score, boll_score]
    std_dev = np.std(scores)
    confidence = 1 - min(std_dev / 50, 1)  # 标准差越小，置信度越高

    # 判断趋势
    if score >= 80:
        trend = "强势上涨"
    elif score >= 60:
        trend = "上涨"
    elif score >= 40:
        trend = "震荡"
    elif score >= 20:
        trend = "下跌"
    else:
        trend = "强势下跌"

    return {
        'score': round(score, 2),
        'trend': trend,
        'confidence': round(confidence, 2)
    }
```

---

### 6.3 买卖点识别模型

#### 6.3.1 多指标融合买入信号识别

**算法逻辑**：
```python
def detect_buy_signal(df: pd.DataFrame, lookback: int = 5) -> dict:
    """
    检测买入信号

    Args:
        df: 包含所有指标的DataFrame
        lookback: 回溯天数，用于检测交叉等信号

    Returns:
        {
            'signal': True/False,
            'level': 'high'|'medium'|'low',
            'reasons': [满足的条件列表],
            'score': 信号强度评分
        }
    """
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    reasons = []
    score = 0

    # 条件1: MACD金叉 (权重: 20分)
    if (latest['MACD_DIF'] > latest['MACD_DEA'] and
        prev['MACD_DIF'] <= prev['MACD_DEA']):
        reasons.append("MACD金叉")
        score += 20

        # 零轴上方金叉加分
        if latest['MACD_DIF'] > 0:
            reasons.append("MACD零轴上方金叉")
            score += 10

    # 条件2: KDJ低位金叉 (权重: 20分)
    if (latest['KDJ_K'] > latest['KDJ_D'] and
        prev['KDJ_K'] <= prev['KDJ_D'] and
        latest['KDJ_K'] < 50):
        reasons.append("KDJ低位金叉")
        score += 20

        # 超卖区反弹加分
        if latest['KDJ_K'] < 20:
            reasons.append("KDJ超卖区反弹")
            score += 10

    # 条件3: RSI超卖反弹 (权重: 15分)
    if prev['RSI14'] < 30 and latest['RSI14'] > prev['RSI14']:
        reasons.append("RSI超卖反弹")
        score += 15

    # 条件4: 均线金叉 (权重: 15分)
    if (latest['MA5'] > latest['MA10'] and
        prev['MA5'] <= prev['MA10']):
        reasons.append("MA5上穿MA10")
        score += 15

    # 条件5: 价格站上均线 (权重: 10分)
    if latest['close'] > latest['MA20'] and prev['close'] <= prev['MA20']:
        reasons.append("股价突破20日均线")
        score += 10

    # 条件6: 成交量放大 (权重: 15分)
    if 'volume' in df.columns:
        avg_volume = df['volume'].rolling(window=5).mean().iloc[-1]
        if latest['volume'] > avg_volume * 1.5:
            reasons.append("成交量放大")
            score += 15

    # 条件7: 布林带下轨反弹 (权重: 10分)
    if prev['close'] < prev['BOLL_DN'] and latest['close'] > latest['BOLL_DN']:
        reasons.append("布林带下轨反弹")
        score += 10

    # 条件8: 底背离 (权重: 20分)
    divergence = detect_bullish_divergence(df, lookback=20)
    if divergence:
        reasons.append("MACD底背离")
        score += 20

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
        'timestamp': latest.name if hasattr(latest, 'name') else None
    }
```

#### 6.3.2 多指标融合卖出信号识别

**算法逻辑**：
```python
def detect_sell_signal(df: pd.DataFrame, lookback: int = 5) -> dict:
    """检测卖出信号"""
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    reasons = []
    score = 0

    # 条件1: MACD死叉 (权重: 20分)
    if (latest['MACD_DIF'] < latest['MACD_DEA'] and
        prev['MACD_DIF'] >= prev['MACD_DEA']):
        reasons.append("MACD死叉")
        score += 20

        # 零轴下方死叉加分
        if latest['MACD_DIF'] < 0:
            reasons.append("MACD零轴下方死叉")
            score += 10

    # 条件2: KDJ高位死叉 (权重: 20分)
    if (latest['KDJ_K'] < latest['KDJ_D'] and
        prev['KDJ_K'] >= prev['KDJ_D'] and
        latest['KDJ_K'] > 50):
        reasons.append("KDJ高位死叉")
        score += 20

        # 超买区回落加分
        if latest['KDJ_K'] > 80:
            reasons.append("KDJ超买区回落")
            score += 10

    # 条件3: RSI超买回落 (权重: 15分)
    if prev['RSI14'] > 70 and latest['RSI14'] < prev['RSI14']:
        reasons.append("RSI超买回落")
        score += 15

    # 条件4: 均线死叉 (权重: 15分)
    if (latest['MA5'] < latest['MA10'] and
        prev['MA5'] >= prev['MA10']):
        reasons.append("MA5下穿MA10")
        score += 15

    # 条件5: 价格跌破均线 (权重: 10分)
    if latest['close'] < latest['MA20'] and prev['close'] >= prev['MA20']:
        reasons.append("股价跌破20日均线")
        score += 10

    # 条件6: 成交量萎缩或顶部放量 (权重: 15分)
    if 'volume' in df.columns:
        avg_volume = df['volume'].rolling(window=5).mean().iloc[-1]
        # 萎缩
        if latest['volume'] < avg_volume * 0.7:
            reasons.append("成交量萎缩")
            score += 10
        # 顶部放量
        elif latest['volume'] > avg_volume * 2 and latest['close'] < prev['close']:
            reasons.append("顶部放量")
            score += 15

    # 条件7: 布林带上轨回落 (权重: 10分)
    if prev['close'] > prev['BOLL_UP'] and latest['close'] < latest['BOLL_UP']:
        reasons.append("布林带上轨回落")
        score += 10

    # 条件8: 顶背离 (权重: 20分)
    divergence = detect_bearish_divergence(df, lookback=20)
    if divergence:
        reasons.append("MACD顶背离")
        score += 20

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
        'timestamp': latest.name if hasattr(latest, 'name') else None
    }
```

---

### 6.4 顶部底部预测算法

#### 6.4.1 背离检测算法

**底背离检测（看涨）**：
```python
def detect_bullish_divergence(df: pd.DataFrame, lookback: int = 20) -> bool:
    """
    检测底背离（价格创新低但指标不创新低）

    Args:
        df: DataFrame
        lookback: 回溯周期

    Returns:
        True表示检测到底背离
    """
    if len(df) < lookback:
        return False

    recent_data = df.tail(lookback)

    # 找到价格的两个低点
    price_lows = recent_data.nsmallest(2, 'low')
    if len(price_lows) < 2:
        return False

    # 按时间排序
    price_lows = price_lows.sort_index()
    low1_idx = price_lows.index[0]
    low2_idx = price_lows.index[1]

    # 确保第二个低点在第一个之后
    if low2_idx <= low1_idx:
        return False

    # 价格创新低
    if price_lows.iloc[1]['low'] >= price_lows.iloc[0]['low']:
        return False

    # MACD不创新低（底背离）
    macd1 = df.loc[low1_idx, 'MACD_DIF']
    macd2 = df.loc[low2_idx, 'MACD_DIF']

    if macd2 > macd1:  # MACD第二个低点高于第一个低点
        return True

    return False
```

**顶背离检测（看跌）**：
```python
def detect_bearish_divergence(df: pd.DataFrame, lookback: int = 20) -> bool:
    """
    检测顶背离（价格创新高但指标不创新高）

    Returns:
        True表示检测到顶背离
    """
    if len(df) < lookback:
        return False

    recent_data = df.tail(lookback)

    # 找到价格的两个高点
    price_highs = recent_data.nlargest(2, 'high')
    if len(price_highs) < 2:
        return False

    # 按时间排序
    price_highs = price_highs.sort_index()
    high1_idx = price_highs.index[0]
    high2_idx = price_highs.index[1]

    # 确保第二个高点在第一个之后
    if high2_idx <= high1_idx:
        return False

    # 价格创新高
    if price_highs.iloc[1]['high'] <= price_highs.iloc[0]['high']:
        return False

    # MACD不创新高（顶背离）
    macd1 = df.loc[high1_idx, 'MACD_DIF']
    macd2 = df.loc[high2_idx, 'MACD_DIF']

    if macd2 < macd1:  # MACD第二个高点低于第一个高点
        return True

    return False
```

#### 6.4.2 形态识别算法

**W底形态识别**：
```python
def detect_w_bottom(df: pd.DataFrame, lookback: int = 30, tolerance: float = 0.02) -> dict:
    """
    检测W底形态（双底）

    Args:
        df: DataFrame
        lookback: 回溯周期
        tolerance: 两个低点的价格容差（2%）

    Returns:
        {
            'detected': True/False,
            'support_level': 支撑位,
            'neckline': 颈线位,
            'confidence': 置信度
        }
    """
    if len(df) < lookback:
        return {'detected': False}

    recent_data = df.tail(lookback)

    # 找到两个最低点
    lows = recent_data.nsmallest(3, 'low').sort_index()

    if len(lows) < 3:
        return {'detected': False}

    # 提取两个低点（排除中间的）
    low1 = lows.iloc[0]
    low3 = lows.iloc[-1]

    # 两个低点价格应该接近（在tolerance范围内）
    price_diff = abs(low1['low'] - low3['low']) / low1['low']
    if price_diff > tolerance:
        return {'detected': False}

    # 找到中间的高点
    middle_start = low1.name
    middle_end = low3.name
    middle_data = df.loc[middle_start:middle_end]

    if len(middle_data) < 3:
        return {'detected': False}

    high_point = middle_data['high'].max()

    # W底条件：
    # 1. 两个低点差不多高
    # 2. 中间有一个明显的高点
    # 3. 当前价格突破颈线（中间高点）

    support_level = (low1['low'] + low3['low']) / 2
    neckline = high_point
    current_price = df.iloc[-1]['close']

    # 检测是否突破颈线
    breakthrough = current_price > neckline

    # 计算置信度
    confidence = 0.5
    if price_diff < 0.01:  # 两个低点非常接近
        confidence += 0.2
    if breakthrough:  # 突破颈线
        confidence += 0.3

    return {
        'detected': True,
        'support_level': round(support_level, 2),
        'neckline': round(neckline, 2),
        'breakthrough': breakthrough,
        'confidence': round(confidence, 2)
    }
```

**M顶形态识别**：
```python
def detect_m_top(df: pd.DataFrame, lookback: int = 30, tolerance: float = 0.02) -> dict:
    """
    检测M顶形态（双顶）

    Returns:
        {
            'detected': True/False,
            'resistance_level': 阻力位,
            'neckline': 颈线位,
            'confidence': 置信度
        }
    """
    if len(df) < lookback:
        return {'detected': False}

    recent_data = df.tail(lookback)

    # 找到两个最高点
    highs = recent_data.nlargest(3, 'high').sort_index()

    if len(highs) < 3:
        return {'detected': False}

    # 提取两个高点
    high1 = highs.iloc[0]
    high3 = highs.iloc[-1]

    # 两个高点价格应该接近
    price_diff = abs(high1['high'] - high3['high']) / high1['high']
    if price_diff > tolerance:
        return {'detected': False}

    # 找到中间的低点
    middle_start = high1.name
    middle_end = high3.name
    middle_data = df.loc[middle_start:middle_end]

    if len(middle_data) < 3:
        return {'detected': False}

    low_point = middle_data['low'].min()

    resistance_level = (high1['high'] + high3['high']) / 2
    neckline = low_point
    current_price = df.iloc[-1]['close']

    # 检测是否跌破颈线
    breakdown = current_price < neckline

    # 计算置信度
    confidence = 0.5
    if price_diff < 0.01:
        confidence += 0.2
    if breakdown:
        confidence += 0.3

    return {
        'detected': True,
        'resistance_level': round(resistance_level, 2),
        'neckline': round(neckline, 2),
        'breakdown': breakdown,
        'confidence': round(confidence, 2)
    }
```

#### 6.4.3 综合顶底预测模型

```python
def predict_top_bottom(df: pd.DataFrame) -> dict:
    """
    综合预测顶部和底部

    Returns:
        {
            'type': 'top'|'bottom'|'neutral',
            'probability': 0-1,
            'signals': [信号列表],
            'recommendation': 操作建议
        }
    """
    signals = []
    top_score = 0
    bottom_score = 0

    latest = df.iloc[-1]

    # 1. 背离检测
    if detect_bullish_divergence(df):
        signals.append("MACD底背离")
        bottom_score += 30

    if detect_bearish_divergence(df):
        signals.append("MACD顶背离")
        top_score += 30

    # 2. 形态识别
    w_bottom = detect_w_bottom(df)
    if w_bottom['detected']:
        signals.append(f"W底形态(支撑位:{w_bottom['support_level']})")
        bottom_score += 25 * w_bottom['confidence']

    m_top = detect_m_top(df)
    if m_top['detected']:
        signals.append(f"M顶形态(阻力位:{m_top['resistance_level']})")
        top_score += 25 * m_top['confidence']

    # 3. 超买超卖
    if latest['RSI14'] > 80:
        signals.append("RSI严重超买(>80)")
        top_score += 20
    elif latest['RSI14'] < 20:
        signals.append("RSI严重超卖(<20)")
        bottom_score += 20

    # 4. 布林带极端位置
    if latest['close'] > latest['BOLL_UP']:
        signals.append("价格突破布林带上轨")
        top_score += 15
    elif latest['close'] < latest['BOLL_DN']:
        signals.append("价格跌破布林带下轨")
        bottom_score += 15

    # 5. KDJ极端值
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
```

---

（文档继续，接下来是完整的系统集成示例）
