"""
Context Builder Engine for the WhatsApp Notification Router.

Normalizes raw incoming messages and enriches them with user context, sender profiles,
media understanding, group/business intelligence, computed scores, and relevant evidence.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from data.data_loader import DataStore
from data.models import (
    EvidenceMessage,
    HistoricalMessage,
    Message,
    MessageEvent,
    UnifiedMessage,
)
from pipeline.business_intelligence import BusinessIntelligenceEngine
from pipeline.group_intelligence import GroupIntelligenceEngine
from pipeline.media_understanding import MediaUnderstandingEngine
from pipeline.personalization import PersonalizationEngine
from pipeline.risk_engine import RiskEngine
from pipeline.trust_engine import TrustEngine

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds a normalized UnifiedMessage object for the reasoning engine."""

    def __init__(
        self,
        ds: DataStore,
        media_engine: Optional[MediaUnderstandingEngine] = None,
        trust_engine: Optional[TrustEngine] = None,
        risk_engine: Optional[RiskEngine] = None,
        personalization_engine: Optional[PersonalizationEngine] = None,
        group_engine: Optional[GroupIntelligenceEngine] = None,
        business_engine: Optional[BusinessIntelligenceEngine] = None,
    ):
        self.ds = ds
        self.media_engine = media_engine or MediaUnderstandingEngine()
        self.trust_engine = trust_engine or TrustEngine()
        self.risk_engine = risk_engine or RiskEngine()
        self.personalization_engine = personalization_engine or PersonalizationEngine()
        self.group_engine = group_engine or GroupIntelligenceEngine()
        self.business_engine = business_engine or BusinessIntelligenceEngine()

    def build_unified_message(self, message: Message) -> UnifiedMessage:
        """Converts raw Message into a fully enriched UnifiedMessage object."""
        user = self.ds.get_user(message.user_id)
        sender = self.ds.get_user(message.sender_user_id) if message.sender_user_id else None
        
        # 1. Media Understanding
        media_path = self.ds.get_media_path(message.media_type, message.media_id)
        media_analysis = self.media_engine.analyze(message.media_type, message.media_id, media_path)

        # 2. Group & Business Intelligence
        group = self.ds.get_group(message.group_id)
        membership = self.ds.get_membership(message.group_id, message.user_id)
        group_ctx = self.group_engine.analyze(message, group, membership)

        business = self.ds.get_business(message.business_id)
        user_biz_history = self.ds.get_user_business_history(message.user_id, message.business_id)
        biz_ctx = self.business_engine.analyze(message, business, user_biz_history)

        # 3. User History & Past Interactions
        user_hist_msgs = self.ds.get_historical_messages_for_user(message.user_id)
        sender_replied_count = 0
        if message.sender_user_id:
            for hm in user_hist_msgs:
                if hm.sender_user_id == message.sender_user_id:
                    evt = self.ds.get_event_for_message(message.user_id, hm.message_id)
                    if evt and evt.message_replied:
                        sender_replied_count += 1

        # 4. Compute Scores
        trust_score = self.trust_engine.compute(
            message=message,
            user=user,
            sender=sender,
            membership=membership,
            business=business,
            user_biz_history=user_biz_history,
            sender_messages_replied_count=sender_replied_count,
        )

        risk_score = self.risk_engine.compute(
            message=message,
            business=business,
            media_analysis=media_analysis,
        )

        user_events = [
            evt for evt in self.ds.message_events if evt.user_id == message.user_id
        ]
        personalization_score = self.personalization_engine.compute(
            message=message,
            user=user,
            membership=membership,
            user_biz_history=user_biz_history,
            user_history=user_hist_msgs,
            user_events=user_events,
        )

        # 5. Evidence Selection
        evidence_msgs = self._select_evidence_messages(message, user_hist_msgs)

        # 6. DND Status Check
        is_dnd = self._check_is_dnd(user, message.created_at)

        return UnifiedMessage(
            message=message,
            user=user,
            daily_notification_load=self.ds.daily_summaries_by_user.get(message.user_id, []),
            sender=sender,
            group_context=group_ctx,
            business_context=biz_ctx,
            media_analysis=media_analysis,
            trust_score=trust_score,
            risk_score=risk_score,
            personalization_score=personalization_score,
            evidence_messages=evidence_msgs,
            is_during_dnd=is_dnd,
            sender_is_known=bool(sender or (user_biz_history and user_biz_history.activity_count_180d > 0)),
            ds=self.ds,
        )

    def _select_evidence_messages(
        self, message: Message, user_history: List[HistoricalMessage]
    ) -> List[EvidenceMessage]:
        """Finds top relevant historical message IDs as evidence for decision explainability."""
        results: List[EvidenceMessage] = []

        for hm in user_history:
            relevance_reasons = []

            # Same business
            if message.business_id and hm.business_id == message.business_id:
                relevance_reasons.append("same_business_history")

            # Same group & sender
            if message.group_id and hm.group_id == message.group_id and hm.sender_user_id == message.sender_user_id:
                relevance_reasons.append("same_group_sender_history")

            # Same personal sender
            if message.sender_user_id and hm.sender_user_id == message.sender_user_id:
                relevance_reasons.append("same_contact_history")

            if relevance_reasons:
                evt = self.ds.get_event_for_message(message.user_id, hm.message_id)
                results.append(
                    EvidenceMessage(
                        message_id=hm.message_id,
                        relevance="; ".join(relevance_reasons),
                        event=evt,
                    )
                )

        # Sort by relevance and take top 2
        results.sort(key=lambda x: 1 if "same_business" in x.relevance or "same_contact" in x.relevance else 2)
        return results[:2]

    def _check_is_dnd(self, user: Optional[User], created_at: str) -> bool:
        """Checks if created_at timestamp falls within user's DND window."""
        if not user or not user.do_not_disturb_window or not created_at:
            return False
        try:
            time_part = created_at.split()[1] if " " in created_at else created_at
            msg_hour = int(time_part.split(":")[0])
            
            dnd_start, dnd_end = user.do_not_disturb_window.split("-")
            start_hour = int(dnd_start.split(":")[0])
            end_hour = int(dnd_end.split(":")[0])

            if start_hour > end_hour:  # Overnight range e.g. 22:00-07:00
                return msg_hour >= start_hour or msg_hour < end_hour
            else:
                return start_hour <= msg_hour < end_hour
        except Exception:
            return False
