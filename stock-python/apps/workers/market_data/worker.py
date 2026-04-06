"""
Market Data Worker - Background tasks for market data operations.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from infra.database import async_session_maker
from domains.market_data.symbol_sync_service import SymbolSyncService
from domains.market_data.ohlcv_import_service import OhlcvImportService
from domains.market_data.quality_service import OhlcvQualityService
from domains.market_data.repository import SymbolRepository

logger = logging.getLogger(__name__)


# ============================================
# Symbol Sync Tasks
# ============================================


@shared_task(name="market_data.sync_symbol", bind=True, max_retries=3)
def sync_symbol(self, symbol: str, **kwargs):
    """
    Sync a single symbol's metadata from external source.
    """
    async def _sync():
        async with async_session_maker() as session:
            service = SymbolSyncService(session)
            result = await service.sync_symbol(
                symbol=symbol,
                name=kwargs.get("name", symbol),
                exchange=kwargs.get("exchange"),
                asset_type=kwargs.get("asset_type", "stock"),
                sector=kwargs.get("sector"),
                industry=kwargs.get("industry"),
                currency=kwargs.get("currency", "USD"),
                data_source=kwargs.get("data_source", "yahoo"),
            )
            await session.commit()
            return result
    
    # Run sync
    try:
        result = asyncio.get_event_loop().run_until_complete(_sync())
        logger.info(f"Symbol {symbol} synced: {result}")
        return {"success": True, "symbol": symbol, "result": result}
    except Exception as e:
        logger.error(f"Failed to sync symbol {symbol}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(name="market_data.sync_symbols_batch", bind=True)
def sync_symbols_batch(self, symbols: List[Dict[str, Any]], data_source: str = "yahoo"):
    """
    Batch sync multiple symbols.
    """
    async def _sync_batch():
        async with async_session_maker() as session:
            service = SymbolSyncService(session)
            result = await service.sync_batch(symbols, data_source)
            await session.commit()
            return result
    
    try:
        result = asyncio.get_event_loop().run_until_complete(_sync_batch())
        logger.info(f"Batch sync completed: {result}")
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Failed to batch sync symbols: {e}")
        return {"success": False, "error": str(e)}


@shared_task(name="market_data.sync_from_yahoo")
def sync_from_yahoo(symbols: List[str]):
    """
    Sync symbols from Yahoo Finance.
    """
    async def _sync():
        async with async_session_maker() as session:
            service = SymbolSyncService(session)
            result = await service.sync_from_yahoo(symbols)
            await session.commit()
            return result
    
    try:
        result = asyncio.get_event_loop().run_until_complete(_sync())
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Failed to sync from Yahoo: {e}")
        return {"success": False, "error": str(e)}


# ============================================
# OHLCV Import Tasks
# ============================================


@shared_task(name="market_data.import_ohlcv", bind=True, max_retries=3)
def import_ohlcv(
    self,
    symbol: str,
    timeframe: str = "1d",
    data: List[Dict[str, Any]] = None,
    source: str = "yahoo",
):
    """
    Import OHLCV data for a symbol.
    """
    async def _import():
        async with async_session_maker() as session:
            service = OhlcvImportService(session)
            result = await service.import_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                data=data or [],
                source=source,
            )
            await session.commit()
            return result
    
    try:
        result = asyncio.get_event_loop().run_until_complete(_import())
        logger.info(f"OHLCV imported for {symbol}: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to import OHLCV for {symbol}: {e}")
        raise self.retry(exc=e, countdown=120)


@shared_task(name="market_data.import_ohlcv_range")
def import_ohlcv_range(
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str = "1d",
    source: str = "yahoo",
):
    """
    Import OHLCV data for a date range.
    """
    async def _import():
        async with async_session_maker() as session:
            service = OhlcvImportService(session)
            result = await service.import_from_yahoo(
                symbol=symbol,
                start_date=datetime.fromisoformat(start_date),
                end_date=datetime.fromisoformat(end_date),
                timeframe=timeframe,
            )
            await session.commit()
            return result
    
    try:
        result = asyncio.get_event_loop().run_until_complete(_import())
        return result
    except Exception as e:
        logger.error(f"Failed to import OHLCV range for {symbol}: {e}")
        return {"success": False, "error": str(e)}


@shared_task(name="market_data.import_ohlcv_batch")
def import_ohlcv_batch(
    symbols: List[str],
    start_date: str,
    end_date: str,
    timeframe: str = "1d",
):
    """
    Batch import OHLCV for multiple symbols.
    """
    results = []
    
    for symbol in symbols:
        task = import_ohlcv_range.delay(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )
        results.append({"symbol": symbol, "task_id": task.id})
    
    return {
        "success": True,
        "total": len(symbols),
        "tasks": results,
    }


# ============================================
# Quality Check Tasks
# ============================================


@shared_task(name="market_data.check_quality")
def check_quality(
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str = "1d",
):
    """
    Run quality check on OHLCV data for a symbol.
    """
    async def _check():
        async with async_session_maker() as session:
            service = OhlcvQualityService(session)
            result = await service.check_symbol_quality(
                symbol=symbol,
                start_date=datetime.fromisoformat(start_date),
                end_date=datetime.fromisoformat(end_date),
                timeframe=timeframe,
            )
            await session.commit()
            return result
    
    try:
        result = asyncio.get_event_loop().run_until_complete(_check())
        logger.info(f"Quality check for {symbol}: {result.get('quality_score')}")
        return result
    except Exception as e:
        logger.error(f"Failed quality check for {symbol}: {e}")
        return {"success": False, "error": str(e)}


@shared_task(name="market_data.check_quality_batch")
def check_quality_batch(symbols: List[str], days_back: int = 30, timeframe: str = "1d"):
    """
    Run quality check on multiple symbols.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    
    results = []
    
    for symbol in symbols:
        task = check_quality.delay(
            symbol=symbol,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            timeframe=timeframe,
        )
        results.append({"symbol": symbol, "task_id": task.id})
    
    return {
        "success": True,
        "total": len(symbols),
        "tasks": results,
    }


@shared_task(name="market_data.resolve_anomaly")
def resolve_anomaly(anomaly_id: int, notes: Optional[str] = None):
    """
    Mark a quality anomaly as resolved.
    """
    async def _resolve():
        async with async_session_maker() as session:
            service = OhlcvQualityService(session)
            result = await service.resolve_anomaly(anomaly_id, notes)
            await session.commit()
            return result
    
    try:
        result = asyncio.get_event_loop().run_until_complete(_resolve())
        return {"success": result, "anomaly_id": anomaly_id}
    except Exception as e:
        logger.error(f"Failed to resolve anomaly {anomaly_id}: {e}")
        return {"success": False, "error": str(e)}


# ============================================
# Scheduled Tasks
# ============================================


@shared_task(name="market_data.daily_symbol_sync")
def daily_symbol_sync():
    """
    Daily scheduled task to sync all active symbols.
    """
    async def _sync():
        async with async_session_maker() as session:
            repo = SymbolRepository(session)
            symbols, total = await repo.get_all(status="active", limit=1000)
            
            sync_service = SymbolSyncService(session)
            results = await sync_service.sync_batch(
                [
                    {
                        "symbol": s.symbol,
                        "name": s.name,
                        "exchange": s.exchange,
                        "asset_type": s.asset_type.value,
                    }
                    for s in symbols
                ]
            )
            await session.commit()
            return results
    
    try:
        result = asyncio.get_event_loop().run_until_complete(_sync())
        logger.info(f"Daily symbol sync completed: {result}")
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Daily symbol sync failed: {e}")
        return {"success": False, "error": str(e)}


@shared_task(name="market_data.daily_quality_check")
def daily_quality_check(days_back: int = 30):
    """
    Daily scheduled task to run quality checks on all active symbols.
    """
    async def _check():
        async with async_session_maker() as session:
            repo = SymbolRepository(session)
            symbols, total = await repo.get_all(status="active", limit=1000)
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days_back)
            
            quality_service = OhlcvQualityService(session)
            results = []
            
            for symbol in symbols:
                result = await quality_service.check_symbol_quality(
                    symbol=symbol.symbol,
                    start_date=start_date,
                    end_date=end_date,
                )
                results.append(result)
            
            await session.commit()
            return results
    
    try:
        results = asyncio.get_event_loop().run_until_complete(_check())
        
        # Calculate summary
        total_checked = len(results)
        avg_score = sum(r.get("quality_score", 0) for r in results) / total_checked if total_checked > 0 else 0
        
        logger.info(f"Daily quality check completed: {total_checked} symbols, avg score: {avg_score:.2f}")
        
        return {
            "success": True,
            "total_checked": total_checked,
            "avg_quality_score": round(avg_score, 2),
            "results": results,
        }
    except Exception as e:
        logger.error(f"Daily quality check failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================
# Worker Initialization
# ============================================


class MarketDataWorker:
    """
    Market Data Worker class for direct invocation (non-Celery).
    """
    
    @staticmethod
    async def sync_symbol(symbol: str, **kwargs):
        """Sync a single symbol."""
        async with async_session_maker() as session:
            service = SymbolSyncService(session)
            result = await service.sync_symbol(symbol, **kwargs)
            await session.commit()
            return result
    
    @staticmethod
    async def import_ohlcv(symbol: str, timeframe: str, data: List[Dict]):
        """Import OHLCV data."""
        async with async_session_maker() as session:
            service = OhlcvImportService(session)
            result = await service.import_ohlcv(symbol, timeframe, data)
            await session.commit()
            return result
    
    @staticmethod
    async def check_quality(symbol: str, days_back: int = 30):
        """Run quality check."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        async with async_session_maker() as session:
            service = OhlcvQualityService(session)
            result = await service.check_symbol_quality(
                symbol, start_date, end_date
            )
            await session.commit()
            return result


# Need to import asyncio for Celery tasks
import asyncio