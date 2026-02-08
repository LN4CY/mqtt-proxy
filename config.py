"""Configuration management for MQTT Proxy."""

import os
import logging
import sys

logger = logging.getLogger("mqtt-proxy.config")

class Config:
    """Configuration manager for MQTT Proxy."""
    
    def __init__(self):
        # logging setup
        self.log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
        self.log_level = getattr(logging, self.log_level_str, logging.INFO)

        # Interface configuration
        self.interface_type = os.environ.get("INTERFACE_TYPE", "tcp").lower()

        # TCP configuration
        self.tcp_node_host = os.environ.get("TCP_NODE_HOST", "localhost")
        self.tcp_node_port = int(os.environ.get("TCP_NODE_PORT", "4403"))

        # Serial configuration
        self.serial_port = os.environ.get("SERIAL_PORT", "/dev/ttyUSB0")

        # BLE configuration
        self.ble_address = os.environ.get("BLE_ADDRESS", "")

        # Timeout configurations (in seconds)
        self.tcp_timeout = int(os.environ.get("TCP_TIMEOUT", "300"))  # 5 minutes default
        self.config_wait_timeout = int(os.environ.get("CONFIG_WAIT_TIMEOUT", "60"))  # 1 minute default
        self.poll_interval = int(os.environ.get("POLL_INTERVAL", "1"))  # 1 second default

        # Health check configurations
        self.health_check_activity_timeout = int(os.environ.get("HEALTH_CHECK_ACTIVITY_TIMEOUT", "300"))  # 5 minutes default
        # Default to half of timeout
        self.health_check_probe_interval = int(os.environ.get("HEALTH_CHECK_PROBE_INTERVAL", str(self.health_check_activity_timeout // 2))) 
        self.health_check_status_interval = int(os.environ.get("HEALTH_CHECK_STATUS_INTERVAL", "60"))  # 60 seconds default
        self.mqtt_reconnect_delay = int(os.environ.get("MQTT_RECONNECT_DELAY", "5"))  # 5 seconds default
        
        # Transmission configuration
        self.mesh_transmit_delay = float(os.environ.get("MESH_TRANSMIT_DELAY", "0.5"))  # 0.5 seconds default delay between packets

# Global instance
cfg = Config()
