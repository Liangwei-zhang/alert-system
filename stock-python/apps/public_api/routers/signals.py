"""
Signal API endpoints.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from infra.database import get_db
from domains.signals.signal import Signal, SignalType, SignalStatus
from domains.signals.signal_service import SignalService

router = APIRouter(prefix="/signals", tags=["signals"])


# Pydantic schemas
class SignalCreate(BaseModel):
    """Schema for creating a signal manually."""
    stock_id: int
    signal_type: SignalType
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    reasoning: Optional[str] = None


class SignalUpdate(BaseModel):
    """Schema for updating a signal."""
    status: Optional[SignalStatus] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None


class SignalResponse(BaseModel):
    """Schema for signal response."""
    id: int
    stock_id: int
    symbol: str
    signal_type: SignalType
    status: SignalStatus
    entry_price: float
    stop_loss: Optional[float]
    take_profit_1: Optional[float]
    take_profit_2: Optional[float]
    take_profit_3: Optional[float]
    probability: float
    confidence: float
    risk_reward_ratio: Optional[float]
    sfp_validated: bool
    chooch_validated: bool
    fvg_validated: bool
    atr_value: Optional[float]
    atr_multiplier: float
    reasoning: Optional[str]
    generated_at: datetime
    triggered_at: Optional[datetime]
    expired_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class SignalStatsResponse(BaseModel):
    """Schema for signal statistics."""
    total_signals: int
    active_signals: int
    triggered_signals: int
    average_confidence: float


class OHLCVRequest(BaseModel):
    """Schema for OHLCV data submission."""
    symbol: str = Field(..., description="Stock symbol")
    high: list[float] = Field(..., description="High prices (list)")
    low: list[float] = Field(..., description="Low prices (list)")
    close: list[float] = Field(..., description="Close prices (list)")
    volume: list[int] = Field(..., description="Volumes (list)")
    strategy_id: Optional[int] = Field(None, description="Strategy ID to use")


@router.get("/", response_model=list[SignalResponse])
async def list_signals(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    status: Optional[SignalStatus] = Query(None, description="Filter by status"),
    signal_type: Optional[SignalType] = Query(None, description="Filter by signal type"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db)
):
    """List signals with optional filters."""
    service = SignalService(db)
    
    query = db.query(Signal)
    
    if symbol:
        query = query.filter(Signal.symbol == symbol.upper())
    if status:
        query = query.filter(Signal.status == status)
    if signal_type:
        query = query.filter(Signal.signal_type == signal_type)
    
    signals = query.order_by(Signal.generated_at.desc()).limit(limit).all()
    return signals


@router.get("/active", response_model=list[SignalResponse])
async def get_active_signals(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    db: Session = Depends(get_db)
):
    """Get all active signals."""
    service = SignalService(db)
    signals = service.get_active_signals(symbol)
    return signals


@router.get("/stats", response_model=SignalStatsResponse)
async def get_signal_stats(db: Session = Depends(get_db)):
    """Get signal statistics."""
    service = SignalService(db)
    stats = service.get_signal_stats()
    return stats


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(signal_id: int, db: Session = Depends(get_db)):
    """Get a specific signal by ID."""
    service = SignalService(db)
    signal = service.get_signal_by_id(signal_id)
    
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    return signal


@router.post("/generate", response_model=SignalResponse)
async def generate_signal(request: OHLCVRequest, db: Session = Depends(get_db)):
    """Generate a signal from OHLCV data using Gen 3.1 algorithm."""
    from domains.search.stock import Stock
    
    # Validate data
    if len(request.high) < 20:
        raise HTTPException(status_code=400, detail="Need at least 20 data points")
    
    if not (len(request.high) == len(request.low) == len(request.close) == len(request.volume)):
        raise HTTPException(status_code=400, detail="OHLCV arrays must be same length")
    
    # Get or create stock
    stock = db.query(Stock).filter(Stock.symbol == request.symbol.upper()).first()
    if not stock:
        # Create basic stock entry
        stock = Stock(
            symbol=request.symbol.upper(),
            name=request.symbol.upper(),
            exchange="UNKNOWN",
            current_price=request.close[-1]
        )
        db.add(stock)
        db.commit()
        db.refresh(stock)
    
    # Generate signal
    service = SignalService(db)
    signal = service.create_signal_from_ohlcv(
        stock=stock,
        high=request.high,
        low=request.low,
        close=request.close,
        volume=request.volume,
        strategy_id=request.strategy_id
    )
    
    if not signal:
        raise HTTPException(status_code=400, detail="No signal generated from data")
    
    return signal


@router.post("/", response_model=SignalResponse)
async def create_signal(
    signal_data: SignalCreate,
    db: Session = Depends(get_db)
):
    """Create a signal manually."""
    signal = Signal(
        stock_id=signal_data.stock_id,
        signal_type=signal_data.signal_type,
        status=SignalStatus.PENDING,
        entry_price=signal_data.entry_price,
        stop_loss=signal_data.stop_loss,
        take_profit_1=signal_data.take_profit_1,
        take_profit_2=signal_data.take_profit_2,
        take_profit_3=signal_data.take_profit_3,
        reasoning=signal_data.reasoning
    )
    
    db.add(signal)
    db.commit()
    db.refresh(signal)
    
    return signal


@router.patch("/{signal_id}", response_model=SignalResponse)
async def update_signal(
    signal_id: int,
    updates: SignalUpdate,
    db: Session = Depends(get_db)
):
    """Update a signal."""
    service = SignalService(db)
    signal = service.get_signal_by_id(signal_id)
    
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    if updates.status is not None:
        signal.status = updates.status
    if updates.stop_loss is not None:
        signal.stop_loss = updates.stop_loss
    if updates.take_profit_1 is not None:
        signal.take_profit_1 = updates.take_profit_1
    if updates.take_profit_2 is not None:
        signal.take_profit_2 = updates.take_profit_2
    if updates.take_profit_3 is not None:
        signal.take_profit_3 = updates.take_profit_3
    
    db.commit()
    db.refresh(signal)
    
    return signal


@router.post("/{signal_id}/trigger", response_model=SignalResponse)
async def trigger_signal(signal_id: int, db: Session = Depends(get_db)):
    """Mark a signal as triggered."""
    service = SignalService(db)
    signal = service.trigger_signal(signal_id)
    
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    return signal


@router.post("/{signal_id}/expire", response_model=SignalResponse)
async def expire_signal(signal_id: int, db: Session = Depends(get_db)):
    """Mark a signal as expired."""
    service = SignalService(db)
    signal = service.expire_signal(signal_id)
    
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    return signal


@router.post("/{signal_id}/cancel", response_model=SignalResponse)
async def cancel_signal(signal_id: int, db: Session = Depends(get_db)):
    """Cancel a signal."""
    service = SignalService(db)
    signal = service.cancel_signal(signal_id)
    
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    return signal


@router.get("/history/range")
async def get_signals_by_date(
    start_date: str = Query(..., description="Start date (ISO format)"),
    end_date: str = Query(..., description="End date (ISO format)"),
    signal_type: Optional[SignalType] = Query(None),
    db: Session = Depends(get_db)
):
    """Get signals within a date range."""
    try:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    service = SignalService(db)
    signals = service.get_signals_by_date_range(start, end, signal_type)
    
    return signals
