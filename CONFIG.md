# Configuration Guide

Complete configuration reference for the Meshtastic MQTT Proxy.

## Interface Configuration

### TCP Interface

Connect to a Meshtastic node via TCP network connection.

**Use Cases:**
- MeshMonitor virtual node
- Meshtastic devices with network connectivity
- Remote node access

**Configuration:**
```env
INTERFACE_TYPE=tcp
TCP_NODE_HOST=192.168.1.100
TCP_NODE_PORT=4403
TCP_TIMEOUT=300
```

**Parameters:**
- `TCP_NODE_HOST` - Hostname or IP address of the Meshtastic node
- `TCP_NODE_PORT` - TCP port (default: 4403, MeshMonitor virtual node: 4404)
- `TCP_TIMEOUT` - Connection timeout in seconds (default: 300)

### Serial Interface

Connect to a USB-connected Meshtastic device.

**Use Cases:**
- Direct USB connection to Meshtastic device
- Raspberry Pi with USB radio
- Development and testing

**Configuration:**
```env
INTERFACE_TYPE=serial
SERIAL_PORT=/dev/ttyACM0
```

**Parameters:**
- `SERIAL_PORT` - Device path (Linux: `/dev/ttyACM0`, `/dev/ttyUSB0`)

**Finding Your Serial Port:**
```bash
# List all serial devices
ls /dev/tty*

# Or use dmesg to see recent connections
dmesg | grep tty
```

**Docker Requirements:**
- Device must be mapped in docker-compose.yml
- Privileged mode required (already configured)

### BLE Interface

**Status:** Not yet supported (code present but commented out)

BLE support requires custom implementation using the `bleak` library. See the [meshtastic-ble-bridge](https://github.com/Yeraze/meshtastic-ble-bridge) project for reference.

## Environment Variables

### Core Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `INTERFACE_TYPE` | string | `tcp` | Interface type: `tcp` or `serial` |
| `LOG_LEVEL` | string | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### TCP Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `TCP_NODE_HOST` | string | `localhost` | TCP hostname or IP address |
| `TCP_NODE_PORT` | integer | `4403` | TCP port number |
| `TCP_TIMEOUT` | integer | `300` | Connection timeout (seconds) |

### Serial Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SERIAL_PORT` | string | `/dev/ttyUSB0` | Serial device path |

### Advanced Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CONFIG_WAIT_TIMEOUT` | integer | `60` | Max time to wait for node config (seconds) |
| `POLL_INTERVAL` | integer | `1` | Config polling interval (seconds) |

### Health Check Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HEALTH_CHECK_ACTIVITY_TIMEOUT` | integer | `300` | Max time without MQTT activity before health check fails (seconds) |
| `HEALTH_CHECK_PROBE_INTERVAL` | integer | `150` | Time without activity before sending active probe (seconds, default is 50% of timeout) |
| `HEALTH_CHECK_STATUS_INTERVAL` | integer | `60` | How often to log status information (seconds) |
| `MQTT_RECONNECT_DELAY` | integer | `5` | Delay before attempting MQTT reconnection (seconds) |

> [!NOTE]
> The health check monitors both MQTT connection state and message activity. If the proxy stops sending/receiving messages for longer than `HEALTH_CHECK_ACTIVITY_TIMEOUT`, Docker will automatically restart the container.
>
> If the network is idle for `HEALTH_CHECK_PROBE_INTERVAL`, the proxy will send a "mqtt-health" text message to the node to verify connectivity.

## Meshtastic Node Configuration

The Meshtastic node must have MQTT properly configured for the proxy to work.

### Required Settings

Check your node configuration:
```bash
meshtastic --get mqtt
```

**Required values:**
```
mqtt.enabled: True
mqtt.proxy_to_client_enabled: True
mqtt.address: <your-mqtt-broker>
mqtt.username: <mqtt-username>
mqtt.password: <mqtt-password>
```

### Enabling MQTT Proxy

If not enabled, configure your node:
```bash
meshtastic --set mqtt.enabled true
meshtastic --set mqtt.proxy_to_client_enabled true
meshtastic --set mqtt.address mqtt.example.com
meshtastic --set mqtt.username myuser
meshtastic --set mqtt.password mypass
```

## Docker Compose Configuration

### Basic Setup

```yaml
services:
  mqtt-proxy:
    build: .
    image: mqtt-proxy
    container_name: mqtt-proxy
    restart: unless-stopped
    environment:
      - INTERFACE_TYPE=${INTERFACE_TYPE:-tcp}
      - TCP_NODE_HOST=${TCP_NODE_HOST:-localhost}
      - TCP_NODE_PORT=${TCP_NODE_PORT:-4403}
    network_mode: host
```

### Serial Interface Setup

For serial connections, add device mapping:

```yaml
services:
  mqtt-proxy:
    # ... other config ...
    devices:
      - /dev/ttyACM0:/dev/ttyACM0
    privileged: true
```

## Example Configurations

### MeshMonitor Virtual Node

```env
INTERFACE_TYPE=tcp
TCP_NODE_HOST=192.168.1.100
TCP_NODE_PORT=4404
LOG_LEVEL=INFO
```

### USB-Connected Device

```env
INTERFACE_TYPE=serial
SERIAL_PORT=/dev/ttyACM0
LOG_LEVEL=INFO
```

### Development/Debug

```env
INTERFACE_TYPE=tcp
TCP_NODE_HOST=localhost
TCP_NODE_PORT=4403
LOG_LEVEL=DEBUG
CONFIG_WAIT_TIMEOUT=120
```

## Logging

### Log Levels

- `DEBUG` - Detailed debugging information (verbose)
- `INFO` - General informational messages (default)
- `WARNING` - Warning messages
- `ERROR` - Error messages only

### Viewing Logs

```bash
# Follow logs in real-time
docker compose logs -f mqtt-proxy

# View last 100 lines
docker compose logs --tail=100 mqtt-proxy

# View logs since 10 minutes ago
docker compose logs --since=10m mqtt-proxy
```

### Log Output Examples

**Successful Connection:**
```
[INFO] MQTT Proxy starting (interface: TCP)...
[INFO] Creating TCP interface...
[INFO] Connected to node !10ae8907
[INFO] Starting MQTT Client...
[INFO] MQTT Connected with result code: 0
```

**MQTT Traffic:**
```
[INFO] MQTT RX (Forwarding): Topic=msh/US/2/e/LongFast/!12345678 Size=156 bytes
[INFO] Node→MQTT: Topic=msh/US/2/e/LongFast/!87654321 Size=142 bytes
```

## Troubleshooting

### Common Issues

**"No localNode available"**
- Node not responding
- Check connection settings
- Verify node is powered on

**"MQTT is NOT enabled in node config"**
- Enable MQTT on node: `meshtastic --set mqtt.enabled true`
- Enable proxy mode: `meshtastic --set mqtt.proxy_to_client_enabled true`

**"Connection timeout"**
- Increase `TCP_TIMEOUT`
- Check network connectivity
- Verify firewall rules

**Serial device not found**
- Check device path: `ls /dev/tty*`
- Verify device permissions
- Ensure device is mapped in docker-compose.yml

### Health Check Issues

**Container keeps restarting**
- Check logs: `docker compose logs --tail=100 mqtt-proxy`
- Look for "Health check FAILED" messages
- Common causes:
  - MQTT broker is down or unreachable
  - No message activity for > 5 minutes (configurable via `HEALTH_CHECK_ACTIVITY_TIMEOUT`)
  - Meshtastic node disconnected

**Monitoring container health**
```bash
# Check current health status
docker inspect --format='{{.State.Health.Status}}' mqtt-proxy

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' mqtt-proxy
```

**Understanding health check failures**
The health check monitors:
1. MQTT connection state (must be connected)
2. Message activity (must send or receive within timeout period)

Status logs appear every 60 seconds showing:
- MQTT connection state
- Message TX/RX counts and last activity time
- Warnings when approaching activity timeout

## Performance Tuning

### Timeout Settings

Adjust timeouts based on your network:

```env
# Slow/unreliable network
TCP_TIMEOUT=600
CONFIG_WAIT_TIMEOUT=120

# Fast/reliable network
TCP_TIMEOUT=60
CONFIG_WAIT_TIMEOUT=30
```

### Polling Interval

Adjust config polling frequency:

```env
# More responsive (higher CPU)
POLL_INTERVAL=0.5

# Less responsive (lower CPU)
POLL_INTERVAL=2
```

## Security Considerations

### Network Security

- Use firewall rules to restrict TCP access
- Consider VPN for remote connections
- Use strong MQTT credentials

### Docker Security

- Run with minimal privileges when possible
- Keep Docker images updated
- Review docker-compose.yml security settings

## Advanced Topics

### Multiple Proxies

Run multiple proxy instances for different nodes:

```yaml
services:
  mqtt-proxy-1:
    # ... config for node 1 ...
    
  mqtt-proxy-2:
    # ... config for node 2 ...
```

### Custom Docker Network

Use bridge network instead of host mode:

```yaml
services:
  mqtt-proxy:
    # ... other config ...
    networks:
      - mqtt-network
    ports:
      - "4403:4403"

networks:
  mqtt-network:
    driver: bridge
```

---

For more information, see [README.md](README.md) or open an issue on GitHub.
