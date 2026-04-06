# Account Team Execution Guide

## Overview

The Account Team handles user authentication, authorization, user management, and subscription management.

## Responsibilities

- User registration and login
- JWT token management (access/refresh tokens)
- Email verification
- User profile management
- Subscription tiers and billing

## Current Status

### Completed Components

1. **Authentication (domains/auth/)**
   - User registration with validation
   - Email/password login
   - Verification code login
   - Token refresh mechanism
   - Session logout

2. **User Management (domains/account/)**
   - User profile CRUD operations
   - Password management
   - Account settings

3. **Subscription (domains/subscription/)**
   - Subscription tiers: FREE, STARTER, PRO, ENTERPRISE
   - Trial period management
   - Feature flags per tier
   - Subscription status tracking

4. **Admin User Management (apps/admin_api/routers/admin.py)**
   - Admin user CRUD
   - Role-based access control (VIEWER, USER, MODERATOR, ADMIN, SUPER_ADMIN)

## Migration Tasks

### Phase 1: Authentication

- [x] Implement registration endpoint
- [x] Implement login with email/password
- [x] Implement verification code login
- [x] Implement token refresh
- [x] Implement logout

### Phase 2: User Management

- [x] User profile retrieval
- [x] User profile update
- [x] Password change
- [x] Email verification

### Phase 3: Subscription

- [x] Subscription tier definitions
- [x] Feature flag mapping per tier
- [x] Trial period handling
- [x] Subscription status management

### Phase 4: Admin Features

- [x] Admin user CRUD
- [x] Role assignment
- [x] User activation/deactivation

## API Endpoints

### Auth Endpoints (Public API)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login with email/password |
| POST | `/api/v1/auth/login/code` | Login with verification code |
| POST | `/api/v1/auth/code/send` | Send verification code |
| POST | `/api/v1/auth/verify` | Verify email |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/logout` | Logout |

### Admin User Endpoints (Admin API)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/users` | List admin users |
| POST | `/api/v1/admin/users` | Create admin user |
| GET | `/api/v1/admin/users/{user_id}` | Get admin user |
| PATCH | `/api/v1/admin/users/{user_id}` | Update admin user |
| DELETE | `/api/v1/admin/users/{user_id}` | Delete admin user |

### Subscription Endpoints (Admin API)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/subscription-stats` | Get subscription stats |
| GET | `/api/v1/admin/subscriptions` | List all subscriptions |
| GET | `/api/v1/admin/subscriptions/{id}` | Get subscription |
| PATCH | `/api/v1/admin/subscriptions/{id}` | Update subscription |

## Dependencies

- `domains/auth/auth_service.py` - Authentication logic
- `domains/auth/user.py` - User model
- `domains/account/` - Account management
- `domains/subscription/subscription.py` - Subscription models
- `infra/security/` - JWT and password hashing

## Testing Strategy

1. Unit tests for auth service
2. Integration tests for login/registration flows
3. Subscription tier validation tests
4. Admin role permission tests

## Subscription Tiers

| Tier | Signals/Day | Max Portfolios | Max Strategies | Realtime | Backtesting | API Access |
|------|--------------|----------------|-----------------|----------|-------------|------------|
| FREE | 5 | 1 | 1 | ❌ | ❌ | ❌ |
| STARTER | 20 | 3 | 3 | ❌ | ❌ | ❌ |
| PRO | 100 | 10 | 10 | ✅ | ✅ | ✅ |
| ENTERPRISE | Unlimited | Unlimited | Unlimited | ✅ | ✅ | ✅ |

## Next Steps

1. Add password reset functionality
2. Implement 2FA support
3. Add rate limiting for auth endpoints
4. Enhance subscription billing integration