"""Application error classes."""
from typing import Any, Optional


class AppError(Exception):
    """Base application error."""
    
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(AppError):
    """Validation error for invalid input."""
    
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class UnauthorizedError(AppError):
    """Error for unauthenticated requests."""
    
    def __init__(self, message: str = "Authentication required", details: Optional[dict[str, Any]] = None):
        super().__init__(message, code="UNAUTHORIZED", details=details)


class ForbiddenError(AppError):
    """Error for unauthorized access."""
    
    def __init__(self, message: str = "Access denied", details: Optional[dict[str, Any]] = None):
        super().__init__(message, code="FORBIDDEN", details=details)


class NotFoundError(AppError):
    """Error for missing resources."""
    
    def __init__(self, message: str = "Resource not found", details: Optional[dict[str, Any]] = None):
        super().__init__(message, code="NOT_FOUND", details=details)


class ConflictError(AppError):
    """Error for conflicting operations."""
    
    def __init__(self, message: str = "Conflict", details: Optional[dict[str, Any]] = None):
        super().__init__(message, code="CONFLICT", details=details)


class RateLimitError(AppError):
    """Error for rate limit exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[dict[str, Any]] = None):
        super().__init__(message, code="RATE_LIMIT_EXCEEDED", details=details)


class ExternalServiceError(AppError):
    """Error for external service failures."""
    
    def __init__(
        self,
        message: str = "External service error",
        service: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        details = details or {}
        if service:
            details["service"] = service
        super().__init__(message, code="EXTERNAL_SERVICE_ERROR", details=details)


class DomainRuleError(AppError):
    """Error for domain business rule violations."""
    
    def __init__(self, message: str, rule: Optional[str] = None, details: Optional[dict[str, Any]] = None):
        details = details or {}
        if rule:
            details["rule"] = rule
        super().__init__(message, code="DOMAIN_RULE_VIOLATION", details=details)