# Signal Team Execution Guide

## Overview

The Signal Team handles trading signal generation, management, and the Gen 3.1 algorithm implementation.

## Responsibilities

- Trading signal creation and management
- Signal validation (SFP, CHOOCH, FVG)
- Signal status lifecycle (pending, triggered, expired, cancelled)
- OHLCV data processing for signal generation
- Signal statistics and distribution

## Current Status

### Completed Components

1. **Signal Models (domains/signals/)**
   - SignalType: BUY, SELL
   - SignalStatus: PENDING, TRIGGERED, EXPIRED, CANCELLED
   - Signal validation flags (sfp_validated, chooch_validated, fvg_validated)
   - Risk/reward ratio calculation

2. **Signal Service (domains/signals/signal_service.py)**
   - Signal CRUD operations
   - Active signal retrieval
   - Signal triggering
   - Signal expiration
   - Signal statistics

3. **Scanners (apps/workers/scanner/)**
   - Buy scanner for entry signals
   - Sell scanner for exit signals
   - Position engine for tracking

4. **Backtesting (apps/workers/backtest/backtest_service.py)**
   - Historical signal backtesting
   - Performance metrics

## Migration Tasks

### Phase 1: Signal Models

- [x] Define signal types and statuses
- [x] Implement validation flags
- [x] Add pricing levels (entry, stop loss, take profits)

### Phase 2: Signal Service

- [x] Create signal CRUD operations
- [x] Implement signal triggering
- [x] Implement signal expiration
- [x] Add signal statistics

### Phase 3: Signal Generation

- [x] OHLCV data processing
- [x] Gen 3.1 algorithm integration
- [x] Signal probability calculation

### Phase 4: Scanners

- [x] Buy scanner implementation
- [x] Sell scanner implementation
- [x] Position tracking engine

### Phase 5: Backtesting

- [x] Historical backtesting service
- [x] Performance metrics calculation

## API Endpoints

### Signal Endpoints (Public API)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/signals` | List signals with filters |
| GET | `/api/v1/signals/active` | Get active signals |
| GET | `/api/v1/signals/stats` | Get signal statistics |
| GET | `/api/v1/signals/{signal_id}` | Get signal by ID |
| POST | `/api/v1/signals` | Create signal manually |
| POST | `/api/v1/signals/generate` | Generate signal from OHLCV |
| PATCH | `/api/v1/signals/{signal_id}` | Update signal |
| POST | `/api/v1/signals/{signal_id}/trigger` | Trigger signal |
| POST | `/api/v1/signals/{signal_id}/expire` | Expire signal |
| POST | `/api/v1/signals/{signal_id}/cancel` | Cancel signal |
| GET | `/api/v1/signals/history/range` | Get signals by date range |

## Signal Lifecycle

```
PENDING → TRIGGERED (entry executed)
       → EXPIRED (not triggered in time)
       → CANCELLED (manually cancelled)
```

## Signal Validation

| Validation | Description |
|------------|-------------|
| SFP | Smart Money Concept - Fair Value Gap |
| CHOOCH | CHOOCH indicator confirmation |
| FVG | Fair Value Gap validation |

## Dependencies

- `domains/signals/signal.py` - Signal model
- `domains/signals/signal_service.py` - Signal service
- `domains/search/stock.py` - Stock model
- `apps/workers/scanner/` - Scanner workers
- `apps/workers/backtest/` - Backtesting worker

## Testing Strategy

1. Unit tests for signal service
2. Signal lifecycle tests
3. Validation algorithm tests
4. Backtesting validation tests

## Signal Data Model

```python
{
    "stock_id": int,
    "symbol": str,
    "signal_type": "BUY" | "SELL",
    "status": "PENDING" | "TRIGGERED" | "EXPIRED" | "CANCELLED",
    "entry_price": float,
    "stop_loss": float | None,
    "take_profit_1": float | None,
    "take_profit_2": float | None,
    "take_profit_3": float | None,
    "probability": float,
    "confidence": float,
    "risk_reward_ratio": float | None,
    "sfp_validated": bool,
    "chooch_validated": bool,
    "fvg_validated": bool,
    "atr_value": float | None,
    "atr_multiplier": float,
    "reasoning": str | None,
    "generated_at": datetime,
    "triggered_at": datetime | None,
    "expired_at": datetime | None
}
```

## Next Steps

1. Add more sophisticated signal algorithms
2. Implement signal clustering for similar signals
3. Add machine learning-based signal scoring
4. Enhance backtesting with portfolio-level metrics