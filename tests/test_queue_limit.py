
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.queue import MessageQueue

class MockConfig:
    def __init__(self, max_size=10):
        self.mesh_transmit_delay = 0.1
        self.mesh_max_queue_size = max_size

class TestMessageQueueLimit(unittest.TestCase):

    def setUp(self):
        self.max_size = 5
        self.config = MockConfig(max_size=self.max_size)
        self.mock_iface = MagicMock()
        self.iface_provider = MagicMock(return_value=self.mock_iface)
        self.q = MessageQueue(self.config, self.iface_provider)

    def tearDown(self):
        self.q.stop()

    def test_queue_full_evicts_oldest(self):
        """When queue is full, adding a new message evicts the oldest."""
        # Fill the queue
        for i in range(self.max_size):
            self.q.put(f"topic_{i}", b"data", False)

        self.assertEqual(self.q.qsize(), self.max_size)

        # Add one more — should evict topic_0
        self.q.put("topic_new", b"data", False)

        # Size unchanged
        self.assertEqual(self.q.qsize(), self.max_size)

        # Drain and verify oldest (topic_0) is gone, newest is present
        items = list(self.q.drain_all())
        topics = [item['topic'] for item in items]
        self.assertNotIn("topic_0", topics)
        self.assertIn("topic_new", topics)
        self.assertEqual(len(topics), self.max_size)

    def test_queue_full_logs_eviction(self):
        """When queue is full, eviction is logged as a warning with counter."""
        with patch('handlers.queue.logger') as mock_logger:
            for i in range(self.max_size):
                self.q.put(f"topic_{i}", b"data", False)

            self.q.put("topic_new", b"data", False)

            # Should have logged a warning about eviction
            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            eviction_logged = any("Evicting oldest" in c for c in warning_calls)
            self.assertTrue(eviction_logged, f"Expected eviction warning, got: {warning_calls}")
            # Should include eviction counter
            counter_logged = any("evicted 1 total" in c for c in warning_calls)
            self.assertTrue(counter_logged, f"Expected eviction counter, got: {warning_calls}")

    def test_queue_warning_near_full(self):
        """When queue reaches 80% capacity, a warning is logged."""
        with patch('handlers.queue.logger') as mock_logger:
            # Fill to 80% (4 of 5)
            for i in range(4):
                self.q.put(f"topic_{i}", b"data", False)

            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            nearly_full_logged = any("nearly full" in c for c in warning_calls)
            self.assertTrue(nearly_full_logged, f"Expected 'nearly full' warning, got: {warning_calls}")

if __name__ == '__main__':
    unittest.main()
