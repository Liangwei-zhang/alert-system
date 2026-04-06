"""Outbox pattern for reliable event publishing."""
from typing import Any, Callable, List, Dict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import asyncio


@dataclass
class OutboxEvent:
    """Event stored in the outbox."""
    
    id: str
    event_type: str
    payload: Dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: Optional[datetime] = None


class OutboxPublisher:
    """Publisher that stores events in an outbox for reliable delivery."""
    
    def __init__(self, session: Any, publish_fn: Callable):
        """Initialize the outbox publisher.
        
        Args:
            session: Database session for storing outbox events
            publish_fn: Function to actually publish events
        """
        self._session = session
        self._publish_fn = publish_fn
        self._pending_events: List[OutboxEvent] = []
    
    async def publish_after_commit(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Schedule an event to be published after transaction commits.
        
        Args:
            event_type: Type of the event
            payload: Event payload
        """
        event = OutboxEvent(
            id=self._generate_id(),
            event_type=event_type,
            payload=payload,
        )
        self._pending_events.append(event)
    
    async def publish_batch_after_commit(
        self,
        events: List[tuple[str, Dict[str, Any]]],
    ) -> None:
        """Schedule a batch of events to be published after transaction commits.
        
        Args:
            events: List of (event_type, payload) tuples
        """
        for event_type, payload in events:
            event = OutboxEvent(
                id=self._generate_id(),
                event_type=event_type,
                payload=payload,
            )
            self._pending_events.append(event)
    
    async def flush(self) -> None:
        """Flush pending events to the outbox table."""
        if self._pending_events:
            # In a real implementation, this would insert into an outbox table
            # For now, we just clear the pending list
            self._pending_events.clear()
    
    async def publish_pending(self) -> None:
        """Publish all pending events via the publish function."""
        if not self._pending_events:
            return
        
        events_to_publish = self._pending_events.copy()
        self._pending_events.clear()
        
        for event in events_to_publish:
            await self._publish_fn(event.event_type, event.payload)
            event.published_at = datetime.now(timezone.utc)
    
    def _generate_id(self) -> str:
        import uuid
        return str(uuid.uuid4())


# Type alias for Optional
from typing import Optional