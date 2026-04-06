"""
Buy scanner - detect buy signals from watchlist stocks.

Process watchlist stocks, generate buy signals with scoring,
and notify subscribed users with position suggestions.
"""
import uuid
import hmac
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.search.stock import WatchlistItem, Stock
from domains.auth.user import User
from domains.signals.signal import Signal, SignalType
from infra.config import settings
from apps.workers.scanner.position_engine import calc_position, PositionSuggestion


# Placeholder - will integrate with actual notification/message distribution
notification_service = None  # type: ignore
message_distribution_service = None  # type: ignore


@dataclass
class BuySignal:
    """Buy signal data."""
    symbol: str
    score: int
    price: float
    reasons: list[str] = field(default_factory=list)
    analysis: dict = field(default_factory=dict)
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    confirmation_level: Optional[str] = None


@dataclass
class UserPortfolio:
    """User portfolio info for position calculation."""
    user_id: int
    email: str
    total_capital: float
    currency: str
    existing_shares: Optional[float] = None
    existing_avg_cost: Optional[float] = None


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


def _build_buy_notification_body(signal: BuySignal) -> str:
    """Build notification body for buy signal."""
    reasons_summary = ', '.join(signal.reasons[:3]) if signal.reasons else 'Buy signal detected.'
    return f"{signal.symbol} scored {signal.score}/100 at ${signal.price:.2f}. {reasons_summary}"


def _summarize_reasons(reasons: list[str], fallback: str) -> str:
    """Summarize reasons for notification."""
    if not reasons:
        return fallback
    return ', '.join(reasons[:3])


def _generate_trade_link(user_id: int, symbol: str) -> tuple[str, str]:
    """Generate trade link token and signature."""
    link_token = str(uuid.uuid4())
    link_sig = hmac.new(
        settings.TRADE_LINK_SECRET.encode(),
        f"{link_token}:{user_id}:{symbol}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return link_token, link_sig


async def process_buy_signal(signal: BuySignal, db: AsyncSession) -> Optional[int]:
    """
    Process a buy signal - insert into DB and notify subscribers.
    
    Returns the signal ID if created, None otherwise.
    """
    # Insert signal into database
    signal_obj = Signal(
        stock_id=0,  # Will be looked up
        symbol=signal.symbol,
        signal_type=SignalType.BUY,
        entry_price=signal.price,
        stop_loss=signal.stop_loss,
        take_profit_1=signal.take_profit,
        confidence=signal.score,
        reasoning=', '.join(signal.reasons) if signal.reasons else None,
    )
    db.add(signal_obj)
    await db.flush()
    
    # Look up stock to link
    stock_result = await db.execute(
        select(Stock).where(Stock.symbol == signal.symbol)
    )
    stock = stock_result.scalar_one_or_none()
    if stock:
        signal_obj.stock_id = stock.id
    
    signal_id = signal_obj.id

    # Get subscribers (users watching this symbol with notifications enabled)
    # This would join watchlist_items with user settings
    # For now, query users who have this in their watchlist
    subscribers = await _get_watchlist_subscribers(signal.symbol, db)
    
    if not subscribers:
        return signal_id

    # Load portfolio totals and pending trades
    user_ids = [s.user_id for s in subscribers]
    portfolio_totals = await _load_portfolio_totals(user_ids, db)
    pending_trades = await _load_pending_trade_actions(user_ids, signal.symbol, ['buy', 'add'], db)
    
    expires_at = (datetime.utcnow() + timedelta(days=1)).isoformat()
    notification_body = _build_buy_notification_body(signal)
    
    pending_trade_entries = []
    message_entries = []

    for sub in subscribers:
        portfolio_value = portfolio_totals.get(sub.user_id, 0)
        available_cash = sub.total_capital - portfolio_value

        # Calculate position
        suggestion = calc_position(
            total_capital=sub.total_capital,
            available_cash=available_cash,
            current_price=signal.price,
            score=signal.score,
            existing_shares=int(sub.existing_shares or 0),
            existing_avg_cost=float(sub.existing_avg_cost or 0),
            confirmation_level=signal.confirmation_level or 'full',
        )

        if not suggestion:
            continue

        # Skip if user already has pending action
        if pending_trades.get(sub.user_id, set()):
            continue

        link_token, link_sig = _generate_trade_link(sub.user_id, signal.symbol)
        trade_id = str(uuid.uuid4())

        subject = f"{'Buy' if suggestion.action == 'buy' else 'Add'} signal | {signal.symbol}"

        pending_trade_entries.append(PendingTrade(
            id=trade_id,
            user_id=sub.user_id,
            symbol=signal.symbol,
            action=suggestion.action,
            suggested_shares=suggestion.suggested_shares,
            suggested_price=suggestion.suggested_price,
            suggested_amount=suggestion.suggested_amount,
            signal_id=signal_id,
            link_token=link_token,
            link_sig=link_sig,
            expires_at=expires_at,
        ))

        message_entries.append({
            'user_id': sub.user_id,
            'signal_id': signal_id,
            'trade_id': trade_id,
            'in_app': {
                'type': 'buy_signal' if suggestion.action == 'buy' else 'add_signal',
                'title': f"{'Buy' if suggestion.action == 'buy' else 'Add'} signal: {signal.symbol}",
                'body': notification_body,
            },
            'email': {
                'email': sub.email,
                'subject': subject,
                'body_html': _build_buy_email_html(signal, suggestion, trade_id, link_token, sub, db),
                'priority': 3 if signal.score >= 90 else 5,
            },
        })

    if pending_trade_entries:
        await _insert_pending_trades(pending_trade_entries, db)
        await _distribute_messages(message_entries, db)

    return signal_id


async def _get_watchlist_subscribers(symbol: str, db: AsyncSession) -> list[UserPortfolio]:
    """Get users who have this symbol in watchlist with notifications enabled."""
    # This would be a proper SQL join in production
    # Simplified version for now
    result = await db.execute(
        select(User).where(User.is_active == True)
    )
    users = result.scalars().all()
    
    subscribers = []
    for user in users:
        # Check if user has watchlist with this symbol
        # For now, return basic user info - would be enhanced with actual watchlist check
        subscribers.append(UserPortfolio(
            user_id=user.id,
            email=user.email,
            total_capital=10000,  # Default - would come from user_account
            currency='USD',
            existing_shares=None,
            existing_avg_cost=None,
        ))
    
    return subscribers


async def _load_portfolio_totals(user_ids: list[int], db: AsyncSession) -> dict[int, float]:
    """Load total portfolio values for users."""
    # Simplified - would query actual portfolio
    return {uid: 0 for uid in user_ids}


async def _load_pending_trade_actions(
    user_ids: list[int],
    symbol: str,
    actions: list[str],
    db: AsyncSession,
) -> dict[int, set]:
    """Load pending trade actions for users."""
    # Simplified - would query pending_trades table
    return {uid: set() for uid in user_ids}


async def _insert_pending_trades(trades: list[PendingTrade], db: AsyncSession):
    """Insert pending trades into database."""
    # Would integrate with trade suggestions service
    pass


async def _distribute_messages(messages: list[dict], db: AsyncSession):
    """Distribute user messages (in-app + email)."""
    # Would integrate with message distribution service
    pass


def _build_buy_email_html(
    signal: BuySignal,
    suggestion: PositionSuggestion,
    trade_id: str,
    link_token: str,
    user: UserPortfolio,
    db: AsyncSession,
) -> str:
    """Build HTML email for buy signal."""
    app_url = settings.APP_URL or 'http://localhost:8000'
    confirm_url = f"{app_url}/api/trade/{trade_id}/confirm?action=accept&t={link_token}"
    adjust_url = f"{app_url}/trade/adjust?id={trade_id}&t={link_token}"
    ignore_url = f"{app_url}/api/trade/{trade_id}/confirm?action=ignore&t={link_token}"

    if signal.score >= 90:
        score_label = 'Strong buy'
    elif signal.score >= 80:
        score_label = 'Buy'
    elif signal.score >= 70:
        score_label = 'Moderate buy'
    else:
        score_label = 'Watch'

    after_cash = user.total_capital - user.existing_shares * user.existing_avg_cost - suggestion.suggested_amount
    action_label = 'Add position' if suggestion.action == 'add' else 'Buy'

    plan_rows = ''
    for stage in suggestion.plan:
        plan_rows += f"""
        <tr>
            <td style="padding:8px 0;color:#333;font-weight:600">{stage.label}</td>
            <td style="padding:8px 0;color:#666">{stage.target_pct}%</td>
            <td style="padding:8px 0;color:#666">{stage.suggested_shares} shares</td>
            <td style="padding:8px 0;color:#666">${stage.suggested_amount:.2f}</td>
        </tr>
        <tr>
            <td colspan="4" style="padding:0 0 10px;color:#888;font-size:12px">{stage.trigger}</td>
        </tr>
        """

    risk_frame = ''
    if signal.take_profit or signal.stop_loss:
        risk_frame = f"""
        <div style="background:#fffbe6;border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:13px">
            <p style="margin:0 0 6px;font-weight:bold">Signal risk frame</p>
            {f'<p style="margin:2px 0">Take profit reference: ${signal.take_profit:.2f}</p>' if signal.take_profit else ''}
            {f'<p style="margin:2px 0">Stop loss reference: ${signal.stop_loss:.2f}</p>' if signal.stop_loss else ''}
            {f'<p style="margin:2px 0">Confirmation: {signal.confirmation_level}</p>' if signal.confirmation_level else ''}
        </div>
        """

    reasons_html = ''.join(f"<p style='margin:2px 0'>- {reason}</p>" for reason in signal.reasons)

    return f"""
<div style="font-family:sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#333">
  <h2 style="margin:0 0 16px">{action_label} suggestion | {signal.symbol}</h2>

  <div style="background:#f0f8ff;border-radius:8px;padding:16px;margin-bottom:16px">
    <p style="margin:0 0 6px">Signal strength: <strong>{score_label} (Score: {signal.score}/100)</strong></p>
    <p style="margin:0">Current price: <strong>${signal.price:.2f}</strong></p>
  </div>

  <div style="border:1px solid #e8e8e8;border-radius:8px;padding:16px;margin-bottom:16px">
    <p style="margin:0 0 4px;font-weight:bold">Suggested action</p>
    <p style="margin:0;font-size:18px">
      {action_label} <strong>{suggestion.suggested_shares} shares</strong> x ${suggestion.suggested_price:.2f}<br>
      Estimated amount: <strong>${suggestion.suggested_amount:.2f}</strong>
    </p>
    <p style="margin:8px 0 0;font-size:13px;color:#666">{suggestion.notes}</p>
  </div>

  <div style="background:#fafafa;border-radius:8px;padding:16px;margin-bottom:16px;font-size:14px">
    <p style="margin:0 0 4px;font-weight:bold">Account snapshot</p>
    <p style="margin:2px 0">Total capital: ${user.total_capital:.0f} {user.currency}</p>
    <p style="margin:2px 0">Available cash: ${user.total_capital - (user.existing_shares or 0) * (user.existing_avg_cost or 0):.0f} -> <strong>${after_cash:.0f}</strong></p>
  </div>

  <div style="background:#fafafa;border-radius:8px;padding:16px;margin-bottom:16px;font-size:13px">
    <p style="margin:0 0 8px;font-weight:bold">Staged entry plan</p>
    <table style="width:100%;border-collapse:collapse">
      <thead>
        <tr style="text-align:left;color:#888;font-size:12px">
          <th style="padding:0 0 8px">Batch</th>
          <th style="padding:0 0 8px">Capital</th>
          <th style="padding:0 0 8px">Shares</th>
          <th style="padding:0 0 8px">Amount</th>
        </tr>
      </thead>
      <tbody>{plan_rows}</tbody>
    </table>
  </div>

  {risk_frame}

  <div style="background:#fafafa;border-radius:8px;padding:16px;margin-bottom:24px;font-size:13px">
    <p style="margin:0 0 6px;font-weight:bold">Why this triggered</p>
    {reasons_html}
  </div>

  <p style="color:#999;font-size:12px">This is an algorithmic simulation alert, not investment advice.</p>

  <div style="display:flex;gap:8px;margin-top:16px">
    <a href="{confirm_url}" style="flex:1;text-align:center;padding:12px;background:#52c41a;color:#fff;text-decoration:none;border-radius:8px;font-weight:bold">Accept</a>
    <a href="{adjust_url}" style="flex:1;text-align:center;padding:12px;background:#1677ff;color:#fff;text-decoration:none;border-radius:8px;font-weight:bold">Adjust</a>
    <a href="{ignore_url}" style="flex:1;text-align:center;padding:12px;background:#8c8c8c;color:#fff;text-decoration:none;border-radius:8px;font-weight:bold">Ignore</a>
  </div>
</div>
"""