"""Request context for tracking request metadata."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


@dataclass
class RequestContext:
    """Context information for incoming requests."""
    
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: Optional[str] = None
    user_id: Optional[str] = None
    operator_id: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    locale: str = "en"
    timezone: str = "UTC"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def with_trace_id(self, trace_id: str) -> "RequestContext":
        """Create a copy with a new trace_id."""
        return RequestContext(
            request_id=self.request_id,
            trace_id=trace_id,
            user_id=self.user_id,
            operator_id=self.operator_id,
            ip=self.ip,
            user_agent=self.user_agent,
            locale=self.locale,
            timezone=self.timezone,
            timestamp=self.timestamp,
        )
    
    def with_user(self, user_id: str, operator_id: Optional[str] = None) -> "RequestContext":
        """Create a copy with user information."""
        return RequestContext(
            request_id=self.request_id,
            trace_id=self.trace_id,
            user_id=user_id,
            operator_id=operator_id,
            ip=self.ip,
            user_agent=self.user_agent,
            locale=self.locale,
            timezone=self.timezone,
            timestamp=self.timestamp,
        )