# MQTT Proxy Configuration Reference

## Environment Variables

All configuration is done via environment variables in `docker-compose.yml` or `.env` file.

### Interface Selection

| Variable | Default | Description |
|----------|---------|-------------|
| `INTERFACE_TYPE` | `tcp` | Interface type: `tcp`, `serial`, or `ble` |

### Node Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `TCP_NODE_HOST` | `localhost` | Hostname or IP address of the Meshtastic node (TCP only) |
| `TCP_NODE_PORT` | `4403` | TCP port of the Meshtastic node (TCP only) |
| `SERIAL_PORT` | `/dev/ttyUSB0` | Serial port device path (Serial only) |
| `BLE_ADDRESS` | `` | Bluetooth MAC address (BLE only, required for BLE) |

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Timeouts

| Variable | Default | Description |
|----------|---------|-------------|
| `TCP_TIMEOUT` | `300` | TCP connection timeout in seconds (5 minutes) |
| `CONFIG_WAIT_TIMEOUT` | `60` | Maximum time to wait for node configuration in seconds (1 minute) |
| `POLL_INTERVAL` | `1` | Configuration polling interval in seconds |

## Example Configuration

### Basic Setup (docker-compose.yml)
```yaml
services:
  mqtt-proxy:
    environment:
      - TCP_NODE_HOST=192.168.1.100
      - TCP_NODE_PORT=4404
      - LOG_LEVEL=INFO
```

### Custom Timeouts (.env file)
```bash
TCP_NODE_HOST=meshtastic.local
TCP_NODE_PORT=4404
TCP_TIMEOUT=600          # 10 minutes for slow networks
CONFIG_WAIT_TIMEOUT=120  # 2 minutes for slow nodes
LOG_LEVEL=DEBUG          # Verbose logging
```

## Notes

- **No hardcoded values**: All configuration is via environment variables
- **Channel configuration**: Automatically read from the connected node
- **MQTT settings**: Automatically read from the node's MQTT module configuration
- **Fully portable**: Works with any Meshtastic node without code changes
