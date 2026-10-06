"""
Group Intelligence Module for the WhatsApp Notification Router.

Analyzes group type, user role, direct mentions (@user_id), admin updates,
announcements, and deadline urgency within group conversations.
"""

from __future__ import annotations

import re
from typing import Optional

from data.models import Group, GroupContext, GroupMembership, Message


class GroupIntelligenceEngine:
    """Enriches group context and assesses message significance."""

    def analyze(
        self,
        message: Message,
        group: Optional[Group],
        membership: Optional[GroupMembership],
    ) -> GroupContext:
        if not group or not message.group_id:
            return GroupContext()

        sender_is_admin = membership.role == "admin" if membership else False
        
        # Check for direct tag / mention e.g. @u_001, @u_007, @u_010
        user_mention_pattern = rf"@{message.user_id}\b"
        is_direct_mention = bool(re.search(user_mention_pattern, message.message_text or "", re.IGNORECASE))

        # Group type importance heuristics
        group_type = (group.group_type or "").lower()
        if group_type in ("society", "school_group", "coworker", "caregiving", "safety"):
            group_importance = "high"
        elif group_type in ("family", "college_faculty", "tech_community", "sports"):
            group_importance = "medium"
        else:
            group_importance = "low"  # marketplace, local_food, investment_tips, real_estate

        # Message significance heuristics
        text_lower = (message.message_text or "").lower()
        message_significance = "normal"
        if is_direct_mention:
            message_significance = "urgent"
        elif sender_is_admin and any(kw in text_lower for kw in ["notice", "urgent", "penalty", "cutoff", "deadline", "closing"]):
            message_significance = "announcement"
        elif any(kw in text_lower for kw in ["urgent", "immediately", "today 5 pm", "before 6 pm", "tanker is leaving"]):
            message_significance = "urgent"

        return GroupContext(
            group=group,
            membership=membership,
            sender_is_admin=sender_is_admin,
            is_direct_mention=is_direct_mention,
            group_importance=group_importance,
            message_significance=message_significance,
        )
