from __future__ import annotations

import json
from typing import Any


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_payload(raw_value: Any) -> dict[str, Any]:
    if isinstance(raw_value, dict):
        return dict(raw_value)
    if isinstance(raw_value, str):
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            return {}
        return dict(payload) if isinstance(payload, dict) else {}
    return {}


def _normalize_stage(stage: Any, *, index: int) -> dict[str, Any] | None:
    if not isinstance(stage, dict):
        return None

    trigger_pct = _coerce_float(
        stage.get("trigger_pct") if stage.get("trigger_pct") is not None else stage.get("triggerPct")
    )
    sell_pct = _coerce_float(
        stage.get("sell_pct") if stage.get("sell_pct") is not None else stage.get("sellPct")
    )
    if trigger_pct is None or sell_pct is None:
        return None

    stage_id = str(stage.get("id") or f"tp{index}").strip() or f"tp{index}"
    label = str(stage.get("label") or f"Batch {index}").strip() or f"Batch {index}"
    return {
        "id": stage_id,
        "label": label,
        "trigger_pct": round(clamp(trigger_pct, 0.03, 0.8), 4),
        "sell_pct": round(clamp(sell_pct, 0.05, 1.0), 4),
    }


def _normalize_stages(raw_stages: Any, *, target_profit: float) -> list[dict[str, Any]]:
    if not isinstance(raw_stages, list):
        return build_sell_stages(target_profit)

    stages = [
        normalized_stage
        for index, stage in enumerate(raw_stages, start=1)
        if (normalized_stage := _normalize_stage(stage, index=index)) is not None
    ]
    return stages or build_sell_stages(target_profit)


def _candidate_trade_payloads(raw_trade_extra: Any) -> list[dict[str, Any]]:
    payload = _load_payload(raw_trade_extra)
    candidates = [payload]
    for key in ("signal", "analysis", "portfolio_extra", "metadata"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidates.append(dict(nested))
    return candidates


def _extract_take_profit_ratios(avg_cost: float, raw_trade_extra: Any) -> list[float]:
    ratios: list[float] = []
    if avg_cost <= 0:
        return ratios

    for payload in _candidate_trade_payloads(raw_trade_extra):
        for key in ("take_profit_1", "take_profit_2", "take_profit_3", "takeProfit1", "takeProfit2", "takeProfit3"):
            value = _coerce_float(payload.get(key))
            if value is None or value <= 0:
                continue
            if value < 1:
                ratios.append(clamp(value, 0.03, 0.8))
            elif value > avg_cost:
                ratios.append(clamp((value - avg_cost) / avg_cost, 0.03, 0.8))
    return sorted({round(ratio, 4) for ratio in ratios})


def _extract_trade_sell_plan(raw_trade_extra: Any, *, target_profit: float) -> list[dict[str, Any]] | None:
    for payload in _candidate_trade_payloads(raw_trade_extra):
        raw_sell_plan = payload.get("sell_plan") if isinstance(payload.get("sell_plan"), dict) else {}
        stages = _normalize_stages(raw_sell_plan.get("stages"), target_profit=target_profit)
        if stages:
            return stages
    return None


def build_sell_stages(
    target_profit: float,
    *,
    explicit_take_profit_ratios: list[float] | None = None,
) -> list[dict[str, Any]]:
    target_levels = [
        round(float(value), 4)
        for value in (explicit_take_profit_ratios or [])
        if value and float(value) > 0
    ][:3]
    base_target = clamp(float(target_profit or 0.15), 0.05, 0.2)

    while len(target_levels) < 1:
        target_levels.append(base_target)
    while len(target_levels) < 2:
        target_levels.append(max(target_levels[0] * 1.45, target_levels[0] + 0.08))
    while len(target_levels) < 3:
        target_levels.append(max(target_levels[1] * 1.35, target_levels[1] + 0.10))

    stage1 = clamp(target_levels[0], 0.03, 0.2)
    stage2 = clamp(max(target_levels[1], stage1 + 0.03), stage1 + 0.03, 0.4)
    stage3 = clamp(max(target_levels[2], stage2 + 0.03), stage2 + 0.03, 0.6)

    return [
        {"id": "tp1", "label": "Batch 1", "trigger_pct": round(stage1, 4), "sell_pct": 0.25},
        {"id": "tp2", "label": "Batch 2", "trigger_pct": round(stage2, 4), "sell_pct": 0.35},
        {"id": "tp3", "label": "Batch 3", "trigger_pct": round(stage3, 4), "sell_pct": 0.4},
    ]


def parse_portfolio_extra(
    raw_extra: Any,
    *,
    shares: int,
    target_profit: float,
) -> dict[str, Any]:
    payload = _load_payload(raw_extra)
    sell_plan = payload.get("sell_plan") if isinstance(payload.get("sell_plan"), dict) else {}
    progress = payload.get("sell_progress") if isinstance(payload.get("sell_progress"), dict) else {}

    base_shares = int(
        _coerce_float(
            sell_plan.get("base_shares") if sell_plan.get("base_shares") is not None else sell_plan.get("baseShares")
        )
        or shares
    )
    if base_shares < shares:
        base_shares = shares

    raw_completed = (
        progress.get("completed_stage_ids")
        if progress.get("completed_stage_ids") is not None
        else progress.get("completedStageIds")
    )
    completed_stage_ids: list[str] = []
    if isinstance(raw_completed, list):
        for item in raw_completed:
            stage_id = str(item or "").strip()
            if stage_id and stage_id not in completed_stage_ids:
                completed_stage_ids.append(stage_id)

    return {
        **payload,
        "sell_plan": {
            "base_shares": base_shares,
            "stages": _normalize_stages(sell_plan.get("stages"), target_profit=target_profit),
        },
        "sell_progress": {
            "completed_stage_ids": completed_stage_ids,
        },
    }


def resolve_target_profit_ratio(current_target_profit: float, avg_cost: float, raw_trade_extra: Any) -> float:
    for payload in _candidate_trade_payloads(raw_trade_extra):
        for key in ("take_profit_1", "takeProfit1", "target_profit", "targetProfit"):
            value = _coerce_float(payload.get(key))
            if value is None or value <= 0:
                continue
            if value < 1:
                return round(clamp(value, 0.03, 0.8), 4)
            if avg_cost > 0 and value > avg_cost:
                return round(clamp((value - avg_cost) / avg_cost, 0.03, 0.8), 4)
    return round(clamp(float(current_target_profit or 0.15), 0.03, 0.8), 4)


def resolve_stop_loss_ratio(current_stop_loss: float, avg_cost: float, raw_trade_extra: Any) -> float:
    for payload in _candidate_trade_payloads(raw_trade_extra):
        for key in ("stop_loss", "stopLoss"):
            value = _coerce_float(payload.get(key))
            if value is None or value <= 0:
                continue
            if value < 1:
                return round(clamp(value, 0.02, 0.8), 4)
            if avg_cost > 0 and value < avg_cost:
                return round(clamp((avg_cost - value) / avg_cost, 0.02, 0.8), 4)
    return round(clamp(float(current_stop_loss or 0.08), 0.02, 0.8), 4)


def build_portfolio_extra(
    raw_portfolio_extra: Any,
    *,
    shares: int,
    avg_cost: float,
    target_profit: float,
    stop_loss: float,
    trade_extra: Any,
) -> dict[str, Any]:
    payload = parse_portfolio_extra(
        raw_portfolio_extra,
        shares=shares,
        target_profit=target_profit,
    )
    explicit_sell_plan = _extract_trade_sell_plan(trade_extra, target_profit=target_profit)
    if explicit_sell_plan:
        payload["sell_plan"]["stages"] = explicit_sell_plan
    else:
        take_profit_ratios = _extract_take_profit_ratios(avg_cost, trade_extra)
        if take_profit_ratios:
            payload["sell_plan"]["stages"] = build_sell_stages(
                target_profit,
                explicit_take_profit_ratios=take_profit_ratios,
            )

    payload["sell_plan"]["base_shares"] = max(int(payload["sell_plan"]["base_shares"]), shares)
    payload["risk_frame"] = {
        "target_profit": round(clamp(float(target_profit or 0.15), 0.03, 0.8), 4),
        "stop_loss": round(clamp(float(stop_loss or 0.08), 0.02, 0.8), 4),
    }
    return payload


def apply_sell_execution(
    raw_portfolio_extra: Any,
    *,
    shares_before: int,
    shares_after: int,
    target_profit: float,
    trade_extra: Any,
) -> dict[str, Any] | None:
    if shares_after <= 0:
        return None

    payload = parse_portfolio_extra(
        raw_portfolio_extra,
        shares=shares_before,
        target_profit=target_profit,
    )
    trade_payload = _load_payload(trade_extra)
    stage_id = str(
        trade_payload.get("sell_stage_id") if trade_payload.get("sell_stage_id") is not None else trade_payload.get("sellStageId") or ""
    ).strip()
    completed_stage_ids = list(payload["sell_progress"]["completed_stage_ids"])
    if stage_id and stage_id not in completed_stage_ids:
        completed_stage_ids.append(stage_id)
    payload["sell_progress"]["completed_stage_ids"] = completed_stage_ids
    payload["sell_plan"]["base_shares"] = max(int(payload["sell_plan"]["base_shares"]), shares_before)
    payload["last_exit"] = {
        "executed_shares": max(shares_before - shares_after, 0),
        "remaining_shares": shares_after,
        "stage_id": stage_id or None,
    }
    return payload