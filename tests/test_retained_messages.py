"""Test that retained messages are not forwarded to the node by default."""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.mqtt import MQTTHandler

def test_retained_messages_skipped_by_default():
    """Test that retained messages are not forwarded to the node by default."""
    config = MagicMock()
    config.mqtt_forward_retained = False  # Default behavior
    
    callback = MagicMock()
    handler = MQTTHandler(config, "!12345678", on_message_callback=callback)
    
    # Simulate retained message
    msg = MagicMock()
    msg.topic = "msh/US/2/e/LongFast/!12345678"
    msg.payload = b"test"
    msg.retain = True  # Retained message
    
    handler._on_message(None, None, msg)
    
    # Callback should NOT be called for retained messages
    callback.assert_not_called()

def test_retained_messages_forwarded_when_enabled():
    """Test that retained messages ARE forwarded when config allows."""
    config = MagicMock()
    config.mqtt_forward_retained = True  # Explicitly enabled
    
    callback = MagicMock()
    handler = MQTTHandler(config, "!12345678", on_message_callback=callback)
    
    # Simulate retained message
    msg = MagicMock()
    msg.topic = "msh/US/2/e/LongFast/!12345678"
    msg.payload = b"test"
    msg.retain = True  # Retained message
    
    handler._on_message(None, None, msg)
    
    # Callback SHOULD be called when forwarding is enabled
    callback.assert_called_once_with("msh/US/2/e/LongFast/!12345678", b"test", True)
