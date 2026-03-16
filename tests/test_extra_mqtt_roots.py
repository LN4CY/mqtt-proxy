import os
import sys
import pytest
from unittest.mock import patch, MagicMock, call

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestExtraMqttRootsConfig:
    """Test EXTRA_MQTT_ROOTS config parsing."""

    def test_default_is_empty_list(self):
        """No env var set => empty list."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EXTRA_MQTT_ROOTS", None)
            from config import Config
            cfg = Config()
            assert cfg.extra_mqtt_roots == []

    def test_single_root(self):
        """Single root topic."""
        with patch.dict(os.environ, {"EXTRA_MQTT_ROOTS": "msh/US/OH"}):
            from config import Config
            cfg = Config()
            assert cfg.extra_mqtt_roots == ["msh/US/OH"]

    def test_multiple_roots(self):
        """Comma-separated list."""
        with patch.dict(os.environ, {"EXTRA_MQTT_ROOTS": "msh/US/OH,msh/US/CA"}):
            from config import Config
            cfg = Config()
            assert cfg.extra_mqtt_roots == ["msh/US/OH", "msh/US/CA"]

    def test_whitespace_stripped(self):
        """Whitespace around entries is stripped."""
        with patch.dict(os.environ, {"EXTRA_MQTT_ROOTS": " msh/US/OH , msh/US/CA "}):
            from config import Config
            cfg = Config()
            assert cfg.extra_mqtt_roots == ["msh/US/OH", "msh/US/CA"]

    def test_empty_string(self):
        """Empty string => empty list."""
        with patch.dict(os.environ, {"EXTRA_MQTT_ROOTS": ""}):
            from config import Config
            cfg = Config()
            assert cfg.extra_mqtt_roots == []

    def test_trailing_comma_ignored(self):
        """Trailing comma doesn't create empty entry."""
        with patch.dict(os.environ, {"EXTRA_MQTT_ROOTS": "msh/US/OH,"}):
            from config import Config
            cfg = Config()
            assert cfg.extra_mqtt_roots == ["msh/US/OH"]


class TestExtraMqttRootsSubscription:
    """Test that extra roots get subscribed on MQTT connect."""

    def _make_handler(self, extra_roots):
        """Create an MQTTHandler with given extra roots."""
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
        """Only the node's root topic is subscribed."""
        handler = self._make_handler([])
        mock_client = MagicMock()
        handler._on_connect(mock_client, None, None, 0)

        subscribe_calls = mock_client.subscribe.call_args_list
        assert len(subscribe_calls) == 1
        assert subscribe_calls[0] == call("msh/US/MI/2/e/#")

    def test_extra_roots_subscribed(self):
        """Extra roots are subscribed in addition to node root."""
        handler = self._make_handler(["msh/US/OH", "msh/US/CA"])
        mock_client = MagicMock()
        handler._on_connect(mock_client, None, None, 0)

        subscribe_calls = mock_client.subscribe.call_args_list
        topics = [c[0][0] for c in subscribe_calls]
        assert "msh/US/MI/2/e/#" in topics
        assert "msh/US/OH/2/e/#" in topics
        assert "msh/US/CA/2/e/#" in topics
        assert len(topics) == 3

    def test_duplicate_root_not_subscribed_twice(self):
        """If extra root matches node root, don't double-subscribe."""
        handler = self._make_handler(["msh/US/MI", "msh/US/OH"])
        mock_client = MagicMock()
        handler._on_connect(mock_client, None, None, 0)

        subscribe_calls = mock_client.subscribe.call_args_list
        topics = [c[0][0] for c in subscribe_calls]
        assert topics.count("msh/US/MI/2/e/#") == 1
        assert "msh/US/OH/2/e/#" in topics
        assert len(topics) == 2

    def test_failed_connect_no_extra_subscriptions(self):
        """Non-zero rc means no subscriptions at all."""
        handler = self._make_handler(["msh/US/OH"])
        mock_client = MagicMock()
        handler._on_connect(mock_client, None, None, 5)

        mock_client.subscribe.assert_not_called()
