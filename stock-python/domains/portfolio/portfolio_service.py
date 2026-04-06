"""
Portfolio service for business logic.
"""
from datetime import datetime
from typing import Optional
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.portfolio.portfolio import Portfolio, Position, Transaction, TransactionType


class PortfolioService:
    """Service for portfolio operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Portfolio CRUD
    async def create_portfolio(
        self, user_id: int, name: str, initial_cash: float = 0
    ) -> Portfolio:
        """Create a new portfolio."""
        portfolio = Portfolio(
            user_id=user_id,
            name=name,
            cash_balance=initial_cash,
            total_value=initial_cash,
        )
        self.db.add(portfolio)
        await self.db.commit()
        await self.db.refresh(portfolio)
        return portfolio

    async def get_portfolio(self, portfolio_id: int) -> Optional[Portfolio]:
        """Get portfolio by ID."""
        result = await self.db.execute(
            select(Portfolio).where(Portfolio.id == portfolio_id)
        )
        return result.scalar_one_or_none()

    async def get_user_portfolios(self, user_id: int) -> list[Portfolio]:
        """Get all portfolios for a user."""
        result = await self.db.execute(
            select(Portfolio).where(Portfolio.user_id == user_id)
        )
        return list(result.scalars().all())

    async def update_cash_balance(
        self, portfolio_id: int, amount: float
    ) -> Optional[Portfolio]:
        """Update cash balance."""
        portfolio = await self.get_portfolio(portfolio_id)
        if portfolio:
            portfolio.cash_balance += amount
            await self.db.commit()
            await self.db.refresh(portfolio)
        return portfolio

    # Position CRUD
    async def create_position(
        self, portfolio_id: int, stock_id: int, quantity: int, average_cost: float
    ) -> Position:
        """Create a new position."""
        position = Position(
            portfolio_id=portfolio_id,
            stock_id=stock_id,
            quantity=quantity,
            average_cost=average_cost,
        )
        self.db.add(position)
        await self.db.commit()
        await self.db.refresh(position)
        return position

    async def get_position(
        self, portfolio_id: int, stock_id: int
    ) -> Optional[Position]:
        """Get position for a specific stock in a portfolio."""
        result = await self.db.execute(
            select(Position).where(
                Position.portfolio_id == portfolio_id,
                Position.stock_id == stock_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_portfolio_positions(self, portfolio_id: int) -> list[Position]:
        """Get all positions in a portfolio."""
        result = await self.db.execute(
            select(Position)
            .where(Position.portfolio_id == portfolio_id)
            .where(Position.quantity > 0)
        )
        return list(result.scalars().all())

    async def update_position(
        self,
        portfolio_id: int,
        stock_id: int,
        quantity_delta: int,
        price: float,
    ) -> Position:
        """Update position after a buy/sell."""
        position = await self.get_position(portfolio_id, stock_id)

        if quantity_delta > 0:  # Buy
            if position is None:
                position = await self.create_position(
                    portfolio_id, stock_id, quantity_delta, price
                )
            else:
                # Calculate new average cost
                total_cost = (position.quantity * float(position.average_cost or 0)) + (
                    quantity_delta * price
                )
                new_quantity = position.quantity + quantity_delta
                position.average_cost = total_cost / new_quantity if new_quantity > 0 else 0
                position.quantity = new_quantity
                await self.db.commit()
                await self.db.refresh(position)
        elif quantity_delta < 0 and position:  # Sell
            position.quantity += quantity_delta  # quantity_delta is negative
            await self.db.commit()
            await self.db.refresh(position)

        return position

    async def delete_position(self, position_id: int) -> bool:
        """Delete a position."""
        position = await self.db.get(Position, position_id)
        if position:
            await self.db.delete(position)
            await self.db.commit()
            return True
        return False

    # Transaction CRUD
    async def create_transaction(
        self,
        portfolio_id: int,
        transaction_type: TransactionType,
        amount: float,
        stock_id: Optional[int] = None,
        quantity: int = 0,
        price: float = 0,
        notes: Optional[str] = None,
    ) -> Transaction:
        """Create a new transaction."""
        transaction = Transaction(
            portfolio_id=portfolio_id,
            stock_id=stock_id,
            type=transaction_type,
            quantity=quantity,
            price=price,
            total_amount=amount,
            notes=notes,
            transaction_date=datetime.utcnow(),
        )
        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(transaction)
        return transaction

    async def get_portfolio_transactions(
        self, portfolio_id: int, limit: int = 100
    ) -> list[Transaction]:
        """Get transaction history for a portfolio."""
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.transaction_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_stock_transactions(
        self, portfolio_id: int, stock_id: int, limit: int = 50
    ) -> list[Transaction]:
        """Get transaction history for a specific stock."""
        result = await self.db.execute(
            select(Transaction)
            .where(
                Transaction.portfolio_id == portfolio_id,
                Transaction.stock_id == stock_id,
            )
            .order_by(Transaction.transaction_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # Portfolio Summary & P&L
    async def calculate_portfolio_value(self, portfolio_id: int) -> dict:
        """Calculate total portfolio value including positions and cash."""
        portfolio = await self.get_portfolio(portfolio_id)
        if not portfolio:
            return {}

        positions = await self.get_portfolio_positions(portfolio_id)

        positions_value = 0
        total_cost = 0
        positions_data = []

        for pos in positions:
            current_val = pos.current_value
            cost = pos.total_cost
            positions_value += current_val
            total_cost += cost

            positions_data.append({
                "stock_id": pos.stock_id,
                "quantity": pos.quantity,
                "average_cost": float(pos.average_cost or 0),
                "current_price": float(pos.stock.current_price or 0) if pos.stock else 0,
                "current_value": current_val,
                "cost_basis": cost,
                "profit_loss": current_val - cost,
                "profit_loss_pct": ((current_val - cost) / cost * 100) if cost > 0 else 0,
            })

        total_value = float(portfolio.cash_balance) + positions_value
        total_profit_loss = positions_value - total_cost

        return {
            "portfolio_id": portfolio_id,
            "name": portfolio.name,
            "cash_balance": float(portfolio.cash_balance),
            "positions_value": positions_value,
            "total_value": total_value,
            "total_cost_basis": total_cost,
            "total_profit_loss": total_profit_loss,
            "total_profit_loss_pct": (total_profit_loss / total_cost * 100) if total_cost > 0 else 0,
            "positions": positions_data,
        }

    async def execute_buy(
        self, portfolio_id: int, stock_id: int, quantity: int, price: float
    ) -> dict:
        """Execute a buy order."""
        portfolio = await self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError("Portfolio not found")

        total_cost = quantity * price
        if total_cost > float(portfolio.cash_balance):
            raise ValueError("Insufficient cash balance")

        # Update position
        await self.update_position(portfolio_id, stock_id, quantity, price)

        # Deduct cash
        portfolio.cash_balance -= total_cost

        # Create transaction record
        await self.create_transaction(
            portfolio_id=portfolio_id,
            transaction_type=TransactionType.BUY,
            amount=total_cost,
            stock_id=stock_id,
            quantity=quantity,
            price=price,
            notes=f"Bought {quantity} shares at ${price}",
        )

        await self.db.commit()
        await self.db.refresh(portfolio)

        return {
            "success": True,
            "quantity": quantity,
            "price": price,
            "total_amount": total_cost,
            "new_cash_balance": float(portfolio.cash_balance),
        }

    async def execute_sell(
        self, portfolio_id: int, stock_id: int, quantity: int, price: float
    ) -> dict:
        """Execute a sell order."""
        portfolio = await self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError("Portfolio not found")

        position = await self.get_position(portfolio_id, stock_id)
        if not position or position.quantity < quantity:
            raise ValueError("Insufficient shares to sell")

        total_proceeds = quantity * price

        # Update position (quantity_delta is negative)
        await self.update_position(portfolio_id, stock_id, -quantity, price)

        # Add cash
        portfolio.cash_balance += total_proceeds

        # Create transaction record
        await self.create_transaction(
            portfolio_id=portfolio_id,
            transaction_type=TransactionType.SELL,
            amount=total_proceeds,
            stock_id=stock_id,
            quantity=quantity,
            price=price,
            notes=f"Sold {quantity} shares at ${price}",
        )

        await self.db.commit()
        await self.db.refresh(portfolio)

        return {
            "success": True,
            "quantity": quantity,
            "price": price,
            "total_amount": total_proceeds,
            "new_cash_balance": float(portfolio.cash_balance),
        }

    async def deposit(self, portfolio_id: int, amount: float) -> dict:
        """Deposit cash into portfolio."""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        portfolio = await self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError("Portfolio not found")

        portfolio.cash_balance += amount

        await self.create_transaction(
            portfolio_id=portfolio_id,
            transaction_type=TransactionType.DEPOSIT,
            amount=amount,
            notes=f"Deposited ${amount}",
        )

        await self.db.commit()
        await self.db.refresh(portfolio)

        return {
            "success": True,
            "amount": amount,
            "new_cash_balance": float(portfolio.cash_balance),
        }

    async def withdraw(self, portfolio_id: int, amount: float) -> dict:
        """Withdraw cash from portfolio."""
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")

        portfolio = await self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError("Portfolio not found")

        if amount > float(portfolio.cash_balance):
            raise ValueError("Insufficient cash balance")

        portfolio.cash_balance -= amount

        await self.create_transaction(
            portfolio_id=portfolio_id,
            transaction_type=TransactionType.WITHDRAWAL,
            amount=-amount,
            notes=f"Withdrew ${amount}",
        )

        await self.db.commit()
        await self.db.refresh(portfolio)

        return {
            "success": True,
            "amount": amount,
            "new_cash_balance": float(portfolio.cash_balance),
        }