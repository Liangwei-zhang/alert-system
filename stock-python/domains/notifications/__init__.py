"""
Notification domain - models and services.
"""
from domains.notifications.notification import (
    Notification,
    NotificationType,
    NotificationPriority,
    Device,
    # Schemas
    NotificationBase,
    NotificationCreate,
    NotificationResponse,
    NotificationListResponse,
    DeviceBase,
    DeviceCreate,
    DeviceResponse,
    WebPushSubscriptionCreate,
    WebPushSubscriptionResponse,
    MarkReadRequest,
)

from domains.notifications.template_service import (
    TemplateEngine,
    TemplateService,
    template_service,
)

from domains.notifications.batch_service import (
    BatchConfig,
    BatchService,
    batch_service,
)

from domains.notifications.delivery_tracker import (
    DeliveryStatus,
    DeliveryChannel,
    DeliveryTracker,
    DeliveryTrackerService,
)

from domains.notifications.retry_service import (
    RetryStrategy,
    RetryConfig,
    RetryService,
    retry_service,
)

__all__ = [
    # Core models
    "Notification",
    "NotificationType", 
    "NotificationPriority",
    "Device",
    # Schemas
    "NotificationBase",
    "NotificationCreate",
    "NotificationResponse",
    "NotificationListResponse",
    "DeviceBase",
    "DeviceCreate",
    "DeviceResponse",
    "WebPushSubscriptionCreate",
    "WebPushSubscriptionResponse",
    "MarkReadRequest",
    # Template service
    "TemplateEngine",
    "TemplateService",
    "template_service",
    # Batch service
    "BatchConfig",
    "BatchService",
    "batch_service",
    # Delivery tracker
    "DeliveryStatus",
    "DeliveryChannel",
    "DeliveryTracker",
    "DeliveryTrackerService",
    # Retry service
    "RetryStrategy",
    "RetryConfig",
    "RetryService",
    "retry_service",
]