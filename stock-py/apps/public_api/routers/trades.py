"""
Trade API router - public and app endpoints for trade confirmations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from domains.trades.html_renderer import TradeHtmlRenderer
from domains.trades.schemas import (
    AdjustResponse,
    AdjustTradeRequest,
    ConfirmResponse,
    IgnoreResponse,
    TradeInfoAppResponse,
    TradeInfoPublicResponse,
    TradeInfoResponse,
)
from domains.trades.service import TradeService
from infra.db.session import get_db_session
from infra.security.auth import CurrentUser, require_user

router = APIRouter(prefix="/trades", tags=["trades"])


# Helper models for HTML form responses
class TradeConfirmHtmlResponse(BaseModel):
    """HTML response for trade confirmation page."""

    content: str
    content_type: str = "text/html"


@router.get("/{trade_id}/info", response_model=TradeInfoPublicResponse, name="get_trade_info")
async def get_trade_info(
    trade_id: str,
    t: str = Query(..., description="Link token"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get trade info via public link.

    Requires link token for authentication.
    """
    service = TradeService(db)
    trade = await service.get_trade_info_by_id(trade_id)

    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade record not found")

    # Verify link token
    if not service.verify_link_token(trade, t):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid link token")

    return TradeInfoPublicResponse(
        trade=TradeInfoResponse(**service.serialize_trade(trade)),
        is_expired=service.is_expired(trade),
        expires_at=trade.expires_at,
    )


@router.get("/{trade_id}/app-info", response_model=TradeInfoAppResponse, name="get_trade_app_info")
async def get_trade_app_info(
    trade_id: str,
    current_user: CurrentUser = Depends(require_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get trade info via app (authenticated).

    Requires user authentication.
    """
    service = TradeService(db)
    trade = await service.get_trade_info_for_user(trade_id, current_user.user_id)

    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade record not found")

    return TradeInfoAppResponse(
        trade=TradeInfoResponse(**service.serialize_trade(trade)),
        is_expired=service.is_expired(trade),
        expires_at=trade.expires_at,
    )


@router.get(
    "/{trade_id}/confirm", response_model=TradeConfirmHtmlResponse, name="get_trade_confirm_page"
)
async def get_trade_confirm_page(
    trade_id: str,
    action: str = Query(..., pattern="^(accept|ignore)$"),
    t: str = Query(..., description="Link token"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get trade confirmation page (HTML) via public link.

    Renders the confirmation form for user interaction.
    """
    service = TradeService(db)
    trade = await service.get_trade_by_id(trade_id)

    if not trade:
        return TradeConfirmHtmlResponse(
            content=TradeHtmlRenderer.render_page("X", "Trade record not found")
        )

    # Check status
    if trade.status != "pending":
        return TradeConfirmHtmlResponse(
            content=TradeHtmlRenderer.render_page(
                "i",
                f"This suggestion is already {TradeHtmlRenderer.status_label(trade.status.value)} and does not need another action.",
            )
        )

    # Check expiration
    if service.is_expired(trade):
        return TradeConfirmHtmlResponse(
            content=TradeHtmlRenderer.render_page(
                "!", "This confirmation link has expired. Links are valid for 24 hours."
            )
        )

    # Verify token
    if not service.verify_link_token(trade, t):
        return TradeConfirmHtmlResponse(
            content=TradeHtmlRenderer.render_page(
                "!", "This link is invalid or no longer available."
            )
        )

    # Render confirmation page
    return TradeConfirmHtmlResponse(
        content=TradeHtmlRenderer.render_confirm_page(
            trade_id=trade_id,
            token=t,
            action=action,
            symbol=trade.symbol,
            trade_action=trade.action.value,
            suggested_shares=float(trade.suggested_shares),
            suggested_price=float(trade.suggested_price),
            suggested_amount=float(trade.suggested_amount),
        )
    )


@router.post("/{trade_id}/confirm", response_model=ConfirmResponse, name="confirm_trade")
async def confirm_trade(
    trade_id: str,
    action: str = Query(..., pattern="^(accept|ignore)$"),
    t: str = Query(..., description="Link token"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Confirm or ignore a trade via public link.

    Requires link token for authentication.
    """
    service = TradeService(db)
    trade = await service.get_trade_by_id(trade_id)

    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade record not found")

    if trade.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"This trade has already been processed"
        )

    if service.is_expired(trade):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This confirmation link has expired"
        )

    if not service.verify_link_token(trade, t):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid link token")

    if action == "ignore":
        await service.ignore_trade(trade)
        await service.acknowledge_receipts(trade)
        return ConfirmResponse(message="This suggestion has been ignored.")

    # Confirm with suggested values
    actual_amount = await service.confirm_trade(
        trade,
        actual_shares=float(trade.suggested_shares),
        actual_price=float(trade.suggested_price),
    )
    await service.acknowledge_receipts(trade)

    return ConfirmResponse(message="Confirmed. Your portfolio has been updated automatically.")


@router.post("/{trade_id}/ignore", response_model=IgnoreResponse, name="ignore_trade")
async def ignore_trade(
    trade_id: str,
    t: str = Query(..., description="Link token"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Ignore a trade via public link.

    Requires link token for authentication.
    """
    service = TradeService(db)
    trade = await service.get_trade_by_id(trade_id)

    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade record not found")

    if trade.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This trade has already been processed"
        )

    if service.is_expired(trade):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This link has expired")

    if not service.verify_link_token(trade, t):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid link token")

    await service.ignore_trade(trade)
    await service.acknowledge_receipts(trade)

    return IgnoreResponse(message="Trade ignored successfully")


@router.post("/{trade_id}/adjust", response_model=AdjustResponse, name="adjust_trade")
async def adjust_trade(
    trade_id: str,
    adjust_request: AdjustTradeRequest,
    t: str = Query(..., description="Link token"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Adjust and confirm a trade via public link.

    Allows changing the actual shares and price.
    Requires link token for authentication.
    """
    service = TradeService(db)
    trade = await service.get_trade_by_id(trade_id)

    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade record not found")

    if trade.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This trade has already been processed"
        )

    if service.is_expired(trade):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This link has expired")

    if not service.verify_link_token(trade, t):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid link token")

    actual_amount = await service.adjust_trade(
        trade, actual_shares=adjust_request.actual_shares, actual_price=adjust_request.actual_price
    )
    await service.acknowledge_receipts(trade)

    return AdjustResponse(message="Actual execution recorded", actual_amount=actual_amount)


@router.post("/{trade_id}/app-confirm", response_model=ConfirmResponse, name="app_confirm_trade")
async def app_confirm_trade(
    trade_id: str,
    current_user: CurrentUser = Depends(require_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Confirm a trade via app (authenticated).

    Uses suggested values from the trade.
    """
    service = TradeService(db)
    trade = await service.get_trade_for_user(trade_id, current_user.user_id)

    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade record not found")

    # Check availability
    unavailable_error = service.get_unavailable_error(trade)
    if unavailable_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=unavailable_error)

    actual_amount = await service.confirm_trade(
        trade,
        actual_shares=float(trade.suggested_shares),
        actual_price=float(trade.suggested_price),
    )
    await service.acknowledge_receipts(trade)

    return ConfirmResponse(message="Trade confirmed")


@router.post("/{trade_id}/app-ignore", response_model=IgnoreResponse, name="app_ignore_trade")
async def app_ignore_trade(
    trade_id: str,
    current_user: CurrentUser = Depends(require_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Ignore a trade via app (authenticated).
    """
    service = TradeService(db)
    trade = await service.get_trade_for_user(trade_id, current_user.user_id)

    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade record not found")

    # Check availability
    unavailable_error = service.get_unavailable_error(trade)
    if unavailable_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=unavailable_error)

    await service.ignore_trade(trade)
    await service.acknowledge_receipts(trade)

    return IgnoreResponse(message="Trade ignored")


@router.post("/{trade_id}/app-adjust", response_model=AdjustResponse, name="app_adjust_trade")
async def app_adjust_trade(
    trade_id: str,
    adjust_request: AdjustTradeRequest,
    current_user: CurrentUser = Depends(require_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Adjust and confirm a trade via app (authenticated).

    Allows changing the actual shares and price.
    """
    service = TradeService(db)
    trade = await service.get_trade_for_user(trade_id, current_user.user_id)

    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade record not found")

    # Check availability
    unavailable_error = service.get_unavailable_error(trade)
    if unavailable_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=unavailable_error)

    actual_amount = await service.adjust_trade(
        trade, actual_shares=adjust_request.actual_shares, actual_price=adjust_request.actual_price
    )
    await service.acknowledge_receipts(trade)

    return AdjustResponse(message="Actual execution recorded", actual_amount=actual_amount)
