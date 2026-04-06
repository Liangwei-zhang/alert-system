"""
Scanner tasks - periodic watchlist scanning and signal detection via Celery.
"""
from typing import Optional
from celery import group

from apps.workers.celery_app import celery_app
from infra.database import AsyncSessionLocal
from apps.workers.scanner.scanner_service import scanner_service
from apps.workers.scanner.buy_scanner import BuySignal, process_buy_signal
from apps.workers.scanner.sell_scanner import SellSignal, process_sell_signal
from domains.notifications.notification import notification_service
from domains.auth.user import User
from domains.search.stock import Stock


@celery_app.task(bind=True, max_retries=3)
def scan_watchlist_task(self, watchlist_id: int, threshold_percent: float = 5.0):
    """Scan a single watchlist for price changes."""
    import asyncio

    async def _scan():
        async with AsyncSessionLocal() as db:
            changes = await scanner_service.scan_watchlist(
                db, watchlist_id, threshold_percent
            )
            if changes:
                # Get watchlist info
                from sqlalchemy import select
                from domains.search.stock import Watchlist
                result = await db.execute(
                    select(Watchlist).where(Watchlist.id == watchlist_id)
                )
                watchlist = result.scalar_one_or_none()
                
                if watchlist:
                    # Build alert message
                    change_msgs = []
                    for c in changes:
                        emoji = "📈" if c.direction == "up" else "📉"
                        change_msgs.append(
                            f"{emoji} {c.symbol}: ${c.old_price:.2f} → ${c.new_price:.2f} ({c.change_percent:+.2f}%)"
                        )
                    
                    alert_text = f"🔔 Price Alert: {watchlist.name}\n" + "\n".join(change_msgs)
                    
                    # Notify user
                    user_result = await db.execute(
                        select(User).where(User.id == watchlist.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    if user:
                        await notification_service.send_notification(
                            user_id=user.id,
                            title="Price Alert",
                            message=alert_text
                        )
            return len(changes)

    return asyncio.run(_scan())


@celery_app.task(bind=True, max_retries=3)
def scan_all_watchlists_task(self, threshold_percent: float = 5.0):
    """Scan all watchlists for price changes."""
    import asyncio

    async def _scan():
        async with AsyncSessionLocal() as db:
            changes_by_watchlist = await scanner_service.scan_all_watchlists(
                db, threshold_percent
            )
            total_changes = sum(len(changes) for changes in changes_by_watchlist.values())
            return {
                "watchlists_scanned": len(changes_by_watchlist),
                "total_alerts": total_changes,
                "details": changes_by_watchlist
            }

    return asyncio.run(_scan())


@celery_app.task
def periodic_scanner_task():
    """Run periodic scan on all watchlists - called by Celery beat."""
    return scan_all_watchlists_task.delay(5.0)


# Convenience function to schedule periodic scans
def schedule_periodic_scans():
    """Schedule periodic scanner tasks (call once at startup)."""
    from celery.schedules import crontab
    
    celery_app.conf.beat_schedule = {
        "scan-watchlists-every-15-min": {
            "task": "app.tasks.scanner_tasks.periodic_scanner_task",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
        },
    }


# ============== Buy/Sell Signal Detection Tasks ==============

@celery_app.task(bind=True, max_retries=3)
def scan_buy_signals_task(self, min_score: int = 70):
    """
    Scan watchlist stocks for buy signals.
    
    Args:
        min_score: Minimum score threshold for buy signals (default 70)
    """
    import asyncio
    
    async def _scan():
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            
            # Get all stocks in watchlists that have notifications enabled
            result = await db.execute(
                select(Stock).where(Stock.current_price.isnot(None))
            )
            stocks = result.scalars().all()
            
            signals_created = 0
            for stock in stocks:
                # In production, this would call the actual signal generation logic
                # For now, just simulate scanning
                if stock.current_price and stock.current_price > 0:
                    # Placeholder for actual signal generation
                    # Would integrate with signal_service.generate_buy_signals()
                    pass
            
            return {
                "stocks_scanned": len(stocks),
                "signals_created": signals_created,
            }
    
    return asyncio.run(_scan())


@celery_app.task(bind=True, max_retries=3)
def scan_sell_signals_task(self):
    """
    Scan portfolio positions for sell signals.
    
    Checks for:
    - Stop loss triggers
    - Take profit stage triggers
    - SMC top probability signals
    """
    import asyncio
    
    async def _scan():
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            from domains.portfolio.portfolio import Position
            
            # Get all positions with notifications enabled
            result = await db.execute(
                select(Position).where(Position.quantity > 0)
            )
            positions = result.scalars().all()
            
            signals_triggered = 0
            for position in positions:
                # In production, this would check actual P&L vs targets
                # Would integrate with sell_scanner.process_sell_signal()
                pass
            
            return {
                "positions_scanned": len(positions),
                "signals_triggered": signals_triggered,
            }
    
    return asyncio.run(_scan())


@celery_app.task(bind=True, max_retries=2)
def process_buy_signal_task(
    self,
    symbol: str,
    score: int,
    price: float,
    reasons: list[str],
    analysis: Optional[dict] = None,
    take_profit: Optional[float] = None,
    stop_loss: Optional[float] = None,
):
    """
    Process a specific buy signal and notify subscribers.
    
    Args:
        symbol: Stock symbol
        score: Signal score (0-100)
        price: Current price
        reasons: List of reasons for the signal
        analysis: Additional analysis data
        take_profit: Optional take profit level
        stop_loss: Optional stop loss level
    """
    import asyncio
    
    async def _process():
        async with AsyncSessionLocal() as db:
            signal = BuySignal(
                symbol=symbol,
                score=score,
                price=price,
                reasons=reasons,
                analysis=analysis or {},
                take_profit=take_profit,
                stop_loss=stop_loss,
            )
            signal_id = await process_buy_signal(signal, db)
            await db.commit()
            return signal_id
    
    return asyncio.run(_process())


@celery_app.task(bind=True, max_retries=2)
def process_sell_signal_task(
    self,
    symbol: str,
    current_price: float,
    smc_top_probability: Optional[float] = None,
    score: Optional[int] = None,
    reasons: Optional[list[str]] = None,
    analysis: Optional[dict] = None,
    take_profit: Optional[float] = None,
    stop_loss: Optional[float] = None,
):
    """
    Process a specific sell signal and notify affected users.
    
    Args:
        symbol: Stock symbol
        current_price: Current market price
        smc_top_probability: SMC top reversal probability (0-1)
        score: Optional signal score
        reasons: Optional list of reasons
        analysis: Additional analysis data
        take_profit: Override take profit level
        stop_loss: Override stop loss level
    """
    import asyncio
    
    async def _process():
        async with AsyncSessionLocal() as db:
            signal = SellSignal(
                symbol=symbol,
                current_price=current_price,
                smc_top_probability=smc_top_probability,
                score=score,
                reasons=reasons,
                analysis=analysis,
                take_profit=take_profit,
                stop_loss=stop_loss,
            )
            signal_id = await process_sell_signal(signal, db)
            await db.commit()
            return signal_id
    
    return asyncio.run(_process())


# Convenience function to schedule signal scanning
def schedule_signal_scans():
    """Schedule periodic buy/sell signal scanning tasks."""
    from celery.schedules import crontab
    
    # Add to existing schedule
    existing = getattr(celery_app.conf, 'beat_schedule', {})
    
    existing.update({
        "scan-buy-signals-every-hour": {
            "task": "app.tasks.scanner_tasks.scan_buy_signals_task",
            "schedule": crontab(minute=0),  # Every hour
            "args": (70,),
        },
        "scan-sell-signals-every-hour": {
            "task": "app.tasks.scanner_tasks.scan_sell_signals_task",
            "schedule": crontab(minute=30),  # Every hour at :30
        },
    })
    
    celery_app.conf.beat_schedule = existing