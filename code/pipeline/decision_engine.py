"""
Decision Engine for the WhatsApp Notification Router.

Combines AI reasoning output with hard safety overrides, weighted score thresholds,
and evidence formatting to produce the final valid RoutingDecision.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from config.settings import settings
from data.models import Action, MessageType, RoutingDecision, UnifiedMessage

logger = logging.getLogger(__name__)


class DecisionEngine:
    """Consolidates scores and reasoning into a deterministic RoutingDecision."""

    def make_decision(self, um: UnifiedMessage, reasoning_res: Dict[str, Any]) -> RoutingDecision:
        msg = um.message
        
        # 1. Parse raw LLM/reasoning fields
        raw_action_str = str(reasoning_res.get("decision", "digest")).strip().lower()
        raw_mtype_str = str(reasoning_res.get("message_type", "unknown")).strip().lower()
        reason = str(reasoning_res.get("reason", "Standard routing decision.")).strip()
        confidence = float(reasoning_res.get("confidence", 0.80))
        importance = int(reasoning_res.get("importance", 5))
        urgency = int(reasoning_res.get("urgency", 5))
        risk = int(reasoning_res.get("risk", 0))

        # Validate action enum
        try:
            action = Action(raw_action_str)
        except ValueError:
            action = Action.DIGEST

        # Map common LLM synonyms to strict MessageType enum values
        SYNONYM_MAP = {
            "chat": "personal",
            "social": "personal",
            "casual": "personal",
            "discussion": "personal",
            "question": "personal",
            "marketing": "promotion",
            "ad": "promotion",
            "advertisement": "promotion",
            "sale": "promotion",
            "discount": "promotion",
            "offer": "promotion",
            "deal": "promotion",
            "transactional": "business_update",
            "order": "business_update",
            "status": "business_update",
            "update": "business_update",
            "announcement": "business_update",
            "alert": "urgent",
            "critical": "urgent",
            "emergency": "urgent",
            "reminder": "event",
            "invitation": "event",
            "schedule": "event",
            "notice": "event",
            "phishing": "scam",
            "fraud": "scam",
            "otp_request": "scam",
            "telemarketing": "spam",
            "viral": "forward",
            "chain": "forward",
        }
        raw_mtype_str = SYNONYM_MAP.get(raw_mtype_str, raw_mtype_str)

        # Validate message_type enum
        try:
            message_type = MessageType(raw_mtype_str)
        except ValueError:
            message_type = MessageType.UNKNOWN

        # -------------------------------------------------------------------
        # 2. Hard Safety Override Engine
        # -------------------------------------------------------------------
        # Rule: Clear scams, phishing, or prompt injections MUST be muted regardless of user preferences or LLM outputs
        if um.risk_score:
            if um.risk_score.score >= settings.risk_scam_threshold or um.risk_score.is_prompt_injection:
                action = Action.MUTE
                if message_type not in (MessageType.SCAM, MessageType.SPAM):
                    message_type = MessageType.SCAM
                reason = um.risk_score.reason or "High security risk or scam pattern detected."
                confidence = max(confidence, 0.85)

        # -------------------------------------------------------------------
        # 3. Muted Group Override (unless direct mention or urgent admin notice)
        # -------------------------------------------------------------------
        if um.group_context and um.group_context.membership:
            if um.group_context.membership.group_muted_by_user:
                # If muted group and NOT direct mention or urgent admin notice -> force mute/digest
                if not um.group_context.is_direct_mention and not (um.group_context.sender_is_admin and um.group_context.message_significance == "urgent"):
                    if action == Action.NOTIFY:
                        action = Action.DIGEST

        # -------------------------------------------------------------------
        # 4. Opted-out Business Marketing Override
        # -------------------------------------------------------------------
        if um.business_context and um.business_context.user_history:
            if um.business_context.user_history.promotions_opted_out_at:
                if message_type in (MessageType.PROMOTION, MessageType.BUSINESS_UPDATE):
                    action = Action.MUTE
                    message_type = MessageType.PROMOTION
                    reason = "The user has opted out of or repeatedly dismissed similar marketing messages."

        # -------------------------------------------------------------------
        # 5. Format Evidence Message IDs
        # -------------------------------------------------------------------
        evidence_str = "none"
        if um.evidence_messages:
            evidence_str = ";".join([e.message_id for e in um.evidence_messages])

        # Clamp confidence between 0.0 and 1.0
        final_confidence = round(max(0.0, min(1.0, confidence)), 2)

        return RoutingDecision(
            message_id=msg.message_id,
            action=action,
            message_type=message_type,
            reason=reason,
            confidence=final_confidence,
            evidence_message_ids=evidence_str,
            importance=importance,
            urgency=urgency,
            risk=risk,
        )
