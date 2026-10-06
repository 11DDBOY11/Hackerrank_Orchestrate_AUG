"""
Output Generator for the WhatsApp Notification Router.

Writes the final routing decisions to output.csv matching the exact required schema
and message_id row order from the template dataset file.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, List

from config.settings import settings
from data.models import RoutingDecision

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "message_id",
    "action",
    "message_type",
    "reason",
    "confidence",
    "evidence_message_ids",
]


class OutputGenerator:
    """Writes and validates submission output CSV file."""

    def write_output_csv(
        self,
        decisions: List[RoutingDecision],
        output_file_path: Path | str = settings.output_file,
        template_file_path: Path | str = settings.output_file,
    ) -> Path:
        output_path = Path(output_file_path).resolve()
        template_path = Path(template_file_path).resolve()

        # Map decisions by message_id
        decisions_by_id: Dict[str, RoutingDecision] = {d.message_id: d for d in decisions}

        # Determine target message_id order from template (or from decisions list if template empty)
        ordered_ids: List[str] = []
        if template_path.exists():
            with open(template_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    msg_id = row.get("message_id", "").strip()
                    if msg_id:
                        ordered_ids.append(msg_id)

        if not ordered_ids:
            ordered_ids = [d.message_id for d in decisions]

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=REQUIRED_COLUMNS)
            writer.writeheader()

            for msg_id in ordered_ids:
                if msg_id in decisions_by_id:
                    d = decisions_by_id[msg_id]
                    writer.writerow({
                        "message_id": d.message_id,
                        "action": d.action.value,
                        "message_type": d.message_type.value,
                        "reason": d.reason,
                        "confidence": f"{d.confidence:.2f}",
                        "evidence_message_ids": d.evidence_message_ids if d.evidence_message_ids else "none",
                    })
                else:
                    logger.warning(f"Missing decision for message_id={msg_id}; writing default row.")
                    writer.writerow({
                        "message_id": msg_id,
                        "action": "mute",
                        "message_type": "unknown",
                        "reason": "Default decision fallback.",
                        "confidence": "0.50",
                        "evidence_message_ids": "none",
                    })

        logger.info(f"Successfully wrote {len(ordered_ids)} prediction rows to {output_path}")
        return output_path
