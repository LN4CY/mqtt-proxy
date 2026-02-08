
import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mqtt_proxy import MQTTProxy

class TestReconnectionLoop(unittest.TestCase):
    
    def setUp(self):
        # Create instance
        self.proxy = MQTTProxy()
        self.proxy.connection_lost_time = 0
        self.proxy.iface = MagicMock()
        
    def test_reconnection_debounce(self):
        """
        Test that on_connection_lost debounce prevents immediate recursion loops.
        """
        # Call 1
        self.proxy.on_connection_lost(None)
        first_time = self.proxy.connection_lost_time
        assert first_time > 0
        
        # Call 2 (Immediate)
        self.proxy.on_connection_lost(None)
        assert self.proxy.connection_lost_time == first_time
        
if __name__ == '__main__':
    unittest.main()
