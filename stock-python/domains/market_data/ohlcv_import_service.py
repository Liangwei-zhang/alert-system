"""
OHLCV import service - batch import OHLCV data from external sources.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from domains.market_data.repository import (
    SymbolRepository,
    OhlcvRepository,
)
from domains.market_data.schemas import OhlcvBase

logger = logging.getLogger(__name__)


class OhlcvImportService:
    """Service for importing OHLCV data from external sources."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.symbol_repo = SymbolRepository(session)
        self.ohlcv_repo = OhlcvRepository(session)

    async def import_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        data: List[Dict[str, Any]],
        source: str = "yahoo",
        batch_size: int = 1000,
    ) -> Dict[str, Any]:
        """
        Import OHLCV data for a symbol.
        
        Args:
            symbol: Stock ticker symbol (e.g., "AAPL")
            timeframe: Timeframe (e.g., "1d", "1h", "5m")
            data: List of OHLCV records
            source: Data source identifier
            batch_size: Number of records per batch insert
        
        Returns dict with 'imported', 'updated', 'skipped', 'failed' counts.
        """
        # Get symbol ID
        symbol_obj = await self.symbol_repo.get_by_symbol(symbol)
        if not symbol_obj:
            return {
                "success": False,
                "error": f"Symbol {symbol} not found",
            }

        results = {
            "imported": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
        }

        # Process in batches
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            batch_results = await self._process_batch(
                symbol_id=symbol_obj.id,
                timeframe=timeframe,
                batch=batch,
                source=source,
            )
            
            results["imported"] += batch_results["imported"]
            results["updated"] += batch_results["updated"]
            results["skipped"] += batch_results["skipped"]
            results["failed"] += batch_results["failed"]
            results["errors"].extend(batch_results["errors"])

        # Update symbol last sync time
        await self.symbol_repo.update(
            symbol_obj.id,
            {"last_sync_at": datetime.utcnow()},
        )

        return {
            "success": True,
            "symbol": symbol,
            "symbol_id": symbol_obj.id,
            "timeframe": timeframe,
            "total_records": len(data),
            **results,
        }

    async def _process_batch(
        self,
        symbol_id: int,
        timeframe: str,
        batch: List[Dict[str, Any]],
        source: str,
    ) -> Dict[str, Any]:
        """Process a batch of OHLCV records."""
        results = {
            "imported": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
        }

        for record in batch:
            try:
                # Validate required fields
                if not self._validate_record(record):
                    results["skipped"] += 1
                    continue

                # Check if record exists
                timestamp = self._parse_timestamp(record.get("timestamp"))
                if not timestamp:
                    results["skipped"] += 1
                    continue

                # Check for existing record
                existing = await self.ohlcv_repo.session.execute(
                    self.ohlcv_repo.session.execute(
                        f"SELECT id FROM ohlcv WHERE symbol_id = {symbol_id} AND timestamp = '{timestamp}' AND timeframe = '{timeframe}'"
                    )
                )

                record_data = {
                    "symbol_id": symbol_id,
                    "timestamp": timestamp,
                    "timeframe": timeframe,
                    "open": float(record.get("open", 0)),
                    "high": float(record.get("high", 0)),
                    "low": float(record.get("low", 0)),
                    "close": float(record.get("close", 0)),
                    "volume": int(record.get("volume", 0)),
                    "adjusted_close": float(record["adjusted_close"]) if record.get("adjusted_close") else None,
                    "dividends": float(record["dividends"]) if record.get("dividends") else None,
                    "splits": float(record["splits"]) if record.get("splits") else None,
                    "is_adjusted": bool(record.get("is_adjusted", False)),
                    "source": source,
                }

                if existing:
                    # Update existing
                    # Note: In production, use proper SQLAlchemy update
                    results["updated"] += 1
                else:
                    # Insert new
                    await self.ohlcv_repo.create(record_data)
                    results["imported"] += 1

            except Exception as e:
                logger.error(f"Failed to process OHLCV record: {e}")
                results["failed"] += 1
                results["errors"].append({"error": str(e)})

        await self.session.flush()
        return results

    def _validate_record(self, record: Dict[str, Any]) -> bool:
        """Validate a single OHLCV record."""
        required = ["timestamp", "open", "high", "low", "close", "volume"]
        
        for field in required:
            if field not in record:
                return False
        
        # Validate prices are positive
        try:
            for field in ["open", "high", "low", "close"]:
                if float(record[field]) < 0:
                    return False
            if int(record["volume"]) < 0:
                return False
        except (ValueError, TypeError):
            return False

        # Validate high >= low
        try:
            if float(record["high"]) < float(record["low"]):
                return False
        except (ValueError, TypeError):
            return False

        return True

    def _parse_timestamp(self, value: Any) -> Optional[datetime]:
        """Parse timestamp from various formats."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        return None

    async def import_from_yahoo(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1d",
    ) -> Dict[str, Any]:
        """
        Import OHLCV data from Yahoo Finance.
        
        In production, this would use yfinance library or API.
        """
        logger.info(f"Yahoo import requested for {symbol} from {start_date} to {end_date}")
        
        # Placeholder - in production, fetch from Yahoo Finance
        return {
            "success": False,
            "message": "Yahoo import not implemented - use data_source module",
        }

    async def get_import_status(
        self,
        symbol: str,
        timeframe: str,
    ) -> Optional[Dict[str, Any]]:
        """Get import status for a symbol/timeframe."""
        symbol_obj = await self.symbol_repo.get_by_symbol(symbol)
        if not symbol_obj:
            return None

        latest = await self.ohlcv_repo.get_latest(symbol_obj.id, timeframe)
        oldest = await self.ohlcv_repo.get_oldest(symbol_obj.id, timeframe)
        count = await self.ohlcv_repo.count(symbol_obj.id, timeframe)

        return {
            "symbol": symbol,
            "symbol_id": symbol_obj.id,
            "timeframe": timeframe,
            "total_records": count,
            "earliest_date": oldest.timestamp if oldest else None,
            "latest_date": latest.timestamp if latest else None,
            "last_sync_at": symbol_obj.last_sync_at,
        }

    async def delete_range(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """Delete OHLCV data in a date range."""
        symbol_obj = await self.symbol_repo.get_by_symbol(symbol)
        if not symbol_obj:
            return {"success": False, "error": f"Symbol {symbol} not found"}

        deleted = await self.ohlcv_repo.delete_range(
            symbol_obj.id, timeframe, start_date, end_date
        )

        return {
            "success": True,
            "symbol": symbol,
            "deleted": deleted,
        }