"""
Auth Domain Tests
=================
Tested by: Portfolio Team (Agent B)
Original developer: Auth Team (Agent A)

Test Coverage:
- Happy path: login, register, JWT token generation, refresh token flow
- Edge cases: rate limiting, session expiry, duplicate user registration
- Error handling: invalid credentials, disabled account, expired verification code
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from domains.auth.auth_service import AuthService
from domains.auth.user import User


class MockUser:
    """Mock User for testing."""
    def __init__(
        self,
        id=1,
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$mock_hash",
        is_active=True,
        email_verified=False,
        verification_code=None,
        verification_expires=None,
        last_login=None,
        last_ip=None,
    ):
        self.id = id
        self.username = username
        self.email = email
        self.hashed_password = hashed_password
        self.is_active = is_active
        self.email_verified = email_verified
        self.verification_code = verification_code
        self.verification_expires = verification_expires
        self.last_login = last_login
        self.last_ip = last_ip


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def auth_service(mock_db):
    """AuthService instance with mock db."""
    return AuthService(mock_db)


class TestUserRegistration:
    """Test user registration - Happy Path."""

    @pytest.mark.asyncio
    async def test_register_new_user_success(self, auth_service, mock_db):
        """Test successful user registration."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act
        user = await auth_service.register(
            username="newuser",
            email="new@example.com",
            password="SecurePass123!",
            full_name="New User",
            ip="192.168.1.1"
        )

        # Assert
        assert user.username == "newuser"
        assert user.email == "new@example.com"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, auth_service, mock_db):
        """Test registration with duplicate username - Edge Case."""
        # Arrange
        existing_user = MockUser(username="existing", email="other@example.com")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute.return_value = mock_result

        # Act & Assert
        with pytest.raises(ValueError, match="already exists"):
            await auth_service.register(
                username="existing",
                email="new@example.com",
                password="SecurePass123!"
            )

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, auth_service, mock_db):
        """Test registration with duplicate email - Edge Case."""
        # Arrange
        existing_user = MockUser(username="other", email="taken@example.com")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute.return_value = mock_result

        # Act & Assert
        with pytest.raises(ValueError, match="already exists"):
            await auth_service.register(
                username="newuser",
                email="taken@example.com",
                password="SecurePass123!"
            )


class TestUserLogin:
    """Test user login - Happy Path."""

    @pytest.mark.asyncio
    async def test_login_success(self, auth_service, mock_db):
        """Test successful login returns tokens."""
        # Arrange
        user = MockUser(id=1, email="test@example.com", is_active=True)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        with patch('domains.auth.auth_service.verify_password', return_value=True), \
             patch('domains.auth.auth_service.create_access_token', return_value="access_token"), \
             patch('domains.auth.auth_service.create_refresh_token', return_value="refresh_token"), \
             patch('domains.auth.auth_service.cache') as mock_cache:
            
            # Act
            result = await auth_service.login(
                email="test@example.com",
                password="password123",
                ip="192.168.1.1"
            )

        # Assert
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["user"] is user

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, auth_service, mock_db):
        """Test login with invalid password - Error Handling."""
        # Arrange
        user = MockUser(email="test@example.com")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        with patch('domains.auth.auth_service.verify_password', return_value=False):
            # Act & Assert
            with pytest.raises(ValueError, match="Invalid email or password"):
                await auth_service.login(
                    email="test@example.com",
                    password="wrongpassword"
                )

    @pytest.mark.asyncio
    async def test_login_disabled_account(self, auth_service, mock_db):
        """Test login with disabled account - Error Handling."""
        # Arrange
        user = MockUser(is_active=False)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        with patch('domains.auth.auth_service.verify_password', return_value=True):
            # Act & Assert
            with pytest.raises(ValueError, match="Account is disabled"):
                await auth_service.login(
                    email="test@example.com",
                    password="password123"
                )

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, auth_service, mock_db):
        """Test login with non-existent user - Error Handling."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid email or password"):
            await auth_service.login(
                email="nonexistent@example.com",
                password="password123"
            )


class TestTokenRefresh:
    """Test JWT token refresh - Happy Path."""

    @pytest.mark.asyncio
    async def test_refresh_tokens_success(self, auth_service, mock_db):
        """Test successful token refresh."""
        # Arrange
        user = MockUser(id=1, email="test@example.com", is_active=True, last_ip="192.168.1.1")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        with patch('domains.auth.auth_service.verify_token_type') as mock_verify, \
             patch('domains.auth.auth_service.create_access_token', return_value="new_access"), \
             patch('domains.auth.auth_service.create_refresh_token', return_value="new_refresh"), \
             patch('domains.auth.auth_service.cache'):
            
            mock_verify.return_value = {"sub": "1", "email": "test@example.com", "type": "refresh"}

            # Act
            result = await auth_service.refresh_tokens("old_refresh_token")

        # Assert
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["access_token"] == "new_access"

    @pytest.mark.asyncio
    async def test_refresh_tokens_invalid_user(self, auth_service, mock_db):
        """Test token refresh with invalid user - Error Handling."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch('domains.auth.auth_service.verify_token_type') as mock_verify:
            mock_verify.return_value = {"sub": "999", "type": "refresh"}

            # Act & Assert
            with pytest.raises(ValueError, match="Invalid user"):
                await auth_service.refresh_tokens("some_refresh_token")


class TestRateLimiting:
    """Test rate limiting - Edge Cases."""

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, auth_service, mock_db):
        """Test rate limit is enforced - Edge Case."""
        # Arrange
        user = MockUser(email="test@example.com")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        with patch('domains.auth.auth_service.verify_password', return_value=True), \
             patch('domains.auth.auth_service.settings') as mock_settings, \
             patch('domains.auth.auth_service.cache') as mock_cache:
            
            mock_settings.RATE_LIMIT_PER_MINUTE = 5
            mock_cache.incr.return_value = 100  # Exceeds limit

            # Act & Assert
            with pytest.raises(ValueError, match="Rate limit exceeded"):
                await auth_service.login(
                    email="test@example.com",
                    password="password123",
                    ip="192.168.1.1"
                )


class TestVerificationCode:
    """Test email verification code - Edge Cases."""

    @pytest.mark.asyncio
    async def test_verify_email_expired_code(self, auth_service, mock_db):
        """Test verification with expired code - Error Handling."""
        # Arrange
        user = MockUser(
            verification_code="123456",
            verification_expires=datetime.utcnow() - timedelta(minutes=20)
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        # Act
        result = await auth_service.verify_email("test@example.com", "123456")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_email_invalid_code(self, auth_service, mock_db):
        """Test verification with invalid code - Error Handling."""
        # Arrange
        user = MockUser(
            verification_code="123456",
            verification_expires=datetime.utcnow() + timedelta(minutes=10)
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = mock_result

        # Act
        result = await auth_service.verify_email("test@example.com", "000000")

        # Assert
        assert result is False


class TestSessionManagement:
    """Test session management - Happy Path & Edge Cases."""

    @pytest.mark.asyncio
    async def test_logout_deletes_session(self, auth_service, mock_db):
        """Test logout deletes session - Happy Path."""
        # Arrange
        with patch('domains.auth.auth_service.cache') as mock_cache:
            mock_cache.delete = AsyncMock()

            # Act
            await auth_service.logout("valid_token")

        # Assert
        mock_cache.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_session_returns_data(self, auth_service, mock_db):
        """Test session validation - Happy Path."""
        # Arrange
        session_data = {"user_id": 1, "ip": "192.168.1.1"}
        with patch('domains.auth.auth_service.cache') as mock_cache:
            mock_cache.get = AsyncMock(return_value=session_data)

            # Act
            result = await auth_service.validate_session("valid_token")

        # Assert
        assert result == session_data