"""
Portfolio Domain Tests
======================
Tested by: Signal Team
Original developer: Portfolio Team

Test Coverage:
- Happy path: create portfolio, buy/sell execution, P&L calculation
- Edge cases: insufficient cash, insufficient shares, negative amounts
- Error handling: portfolio not found, position not found, invalid operations
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime

from domains.portfolio.portfolio_service import PortfolioService
from domains.portfolio.portfolio import Portfolio, Position, Transaction, TransactionType


class MockPortfolio:
    """Mock Portfolio for testing."""
    def __init__(
        self,
        id=1,
        user_id=1,
        name="Test Portfolio",
        cash_balance=10000.0,
        total_value=10000.0,
    ):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.cash_balance = Decimal(str(cash_balance))
        self.total_value = total_value


class MockPosition:
    """Mock Position for testing."""
    def __init__(
        self,
        id=1,
        portfolio_id=1,
        stock_id=1,
        quantity=100,
        average_cost=50.0,
        stock=None,
    ):
        self.id = id
        self.portfolio_id = portfolio_id
        self.stock_id = stock_id
        self.quantity = quantity
        self.average_cost = Decimal(str(average_cost))
        self.stock = stock
        self.current_value = quantity * 50.0
        self.total_cost = quantity * average_cost


class MockStock:
    """Mock Stock for testing."""
    def __init__(self, id=1, symbol="AAPL", current_price=55.0):
        self.id = id
        self.symbol = symbol
        self.current_price = current_price


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def portfolio_service(mock_db):
    """PortfolioService instance with mock db."""
    return PortfolioService(mock_db)


class TestPortfolioCreation:
    """Test portfolio creation - Happy Path."""

    @pytest.mark.asyncio
    async def test_create_portfolio_success(self, portfolio_service, mock_db):
        """Test successful portfolio creation."""
        # Act
        portfolio = await portfolio_service.create_portfolio(
            user_id=1,
            name="My Portfolio",
            initial_cash=10000.0
        )

        # Assert
        assert portfolio.user_id == 1
        assert portfolio.name == "My Portfolio"
        assert portfolio.cash_balance == Decimal("10000.0")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_portfolio_by_id(self, portfolio_service, mock_db):
        """Test get portfolio by ID - Happy Path."""
        # Arrange
        mock_portfolio = MockPortfolio(id=1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_portfolio
        mock_db.execute.return_value = mock_result

        # Act
        portfolio = await portfolio_service.get_portfolio(1)

        # Assert
        assert portfolio is not None
        assert portfolio.id == 1

    @pytest.mark.asyncio
    async def test_get_user_portfolios(self, portfolio_service, mock_db):
        """Test get all portfolios for user - Happy Path."""
        # Arrange
        portfolios = [MockPortfolio(id=1), MockPortfolio(id=2)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = portfolios
        mock_db.execute.return_value = mock_result

        # Act
        result = await portfolio_service.get_user_portfolios(1)

        # Assert
        assert len(result) == 2


class TestBuyExecution:
    """Test buy execution - Happy Path."""

    @pytest.mark.asyncio
    async def test_execute_buy_success(self, portfolio_service, mock_db):
        """Test successful buy execution."""
        # Arrange
        portfolio = MockPortfolio(cash_balance=10000.0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = portfolio
        mock_db.execute.return_value = mock_result
        mock_db.refresh = AsyncMock(side_effect=lambda x: setattr(x, 'cash_balance', Decimal('9500.0')))

        # Act
        result = await portfolio_service.execute_buy(
            portfolio_id=1,
            stock_id=1,
            quantity=10,
            price=50.0
        )

        # Assert
        assert result["success"] is True
        assert result["quantity"] == 10
        assert result["price"] == 50.0
        assert result["total_amount"] == 500.0

    @pytest.mark.asyncio
    async def test_execute_buy_insufficient_cash(self, portfolio_service, mock_db):
        """Test buy with insufficient cash - Error Handling."""
        # Arrange
        portfolio = MockPortfolio(cash_balance=100.0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = portfolio
        mock_db.execute.return_value = mock_result

        # Act & Assert
        with pytest.raises(ValueError, match="Insufficient cash"):
            await portfolio_service.execute_buy(
                portfolio_id=1,
                stock_id=1,
                quantity=100,
                price=50.0
            )

    @pytest.mark.asyncio
    async def test_execute_buy_portfolio_not_found(self, portfolio_service, mock_db):
        """Test buy with non-existent portfolio - Error Handling."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act & Assert
        with pytest.raises(ValueError, match="Portfolio not found"):
            await portfolio_service.execute_buy(
                portfolio_id=999,
                stock_id=1,
                quantity=10,
                price=50.0
            )


class TestSellExecution:
    """Test sell execution - Happy Path."""

    @pytest.mark.asyncio
    async def test_execute_sell_success(self, portfolio_service, mock_db):
        """Test successful sell execution."""
        # Arrange
        portfolio = MockPortfolio(cash_balance=10000.0)
        position = MockPosition(quantity=100, average_cost=50.0)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = portfolio
        mock_db.execute.return_value = mock_result
        mock_db.refresh = AsyncMock(side_effect=lambda x: setattr(x, 'cash_balance', Decimal('10500.0')))

        # Mock the position lookup
        with patch.object(portfolio_service, 'get_position', return_value=position):
            # Act
            result = await portfolio_service.execute_sell(
                portfolio_id=1,
                stock_id=1,
                quantity=10,
                price=55.0
            )

        # Assert
        assert result["success"] is True
        assert result["quantity"] == 10
        assert result["total_amount"] == 550.0

    @pytest.mark.asyncio
    async def test_execute_sell_insufficient_shares(self, portfolio_service, mock_db):
        """Test sell with insufficient shares - Error Handling."""
        # Arrange
        portfolio = MockPortfolio(cash_balance=10000.0)
        position = MockPosition(quantity=5, average_cost=50.0)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = portfolio
        mock_db.execute.return_value = mock_result

        with patch.object(portfolio_service, 'get_position', return_value=position):
            # Act & Assert
            with pytest.raises(ValueError, match="Insufficient shares"):
                await portfolio_service.execute_sell(
                    portfolio_id=1,
                    stock_id=1,
                    quantity=10,
                    price=55.0
                )


class TestPositionManagement:
    """Test position management - Happy Path & Edge Cases."""

    @pytest.mark.asyncio
    async def test_update_position_buy_new(self, portfolio_service, mock_db):
        """Test creating new position on buy - Happy Path."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act
        position = await portfolio_service.update_position(
            portfolio_id=1,
            stock_id=1,
            quantity_delta=100,
            price=50.0
        )

        # Assert
        assert position is not None
        assert position.quantity == 100

    @pytest.mark.asyncio
    async def test_update_position_buy_increase(self, portfolio_service, mock_db):
        """Test increasing existing position - Edge Case."""
        # Arrange
        existing_position = MockPosition(quantity=100, average_cost=45.0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_position
        mock_db.execute.return_value = mock_result

        # Act
        position = await portfolio_service.update_position(
            portfolio_id=1,
            stock_id=1,
            quantity_delta=50,
            price=50.0
        )

        # Assert
        assert position.quantity == 150

    @pytest.mark.asyncio
    async def test_delete_position(self, portfolio_service, mock_db):
        """Test deleting position - Happy Path."""
        # Arrange
        position = MockPosition(id=1)
        mock_db.get.return_value = position

        # Act
        result = await portfolio_service.delete_position(1)

        # Assert
        assert result is True
        mock_db.delete.assert_called_once()


class TestTransactions:
    """Test transaction operations - Happy Path."""

    @pytest.mark.asyncio
    async def test_create_transaction(self, portfolio_service, mock_db):
        """Test creating transaction - Happy Path."""
        # Act
        transaction = await portfolio_service.create_transaction(
            portfolio_id=1,
            transaction_type=TransactionType.BUY,
            amount=500.0,
            stock_id=1,
            quantity=10,
            price=50.0,
            notes="Test buy"
        )

        # Assert
        assert transaction.portfolio_id == 1
        assert transaction.type == TransactionType.BUY
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_portfolio_transactions(self, portfolio_service, mock_db):
        """Test getting portfolio transactions - Happy Path."""
        # Arrange
        transactions = [
            MagicMock(spec=Transaction, id=1, portfolio_id=1),
            MagicMock(spec=Transaction, id=2, portfolio_id=1),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = transactions
        mock_db.execute.return_value = mock_result

        # Act
        result = await portfolio_service.get_portfolio_transactions(1)

        # Assert
        assert len(result) == 2


class TestPandL:
    """Test P&L calculation - Happy Path."""

    @pytest.mark.asyncio
    async def test_calculate_portfolio_value_with_profit(self, portfolio_service, mock_db):
        """Test P&L calculation with profit - Happy Path."""
        # Arrange
        portfolio = MockPortfolio(cash_balance=5000.0)
        stock = MockStock(id=1, current_price=55.0)
        position = MockPosition(quantity=100, average_cost=45.0, stock=stock)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = portfolio
        mock_db.execute.return_value = mock_result

        # Mock positions query
        positions_result = MagicMock()
        positions_result.scalars.return_value.all.return_value = [position]
        
        # Different queries for portfolio vs positions
        with patch.object(portfolio_service, 'get_portfolio_positions', return_value=[position]):
            # Act
            result = await portfolio_service.calculate_portfolio_value(1)

        # Assert
        assert "total_profit_loss" in result
        assert result["total_value"] > 0

    @pytest.mark.asyncio
    async def test_calculate_portfolio_value_not_found(self, portfolio_service, mock_db):
        """Test P&L with non-existent portfolio - Error Handling."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act
        result = await portfolio_service.calculate_portfolio_value(999)

        # Assert
        assert result == {}


class TestDepositWithdraw:
    """Test deposit and withdrawal - Happy Path & Edge Cases."""

    @pytest.mark.asyncio
    async def test_deposit_success(self, portfolio_service, mock_db):
        """Test successful deposit - Happy Path."""
        # Arrange
        portfolio = MockPortfolio(cash_balance=10000.0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = portfolio
        mock_db.execute.return_value = mock_result
        mock_db.refresh = AsyncMock(side_effect=lambda x: setattr(x, 'cash_balance', Decimal('11000.0')))

        # Act
        result = await portfolio_service.deposit(1, 1000.0)

        # Assert
        assert result["success"] is True
        assert result["amount"] == 1000.0

    @pytest.mark.asyncio
    async def test_deposit_negative_amount(self, portfolio_service, mock_db):
        """Test deposit with negative amount - Edge Case."""
        # Arrange
        portfolio = MockPortfolio(cash_balance=10000.0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = portfolio
        mock_db.execute.return_value = mock_result

        # Act & Assert
        with pytest.raises(ValueError, match="positive"):
            await portfolio_service.deposit(1, -100.0)

    @pytest.mark.asyncio
    async def test_withdraw_insufficient_balance(self, portfolio_service, mock_db):
        """Test withdrawal exceeding balance - Edge Case."""
        # Arrange
        portfolio = MockPortfolio(cash_balance=100.0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = portfolio
        mock_db.execute.return_value = mock_result

        # Act & Assert
        with pytest.raises(ValueError, match="Insufficient cash"):
            await portfolio_service.withdraw(1, 500.0)