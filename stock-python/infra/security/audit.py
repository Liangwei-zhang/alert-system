"""
Operation logging middleware for tracking API requests.
"""
import time
import json
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from domains.admin.audit import AuditLog, AuditAction


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically log admin API operations.
    """

    # Paths to exclude from auditing
    EXCLUDED_PATHS = {
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api/v1/health",
        "/ws",
        "/api/v1/ws",
    }

    # Paths that are considered "admin" operations
    ADMIN_PATHS = {
        "/api/v1/admin",
    }

    def __init__(
        self,
        app: ASGIApp,
        get_current_admin_user: Optional[Callable] = None,
    ):
        super().__init__(app)
        self.get_current_admin_user = get_current_admin_user

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and log audit events."""
        # Skip excluded paths
        if any(request.url.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return await call_next(request)

        # Only audit admin paths
        is_admin_path = any(
            request.url.path.startswith(path) for path in self.ADMIN_PATHS
        )

        # Extract request info
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")[:255]

        # Try to get admin user info if available
        admin_user_id = None
        username = None
        if self.get_current_admin_user:
            try:
                admin_user = await self.get_current_admin_user(request)
                if admin_user:
                    admin_user_id = admin_user.id
                    username = admin_user.username
            except Exception:
                pass

        # Process request
        response = None
        error_message = None
        status = "success"

        try:
            response = await call_next(request)
            status_code = response.status_code
            if status_code >= 400:
                status = "failure"
        except Exception as e:
            status = "failure"
            error_message = str(e)[:500]
            raise
        finally:
            duration = time.time() - start_time

            # Only log if it's an admin path
            if is_admin_path and admin_user_id:
                action = self._determine_action(request)
                if action:
                    await self._log_audit(
                        admin_user_id=admin_user_id,
                        username=username,
                        action=action,
                        request=request,
                        status=status,
                        error_message=error_message,
                        duration=duration,
                        client_ip=client_ip,
                        user_agent=user_agent,
                    )

        return response

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Extract client IP from request headers."""
        # Check for forwarded headers
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        if request.client:
            return request.client.host
        return None

    def _determine_action(self, request: Request) -> Optional[str]:
        """Determine the audit action based on HTTP method and path."""
        path = request.url.path
        method = request.method.upper()

        # Map paths to audit actions
        if "/admin/users" in path:
            if method == "POST":
                return AuditAction.USER_CREATE
            elif method in ("PATCH", "PUT"):
                return AuditAction.USER_UPDATE
            elif method == "DELETE":
                return AuditAction.USER_DELETE
        elif "/admin/subscriptions" in path:
            if method == "POST":
                return AuditAction.DISTRIBUTION_CREATE
            elif method in ("PATCH", "PUT"):
                return AuditAction.DISTRIBUTION_UPDATE
            elif method == "DELETE":
                return AuditAction.DISTRIBUTION_DELETE
        elif "/admin/strategies" in path:
            if method == "POST":
                return AuditAction.STRATEGY_CREATE
            elif method in ("PATCH", "PUT"):
                return AuditAction.STRATEGY_UPDATE
            elif method == "DELETE":
                return AuditAction.STRATEGY_DELETE

        return None

    async def _log_audit(
        self,
        admin_user_id: int,
        username: Optional[str],
        action: str,
        request: Request,
        status: str,
        error_message: Optional[str],
        duration: float,
        client_ip: Optional[str],
        user_agent: str,
    ):
        """Create an audit log entry."""
        try:
            from infra.database import async_session_maker

            async with async_session_maker() as session:
                # Extract resource info from path
                path_parts = request.url.path.split("/")
                resource_type = None
                resource_id = None

                # Try to extract resource type and ID from path
                if "users" in path_parts:
                    resource_type = "user"
                    resource_id = path_parts[-1] if path_parts[-1].isdigit() else None
                elif "subscriptions" in path_parts:
                    resource_type = "subscription"
                    resource_id = path_parts[-1] if path_parts[-1].isdigit() else None

                # Get request body for details (limited)
                details = None
                if request.method in ("POST", "PATCH", "PUT"):
                    # Store request method and path as details
                    details = f"{request.method} {request.url.path}"

                log_entry = AuditLog(
                    admin_user_id=admin_user_id,
                    username=username,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details=details,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    status=status,
                    error_message=error_message,
                )
                session.add(log_entry)
                await session.commit()
        except Exception as e:
            # Don't let audit logging failures break the request
            import logging
            logging.error(f"Failed to write audit log: {e}")


async def get_current_admin_user(request: Request) -> Optional[object]:
    """
    Dependency to get current admin user from request.
    Implement based on your authentication system.
    """
    # This is a placeholder - integrate with your actual auth
    # For now, returns None (unauthenticated)
    return None