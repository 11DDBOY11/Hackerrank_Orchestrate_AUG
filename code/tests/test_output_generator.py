import csv
import sys
import tempfile
import unittest
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from data.models import Action, MessageType, RoutingDecision
from output_generator import OutputGenerator, REQUIRED_COLUMNS


class TestOutputGenerator(unittest.TestCase):

    def test_output_generator_writes_valid_csv(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "output.csv"
            generator = OutputGenerator()

            decisions = [
                RoutingDecision(
                    message_id="msg_001",
                    action=Action.NOTIFY,
                    message_type=MessageType.URGENT,
                    reason="Urgent update from admin",
                    confidence=0.9,
                    evidence_message_ids="message_0001",
                ),
                RoutingDecision(
                    message_id="msg_002",
                    action=Action.MUTE,
                    message_type=MessageType.SCAM,
                    reason="Phishing link detected",
                    confidence=0.95,
                    evidence_message_ids="none",
                ),
            ]

            generator.write_output_csv(decisions, output_file_path=output_path, template_file_path=output_path)

            self.assertTrue(output_path.exists())
            with open(output_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                rows = list(reader)

            self.assertEqual(fieldnames, REQUIRED_COLUMNS)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["message_id"], "msg_001")
            self.assertEqual(rows[0]["action"], "notify")
            self.assertEqual(rows[1]["action"], "mute")


if __name__ == "__main__":
    unittest.main()
