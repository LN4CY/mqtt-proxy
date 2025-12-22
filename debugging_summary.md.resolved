# Proxy Debugging Summary

## What Works
- ✅ Proxy connects to TCP node successfully
- ✅ Proxy publishes packets to MQTT broker
- ✅ Packets appear on correct MQTT topic: `msh/US/2/e/LongFast/!10ae8907`
- ✅ iOS proxy works perfectly (node `!ccba09cb`)
- ✅ Virtual node (port 4404) works with iOS app
- ✅ MeshMonitor has MQTT configured (`mqtt.ncmesh.net`)

## What We've Tried
1. **Topic switching** - Tried `/c/` (cleartext) topic → MeshMonitor doesn't support it
2. **JSON fallback** - Server doesn't support JSON topic
3. **Gateway ID modification** - Tried `!10ae89ff` → Made it worse
4. **Gateway ID matching** - Reverted to `!10ae8907` → Still doesn't work
5. **Decoded field stripping** - Enabled/disabled → No difference
6. **Port changes** - Tried 4403 vs 4404 → User confirmed 4404 is correct

## Current Configuration
- **Gateway ID**: `!10ae8907` (matches virtual node)
- **Topic**: `msh/US/2/e/LongFast/!10ae8907`
- **Decoded field**: Stripped (matching iOS behavior)
- **Port**: 4404 (virtual node)
- **Node ID**: `10ae8907`

## The Mystery
- iOS proxy (`!ccba09cb`) packets → MeshMonitor displays them ✅
- Docker proxy (`!10ae8907`) packets → MeshMonitor ignores them ❌
- **Both publish to same MQTT broker with same topic structure**

## Hypothesis
MeshMonitor might be filtering packets based on:
1. Gateway whitelist (only trusts specific gateway IDs)
2. Packet structure differences we haven't identified
3. Some metadata field we're not setting correctly
4. Virtual node only displays packets from its own TCP clients, not from MQTT
