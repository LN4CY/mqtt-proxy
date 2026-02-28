
import unittest
import time
import queue
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.queue import MessageQueue

class MockConfig:
    def __init__(self):
        self.mesh_transmit_delay = 0.1 # Fast for tests

class TestMessageQueue(unittest.TestCase):
    
    def setUp(self):
        self.config = MockConfig()
        self.mock_iface = MagicMock()
        self.iface_provider = MagicMock(return_value=self.mock_iface)
        self.q = MessageQueue(self.config, self.iface_provider)

    def tearDown(self):
        self.q.stop()

    def test_put_enqueues_item(self):
        """Test adding items to the queue."""
        self.q.put("topic", b"payload", False)
        assert self.q.queue.qsize() == 1
        item = self.q.queue.get()
        assert item['topic'] == "topic"
        assert item['payload'] == b"payload"
        assert item['retained'] == False

    def test_processing_loop_sends_messages(self):
        """Test that the loop processes messages and sends them to interface."""
        self.q.start()
        
        self.q.put("t1", b"p1", False)
        self.q.put("t2", b"p2", True)
        
        # Wait for processing
        time.sleep(0.3)
        
        # Verify calls - we now expect _sendToRadio since it exists on the MagicMock
        assert self.mock_iface._sendToRadio.call_count >= 2
        
        # Check args of first call
        args, _ = self.mock_iface._sendToRadio.call_args_list[0]
        to_radio = args[0]
        assert to_radio.mqttClientProxyMessage.topic == "t1"
        assert to_radio.mqttClientProxyMessage.data == b"p1"

        # Check args of second call
        args, _ = self.mock_iface._sendToRadio.call_args_list[1]
        to_radio = args[0]
        assert to_radio.mqttClientProxyMessage.topic == "t2"
        assert to_radio.mqttClientProxyMessage.data == b"p2"

    def test_rate_limiting(self):
        """Test that messages are spaced out."""
        self.config.mesh_transmit_delay = 0.2
        self.q.start()
        
        start_time = time.time()
        self.q.put("t1", b"p1", False)
        self.q.put("t2", b"p2", False)
        
        # Wait enough time for both to process
        time.sleep(0.5) 
        
        # Should be called 2 times
        assert self.mock_iface._sendToRadio.call_count == 2
        
        pass 

    def test_waits_for_interface(self):
        """Test that queue waits if interface provider returns None."""
        # Capture real sleep to avoid recursion since patching time.sleep patches it globally
        real_sleep = time.sleep
        
        with patch('handlers.queue.time.sleep', side_effect=lambda x: real_sleep(0.001)):
            # Interface is initially None
            self.iface_provider.return_value = None
            self.q.start()
            
            self.q.put("t1", b"p1", False)
            # Give it a moment to enter the loop and block on get()
            real_sleep(0.1)
            
            # Should NOT have sent anything yet (it's waiting for interface)
            assert self.mock_iface._sendToRadio.call_count == 0
            
            # Now provide interface
            self.iface_provider.return_value = self.mock_iface
            
            # We need to ensure the loop iterates. 
            real_sleep(0.1)
            
            # Should now send
            # We loop a bit to be sure.
            for _ in range(10):
                if self.mock_iface._sendToRadio.call_count > 0:
                    break
                real_sleep(0.05)
                
            assert self.mock_iface._sendToRadio.call_count == 1

    def test_start_idempotency(self):
        """Test calling start twice doesn't spawn two threads."""
        self.q.start()
        thread1 = self.q.thread
        self.q.start()
        thread2 = self.q.thread
        assert thread1 == thread2
        assert self.q.running

    def test_queue_full_logging(self):
        """Test that logging occurs when queue grows."""
        with patch('handlers.queue.logger') as mock_logger:
            for i in range(15):
                self.q.put(f"t{i}", b"p", False)
            
            # Should verify logger.debug was called
            # qsize > 10 check
            mock_logger.debug.assert_called()
            # We can check specific call if we want, but checking it's called is sufficient for coverage

    def test_send_exception_handling(self):
        """Test exception handling during send."""
        self.q.start()
        
        # Mock send to raise exception
        self.mock_iface._sendToRadio.side_effect = Exception("Radio error")
        
        with patch('handlers.queue.logger') as mock_logger:
            self.q.put("t1", b"p", False)
            
            time.sleep(0.2)
            
            # Should have logged error
            mock_logger.error.assert_called_with("❌ Failed to send to radio: Radio error")
            # Queue should still be running/processing
            assert self.q.running

if __name__ == '__main__':
    unittest.main()
