"""Message Queue for MQTT Proxy."""
# Copyright (c) 2026 LN4CY
# This software is licensed under the MIT License. See LICENSE file for details.

import time
import logging
import threading
from collections import deque
from meshtastic import mesh_pb2

logger = logging.getLogger("mqtt-proxy.queue")

class MessageQueue:
    """
    Thread-safe queue for buffering and rate-limiting outgoing messages to the radio.

    Uses drop-oldest eviction: when the queue is full, the oldest message is
    discarded to make room for the newest. This ensures the most recent MQTT
    traffic always reaches the radio.
    """
    def __init__(self, config, interface_provider):
        self.config = config
        self.get_interface = interface_provider

        raw_max_size = getattr(config, 'mesh_max_queue_size', 100)
        if isinstance(raw_max_size, int):
            self.max_size = raw_max_size
        else:
            try:
                self.max_size = int(raw_max_size)
            except (TypeError, ValueError):
                self.max_size = 100

        self._deque = deque()
        self._lock = threading.Lock()
        self._event = threading.Event()
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
        self._event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        logger.info("Message queue stopped.")

    def qsize(self):
        """Return current queue size."""
        with self._lock:
            return len(self._deque)

    def put(self, topic, payload, retained):
        """Enqueue a message. If full, evict the oldest message."""
        item = {
            'topic': topic,
            'payload': payload,
            'retained': retained,
            'timestamp': time.time()
        }

        with self._lock:
            if len(self._deque) >= self.max_size:
                evicted = self._deque.popleft()
                logger.warning(f"Queue full ({self.max_size}/{self.max_size}). Evicting oldest message to make room.")
                logger.debug(f"Evicted message for topic: {evicted['topic']}")

            self._deque.append(item)
            size = len(self._deque)

        self._event.set()

        if size >= (self.max_size * 0.8) and size < self.max_size:
            logger.warning(f"Queue nearly full: {size}/{self.max_size} messages pending")
        elif size > 10:
            logger.debug(f"Queue growing: {size} messages pending")

    def drain_all(self):
        """Remove and yield all items. Used for testing."""
        with self._lock:
            while self._deque:
                yield self._deque.popleft()

    def _get(self):
        """Get the next item from the deque, or None if empty."""
        with self._lock:
            if self._deque:
                return self._deque.popleft()
            return None

    def _process_loop(self):
        """Main processing loop."""
        while self.running:
            try:
                item = self._get()

                if item is None:
                    self._event.wait(timeout=1.0)
                    self._event.clear()
                    continue

                iface = self._wait_for_interface()
                if not iface or not self.running:
                    continue

                try:
                    queue_duration = time.time() - item['timestamp']
                    send_start = time.time()
                    self._send_to_radio(iface, item)
                    send_duration = time.time() - send_start

                    queue_size = self.qsize()
                    logger.info(f"Message processed. Queue: {queue_size}/{self.max_size}, Wait: {queue_duration:.3f}s, Send: {send_duration:.3f}s")

                    time.sleep(self.config.mesh_transmit_delay)

                except Exception as e:
                    logger.error(f"Failed to send to radio: {e}")

            except Exception as e:
                logger.error(f"Error in queue processing loop: {e}")
                time.sleep(1)

    def _wait_for_interface(self):
        """Blocks until an interface is available or running is False."""
        while self.running:
            iface = self.get_interface()
            if iface:
                return iface
            time.sleep(1)
        return None

    def _send_to_radio(self, iface, item):
        """Construct protobuf and call interface send."""
        mqtt_proxy_msg = mesh_pb2.MqttClientProxyMessage()
        mqtt_proxy_msg.topic = item['topic']
        mqtt_proxy_msg.data = item['payload']
        mqtt_proxy_msg.retained = item['retained']

        to_radio = mesh_pb2.ToRadio()
        to_radio.mqttClientProxyMessage.CopyFrom(mqtt_proxy_msg)

        size = len(item['payload'])

        if hasattr(iface, "_sendToRadio"):
             iface._sendToRadio(to_radio)
        else:
             logger.warning("Interface missing _sendToRadio, falling back to _sendToRadioImpl")
             iface._sendToRadioImpl(to_radio)

        logger.debug(f"Sent to radio: {item['topic']} ({size} bytes)")
