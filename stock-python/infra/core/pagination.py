"""Cursor-based pagination utilities."""
from dataclasses import dataclass, field
from typing import Generic, TypeVar, Optional, List, Any
import base64
import json


T = TypeVar("T")


@dataclass(generic=True)
class CursorPage(Generic[T]):
    """Cursor-based paginated result."""
    
    items: List[T] = field(default_factory=list)
    next_cursor: Optional[str] = None
    has_more: bool = False
    total: Optional[int] = None
    
    @classmethod
    def create(
        cls,
        items: List[T],
        next_after: Optional[Any] = None,
        limit: int = 20,
        total: Optional[int] = None,
    ) -> "CursorPage[T]":
        """Create a paginated result.
        
        Args:
            items: List of items for this page
            next_after: Cursor value for next page (usually last item's ID/timestamp)
            limit: Requested limit
            total: Total count (optional)
        """
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]
        
        next_cursor = None
        if has_more and next_after is not None:
            next_cursor = encode_cursor(next_after)
        
        return CursorPage(
            items=items,
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
        )


def encode_cursor(value: Any) -> str:
    """Encode a value into a cursor string.
    
    Args:
        value: The cursor value (typically last item's ID or timestamp)
        
    Returns:
        Base64 encoded JSON string
    """
    encoded = json.dumps(value, default=str)
    return base64.urlsafe_b64encode(encoded.encode()).decode()


def decode_cursor(cursor: str) -> Any:
    """Decode a cursor string into its value.
    
    Args:
        cursor: Base64 encoded cursor string
        
    Returns:
        The decoded cursor value
        
    Raises:
        ValueError: If cursor is invalid
    """
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
        return json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"Invalid cursor: {e}")