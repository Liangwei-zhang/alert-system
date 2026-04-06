"""
Sell scanner - detect sell signals from user positions.

Process portfolio positions, calculate P&L vs targets,
and notify users with sell/trim suggestions.
"""
import uuid
import hmac
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.portfolio.portfolio import Position
from domains.auth.user import User
from domains.signals.signal import Signal, SignalType
from infra.config import settings
from apps.workers.scanner.position_engine import (
    calc_sell_decision,
    parse_portfolio_extra,
    build_sell_stages,
    clamp,
    normalize_pct,
    SellPlanStage,
    PortfolioExtra,
    SellDecision,
)


# Placeholder - will integrate with actual notification/message distribution
notification_service = None  # type: ignore
message_distribution_service = None  # type: ignore


@dataclass
class SellSignal:
    """Sell signal data."""
    symbol: str
    current_price: float
    smc_top_probability: Optional[float] = None
    score: Optional[int] = None
    reasons: Optional[list[str]] = None
    analysis: Optional[dict] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    confirmation_level: Optional[str] = None


@dataclass
class PortfolioInfo:
    """Portfolio position info for sell decision."""
    id: int
    user_id: int
    email: str
    symbol: str
    shares: int
    avg_cost: float
    total_capital: float
    target_profit: float
    stop_loss: float
    currency: str
    extra: dict = field(default_factory=dict)


@dataclass
class PendingTrade:
    """Pending trade for user confirmation."""
    id: str
    user_id: int
    symbol: str
    action: str
    suggested_shares: int
    suggested_price: float
    suggested_amount: float
    signal_id: int
    link_token: str
    link_sig: str
    expires_at: str
    extra: dict = field(default_factory=dict)


def _normalize_reasons(signal: SellSignal, fallback: str) -> list[str]:
    """Normalize reasons list."""
    if not signal.reasons:
        return [fallback]
    reasons = [r.strip() for r in signal.reasons if r.strip()][:8]
    return reasons if reasons else [fallback]


def _build_sell_notification_body(
    symbol: str,
    current_price: float,
    reasons: list[str],
    fallback: str,
) -> str:
    """Build notification body for sell signal."""
    reasons_summary = ', '.join(reasons[:3]) if reasons else fallback
    return f"{symbol} at ${current_price:.2f}. {reasons_summary}"


def _generate_trade_link(user_id: int, symbol: str) -> tuple[str, str]:
    """Generate trade link token and signature."""
    link_token = str(uuid.uuid4())
    link_sig = hmac.new(
        settings.TRADE_LINK_SECRET.encode(),
        f"{link_token}:{user_id}:{symbol}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return link_token, link_sig


async def process_sell_signal(signal: SellSignal, db: AsyncSession) -> Optional[int]:
    """
    Process a sell signal - evaluate positions and notify users.
    
    Returns the signal ID if created, None otherwise.
    """
    symbol = signal.symbol
    current_price = signal.current_price
    smc_top_probability = signal.smc_top_probability or 0

    # Get all positions for this symbol with notifications enabled
    positions = await _get_portfolio_positions(symbol, db)
    
    if not positions:
        return None

    # Load pending trade actions
    user_ids = [p.user_id for p in positions]
    pending_trades = await _load_pending_trade_actions(user_ids, symbol, ['sell'], db)

    expires_at = (datetime.utcnow() + timedelta(days=1)).isoformat()
    signal_ids: dict[str, int] = {}
    pending_trade_entries = []
    message_entries = []

    for portfolio in positions:
        shares = portfolio.shares
        avg_cost = portfolio.avg_cost

        # Calculate target profit and stop loss
        target_profit = signal.take_profit if signal.take_profit else portfolio.target_profit
        stop_loss = signal.stop_loss if signal.stop_loss else portfolio.stop_loss

        # Apply clamping
        if signal.take_profit and avg_cost > 0:
            target_profit = clamp(
                (signal.take_profit - avg_cost) / avg_cost,
                0.03,
                0.5,
            )
        if signal.stop_loss and avg_cost > 0:
            stop_loss = clamp(
                (avg_cost - signal.stop_loss) / avg_cost,
                0.02,
                0.5,
            )

        # Parse portfolio extra
        extra = parse_portfolio_extra(portfolio.extra, shares, target_profit)

        # Calculate sell decision
        decision = calc_sell_decision(
            shares=shares,
            avg_cost=avg_cost,
            current_price=current_price,
            target_profit=target_profit,
            stop_loss=stop_loss,
            smc_top_probability=smc_top_probability,
            extra=extra,
        )

        if not decision:
            continue

        # Skip if user already has pending sell action
        if pending_trades.get(portfolio.user_id, set()):
            continue

        # Calculate sell shares
        completed_stages = set(extra.sell_progress_completed_stage_ids)
        pending_stages = [s for s in decision.stages if s.id not in completed_stages]
        
        if not decision.stage_id or len(pending_stages) <= 1:
            sell_shares = shares
        else:
            base_shares = extra.sell_plan_base_shares or shares
            sell_shares = min(shares, max(1, int(base_shares * decision.sell_pct)))

        if sell_shares < 1:
            continue

        suggested_amount = round(sell_shares * current_price, 2)
        pnl = round((current_price - avg_cost) * sell_shares, 2)
        pnl_pct = round(((current_price - avg_cost) / avg_cost) * 100, 2)

        is_stopping = pnl_pct < 0
        trade_type = 'stop_loss' if is_stopping else 'sell'
        signal_reasons = _normalize_reasons(signal, decision.reason)

        # Determine score
        signal_score = 30 if is_stopping else max(50, min(100, signal.score or 75))

        # Insert signal if not already done for this type
        if trade_type not in signal_ids:
            signal_id = await _insert_signal(
                symbol=symbol,
                trade_type=trade_type,
                score=signal_score,
                price=current_price,
                reasons=signal_reasons,
                analysis=signal.analysis or {},
                db=db,
            )
            if not signal_id:
                continue
            signal_ids[trade_type] = signal_id
        else:
            signal_id = signal_ids[trade_type]

        # Generate trade link
        link_token, link_sig = _generate_trade_link(portfolio.user_id, symbol)
        trade_id = str(uuid.uuid4())

        # Build trade extra with sell plan info
        trade_extra = {
            'sellStageId': decision.stage_id,
            'sellPlan': {
                'baseShares': extra.sell_plan_base_shares or shares,
                'stages': [
                    {'id': s.id, 'label': s.label, 'triggerPct': s.trigger_pct, 'sellPct': s.sell_pct}
                    for s in decision.stages
                ],
            },
        }

        subject = f"{'Stop loss alert' if is_stopping else 'Take profit suggestion'} | {symbol}"

        pending_trade_entries.append(PendingTrade(
            id=trade_id,
            user_id=portfolio.user_id,
            symbol=symbol,
            action='sell',
            suggested_shares=sell_shares,
            suggested_price=current_price,
            suggested_amount=suggested_amount,
            signal_id=signal_id,
            link_token=link_token,
            link_sig=link_sig,
            expires_at=expires_at,
            extra=trade_extra,
        ))

        message_entries.append({
            'user_id': portfolio.user_id,
            'signal_id': signal_id,
            'trade_id': trade_id,
            'in_app': {
                'type': 'stop_loss_signal' if is_stopping else 'sell_signal',
                'title': f"{'Stop loss' if is_stopping else 'Sell'} signal: {symbol}",
                'body': _build_sell_notification_body(symbol, current_price, signal_reasons, decision.reason),
            },
            'email': {
                'email': portfolio.email,
                'subject': subject,
                'body_html': _build_sell_email_html(
                    symbol=symbol,
                    is_stopping=is_stopping,
                    shares=shares,
                    avg_cost=avg_cost,
                    current_price=current_price,
                    sell_shares=sell_shares,
                    suggested_amount=suggested_amount,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    reason=decision.reason,
                    trade_id=trade_id,
                    link_token=link_token,
                    currency=portfolio.currency,
                    remain_shares=shares - sell_shares,
                    stages=decision.stages,
                    active_stage_id=decision.stage_id,
                    stop_loss_pct=decision.stop_loss_pct,
                ),
                'priority': 1 if is_stopping else 5,
            },
        })

    if pending_trade_entries:
        await _insert_pending_trades(pending_trade_entries, db)
        await _distribute_messages(message_entries, db)

    return signal_ids.get('sell') or signal_ids.get('stop_loss')


async def _get_portfolio_positions(symbol: str, db: AsyncSession) -> list[PortfolioInfo]:
    """Get all positions for a symbol with notifications enabled."""
    result = await db.execute(
        select(Position).where(Position.stock.has(symbol=symbol))
    )
    positions = result.scalars().all()
    
    # In production, would join with user and user_account tables
    # Simplified for now
    portfolios = []
    for pos in positions:
        portfolios.append(PortfolioInfo(
            id=pos.id,
            user_id=pos.portfolio_id,  # Would be actual user_id
            email='user@example.com',   # Would come from user table
            symbol=symbol,
            shares=pos.quantity,
            avg_cost=float(pos.average_cost),
            total_capital=10000,  # Would come from user_account
            target_profit=0.15,   # Would come from position or user settings
            stop_loss=0.05,       # Would come from position or user settings
            currency='USD',
            extra={},
        ))
    
    return portfolios


async def _load_pending_trade_actions(
    user_ids: list[int],
    symbol: str,
    actions: list[str],
    db: AsyncSession,
) -> dict[int, set]:
    """Load pending trade actions for users."""
    # Simplified - would query pending_trades table
    return {uid: set() for uid in user_ids}


async def _insert_signal(
    symbol: str,
    trade_type: str,
    score: int,
    price: float,
    reasons: list[str],
    analysis: dict,
    db: AsyncSession,
) -> Optional[int]:
    """Insert signal into database."""
    signal_type = SignalType.SELL if trade_type == 'sell' else SignalType.BUY
    
    signal_obj = Signal(
        stock_id=0,  # Would be looked up
        symbol=symbol,
        signal_type=signal_type,
        entry_price=price,
        confidence=score,
        reasoning=', '.join(reasons) if reasons else None,
    )
    db.add(signal_obj)
    await db.flush()
    return signal_obj.id


async def _insert_pending_trades(trades: list[PendingTrade], db: AsyncSession):
    """Insert pending trades into database."""
    # Would integrate with trade suggestions service
    pass


async def _distribute_messages(messages: list[dict], db: AsyncSession):
    """Distribute user messages (in-app + email)."""
    # Would integrate with message distribution service
    pass


def _build_sell_email_html(params: dict) -> str:
    """Build HTML email for sell signal."""
    symbol = params['symbol']
    is_stopping = params['is_stopping']
    shares = params['shares']
    avg_cost = params['avg_cost']
    current_price = params['current_price']
    sell_shares = params['sell_shares']
    suggested_amount = params['suggested_amount']
    pnl = params['pnl']
    pnl_pct = params['pnl_pct']
    reason = params['reason']
    trade_id = params['trade_id']
    link_token = params['link_token']
    currency = params['currency']
    remain_shares = params['remain_shares']
    stages = params['stages']
    active_stage_id = params['active_stage_id']
    stop_loss_pct = params['stop_loss_pct']

    app_url = settings.APP_URL or 'http://localhost:8000'
    confirm_url = f"{app_url}/api/trade/{trade_id}/confirm?action=accept&t={link_token}"
    adjust_url = f"{app_url}/trade/adjust?id={trade_id}&t={link_token}"
    ignore_url = f"{app_url}/api/trade/{trade_id}/confirm?action=ignore&t={link_token}"

    title = 'Stop loss alert' if is_stopping else 'Take profit suggestion'
    pnl_color = '#52c41a' if pnl_pct >= 0 else '#ff4d4f'

    stage_rows = ''
    for stage in stages:
        is_active = stage.id == active_stage_id
        bg_style = 'background:rgba(82,196,26,0.08);' if is_active else ''
        stage_rows += f"""
        <tr style="{bg_style}">
            <td style="padding:8px 0;font-weight:600">{stage.label}</td>
            <td style="padding:8px 0">{normalize_pct(stage.trigger_pct)}%</td>
            <td style="padding:8px 0">{normalize_pct(stage.sell_pct)}%</td>
        </tr>
        """

    remain_html = f"<p style='margin:8px 0 0;font-size:13px;color:#666'>Remaining position after execution: {remain_shares} shares</p>" if remain_shares > 0 else ""

    return f"""
<div style="font-family:sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#333">
  <h2 style="margin:0 0 16px">{title} | {symbol}</h2>

  <div style="background:#fafafa;border-radius:8px;padding:16px;margin-bottom:16px;font-size:14px">
    <p style="margin:2px 0">Current holding: {shares} shares x cost ${avg_cost:.2f}</p>
    <p style="margin:2px 0">Current price: <strong>${current_price:.2f}</strong></p>
    <p style="margin:2px 0">P&L: <strong style="color:{pnl_color}">{'+' if pnl_pct >= 0 else ''}${pnl:.0f} ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%)</strong></p>
    <p style="margin:2px 0">Protective stop frame: <strong>{normalize_pct(stop_loss_pct)}%</strong></p>
  </div>

  <div style="border:1px solid #e8e8e8;border-radius:8px;padding:16px;margin-bottom:16px">
    <p style="margin:0 0 4px;font-weight:bold">Suggested action</p>
    <p style="margin:0;font-size:18px">
      Sell <strong>{sell_shares} shares</strong> x ${current_price:.2f}<br>
      Estimated proceeds: <strong>${suggested_amount:.2f}</strong>
    </p>
    {remain_html}
  </div>

  <div style="background:#fafafa;border-radius:8px;padding:16px;margin-bottom:16px;font-size:13px">
    <p style="margin:0 0 8px;font-weight:bold">Staged exit plan</p>
    <table style="width:100%;border-collapse:collapse">
      <thead>
        <tr style="text-align:left;color:#888;font-size:12px">
          <th style="padding:0 0 8px">Batch</th>
          <th style="padding:0 0 8px">Trigger</th>
          <th style="padding:0 0 8px">Trim</th>
        </tr>
      </thead>
      <tbody>{stage_rows}</tbody>
    </table>
  </div>

  <div style="background:#fffbe6;border-radius:8px;padding:12px 16px;margin-bottom:24px;font-size:13px">
    {reason}
  </div>

  <p style="color:#999;font-size:12px">This is an algorithmic simulation alert, not investment advice.</p>

  <div style="display:flex;gap:8px;margin-top:16px">
    <a href="{confirm_url}" style="flex:1;text-align:center;padding:12px;background:#52c41a;color:#fff;text-decoration:none;border-radius:8px;font-weight:bold">Accept</a>
    <a href="{adjust_url}" style="flex:1;text-align:center;padding:12px;background:#1677ff;color:#fff;text-decoration:none;border-radius:8px;font-weight:bold">Adjust</a>
    <a href="{ignore_url}" style="flex:1;text-align:center;padding:12px;background:#8c8c8c;color:#fff;text-decoration:none;border-radius:8px;font-weight:bold">Ignore</a>
  </div>
</div>
"""