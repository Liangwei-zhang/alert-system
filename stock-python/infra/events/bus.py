"""Event bus for publishing and subscribing to domain events."""
from typing import Any, Callable, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
import asyncio


@dataclass
class DomainEvent:
    """Base domain event."""
    
    event_type: str
    payload: Dict[str, Any]
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class EventBus:
    """In-memory event bus for publishing domain events."""
    
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._event_history: List[DomainEvent] = []
    
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe a handler to an event type.
        
        Args:
            event_type: Type of event to listen for
            handler: Async function to handle the event
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe a handler from an event type.
        
        Args:
            event_type: Type of event
            handler: Handler to remove
        """
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]
    
    async def publish(self, event: DomainEvent) -> None:
        """Publish a single event to all subscribers.
        
        Args:
            event: The domain event to publish
        """
        self._event_history.append(event)
        
        if event.event_type in self._handlers:
            tasks = []
            for handler in self._handlers[event.event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        tasks.append(handler(event))
                    else:
                        handler(event)
                except Exception as e:
                    # Log but don't fail the publish
                    print(f"Error in event handler: {e}")
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    
    async def publish_batch(self, events: List[DomainEvent]) -> None:
        """Publish multiple events.
        
        Args:
            events: List of domain events to publish
        """
        for event in events:
            await self.publish(event)
    
    def get_history(self, event_type: Optional[str] = None) -> List[DomainEvent]:
        """Get event history, optionally filtered by type.
        
        Args:
            event_type: Optional filter by event type
            
        Returns:
            List of published events
        """
        if event_type is None:
            return self._event_history.copy()
        return [e for e in self._event_history if e.event_type == event_type]
    
    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()


# Type alias for Optional
from typing import Optional