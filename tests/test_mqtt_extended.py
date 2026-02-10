import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.mqtt import MQTTHandler
from meshtastic import mesh_pb2
from meshtastic.protobuf import mqtt_pb2
import paho.mqtt.client as mqtt

def test_mqtt_configure_minimal():
    config = MagicMock()
    handler = MQTTHandler(config, "1234abcd")
    
    # Minimal config (no address)
    node_cfg = MagicMock()
    node_cfg.enabled = True
    node_cfg.address = None
    node_cfg.port = 1883
    node_cfg.tlsEnabled = False
    node_cfg.username = None
    node_cfg.password = None
    node_cfg.root = 'msh'
    
    handler.configure(node_cfg)
    assert handler.mqtt_address is None
    assert handler.mqtt_port == 1883

def test_mqtt_configure_tls():
    config = MagicMock()
    handler = MQTTHandler(config, "1234abcd")
    
    node_cfg = MagicMock()
    node_cfg.enabled = True
    node_cfg.address = "mqtt.meshtastic.org"
    node_cfg.port = 1883
    node_cfg.tlsEnabled = True
    node_cfg.username = None
    node_cfg.password = None
    node_cfg.root = 'msh'
    
    with patch('ssl.create_default_context') as mock_ssl:
        handler.configure(node_cfg)
        assert handler.mqtt_port == 8883
        mock_ssl.assert_called()

def test_mqtt_start_invalid_address():
    config = MagicMock()
    handler = MQTTHandler(config, "1234abcd")
    
    # Start without address
    handler.start() # Should log error and return
    
    # Start with broadast address (255.255.255.255)
    node_cfg = MagicMock()
    node_cfg.enabled = True
    node_cfg.address = "255.255.255.255"
    node_cfg.port = 1883
    node_cfg.tlsEnabled = False
    node_cfg.username = None
    node_cfg.password = None
    node_cfg.root = 'msh'
    handler.configure(node_cfg)
    handler.start() # Should log warning and return

def test_mqtt_publish_failure():
    config = MagicMock()
    handler = MQTTHandler(config, "1234abcd")
    handler.client = MagicMock()
    
    # Simulate failure
    result = MagicMock()
    result.rc = mqtt.MQTT_ERR_NOMEM
    handler.client.publish.return_value = result
    
    assert handler.publish("test", b"abc") == False
    assert handler.tx_failures == 1

def test_mqtt_on_connect_failure():
    config = MagicMock()
    handler = MQTTHandler(config, "1234abcd")
    
    handler._on_connect(None, None, None, 5) # rc=5 (auth failure)
    assert handler.connected == False

def test_mqtt_on_disconnect_unexpected():
    config = MagicMock()
    handler = MQTTHandler(config, "1234abcd")
    handler.connected = True
    
    handler._on_disconnect(None, None, None, 1) # rc=1 (unexpected)
    assert handler.connected == False

def test_mqtt_on_message_stat():
    callback = MagicMock()
    handler = MQTTHandler(None, "1234abcd", on_message_callback=callback)
    
    msg = MagicMock()
    msg.topic = "msh/2/stat/!1234abcd"
    msg.payload = b"offline"
    
    handler._on_message(None, None, msg)
    callback.assert_not_called()

def test_mqtt_on_message_own():
    callback = MagicMock()
    handler = MQTTHandler(None, "1234abcd", on_message_callback=callback)
    
    msg = MagicMock()
    msg.topic = "msh/2/e/LongFast/!1234abcd"
    msg.payload = b"data"
    
    handler._on_message(None, None, msg)
    callback.assert_not_called()

def test_mqtt_on_message_mesh_packet_fallback():
    callback = MagicMock()
    handler = MQTTHandler(None, "1234abcd", on_message_callback=callback)
    
    # Generate a raw MeshPacket (not ServiceEnvelope)
    packet = mesh_pb2.MeshPacket()
    setattr(packet, "from", 0x12345678)
    packet.id = 12345
    
    msg = MagicMock()
    msg.topic = "msh/2/e/LongFast/!12345678"
    msg.payload = packet.SerializeToString()
    
    handler._on_message(None, None, msg)
    callback.assert_called_once()

def test_mqtt_on_message_exception_handling():
    handler = MQTTHandler(None, "1234abcd", on_message_callback=None)
    
    msg = MagicMock()
    msg.topic = None # Trigger exception in topic check
    
    # Should handle without crashing
    handler._on_message(None, None, msg)
