"""
Authentication API endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, EmailStr

from infra.database import get_db
from domains.auth.auth_service import AuthService
from domains.auth.password_reset_service import PasswordResetService
from domains.auth.two_factor_service import TwoFactorService
from infra.security.rate_limiter import rate_limiter
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/auth", tags=["auth"])


# Pydantic schemas
class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VerificationLoginRequest(BaseModel):
    email: EmailStr
    code: str


class SendCodeRequest(BaseModel):
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    user: dict
    access_token: str
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str


class MessageResponse(BaseModel):
    message: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetVerify(BaseModel):
    email: EmailStr
    code: str


class PasswordResetComplete(BaseModel):
    email: EmailStr
    code: str
    new_password: str


class TwoFactorSetupResponse(BaseModel):
    secret: str
    qr_url: str
    backup_codes: Optional[list] = None


class TwoFactorVerifyRequest(BaseModel):
    code: str


class TwoFactorDisableRequest(BaseModel):
    password: str
    code: Optional[str] = None


# Dependency
async def get_auth_service(
    db: AsyncSession = Depends(get_db),
) -> AuthService:
    return AuthService(db)


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


# Endpoints
@router.post("/register", response_model=AuthResponse)
async def register(
    data: RegisterRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    """Register a new user."""
    try:
        ip = get_client_ip(request)
        user = await auth.register(
            username=data.username,
            email=data.email,
            password=data.password,
            full_name=data.full_name,
            ip=ip,
        )
        # Auto login after register
        result = await auth.login(data.email, data.password, ip)
        return AuthResponse(
            user={"id": user.id, "username": user.username, "email": user.email},
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=AuthResponse)
async def login(
    data: LoginRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    """Login with email and password."""
    try:
        ip = get_client_ip(request)
        result = await auth.login(data.email, data.password, ip)
        return AuthResponse(
            user={
                "id": result["user"].id,
                "username": result["user"].username,
                "email": result["user"].email,
            },
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/login/code", response_model=AuthResponse)
async def login_with_code(
    data: VerificationLoginRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    """Login with email verification code."""
    try:
        ip = get_client_ip(request)
        result = await auth.login_with_verification_code(data.email, data.code, ip)
        return AuthResponse(
            user={
                "id": result["user"].id,
                "username": result["user"].username,
                "email": result["user"].email,
            },
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/code/send", response_model=MessageResponse)
async def send_verification_code(
    data: SendCodeRequest,
    auth: AuthService = Depends(get_auth_service),
):
    """Send verification code to email."""
    try:
        code = await auth.send_verification_code(data.email)
        # TODO: In production, send code via email
        # For dev, return code in response
        return MessageResponse(message=f"Verification code sent: {code}")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/verify", response_model=MessageResponse)
async def verify_email(
    data: VerifyEmailRequest,
    auth: AuthService = Depends(get_auth_service),
):
    """Verify email with code."""
    success = await auth.verify_email(data.email, data.code)
    if success:
        return MessageResponse(message="Email verified successfully")
    raise HTTPException(status_code=400, detail="Invalid or expired code")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    data: RefreshRequest,
    auth: AuthService = Depends(get_auth_service),
):
    """Refresh access token."""
    try:
        result = await auth.refresh_tokens(data.refresh_token)
        return TokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    """Logout current session."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        await auth.logout(token)
    return MessageResponse(message="Logged out successfully")


# ============== Password Reset Endpoints ==============


@router.post("/password-reset/request", response_model=MessageResponse)
async def request_password_reset(
    data: PasswordResetRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    """Request password reset code."""
    try:
        # Check rate limit
        await rate_limiter.check_rate_limit(
            "auth:password_reset_request", request, email=data.email
        )
        
        reset_service = PasswordResetService(auth.db)
        code = await reset_service.request_password_reset(data.email)
        # TODO: Send code via email
        return MessageResponse(
            message=f"Password reset code sent: {code}" if code == "reset_sent" 
                    else "Password reset code sent"
        )
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))


@router.post("/password-reset/verify", response_model=MessageResponse)
async def verify_password_reset_code(
    data: PasswordResetVerify,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    """Verify password reset code."""
    try:
        await rate_limiter.check_rate_limit(
            "auth:password_reset_verify", request, email=data.email
        )
        
        reset_service = PasswordResetService(auth.db)
        valid = await reset_service.verify_reset_code(data.email, data.code)
        if valid:
            return MessageResponse(message="Code verified successfully")
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))


@router.post("/password-reset/complete", response_model=MessageResponse)
async def complete_password_reset(
    data: PasswordResetComplete,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    """Complete password reset with new password."""
    try:
        reset_service = PasswordResetService(auth.db)
        await reset_service.reset_password(data.email, data.code, data.new_password)
        return MessageResponse(message="Password reset successfully")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== 2FA Endpoints ==============


@router.get("/2fa/status", response_model=dict)
async def get_2fa_status(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    """Get 2FA status for current user."""
    # Would need auth middleware to get user_id
    return {"enabled": False, "message": "Auth middleware required"}


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    """Start 2FA setup (generate secret and QR code)."""
    # Placeholder - requires auth middleware
    raise HTTPException(status_code=501, detail="Requires authentication")


@router.post("/2fa/enable", response_model=MessageResponse)
async def enable_2fa(
    data: TwoFactorVerifyRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    """Enable 2FA with verification code."""
    raise HTTPException(status_code=501, detail="Requires authentication")


@router.post("/2fa/disable", response_model=MessageResponse)
async def disable_2fa(
    data: TwoFactorDisableRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    """Disable 2FA (requires password + 2FA code or backup code)."""
    raise HTTPException(status_code=501, detail="Requires authentication")


@router.post("/2fa/verify", response_model=dict)
async def verify_2fa(
    data: TwoFactorVerifyRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    """Verify 2FA code during login."""
    raise HTTPException(status_code=501, detail="Requires authentication")