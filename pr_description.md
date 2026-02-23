# Fix: Bypass MQTT Loop Protection for Self-Echoed Packets

## Description
This PR resolves the "Failed to Send" (Red X) bug that occurs when forwarding messages from MeshMonitor (or other API clients) through `mqtt-proxy` with the `proxy_to_client_enabled` firmware setting. 

The issue occurred because the `mqtt-proxy`'s strict loop deduplication logic was aggressively dropping echoed `ServiceEnvelope` packets published to the MQTT broker by the physical node. The firmware requires receiving these specific echoes to generate a local `meshtastic_Routing_Error_NONE` (Implicit ACK) that confirms the message successfully entered the MQTT network. By dropping the echo, the firmware never generated the ACK, eventually leading to a `MAX_RETRANSMIT` timeout NAK that was sent back via API and incorrectly interpreted as a hard failure by MeshMonitor.

## Changes
- **`handlers/mqtt.py`**: Added `is_echo` bypass logic that parses the incoming `ServiceEnvelope` and allows the payload through if the `gateway_id` matches the local node's ID.
- The bypassed echo is safely blocked from creating a broadcast storm by the firmware's own check inside `MQTT::onReceiveProto()`.
- Works flawlessly with both cleartext and encrypted private channel traffic since `gateway_id` sits at the top level of the `ServiceEnvelope`.

## Verification
- Ran existing `pytest` test suite to ensure standard cross-node loop deduplication logic remains functional.
- Verified all loops correctly break internally at the firmware boundaries.
- Resolves "Missed Messages / False Positive Routing Errors".
