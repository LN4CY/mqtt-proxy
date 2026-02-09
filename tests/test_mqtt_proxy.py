import os
import sys
import time
import pytest
from unittest.mock import MagicMock, patch, ANY

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from handlers.mqtt import MQTTHandler
from handlers.meshtastic import create_interface, MQTTProxyMixin
from handlers.queue import MessageQueue

# Dummy proxy class for testing mixins
class MockProxy:
    def __init__(self):
        self.mqtt_handler = MagicMock()
        self.last_radio_activity = 0

class TestMQTTHandler:
    
    @patch('paho.mqtt.client.Client')
    def test_mqtt_connect(self, mock_client_cls):
        """Test MQTT connection and subscription"""
        config = Config()
        config.mqtt_root = "msh"
        
        handler = MQTTHandler(config, "1234abcd")
        
        # Mock node config
        node_cfg = MagicMock()
        node_cfg.enabled = True
        node_cfg.address = "1.2.3.4"
        node_cfg.port = 1883
        node_cfg.root = "msh"
        
        handler.configure(node_cfg)
        handler.start()
        
        client = handler.client
        
        # Simulate connect callback
        handler._on_connect(client, None, None, 0)
        
        # Check subscription
        client.subscribe.assert_called_with("msh/2/e/#")
        
    def test_publish(self):
        """Test publishing logic"""
        config = Config()
        handler = MQTTHandler(config, "1234abcd")
        handler.client = MagicMock()
        handler.client.publish.return_value.rc = 0
        
        assert handler.publish("topic", b"payload") == True
        handler.client.publish.assert_called_with("topic", b"payload", retain=False)

    def test_on_message(self):
        """Test MQTT -> Node message handling"""
        callback = MagicMock()
        config = Config()
        handler = MQTTHandler(config, "1234abcd", on_message_callback=callback)
        
        msg = MagicMock()
        msg.topic = "msh/2/c/LongFast/!other"
        msg.payload = b"data"
        msg.retain = False
        
        handler._on_message(None, None, msg)
        
        callback.assert_called_with(msg.topic, msg.payload, msg.retain)

class TestMeshtasticHandler:
    
    def test_proxy_mixin_node_to_mqtt(self):
        """Regression Test: Verify Node -> MQTT traffic forwarding"""
        
        # Create a mock interface using the Mixin
        class TestInterface(MQTTProxyMixin):
             def _handleFromRadio(self, fromRadio):
                 super()._handleFromRadio(fromRadio)
        
        # Mock the parent class for super() call
        with patch('meshtastic.tcp_interface.TCPInterface._handleFromRadio') as mock_super:
            
            # Setup proxy and handler
            proxy = MockProxy()
            interface = TestInterface()
            interface.proxy = proxy
            
            # Create FromRadio with mqttClientProxyMessage
            from meshtastic import mesh_pb2
            from_radio = mesh_pb2.FromRadio()
            mqtt_msg = from_radio.mqttClientProxyMessage
            mqtt_msg.topic = "msh/2/json/LongFast"
            mqtt_msg.data = b"payload"
            mqtt_msg.retained = False
            
            # Execute
            interface._handleFromRadio(from_radio)
            
            # VERIFY: The proxy's mqtt_handler.publish was called
            proxy.mqtt_handler.publish.assert_called_with("msh/2/json/LongFast", b"payload", retain=False)
            
            # Verify radio activity updated
            assert proxy.last_radio_activity > 0

    @patch('handlers.meshtastic.RawTCPInterface')
    def test_create_interface_tcp(self, mock_tcp):
        """Test factory creates TCP interface"""
        config = Config()
        config.interface_type = "tcp"
        config.tcp_node_host = "1.2.3.4"
        config.tcp_node_port = 4403
        
        proxy = MockProxy()
        create_interface(config, proxy)
        
        mock_tcp.assert_called_with("1.2.3.4", portNumber=4403, timeout=300, proxy=proxy)

class TestMessageQueue:
    
    def test_uses_safe_send_to_radio(self):
        """Test that _sendToRadio is used when available"""
        config = MagicMock()
        config.mesh_transmit_delay = 0.01
        
        mock_iface = MagicMock()
        # Mocking existence of _sendToRadio
        mock_iface._sendToRadio = MagicMock()
        
        mq = MessageQueue(config, lambda: mock_iface)
        mq.start()
        
        mq.put("test", b"data", False)
        
        time.sleep(0.1)
        mq.stop()
        
        mock_iface._sendToRadio.assert_called_once()
        mock_iface._sendToRadioImpl.assert_not_called()

    def test_fallback_to_impl(self):
        """Test fallback to _sendToRadioImpl if _sendToRadio is missing"""
        config = MagicMock()
        config.mesh_transmit_delay = 0.01
        
        mock_iface = MagicMock()
        # Ensure _sendToRadio does NOT exist
        del mock_iface._sendToRadio

        mq = MessageQueue(config, lambda: mock_iface)
        mq.start()
        
        mq.put("test", b"data", False)
        
        time.sleep(0.1)
        mq.stop()
        
        mock_iface._sendToRadioImpl.assert_called_once()
