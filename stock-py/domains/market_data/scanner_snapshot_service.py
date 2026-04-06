from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any


class ScannerSnapshotService:
    def build_snapshot(
        self, symbol: str, bars: list[dict[str, Any]], timeframe: str = "1d"
    ) -> dict[str, Any] | None:
        normalized = self._normalize_bars(bars)
        if len(normalized) < 20:
            return None

        closes = [bar["close"] for bar in normalized]
        highs = [bar["high"] for bar in normalized]
        lows = [bar["low"] for bar in normalized]
        volumes = [bar["volume"] for bar in normalized]
        current_price = closes[-1]

        sma_short = mean(closes[-5:])
        sma_long = mean(closes[-20:])
        trend_delta = ((sma_short / sma_long) - 1.0) if sma_long else 0.0
        dislocation_pct = ((current_price / sma_long) - 1.0) if sma_long else 0.0
        momentum_raw = ((current_price / closes[-5]) - 1.0) if closes[-5] else 0.0
        returns = [
            ((closes[index] / closes[index - 1]) - 1.0)
            for index in range(1, len(closes))
            if closes[index - 1]
        ]
        volatility = pstdev(returns[-20:]) if len(returns) >= 2 else 0.0
        volatility_score = min(1.0, volatility * math.sqrt(252) * 8)
        trend_strength = min(1.0, max(abs(trend_delta) * 18, abs(momentum_raw) * 14))
        direction = self._infer_direction(trend_delta, momentum_raw, dislocation_pct)
        if direction is None:
            return None

        atr = self._average_true_range(highs, lows, closes)
        atr_multiplier = 1.5
        if direction == "buy":
            stop_loss = max(0.01, current_price - (atr * atr_multiplier))
            take_profit_1 = current_price + (atr * 2.0)
            take_profit_2 = current_price + (atr * 3.2)
            take_profit_3 = current_price + (atr * 4.4)
            risk_reward_ratio = (
                ((take_profit_1 - current_price) / (current_price - stop_loss))
                if current_price > stop_loss
                else 0.0
            )
        else:
            stop_loss = current_price + (atr * atr_multiplier)
            take_profit_1 = max(0.01, current_price - (atr * 2.0))
            take_profit_2 = max(0.01, current_price - (atr * 3.2))
            take_profit_3 = max(0.01, current_price - (atr * 4.4))
            risk_reward_ratio = (
                ((current_price - take_profit_1) / (stop_loss - current_price))
                if stop_loss > current_price
                else 0.0
            )

        avg_volume = mean(volumes[-20:]) if len(volumes) >= 20 else mean(volumes)
        volume_confirmed = volumes[-1] >= (avg_volume * 1.1) if avg_volume else False
        reversal_confirmed = abs(dislocation_pct) >= 0.03
        trend_confirmed = abs(trend_delta) >= 0.01
        setup_quality = int(
            max(
                0,
                min(
                    100,
                    round(
                        45
                        + (trend_strength * 25)
                        + (min(abs(dislocation_pct), 0.08) * 300)
                        + (10 if volume_confirmed else 0)
                    ),
                ),
            )
        )
        confidence = max(
            0.0, min(100.0, 50.0 + (trend_strength * 28.0) + (8.0 if volume_confirmed else 0.0))
        )
        probability = max(
            0.0, min(1.0, 0.45 + (trend_strength * 0.25) + (0.05 if volume_confirmed else 0.0))
        )
        market_regime = (
            "volatile"
            if volatility_score >= 0.75
            else "trend" if trend_strength >= 0.6 else "range"
        )

        return {
            "symbol": symbol.strip().upper(),
            "direction": direction,
            "price": current_price,
            "last_price": current_price,
            "timeframe": timeframe,
            "dislocation_pct": abs(dislocation_pct),
            "momentum_score": max(abs(momentum_raw) * 20, trend_strength),
            "trend_strength": trend_strength,
            "volatility_score": volatility_score,
            "confidence": confidence,
            "probability": probability,
            "risk_reward_ratio": round(risk_reward_ratio, 4),
            "stop_loss": round(stop_loss, 4),
            "take_profit_1": round(take_profit_1, 4),
            "take_profit_2": round(take_profit_2, 4),
            "take_profit_3": round(take_profit_3, 4),
            "market_regime": market_regime,
            "reasons": self._build_reasons(
                direction, trend_delta, dislocation_pct, volume_confirmed
            ),
            "analysis": {
                "atr_value": round(atr, 4),
                "atr_multiplier": atr_multiplier,
                "volume_confirmed": volume_confirmed,
                "trend_confirmed": trend_confirmed,
                "reversal_confirmed": reversal_confirmed,
                "setup_quality": setup_quality,
                "strategy_window": timeframe,
                "market_regime": market_regime,
                "trend_delta": round(trend_delta, 6),
                "dislocation_pct": round(dislocation_pct, 6),
                "momentum_raw": round(momentum_raw, 6),
            },
        }

    @staticmethod
    def _normalize_bars(bars: list[dict[str, Any]]) -> list[dict[str, float]]:
        normalized: list[dict[str, float]] = []
        for bar in bars:
            try:
                normalized.append(
                    {
                        "open": float(bar["open"]),
                        "high": float(bar["high"]),
                        "low": float(bar["low"]),
                        "close": float(bar["close"]),
                        "volume": float(bar.get("volume", 0) or 0),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
        return normalized

    @staticmethod
    def _infer_direction(
        trend_delta: float, momentum_raw: float, dislocation_pct: float
    ) -> str | None:
        if trend_delta >= 0.01 or momentum_raw >= 0.015:
            return "buy"
        if trend_delta <= -0.01 or momentum_raw <= -0.015:
            return "sell"
        if dislocation_pct <= -0.03:
            return "buy"
        if dislocation_pct >= 0.03:
            return "sell"
        return None

    @staticmethod
    def _average_true_range(
        highs: list[float], lows: list[float], closes: list[float], period: int = 14
    ) -> float:
        true_ranges: list[float] = []
        for index in range(1, len(closes)):
            high = highs[index]
            low = lows[index]
            prev_close = closes[index - 1]
            true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        if not true_ranges:
            return max(0.01, highs[-1] - lows[-1])
        window = true_ranges[-period:]
        return max(0.01, mean(window))

    @staticmethod
    def _build_reasons(
        direction: str, trend_delta: float, dislocation_pct: float, volume_confirmed: bool
    ) -> list[str]:
        if direction == "buy":
            reasons = [
                (
                    "Uptrend continuation setup detected"
                    if trend_delta >= 0.01
                    else "Mean reversion long setup detected"
                )
            ]
        else:
            reasons = [
                (
                    "Downtrend continuation setup detected"
                    if trend_delta <= -0.01
                    else "Mean reversion short setup detected"
                )
            ]
        reasons.append(f"Price dislocation {dislocation_pct * 100:.2f}% vs 20-bar mean")
        if volume_confirmed:
            reasons.append("Volume expansion confirms the move")
        return reasons
