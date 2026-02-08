#!/usr/bin/env python3
import time
import logging
import signal
from pubsub import pub

from config import cfg
from handlers.mqtt import MQTTHandler
from handlers.meshtastic import create_interface
from handlers.queue import MessageQueue

# Configure logging
logging.basicConfig(
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
        
        # Initialize Message Queue
        # We pass a lambda to always get the current interface instance
        self.message_queue = MessageQueue(cfg, lambda: self.iface)
        
        # State
        self.last_radio_activity = 0
        self.connection_lost_time = 0
        self.last_probe_time = 0
        self.last_status_log_time = 0

    def start(self):
        logger.info("MQTT Proxy starting (interface: %s)...", cfg.interface_type.upper())
        
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
                logger.info("TCP/Serial connection initiated...")
                
                # Wait for node configuration (connection + config packet)
                self._wait_for_config()
                
                logger.info("Node config fully loaded. Proxy active.")
                
                # Main Loop
                last_heartbeat = 0
                while self.running and self.iface:
                    time.sleep(1)
                    current_time = time.time()
                    
                    self._log_status(current_time)
                    health_ok, reasons = self._perform_health_check(current_time)
                    self._update_heartbeat(current_time, health_ok, reasons)
                    
            except Exception as e:
                logger.error("Connection error: %s", e)
            finally:
                self._cleanup()

            if self.running:
                logger.info("Reconnecting in 5 seconds...")
                time.sleep(5)

    def _wait_for_config(self):
        """Wait for the node to provide its configuration."""
        wait_start = time.time()
        while self.running:
            if self.iface.localNode and self.iface.localNode.nodeNum != -1 and self.iface.localNode.moduleConfig:
                return
            
            if time.time() - wait_start > cfg.config_wait_timeout:
                logger.warning(f"Connected but no config received for {cfg.config_wait_timeout}s...")
                # We don't exit, just warn, as sometimes config takes a while or is partial
            
            time.sleep(cfg.poll_interval)

    def on_connection(self, interface, **kwargs):
        """Callback when Meshtastic connection is established."""
        node = interface.localNode
        if not node:
            logger.warning("No localNode available")
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
            logger.error("Error getting node ID: %s", e)
            node_id = "unknown"

        logger.info("Connected to node !%s", node_id)

        # Initialize MQTT
        if node.moduleConfig and node.moduleConfig.mqtt:
            self.mqtt_handler = MQTTHandler(cfg, node_id, self.on_mqtt_message_to_radio)
            self.mqtt_handler.configure(node.moduleConfig.mqtt)
            self.mqtt_handler.start()
        else:
            logger.warning("No MQTT configuration found on node!")

    def on_connection_lost(self, interface, **kwargs):
        """Callback when connection to radio is lost."""
        if self.connection_lost_time > 0 and (time.time() - self.connection_lost_time < 2):
            return # Debounce

        logger.warning("Meshtastic connection reported LOST!")
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
        if self.mqtt_handler and self.mqtt_handler.health_check_enabled and not self.mqtt_handler.connected:
            health_ok = False
            reasons.append("MQTT disconnected")

        # 2. Connection Lost Watchdog
        if self.connection_lost_time > 0:
            if current_time - self.connection_lost_time > 60:
                logger.error("Connection LOST for >60s. Forcing restart...")
                import sys
                sys.exit(1)

        # 3. Radio Watchdog
        if self.last_radio_activity > 0:
            time_since_radio = current_time - self.last_radio_activity
            if time_since_radio > cfg.health_check_activity_timeout:
                # Silence...
                time_since_probe = current_time - self.last_probe_time
                if time_since_probe > 40:
                    logger.warning(f"Radio silent for {int(time_since_radio)}s. Sending active probe...")
                    try:
                        self.last_probe_time = current_time
                        if self.iface:
                             self.iface.sendPosition()
                    except Exception as e:
                        logger.warning("Failed to probe: %s", e)
                elif time_since_probe > 30:
                     health_ok = False
                     reasons.append(f"Radio silent (Probed {int(time_since_probe)}s ago - NO REPLY)")

        # 4. MQTT TX Failures
        if self.mqtt_handler and self.mqtt_handler.tx_failures > 5:
            health_ok = False
            reasons.append(f"Recurring MQTT Publish Failures ({self.mqtt_handler.tx_failures})")

        return health_ok, reasons

    def _log_status(self, current_time):
        if current_time - self.last_status_log_time > cfg.health_check_status_interval:
            time_since_radio = current_time - self.last_radio_activity if self.last_radio_activity > 0 else -1
            mqtt_active = self.mqtt_handler.last_activity if self.mqtt_handler else 0
            time_since_mqtt = current_time - mqtt_active if mqtt_active > 0 else -1
            
            logger.info("=== MQTT Proxy Status ===")
            logger.info("  MQTT Connected: %s", self.mqtt_handler.connected if self.mqtt_handler else False)
            logger.info("  Radio Activity: %s ago", f"{int(time_since_radio)}s" if time_since_radio >= 0 else "never")
            logger.info("  MQTT Activity:  %s ago", f"{int(time_since_mqtt)}s" if time_since_mqtt >= 0 else "never")
            self.last_status_log_time = current_time

    def _update_heartbeat(self, current_time, health_ok, reasons):
        import os
        try:
            if health_ok:
                with open("/tmp/healthy", "w") as f:
                    f.write(str(current_time))
            else:
                if os.path.exists("/tmp/healthy"):
                    os.remove("/tmp/healthy")
                logger.error("Health check FAILED: %s. Exiting...", ", ".join(reasons))
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
        logger.info("Received Ctrl+C, shutting down...")
        self.running = False
        self._cleanup()

if __name__ == "__main__":
    app = MQTTProxy()
    app.start()
