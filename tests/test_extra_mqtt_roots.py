import os
import sys
import pytest
from unittest.mock import patch, MagicMock, call

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestExtraMqttRootsConfig:
    """Test EXTRA_MQTT_ROOTS config parsing."""

    def test_default_is_empty_list(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EXTRA_MQTT_ROOTS", None)
            from config import Config
            cfg = Config()
            assert cfg.extra_mqtt_roots == []

    def test_single_root_default_prefix(self):
        with patch.dict(os.environ, {"EXTRA_MQTT_ROOTS": "msh/US/OH"}):
            from config import Config
            cfg = Config()
            assert cfg.extra_mqtt_roots == [("msh/US/OH", "OH")]

    def test_multiple_roots_default_prefixes(self):
        with patch.dict(os.environ, {"EXTRA_MQTT_ROOTS": "msh/US/OH,msh/US/CA"}):
            from config import Config
            cfg = Config()
            assert cfg.extra_mqtt_roots == [("msh/US/OH", "OH"), ("msh/US/CA", "CA")]

    def test_custom_prefix(self):
        with patch.dict(os.environ, {"EXTRA_MQTT_ROOTS": "msh/US/OH:Ohio, msh/US/CA:California"}):
            from config import Config
            cfg = Config()
            assert cfg.extra_mqtt_roots == [("msh/US/OH", "Ohio"), ("msh/US/CA", "California")]

    def test_whitespace_stripped(self):
        with patch.dict(os.environ, {"EXTRA_MQTT_ROOTS": " msh/US/OH : Ohio , msh/US/CA "}):
            from config import Config
            cfg = Config()
            assert cfg.extra_mqtt_roots == [("msh/US/OH", "Ohio"), ("msh/US/CA", "CA")]

    def test_trailing_comma_ignored(self):
        with patch.dict(os.environ, {"EXTRA_MQTT_ROOTS": "msh/US/OH,"}):
            from config import Config
            cfg = Config()
            assert cfg.extra_mqtt_roots == [("msh/US/OH", "OH")]

class TestExtraMqttRootsSubscription:
    """Test that extra roots get subscribed on MQTT connect."""

    def _make_handler(self, extra_roots):
        from handlers.mqtt import MQTTHandler
        config = MagicMock()
        config.extra_mqtt_roots = extra_roots
        handler = MQTTHandler(config, "1234abcd")
        node_cfg = MagicMock()
        node_cfg.enabled = True
        node_cfg.address = "mqtt.example.com"
        node_cfg.port = 1883
        node_cfg.tlsEnabled = False
        node_cfg.username = "user"
        node_cfg.password = "pass"
        node_cfg.root = "msh/US/MI"
        handler.configure(node_cfg)
        return handler

    def test_no_extra_roots(self):
        handler = self._make_handler([])
        mock_client = MagicMock()
        handler._on_connect(mock_client, None, None, 0)
        subscribe_calls = mock_client.subscribe.call_args_list
        assert len(subscribe_calls) == 1
        assert subscribe_calls[0] == call("msh/US/MI/2/e/#")

    def test_extra_roots_subscribed(self):
        handler = self._make_handler([("msh/US/OH", "OH"), ("msh/US/CA", "CA")])
        mock_client = MagicMock()
        handler._on_connect(mock_client, None, None, 0)
        subscribe_calls = mock_client.subscribe.call_args_list
        topics = [c[0][0] for c in subscribe_calls]
        assert "msh/US/MI/2/e/#" in topics
        assert "msh/US/OH/2/e/#" in topics
        assert "msh/US/CA/2/e/#" in topics
        assert len(topics) == 3

    def test_duplicate_root_not_subscribed_twice(self):
        handler = self._make_handler([("msh/US/MI", "MI"), ("msh/US/OH", "OH")])
        mock_client = MagicMock()
        handler._on_connect(mock_client, None, None, 0)
        subscribe_calls = mock_client.subscribe.call_args_list
        topics = [c[0][0] for c in subscribe_calls]
        assert topics.count("msh/US/MI/2/e/#") == 1
        assert "msh/US/OH/2/e/#" in topics
        assert len(topics) == 2

class TestExtraRootVirtualChannels:
    """Test that extra-root packets are rewritten to Virtual Channels."""

    def _make_handler(self, extra_roots):
        from handlers.mqtt import MQTTHandler
        config = MagicMock()
        config.extra_mqtt_roots = extra_roots
        config.mqtt_forward_retained = False
        handler = MQTTHandler(config, "1234abcd")
        node_cfg = MagicMock()
        node_cfg.enabled = True
        node_cfg.address = "mqtt.example.com"
        node_cfg.port = 1883
        node_cfg.tlsEnabled = False
        node_cfg.username = "user"
        node_cfg.password = "pass"
        node_cfg.root = "msh/US/MI"
        handler.configure(node_cfg)
        return handler

    def _make_message(self, topic, payload=b"\x00" * 20):
        msg = MagicMock()
        msg.topic = topic
        msg.payload = payload
        msg.retain = False
        return msg

    def test_extra_root_rewritten(self):
        """Packet from extra root is rewritten to include internal prefix."""
        handler = self._make_handler([("msh/US/OH", "OH")])
        handler.on_message_callback = MagicMock()
        handler._on_message(None, None, self._make_message("msh/US/OH/2/e/LongFast/!abcd1234"))
        handler.on_message_callback.assert_called_once_with("msh/US/OH/2/e/OH-LongFast/!abcd1234", b"\x00" * 20, False)

    def test_extra_root_custom_prefix_rewritten(self):
        """Packet from extra root with custom prefix is rewritten."""
        handler = self._make_handler([("msh/US/OH", "Ohio")])
        handler.on_message_callback = MagicMock()
        handler._on_message(None, None, self._make_message("msh/US/OH/2/e/Emergency/!abcd1234"))
        handler.on_message_callback.assert_called_once_with("msh/US/OH/2/e/Ohio-Emergency/!abcd1234", b"\x00" * 20, False)

    def test_own_root_never_rewritten(self):
        """Packets from the node's own root are never rewritten."""
        handler = self._make_handler([("msh/US/OH", "OH")])
        handler.on_message_callback = MagicMock()
        handler._on_message(None, None, self._make_message("msh/US/MI/2/e/LongFast/!abcd1234"))
        handler.on_message_callback.assert_called_once_with("msh/US/MI/2/e/LongFast/!abcd1234", b"\x00" * 20, False)

    def test_malformed_topic_forwarded_as_is(self):
        """Malformed topic without channel name is forwarded without crashing."""
        handler = self._make_handler([("msh/US/OH", "OH")])
        handler.on_message_callback = MagicMock()
        handler._on_message(None, None, self._make_message("msh/US/OH/2/e"))
        handler.on_message_callback.assert_called_once_with("msh/US/OH/2/e", b"\x00" * 20, False)
