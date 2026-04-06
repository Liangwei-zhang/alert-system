from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from fastapi import Request


@dataclass(slots=True)
class RequestContext:
    request_id: str
    trace_id: str
    user_id: Optional[str]
    operator_id: Optional[str]
    ip: Optional[str]
    user_agent: Optional[str]


_request_context_var: ContextVar[RequestContext | None] = ContextVar(
    "request_context",
    default=None,
)


def _extract_trace_id(request: Request, request_id: str) -> str:
    traceparent = request.headers.get("traceparent")
    if traceparent:
        parts = traceparent.split("-")
        if len(parts) >= 2 and parts[1]:
            return parts[1]

    return request.headers.get("X-Trace-ID", request_id)


def _extract_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def build_request_context(request: Request) -> RequestContext:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    trace_id = _extract_trace_id(request, request_id)

    user_id = request.headers.get("X-User-ID")
    operator_id = request.headers.get("X-Operator-ID")
    state_user_id = getattr(request.state, "user_id", None)
    state_operator_id = getattr(request.state, "operator_id", None)

    return RequestContext(
        request_id=request_id,
        trace_id=trace_id,
        user_id=str(state_user_id or user_id) if state_user_id or user_id else None,
        operator_id=(
            str(state_operator_id or operator_id) if state_operator_id or operator_id else None
        ),
        ip=_extract_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )


def set_request_context(context: RequestContext) -> Token[RequestContext | None]:
    return _request_context_var.set(context)


def reset_request_context(token: Token[RequestContext | None]) -> None:
    _request_context_var.reset(token)


def get_request_context() -> RequestContext | None:
    return _request_context_var.get()
