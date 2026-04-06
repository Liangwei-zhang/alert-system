# Notification Team Execution Guide

## Overview

The Notification Team handles all notification-related functionality including push notifications, email dispatch, and real-time WebSocket notifications.

## Responsibilities

- Push notification dispatch (WebPush)
- Email notification service
- In-app notification management
- Real-time notification via WebSocket
- Notification preferences and settings

## Current Status

### Completed Components

1. **Notification Service (domains/notifications/)**
   - In-app notification CRUD
   - Notification preferences
   - Unread count tracking
   - Mark as read functionality

2. **Push Notifications (apps/workers/push_dispatch/)**
   - WebPush service
   - Push message tasks
   - Device registration

3. **Email Dispatch (apps/workers/email_dispatch/)**
   - Email service
   - Email templates
   - Async email sending

4. **Notification Orchestrator (apps/workers/notification_orchestrator/)**
   - Distribution tasks
   - Notification scheduling

5. **Real-time (apps/public_api/routers/websocket.py)**
   - WebSocket connection management
   - Channel subscriptions (prices, signals, notifications)
   - Real-time broadcasting

## Migration Tasks

### Phase 1: In-App Notifications

- [x] Notification service implementation
- [x] CRUD operations for notifications
- [x] Unread count tracking
- [x] Mark as read functionality

### Phase 2: Push Notifications

- [x] WebPush service setup
- [x] Device registration
- [x] Push message dispatch
- [x] Push task queue

### Phase 3: Email Notifications

- [x] Email service implementation
- [x] Email template system
- [x] Async email sending via Celery

### Phase 4: Real-time Notifications

- [x] WebSocket endpoint implementation
- [x] Channel-based subscriptions
- [x] Notification broadcasting
- [x] Price and signal streaming

### Phase 5: Orchestration

- [x] Notification distribution service
- [x] Scheduling and batching
- [x] Priority handling

## API Endpoints

### Notification Endpoints (Public API)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/notifications` | Get user notifications |
| GET | `/api/v1/notifications/unread-count` | Get unread count |
| POST | `/api/v1/notifications/mark-read` | Mark as read |
| POST | `/api/v1/notifications/mark-all-read` | Mark all as read |
| DELETE | `/api/v1/notifications/{id}` | Delete notification |

### Device Endpoints (Public API)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/devices` | Get user devices |
| POST | `/api/v1/devices` | Register device |
| DELETE | `/api/v1/devices/{id}` | Unregister device |

### WebSocket Endpoints (Public API)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/ws/notifications` | WebSocket for notifications |
| GET | `/api/v1/ws` | General WebSocket endpoint |

## Notification Channels

1. **In-App** - Stored in database, delivered via API
2. **Push** - WebPush to registered devices
3. **Email** - SMTP-based email delivery
4. **WebSocket** - Real-time streaming

## Dependencies

- `domains/notifications/notification.py` - Notification models
- `apps/workers/push_dispatch/` - Push notification worker
- `apps/workers/email_dispatch/` - Email dispatch worker
- `apps/workers/notification_orchestrator/` - Orchestration worker
- `domains/notifications/webpush_service.py` - WebPush service

## Testing Strategy

1. Unit tests for notification service
2. Push notification delivery tests
3. Email template rendering tests
4. WebSocket connection tests

## Device Registration

```python
{
    "platform": "ios" | "android" | "web",
    "push_token": str,
    "name": str,
    "push_token_expires_at": datetime | None
}
```

## Notification Preferences

- Enable/disable by channel
- Quiet hours settings
- Signal-specific preferences

## Next Steps

1. Add notification templates with dynamic content
2. Implement notification batching for efficiency
3. Add delivery status tracking
4. Implement retry logic for failed deliveries