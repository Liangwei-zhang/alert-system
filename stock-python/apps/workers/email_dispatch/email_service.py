"""
Email notification service with SES/Resend fallback.
"""
import logging
from typing import Optional
from dataclasses import dataclass

from infra.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmailRecipient:
    """Email recipient."""
    email: str
    name: Optional[str] = None


@dataclass
class EmailContent:
    """Email content."""
    subject: str
    html_body: str
    text_body: str


class EmailService:
    """Email notification service with multiple provider support."""

    def __init__(self):
        self.provider = self._detect_provider()

    def _detect_provider(self) -> str:
        """Detect available email provider."""
        # Priority: Resend > SES > Console (dev)
        if settings.RESEND_API_KEY:
            return "resend"
        elif settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            return "ses"
        else:
            return "console"

    async def send_signal_alert(
        self,
        recipient: EmailRecipient,
        signal_type: str,
        symbol: str,
        price: float,
    ) -> bool:
        """Send signal alert email."""
        signal_titles = {
            "buy": f"📈 Buy Signal: {symbol}",
            "sell": f"📉 Sell Signal: {symbol}",
            "split_buy": f"🔄 Split Buy Signal: {symbol}",
            "split_sell": f"🔄 Split Sell Signal: {symbol}",
        }
        
        signal_emojis = {
            "buy": "📈",
            "sell": "📉",
            "split_buy": "🔄",
            "split_sell": "🔄",
        }

        subject = signal_titles.get(signal_type, f"Signal Alert: {symbol}")
        
        html_body = f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto;">
            <div style="background: #f8f9fa; border-radius: 12px; padding: 24px;">
                <div style="font-size: 48px; text-align: center; margin-bottom: 16px;">
                    {signal_emojis.get(signal_type, "📊")}
                </div>
                <h1 style="color: #1a1a2e; margin: 0 0 16px 0; font-size: 24px; text-align: center;">
                    {subject}
                </h1>
                <div style="background: white; border-radius: 8px; padding: 20px; margin: 16px 0;">
                    <p style="color: #666; margin: 0 0 12px 0;">Symbol: <strong>{symbol}</strong></p>
                    <p style="color: #666; margin: 0;">Price: <strong>${price:.2f}</strong></p>
                </div>
                <p style="color: #999; font-size: 12px; text-align: center; margin: 20px 0 0 0;">
                    This is an automated signal notification from StockPy.<br>
                    Log in to your dashboard for more details.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
{subject}

Symbol: {symbol}
Price: ${price:.2f}

This is an automated signal notification from StockPy.
Log in to your dashboard for more details.
        """

        return await self.send_email(
            recipient=recipient,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    async def send_email(
        self,
        recipient: EmailRecipient,
        subject: str,
        html_body: str,
        text_body: str,
        from_email: Optional[str] = None,
    ) -> bool:
        """Send an email."""
        if self.provider == "resend":
            return await self._send_via_resend(
                recipient=recipient,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                from_email=from_email,
            )
        elif self.provider == "ses":
            return await self._send_via_ses(
                recipient=recipient,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
        else:
            return await self._send_via_console(
                recipient=recipient,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )

    async def _send_via_resend(
        self,
        recipient: EmailRecipient,
        subject: str,
        html_body: str,
        text_body: str,
        from_email: Optional[str] = None,
    ) -> bool:
        """Send email via Resend."""
        try:
            import resend
            resend.api_key = settings.RESEND_API_KEY
            
            from_name = settings.EMAIL_FROM_NAME or "StockPy"
            sender = from_email or settings.EMAIL_FROM or f"StockPy <notifications@resend.dev>"
            
            params = {
                "from": sender,
                "to": recipient.email,
                "subject": subject,
                "html": html_body,
                "text": text_body,
            }
            
            response = resend.Emails.send(params)
            logger.info(f"Email sent via Resend to {recipient.email}: {response}")
            return True
        except Exception as e:
            logger.error(f"Resend email failed: {e}")
            # Fall back to console
            return await self._send_via_console(recipient, subject, html_body, text_body)

    async def _send_via_ses(
        self,
        recipient: EmailRecipient,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> bool:
        """Send email via AWS SES."""
        try:
            import boto3
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            client = boto3.client(
                "ses",
                region_name=settings.AWS_REGION or "us-east-1",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.EMAIL_FROM or "StockPy <noreply@stockpy.com>"
            msg["To"] = recipient.email
            
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
            
            response = client.send_raw_email(
                Source=msg["From"],
                Destinations=[recipient.email],
                RawMessage={"Data": msg.as_string()},
            )
            
            logger.info(f"Email sent via SES to {recipient.email}: {response}")
            return True
        except Exception as e:
            logger.error(f"SES email failed: {e}")
            # Fall back to console
            return await self._send_via_console(recipient, subject, html_body, text_body)

    async def _send_via_console(
        self,
        recipient: EmailRecipient,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> bool:
        """Log email to console (for development)."""
        logger.info(f"""
========== EMAIL (Console/Dev) ==========
To: {recipient.email}
Subject: {subject}

{text_body}
=========================================
        """)
        return True


# Global email service instance
email_service = EmailService()
