from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domains.signals.market_regime import MarketRegimeDetector


@dataclass(frozen=True)
class ExitLevelSet:
    stop_loss: float | None
    take_profit_1: float | None
    take_profit_2: float | None
    take_profit_3: float | None
    source: str
    atr_value: float | None
    atr_multiplier: float | None
    field_sources: dict[str, str]
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "take_profit_3": self.take_profit_3,
            "source": self.source,
            "atr_value": self.atr_value,
            "atr_multiplier": self.atr_multiplier,
            "field_sources": dict(self.field_sources),
            "notes": list(self.notes),
        }


class ExitLevelCalculator:
    DEFAULT_ATR_MULTIPLIERS = {
        "trend": 2.2,
        "volatile": 2.8,
        "range": 1.8,
    }
    TAKE_PROFIT_MULTIPLIERS = (1.5, 2.5, 4.0)

    def calculate(
        self,
        *,
        signal_type: str | None,
        entry_price: float | None,
        market_snapshot: dict[str, Any] | None = None,
        analysis: dict[str, Any] | None = None,
        market_regime: str | None = None,
        risk_reward_ratio: float | None = None,
    ) -> dict[str, Any]:
        snapshot = market_snapshot if isinstance(market_snapshot, dict) else {}
        analysis_payload = analysis if isinstance(analysis, dict) else {}
        explicit_levels = {
            "stop_loss": self._first_present(snapshot.get("stop_loss"), analysis_payload.get("stop_loss")),
            "take_profit_1": self._first_present(snapshot.get("take_profit_1"), analysis_payload.get("take_profit_1")),
            "take_profit_2": self._first_present(snapshot.get("take_profit_2"), analysis_payload.get("take_profit_2")),
            "take_profit_3": self._first_present(snapshot.get("take_profit_3"), analysis_payload.get("take_profit_3")),
        }
        explicit_levels = {
            key: self._coerce_float(value)
            for key, value in explicit_levels.items()
        }
        explicit_fields = {key for key, value in explicit_levels.items() if value is not None}

        normalized_regime = MarketRegimeDetector.normalize_family(str(market_regime or analysis_payload.get("market_regime") or snapshot.get("market_regime") or "range"))
        atr_value = self._coerce_float(self._first_present(snapshot.get("atr_value"), analysis_payload.get("atr_value")))
        atr_multiplier = self._coerce_float(self._first_present(snapshot.get("atr_multiplier"), analysis_payload.get("atr_multiplier")))
        if atr_multiplier is None:
            atr_multiplier = self.DEFAULT_ATR_MULTIPLIERS.get(normalized_regime, 2.0)

        computed_levels, notes = self._compute_default_levels(
            signal_type=signal_type,
            entry_price=entry_price,
            atr_value=atr_value,
            atr_multiplier=atr_multiplier,
            risk_reward_ratio=risk_reward_ratio,
        )

        resolved_levels: dict[str, float | None] = {}
        field_sources: dict[str, str] = {}
        for field_name in ("stop_loss", "take_profit_1", "take_profit_2", "take_profit_3"):
            explicit_value = explicit_levels.get(field_name)
            computed_value = computed_levels.get(field_name)
            if explicit_value is not None:
                resolved_levels[field_name] = explicit_value
                field_sources[field_name] = "client"
            elif computed_value is not None:
                resolved_levels[field_name] = computed_value
                field_sources[field_name] = "server_default"
            else:
                resolved_levels[field_name] = None
                field_sources[field_name] = "unavailable"

        source = self._resolve_source(field_sources)
        return ExitLevelSet(
            stop_loss=resolved_levels["stop_loss"],
            take_profit_1=resolved_levels["take_profit_1"],
            take_profit_2=resolved_levels["take_profit_2"],
            take_profit_3=resolved_levels["take_profit_3"],
            source=source,
            atr_value=atr_value,
            atr_multiplier=atr_multiplier,
            field_sources=field_sources,
            notes=tuple(notes),
        ).to_dict()

    def _compute_default_levels(
        self,
        *,
        signal_type: str | None,
        entry_price: float | None,
        atr_value: float | None,
        atr_multiplier: float,
        risk_reward_ratio: float | None,
    ) -> tuple[dict[str, float | None], list[str]]:
        notes: list[str] = []
        if signal_type not in {"buy", "sell", "split_buy", "split_sell"}:
            return {
                "stop_loss": None,
                "take_profit_1": None,
                "take_profit_2": None,
                "take_profit_3": None,
            }, ["signal-type-unavailable"]
        if entry_price is None or entry_price <= 0:
            return {
                "stop_loss": None,
                "take_profit_1": None,
                "take_profit_2": None,
                "take_profit_3": None,
            }, ["entry-price-unavailable"]
        if atr_value is None or atr_value <= 0:
            notes.append("atr-unavailable")
            return {
                "stop_loss": None,
                "take_profit_1": None,
                "take_profit_2": None,
                "take_profit_3": None,
            }, notes

        stop_distance = atr_value * atr_multiplier
        tp_multipliers = list(self.TAKE_PROFIT_MULTIPLIERS)
        if risk_reward_ratio is not None and risk_reward_ratio > 0:
            tp_multipliers[-1] = max(tp_multipliers[-1], risk_reward_ratio * atr_multiplier)

        is_long = signal_type in {"buy", "split_buy"}
        direction = 1.0 if is_long else -1.0
        return {
            "stop_loss": round(entry_price - (direction * stop_distance), 4),
            "take_profit_1": round(entry_price + (direction * atr_value * tp_multipliers[0]), 4),
            "take_profit_2": round(entry_price + (direction * atr_value * tp_multipliers[1]), 4),
            "take_profit_3": round(entry_price + (direction * atr_value * tp_multipliers[2]), 4),
        }, notes

    @staticmethod
    def _resolve_source(field_sources: dict[str, str]) -> str:
        values = set(field_sources.values())
        if values == {"client"}:
            return "client"
        if values <= {"server_default", "unavailable"} and "server_default" in values:
            return "server_default"
        if "client" in values and "server_default" in values:
            return "server_adjusted"
        return "unavailable"

    @staticmethod
    def _first_present(*values: Any) -> Any:
        for value in values:
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None