"""
Template service - Dynamic notification templates with variable substitution.
"""
import logging
from typing import Any
from datetime import datetime
import re

from domains.notifications.notification import NotificationType, NotificationPriority

logger = logging.getLogger(__name__)


class TemplateEngine:
    """Dynamic template engine for notifications."""

    # Template registry: notification_type -> template config
    TEMPLATES = {
        NotificationType.SIGNAL_BUY: {
            "title": "📈 Buy Signal: {symbol}",
            "message": "Buy signal triggered for {symbol} at ${price:.2f}. Confidence: {confidence}%. {additional_info}",
            "default_priority": NotificationPriority.HIGH,
        },
        NotificationType.SIGNAL_SELL: {
            "title": "📉 Sell Signal: {symbol}",
            "message": "Sell signal triggered for {symbol} at ${price:.2f}. Confidence: {confidence}%. {additional_info}",
            "default_priority": NotificationPriority.HIGH,
        },
        NotificationType.SIGNAL_SPLIT_BUY: {
            "title": "🔄 Split Buy: {symbol}",
            "message": "Split buy signal for {symbol}. Old: {old_shares}→{new_shares} shares at ${price:.2f}. {additional_info}",
            "default_priority": NotificationPriority.NORMAL,
        },
        NotificationType.SIGNAL_SPLIT_SELL: {
            "title": "🔄 Split Sell: {symbol}",
            "message": "Split sell signal for {symbol}. Old: {old_shares}→{new_shares} shares at ${price:.2f}. {additional_info}",
            "default_priority": NotificationPriority.NORMAL,
        },
        NotificationType.PRICE_ALERT: {
            "title": "🔔 Price Alert: {symbol}",
            "message": "{symbol} has reached ${price:.2f} ({direction} {percent_change:.1f}%). {additional_info}",
            "default_priority": NotificationPriority.NORMAL,
        },
        NotificationType.SYSTEM: {
            "title": "⚙️ System: {title}",
            "message": "{message}",
            "default_priority": NotificationPriority.LOW,
        },
    }

    # Variable pattern: {variable_name}
    VAR_PATTERN = re.compile(r'\{(\w+)\}')

    def __init__(self):
        self._custom_templates: dict[str, dict] = {}

    def register_template(self, notification_type: str, template: dict) -> None:
        """Register a custom template."""
        self._custom_templates[notification_type] = template
        logger.info(f"Registered custom template for {notification_type}")

    def render(
        self,
        notification_type: NotificationType,
        context: dict[str, Any],
    ) -> tuple[str, str, NotificationPriority]:
        """
        Render a template with the given context.
        
        Returns: (title, message, priority)
        """
        # Get template (custom or default)
        template = self._custom_templates.get(
            notification_type.value,
            self.TEMPLATES.get(notification_type),
        )

        if not template:
            logger.warning(f"No template found for {notification_type}, using fallback")
            return self._render_fallback(notification_type, context)

        try:
            title = template["title"].format(**context)
            message = template["message"].format(**context)
            priority = template.get("default_priority", NotificationPriority.NORMAL)
        except KeyError as e:
            logger.warning(f"Missing template variable {e}, using fallback")
            return self._render_fallback(notification_type, context)

        return title, message, priority

    def _render_fallback(
        self,
        notification_type: NotificationType,
        context: dict[str, Any],
    ) -> tuple[str, str, NotificationPriority]:
        """Render a fallback template when no template is found."""
        title = f"Notification: {notification_type.value}"
        message = " ".join(f"{k}={v}" for k, v in context.items() if v)
        return title, message, NotificationPriority.NORMAL

    def get_required_variables(self, notification_type: NotificationType) -> list[str]:
        """Get list of required variables for a template."""
        template = self._custom_templates.get(
            notification_type.value,
            self.TEMPLATES.get(notification_type),
        )
        if not template:
            return []

        variables = set()
        for field in ["title", "message"]:
            variables.update(self.VAR_PATTERN.findall(template.get(field, "")))

        return sorted(variables)

    def validate_context(
        self,
        notification_type: NotificationType,
        context: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """Validate that context has all required variables."""
        required = self.get_required_variables(notification_type)
        missing = [var for var in required if var not in context or context[var] is None]
        return len(missing) == 0, missing


class TemplateService:
    """Service for managing notification templates."""

    def __init__(self, template_engine: TemplateEngine = None):
        self.engine = template_engine or TemplateEngine()

    def create_from_context(
        self,
        notification_type: NotificationType,
        context: dict[str, Any],
        priority: NotificationPriority = None,
    ) -> tuple[str, str, NotificationPriority]:
        """Create notification content from context."""
        title, message, default_priority = self.engine.render(notification_type, context)
        final_priority = priority or default_priority
        return title, message, final_priority

    def create_signal_notification(
        self,
        signal_type: str,
        symbol: str,
        price: float,
        confidence: float = 0.0,
        additional_info: str = "",
    ) -> tuple[str, str, NotificationPriority]:
        """Create signal notification content."""
        type_map = {
            "buy": NotificationType.SIGNAL_BUY,
            "sell": NotificationType.SIGNAL_SELL,
            "split_buy": NotificationType.SIGNAL_SPLIT_BUY,
            "split_sell": NotificationType.SIGNAL_SPLIT_SELL,
        }

        notification_type = type_map.get(signal_type, NotificationType.SIGNAL_BUY)

        context = {
            "symbol": symbol,
            "price": price,
            "confidence": confidence,
            "additional_info": additional_info or "No additional info",
        }

        return self.create_from_context(notification_type, context)

    def create_price_alert(
        self,
        symbol: str,
        price: float,
        direction: str,  # "up" or "down"
        percent_change: float,
        additional_info: str = "",
    ) -> tuple[str, str, NotificationPriority]:
        """Create price alert notification content."""
        context = {
            "symbol": symbol,
            "price": price,
            "direction": direction,
            "percent_change": percent_change,
            "additional_info": additional_info or "",
        }

        return self.create_from_context(NotificationType.PRICE_ALERT, context)

    def create_system_notification(
        self,
        title: str,
        message: str,
    ) -> tuple[str, str, NotificationPriority]:
        """Create system notification content."""
        context = {
            "title": title,
            "message": message,
        }

        return self.create_from_context(NotificationType.SYSTEM, context)


# Global instance
template_service = TemplateService()