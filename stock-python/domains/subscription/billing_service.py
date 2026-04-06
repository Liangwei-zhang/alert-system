"""
Billing service for subscription payment integration.
Placeholder for Stripe/payment provider integration.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.subscription.subscription import Subscription, SubscriptionTier, SubscriptionStatus
from domains.auth.user import User


class PaymentProvider(str, Enum):
    """Payment providers."""
    STRIPE = "stripe"
    PLAID = "plaid"


class PaymentStatus(str, Enum):
    """Payment status."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class BillingService:
    """
    Billing service for payment integration.
    
    This is a placeholder that provides the interface for payment integration.
    In production, implement actual Stripe/Payment provider calls.
    """

    # Default prices (in cents)
    PRICES = {
        SubscriptionTier.FREE: {"monthly": 0, "yearly": 0},
        SubscriptionTier.BASIC: {"monthly": 999, "yearly": 9990},  # $9.99/mo
        SubscriptionTier.PRO: {"monthly": 2999, "yearly": 29990},  # $29.99/mo
        SubscriptionTier.ENTERPRISE: {"monthly": 9999, "yearly": 99990},  # $99.99/mo
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============== Customer Management ==============

    async def create_customer(
        self, user_id: int, email: str, name: Optional[str] = None
    ) -> str:
        """
        Create a customer in the payment provider.
        Returns customer ID.
        
        Placeholder - implement Stripe customer creation in production.
        """
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("User not found")

        # In production: stripe_customer = stripe.Customer.create(email=email, name=name)
        # Placeholder: generate a fake customer ID
        customer_id = f"cus_placeholder_{user_id}_{datetime.utcnow().timestamp()}"
        
        # Store in subscription
        subscription = await self._get_user_subscription(user_id)
        if subscription:
            subscription.stripe_customer_id = customer_id
            await self.db.commit()

        return customer_id

    async def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """
        Get customer details from payment provider.
        
        Placeholder - implement Stripe customer retrieval in production.
        """
        # In production: return stripe.Customer.retrieve(customer_id)
        return {
            "id": customer_id,
            "email": "user@example.com",
            "name": "User Name",
            "created": datetime.utcnow().isoformat(),
        }

    async def update_customer(
        self, customer_id: str, email: Optional[str] = None, name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update customer in payment provider."""
        # In production: stripe.Customer.modify(customer_id, email=email, name=name)
        return {"id": customer_id, "email": email, "name": name}

    # ============== Subscription Management ==============

    async def create_subscription(
        self,
        user_id: int,
        tier: SubscriptionTier,
        payment_method_id: str,
        is_trial: bool = False,
        billing_cycle: str = "monthly",
    ) -> Dict[str, Any]:
        """
        Create a subscription in the payment provider.
        
        Args:
            user_id: User ID
            tier: Subscription tier
            payment_method_id: Payment method token from Stripe
            is_trial: Whether to use trial period
            billing_cycle: 'monthly' or 'yearly'
        
        Returns:
            Dict with subscription details
        """
        subscription = await self._get_user_subscription(user_id)
        
        if not subscription:
            raise ValueError("User has no subscription")

        # Get price
        price = self.PRICES[tier][billing_cycle]
        
        # In production:
        # stripe_sub = stripe.Subscription.create(
        #     customer=subscription.stripe_customer_id,
        #     items=[{"price": price_id}],
        #     default_payment_method=payment_method_id,
        #     trial_period_days=14 if is_trial else None,
        # )
        
        # Placeholder response
        subscription_id = f"sub_placeholder_{user_id}_{datetime.utcnow().timestamp()}"
        
        # Update subscription with Stripe ID
        subscription.stripe_subscription_id = subscription_id
        await self.db.commit()

        return {
            "id": subscription_id,
            "status": "active" if not is_trial else "trialing",
            "current_period_start": datetime.utcnow().isoformat(),
            "current_period_end": (
                datetime.utcnow() + timedelta(days=14)
                if is_trial
                else datetime.utcnow() + (
                    timedelta(days=365) if billing_cycle == "yearly" else timedelta(days=30)
                )
            ).isoformat(),
            "plan": tier.value,
            "billing_cycle": billing_cycle,
        }

    async def get_subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get subscription details from payment provider."""
        # In production: return stripe.Subscription.retrieve(subscription_id)
        return {
            "id": subscription_id,
            "status": "active",
            "current_period_end": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        }

    async def update_subscription(
        self,
        subscription_id: str,
        new_tier: Optional[SubscriptionTier] = None,
        billing_cycle: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update subscription (upgrade/downgrade, change billing cycle).
        """
        # In production:
        # if new_tier:
        #     stripe.Subscription.modify(subscription_id, items=[...])
        
        return {
            "id": subscription_id,
            "status": "active",
            "plan": new_tier.value if new_tier else "pro",
        }

    async def cancel_subscription(
        self,
        subscription_id: str,
        immediately: bool = False,
    ) -> bool:
        """
        Cancel subscription.
        
        Args:
            subscription_id: Stripe subscription ID
            immediately: If True, cancel immediately; if False, cancel at period end
        """
        # In production:
        # if immediately:
        #     stripe.Subscription.cancel(subscription_id)
        # else:
        #     stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        
        return True

    async def reactivate_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Reactivate a cancelled subscription."""
        # In production: stripe.Subscription.modify(subscription_id, cancel_at_period_end=False)
        return {
            "id": subscription_id,
            "status": "active",
        }

    # ============== Payment Methods ==============

    async def add_payment_method(
        self, customer_id: str, payment_method_token: str
    ) -> str:
        """Add a payment method for a customer."""
        # In production:
        # pm = stripe.PaymentMethod.attach(payment_method_token, customer=customer_id)
        # stripe.Customer.modify(customer_id, invoice_settings={"default_payment_method": pm.id})
        
        return f"pm_placeholder_{payment_method_token}"

    async def remove_payment_method(self, payment_method_id: str) -> bool:
        """Remove a payment method."""
        # In production: stripe.PaymentMethod.detach(payment_method_id)
        return True

    async def get_payment_methods(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get customer's payment methods."""
        # In production: stripe.PaymentMethod.list(customer=customer_id, type="card")
        return []

    async def set_default_payment_method(
        self, customer_id: str, payment_method_id: str
    ) -> bool:
        """Set default payment method for customer."""
        # In production: stripe.Customer.modify(customer_id, invoice_settings={"default_payment_method": payment_method_id})
        return True

    # ============== Invoices ==============

    async def get_invoices(
        self, customer_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get customer invoices."""
        # In production: stripe.Invoice.list(customer=customer_id, limit=limit)
        return []

    async def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Get invoice details."""
        # In production: return stripe.Invoice.retrieve(invoice_id)
        return None

    async def create_invoice_for_subscription(
        self, subscription_id: str
    ) -> str:
        """Create and finalize an invoice for a subscription."""
        # In production: stripe.Invoice.create(customer=customer_id).finalize()
        return f"in_placeholder_{subscription_id}"

    # ============== Webhooks ==============

    async def handle_webhook(
        self, payload: bytes, signature: str
    ) -> Dict[str, Any]:
        """
        Handle webhook events from payment provider.
        
        Placeholder - implement actual webhook handling in production.
        """
        # In production:
        # event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
        # 
        # switch event['type']:
        #     case 'invoice.payment_succeeded': ...
        #     case 'customer.subscription.updated': ...
        #     case 'customer.subscription.deleted': ...
        
        return {"status": "processed"}

    # ============== Helper Methods ==============

    async def _get_user_subscription(self, user_id: int) -> Optional[Subscription]:
        """Get user's subscription."""
        result = await self.db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        return result.scalar_one_or_none()

    def get_price(
        self, tier: SubscriptionTier, billing_cycle: str = "monthly"
    ) -> Dict[str, int]:
        """Get price for a tier and billing cycle."""
        return self.PRICES.get(tier, self.PRICES[SubscriptionTier.FREE])

    async def get_subscription_portal_url(
        self, customer_id: str
    ) -> str:
        """Get URL for customer to manage billing."""
        # In production:
        # session = stripe.billing_portal.sessions.create(customer=customer_id)
        # return session.url
        
        return "https://billing.stockapp.com/portal/placeholder"

    async def create_checkout_session(
        self,
        user_id: int,
        tier: SubscriptionTier,
        billing_cycle: str = "monthly",
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a Stripe checkout session for subscription.
        """
        subscription = await self._get_user_subscription(user_id)
        
        if not subscription:
            raise ValueError("User has no subscription")
        
        # In production:
        # session = stripe.checkout.Session.create(
        #     customer=subscription.stripe_customer_id,
        #     mode='subscription',
        #     line_items=[{'price': price_id, 'quantity': 1}],
        #     success_url=success_url,
        #     cancel_url=cancel_url,
        # )
        
        return {
            "id": f"cs_placeholder_{user_id}",
            "url": f"https://checkout.stockapp.com/cs_placeholder?-tier={tier.value}",
        }

    async def preview_pricing_change(
        self,
        current_tier: SubscriptionTier,
        new_tier: SubscriptionTier,
        billing_cycle: str = "monthly",
    ) -> Dict[str, Any]:
        """Preview pricing when changing tiers."""
        current_price = self.PRICES[current_tier][billing_cycle]
        new_price = self.PRICES[new_tier][billing_cycle]
        
        return {
            "current_tier": current_tier.value,
            "new_tier": new_tier.value,
            "current_price": current_price,
            "new_price": new_price,
            "proration": new_price - current_price,  # Simplified
            "billing_cycle": billing_cycle,
        }