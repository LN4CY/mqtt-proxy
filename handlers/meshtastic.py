"""Meshtastic Interface Handler for MQTT Proxy."""
# Copyright (c) 2026 LN4CY
# This software is licensed under the MIT License. See LICENSE file for details.

import time
import logging
from pubsub import pub
from meshtastic import mesh_pb2
from meshtastic.tcp_interface import TCPInterface
from meshtastic.serial_interface import SerialInterface
from meshtastic.protobuf import portnums_pb2
from google.protobuf.message import DecodeError

logger = logging.getLogger("mqtt-proxy.handlers.meshtastic")

class MQTTProxyMixin:
    """
    Mixin class that provides common _handleFromRadio() logic for all interface types.
    This intercepts mqttClientProxyMessage from the node and publishes to MQTT.
    Also handles "implicit ACKs" (ROUTING_APP packets) and suppresses DecodeErrors.
    """
    def _handleFromRadio(self, fromRadio):
        """
        Intersects mqttClientProxyMessage from the node and publishes to MQTT.
        """
        decoded = None
        try:
            # Update generic radio activity timestamp for ANY received data
            # Access the proxy instance injected/attached to the interface
            if hasattr(self, 'proxy') and self.proxy:
                self.proxy.last_radio_activity = time.time()

            # 1. Parse the packet manually if it's bytes (to inspect it before the main lib potentially fails)
            if isinstance(fromRadio, bytes):
                try:
                    decoded = mesh_pb2.FromRadio()
                    decoded.ParseFromString(fromRadio)
                except Exception as e:
                    logger.debug(f"Failed to parse FromRadio bytes: {e}")
            else:
                decoded = fromRadio

            if decoded:
                # 2. Check for mqttClientProxyMessage (node wants to publish to MQTT)
                if decoded.HasField("mqttClientProxyMessage"):
                    mqtt_msg = decoded.mqttClientProxyMessage
                    logger.info("Node->MQTT: Topic=%s Size=%d bytes Retained=%s", 
                            mqtt_msg.topic, len(mqtt_msg.data), mqtt_msg.retained)
                    
                    if hasattr(self, 'proxy') and self.proxy and self.proxy.mqtt_handler:
                        # Mark this sender as "seen" to prevent loops if we subscribe to this topic
                        try:
                            # Extract sender from packet if available
                            sender_id = None
                            packet_id = None
                            
                            if decoded.packet:
                                # Extract sender from 'from' field (fromId doesn't exist in protobuf)
                                try:
                                    sender_val = getattr(decoded.packet, "from")
                                    sender_id = f"{sender_val:08x}"
                                except:
                                    pass
                                
                                if decoded.packet.id:
                                    packet_id = decoded.packet.id
                            
                            if sender_id and packet_id and hasattr(self.proxy, 'deduplicator') and self.proxy.deduplicator:
                                self.proxy.deduplicator.mark_seen(sender_id, packet_id)
                        except Exception as e:
                            logger.warning(f"Failed to track node/packet: {e}")

                        self.proxy.mqtt_handler.publish(mqtt_msg.topic, mqtt_msg.data, retain=mqtt_msg.retained)
                
                # 3. Handle Implicit ACKs (ROUTING_APP errors with error_reason=NONE)
                # This fixes the "Missing ACK" issue where the radio sends a routing packet instead of a formal ACK
                elif decoded.packet and decoded.packet.decoded and decoded.packet.decoded.portnum == portnums_pb2.ROUTING_APP:
                    try:
                        p = decoded.packet
                        # Check payload for Routing payload
                        r = mesh_pb2.Routing()
                        r.ParseFromString(p.decoded.payload)
                        if r.error_reason == mesh_pb2.Routing.Error.NONE and p.decoded.request_id != 0:
                            # This is effectively an ACK for request_id
                            logger.debug(f"Implicit ACK detected for packetId={p.decoded.request_id} (ROUTING_APP)")
                            # We can force an ACK event if needed, but for now we just log it.
                            # The main lib might not interpret this as an ACK for 'sendText', 
                            # but for custom apps this is good to know.
                            pub.sendMessage("meshtastic.ack", packetId=p.decoded.request_id, interface=self)
                    except Exception as e:
                        pass

                # 4. Standard Mesh Packet Logging (Debug)
                elif decoded.packet and decoded.packet.to:
                    # Logs generic traffic for debugging
                    pub.sendMessage("proxy.receive.raw", packet=decoded.packet, interface=self)

        except Exception as e:
            # Expected protobuf parsing errors - log at debug level
            logger.debug("Error in MQTT proxy interception: %s", e)

        # 5. Safe Super Call
        # Always call super to let the library maintain its state, but prevent crashes
        try:
            super()._handleFromRadio(fromRadio)
        except DecodeError as e:
            logger.warning("Protobuf Decode Error (suppressed): %s", e)
            # We don't re-raise, effectively swallowing the crash
        except Exception as e:
            logger.error("Error in StreamInterface processing: %s", e)


class RawTCPInterface(MQTTProxyMixin, TCPInterface):
    """TCP interface with MQTT proxy support and safe error handling"""
    def __init__(self, *args, **kwargs):
        self.proxy = kwargs.pop('proxy', None)
        super().__init__(*args, **kwargs)


class RawSerialInterface(MQTTProxyMixin, SerialInterface):
    """Serial interface with MQTT proxy support and safe error handling"""
    def __init__(self, *args, **kwargs):
        self.proxy = kwargs.pop('proxy', None)
        super().__init__(*args, **kwargs)


def create_interface(config, proxy_instance):
    """
    Factory function to create the appropriate interface based on config.
    """
    if config.interface_type == "tcp":
        logger.info(f"Creating TCP interface ({config.tcp_node_host}:{config.tcp_node_port})...")
        return RawTCPInterface(
            config.tcp_node_host,
            portNumber=config.tcp_node_port,
            timeout=config.tcp_timeout,
            proxy=proxy_instance
        )
    elif config.interface_type == "serial":
        logger.info(f"Creating Serial interface ({config.serial_port})...")
        return RawSerialInterface(
            config.serial_port,
            proxy=proxy_instance
        )
    else:
        raise ValueError(f"Unknown interface type: {config.interface_type}")

