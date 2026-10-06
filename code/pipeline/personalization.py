"""
Personalization Engine for the WhatsApp Notification Router.

Computes a user-specific personalization score based on historical response rates,
muted group settings, opt-out preferences, and individual notification tolerances.
"""

from __future__ import annotations

from typing import List, Optional

from config.settings import settings
from data.models import (
    GroupMembership,
    HistoricalMessage,
    Message,
    MessageEvent,
    PersonalizationScore,
    User,
    UserBusinessHistory,
)


class PersonalizationEngine:
    """Calculates user-specific interest, relationship score, and fatigue level."""

    def compute(
        self,
        message: Message,
        user: Optional[User],
        membership: Optional[GroupMembership],
        user_biz_history: Optional[UserBusinessHistory],
        user_history: List[HistoricalMessage],
        user_events: List[MessageEvent],
    ) -> PersonalizationScore:
        score = 50.0
        factors = {}
        reason_parts = []

        # -------------------------------------------------------------------
        # 1. User Baseline Activity & Engagement Level
        # -------------------------------------------------------------------
        if user:
            # High responsiveness user
            if user.messages_opened_30d > 0:
                reply_rate = user.messages_replied_30d / max(1, user.messages_opened_30d)
                factors["user_reply_rate"] = round(reply_rate, 2)
                if reply_rate > 0.25:
                    score += 10.0
                    reason_parts.append("User is generally active and responsive")

            # High dismissal rate (fatigue warning)
            if user.notifications_dismissed_30d > 50:
                score -= 10.0
                factors["high_dismissal_rate"] = True
                reason_parts.append("User frequently dismisses notifications")

        # -------------------------------------------------------------------
        # 2. Group Personalization & Mute State
        # -------------------------------------------------------------------
        if membership:
            factors["group_muted_by_user"] = membership.group_muted_by_user
            if membership.group_muted_by_user:
                score -= 35.0
                reason_parts.append("User has explicitly muted this group chat")
            
            if membership.replies_sent_30d > 5:
                score += 15.0
                reason_parts.append("User frequently participates in this group")
            elif membership.messages_read_30d == 0 and membership.replies_sent_30d == 0:
                score -= 15.0
                reason_parts.append("User never reads or interacts in this group")

        # -------------------------------------------------------------------
        # 3. Business Personalization & Opt-In/Out Status
        # -------------------------------------------------------------------
        if user_biz_history:
            factors["allows_promotions"] = user_biz_history.allows_promotions
            factors["promotions_opted_out"] = bool(user_biz_history.promotions_opted_out_at)

            if user_biz_history.promotions_opted_out_at:
                score += settings.personalization_opted_out_penalty
                reason_parts.append("User explicitly opted out of marketing/promotions from this business")
            elif user_biz_history.allows_promotions:
                score += 15.0
                reason_parts.append("User explicitly allowed marketing promotions from this business")

            if user_biz_history.messages_opened_30d > 5 and user_biz_history.messages_dismissed_30d < 2:
                score += settings.personalization_high_engagement_bonus
                reason_parts.append("User regularly opens updates from this business")
            elif user_biz_history.messages_dismissed_30d > 5 and user_biz_history.messages_opened_30d <= 1:
                score += settings.personalization_ignored_history_penalty
                reason_parts.append("User consistently dismisses messages from this business")

        # Clamp final score
        final_score = max(0.0, min(100.0, score))
        engagement_likelihood = final_score / 100.0
        reason_str = ". ".join(reason_parts) if reason_parts else "Standard user personalization baseline"

        return PersonalizationScore(
            score=final_score,
            reason=reason_str,
            engagement_likelihood=engagement_likelihood,
            factors=factors,
        )
