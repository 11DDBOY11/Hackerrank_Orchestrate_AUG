"""
Business Intelligence Module for the WhatsApp Notification Router.

Classifies business accounts, verifies official domains, and categorizes messages
into transactional, authentication, operational updates, vs promotional marketing.
"""

from __future__ import annotations

import re
from typing import Optional

from data.models import BusinessAccount, BusinessContext, Message, UserBusinessHistory


class BusinessIntelligenceEngine:
    """Enriches business context and categorizes business messages."""

    def analyze(
        self,
        message: Message,
        business: Optional[BusinessAccount],
        user_biz_history: Optional[UserBusinessHistory],
    ) -> BusinessContext:
        if not business or not message.business_id:
            return BusinessContext()

        is_verified = business.verified
        is_domain_legitimate = True
        if business.official_domain and business.domain_used_by_sender:
            is_domain_legitimate = business.official_domain.lower() == business.domain_used_by_sender.lower()

        business_category = business.category or "general"
        
        # Categorize message type
        text_lower = (message.message_text or "").lower()
        
        # Check for transactional / authentication vs marketing
        if any(kw in text_lower for kw in ["otp", "verification code", "login code", "security update"]):
            message_category = "authentication"
        elif any(kw in text_lower for kw in ["order ending", "packed", "shipped", "out for delivery", "pickup code", "refund", "pickup today", "statement ready", "appointment"]):
            message_category = "transactional"
        elif any(kw in text_lower for kw in ["off", "discount", "sale", "coupon", "limited offer", "book now", "tour package", "try50", "unsubscribe"]):
            message_category = "marketing"
        else:
            message_category = "general_update"

        return BusinessContext(
            business=business,
            user_history=user_biz_history,
            is_verified=is_verified,
            is_domain_legitimate=is_domain_legitimate,
            business_category=business_category,
            message_category=message_category,
        )
