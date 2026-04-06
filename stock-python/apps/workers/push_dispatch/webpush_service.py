"""
WebPush notification service - VAPID key management and push notification delivery.
"""
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from domains.notifications.notification import Device
from infra.config import settings

logger = logging.getLogger(__name__)

# Try to import web-push, fallback to httpx for implementation
try:
    import webpush
    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    logger.warning("webpush package not available, using HTTP fallback")

# In-memory VAPID keys storage (in production, store in database or config)
_vapid_keys: Optional[dict] = None


class VapidKeys:
    """VAPID keys container."""
    def __init__(self, public_key: str, private_key: str):
        self.public_key = public_key
        self.private_key = private_key


def generate_vapid_keys() -> VapidKeys:
    """
    Generate new VAPID key pair for WebPush.
    
    Returns:
        VapidKeys object with public and private keys
    """
    # First check if keys are in config
    if settings.WEB_PUSH_PUBLIC_KEY and settings.WEB_PUSH_PRIVATE_KEY:
        return VapidKeys(
            public_key=settings.WEB_PUSH_PUBLIC_KEY,
            private_key=settings.WEB_PUSH_PRIVATE_KEY
        )
    
    if not WEBPUSH_AVAILABLE:
        # Generate basic keys for fallback mode using cryptography
        return _generate_vapid_keys_fallback()
    
    # Use py_vapid to generate proper VAPID keys
    try:
        import py_vapid
        vapid = py_vapid.Vapid()
        vapid.generate_keys()
        return VapidKeys(
            public_key=vapid.public_key_pem.decode() if hasattr(vapid.public_key_pem, 'decode') else str(vapid.public_key_pem),
            private_key=vapid.private_key_pem.decode() if hasattr(vapid.private_key_pem, 'decode') else str(vapid.private_key_pem)
        )
    except Exception as e:
        logger.error(f"Failed to generate VAPID keys with py_vapid: {e}")
        # Fallback: generate using cryptography library
        return _generate_vapid_keys_fallback()


def _generate_vapid_keys_fallback() -> VapidKeys:
    """Fallback VAPID key generation using cryptography library."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        import base64
        
        # Generate P-256 elliptic curve keys
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()
        
        # Serialize keys
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return VapidKeys(
            public_key=base64.urlsafe_b64encode(public_pem).decode('utf-8').rstrip('='),
            private_key=base64.urlsafe_b64encode(private_pem).decode('utf-8').rstrip('=')
        )
    except Exception as e:
        logger.error(f"Fallback VAPID key generation failed: {e}")
        raise


def get_vapid_keys() -> Optional[dict]:
    """
    Get stored VAPID keys or generate new ones.
    
    Returns:
        Dict with 'public_key' and 'private_key' or None if not configured
    """
    global _vapid_keys
    
    if _vapid_keys is None:
        # Generate new keys on first access
        keys = generate_vapid_keys()
        _vapid_keys = {
            "public_key": keys.public_key,
            "private_key": keys.private_key
        }
        logger.info("Generated new VAPID keys for WebPush")
    
    return _vapid_keys


def get_vapid_public_key() -> str:
    """Get VAPID public key for client subscription."""
    keys = get_vapid_keys()
    return keys["public_key"] if keys else ""


def set_vapid_keys(public_key: str, private_key: str) -> None:
    """Set existing VAPID keys (for loading from config)."""
    global _vapid_keys
    _vapid_keys = {
        "public_key": public_key,
        "private_key": private_key
    }


class WebPushPayload:
    """WebPush notification payload."""
    def __init__(
        self,
        title: str,
        body: str,
        url: str = "",
        tag: str = "",
        icon: str = "",
        badge: str = ""
    ):
        self.title = title
        self.body = body
        self.url = url
        self.tag = tag
        self.icon = icon
        self.badge = badge
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "body": self.body,
            "url": self.url,
            "tag": self.tag,
            "icon": self.icon,
            "badge": self.badge
        }


class WebPushService:
    """WebPush notification delivery service."""
    
    def __init__(self, db: Session):
        self.db = db
        self.vapid_keys = get_vapid_keys()
    
    def is_configured(self) -> bool:
        """Check if WebPush is configured."""
        return self.vapid_keys is not None
    
    def get_user_subscriptions(self, user_id: int) -> list[Device]:
        """Get all active WebPush subscriptions for a user."""
        return self.db.query(Device).filter(
            Device.user_id == user_id,
            Device.platform == "webpush",
            Device.is_active == True
        ).all()
    
    async def send_notification(
        self,
        user_id: int,
        payload: WebPushPayload
    ) -> dict:
        """
        Send WebPush notification to all user subscriptions.
        
        Args:
            user_id: Target user ID
            payload: Notification payload
            
        Returns:
            Dict with delivery results
        """
        subscriptions = self.get_user_subscriptions(user_id)
        
        if not subscriptions:
            return {
                "delivered": 0,
                "failed": 0,
                "errors": ["no_subscriptions"]
            }
        
        if not self.is_configured():
            return {
                "delivered": 0,
                "failed": len(subscriptions),
                "errors": ["webpush_not_configured"]
            }
        
        # Configure VAPID if webpush package available
        if WEBPUSH_AVAILABLE:
            webpush.configure_vapid(
                subject=settings.WEB_PUSH_SUBJECT or "mailto:admin@stockpy.com",
                public_key=self.vapid_keys["public_key"],
                private_key=self.vapid_keys["private_key"]
            )
        
        results = {
            "delivered": 0,
            "failed": 0,
            "errors": []
        }
        
        for sub in subscriptions:
            try:
                success = await self._send_to_subscription(sub, payload)
                if success:
                    results["delivered"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                logger.error(f"WebPush delivery failed for sub {sub.id}: {e}")
                results["failed"] += 1
                results["errors"].append(str(e))
        
        return results
    
    async def _send_to_subscription(
        self,
        device: Device,
        payload: WebPushPayload
    ) -> bool:
        """Send notification to a single subscription."""
        if not device.subscription_endpoint:
            return False
        
        if WEBPUSH_AVAILABLE:
            subscription_info = {
                "endpoint": device.subscription_endpoint,
                "keys": {
                    "p256dh": device.vapid_public_key or "",
                    "auth": device.vapid_auth_key or ""
                }
            }
            try:
                webpush.send_notification(
                    subscription_info,
                    data=json.dumps(payload.to_dict()),
                    ttl=86400  # 24 hours
                )
                return True
            except Exception as e:
                # Check if subscription is invalid (410 Gone or 404)
                error_str = str(e)
                if "410" in error_str or "404" in error_str:
                    # Mark subscription as inactive
                    device.is_active = False
                    self.db.commit()
                    logger.info(f"WebPush subscription {device.id} expired")
                return False
        
        # Fallback: use httpx to send request
        return await self._send_http_fallback(device, payload)
    
    async def _send_http_fallback(
        self,
        device: Device,
        payload: WebPushPayload
    ) -> bool:
        """Send notification using HTTP fallback."""
        if not device.subscription_endpoint:
            return False
        
        try:
            import httpx
            import time
            
            # Simplified VAPID auth (for demonstration)
            # In production, use proper JWT signing with py-vapid
            timestamp = str(int(time.time()))
            
            headers = {
                "Content-Type": "application/json",
                "TTL": "86400"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    device.subscription_endpoint,
                    json=payload.to_dict(),
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 410:
                    device.is_active = False
                    self.db.commit()
                    logger.info(f"WebPush subscription {device.id} expired (410)")
                    return False
                
                return response.status_code in (200, 201, 202)
        except Exception as e:
            logger.error(f"HTTP fallback WebPush failed: {e}")
            return False


async def send_signal_notification(
    db: Session,
    user_id: int,
    signal_data: dict
) -> dict:
    """
    Convenience function to send signal notification.
    
    Args:
        db: Database session
        user_id: Target user ID
        signal_data: Dict with signal info (symbol, type, price, confidence)
    
    Returns:
        Delivery results
    """
    signal_type = signal_data.get("signal_type", "buy")
    symbol = signal_data.get("symbol", "")
    price = signal_data.get("entry_price", 0)
    confidence = signal_data.get("confidence", 0)
    
    title = f"📈 {signal_type.upper()} Signal: {symbol}"
    body = f"Entry: ${price:.2f} | Confidence: {confidence:.0f}%"
    
    payload = WebPushPayload(
        title=title,
        body=body,
        url=f"/signals/{signal_data.get('signal_id', '')}",
        tag=f"signal-{symbol}"
    )
    
    service = WebPushService(db)
    return await service.send_notification(user_id, payload)