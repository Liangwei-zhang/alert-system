"""
Real-time service - WebSocket price streaming and signal triggering.

Handles:
1. Real-time price streaming via WebSocket
2. Signal generation triggers on price changes
3. Auto-notification when signals are detected
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Callable, Awaitable
from enum import Enum

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.config import settings
from domains.search.stock import Stock
from domains.search.stock_service import StockService
from domains.signals.signal_service import SignalService

logger = logging.getLogger(__name__)


class RealtimeChannel(str, Enum):
    """WebSocket channels for real-time updates."""
    PRICES = "prices"
    SIGNALS = "signals"
    SCANNER = "scanner"
    ALERTS = "alerts"


class PriceUpdate:
    """Represents a real-time price update."""
    
    def __init__(
        self,
        symbol: str,
        price: float,
        change: float,
        change_percent: float,
        volume: int,
        timestamp: datetime = None
    ):
        self.symbol = symbol
        self.price = price
        self.change = change
        self.change_percent = change_percent
        self.volume = volume
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> dict:
        return {
            "channel": RealtimeChannel.PRICES,
            "symbol": self.symbol,
            "price": self.price,
            "change": self.change,
            "change_percent": self.change_percent,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat()
        }


class SignalUpdate:
    """Represents a generated signal update."""
    
    def __init__(
        self,
        signal_id: int,
        symbol: str,
        signal_type: str,
        entry_price: float,
        confidence: float,
        probability: float,
        stop_loss: float,
        take_profit: float,
        direction: str,
        timestamp: datetime = None
    ):
        self.signal_id = signal_id
        self.symbol = symbol
        self.signal_type = signal_type
        self.entry_price = entry_price
        self.confidence = confidence
        self.probability = probability
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.direction = direction
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> dict:
        return {
            "channel": RealtimeChannel.SIGNALS,
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "signal_type": self.signal_type,
            "entry_price": self.entry_price,
            "confidence": self.confidence,
            "probability": self.probability,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "direction": self.direction,
            "timestamp": self.timestamp.isoformat()
        }


class RealtimeService:
    """
    Service for real-time price streaming and signal triggering.
    
    Features:
    - Redis pub/sub for price updates
    - Price change monitoring with configurable thresholds
    - Automatic signal generation when patterns detected
    - WebSocket broadcast for connected clients
    """
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._stock_service = StockService()
        self._price_callbacks: list[Callable[[PriceUpdate], Awaitable[None]]] = []
        self._signal_callbacks: list[Callable[[SignalUpdate], Awaitable[None]]] = []
        self._running = False
        self._monitored_symbols: set[str] = set()
    
    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
        return self._redis
    
    async def _get_pubsub(self) -> redis.client.PubSub:
        if self._pubsub is None:
            r = await self._get_redis()
            self._pubsub = r.pubsub()
        return self._pubsub
    
    async def start(self):
        """Start the real-time service."""
        if self._running:
            return
        
        self._running = True
        logger.info("Real-time service started")
        
        # Subscribe to price updates channel
        pubsub = await self._get_pubsub()
        await pubsub.subscribe("price_updates")
        
        # Start listening for messages
        asyncio.create_task(self._listen_to_redis())
    
    async def stop(self):
        """Stop the real-time service."""
        self._running = False
        if self._pubsub:
            await self._pubsub.unsubscribe("price_updates")
            await self._pubsub.close()
            self._pubsub = None
        logger.info("Real-time service stopped")
    
    async def _listen_to_redis(self):
        """Listen to Redis pub/sub messages."""
        pubsub = await self._get_pubsub()
        
        async for message in pubsub.listen():
            if not self._running:
                break
            
            if message["type"] != "message":
                continue
            
            try:
                data = json.loads(message["data"])
                channel = data.get("channel")
                
                if channel == RealtimeChannel.PRICES:
                    price_update = PriceUpdate(
                        symbol=data["symbol"],
                        price=data["price"],
                        change=data.get("change", 0),
                        change_percent=data.get("change_percent", 0),
                        volume=data.get("volume", 0)
                    )
                    await self._handle_price_update(price_update)
                    
                elif channel == RealtimeChannel.SIGNALS:
                    # Handle incoming signals from other sources
                    pass
                    
            except Exception as e:
                logger.error(f"Error processing Redis message: {e}")
    
    async def _handle_price_update(self, update: PriceUpdate):
        """Handle incoming price update."""
        # Call registered callbacks
        for callback in self._price_callbacks:
            try:
                await callback(update)
            except Exception as e:
                logger.error(f"Error in price callback: {e}")
        
        # Check signal triggering conditions
        await self._check_signal_trigger(update)
    
    async def _check_signal_trigger(self, update: PriceUpdate):
        """Check if price update triggers signal generation."""
        symbol = update.symbol
        
        # Get cached price history from Redis
        r = await self._get_redis()
        history_key = f"price_history:{symbol}"
        
        # Get last 20 price points
        history_data = await r.lrange(history_key, -20, -1)
        
        if history_data:
            prices = [float(p) for p in history_data]
            prices.append(update.price)
        else:
            prices = [update.price]
        
        # Need at least 20 data points for signal generation
        if len(prices) < 20:
            await r.rpush(history_key, str(update.price))
            await r.expire(history_key, 86400)  # 24h expiry
            return
        
        # Keep only last 50 prices
        if len(prices) > 50:
            await r.ltrim(history_key, -50, -1)
        
        await r.rpush(history_key, str(update.price))
        
        # Generate signal if we have enough data
        # This would integrate with the signal_service
        # For now, emit to scanner channel for downstream processing
        await r.publish("signal_check", json.dumps({
            "symbol": symbol,
            "prices": prices[-20:],
            "current_price": update.price
        }))
    
    async def subscribe_to_prices(
        self,
        callback: Callable[[PriceUpdate], Awaitable[None]]
    ):
        """Register a callback for price updates."""
        self._price_callbacks.append(callback)
    
    async def subscribe_to_signals(
        self,
        callback: Callable[[SignalUpdate], Awaitable[None]]
    ):
        """Register a callback for signal updates."""
        self._signal_callbacks.append(callback)
    
    async def broadcast_price(self, update: PriceUpdate):
        """Broadcast price update to WebSocket clients."""
        r = await self._get_redis()
        await r.publish("price_updates", json.dumps(update.to_dict()))
    
    async def broadcast_signal(self, update: SignalUpdate):
        """Broadcast signal update to WebSocket clients."""
        r = await self._get_redis()
        await r.publish("signal_updates", json.dumps(update.to_dict()))
    
    async def get_realtime_price(self, symbol: str) -> Optional[PriceUpdate]:
        """Get current price for a symbol."""
        quote = await self._stock_service.get_quote(symbol)
        if quote:
            return PriceUpdate(
                symbol=symbol,
                price=quote.price,
                change=quote.change,
                change_percent=quote.change_percent,
                volume=quote.volume
            )
        return None
    
    async def subscribe_symbol(self, symbol: str):
        """Add symbol to monitored symbols."""
        self._monitored_symbols.add(symbol.upper())
        logger.info(f"Subscribed to {symbol} for real-time updates")
    
    async def unsubscribe_symbol(self, symbol: str):
        """Remove symbol from monitored symbols."""
        self._monitored_symbols.discard(symbol.upper())
        logger.info(f"Unsubscribed from {symbol}")
    
    def get_monitored_symbols(self) -> set[str]:
        """Get all monitored symbols."""
        return self._monitored_symbols.copy()


# Singleton instance
realtime_service = RealtimeService()


class PriceStream:
    """
    Simple price streaming for terminal display.
    Outputs to console for terminal-based monitoring.
    """
    
    def __init__(self):
        self._streaming = False
        self._symbols: list[str] = []
    
    async def start(self, symbols: list[str], interval: int = 5):
        """Start streaming prices for symbols."""
        self._symbols = [s.upper() for s in symbols]
        self._streaming = True
        
        logger.info(f"Starting price stream for: {self._symbols}")
        
        while self._streaming:
            for symbol in self._symbols:
                try:
                    quote = await realtime_service.get_realtime_price(symbol)
                    if quote:
                        self._print_price(quote)
                except Exception as e:
                    logger.error(f"Error streaming {symbol}: {e}")
            
            await asyncio.sleep(interval)
    
    def stop(self):
        """Stop the price stream."""
        self._streaming = False
        logger.info("Price stream stopped")
    
    def _print_price(self, update: PriceUpdate):
        """Print price update in terminal-friendly format."""
        import sys
        
        emoji = "🟢" if update.change >= 0 else "🔴"
        direction = "+" if update.change >= 0 else ""
        
        line = (
            f"{emoji} {update.symbol:6} | "
            f"${update.price:8.2f} | "
            f"{direction}{update.change:7.2f} ({update.change_percent:+6.2f}%) | "
            f"Vol: {update.volume:,.0f}"
        )
        
        # Use carriage return to update in place
        sys.stdout.write(f"\r{line}")
        sys.stdout.flush()


# Convenience functions
async def start_price_stream(symbols: list[str], interval: int = 5):
    """Start streaming prices to terminal."""
    stream = PriceStream()
    await stream.start(symbols, interval)
    return stream


async def subscribe_to_realtime_prices(
    callback: Callable[[PriceUpdate], Awaitable[None]]
):
    """Subscribe to real-time price updates."""
    await realtime_service.subscribe_to_prices(callback)


async def subscribe_to_signals(
    callback: Callable[[SignalUpdate], Awaitable[None]]
):
    """Subscribe to signal updates."""
    await realtime_service.subscribe_to_signals(callback)