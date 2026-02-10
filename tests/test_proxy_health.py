import pytest
import time
import os
from unittest.mock import MagicMock, patch, mock_open
import sys

# Load MQTTProxy
import importlib.util
def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # Patch sys.modules before exec to avoid circular issues
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        print(f"FAILED TO LOAD {path}: {e}")
        # We don't re-raise to see the failure in tests later
    return mod

mqtt_proxy_mod = load_module("mqtt_proxy_test", "mqtt-proxy.py")
MQTTProxy = mqtt_proxy_mod.MQTTProxy

def test_proxy_init():
    proxy = MQTTProxy()
    assert proxy.running == True
    assert proxy.deduplicator is not None
    assert proxy.message_queue is not None

def test_on_connection_edge_cases():
    proxy = MQTTProxy()
    
    # CASE: No localNode
    iface = MagicMock()
    iface.localNode = None
    proxy.on_connection(iface)
    assert proxy.last_radio_activity == 0
    
    # CASE: Exception in node ID
    node = MagicMock()
    iface.localNode = node
    type(node).nodeNum = property(lambda x: 1/0) # Trigger exception
    proxy.on_connection(iface)
    # Should handle gracefully
    
    # CASE: No MQTT config - moduleConfig itself is None
    class SimpleNode:
        def __init__(self):
            self.nodeNum = 12345
            self.nodeId = "!12345"
            self.moduleConfig = None  # No moduleConfig at all
    
    proxy.mqtt_handler = None  # Reset from previous tests
    iface.localNode = SimpleNode()
    proxy.on_connection(iface)
    assert proxy.mqtt_handler is None

def test_on_connection_lost_debounce():
    proxy = MQTTProxy()
    proxy.on_connection_lost(None)
    t1 = proxy.connection_lost_time
    assert t1 > 0
    
    # Immediate second call
    proxy.on_connection_lost(None)
    assert proxy.connection_lost_time == t1

def test_health_check_logic():
    now = time.time()
    proxy = MQTTProxy()
    proxy.connection_lost_time = 0.0
    proxy.last_radio_activity = now
    proxy.mqtt_handler = MagicMock()
    proxy.mqtt_handler.connected = True
    proxy.mqtt_handler.health_check_enabled = True
    proxy.mqtt_handler.tx_failures = 0
    
    # 1. OK State
    ok, reasons = proxy._perform_health_check(now)
    assert ok == True
    
    # 2. MQTT Disconnected
    proxy.mqtt_handler.connected = False
    ok, reasons = proxy._perform_health_check(now)
    assert ok == False
    assert "MQTT disconnected" in reasons
    
    # 3. Connection Lost Watchdog (Simulate < 60s)
    proxy.connection_lost_time = now - 30.0
    ok, reasons = proxy._perform_health_check(now)
    # Should NOT exit yet, just wait (if it were > 60 it would exit)
    
    # 4. Radio Watchdog (Silent)
    proxy.last_radio_activity = now - 400.0 # Long time ago
    proxy.last_probe_time = 0.0
    # Also ensure cfg.health_check_activity_timeout is a number
    with patch('mqtt_proxy_test.cfg') as mock_cfg:
        mock_cfg.health_check_activity_timeout = 300
        with patch.object(proxy, 'iface') as mock_iface:
            ok, reasons = proxy._perform_health_check(now)
            # Should send probe
            mock_iface.sendPosition.assert_called()
        
    # 5. Radio Watchdog (Silent + Probe Failure)
    proxy.mqtt_handler.connected = True  # Reset to passing state first
    proxy.connection_lost_time = 0.0  # Reset
    proxy.last_probe_time = now - 35.0
    with patch('mqtt_proxy_test.cfg') as mock_cfg:
        mock_cfg.health_check_activity_timeout = 300
        ok, reasons = proxy._perform_health_check(now)
        assert ok == False
        assert "Radio silent" in reasons[0]

    # 6. MQTT TX Failures
    proxy.mqtt_handler.tx_failures = 10
    ok, reasons = proxy._perform_health_check(now)
    assert ok == False
    assert "MQTT Publish Failures" in reasons[-1]

def test_log_status():
    proxy = MQTTProxy()
    proxy.mqtt_handler = MagicMock()
    proxy.mqtt_handler.connected = True
    proxy.mqtt_handler.last_activity = time.time()
    proxy.last_radio_activity = time.time() - 10.0
    proxy.last_status_log_time = time.time() - 100.0 # Exceed interval
    
    with patch('mqtt_proxy_test.cfg') as mock_cfg:
        mock_cfg.health_check_status_interval = 60
        with patch('logging.Logger.info') as mock_log:
             proxy._log_status(time.time())
             mock_log.assert_called()


def test_cleanup():
    proxy = MQTTProxy()
    proxy.mqtt_handler = MagicMock()
    proxy.iface = MagicMock()
    proxy.message_queue = MagicMock()
    
    proxy._cleanup()
    proxy.mqtt_handler.stop.assert_called()
    proxy.iface.close.assert_called()
    proxy.message_queue.stop.assert_called()
