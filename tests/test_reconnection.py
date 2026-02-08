
import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import importlib.util

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

# Load mqtt-proxy module dynamically due to hyphen in filename
try:
    mqtt_proxy_mod = load_module("mqtt_proxy_main", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mqtt-proxy.py"))
    MQTTProxy = mqtt_proxy_mod.MQTTProxy
except Exception as e:
    print(f"Failed to load mqtt-proxy: {e}")
    MQTTProxy = None

class TestReconnectionLoop(unittest.TestCase):
    
    def setUp(self):
        if MQTTProxy is None:
            self.skipTest("Could not import MQTTProxy")
            
        # Create instance
        self.proxy = MQTTProxy()
        # Mock internal state
        self.proxy.connection_lost_time = 0
        self.proxy.iface = MagicMock()
        self.proxy.running = True
        
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
