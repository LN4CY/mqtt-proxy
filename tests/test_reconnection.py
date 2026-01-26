
import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import time

# Add parent directory to path to import mqtt-proxy
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the module to be tested
# We import it as 'proxy' to avoid syntax errors with hyphens in filename
try:
    proxy = __import__('mqtt-proxy')
except ImportError:
    # Handle the case where the file is named mqtt-proxy.py (hyphen)
    # We can use importlib or just rename it in our dev env if needed,
    # but strictly speaking `__import__` handles it if we pass the filename without .py?
    # No, python module names shouldn't have hyphens. 
    # The file in the repo is `mqtt-proxy.py`. 
    # We typically load this using SourceFileLoader or similar for testing scripts with bad names.
    import importlib.util
    spec = importlib.util.spec_from_file_location("mqtt_proxy", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mqtt-proxy.py"))
    proxy = importlib.util.module_from_spec(spec)
    sys.modules["mqtt_proxy"] = proxy
    spec.loader.exec_module(proxy)

class TestReconnectionLoop(unittest.TestCase):
    
    def setUp(self):
        # Reset global state
        proxy.connection_lost_time = 0
        proxy.iface = MagicMock()
        
    def test_infinite_recursion_on_close(self):
        """
        Reproduce the infinite recursion loop:
        on_connection_lost -> iface.close() -> (triggers) on_connection_lost -> ...
        """
        # Mock interface close to trigger connection_lost again IMMEDIATELY
        # mimicking the behavior of the library which might emit the signal on close
        
        call_count = 0
        
        def recursive_trigger():
            nonlocal call_count
            call_count += 1
            if call_count > 100:
                raise RecursionError("Infinite loop detected!")
            
            # recursive call simulation
            proxy.on_connection_lost(None)

        # Set the side effect of close() to trigger the recursion
        proxy.iface.close.side_effect = recursive_trigger
        
        try:
            proxy.on_connection_lost(None)
        except RecursionError:
            self.fail("RecursionError raised! Fix failed.")
            
        # If the fix works, call_count should be 1 (initial call) + maybe 1 (if strict debounce timing allows, but mock is fast)
        # Actually with the fix, we set iface=None, so subsequent close() shouldn't even happen or safely return.
        
        # We Expect PASS if count is low (loop prevented)
        self.assertLessEqual(call_count, 5, f"Recursion loop detected! Count: {call_count}")
            
if __name__ == '__main__':
    unittest.main()
