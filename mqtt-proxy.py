#!/usr/bin/env python3
# Copyright (c) 2026 LN4CY
# This software is licensed under the MIT License. See LICENSE file for details.
import time
import logging
import signal
import sys
import os
import argparse
from pubsub import pub

from config import cfg
from version import __version__
from handlers.mqtt import MQTTHandler
from handlers.meshtastic import create_interface
from handlers.node_tracker import PacketDeduplicator
from handlers.queue import MessageQueue

# Force unbuffered standard output and utf-8 encoding for real-time logging when run via spawn/exec
if sys.stdout and not sys.stdout.isatty():
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
if sys.stderr and not sys.stderr.isatty():
    sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
    level=cfg.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("mqtt-proxy")

class MQTTProxy:
    """
    Main application class for MQTT Proxy.
    Orchestrates the connection between Meshtastic and MQTT.
    """
    def __init__(self):
        self.running = True
        self.iface = None
        self.mqtt_handler = None
        
        # Initialize Packet Deduplicator (Loop Prevention)
        self.deduplicator = PacketDeduplicator()
        
        # Initialize Message Queue
        # We pass a lambda to always get the current interface instance
        self.message_queue = MessageQueue(cfg, lambda: self.iface)
        
        # State
        self.last_radio_activity = 0
        self.connection_lost_time = 0
        self.last_probe_time = 0
        self.last_status_log_time = 0

    def start(self):
        logger.info("🚀 MQTT Proxy v%s starting (interface: %s)...", __version__, cfg.interface_type.upper())
        
        # Start the message queue
        self.message_queue.start()

        # Subscribe to events
        pub.subscribe(self.on_connection, "meshtastic.connection.established")
        pub.subscribe(self.on_connection_lost, "meshtastic.connection.lost")
        
        # Signal handling
        signal.signal(signal.SIGINT, self.handle_sigint)
        signal.signal(signal.SIGTERM, self.handle_sigint)

        while self.running:
            self.iface = None
            try:
                # Create interface (this connects to the radio)
                self.iface = create_interface(cfg, self)
                logger.info("🔌 TCP/Serial connection initiated...")
                
                # Wait for node configuration (connection + config packet)
                self._wait_for_config()
                
                # Initialize MQTT after config is fully loaded
                self._init_mqtt()
                
                logger.info("✅ Node config fully loaded. Proxy active.")
                
                # Main Loop
                last_heartbeat = 0
                while self.running and self.iface:
                    time.sleep(1)
                    current_time = time.time()
                    
                    self._log_status(current_time)
                    health_ok, reasons = self._perform_health_check(current_time)
                    self._update_heartbeat(current_time, health_ok, reasons)
                    
            except Exception as e:
                logger.error("❌ Connection error: %s", e)
            finally:
                self._cleanup()

            if self.running:
                logger.info("⏳ Reconnecting in 5 seconds...")
                time.sleep(5)

    def _wait_for_config(self):
        """Wait for the node to provide its configuration."""
        wait_start = time.time()
        while self.running:
            if self.iface.localNode and self.iface.localNode.nodeNum != -1 and self.iface.localNode.moduleConfig:
                return
            
            if time.time() - wait_start > cfg.config_wait_timeout:
                logger.warning(f"⚠️ Connected but no config received for {cfg.config_wait_timeout}s...")
                # We don't exit, just warn, as sometimes config takes a while or is partial
            
            time.sleep(cfg.poll_interval)

    def on_connection(self, interface, **kwargs):
        """Callback when Meshtastic connection is established."""
        node = interface.localNode
        if not node:
            logger.warning("⚠️ No localNode available")
            return

        self.last_radio_activity = time.time()
        self.connection_lost_time = 0

        # Node ID
        try:
            if hasattr(node, "nodeId"):
                node_id = node.nodeId.replace('!', '')
            else:
                node_id = "{:08x}".format(node.nodeNum)
        except Exception as e:
            logger.error("❌ Error getting node ID: %s", e)
            node_id = "unknown"

        logger.info("📻 Connected to node !%s", node_id)

    def _init_mqtt(self):
        """Initialize and start the MQTT handler."""
        if not self.iface or not self.iface.localNode:
            logger.warning("⚠️ No interface or localNode for MQTT initialization")
            return

        node = self.iface.localNode
        
        # Determine Node ID
        try:
            if hasattr(node, "nodeId"):
                node_id = node.nodeId.replace('!', '')
            else:
                node_id = "{:08x}".format(node.nodeNum)
        except Exception:
            node_id = "unknown"

        # Cleanup existing handler if any
        if self.mqtt_handler:
            logger.info("🛑 Stopping old MQTT handler before restart...")
            self.mqtt_handler.stop()
            self.mqtt_handler = None

        # Initialize MQTT if config exists
        if node.moduleConfig and node.moduleConfig.mqtt:
            logger.info("🌐 Initializing MQTT Handler for node !%s...", node_id)
            self.mqtt_handler = MQTTHandler(cfg, node_id, self.on_mqtt_message_to_radio, deduplicator=self.deduplicator)
            self.mqtt_handler.configure(node.moduleConfig.mqtt)

            # Extract node channel names for extra-root crosstalk prevention
            self.mqtt_handler.node_channel_names = self._get_node_channel_names(node)
            if self.mqtt_handler.node_channel_names:
                logger.info("📋 Node channels for extra-root filtering: %s", self.mqtt_handler.node_channel_names)

            self.mqtt_handler.start()
        else:
            logger.warning("⚠️ No MQTT configuration found on node !%s!", node_id)

    @staticmethod
    def _get_node_channel_names(node):
        """Extract channel names from the node's channel list."""
        names = set()
        try:
            if not hasattr(node, 'channels') or not node.channels:
                return names
            for ch in node.channels:
                if ch.role == 0:  # DISABLED
                    continue
                name = ch.settings.name if ch.settings and ch.settings.name else None
                if not name and ch.role == 1:  # PRIMARY with empty name defaults to modem preset
                    name = "LongFast"  # Most common default
                if name:
                    names.add(name)
        except Exception as e:
            logger.warning("⚠️ Failed to read node channel names: %s", e)
        return names

    def on_connection_lost(self, interface, **kwargs):
        """Callback when connection to radio is lost."""
        if self.connection_lost_time > 0 and (time.time() - self.connection_lost_time < 2):
            return # Debounce

        logger.warning("⚠️ Meshtastic connection reported LOST!")
        self.connection_lost_time = time.time()
        
        # Cleanup will happen in main loop via _cleanup or forced restart in health check

    def on_mqtt_message_to_radio(self, topic, payload, retained):
        """Callback from MQTT Handler to send message to Radio."""
        # Queue the message instead of sending directly
        self.message_queue.put(topic, payload, retained)

    def _perform_health_check(self, current_time):
        """Check system health."""
        health_ok = True
        reasons = []

        # 1. MQTT Check
        if self.mqtt_handler:
            if self.mqtt_handler.health_check_enabled and not self.mqtt_handler.connected:
                health_ok = False
                reasons.append("MQTT disconnected")
            
            # 4. MQTT TX Failures (Ensure we use integers for comparison)
            tx_fails = getattr(self.mqtt_handler, 'tx_failures', 0)
            if isinstance(tx_fails, (int, float)) and tx_fails > 5:
                health_ok = False
                reasons.append(f"Recurring MQTT Publish Failures ({tx_fails})")
        elif self.iface and self.iface.localNode and self.iface.localNode.moduleConfig:
            # We have config but no handler? 
            if self.iface.localNode.moduleConfig.mqtt and getattr(self.iface.localNode.moduleConfig.mqtt, 'enabled', False):
                 health_ok = False
                 reasons.append("MQTT handler uninitialized")

        # 2. Connection Lost Watchdog
        if self.connection_lost_time > 0:
            if current_time - self.connection_lost_time > 60:
                logger.error("🚨 Connection LOST for >60s. Forcing restart...")
                sys.exit(1)

        # 3. Radio Watchdog
        if self.last_radio_activity > 0:
            time_since_radio = current_time - self.last_radio_activity
            if time_since_radio > cfg.health_check_activity_timeout:
                # Silence...
                time_since_probe = current_time - self.last_probe_time
                if time_since_probe > 40:
                    logger.warning(f"📡 Radio silent for {int(time_since_radio)}s. Sending active probe...")
                    try:
                        self.last_probe_time = current_time
                        if self.iface:
                             self.iface.sendPosition()
                    except Exception as e:
                        logger.warning("⚠️ Failed to probe: %s", e)
                elif time_since_probe > 30:
                     health_ok = False
                     reasons.append(f"Radio silent (Probed {int(time_since_probe)}s ago - NO REPLY)")

        return health_ok, reasons

    def _log_status(self, current_time):
        if current_time - self.last_status_log_time > cfg.health_check_status_interval:
            time_since_radio = current_time - self.last_radio_activity if self.last_radio_activity > 0 else -1
            
            mqtt_connected = False
            time_since_mqtt = -1
            if self.mqtt_handler:
                mqtt_connected = getattr(self.mqtt_handler, 'connected', False)
                mqtt_active = getattr(self.mqtt_handler, 'last_activity', 0)
                if isinstance(mqtt_active, (int, float)) and mqtt_active > 0:
                    time_since_mqtt = current_time - mqtt_active
            
            logger.info("📊 === MQTT Proxy Status ===")
            logger.info("  MQTT Connected: %s", mqtt_connected)
            logger.info("  Radio Activity: %s ago", f"{int(time_since_radio)}s" if time_since_radio >= 0 else "never")
            logger.info("  MQTT Activity:  %s ago", f"{int(time_since_mqtt)}s" if time_since_mqtt >= 0 else "never")
            self.last_status_log_time = current_time

    def _update_heartbeat(self, current_time, health_ok, reasons):
        try:
            if health_ok:
                with open("/tmp/healthy", "w") as f:
                    f.write(str(current_time))
            else:
                if os.path.exists("/tmp/healthy"):
                    os.remove("/tmp/healthy")
                logger.error("❌ Health check FAILED: %s. Exiting...", ", ".join(reasons))
                sys.exit(1)
        except Exception as e:
            pass

    def _cleanup(self):
        if self.mqtt_handler:
            self.mqtt_handler.stop()
        if self.iface:
            try:
                self.iface.close()
            except: pass
        if getattr(self, 'message_queue', None):
            self.message_queue.stop()

    def handle_sigint(self, sig, frame):
        logger.info("🛑 Received Ctrl+C, shutting down...")
        self.running = False
        self._cleanup()

if __name__ == "__main__":
    # If the user explicitly asks for help on the main script, show full usage
    # We do a quick check here before the main proxy loops start.
    parser = argparse.ArgumentParser(description=f"Meshtastic MQTT Proxy v{__version__}")
    parser.add_argument('--version', action='version', version=f'%(prog)s v{__version__}')
    parser.add_argument("--interface", type=str, help="Interface type: 'tcp' or 'serial' (default: tcp)")
    parser.add_argument("--tcp-host", type=str, help="TCP hostname or IP address (default: localhost)")
    parser.add_argument("--tcp-port", type=int, help="TCP port number (default: 4403)")
    parser.add_argument("--serial-port", type=str, help="Serial device path (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("--log-level", type=str, help="Logging level (e.g. INFO, DEBUG)")
    # We don't need to save the args here, config.py already parsed them using parse_known_args
    parser.parse_known_args()

    app = MQTTProxy()
    app.start()
