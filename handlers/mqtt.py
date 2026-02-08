"""MQTT Handler for MQTT Proxy."""

import time
import logging
import ssl
import paho.mqtt.client as mqtt
from meshtastic import mesh_pb2

logger = logging.getLogger("mqtt-proxy.handlers.mqtt")

class MQTTHandler:
    """Handles MQTT connection and message processing."""

    def __init__(self, config, node_id, on_message_callback=None):
        self.config = config
        self.node_id = node_id
        self.client = None
        self.connected = False
        self.health_check_enabled = False
        self.last_activity = 0
        self.tx_count = 0
        self.tx_failures = 0
        self.rx_count = 0
        
        # Callback for when an MQTT message is received that needs to go to the radio
        # Signature: (topic, payload, retained)
        self.on_message_callback = on_message_callback
        
        self.current_mqtt_cfg = None

    def configure(self, node_mqtt_config):
        """Configure the MQTT client based on node settings."""
        self.current_mqtt_cfg = node_mqtt_config
        cfg = node_mqtt_config

        if not getattr(cfg, 'enabled', False):
            logger.warning("MQTT is NOT enabled in node config! Please enable it via 'meshtastic --set mqtt.enabled true'")
        
        # Safely get attributes with defaults
        mqtt_address = getattr(cfg, 'address', None)
        mqtt_port = int(getattr(cfg, 'port', 1883) or 1883)
        mqtt_username = getattr(cfg, 'username', None)
        mqtt_password = getattr(cfg, 'password', None)
        self.mqtt_root = getattr(cfg, 'root', 'msh')
        
        logger.info("Starting MQTT Client...")
        logger.info("  Server: %s:%d", mqtt_address, mqtt_port)
        logger.info("  User: %s", mqtt_username)
        logger.info("  Root Topic: %s", self.mqtt_root)
        
        # Client ID matching iOS pattern
        client_id = f"MeshtasticPythonMqttProxy-{self.node_id}"
        logger.info("Setting MQTT Client ID: %s", client_id)
        
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        if mqtt_username and mqtt_password:
            self.client.username_pw_set(mqtt_username, mqtt_password)
            
        # SSL/TLS Configuration
        use_ssl = getattr(cfg, 'tlsEnabled', False)
        if mqtt_address and "mqtt.meshtastic.org" in mqtt_address:
             use_ssl = True
             
        if use_ssl:
             logger.info("SSL/TLS Enabled")
             context = ssl.create_default_context()
             context.check_hostname = False
             context.verify_mode = ssl.CERT_NONE
             self.client.tls_set_context(context)
             
             if mqtt_port == 1883:
                 mqtt_port = 8883
                 logger.info("Switching to default SSL port: 8883")
        
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        # Store for connection
        self.mqtt_address = mqtt_address
        self.mqtt_port = mqtt_port

    def start(self):
        """Connect and start the MQTT loop."""
        if not self.client or not self.mqtt_address:
            logger.error("MQTT not configured, cannot start.")
            return

        try:
            if not self.mqtt_address or self.mqtt_address == "255.255.255.255":
                logger.warning("Invalid MQTT address in config: %s", self.mqtt_address)
                return

            # LWT (Last Will and Testament)
            if self.node_id:
               topic_stat = f"{self.mqtt_root}/2/stat/!{self.node_id}"
               self.client.will_set(topic_stat, payload="offline", retain=True)
            
            logger.info(f"Connecting to {self.mqtt_address}:{self.mqtt_port}...")
            self.client.connect(self.mqtt_address, self.mqtt_port, 60)
            self.client.loop_start()
            
        except Exception as e:
            logger.error("Failed to connect to MQTT broker: %s", e)

    def stop(self):
        """Stop the MQTT loop and disconnect."""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass

    def publish(self, topic, payload, retain=False):
        """Publish a message to MQTT."""
        if self.client:
            result = self.client.publish(topic, payload, retain=retain)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.tx_count += 1
                self.tx_failures = 0
                return True
            else:
                logger.warning("MQTT publish failed: rc=%s", result.rc)
                self.tx_failures += 1
                return False
        return False

    def _on_connect(self, client, userdata, flags, rc, props=None):
        logger.info("MQTT Connected with result code: %s", rc)
        if rc == 0:
            self.connected = True
            self.health_check_enabled = True
            self.last_activity = time.time()
            
            if self.current_mqtt_cfg:
                root_topic = self.mqtt_root
                
                # Publish Online Presence
                topic_stat = f"{root_topic}/2/stat/!{self.node_id}"
                client.publish(topic_stat, payload="online", retain=True)
                
                # Subscribe to ALL Encrypted Traffic
                topic_enc = f"{root_topic}/2/e/#"
                logger.info("Subscribing to Encrypted Wildcard: %s", topic_enc)
                client.subscribe(topic_enc)
        else:
            self.connected = False
            logger.error("MQTT Connect failed: %s", rc)

    def _on_disconnect(self, client, userdata, flags, rc, props=None):
        self.connected = False
        if rc != 0:
            logger.warning("MQTT Disconnected unexpectedly (rc=%s). Will attempt to reconnect.", rc)
        else:
            logger.info("MQTT Disconnected gracefully.")

    def _on_message(self, client, userdata, message):
        """Handle incoming MQTT messages."""
        try:
            # Skip stat messages
            if "/stat/" in message.topic:
                return

            # Loop protection
            if self.node_id and message.topic.endswith(f"!{self.node_id}"):
                 logger.debug("Ignoring own MQTT message (Loop protection): %s", message.topic)
                 return
             
            self.last_activity = time.time()
            self.rx_count += 1
            
            logger.info("MQTT->Node: Topic=%s Size=%d bytes Retained=%s", message.topic, len(message.payload), message.retain)
            
            if self.on_message_callback:
                self.on_message_callback(message.topic, message.payload, message.retain)
                
        except Exception as e:
            logger.error("Error handling MQTT message: %s", e)
