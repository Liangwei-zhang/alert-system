"""
WebSocket endpoints for real-time updates and notifications.
"""
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from fastapi.security import HTTPBearer

from apps.public_api.routers.notifications import router as notification_router
from apps.workers.notification_orchestrator.notification_service import NotificationService, notification_broadcaster
from domains.market_data.realtime_service import RealtimeChannel, PriceUpdate, SignalUpdate, realtime_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Security scheme for WebSocket
security = HTTPBearer(auto_error=False)


class WebSocketManager:
    """Manages WebSocket connections with channel subscriptions."""
    
    def __init__(self):
        self.active_connections: dict[int, WebSocket] = {}
        self.subscriptions: dict[int, set[str]] = {}  # user_id -> channels
    
    async def connect(self, user_id: int, websocket: WebSocket, channels: list[str] = None):
        """Connect a WebSocket for a user with channel subscriptions."""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.subscriptions[user_id] = set(channels) if channels else {"notifications"}
        notification_broadcaster.add_connection(user_id, websocket)
        
        # Subscribe to real-time channels
        if channels:
            for ch in channels:
                if ch == RealtimeChannel.PRICES:
                    asyncio.create_task(self._stream_prices(user_id, websocket))
                elif ch == RealtimeChannel.SIGNALS:
                    asyncio.create_task(self._stream_signals(user_id, websocket))
        
        logger.info(f"WebSocket connected for user {user_id}, channels: {channels}")
    
    def disconnect(self, user_id: int):
        """Disconnect a WebSocket for a user."""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if user_id in self.subscriptions:
            del self.subscriptions[user_id]
        notification_broadcaster.remove_connection(user_id, self.active_connections.get(user_id))
        logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_message(self, user_id: int, message: dict):
        """Send a message to a user."""
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)
    
    async def broadcast_to_user(self, user_id: int, notification: dict):
        """Broadcast notification to user."""
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json({
                "type": "notification",
                "data": notification,
            })
    
    async def broadcast_to_channel(self, channel: str, message: dict):
        """Broadcast message to all users subscribed to channel."""
        for user_id, channels in self.subscriptions.items():
            if channel in channels and user_id in self.active_connections:
                ws = self.active_connections[user_id]
                await ws.send_json(message)
    
    async def _stream_prices(self, user_id: int, websocket: WebSocket):
        """Stream real-time prices to user."""
        async def price_callback(update: PriceUpdate):
            if user_id in self.active_connections:
                try:
                    await websocket.send_json(update.to_dict())
                except Exception as e:
                    logger.error(f"Error streaming price: {e}")
        
        await realtime_service.subscribe_to_prices(price_callback)
    
    async def _stream_signals(self, user_id: int, websocket: WebSocket):
        """Stream signals to user."""
        async def signal_callback(update: SignalUpdate):
            if user_id in self.active_connections:
                try:
                    await websocket.send_json(update.to_dict())
                except Exception as e:
                    logger.error(f"Error streaming signal: {e}")
        
        await realtime_service.subscribe_to_signals(signal_callback)


ws_manager = WebSocketManager()


@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    """WebSocket endpoint for real-time notifications."""
    user_id: Optional[int] = None
    
    try:
        # Receive auth token first
        data = await websocket.receive_text()
        try:
            message = json.loads(data)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "message": "Invalid JSON"})
            await websocket.close()
            return
        
        token = message.get("token")
        if not token:
            await websocket.send_json({"type": "error", "message": "Token required"})
            await websocket.close()
            return
        
        # Verify token and get user
        try:
            from infra.security import decode_token
            payload = decode_token(token)
            user_id = payload.get("sub")
            if not user_id:
                await websocket.send_json({"type": "error", "message": "Invalid token"})
                await websocket.close()
                return
            user_id = int(user_id)
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            await websocket.send_json({"type": "error", "message": "Token verification failed"})
            await websocket.close()
            return
        
        # Get requested channels
        channels = message.get("channels", ["notifications"])
        
        # Accept connection
        await ws_manager.connect(user_id, websocket, channels)
        
        # Send confirmation
        await websocket.send_json({
            "type": "connected",
            "channels": channels,
            "message": f"Connected to {', '.join(channels)} stream",
        })
        
        # Keep connection alive and handle messages
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                msg_type = message.get("type")
                
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        if user_id:
            ws_manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if user_id:
            ws_manager.disconnect(user_id)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for general real-time updates."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                msg_type = message.get("type")
                
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
    except WebSocketDisconnect:
        pass