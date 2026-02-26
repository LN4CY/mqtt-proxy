"""Configuration management for MQTT Proxy."""
# Copyright (c) 2026 LN4CY
# This software is licensed under the MIT License. See LICENSE file for details.

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
        # Delay between consecutive messages sent to radio to prevent mesh network flooding
        # Typical transmission time is ~1ms, so 10ms provides a safe margin while maintaining responsiveness
        self.mesh_transmit_delay = float(os.environ.get("MESH_TRANSMIT_DELAY", "0.01"))  # 10ms default delay between packets
        
        # Max number of messages to keep in queue before dropping new ones
        self.mesh_max_queue_size = int(os.environ.get("MESH_MAX_QUEUE_SIZE", "100")) 
        
        # MQTT retained message handling
        # By default, skip retained messages to prevent startup floods with historical data
        self.mqtt_forward_retained = os.environ.get("MQTT_FORWARD_RETAINED", "false").lower() == "true"

# Global instance
cfg = Config()
