"""
Symbol synchronization service - sync symbol metadata from external sources.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from domains.market_data.repository import SymbolRepository
from infra.db.models.market_data import AssetType, SymbolStatus

logger = logging.getLogger(__name__)


class SymbolSyncService:
    """Service for synchronizing symbol metadata from external sources."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = SymbolRepository(session)

    async def sync_symbol(
        self,
        symbol: str,
        name: str,
        exchange: Optional[str] = None,
        asset_type: AssetType = AssetType.STOCK,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        currency: str = "USD",
        data_source: str = "yahoo",
    ) -> Dict[str, Any]:
        """
        Sync a single symbol. Creates if not exists, updates if exists.
        
        Returns dict with 'symbol', 'is_new', 'is_updated' keys.
        """
        symbol_obj, is_new = await self.repository.upsert(
            symbol=symbol,
            data={
                "name": name,
                "exchange": exchange,
                "asset_type": asset_type,
                "sector": sector,
                "industry": industry,
                "currency": currency,
                "data_source": data_source,
                "last_sync_at": datetime.utcnow(),
                "status": SymbolStatus.ACTIVE,
            },
        )
        
        return {
            "symbol": symbol_obj,
            "is_new": is_new,
            "is_updated": not is_new,
        }

    async def sync_batch(
        self,
        symbols: List[Dict[str, Any]],
        data_source: str = "yahoo",
    ) -> Dict[str, Any]:
        """
        Batch sync multiple symbols.
        
        Expected input format:
        [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "exchange": "NASDAQ",
                "asset_type": "stock",
                ...
            },
            ...
        ]
        
        Returns dict with 'synced', 'created', 'updated', 'failed' counts.
        """
        results = {
            "synced": 0,
            "created": 0,
            "updated": 0,
            "failed": 0,
            "errors": [],
        }

        for sym_data in symbols:
            try:
                result = await self.sync_symbol(
                    symbol=sym_data.get("symbol"),
                    name=sym_data.get("name"),
                    exchange=sym_data.get("exchange"),
                    asset_type=AssetType(sym_data.get("asset_type", "stock")),
                    sector=sym_data.get("sector"),
                    industry=sym_data.get("industry"),
                    currency=sym_data.get("currency", "USD"),
                    data_source=data_source,
                )
                
                results["synced"] += 1
                if result["is_new"]:
                    results["created"] += 1
                else:
                    results["updated"] += 1
                    
            except Exception as e:
                logger.error(f"Failed to sync symbol {sym_data.get('symbol')}: {e}")
                results["failed"] += 1
                results["errors"].append({
                    "symbol": sym_data.get("symbol"),
                    "error": str(e),
                })

        return results

    async def sync_from_yahoo(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Sync symbols from Yahoo Finance.
        
        This would normally fetch data from Yahoo API. For now, we'll
        use a placeholder approach - in production this would call
        the Yahoo Finance API or a wrapper service.
        """
        # Placeholder: In production, use yahoo-finance or similar
        # For now, we'll just return a success with 0 synced
        logger.info(f"Yahoo sync requested for {len(symbols)} symbols")
        
        results = {
            "synced": 0,
            "created": 0,
            "updated": 0,
            "failed": 0,
            "errors": [],
            "message": "Yahoo sync not implemented - use external data source",
        }
        
        return results

    async def verify_symbol(self, symbol: str) -> bool:
        """
        Mark a symbol as verified (manually or via external validation).
        """
        symbol_obj = await self.repository.get_by_symbol(symbol)
        if not symbol_obj:
            return False
        
        await self.repository.update(
            symbol_obj.id,
            {"is_verified": True, "last_sync_at": datetime.utcnow()},
        )
        return True

    async def deactivate_symbol(self, symbol: str) -> bool:
        """Mark a symbol as inactive/delisted."""
        symbol_obj = await self.repository.get_by_symbol(symbol)
        if not symbol_obj:
            return False
        
        await self.repository.update(
            symbol_obj.id,
            {"status": SymbolStatus.INACTIVE, "last_sync_at": datetime.utcnow()},
        )
        return True

    async def get_sync_status(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get synchronization status for a symbol."""
        symbol_obj = await self.repository.get_by_symbol(symbol)
        if not symbol_obj:
            return None
        
        return {
            "symbol": symbol_obj.symbol,
            "name": symbol_obj.name,
            "status": symbol_obj.status.value,
            "is_verified": symbol_obj.is_verified,
            "last_sync_at": symbol_obj.last_sync_at,
            "data_source": symbol_obj.data_source,
        }