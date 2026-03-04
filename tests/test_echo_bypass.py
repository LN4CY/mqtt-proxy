import os
import sys
from unittest.mock import MagicMock
import pytest

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.mqtt import MQTTHandler
from meshtastic import mesh_pb2
from meshtastic.protobuf import mqtt_pb2

def test_mqtt_loop_prevention_echo_bypass_encrypted():
    config_mock = MagicMock()
    handler = MQTTHandler(config_mock, "mynode")
    
    # Simulate a packet that we encrypted
    envelope = mqtt_pb2.ServiceEnvelope()
    envelope.gateway_id = "!mynode"
    envelope.packet.encrypted = b'secret'
    
    msg = MagicMock()
    msg.topic = "msh/US/2/e/LongFast/!mynode" # From us
    msg.payload = envelope.SerializeToString()
    msg.retain = False
    
    callback = MagicMock()
    handler.on_message_callback = callback
    
    # Process message - should bypass loop prevention because it's encrypted
    handler._on_message(None, None, msg)
    
    callback.assert_called_once()


def test_mqtt_loop_prevention_echo_bypass_request_id():
    config_mock = MagicMock()
    handler = MQTTHandler(config_mock, "mynode")
    
    # Simulate a packet that has a request_id
    envelope = mqtt_pb2.ServiceEnvelope()
    envelope.gateway_id = "!mynode"
    envelope.packet.decoded.request_id = 1234
    
    msg = MagicMock()
    msg.topic = "msh/US/2/e/LongFast/!mynode" # From us
    msg.payload = envelope.SerializeToString()
    msg.retain = False
    
    callback = MagicMock()
    handler.on_message_callback = callback
    
    # Process message - should bypass loop prevention because it has request_id
    handler._on_message(None, None, msg)
    
    callback.assert_called_once()
    
def test_mqtt_loop_prevention_blocks_unencrypted_no_request():
    config_mock = MagicMock()
    handler = MQTTHandler(config_mock, "mynode")
    
    # Simulate a packet like NodeInfo without encryption or request_id
    envelope = mqtt_pb2.ServiceEnvelope()
    envelope.gateway_id = "!mynode"
    envelope.packet.decoded.portnum = 1 # NODEINFO_APP
    
    msg = MagicMock()
    msg.topic = "msh/US/2/e/LongFast/!mynode" # From us
    msg.payload = envelope.SerializeToString()
    msg.retain = False
    
    callback = MagicMock()
    handler.on_message_callback = callback
    
    # Process message - should be blocked by loop prevention
    handler._on_message(None, None, msg)
    
    callback.assert_not_called()
