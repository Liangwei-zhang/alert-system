"""
Portfolio API endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from infra.database import get_db
from domains.portfolio.portfolio_service import PortfolioService
from domains.portfolio.portfolio import TransactionType

router = APIRouter(prefix="/portfolios", tags=["portfolio"])


# Pydantic schemas
class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    initial_cash: float = Field(default=0, ge=0)


class PortfolioResponse(BaseModel):
    id: int
    user_id: int
    name: str
    cash_balance: float
    total_value: float

    class Config:
        from_attributes = True


class PositionCreate(BaseModel):
    stock_id: int
    quantity: int = Field(..., gt=0)
    average_cost: float = Field(..., gt=0)


class PositionResponse(BaseModel):
    id: int
    portfolio_id: int
    stock_id: int
    quantity: int
    average_cost: float
    current_value: float
    total_cost: float
    profit_loss: float
    profit_loss_pct: float


class TransactionCreate(BaseModel):
    type: TransactionType
    stock_id: Optional[int] = None
    quantity: int = Field(default=0, ge=0)
    price: float = Field(default=0, ge=0)
    amount: float
    notes: Optional[str] = None


class TransactionResponse(BaseModel):
    id: int
    portfolio_id: int
    stock_id: Optional[int]
    type: TransactionType
    quantity: int
    price: float
    total_amount: float
    notes: Optional[str]
    transaction_date: str

    class Config:
        from_attributes = True


class BuyRequest(BaseModel):
    stock_id: int
    quantity: int = Field(..., gt=0)
    price: float = Field(..., gt=0)


class SellRequest(BaseModel):
    stock_id: int
    quantity: int = Field(..., gt=0)
    price: float = Field(..., gt=0)


class CashOperation(BaseModel):
    amount: float = Field(..., gt=0)


class PortfolioSummaryResponse(BaseModel):
    portfolio_id: int
    name: str
    cash_balance: float
    positions_value: float
    total_value: float
    total_cost_basis: float
    total_profit_loss: float
    total_profit_loss_pct: float
    positions: list


# Portfolio endpoints
@router.post("/", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    portfolio_data: PortfolioCreate,
    user_id: int = 1,  # TODO: Get from auth
    db: AsyncSession = Depends(get_db),
):
    """Create a new portfolio."""
    service = PortfolioService(db)
    portfolio = await service.create_portfolio(
        user_id=user_id,
        name=portfolio_data.name,
        initial_cash=portfolio_data.initial_cash,
    )
    return portfolio


@router.get("/", response_model=list[PortfolioResponse])
async def list_portfolios(
    user_id: int = 1,  # TODO: Get from auth
    db: AsyncSession = Depends(get_db),
):
    """List all portfolios for a user."""
    service = PortfolioService(db)
    portfolios = await service.get_user_portfolios(user_id)
    return portfolios


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific portfolio."""
    service = PortfolioService(db)
    portfolio = await service.get_portfolio(portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


@router.get("/{portfolio_id}/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get portfolio summary with P&L."""
    service = PortfolioService(db)
    summary = await service.calculate_portfolio_value(portfolio_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return summary


# Position endpoints
@router.get("/{portfolio_id}/positions", response_model=list[PositionResponse])
async def list_positions(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List all positions in a portfolio."""
    service = PortfolioService(db)
    positions = await service.get_portfolio_positions(portfolio_id)
    return [
        PositionResponse(
            id=p.id,
            portfolio_id=p.portfolio_id,
            stock_id=p.stock_id,
            quantity=p.quantity,
            average_cost=float(p.average_cost or 0),
            current_value=p.current_value,
            total_cost=p.total_cost,
            profit_loss=p.profit_loss,
            profit_loss_pct=p.profit_loss_pct,
        )
        for p in positions
    ]


@router.post("/{portfolio_id}/positions", status_code=status.HTTP_201_CREATED)
async def create_position(
    portfolio_id: int,
    position_data: PositionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new position (manual entry)."""
    service = PortfolioService(db)
    position = await service.create_position(
        portfolio_id=portfolio_id,
        stock_id=position_data.stock_id,
        quantity=position_data.quantity,
        average_cost=position_data.average_cost,
    )
    return {
        "id": position.id,
        "portfolio_id": position.portfolio_id,
        "stock_id": position.stock_id,
        "quantity": position.quantity,
        "average_cost": float(position.average_cost or 0),
    }


@router.delete("/{portfolio_id}/positions/{position_id}")
async def delete_position(
    portfolio_id: int,
    position_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a position."""
    service = PortfolioService(db)
    success = await service.delete_position(position_id)
    if not success:
        raise HTTPException(status_code=404, detail="Position not found")
    return {"success": True, "message": "Position deleted"}


# Transaction endpoints
@router.get("/{portfolio_id}/transactions", response_model=list[TransactionResponse])
async def list_transactions(
    portfolio_id: int,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List transaction history for a portfolio."""
    service = PortfolioService(db)
    transactions = await service.get_portfolio_transactions(portfolio_id, limit)
    return [
        TransactionResponse(
            id=t.id,
            portfolio_id=t.portfolio_id,
            stock_id=t.stock_id,
            type=t.type,
            quantity=t.quantity,
            price=float(t.price or 0),
            total_amount=float(t.total_amount),
            notes=t.notes,
            transaction_date=t.transaction_date.isoformat(),
        )
        for t in transactions
    ]


# Trading endpoints
@router.post("/{portfolio_id}/buy")
async def execute_buy(
    portfolio_id: int,
    buy_request: BuyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute a buy order."""
    service = PortfolioService(db)
    try:
        result = await service.execute_buy(
            portfolio_id=portfolio_id,
            stock_id=buy_request.stock_id,
            quantity=buy_request.quantity,
            price=buy_request.price,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{portfolio_id}/sell")
async def execute_sell(
    portfolio_id: int,
    sell_request: SellRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute a sell order."""
    service = PortfolioService(db)
    try:
        result = await service.execute_sell(
            portfolio_id=portfolio_id,
            stock_id=sell_request.stock_id,
            quantity=sell_request.quantity,
            price=sell_request.price,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Cash management
@router.post("/{portfolio_id}/deposit")
async def deposit_cash(
    portfolio_id: int,
    cash_operation: CashOperation,
    db: AsyncSession = Depends(get_db),
):
    """Deposit cash into portfolio."""
    service = PortfolioService(db)
    try:
        result = await service.deposit(portfolio_id, cash_operation.amount)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{portfolio_id}/withdraw")
async def withdraw_cash(
    portfolio_id: int,
    cash_operation: CashOperation,
    db: AsyncSession = Depends(get_db),
):
    """Withdraw cash from portfolio."""
    service = PortfolioService(db)
    try:
        result = await service.withdraw(portfolio_id, cash_operation.amount)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))