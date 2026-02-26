"""Message Queue for MQTT Proxy."""
# Copyright (c) 2026 LN4CY
# This software is licensed under the MIT License. See LICENSE file for details.

import time
import logging
import threading
import queue
from meshtastic import mesh_pb2

logger = logging.getLogger("mqtt-proxy.queue")

class MessageQueue:
    """
    Thread-safe queue for buffering and rate-limiting outgoing messages to the radio.
    """
    def __init__(self, config, interface_provider):
        """
        Initialize the message queue.
        
        Args:
            config: Config object containing mesh_transmit_delay.
            interface_provider: Callable that returns the current Meshtastic interface (or None).
        """
        self.config = config
        self.get_interface = interface_provider
        self.max_size = getattr(config, 'mesh_max_queue_size', 100)
        self.queue = queue.Queue(maxsize=self.max_size)
        self.running = False
        self.thread = None

    def start(self):
        """Start the queue processing thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._process_loop, daemon=True, name="MessageQueueWorker")
        self.thread.start()
        logger.info("Message queue started.")

    def stop(self):
        """Stop the queue processing."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        logger.info("Message queue stopped.")

    def put(self, topic, payload, retained):
        """Enqueue a message to be sent to the radio."""
        try:
            self.queue.put({
                'topic': topic,
                'payload': payload,
                'retained': retained,
                'timestamp': time.time()
            }, block=False)
            
            qsize = self.queue.qsize()
            if qsize >= (self.max_size * 0.8):
                 logger.warning(f"Queue nearly full: {qsize}/{self.max_size} messages pending")
            elif qsize > 10:
                 logger.debug(f"Queue growing: {qsize} messages pending")
        except queue.Full:
            logger.error(f"Queue FULL ({self.max_size} msgs). Dropping new message for topic: {topic}")

    def _process_loop(self):
        """Main processing loop."""
        while self.running:
            try:
                # 1. Get an item from the queue (blocking with timeout to allow shutdown check)
                item = self.queue.get(timeout=1.0)
                
                # 2. Wait for interface to be ready
                iface = self._wait_for_interface()
                if not iface or not self.running:
                    # If we shut down while waiting, put it back or drop?
                    # Since we are daemon, dropping is fine on shutdown.
                    self.queue.task_done()
                    continue

                # 3. Send the item
                try:
                    queue_duration = time.time() - item['timestamp']
                    send_start = time.time()
                    self._send_to_radio(iface, item)
                    send_duration = time.time() - send_start
                    
                    queue_size = self.queue.qsize()
                    logger.info(f"Message processed. Queue: {queue_size} msgs, Wait: {queue_duration:.3f}s, Send: {send_duration:.3f}s")
                    
                    # 4. Rate Limiting
                    time.sleep(self.config.mesh_transmit_delay)
                    
                except Exception as e:
                    logger.error(f"Failed to send to radio: {e}")
                    # Potentially re-queue? For now, we assume simple failure means drop to avoid head-of-line blocking
                    # on malformed packets. If connection lost, _wait_for_interface matches next time.
                
                self.queue.task_done()
                
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error in queue processing loop: {e}")
                time.sleep(1)

    def _wait_for_interface(self):
        """Blocks until an interface is available or running is False."""
        while self.running:
            iface = self.get_interface()
            if iface:
                return iface
            time.sleep(1) # Wait for connection
        return None

    def _send_to_radio(self, iface, item):
        """Construct protobuf and call interface send."""
        # Construct Protobuf
        mqtt_proxy_msg = mesh_pb2.MqttClientProxyMessage()
        mqtt_proxy_msg.topic = item['topic']
        mqtt_proxy_msg.data = item['payload']
        mqtt_proxy_msg.retained = item['retained']
        
        to_radio = mesh_pb2.ToRadio()
        # The 'mqttClientProxyMessage' field in ToRadio is the one we use
        to_radio.mqttClientProxyMessage.CopyFrom(mqtt_proxy_msg)
        
        # Determine size for logging
        size = len(item['payload'])
        
        # Use _sendToRadio if available (thread-safe with locking), fall back to Impl
        if hasattr(iface, "_sendToRadio"):
             iface._sendToRadio(to_radio)
        else:
             logger.warning("Interface missing _sendToRadio, falling back to _sendToRadioImpl (potentially unsafe)")
             iface._sendToRadioImpl(to_radio)
             
        logger.debug(f"Sent to radio: {item['topic']} ({size} bytes)")
