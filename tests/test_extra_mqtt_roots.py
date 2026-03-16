import os
import sys
import pytest
from unittest.mock import patch

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
