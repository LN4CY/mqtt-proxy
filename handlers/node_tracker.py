"""Packet Deduplicator for MQTT Proxy loop prevention."""
# Copyright (c) 2026 LN4CY
# This software is licensed under the MIT License. See LICENSE file for details.

import time
import logging
import threading

logger = logging.getLogger("mqtt-proxy.packet_deduplicator")

class PacketDeduplicator:
    """
    Tracks (node_id, packet_id) tuples seen on the mesh (RF/Serial) to prevent loops.
    If we see a specific packet on RF, we should ignore the exact same packet if it comes back via MQTT.
    """
    def __init__(self, timeout_seconds=60):
        self.seen_packets = {}
        self.timeout = timeout_seconds
        self.lock = threading.Lock()

    def mark_seen(self, node_id, packet_id):
        """Mark a (node_id, packet_id) pair as seen on the mesh interface."""
        if not node_id or packet_id is None:
            return
            
        clean_id = node_id.replace('!', '')
        key = (clean_id, packet_id)
        
        with self.lock:
            self.seen_packets[key] = time.time()
            # logger.debug(f"Marked packet {key} as seen on mesh.")
            self._cleanup()

    def is_duplicate(self, node_id, packet_id):
        """Check if a (node_id, packet_id) pair was recently seen on the mesh."""
        if not node_id or packet_id is None:
            return False
            
        clean_id = node_id.replace('!', '')
        key = (clean_id, packet_id)
        
        with self.lock:
            if key in self.seen_packets:
                last_seen = self.seen_packets[key]
                if time.time() - last_seen < self.timeout:
                    return True
                else:
                    del self.seen_packets[key]
        return False

    def _cleanup(self):
        """Remove expired entries."""
        now = time.time()
        # Simple cleanup strategy: if too big, or just periodically?
        # For now, let's just do a full sweep if it gets too large? 
        # Or just lazy delete? Lazy delete in is_duplicate is fine, but if we never see it again it grows.
        # Let's do a quick sweep if size > 1000
        if len(self.seen_packets) > 1000:
            keys_to_remove = [k for k, t in self.seen_packets.items() if now - t > self.timeout]
            for k in keys_to_remove:
                del self.seen_packets[k]
