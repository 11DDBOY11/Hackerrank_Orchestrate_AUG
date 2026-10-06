import sys
import unittest
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from data.models import BusinessAccount, ConversationType, Message
from pipeline.trust_engine import TrustEngine


class TestTrustEngine(unittest.TestCase):

    def test_trust_engine_verified_business(self):
        engine = TrustEngine()
        msg = Message(
            message_id="msg_test",
            user_id="u_001",
            conversation_type=ConversationType.BUSINESS,
            group_id=None,
            business_id="biz_test",
            sender_user_id=None,
            created_at="2026-07-31 10:00",
            message_text="Hello Customer",
            media_type=None,
            media_id=None,
            forwarded_count=0,
        )

        biz = BusinessAccount(
            business_id="biz_test",
            display_name="Amazon India",
            brand_name="Amazon",
            category="ecommerce",
            verified=True,
            official_domain="amazon.in",
            domain_used_by_sender="amazon.in",
            account_age_days=500,
            messages_sent_30d=1000,
            user_reports_30d=0,
            domain_used_by_sender_age_days=500,
        )

        trust = engine.compute(msg, None, None, None, biz, None)
        self.assertGreaterEqual(trust.score, 70.0)
        self.assertTrue(trust.factors.get("verified_business"))

    def test_trust_engine_domain_mismatch_penalty(self):
        engine = TrustEngine()
        msg = Message(
            message_id="msg_test",
            user_id="u_001",
            conversation_type=ConversationType.BUSINESS,
            group_id=None,
            business_id="biz_fake",
            sender_user_id=None,
            created_at="2026-07-31 10:00",
            message_text="Update",
            media_type=None,
            media_id=None,
            forwarded_count=0,
        )

        fake_biz = BusinessAccount(
            business_id="biz_fake",
            display_name="Chase Fake",
            brand_name="Chase",
            category="bank",
            verified=False,
            official_domain="chase.com",
            domain_used_by_sender="chase-secure-alert.com",
            account_age_days=10,
            messages_sent_30d=100,
            user_reports_30d=50,
            domain_used_by_sender_age_days=5,
        )

        trust = engine.compute(msg, None, None, None, fake_biz, None)
        self.assertLess(trust.score, 30.0)
        self.assertTrue(trust.factors.get("domain_spoof_warning"))


if __name__ == "__main__":
    unittest.main()
