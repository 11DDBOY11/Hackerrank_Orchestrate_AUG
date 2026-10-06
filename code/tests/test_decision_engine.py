import sys
import unittest
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from data.models import Action, ConversationType, Message, MessageType, RiskScore, UnifiedMessage
from pipeline.decision_engine import DecisionEngine


class TestDecisionEngine(unittest.TestCase):

    def test_decision_engine_overrides_high_risk_scam_to_mute(self):
        engine = DecisionEngine()
        msg = Message(
            message_id="msg_scam",
            user_id="u_001",
            conversation_type=ConversationType.PERSONAL,
            group_id=None,
            business_id=None,
            sender_user_id="u_unknown",
            created_at="2026-07-31 10:00",
            message_text="Send OTP now",
            media_type=None,
            media_id=None,
            forwarded_count=0,
        )

        um = UnifiedMessage(
            message=msg,
            risk_score=RiskScore(score=85.0, reason="Phishing detected", is_prompt_injection=False)
        )

        reasoning_res = {
            "decision": "notify",  # Adversarial / hallucinated decision
            "message_type": "urgent",
            "reason": "Sounds urgent",
            "confidence": 0.9,
        }

        decision = engine.make_decision(um, reasoning_res)
        self.assertEqual(decision.action, Action.MUTE)
        self.assertEqual(decision.message_type, MessageType.SCAM)


if __name__ == "__main__":
    unittest.main()
