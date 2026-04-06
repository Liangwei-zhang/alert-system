"""
Admin API endpoints for user management.
"""
from typing import List, Optional
from pydantic import BaseModel, EmailStr

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from infra.database import get_db
from domains.admin.admin_service import AdminService
from domains.admin.admin import AdminRole


router = APIRouter(prefix="/admin/users", tags=["admin"])


# Pydantic schemas
class AdminUserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: AdminRole = AdminRole.VIEWER


class AdminUserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[AdminRole] = None
    is_active: Optional[bool] = None


class AdminUserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    role: AdminRole
    is_active: bool
    created_at: str
    last_login: Optional[str]

    class Config:
        from_attributes = True


def get_admin_service(db: Session = Depends(get_db)) -> AdminService:
    return AdminService(db)


@router.get("", response_model=List[AdminUserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    service: AdminService = Depends(get_admin_service),
):
    """List all admin users."""
    users = service.list_users(skip=skip, limit=limit)
    return [
        AdminUserResponse(
            id=u.id,
            username=u.username,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at.isoformat(),
            last_login=u.last_login.isoformat() if u.last_login else None,
        )
        for u in users
    ]


@router.get("/{user_id}", response_model=AdminUserResponse)
def get_user(
    user_id: int,
    service: AdminService = Depends(get_admin_service),
):
    """Get admin user by ID."""
    user = service.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return AdminUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    data: AdminUserCreate,
    service: AdminService = Depends(get_admin_service),
):
    """Create a new admin user."""
    # Check if username exists
    if service.get_by_username(data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )
    # Check if email exists
    if service.get_by_email(data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )

    user = service.create_user(
        username=data.username,
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        role=data.role,
    )
    return AdminUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.patch("/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: int,
    data: AdminUserUpdate,
    service: AdminService = Depends(get_admin_service),
):
    """Update an admin user."""
    user = service.update_user(
        user_id=user_id,
        email=data.email,
        full_name=data.full_name,
        role=data.role,
        is_active=data.is_active,
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return AdminUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    service: AdminService = Depends(get_admin_service),
):
    """Delete an admin user."""
    if not service.delete_user(user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return None