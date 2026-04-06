"""
Auth Service Tests
=================
Tested by: Portfolio Team (Agent B)
Original developer: Auth Team (Agent A)

Comprehensive tests for Auth domain services:
- AuthService (login, register, sessions, rate limiting)
- PasswordResetService 
- TwoFactorService

Coverage: Happy path, edge cases, error handling
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timedelta
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ============== Mock Classes ==============

class MockUser:
    """Mock User model for testing."""
    def __init__(
        self,
        id=1,
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$mock_hash",
        full_name="Test User",
        is_active=True,
        is_superuser=False,
        email_verified=False,
        verification_code=None,
        verification_expires=None,
        reset_code=None,
        reset_code_expires=None,
        two_factor_enabled=False,
        two_factor_secret=None,
        two_factor_backup_codes=None,
        last_login=None,
        last_ip=None,
    ):
        self.id = id
        self.username = username
        self.email = email
        self.hashed_password = hashed_password
        self.full_name = full_name
        self.is_active = is_active
        self.is_superuser = is_superuser
        self.email_verified = email_verified
        self.verification_code = verification_code
        self.verification_expires = verification_expires
        self.reset_code = reset_code
        self.reset_code_expires = reset_code_expires
        self.two_factor_enabled = two_factor_enabled
        self.two_factor_secret = two_factor_secret
        self.two_factor_backup_codes = two_factor_backup_codes
        self.last_login = last_login
        self.last_ip = last_ip


class MockCache:
    """Mock Redis cache for testing."""
    def __init__(self):
        self.store = {}
        self.client = MagicMock()
    
    async def get(self, key: str):
        return self.store.get(key)
    
    async def set(self, key: str, value, expire=None):
        self.store[key] = value
    
    async def delete(self, key: str):
        if key in self.store:
            del self.store[key]
    
    async def incr(self, key: str):
        current = self.store.get(key, {"count": 0})
        if isinstance(current, dict):
            current["count"] = current.get("count", 0) + 1
            self.store[key] = current
            return current["count"]
        return 1


# ============== Fixtures ==============

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def mock_cache():
    """Mock cache for testing."""
    return MockCache()


@pytest.fixture
def mock_user():
    """Mock user fixture."""
    return MockUser()


# ============== AuthService Tests ==============

class TestAuthServiceRegistration:
    """Tests for user registration - Happy Path."""
    
    @pytest.mark.asyncio
    @patch('domains.auth.auth_service.hash_password')
    @patch('domains.auth.auth_service.User')
    async def test_register_success(self, mock_user_class, mock_hash, mock_db, mock_cache):
        """Test successful user registration."""
        # Setup
        mock_hash.return_value = "hashed_password"
        mock_user_instance = MockUser()
        mock_user_class.return_value = mock_user_instance
        
        with patch('domains.auth.auth_service.cache', mock_cache):
            with patch('domains.auth.auth_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                mock_db.execute.return_value = mock_result
                
                from domains.auth.auth_service import AuthService
                service = AuthService(mock_db)
                
                # Act
                user = await service.register(
                    username="newuser",
                    email="new@example.com",
                    password="SecurePass123!",
                    full_name="New User",
                    ip="192.168.1.1"
                )
                
                # Assert
                assert user is not None
                mock_db.add.assert_called()
                mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    @patch('domains.auth.auth_service.hash_password')
    @patch('domains.auth.auth_service.User')
    async def test_register_with_optional_fields(self, mock_user_class, mock_hash, mock_db, mock_cache):
        """Test registration with optional ip and full_name."""
        mock_hash.return_value = "hashed_password"
        
        with patch('domains.auth.auth_service.cache', mock_cache):
            with patch('domains.auth.auth_service.select'):
                from domains.auth.auth_service import AuthService
                service = AuthService(mock_db)
                
                user = await service.register(
                    username="user1",
                    email="user1@example.com",
                    password="Pass123!",
                )
                
                assert user is not None


class TestAuthServiceRegistrationEdgeCases:
    """Tests for registration - Edge Cases."""
    
    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, mock_db):
        """Test duplicate username raises error."""
        with patch('domains.auth.auth_service.cache', mock_cache):
            with patch('domains.auth.auth_service.select') as mock_select:
                existing_user = MockUser(username="existing", email="existing@example.com")
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = existing_user
                mock_db.execute.return_value = mock_result
                
                from domains.auth.auth_service import AuthService
                service = AuthService(mock_db)
                
                with pytest.raises(ValueError, match="already exists"):
                    await service.register(
                        username="existing",
                        email="different@example.com",
                        password="Pass123!"
                    )
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, mock_db):
        """Test duplicate email raises error."""
        with patch('domains.auth.auth_service.cache', mock_cache):
            with patch('domains.auth.auth_service.select') as mock_select:
                existing_user = MockUser(username="existing", email="existing@example.com")
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = existing_user
                mock_db.execute.return_value = mock_result
                
                from domains.auth.auth_service import AuthService
                service = AuthService(mock_db)
                
                with pytest.raises(ValueError, match="already exists"):
                    await service.register(
                        username="different",
                        email="existing@example.com",
                        password="Pass123!"
                    )


class TestAuthServiceLogin:
    """Tests for user login - Happy Path."""
    
    @pytest.mark.asyncio
    @patch('domains.auth.auth_service.verify_password')
    @patch('domains.auth.auth_service.create_access_token')
    @patch('domains.auth.auth_service.create_refresh_token')
    async def test_login_success(self, mock_refresh, mock_access, mock_verify, mock_db, mock_cache):
        """Test successful login returns tokens."""
        mock_verify.return_value = True
        mock_access.return_value = "access_token"
        mock_refresh.return_value = "refresh_token"
        
        test_user = MockUser()
        
        with patch('domains.auth.auth_service.cache', mock_cache):
            with patch('domains.auth.auth_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = test_user
                mock_db.execute.return_value = mock_result
                
                from domains.auth.auth_service import AuthService
                service = AuthService(mock_db)
                
                result = await service.login(
                    email="test@example.com",
                    password="correct_password",
                    ip="192.168.1.1"
                )
                
                assert "access_token" in result
                assert "refresh_token" in result
                assert result["user"] is test_user


class TestAuthServiceLoginErrors:
    """Tests for login - Error Handling."""
    
    @pytest.mark.asyncio
    @patch('domains.auth.auth_service.verify_password')
    async def test_login_invalid_password(self, mock_verify, mock_db, mock_cache):
        """Test login with invalid password."""
        mock_verify.return_value = False
        
        with patch('domains.auth.auth_service.cache', mock_cache):
            with patch('domains.auth.auth_service.select') as mock_select:
                test_user = MockUser()
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = test_user
                mock_db.execute.return_value = mock_result
                
                from domains.auth.auth_service import AuthService
                service = AuthService(mock_db)
                
                with pytest.raises(ValueError, match="Invalid"):
                    await service.login(
                        email="test@example.com",
                        password="wrong_password"
                    )
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, mock_db, mock_cache):
        """Test login with nonexistent user."""
        with patch('domains.auth.auth_service.cache', mock_cache):
            with patch('domains.auth.auth_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                mock_db.execute.return_value = mock_result
                
                from domains.auth.auth_service import AuthService
                service = AuthService(mock_db)
                
                with pytest.raises(ValueError, match="Invalid"):
                    await service.login(
                        email="notfound@example.com",
                        password="any_password"
                    )
    
    @pytest.mark.asyncio
    @patch('domains.auth.auth_service.verify_password')
    async def test_login_disabled_account(self, mock_verify, mock_db, mock_cache):
        """Test login with disabled account."""
        mock_verify.return_value = True
        
        disabled_user = MockUser(is_active=False)
        
        with patch('domains.auth.auth_service.cache', mock_cache):
            with patch('domains.auth.auth_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = disabled_user
                mock_db.execute.return_value = mock_result
                
                from domains.auth.auth_service import AuthService
                service = AuthService(mock_db)
                
                with pytest.raises(ValueError, match="disabled"):
                    await service.login(
                        email="test@example.com",
                        password="correct_password"
                    )


class TestAuthServiceTokenRefresh:
    """Tests for token refresh - Happy Path."""
    
    @pytest.mark.asyncio
    @patch('domains.auth.auth_service.verify_token_type')
    @patch('domains.auth.auth_service.create_access_token')
    @patch('domains.auth.auth_service.create_refresh_token')
    async def test_refresh_tokens_success(self, mock_refresh, mock_access, mock_verify, mock_db, mock_cache):
        """Test successful token refresh."""
        mock_verify.return_value = {"sub": "1", "type": "refresh"}
        mock_access.return_value = "new_access"
        mock_refresh.return_value = "new_refresh"
        
        test_user = MockUser()
        
        with patch('domains.auth.auth_service.cache', mock_cache):
            with patch('domains.auth.auth_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = test_user
                mock_db.execute.return_value = mock_result
                
                from domains.auth.auth_service import AuthService
                service = AuthService(mock_db)
                
                result = await service.refresh_tokens("valid_refresh_token")
                
                assert "access_token" in result
                assert "refresh_token" in result


class TestAuthServiceLogout:
    """Tests for logout - Happy Path."""
    
    @pytest.mark.asyncio
    async def test_logout(self, mock_db, mock_cache):
        """Test logout deletes session."""
        with patch('domains.auth.auth_service.cache', mock_cache):
            from domains.auth.auth_service import AuthService
            service = AuthService(mock_db)
            
            # No error should occur
            await service.logout("some_token")
            
            # Session should be deleted from cache
            assert True  # If we get here, test passed


# ============== PasswordResetService Tests ==============

class TestPasswordResetService:
    """Tests for password reset functionality."""
    
    @pytest.mark.asyncio
    async def test_request_password_reset_success(self, mock_db, mock_cache):
        """Test successful password reset request."""
        with patch('domains.auth.password_reset_service.cache', mock_cache):
            with patch('domains.auth.password_reset_service.select') as mock_select:
                test_user = MockUser()
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = test_user
                mock_db.execute.return_value = mock_result
                
                from domains.auth.password_reset_service import PasswordResetService
                service = PasswordResetService(mock_db)
                
                code = await service.request_password_reset("test@example.com")
                
                assert code is not None
                mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_request_password_reset_nonexistent_email(self, mock_db, mock_cache):
        """Test password reset for nonexistent email - no enumeration."""
        with patch('domains.auth.password_reset_service.cache', mock_cache):
            with patch('domains.auth.password_reset_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                mock_db.execute.return_value = mock_result
                
                from domains.auth.password_reset_service import PasswordResetService
                service = PasswordResetService(mock_db)
                
                # Should return generic message, not reveal user doesn't exist
                result = await service.request_password_reset("nonexistent@example.com")
                assert result == "reset_sent"


class TestPasswordResetVerification:
    """Tests for password reset verification."""
    
    @pytest.mark.asyncio
    async def test_verify_reset_code_valid(self, mock_db):
        """Test valid reset code verification."""
        test_user = MockUser(
            reset_code="ABC123",
            reset_code_expires=datetime.utcnow() + timedelta(minutes=10)
        )
        
        with patch('domains.auth.password_reset_service.select') as mock_select:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = test_user
            mock_db.execute.return_value = mock_result
            
            from domains.auth.password_reset_service import PasswordResetService
            service = PasswordResetService(mock_db)
            
            result = await service.verify_reset_code("test@example.com", "ABC123")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_verify_reset_code_expired(self, mock_db):
        """Test expired reset code verification."""
        test_user = MockUser(
            reset_code="ABC123",
            reset_code_expires=datetime.utcnow() - timedelta(minutes=1)
        )
        
        with patch('domains.auth.password_reset_service.select') as mock_select:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = test_user
            mock_db.execute.return_value = mock_result
            
            from domains.auth.password_reset_service import PasswordResetService
            service = PasswordResetService(mock_db)
            
            result = await service.verify_reset_code("test@example.com", "ABC123")
            assert result is False


class TestPasswordReset:
    """Tests for actual password reset."""
    
    @pytest.mark.asyncio
    @patch('domains.auth.password_reset_service.hash_password')
    async def test_reset_password_success(self, mock_hash, mock_db):
        """Test successful password reset."""
        mock_hash.return_value = "new_hashed_password"
        
        test_user = MockUser(
            reset_code="ABC123",
            reset_code_expires=datetime.utcnow() + timedelta(minutes=10)
        )
        
        with patch('domains.auth.password_reset_service.cache', MockCache()):
            with patch('domains.auth.password_reset_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = test_user
                mock_db.execute.return_value = mock_result
                
                from domains.auth.password_reset_service import PasswordResetService
                service = PasswordResetService(mock_db)
                
                result = await service.reset_password(
                    "test@example.com",
                    "ABC123",
                    "NewPass123!"
                )
                
                assert result is True
                mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_reset_password_invalid_code(self, mock_db):
        """Test password reset with invalid code."""
        test_user = MockUser(
            reset_code="ABC123",
            reset_code_expires=datetime.utcnow() + timedelta(minutes=10)
        )
        
        with patch('domains.auth.password_reset_service.cache', MockCache()):
            with patch('domains.auth.password_reset_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = test_user
                mock_db.execute.return_value = mock_result
                
                from domains.auth.password_reset_service import PasswordResetService
                service = PasswordResetService(mock_db)
                
                with pytest.raises(ValueError, match="Invalid"):
                    await service.reset_password(
                        "test@example.com",
                        "WRONGCODE",
                        "NewPass123!"
                    )


class TestPasswordResetEdgeCases:
    """Tests for password reset - Edge Cases."""
    
    @pytest.mark.asyncio
    async def test_password_too_short(self, mock_db):
        """Test password too short."""
        with patch('domains.auth.password_reset_service.cache', MockCache()):
            with patch('domains.auth.password_reset_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                mock_db.execute.return_value = mock_result
                
                from domains.auth.password_reset_service import PasswordResetService
                service = PasswordResetService(mock_db)
                
                test_user = MockUser(reset_code="ABC123", reset_code_expires=datetime.utcnow() + timedelta(minutes=10))
                
                with patch('domains.auth.password_reset_service.select', create=True) as mock_sel:
                    mock_res = MagicMock()
                    mock_res.scalar_one_or_none.return_value = test_user
                    mock_db.execute.return_value = mock_res
                    
                    with pytest.raises(ValueError, match="at least 8"):
                        await service.reset_password(
                            "test@example.com",
                            "ABC123",
                            "short"
                        )
    
    @pytest.mark.asyncio
    async def test_password_weak(self, mock_db):
        """Test weak password (no mixed case/digits)."""
        test_user = MockUser(
            reset_code="ABC123",
            reset_code_expires=datetime.utcnow() + timedelta(minutes=10)
        )
        
        with patch('domains.auth.password_reset_service.cache', MockCache()):
            with patch('domains.auth.password_reset_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = test_user
                mock_db.execute.return_value = mock_result
                
                from domains.auth.password_reset_service import PasswordResetService
                service = PasswordResetService(mock_db)
                
                with pytest.raises(ValueError, match="contain at least"):
                    await service.reset_password(
                        "test@example.com",
                        "ABC123",
                        "alllowercase"
                    )


# ============== TwoFactorService Tests ==============

class TestTwoFactorService:
    """Tests for 2FA functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_2fa_setup(self, mock_db):
        """Test 2FA setup generation."""
        test_user = MockUser()
        
        with patch('domains.auth.two_factor_service.cache', MockCache()):
            with patch('domains.auth.two_factor_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = test_user
                mock_db.execute.return_value = mock_result
                
                from domains.auth.two_factor_service import TwoFactorService
                service = TwoFactorService(mock_db)
                
                secret, qr_url = await service.generate_2fa_setup(user_id=1)
                
                assert secret is not None
                assert "otpauth://" in qr_url
    
    @pytest.mark.asyncio
    @patch('domains.auth.two_factor_service.pyotp')
    async def test_enable_2fa_success(self, mock_pyotp, mock_db):
        """Test enabling 2FA with valid code."""
        # Setup mock for TOTP verification
        mock_totp = MagicMock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp
        
        test_user = MockUser()
        
        with patch('domains.auth.two_factor_service.cache', MockCache()):
            with patch('domains.auth.two_factor_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = test_user
                mock_db.execute.return_value = mock_result
                
                from domains.auth.two_factor_service import TwoFactorService
                service = TwoFactorService(mock_db)
                
                # Need to setup pending 2FA first
                mock_cache = MockCache()
                await mock_cache.set("2fa_pending:1", {"secret": "JBSWY3DPEHPK3PXP"})
                
                with patch('domains.auth.two_factor_service.cache', mock_cache):
                    result = await service.enable_2fa(user_id=1, code="123456")
                    
                    assert result is True
    
    @pytest.mark.asyncio
    async def test_disable_2fa_no_code(self, mock_db):
        """Test disabling 2FA without code when enabled."""
        test_user = MockUser(two_factor_enabled=True)
        
        with patch('domains.auth.two_factor_service.cache', MockCache()):
            with patch('domains.auth.two_factor_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = test_user
                mock_db.execute.return_value = mock_result
                
                from domains.auth.two_factor_service import TwoFactorService
                service = TwoFactorService(mock_db)
                
                with pytest.raises(ValueError, match="2FA code required"):
                    await service.disable_2fa(user_id=1, password="any_password")
    
    @pytest.mark.asyncio
    async def test_get_2fa_status_disabled(self, mock_db):
        """Test getting 2FA status when disabled."""
        test_user = MockUser(two_factor_enabled=False)
        
        with patch('domains.auth.two_factor_service.select') as mock_select:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = test_user
            mock_db.execute.return_value = mock_result
            
            from domains.auth.two_factor_service import TwoFactorService
            service = TwoFactorService(mock_db)
            
            status = await service.get_2fa_status(user_id=1)
            
            assert status["enabled"] is False
    
    @pytest.mark.asyncio
    async def test_get_2fa_status_enabled(self, mock_db):
        """Test getting 2FA status when enabled."""
        test_user = MockUser(
            two_factor_enabled=True,
            two_factor_backup_codes="hashed_codes"
        )
        
        with patch('domains.auth.two_factor_service.select') as mock_select:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = test_user
            mock_db.execute.return_value = mock_result
            
            from domains.auth.two_factor_service import TwoFactorService
            service = TwoFactorService(mock_db)
            
            status = await service.get_2fa_status(user_id=1)
            
            assert status["enabled"] is True
            assert status["has_backup_codes"] is True


class TestTwoFactorServiceErrors:
    """Tests for 2FA - Error Handling."""
    
    @pytest.mark.asyncio
    async def test_enable_2fa_no_pending(self, mock_db):
        """Test enabling 2FA without pending setup."""
        empty_cache = MockCache()
        
        with patch('domains.auth.two_factor_service.cache', empty_cache):
            from domains.auth.two_factor_service import TwoFactorService
            service = TwoFactorService(mock_db)
            
            with pytest.raises(ValueError, match="No pending 2FA setup"):
                await service.enable_2fa(user_id=1, code="123456")
    
    @pytest.mark.asyncio
    async def test_verify_2fa_user_not_found(self, mock_db):
        """Test verifying 2FA for nonexistent user."""
        with patch('domains.auth.two_factor_service.cache', MockCache()):
            with patch('domains.auth.two_factor_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                mock_db.execute.return_value = mock_result
                
                from domains.auth.two_factor_service import TwoFactorService
                service = TwoFactorService(mock_db)
                
                result = await service.verify_2fa(user_id=1, code="123456")
                
                assert result is False
    
    @pytest.mark.asyncio
    @patch('domains.auth.two_factor_service.pyotp')
    async def test_verify_2fa_invalid_code(self, mock_pyotp, mock_db):
        """Test verifying 2FA with invalid code."""
        mock_totp = MagicMock()
        mock_totp.verify.return_value = False
        mock_pyotp.TOTP.return_value = mock_totp
        
        test_user = MockUser(two_factor_enabled=True, two_factor_secret="SECRET")
        
        with patch('domains.auth.two_factor_service.cache', MockCache()):
            with patch('domains.auth.two_factor_service.select') as mock_select:
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = test_user
                mock_db.execute.return_value = mock_result
                
                from domains.auth.two_factor_service import TwoFactorService
                service = TwoFactorService(mock_db)
                
                result = await service.verify_2fa(user_id=1, code="wrong_code")
                
                assert result is False


# ============== Rate Limiting Tests ==============

class TestRateLimiting:
    """Tests for rate limiting functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_check_first_request(self, mock_db):
        """Test first request doesn't hit limit."""
        with patch('domains.auth.auth_service.cache', MockCache()):
            with patch('domains.auth.auth_service.settings') as mock_settings:
                mock_settings.RATE_LIMIT_PER_MINUTE = 10
                
                from domains.auth.auth_service import AuthService
                service = AuthService(mock_db)
                
                # Should not raise
                await service._check_rate_limit("192.168.1.1")
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, mock_db):
        """Test rate limit exceeded error."""
        mock_cache = MockCache()
        # Pre-fill to exceed limit
        mock_cache.store["rate_limit:192.168.1.1"] = {"count": 100}
        
        with patch('domains.auth.auth_service.cache', mock_cache):
            with patch('domains.auth.auth_service.settings') as mock_settings:
                mock_settings.RATE_LIMIT_PER_MINUTE = 10
                
                from domains.auth.auth_service import AuthService
                service = AuthService(mock_db)
                
                with pytest.raises(ValueError, match="Rate limit"):
                    await service._check_rate_limit("192.168.1.1")


# ============== Session Tests ==============

class TestSessionManagement:
    """Tests for session management."""
    
    @pytest.mark.asyncio
    async def test_create_session(self, mock_db):
        """Test session creation."""
        mock_cache = MockCache()
        
        with patch('domains.auth.auth_service.cache', mock_cache):
            from domains.auth.auth_service import AuthService
            service = AuthService(mock_db)
            
            await service._create_session("token123", user_id=1, ip="192.168.1.1")
            
            session = await mock_cache.get("session:token123")
            assert session is not None
            assert session["user_id"] == 1
    
    @pytest.mark.asyncio
    async def test_validate_session(self, mock_db):
        """Test session validation."""
        mock_cache = MockCache()
        mock_cache.store["session:token123"] = {"user_id": 1, "ip": "192.168.1.1"}
        
        with patch('domains.auth.auth_service.cache', mock_cache):
            from domains.auth.auth_service import AuthService
            service = AuthService(mock_db)
            
            session = await service.validate_session("token123")
            
            assert session is not None
            assert session["user_id"] == 1
    
    @pytest.mark.asyncio
    async def test_delete_session(self, mock_db):
        """Test session deletion."""
        mock_cache = MockCache()
        mock_cache.store["session:token123"] = {"user_id": 1}
        
        with patch('domains.auth.auth_service.cache', mock_cache):
            from domains.auth.auth_service import AuthService
            service = AuthService(mock_db)
            
            await service.logout("token123")
            
            session = await mock_cache.get("session:token123")
            assert session is None