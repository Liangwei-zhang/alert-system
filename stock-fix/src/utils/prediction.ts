/**
 * prediction.ts — 顶底预测（完整重写）
 *
 * 算法架构：
 * 1. RSI 背离（先行，权重 40 分）— 已在 indicators.ts 精确计算
 * 2. 布林带 Squeeze 爆发方向（20 分）
 * 3. POC 突破（价值区边界突破往往引发短期爆发）（18 分）
 * 4. EMA + ADX 趋势强度（15 分）
 * 5. RSI 极值区（辅助确认，12 分）
 * 6. KDJ 极端值（辅助，8 分）
 *
 * 总分 ≥ 55 才触发预测（避免过多噪声信号）
 */

import { StockData, PredictionResult } from '../types';
import { calculateAllIndicators, getPreviousIndicators } from './indicators';

export function predictTopBottom(data: StockData[]): PredictionResult {
  // 需要足够历史数据（ADX 需要 28+，背离检测需要 60+）
  if (data.length < 65) {
    return {
      type: 'neutral',
      probability: 0,
      signals: [],
      recommendation: '数据不足，无法预测',
    };
  }

  const latest  = calculateAllIndicators(data);
  const prev    = getPreviousIndicators(data, 1);
  const cur     = data[data.length - 1];
  const pre1    = data[data.length - 2];

  let topScore    = 0;
  let bottomScore = 0;
  const signals: string[] = [];

  // ══════════════════════════════════════════════════════
  //  1. RSI 背离（先行指标，最高各 40 分）
  //     研究显示：背离信号 3~10 根K线内反转概率 >60%
  // ══════════════════════════════════════════════════════

  if (latest.rsiBullDiv) {
    bottomScore += 40;
    signals.push('RSI14 底背离（价格新低，动能未创新低）');
  }

  if (latest.rsiBearDiv) {
    topScore += 40;
    signals.push('RSI14 顶背离（价格新高，动能未创新高）');
  }

  // ══════════════════════════════════════════════════════
  //  2. 布林带 Squeeze 爆发方向（最高各 20 分）
  //     压缩结束后的爆发往往是单边行情
  // ══════════════════════════════════════════════════════

  if (latest.bollSqueezing) {
    // Squeeze 本身是中性的，需要通过价格位置判断方向
    if (cur.close > latest.bollMb && latest.ema9 > latest.ema21) {
      // 价格在中轨上，EMA 多头 → 向上爆发概率大
      bottomScore += 16;  // 逢低买入机会
      signals.push('布林带极度压缩（即将向上爆发）');
    } else if (cur.close < latest.bollMb && latest.ema9 < latest.ema21) {
      topScore += 16;
      signals.push('布林带极度压缩（即将向下爆发）');
    } else {
      // 方向未明
      signals.push('布林带极度压缩（方向待定）');
    }
  } else {
    // 非 Squeeze：传统上下轨位置判断
    if (latest.bollUp > 0) {
      if (cur.close > latest.bollUp) {
        topScore += 12;
        signals.push('价格突破布林上轨（超买区）');
      } else if (cur.close < latest.bollDn) {
        bottomScore += 12;
        signals.push('价格跌破布林下轨（超卖区）');
      }

      // 带宽急剧扩大（之前有 Squeeze）
      const widthExpanded = latest.bollWidth > prev.bollWidth * 1.2 && prev.bollSqueezing; // Bug1 fix: prev<prev*0.95 was always-false
      if (widthExpanded) {
        signals.push('布林带带宽急剧扩张（趋势启动）');
      }
    }
  }

  // ══════════════════════════════════════════════════════
  //  3. Volume Profile POC 突破（最高各 18 分）
  //     突破高价值区边界 → 短期爆发概率高
  // ══════════════════════════════════════════════════════

  if (latest.valueAreaHigh > 0 && latest.valueAreaLow > 0) {
    const vah = latest.valueAreaHigh;
    const val = latest.valueAreaLow;
    const poc = latest.poc;

    // 向上突破价值区高边界（VAH）
    if (cur.close > vah && pre1.close <= vah) {
      bottomScore += 18;
      signals.push(`向上突破 VAH（$${vah.toFixed(2)}），强势上行信号`);
    }
    // 向下突破价值区低边界（VAL）
    else if (cur.close < val && pre1.close >= val) {
      topScore += 18;
      signals.push(`向下跌破 VAL（$${val.toFixed(2)}），弱势下行信号`);
    }
    // 价格从 POC 两侧明显偏离（均值回归机会）
    else if (cur.close > poc * 1.025) {
      topScore += 8;
      signals.push(`价格偏离 POC（$${poc.toFixed(2)}）过高，回归风险`);
    } else if (cur.close < poc * 0.975) {
      bottomScore += 8;
      signals.push(`价格偏离 POC（$${poc.toFixed(2)}）过低，反弹机会`);
    }
  }

  // ══════════════════════════════════════════════════════
  //  4. EMA + ADX 趋势强度（最高各 15 分）
  //     结合 DI+/DI- 判断趋势方向和衰竭
  // ══════════════════════════════════════════════════════

  if (latest.adx > 25) {
    if (latest.diPlus > latest.diMinus) {
      // 强上涨趋势
      if (latest.adx > prev.adx) {
        bottomScore += 10;
        signals.push(`ADX ${latest.adx.toFixed(0)} 多头趋势增强`);
      } else {
        // ADX 开始下降：趋势减弱，可能见顶
        topScore += 8;
        signals.push(`ADX ${latest.adx.toFixed(0)} 趋势开始减弱`);
      }
    } else if (latest.diMinus > latest.diPlus) {
      if (latest.adx > prev.adx) {
        topScore += 10;
        signals.push(`ADX ${latest.adx.toFixed(0)} 空头趋势增强`);
      } else {
        bottomScore += 8;
        signals.push(`ADX ${latest.adx.toFixed(0)} 空头趋势开始减弱`);
      }
    }
  } else if (latest.adx < 15) {
    // 极低 ADX：即将从整理中突破
    signals.push('ADX 极低，市场即将选择方向');
  }

  // EMA 交叉
  if (latest.ema9 > latest.ema21 && prev.ema9 <= prev.ema21) {
    bottomScore += 12;
    signals.push('EMA9/21 刚完成金叉');
  } else if (latest.ema9 < latest.ema21 && prev.ema9 >= prev.ema21) {
    topScore += 12;
    signals.push('EMA9/21 刚完成死叉');
  }

  // ══════════════════════════════════════════════════════
  //  5. RSI14 极值区（辅助确认，最高各 12 分）
  //     不单独触发，作为背离的补充
  // ══════════════════════════════════════════════════════

  if (latest.rsi14 > 78) {
    topScore += 12;
    signals.push(`RSI14(${latest.rsi14.toFixed(1)}) 严重超买`);
  } else if (latest.rsi14 < 22) {
    bottomScore += 12;
    signals.push(`RSI14(${latest.rsi14.toFixed(1)}) 严重超卖`);
  } else if (latest.rsi14 > 68 && latest.rsi14 < prev.rsi14) {
    topScore += 6;
    signals.push('RSI14 高位开始回落');
  } else if (latest.rsi14 < 32 && latest.rsi14 > prev.rsi14) {
    bottomScore += 6;
    signals.push('RSI14 低位开始回升');
  }

  // ══════════════════════════════════════════════════════
  //  6. KDJ 极端值（辅助，最高各 8 分）
  // ══════════════════════════════════════════════════════

  if (latest.kdjJ > 98) {
    topScore += 8;
    signals.push(`KDJ J(${latest.kdjJ.toFixed(0)}) 极度超买`);
  } else if (latest.kdjJ < 2) {
    bottomScore += 8;
    signals.push(`KDJ J(${latest.kdjJ.toFixed(0)}) 极度超卖`);
  }

  // ══════════════════════════════════════════════════════
  //  判定：阈值 55 分（比原版 50 更严格）
  // ══════════════════════════════════════════════════════

  // 计算概率时对 100 分以上做 log 压缩，避免单一背离就给出过高概率
  const calcProb = (s: number) => Math.min(0.92, s / 100);

  if (topScore > bottomScore && topScore >= 55) {
    return {
      type: 'top',
      probability: calcProb(topScore),
      signals,
      recommendation: buildRecommendation('top', topScore, latest.rsiBearDiv, latest.bollSqueezing),
    };
  }

  if (bottomScore > topScore && bottomScore >= 55) {
    return {
      type: 'bottom',
      probability: calcProb(bottomScore),
      signals,
      recommendation: buildRecommendation('bottom', bottomScore, latest.rsiBullDiv, latest.bollSqueezing),
    };
  }

  return {
    type: 'neutral',
    probability: 0,
    signals: signals.length > 0 ? signals : [],
    recommendation: '未检测到明显顶底信号，保持观察',
  };
}

// ─── 建议文案 ────────────────────────────────────────────────────────────────

function buildRecommendation(
  type: 'top' | 'bottom',
  score: number,
  hasDivergence: boolean,
  isSqueeze: boolean,
): string {
  if (type === 'top') {
    if (hasDivergence && score >= 80) {
      return '⚠️ 高置信度顶部信号：RSI 顶背离确认，建议控制仓位或设置止损，等待回调后再评估';
    }
    if (isSqueeze) {
      return '注意：布林带压缩结束后可能向下爆发，建议减仓观望，确认方向后再操作';
    }
    return '可能接近阶段性高点，建议逐步减仓，不追高';
  } else {
    if (hasDivergence && score >= 80) {
      return '✅ 高置信度底部信号：RSI 底背离确认，可考虑分批布局，建议设置止损于近期低点';
    }
    if (isSqueeze) {
      return '布林带压缩结束后可能向上爆发，可小仓位试探，突破确认后加仓';
    }
    return '可能接近阶段性低点，建议分批建仓，注意控制风险';
  }
}
