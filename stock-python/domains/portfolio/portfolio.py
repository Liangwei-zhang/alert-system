"""
Portfolio, Position, and Transaction models.
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, Numeric, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infra.database import Base


class TransactionType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"


class Portfolio(Base):
    """User portfolio model."""

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    cash_balance: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    total_value: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    positions: Mapped[list["Position"]] = relationship(
        "Position", back_populates="portfolio", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="portfolio", cascade="all, delete-orphan"
    )


class Position(Base):
    """Stock position in a portfolio."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolios.id"), index=True
    )
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    average_cost: Mapped[float] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="positions")
    stock: Mapped["Stock"] = relationship("Stock")

    @property
    def current_value(self) -> float:
        """Calculate current market value of position."""
        if self.stock and self.stock.current_price:
            return float(self.stock.current_price) * self.quantity
        return 0

    @property
    def total_cost(self) -> float:
        """Calculate total cost basis."""
        return float(self.average_cost or 0) * self.quantity

    @property
    def profit_loss(self) -> float:
        """Calculate profit/loss."""
        return self.current_value - self.total_cost

    @property
    def profit_loss_pct(self) -> float:
        """Calculate profit/loss percentage."""
        if self.total_cost > 0:
            return (self.profit_loss / self.total_cost) * 100
        return 0


class Transaction(Base):
    """Transaction history model."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolios.id"), index=True
    )
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=True)
    type: Mapped[TransactionType] = mapped_column(SQLEnum(TransactionType), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    total_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    notes: Mapped[str] = mapped_column(String(500), nullable=True)
    transaction_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="transactions")
    stock: Mapped["Stock"] = relationship("Stock")