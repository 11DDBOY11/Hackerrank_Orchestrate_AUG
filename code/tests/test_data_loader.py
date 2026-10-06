import sys
import unittest
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from config.settings import settings
from data.data_loader import DataLoader
from data.models import ConversationType, Message


class TestDataLoader(unittest.TestCase):

    def test_data_loader_loads_all_files(self):
        loader = DataLoader(settings.dataset_dir)
        ds = loader.load_all()

        self.assertGreater(len(ds.messages), 0)
        self.assertGreater(len(ds.sample_messages), 0)
        self.assertGreater(len(ds.users), 0)
        self.assertGreater(len(ds.groups), 0)
        self.assertGreater(len(ds.business_accounts), 0)
        self.assertGreater(len(ds.message_history), 0)
        self.assertGreater(len(ds.images), 0)
        self.assertGreater(len(ds.voice_notes), 0)

    def test_data_store_indexes(self):
        loader = DataLoader(settings.dataset_dir)
        ds = loader.load_all()

        msg = ds.messages[0]
        user = ds.get_user(msg.user_id)
        self.assertIsNotNone(user)
        self.assertEqual(user.user_id, msg.user_id)

        if msg.group_id:
            group = ds.get_group(msg.group_id)
            self.assertIsNotNone(group)
            membership = ds.get_membership(msg.group_id, msg.user_id)
            self.assertIsNotNone(membership)

        if msg.business_id:
            biz = ds.get_business(msg.business_id)
            self.assertIsNotNone(biz)


if __name__ == "__main__":
    unittest.main()
