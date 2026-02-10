"""Test Loop Prevention logic."""
import time
import pytest
from unittest.mock import MagicMock, patch
from handlers.node_tracker import PacketDeduplicator
from handlers.mqtt import MQTTHandler
from meshtastic import mesh_pb2
from meshtastic.protobuf import mqtt_pb2

def test_packet_deduplicator():
    deduplicator = PacketDeduplicator(timeout_seconds=1)
    
    # Not seen initially
    assert not deduplicator.is_duplicate("!12345678", 101)
    
    # Mark seen
    deduplicator.mark_seen("!12345678", 101)
    assert deduplicator.is_duplicate("!12345678", 101)
    
    # Different packet ID should NOT be duplicate
    assert not deduplicator.is_duplicate("!12345678", 102)
    
    # Different node ID should NOT be duplicate
    assert not deduplicator.is_duplicate("!87654321", 101)
    
    # Wait for timeout
    time.sleep(1.1)
    assert not deduplicator.is_duplicate("!12345678", 101)

def test_mqtt_packet_deduplication():
    config_mock = MagicMock()
    deduplicator = PacketDeduplicator()
    
    handler = MQTTHandler(config_mock, "my_node", deduplicator=deduplicator)
    
    # Simulate seeing a packet on RF
    # Node !deadbeef sends packet ID 999
    deduplicator.mark_seen("!deadbeef", 999)
    
    # Construct a ServiceEnvelope simulating valid MQTT message from that node
    envelope = mqtt_pb2.ServiceEnvelope()
    setattr(envelope.packet, "from", 0xdeadbeef)
    envelope.packet.id = 999
    # envelope.packet.to = ... doesn't matter for this test
    
    msg = MagicMock()
    msg.topic = "msh/US/2/e/LongFast/!deadbeef"
    msg.payload = envelope.SerializeToString()
    msg.retain = False
    
    # Capture logs to verify ignore
    from handlers import mqtt
    with patch.object(mqtt.logger, 'info') as mock_log:
        handler._on_message(None, None, msg)
        
        args, _ = mock_log.call_args
        # Expectation: Logged ignore due to duplicate
        assert "Ignoring duplicate MQTT message" in args[0]
        assert "deadbeef" in args[0]
        assert "999" in args[0]

def test_mqtt_new_packet_passed():
    config_mock = MagicMock()
    deduplicator = PacketDeduplicator()
    handler = MQTTHandler(config_mock, "my_node", deduplicator=deduplicator)
    
    # Seen packet 999
    deduplicator.mark_seen("!deadbeef", 999)
    
    # New packet 1000 from SAME node
    envelope = mqtt_pb2.ServiceEnvelope()
    setattr(envelope.packet, "from", 0xdeadbeef)
    envelope.packet.id = 1000
    
    msg = MagicMock()
    msg.topic = "msh/US/2/e/LongFast/!deadbeef"
    msg.payload = envelope.SerializeToString()
    msg.retain = False
    
    callback = MagicMock()
    handler.on_message_callback = callback
    
    # Process message
    handler._on_message(None, None, msg)
    
    # Verify callback CALLED (passed through)
    callback.assert_called_once()
