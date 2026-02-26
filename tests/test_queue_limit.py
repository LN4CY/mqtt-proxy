
import unittest
import queue
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

    def test_queue_limit_drops_messages(self):
        """Test that adding items beyond max_size drops them."""
        # Fill the queue
        for i in range(self.max_size):
            self.q.put(f"topic_{i}", b"data", False)
            
        self.assertEqual(self.q.queue.qsize(), self.max_size)
        
        # Adding one more should drop it
        with patch('handlers.queue.logger') as mock_logger:
            self.q.put("dropped_topic", b"data", False)
            
            # Size should still be max_size
            self.assertEqual(self.q.queue.qsize(), self.max_size)
            
            # Logger error should have been called
            mock_logger.error.assert_called_with(f"Queue FULL ({self.max_size} msgs). Dropping new message for topic: dropped_topic")

    def test_queue_warning_near_full(self):
        """Test that a warning is logged when queue reaches 80%."""
        # 80% of 5 is 4.
        with patch('handlers.queue.logger') as mock_logger:
            for i in range(4):
                self.q.put(f"topic_{i}", b"data", False)
            
            # 4th message should trigger warning
            mock_logger.warning.assert_called_with(f"Queue nearly full: 4/{self.max_size} messages pending")

if __name__ == '__main__':
    unittest.main()
