## Problem

Virtual channel topic rewriting (renaming `LongFast` → `NC-LongFast` in the MQTT topic) was insufficient to prevent RF rebroadcast crosstalk.

The radio firmware uses **`packet.channel`** (a PSK hash integer inside the `ServiceEnvelope` protobuf payload) to look up the decryption key — **not** the MQTT topic string. When packets from extra MQTT roots shared the same PSK as a local channel (e.g. `LongFast` / `AQ==`), the radio successfully decrypted and rebroadcast them over RF, effectively bridging two independent MQTT server regions.

## Fix

Mutate the `ServiceEnvelope` protobuf **before** injecting to the radio:
- `packet.channel` → synthetic hash derived from the virtual channel name (range 200-254)

The radio firmware finds no matching PSK for the synthetic hash → cannot decrypt → **does not rebroadcast over RF** ✅

The `packet.encrypted` bytes and the `channel_id` string name are **completely untouched**. This allows MeshMonitor to decrypt the packet using its standard Channel Database natively. 

**Known Defect:** Because the PSK hash is faked to prevent radio crosstalk, MeshMonitor's "Enforce Channel Name Validation" cannot be used (it strictly fails the hash check). Consequently, if multiple monitored channels share the exact same key, MeshMonitor will decode and merge their traffic into a single channel display.

## Setup for Users

Users just ensure the original PSK exists in their MeshMonitor Channel Database. No custom `NC-` prefixed entries are required. "Enforce Channel Name Validation" must remain OFF.

## Testing
- All 67 existing tests pass
- Live verified: `packet.channel` carries PSK hash (not slot index) via `inspect_payload.py`
- Confirmed MeshMonitor successfully decrypts natively, with documentation updated on the shared-PSK defect.
