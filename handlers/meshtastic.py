"""Meshtastic Interface Handler for MQTT Proxy."""

import time
import logging
from pubsub import pub
from meshtastic import mesh_pb2
from meshtastic.tcp_interface import TCPInterface
from meshtastic.serial_interface import SerialInterface
from google.protobuf.message import DecodeError

logger = logging.getLogger("mqtt-proxy.handlers.meshtastic")

class MQTTProxyMixin:
    """
    Mixin class that provides common _handleFromRadio() logic for all interface types.
    This intercepts mqttClientProxyMessage from the node and publishes to MQTT.
    """
    def _handleFromRadio(self, fromRadio):
        """
        Intersects mqttClientProxyMessage from the node and publishes to MQTT.
        """
        try:
            # Update generic radio activity timestamp for ANY received data
            # Access the proxy instance injected/attached to the interface
            if hasattr(self, 'proxy') and self.proxy:
                self.proxy.last_radio_activity = time.time()

            # Parse the bytes into a FromRadio object for our inspection
            if isinstance(fromRadio, bytes):
                decoded = mesh_pb2.FromRadio()
                decoded.ParseFromString(fromRadio)
            else:
                decoded = fromRadio
            
            # Check for mqttClientProxyMessage (node wants to publish to MQTT)
            if decoded.HasField("mqttClientProxyMessage"):
                mqtt_msg = decoded.mqttClientProxyMessage
                logger.info("Node->MQTT: Topic=%s Size=%d bytes Retained=%s", 
                           mqtt_msg.topic, len(mqtt_msg.data), mqtt_msg.retained)
                
                if hasattr(self, 'proxy') and self.proxy and self.proxy.mqtt_handler:
                    self.proxy.mqtt_handler.publish(mqtt_msg.topic, mqtt_msg.data, retain=mqtt_msg.retained)
            
            # Also handle regular mesh packets for backward compatibility
            elif decoded.packet and decoded.packet.to:
                # Debug logging
                # logger.debug("RX MeshPacket (not proxied): To=%s From=%s", decoded.packet.to, getattr(decoded.packet, "from"))
                pub.sendMessage("proxy.receive.raw", packet=decoded.packet, interface=self)

        except Exception as e:
            # Expected protobuf parsing errors - log at debug level
            logger.debug("Error in MQTT proxy interception: %s", e)

        # Always call super to let the library maintain its state
        try:
            super()._handleFromRadio(fromRadio)
        except DecodeError as e:
            logger.debug("Protobuf Decode Error (suppressed): %s", e)
        except Exception as e:
            logger.debug("Error in StreamInterface processing: %s", e)


class RawTCPInterface(MQTTProxyMixin, TCPInterface):
    """TCP interface with MQTT proxy support"""
    def __init__(self, *args, **kwargs):
        self.proxy = kwargs.pop('proxy', None)
        super().__init__(*args, **kwargs)


class RawSerialInterface(MQTTProxyMixin, SerialInterface):
    """Serial interface with MQTT proxy support"""
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
