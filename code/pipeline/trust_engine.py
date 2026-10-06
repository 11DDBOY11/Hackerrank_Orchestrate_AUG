"""
Sender Trust Engine for the WhatsApp Notification Router.

Calculates a 0-100 Trust Score for the sender based on relationship history,
shared groups, admin status, business domain verification, and historical interactions.
"""

from __future__ import annotations

from typing import Optional

from config.settings import settings
from data.models import (
    BusinessAccount,
    ConversationType,
    GroupMembership,
    Message,
    TrustScore,
    User,
    UserBusinessHistory,
)


class TrustEngine:
    """Calculates sender trust score and explainable trust factors."""

    def compute(
        self,
        message: Message,
        user: Optional[User],
        sender: Optional[User],
        membership: Optional[GroupMembership],
        business: Optional[BusinessAccount],
        user_biz_history: Optional[UserBusinessHistory],
        sender_messages_replied_count: int = 0,
    ) -> TrustScore:
        score = 50.0  # Base neutral score
        factors = {}
        reason_parts = []

        # -------------------------------------------------------------------
        # 1. Personal / User Sender
        # -------------------------------------------------------------------
        if message.conversation_type == ConversationType.PERSONAL or message.sender_user_id:
            if sender:
                factors["known_sender"] = True
                score += settings.trust_known_contact_bonus
                reason_parts.append("Sender is a known contact")

                # Did user reply to this sender in historical messages?
                if sender_messages_replied_count > 0:
                    score += min(20.0, sender_messages_replied_count * 5.0)
                    factors["previous_interactions"] = sender_messages_replied_count
                    reason_parts.append(f"User replied to sender {sender_messages_replied_count} times in history")
            else:
                factors["unknown_sender"] = True
                score -= 15.0
                reason_parts.append("Sender is an unfamiliar contact")

        # -------------------------------------------------------------------
        # 2. Group Sender Context
        # -------------------------------------------------------------------
        if message.conversation_type == ConversationType.GROUP and membership:
            if membership.role == "admin":
                score += settings.trust_admin_bonus
                factors["group_admin"] = True
                reason_parts.append("Sender is a verified group admin")
            
            if membership.messages_sent_30d > 10:
                score += 10.0
                factors["active_group_member"] = True

        # -------------------------------------------------------------------
        # 3. Business Sender Context
        # -------------------------------------------------------------------
        if message.conversation_type == ConversationType.BUSINESS or business:
            if business:
                factors["verified_business"] = business.verified
                factors["account_age_days"] = business.account_age_days
                factors["domain_match"] = (
                    business.official_domain.lower() == business.domain_used_by_sender.lower()
                    if business.official_domain and business.domain_used_by_sender
                    else False
                )

                if business.verified:
                    score += settings.trust_verified_biz_bonus
                    reason_parts.append(f"Sender is a verified business ({business.display_name})")
                else:
                    score += settings.trust_unverified_biz_penalty
                    reason_parts.append(f"Sender is an unverified business ({business.display_name})")

                # Domain spoofing check
                if business.official_domain and business.domain_used_by_sender:
                    if not factors["domain_match"]:
                        score += settings.trust_domain_mismatch_penalty
                        factors["domain_spoof_warning"] = True
                        reason_parts.append(
                            f"Domain mismatch: sender used '{business.domain_used_by_sender}' "
                            f"instead of official domain '{business.official_domain}'"
                        )

                # Recent user-business relationship
                if user_biz_history:
                    factors["has_user_relationship"] = True
                    reason_parts.append(f"User has relationship: {user_biz_history.why_user_knows_account}")
                    score += 15.0
                    if user_biz_history.messages_replied_30d > 0:
                        score += 10.0

                # High user report penalty
                if business.user_reports_30d > 20:
                    score -= 30.0
                    factors["high_reports_penalty"] = True
                    reason_parts.append(f"Business has high report count ({business.user_reports_30d} reports)")

        # Clamp final score between 0 and 100
        final_score = max(0.0, min(100.0, score))
        confidence = 0.85 if len(factors) > 1 else 0.60
        reason_str = ". ".join(reason_parts) if reason_parts else "Default sender trust score"

        return TrustScore(
            score=final_score,
            reason=reason_str,
            confidence=confidence,
            factors=factors,
        )
