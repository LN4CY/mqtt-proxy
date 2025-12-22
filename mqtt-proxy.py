#!/usr/bin/env python3
import os
import time
import logging
import json
# import base64 # Unused
from pubsub import pub

import paho.mqtt.client as mqtt

import meshtastic
from meshtastic.tcp_interface import TCPInterface
from meshtastic.serial_interface import SerialInterface
# from meshtastic.ble_interface import BLEInterface  # BLE requires custom bleak implementation for Docker compatibility
from meshtastic import mesh_pb2, mqtt_pb2
# from google.protobuf.json_format import ParseDict # Unused
from google.protobuf import json_format
from google.protobuf.message import DecodeError

# Configure logging
log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("mqtt-proxy")

# Interface configuration
INTERFACE_TYPE = os.environ.get("INTERFACE_TYPE", "tcp").lower()

# TCP configuration
TCP_NODE_HOST = os.environ.get("TCP_NODE_HOST", "localhost")
TCP_NODE_PORT = int(os.environ.get("TCP_NODE_PORT", "4403"))

# Serial configuration
SERIAL_PORT = os.environ.get("SERIAL_PORT", "/dev/ttyUSB0")

# BLE configuration
BLE_ADDRESS = os.environ.get("BLE_ADDRESS", "")

# Timeout configurations (in seconds)
TCP_TIMEOUT = int(os.environ.get("TCP_TIMEOUT", "300"))  # 5 minutes default
CONFIG_WAIT_TIMEOUT = int(os.environ.get("CONFIG_WAIT_TIMEOUT", "60"))  # 1 minute default
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "1"))  # 1 second default

# Health check configurations
HEALTH_CHECK_ACTIVITY_TIMEOUT = int(os.environ.get("HEALTH_CHECK_ACTIVITY_TIMEOUT", "300"))  # 5 minutes default
HEALTH_CHECK_PROBE_INTERVAL = int(os.environ.get("HEALTH_CHECK_PROBE_INTERVAL", str(HEALTH_CHECK_ACTIVITY_TIMEOUT // 2))) # Default to half of timeout
HEALTH_CHECK_STATUS_INTERVAL = int(os.environ.get("HEALTH_CHECK_STATUS_INTERVAL", "60"))  # 60 seconds default
MQTT_RECONNECT_DELAY = int(os.environ.get("MQTT_RECONNECT_DELAY", "5"))  # 5 seconds default


running = True
iface = None
mqtt_client = None

# We will store the MQTT config to use in callbacks
current_mqtt_cfg = None
# To store the node ID for topic construction
my_node_id = None

# Health monitoring state
mqtt_connected = False
last_mqtt_tx_time = 0  # Last time we published to MQTT
last_mqtt_rx_time = 0  # Last time we received from MQTT
mqtt_tx_count = 0
mqtt_rx_count = 0
last_status_log_time = 0
last_probe_time = 0

# ---------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------
import signal

def handle_sigint(sig, frame):
    global running
    logger.info("Received Ctrl+C, shutting down...")
    running = False
    if iface:
        try: 
            iface.close()
        except Exception:
            pass
    if mqtt_client:
        try:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        except Exception:
            pass

signal.signal(signal.SIGINT, handle_sigint)
signal.signal(signal.SIGTERM, handle_sigint)

# ---------------------------------------------------------------------
# MQTT Callbacks
# ---------------------------------------------------------------------
def on_mqtt_connect(client, userdata, flags, rc, props=None):
    global mqtt_connected, last_mqtt_rx_time
    logger.info("MQTT Connected with result code: %s", rc)
    if rc == 0:
        mqtt_connected = True
        last_mqtt_rx_time = time.time()  # Reset activity timer on connect
    if rc == 0 and current_mqtt_cfg:
        root_topic = current_mqtt_cfg.root if current_mqtt_cfg.root else "msh"
        # region = "US" # Removed to avoid duplication if root_topic already has region
        
        # 0. Publish Online Presence
        topic_stat = f"{root_topic}/2/stat/!{my_node_id}"
        client.publish(topic_stat,payload="online", retain=True)
        
        # 1. Subscribe to EVERYTHING (Wildcard) as requested
        # Mimics iOS app "Transparent Proxy" behavior
        topic_wildcard = f"{root_topic}/#"
        logger.info("Subscribing to Wildcard Topic: %s", topic_wildcard)
        client.subscribe(topic_wildcard)
        
    else:
        mqtt_connected = False
        logger.error("MQTT Connect failed: %s", rc)

def on_mqtt_disconnect(client, userdata, rc, props=None):
    """Called when MQTT client disconnects"""
    global mqtt_connected
    mqtt_connected = False
    if rc != 0:
        logger.warning("MQTT Disconnected unexpectedly (rc=%s). Will attempt to reconnect.", rc)
    else:
        logger.info("MQTT Disconnected gracefully.")

def on_mqtt_message_callback(client, userdata, message):
    """
    Called when a message is received from the MQTT broker.
    We need to send this packet to the radio via the Interface.
    """
    global last_mqtt_rx_time, mqtt_rx_count
    try:
        if iface is None:
            logger.warning("Ignoring MQTT message: Interface not ready yet.")
            return

        # Skip stat messages (status updates)
        if "/stat/" in message.topic:
            return

        # Loop protection: Ignore messages from our own node ID
        # Topic format: msh/REGION/2/e/CHANNEL/!NODEID
        if my_node_id:
             # Check for !NODEID at end of topic
             if message.topic.endswith(f"!{my_node_id}"):
                 logger.debug("Ignoring own MQTT message (Loop protection): %s", message.topic)
                 return

            
        # Update activity tracking
        last_mqtt_rx_time = time.time()
        mqtt_rx_count += 1
        
        logger.info("MQTT->Node: Topic=%s Size=%d bytes", message.topic, len(message.payload))
        
        # Forward ALL MQTT messages directly to node as mqttClientProxyMessage
        # The node's firmware will handle parsing, channel mapping, and filtering
        mqtt_proxy_msg = mesh_pb2.MqttClientProxyMessage()
        mqtt_proxy_msg.topic = message.topic
        mqtt_proxy_msg.data = message.payload
        mqtt_proxy_msg.retained = False  # Can be enhanced to detect retained messages
        
        to_radio = mesh_pb2.ToRadio()
        to_radio.mqttClientProxyMessage.CopyFrom(mqtt_proxy_msg)
        
        # Send via the interface's _sendToRadioImpl method (matches iOS app implementation)
        # Pass the protobuf object directly, not serialized bytes
        iface._sendToRadioImpl(to_radio)
        
    except Exception as e:
        logger.error("Error handling MQTT message: %s", e)

# ---------------------------------------------------------------------
# Meshtastic Callbacks
# ---------------------------------------------------------------------
def on_connection(interface, **kwargs):
    """Called when the TCP node connection is established"""
    global mqtt_client, current_mqtt_cfg, my_node_id
    
    node = interface.localNode
    if not node:
        logger.warning("No localNode available")
        return

    # Log connection with node ID in hex format (e.g. !10ae8907)
    node_id_hex = "!{:08x}".format(node.nodeNum)
    logger.info("Connected to node %s", node_id_hex)
    
    # helper to get node ID string (e.g. !1234abcd) -> 1234abcd
    try:
        if hasattr(node, "nodeId"):
            my_node_id = node.nodeId.replace('!', '')
        else:
            # Fallback to hex of nodeNum
            my_node_id = "{:08x}".format(node.nodeNum)
    except Exception as e:
        logger.error("Error getting node ID: %s", e)
        my_node_id = "unknown"

    # Log available channels for debugging
    if node.channels:
        logger.info("Local Node Channels:")
        for c in node.channels:
            c_name = c.settings.name if c.settings else "<no-settings>"
            c_role = c.role if hasattr(c, "role") else "?"
            logger.info("  Index %d: Name='%s' Role=%s", c.index, c_name, c_role)


    # MQTT configuration
    if node.moduleConfig and node.moduleConfig.mqtt:
        cfg = node.moduleConfig.mqtt
        current_mqtt_cfg = cfg
        
        if not getattr(cfg, 'enabled', False):
            logger.warning("MQTT is NOT enabled in node config! Please enable it via 'meshtastic --set mqtt.enabled true'")
            # We continue anyway, as the user might want us to act as the MQTT client despite node settings,
            # but usually the node won't send us anything if disabled.
        
        # Safely get attributes with defaults
        mqtt_address = getattr(cfg, 'address', None)
        mqtt_port = int(getattr(cfg, 'port', 1883) or 1883)
        mqtt_username = getattr(cfg, 'username', None)
        mqtt_password = getattr(cfg, 'password', None)
        mqtt_root = getattr(cfg, 'root', 'msh')
    else:
        logger.warning("No MQTT configuration found on node! Please configure MQTT settings on the device.")
        return
        
    logger.info("Starting MQTT Client...")
    logger.info("  Server: %s:%d", mqtt_address, mqtt_port)
    logger.info("  User: %s", mqtt_username)
    logger.info("  Root Topic: %s", mqtt_root)
    
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if mqtt_username and mqtt_password:
        mqtt_client.username_pw_set(mqtt_username, mqtt_password)
        
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_disconnect = on_mqtt_disconnect
    mqtt_client.on_message = on_mqtt_message_callback
    
    try:
        if not mqtt_address or mqtt_address == "255.255.255.255":
            logger.warning("Invalid MQTT address in config: %s", mqtt_address)
            return

        # LWT (Last Will and Testament) for Presence
        # Topic: msh/US/2/stat/!NODEID
        # We need to pre-calculate this, but my_node_id might be unknown until TCP connect?
        # Actually, we connect TCP first (in main), getting my_node_id, THEN we parse config, THEN we start MQTT.
        # So my_node_id should be available.
        
        if my_node_id:
           topic_stat = f"{mqtt_root}/2/stat/!{my_node_id}"
           mqtt_client.will_set(topic_stat, payload="offline", retain=True)
        
        mqtt_client.connect(mqtt_address, mqtt_port, 60)
        mqtt_client.loop_start()
        
        if my_node_id:
            # Publish initial online status
            # We do this after loop_start/connect, best effort.
            # Ideally in on_connect, but we need client context there. 
            # Let's do it here or relying on on_connect?
            # on_connect has the client, we can publish there if we pass the topic.
            pass
        
    except Exception as e:
        logger.error("Failed to connect to MQTT broker: %s", e)

def on_connection_lost(interface, **kwargs):
    """Called when the Meshtastic connection occurs"""
    logger.warning("Meshtastic connection reported LOST!")
    # We can't easily force the main thread to restart, but we can rely on iface.close() happening?
    # Or just let the main loop eventually catch it? 
    # Usually connection lost implies we should close and retry.
    if iface:
        try:
           iface.close()
        except: pass

# Track last packet time for activity monitoring
last_packet_time = 0

def on_receive(packet, interface):
    """
    DEPRECATED: This callback is no longer used.
    The node now sends mqttClientProxyMessage directly (handled in _handleFromRadio).
    Keeping this function to avoid breaking the event subscription, but it does nothing.
    """
    global last_packet_time
    last_packet_time = time.time()
    # return  # Early return - node uses mqttClientProxyMessage now
    
    try:
        if not mqtt_client:
            return
            
        mesh_packet = packet
        # Validation: Ensure it is a protobuf
        if not hasattr(mesh_packet, "SerializeToString"):
             logger.warning("Received packet is not a protobuf object: %s", type(packet))
             return

        # Determine Channel Name
        chan_name = None # Default (was LongFast, but that breaks fallback logic)
        try:
            # mesh_packet.channel is an int index
            idx = mesh_packet.channel
            node = iface.localNode
            if node and node.channels:
                for c in node.channels:
                    # c.index might be missing if it's default? usually it's there.
                    if c.index == idx and c.settings and c.settings.name:
                        chan_name = c.settings.name
                        break
        except Exception as e:
            logger.warning("Could not resolve channel name: %s", e)

        if chan_name is None:
             # Fallback: Use Index "Channel_N" instead of flattening to LongFast
             # This preserves uniqueness if name is missing.
             if idx == 0:
                 chan_name = "LongFast"
             else:
                 chan_name = f"Chan_{idx}"
                 logger.warning("Channel Name lookup failed for Index %d. Using '%s'", idx, chan_name)

        # Create ServiceEnvelope
        se = mqtt_pb2.ServiceEnvelope()
        se.packet.CopyFrom(mesh_packet)
        se.channel_id = chan_name
        # Use the actual node ID as gateway_id to match virtual node behavior
        # MeshMonitor's virtual node uses !10ae8907, so we must match it
        se.gateway_id = f"!{my_node_id}" 
        
        # Topic: msh/REGION/2/[sub]/CHANNEL/!NODEID
        from_node_num = getattr(mesh_packet, "from")
        from_node_hex = "!{:08x}".format(from_node_num)
        
        root_topic = current_mqtt_cfg.root if current_mqtt_cfg.root else "msh"
        
        # Determine Subtopic and Retain Policy
        # Always use 'e' (encrypted) topic to match iOS proxy behavior
        # MeshMonitor expects packets on /e/ even if they contain decoded data
        sub_topic = "e"
        should_retain = False
        
        # If we have decoded info, we can be more specific
        if hasattr(mesh_packet, "decoded") and mesh_packet.decoded.portnum:
            pnum = mesh_packet.decoded.portnum
            
            # Debug: what is the actual pnum integer?
            logger.debug("Packet Pnum: %s (Type: %s)", pnum, type(pnum))
            
            # Constants from PortNum enum (Verified from logs/proto)
            # NODEINFO_APP = 4
            # POSITION_APP = 3
            # TELEMETRY_APP = 67
            # NEIGHBORINFO_APP = 70
            if pnum in [4, 3, 67, 70]:
                should_retain = True
                # Optional: Use 'map' subtopic for Position/NodeInfo? 
                # If iOS uses 'e', we stick to 'e'.
        
        # Security/Optimization: Strip the 'decoded' (plaintext) field before publishing.
        # We only want to send the encrypted 'payload' to the MQTT mesh, matching "Over-the-Air" behavior.
        # Logic matches iOS/Android apps which don't leak plaintext to MQTT.
        se.packet.ClearField("decoded") # Re-enabled to match iOS proxy behavior

        topic = f"{root_topic}/2/{sub_topic}/{chan_name}/{from_node_hex}"
        
        payload = se.SerializeToString()
        logger.debug("Publishing to MQTT: Topic=%s (Size=%d bytes) [From=%s Ch=%s] Retain=%s", 
            topic, len(payload), from_node_hex, chan_name, should_retain)
        
        result = mqtt_client.publish(topic, payload, retain=should_retain)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
             # Update activity tracking for health check
             global last_mqtt_tx_time, mqtt_tx_count
             last_mqtt_tx_time = time.time()
             mqtt_tx_count += 1
        else:
             logger.warning("MQTT publish failed: rc=%s", result.rc)

    except Exception as e:
        logger.error("Error processing packet for MQTT: %s", e)


# ---------------------------------------------------------------------
# Custom Interface Classes for Raw Packet Interception
# ---------------------------------------------------------------------
class MQTTProxyMixin:
    """
    Mixin class that provides common _handleFromRadio() logic for all interface types.
    This intercepts mqttClientProxyMessage from the node and publishes to MQTT.
    """
    def _handleFromRadio(self, fromRadio):
        """
        Override internal library method to capture raw protobufs.
        fromRadio is a mesh_pb2.FromRadio protobuf object OR bytes depending on version.
        """
        try:
            logger.debug("RX Object Type: %s", type(fromRadio))

            # Parse the bytes into a FromRadio object for our inspection
            # Handle both bytes and already-parsed protobuf objects
            if isinstance(fromRadio, bytes):
                # Debug logging for raw bytes
                logger.debug("Raw FromRadio bytes (%d): %s", len(fromRadio), fromRadio.hex())
                decoded = mesh_pb2.FromRadio()
                decoded.ParseFromString(fromRadio)
            else:
                # Already a protobuf object
                decoded = fromRadio
            
            # DEBUG: Log every received packet type
            logger.debug("RX FromRadio: Fields=%s", decoded.ListFields())

            # Check for mqttClientProxyMessage (node wants to publish to MQTT)
            if decoded.HasField("mqttClientProxyMessage"):
                global last_mqtt_tx_time, mqtt_tx_count
                mqtt_msg = decoded.mqttClientProxyMessage
                logger.info("Node->MQTT: Topic=%s Size=%d bytes Retained=%s", 
                           mqtt_msg.topic, len(mqtt_msg.data), mqtt_msg.retained)
                if mqtt_client:
                    result = mqtt_client.publish(mqtt_msg.topic, mqtt_msg.data, retain=mqtt_msg.retained)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        last_mqtt_tx_time = time.time()
                        mqtt_tx_count += 1
                    else:
                        logger.warning("MQTT publish failed: rc=%s", result.rc)
            
            # Also handle regular mesh packets for backward compatibility
            elif decoded.packet and decoded.packet.to:
                # This is a MeshPacket. Publish it raw.
                # using a custom topic 'proxy.receive.raw'
                logger.debug("RX MeshPacket (not proxied): To=%s From=%s", decoded.packet.to, getattr(decoded.packet, "from"))
                pub.sendMessage("proxy.receive.raw", packet=decoded.packet, interface=self)
            else:
                 logger.debug("RX Other (ignored): %s", decoded)

        except Exception as e:
            # Expected protobuf parsing errors - log at debug level
            logger.debug("Error in MQTT proxy interception: %s", e)

        # Always call super to let the library maintain its state (nodes, peers, etc.)
        try:
            super()._handleFromRadio(fromRadio)
        except DecodeError as e:
            # Expected protobuf decode errors - log at debug level
            logger.debug("Protobuf Decode Error (suppressed): %s", e)
        except Exception as e:
            # Unexpected errors in stream processing - log at debug level
            logger.debug("Error in StreamInterface processing: %s", e)


class RawTCPInterface(MQTTProxyMixin, TCPInterface):
    """TCP interface with MQTT proxy support"""
    pass


class RawSerialInterface(MQTTProxyMixin, SerialInterface):
    """Serial interface with MQTT proxy support"""
    pass


# BLE interface commented out - requires custom bleak implementation for Docker compatibility
# See meshtastic-ble-bridge for reference implementation using bleak library
# class RawBLEInterface(MQTTProxyMixin, BLEInterface):
#     """BLE interface with MQTT proxy support"""
#     pass


# ---------------------------------------------------------------------
# Interface Factory
# ---------------------------------------------------------------------
def create_interface():
    """
    Factory function to create the appropriate interface based on INTERFACE_TYPE.
    Returns the configured interface instance.
    """
    interface_type = INTERFACE_TYPE
    
    logger.info("Creating %s interface...", interface_type.upper())
    
    if interface_type == "tcp":
        return RawTCPInterface(
            TCP_NODE_HOST,
            portNumber=TCP_NODE_PORT,
            timeout=TCP_TIMEOUT
        )
    elif interface_type == "serial":
        return RawSerialInterface(SERIAL_PORT)
    # elif interface_type == "ble":
    #     # BLE requires custom bleak implementation for Docker compatibility
    #     if not BLE_ADDRESS:
    #         raise ValueError("BLE_ADDRESS must be set when using BLE interface")
    #     return RawBLEInterface(BLE_ADDRESS)
    else:
        raise ValueError(f"Unknown interface type: {interface_type}. Must be 'tcp' or 'serial' (BLE not yet supported)")

def main():
    logger.info("MQTT Proxy starting (interface: %s)...", INTERFACE_TYPE.upper())
    
    # Subscribe to events once
    pub.subscribe(on_connection, "meshtastic.connection.established")
    pub.subscribe(on_connection_lost, "meshtastic.connection.lost")
    # pub.subscribe(on_receive, "meshtastic.receive") # Standard event (dict) - Unsubscribing
    pub.subscribe(on_receive, "proxy.receive.raw")    # Custom event (protobuf)
    
    while running:
        global iface, last_probe_time
        iface = None
        try:
            # Use factory to create appropriate interface
            iface = create_interface()
            
            logger.info("TCP <-> MQTT transparent proxy connected")

            # Post-connection validation check
            # Even if connected, we might have an incomplete node object initially
            # Wait for valid node ID
            wait_start = time.time()
            while running:
                 if iface.localNode and iface.localNode.nodeNum != -1 and iface.localNode.moduleConfig:
                     break
                 
                 if time.time() - wait_start > CONFIG_WAIT_TIMEOUT and not iface.localNode:
                      # If after timeout we still don't have basic config, something is wrong with the stream
                      logger.warning(f"Connected but no config received for {CONFIG_WAIT_TIMEOUT}s...")
                 
                 time.sleep(POLL_INTERVAL)
                 
            logger.info("Node config fully loaded. Proxy active.")

            # Blocking wait while connected
            last_heartbeat = 0
            while running:
                 time.sleep(1)
                 
                 current_time = time.time()
                 
                 # Periodic status logging
                 global last_status_log_time
                 if current_time - last_status_log_time > HEALTH_CHECK_STATUS_INTERVAL:
                     time_since_tx = current_time - last_mqtt_tx_time if last_mqtt_tx_time > 0 else -1
                     time_since_rx = current_time - last_mqtt_rx_time if last_mqtt_rx_time > 0 else -1
                     
                     logger.info("=== MQTT Proxy Status ===")
                     logger.info("  MQTT Connected: %s", mqtt_connected)
                     logger.info("  Messages TX: %d (last: %s ago)", 
                                mqtt_tx_count, 
                                f"{int(time_since_tx)}s" if time_since_tx >= 0 else "never")
                     logger.info("  Messages RX: %d (last: %s ago)", 
                                mqtt_rx_count,
                                f"{int(time_since_rx)}s" if time_since_rx >= 0 else "never")
                     last_status_log_time = current_time
                 
                 # Health check logic
                 health_ok = True
                 health_reasons = []
                 
                 # Check 1: MQTT must be connected
                 if not mqtt_connected:
                     health_ok = False
                     health_reasons.append("MQTT not connected")
                 
                 # Check 2: Must have recent activity (either TX or RX)
                 # Allow some initial grace period before first message
                 if last_mqtt_tx_time > 0 or last_mqtt_rx_time > 0:
                     last_activity = max(last_mqtt_tx_time, last_mqtt_rx_time)
                     time_since_activity = current_time - last_activity
                     
                     if time_since_activity > HEALTH_CHECK_ACTIVITY_TIMEOUT:
                         health_ok = False
                         health_reasons.append(f"No activity for {int(time_since_activity)}s (timeout: {HEALTH_CHECK_ACTIVITY_TIMEOUT}s)")
                     elif time_since_activity > HEALTH_CHECK_ACTIVITY_TIMEOUT * 0.8:
                         # Warning when approaching timeout (80% threshold)
                         logger.warning("Health check warning: No MQTT activity for %ds (timeout in %ds)", 
                                      int(time_since_activity),
                                      int(HEALTH_CHECK_ACTIVITY_TIMEOUT - time_since_activity))
                 
                 # Active Probe Logic
                 # If idle for more than probe interval, send a dummy text message to the node
                 # This should trigger a response (packet) from the node, confirming the serial/TCP link is alive
                 # and that the node is capable of processing messages.
                 if last_mqtt_tx_time > 0 or last_mqtt_rx_time > 0:
                      last_activity = max(last_mqtt_tx_time, last_mqtt_rx_time)
                      time_since_activity = current_time - last_activity
                      
                      # Only probe if we haven't probed recently (to avoid flooding)
                      if time_since_activity > HEALTH_CHECK_PROBE_INTERVAL and (current_time - last_probe_time > HEALTH_CHECK_PROBE_INTERVAL):
                          try:
                              logger.info("Sending active probe (heartbeat) to node...")
                              if iface:
                                   # iface.sendText("mqtt-health", wantAck=False)
                                   # Use sendPosition (Location TX) as a non-intrusive heartbeat
                                   iface.sendPosition()
                                   last_probe_time = current_time
                          except Exception as e:
                              logger.warning("Failed to send active probe: %s", e)

                 # Update heartbeat file
                 if current_time - last_heartbeat > 10:
                     try:
                         if health_ok:
                             with open("/tmp/healthy", "w") as f:
                                 f.write(str(current_time))
                             last_heartbeat = current_time
                         else:
                             # Remove health file to trigger health check failure
                             import os as os_module
                             if os_module.path.exists("/tmp/healthy"):
                                 os_module.remove("/tmp/healthy")
                             logger.error("Health check FAILED: %s", ", ".join(health_reasons))
                     except Exception as e:
                         logger.debug("Heartbeat error: %s", e)
                 
        except Exception as e:
            logger.error("Connection error: %s", e)
        finally:
             if iface:
                 try:
                    iface.close()
                 except: pass

        if running:
             logger.info("Reconnecting in 5 seconds...")
             time.sleep(5)


if __name__ == "__main__":
    main()
