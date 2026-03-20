import os
import sys
import pytest
from unittest.mock import MagicMock, patch, ANY

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.meshtastic import MQTTProxyMixin
from meshtastic import mesh_pb2

# Load MQTTProxy from the hyphenated filename
import importlib.util
def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

mqtt_proxy_mod = load_module("mqtt_proxy_test", "mqtt-proxy.py")
MQTTProxy = mqtt_proxy_mod.MQTTProxy

class MockChannel:
    def __init__(self, name, role, uplink=True, downlink=True):
        self.role = role
        self.settings = MagicMock()
        self.settings.name = name
        self.settings.uplink_enabled = uplink
        self.settings.downlink_enabled = downlink

class TestChannelFiltering:
    
    def test_extract_channel_from_topic(self):
        proxy = MQTTProxy()
        assert proxy._extract_channel_from_topic("msh/2/e/LongFast/!12345678") == "LongFast"
        assert proxy._extract_channel_from_topic("msh/2/e/MyChannel/!abcd") == "MyChannel"
        assert proxy._extract_channel_from_topic("other/topic") == None
        assert proxy._extract_channel_from_topic("msh/1/e/LongFast") == "LongFast"

    def test_downlink_filtering(self):
        proxy = MQTTProxy()
        proxy.iface = MagicMock()
        
        # Setup channels
        # Index 0: LongFast, Downlink=False
        # Index 1: Secondary, Downlink=True
        proxy.iface.localNode.channels = [
            MockChannel("", 1, uplink=True, downlink=False),
            MockChannel("Secondary", 2, uplink=True, downlink=True)
        ]
        
        # 1. Test LongFast (Downlink disabled)
        proxy.message_queue = MagicMock()
        proxy.on_mqtt_message_to_radio("msh/2/e/LongFast/!123", b"payload", False)
        proxy.message_queue.put.assert_not_called()
        
        # 2. Test Secondary (Downlink enabled)
        proxy.on_mqtt_message_to_radio("msh/2/e/Secondary/!123", b"payload", False)
        proxy.message_queue.put.assert_called_with("msh/2/e/Secondary/!123", b"payload", False)

    def test_uplink_filtering(self):
        # Create a mock interface using the Mixin
        class TestInterface(MQTTProxyMixin):
            def __init__(self, proxy):
                self.proxy = proxy
            def _handleFromRadio(self, fromRadio):
                super()._handleFromRadio(fromRadio)
        
        proxy = MQTTProxy()
        proxy.mqtt_handler = MagicMock()
        proxy.iface = MagicMock()
        
        # Setup channels
        # Index 0: LongFast, Uplink=False
        # Index 1: Secondary, Uplink=True
        proxy.iface.localNode.channels = [
            MockChannel("", 1, uplink=False, downlink=True),
            MockChannel("Secondary", 2, uplink=True, downlink=True)
        ]
        
        interface = TestInterface(proxy)
        
        # Mocking the parent class for super() call
        with patch('meshtastic.tcp_interface.TCPInterface._handleFromRadio'):
            # 1. Test LongFast (Uplink disabled)
            TEST_ROOT = "msh/US/MI"
            from_radio = mesh_pb2.FromRadio()
            from_radio.mqttClientProxyMessage.topic = f"{TEST_ROOT}/2/e/LongFast/!123"
            from_radio.mqttClientProxyMessage.data = b"payload"
            
            interface._handleFromRadio(from_radio)
            proxy.mqtt_handler.publish.assert_not_called()
            
            # 2. Test Secondary (Uplink enabled)
            from_radio_2 = mesh_pb2.FromRadio()
            from_radio_2.mqttClientProxyMessage.topic = "msh/2/e/Secondary/!123"
            from_radio_2.mqttClientProxyMessage.data = b"payload"
            
            interface._handleFromRadio(from_radio_2)
            proxy.mqtt_handler.publish.assert_called_with("msh/2/e/Secondary/!123", b"payload", retain=ANY)

    def test_case_insensitive_matching(self):
        proxy = MQTTProxy()
        proxy.iface = MagicMock()
        proxy.iface.localNode.channels = [
            MockChannel("MyChannel", 1, uplink=True, downlink=False)
        ]
        
        # Should match "mychannel" (case-insensitive)
        assert proxy._is_channel_downlink_enabled("mychannel") == False
        assert proxy._is_channel_downlink_enabled("MYCHANNEL") == False
        
    def test_channel_not_found_default(self):
        proxy = MQTTProxy()
        proxy.iface = MagicMock()
        proxy.iface.localNode.channels = []
        
        # Should allow by default if channel not found
        assert proxy._is_channel_downlink_enabled("Unknown") == True
        assert proxy._is_channel_uplink_enabled("Unknown") == True
