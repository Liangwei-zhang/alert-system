"""
Email worker - Send email notifications via Celery tasks.
"""
import logging
from typing import Optional
from dataclasses import dataclass

from celery import shared_task
from sqlalchemy.orm import Session

from infra.database import get_db_session
from domains.auth.user import User

logger = logging.getLogger(__name__)


@dataclass
class EmailResult:
    """Result of an email send operation."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    provider: str = "unknown"


class EmailWorker:
    """Worker for sending email notifications."""

    def __init__(self, session: Optional[Session] = None):
        self._session = session

    @property
    def session(self) -> Session:
        """Get database session."""
        if self._session is None:
            self._session = next(get_db_session())
        return self._session

    def get_user_email(self, user_id: int) -> Optional[tuple[str, str]]:
        """Get user email and name."""
        user = self.session.query(User).filter(User.id == user_id).first()
        if user:
            return (user.email, user.name or user.username)
        return None

    def send_signal_email(
        self,
        user_id: int,
        signal_type: str,
        symbol: str,
        price: float,
        message_id: Optional[int] = None,
    ) -> EmailResult:
        """Send signal alert email to user."""
        try:
            user_info = self.get_user_email(user_id)
            if not user_info:
                return EmailResult(
                    success=False,
                    error=f"User {user_id} not found",
                    provider="none",
                )

            email, name = user_info

            # Import and use email service
            from app.services.email_service import email_service, EmailRecipient
            import asyncio

            # Run async email service synchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    email_service.send_signal_alert(
                        recipient=EmailRecipient(email=email, name=name),
                        signal_type=signal_type,
                        symbol=symbol,
                        price=price,
                    )
                )
            finally:
                loop.close()

            if result:
                logger.info(
                    f"Signal email sent: user={user_id}, type={signal_type}, symbol={symbol}"
                )
                return EmailResult(success=True, provider=email_service.provider)
            else:
                return EmailResult(
                    success=False, error="Email service returned false", provider=email_service.provider
                )

        except Exception as e:
            logger.error(f"Error sending signal email: {e}")
            return EmailResult(success=False, error=str(e), provider="error")

    def send_price_alert_email(
        self,
        user_id: int,
        symbol: str,
        current_price: float,
        target_price: float,
        message_id: Optional[int] = None,
    ) -> EmailResult:
        """Send price alert email to user."""
        try:
            user_info = self.get_user_email(user_id)
            if not user_info:
                return EmailResult(
                    success=False,
                    error=f"User {user_id} not found",
                    provider="none",
                )

            email, name = user_info

            # Build email content
            direction = "above" if current_price >= target_price else "below"
            
            subject = f"🔔 Price Alert: {symbol} hit ${current_price:.2f}"
            
            html_body = f"""
            <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto;">
                <div style="background: #f8f9fa; border-radius: 12px; padding: 24px;">
                    <div style="font-size: 48px; text-align: center; margin-bottom: 16px;">🔔</div>
                    <h1 style="color: #1a1a2e; margin: 0 0 16px 0; font-size: 24px; text-align: center;">
                        Price Alert: {symbol}
                    </h1>
                    <div style="background: white; border-radius: 8px; padding: 20px; margin: 16px 0;">
                        <p style="color: #666; margin: 0 0 12px 0;">Symbol: <strong>{symbol}</strong></p>
                        <p style="color: #666; margin: 0 0 12px 0;">Current Price: <strong>${current_price:.2f}</strong></p>
                        <p style="color: #666; margin: 0;">Target Price: <strong>${target_price:.2f}</strong></p>
                        <p style="color: #28a745; margin: 12px 0 0 0;">Current price is {direction} your target!</p>
                    </div>
                    <p style="color: #999; font-size: 12px; text-align: center; margin: 20px 0 0 0;">
                        This is an automated price alert from StockPy.<br>
                        Log in to your dashboard to manage alerts.
                    </p>
                </div>
            </body>
            </html>
            """
            
            text_body = f"""
Price Alert: {symbol}

Symbol: {symbol}
Current Price: ${current_price:.2f}
Target Price: ${target_price:.2f}

Current price is {direction} your target!

This is an automated price alert from StockPy.
Log in to your dashboard to manage alerts.
            """

            # Send email
            from app.services.email_service import email_service, EmailRecipient
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    email_service.send_email(
                        recipient=EmailRecipient(email=email, name=name),
                        subject=subject,
                        html_body=html_body,
                        text_body=text_body,
                    )
                )
            finally:
                loop.close()

            if result:
                logger.info(
                    f"Price alert email sent: user={user_id}, symbol={symbol}"
                )
                return EmailResult(success=True, provider=email_service.provider)
            else:
                return EmailResult(
                    success=False, error="Email service returned false", provider=email_service.provider
                )

        except Exception as e:
            logger.error(f"Error sending price alert email: {e}")
            return EmailResult(success=False, error=str(e), provider="error")

    def send_welcome_email(self, user_id: int) -> EmailResult:
        """Send welcome email to new user."""
        try:
            user_info = self.get_user_email(user_id)
            if not user_info:
                return EmailResult(
                    success=False,
                    error=f"User {user_id} not found",
                    provider="none",
                )

            email, name = user_info

            subject = "Welcome to StockPy! 📈"
            
            html_body = f"""
            <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto;">
                <div style="background: #f8f9fa; border-radius: 12px; padding: 24px;">
                    <div style="font-size: 48px; text-align: center; margin-bottom: 16px;">🎉</div>
                    <h1 style="color: #1a1a2e; margin: 0 0 16px 0; font-size: 24px; text-align: center;">
                        Welcome to StockPy, {name}!
                    </h1>
                    <div style="background: white; border-radius: 8px; padding: 20px; margin: 16px 0;">
                        <p style="color: #666; margin: 0;">Thank you for joining StockPy. Start tracking your favorite stocks and receive real-time alerts!</p>
                    </div>
                    <p style="color: #999; font-size: 12px; text-align: center; margin: 20px 0 0 0;">
                        Need help? Reply to this email or visit our docs.<br>
                        - The StockPy Team
                    </p>
                </div>
            </body>
            </html>
            """
            
            text_body = f"""
Welcome to StockPy, {name}!

Thank you for joining StockPy. Start tracking your favorite stocks and receive real-time alerts!

Need help? Reply to this email or visit our docs.
- The StockPy Team
            """

            from app.services.email_service import email_service, EmailRecipient
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    email_service.send_email(
                        recipient=EmailRecipient(email=email, name=name),
                        subject=subject,
                        html_body=html_body,
                        text_body=text_body,
                    )
                )
            finally:
                loop.close()

            return EmailResult(success=result, provider=email_service.provider)

        except Exception as e:
            logger.error(f"Error sending welcome email: {e}")
            return EmailResult(success=False, error=str(e), provider="error")


# =============================================================================
# Celery Tasks
# =============================================================================

@shared_task(
    name="email.send_signal",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def send_signal_email_task(
    self,
    user_id: int,
    signal_type: str,
    symbol: str,
    price: float,
    message_id: Optional[int] = None,
) -> dict:
    """
    Celery task to send signal alert email.
    
    Args:
        user_id: User ID to send email to
        signal_type: Type of signal (buy, sell, split_buy, split_sell)
        symbol: Stock symbol
        price: Current price
        message_id: Optional notification message ID for tracking
    
    Returns:
        dict with success status and details
    """
    logger.info(
        f"Sending signal email task: user={user_id}, type={signal_type}, symbol={symbol}"
    )

    worker = EmailWorker()
    result = worker.send_signal_email(
        user_id=user_id,
        signal_type=signal_type,
        symbol=symbol,
        price=price,
        message_id=message_id,
    )

    if not result.success:
        # Raise exception to trigger retry
        raise Exception(result.error or "Email send failed")

    return {
        "success": True,
        "user_id": user_id,
        "signal_type": signal_type,
        "symbol": symbol,
        "provider": result.provider,
    }


@shared_task(
    name="email.send_price_alert",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def send_price_alert_email_task(
    self,
    user_id: int,
    symbol: str,
    current_price: float,
    target_price: float,
    message_id: Optional[int] = None,
) -> dict:
    """
    Celery task to send price alert email.
    
    Args:
        user_id: User ID to send email to
        symbol: Stock symbol
        current_price: Current stock price
        target_price: Target price that was set
        message_id: Optional notification message ID for tracking
    
    Returns:
        dict with success status and details
    """
    logger.info(
        f"Sending price alert email: user={user_id}, symbol={symbol}, price={current_price}"
    )

    worker = EmailWorker()
    result = worker.send_price_alert_email(
        user_id=user_id,
        symbol=symbol,
        current_price=current_price,
        target_price=target_price,
        message_id=message_id,
    )

    if not result.success:
        raise Exception(result.error or "Price alert email failed")

    return {
        "success": True,
        "user_id": user_id,
        "symbol": symbol,
        "provider": result.provider,
    }


@shared_task(
    name="email.send_welcome",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def send_welcome_email_task(self, user_id: int) -> dict:
    """
    Celery task to send welcome email to new user.
    
    Args:
        user_id: User ID to send welcome email to
    
    Returns:
        dict with success status and details
    """
    logger.info(f"Sending welcome email: user={user_id}")

    worker = EmailWorker()
    result = worker.send_welcome_email(user_id=user_id)

    if not result.success:
        raise Exception(result.error or "Welcome email failed")

    return {
        "success": True,
        "user_id": user_id,
        "provider": result.provider,
    }


@shared_task(
    name="email.batch_send",
    bind=True,
)
def batch_send_emails(self, emails: list[dict]) -> dict:
    """
    Celery task to send multiple emails in batch.
    
    Args:
        emails: List of email configs with keys: user_id, subject, html_body, text_body
    
    Returns:
        dict with success/failure counts
    """
    logger.info(f"Batch sending {len(emails)} emails")

    worker = EmailWorker()
    success_count = 0
    failed_count = 0

    for email_config in emails:
        try:
            result = worker.send_email(
                user_id=email_config["user_id"],
                subject=email_config["subject"],
                html_body=email_config.get("html_body", ""),
                text_body=email_config.get("text_body", ""),
            )
            if result.success:
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"Batch email error: {e}")
            failed_count += 1

    return {
        "total": len(emails),
        "success": success_count,
        "failed": failed_count,
    }


def send_email(
    user_id: int,
    subject: str,
    html_body: str,
    text_body: str,
) -> EmailResult:
    """
    Synchronous helper to send an email.
    
    Used for immediate sends (not queued).
    """
    worker = EmailWorker()
    return worker.send_email(
        user_id=user_id,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )