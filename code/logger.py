"""
Structured Logger for the WhatsApp Notification Router.

Generates readable decision traces in logs/log.txt for every processed message.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

from config.settings import settings
from data.models import RoutingDecision, UnifiedMessage

logger = logging.getLogger(__name__)


class DecisionLogger:
    """Writes detailed decision logs to logs/log.txt."""

    def __init__(self, log_path: Path | str = settings.log_file):
        self.log_path = Path(log_path).resolve()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_decisions(self, items: List[Tuple[RoutingDecision, UnifiedMessage]]) -> None:
        """Writes detailed decision traces for a list of decisions."""
        lines = []
        lines.append("=" * 80)
        lines.append("WHATSAPP NOTIFICATION ROUTER — DECISION LOG TRACE")
        lines.append("=" * 80)
        lines.append(f"Total Messages Logged: {len(items)}\n")

        for dec, um in items:
            msg = um.message
            ocr_sum = um.media_analysis.summary if (um.media_analysis and um.media_analysis.media_type == "image") else "N/A"
            voice_txt = um.media_analysis.raw_transcript if (um.media_analysis and um.media_analysis.media_type == "voice") else "N/A"

            trust_str = f"{um.trust_score.score:.1f} ({um.trust_score.reason})" if um.trust_score else "N/A"
            risk_str = f"{um.risk_score.score:.1f} ({um.risk_score.reason})" if um.risk_score else "N/A"
            pers_str = f"{um.personalization_score.score:.1f} ({um.personalization_score.reason})" if um.personalization_score else "N/A"

            lines.append(f"Message ID: {dec.message_id}")
            lines.append(f"Sender: {msg.sender_user_id or msg.business_id or 'Unknown'}")
            lines.append(f"Conversation Type: {msg.conversation_type.value}")
            lines.append(f"Text: {msg.message_text}")
            lines.append(f"OCR Summary: {ocr_sum}")
            lines.append(f"Voice Transcript: {voice_txt}")
            lines.append(f"Trust Score: {trust_str}")
            lines.append(f"Risk Score: {risk_str}")
            lines.append(f"Personalization Score: {pers_str}")
            lines.append(f"Decision: {dec.action.value.upper()}")
            lines.append(f"Message Type: {dec.message_type.value}")
            lines.append(f"Reason: {dec.reason}")
            lines.append(f"Confidence: {dec.confidence}")
            lines.append(f"Evidence Message IDs: {dec.evidence_message_ids}")
            lines.append(f"Execution Time: {dec.execution_time_ms:.2f} ms")
            lines.append("-" * 40)

        with open(self.log_path, mode="w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        logger.info(f"Wrote decision traces to {self.log_path}")
