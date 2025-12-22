# Meshtastic MQTT Proxy

A production-ready MQTT proxy for Meshtastic devices that enables bidirectional message forwarding between Meshtastic nodes and MQTT brokers. Supports TCP and Serial interface connections with a clean factory pattern architecture.

## Features

- ✅ **Multi-Interface Support** - TCP and Serial connections to Meshtastic nodes
- ✅ **Bidirectional Forwarding** - Messages flow both ways between node and MQTT broker
- ✅ **mqttClientProxyMessage Protocol** - Implements Meshtastic's official proxy protocol
- ✅ **Docker Containerized** - Easy deployment with Docker Compose
- ✅ **Environment Configuration** - Flexible configuration via environment variables
- ✅ **Production Ready** - Error handling, logging, and automatic reconnection
- ✅ **Channel Support** - Works with all Meshtastic channels and message types
- ✅ **MeshMonitor Compatible** - Seamless integration with MeshMonitor and other tools

**Note:** BLE interface is not currently supported. Use TCP or Serial interfaces.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Meshtastic node (accessible via TCP or Serial)
- MQTT broker (configured on your Meshtastic node)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/LN4CY/mqtt-proxy.git
cd mqtt-proxy
```

2. Create `.env` file:
```bash
cp .env.example .env
```

3. Configure your connection in `.env`:
```env
INTERFACE_TYPE=tcp
TCP_NODE_HOST=192.168.1.100
TCP_NODE_PORT=4403
```

4. Start the proxy:
```bash
docker compose up -d
```

### Quick Start (Pre-built Image)

You can run the proxy directly without cloning the code using the pre-built image from GitHub Container Registry:

```bash
docker run -d \
  --name mqtt-proxy \
  --net=host \
  --restart unless-stopped \
  -e INTERFACE_TYPE=tcp \
  -e TCP_NODE_HOST=192.168.1.100 \
  -e TCP_NODE_PORT=4403 \
  ghcr.io/ln4cy/mqtt-proxy:master
```

## Configuration

### Interface Types

**TCP Interface** (default):
```env
INTERFACE_TYPE=tcp
TCP_NODE_HOST=localhost
TCP_NODE_PORT=4403
```

**Serial Interface**:
```env
INTERFACE_TYPE=serial
SERIAL_PORT=/dev/ttyACM0
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `INTERFACE_TYPE` | `tcp` | Interface type: `tcp` or `serial` |
| `TCP_NODE_HOST` | `localhost` | TCP hostname or IP address |
| `TCP_NODE_PORT` | `4403` | TCP port number |
| `SERIAL_PORT` | `/dev/ttyUSB0` | Serial device path |
| `LOG_LEVEL` | `INFO` | Logging level |
| `TCP_TIMEOUT` | `300` | TCP connection timeout (seconds) |
| `CONFIG_WAIT_TIMEOUT` | `60` | Node config wait timeout (seconds) |
| `POLL_INTERVAL` | `1` | Config polling interval (seconds) |

See [CONFIG.md](CONFIG.md) for detailed configuration options.

## Usage

### TCP Interface

Connect to a Meshtastic node via TCP (e.g., MeshMonitor's virtual node):

```bash
# .env
INTERFACE_TYPE=tcp
TCP_NODE_HOST=192.168.1.100
TCP_NODE_PORT=4404
```

### Serial Interface

Connect to a USB-connected Meshtastic device:

```bash
# .env
INTERFACE_TYPE=serial
SERIAL_PORT=/dev/ttyACM0
```

**Note:** Serial interface requires privileged mode (already configured in docker-compose.yml).

### Viewing Logs

```bash
docker compose logs -f mqtt-proxy
```

### Stopping the Proxy

```bash
docker compose down
```

## Windows Support

Running this proxy on Windows? Here's what you need to know:

### 1. TCP Interface (Recommended for Docker)
If you are connecting to a node over TCP (WiFi), Docker Desktop for Windows works perfectly out of the box. Just use the standard `docker-compose.yml`.

### 2. Serial Interface (USB)
Connecting to a USB device via Docker on Windows is **not supported directly** because Docker runs in a VM (WSL2) and Windows does not pass COM ports to it by default.

**Option A: Run Natively (Easiest)**
Install Python on Windows and run the script directly. This allows direct access to COM ports (e.g., `COM3`).

```powershell
# Install dependencies
pip install -r requirements.txt

# Run with environment variables
$env:INTERFACE_TYPE="serial"
$env:SERIAL_PORT="COM3"
python mqtt-proxy.py
```

**Option B: Docker via WSL2 + usbipd (Advanced)**
If you MUST use Docker with USB Config, you need `usbipd-win` to bridge the USB device to WSL2.
1. Install [usbipd-win](https://github.com/dorssel/usbipd-win).
2. Attach the device: `usbipd wsl attach --busid <BUSID>`
3. The device will appear as `/dev/ttyACM0` inside WSL2/Docker.

## Integration with MeshMonitor

For a seamless integration with [MeshMonitor](https://github.com/Yeraze/meshmonitor), add the proxy as a service in your main `docker-compose.yml`.

> [!IMPORTANT]
> If you plan to use the MeshMonitor serial bridge or BLE bridge, you **must** use a virtual node enabled configuration for MeshMonitor to ensure proper connectivity.

### Best Practices (Verified)

1. **Shared Network:** Use a custom bridge network (`meshtastic_net`) for all services to enable service-name discovery.
2. **Startup Order:** Use a healthcheck on `meshmonitor` so `mqtt-proxy` only starts when the virtual node is ready.
3. **Environment:** Use `TCP_NODE_HOST=meshmonitor` to avoid hardcoded IPs.

### Example Configuration

```yaml
version: '3'
services:
  # The main application
  meshmonitor:
    image: ghcr.io/yeraze/meshmonitor:latest
    container_name: meshmonitor
    restart: unless-stopped
    ports:
      - "8181:3001"
      - "4404:4404"
    environment:
      - ENABLE_VIRTUAL_NODE=true
      - VIRTUAL_NODE_PORT=4404
      - MESHTASTIC_NODE_IP=serial-bridge  # Connects to serial-bridge by name
      - STATUS_FILE=/data/.upgrade-status
      - CHECK_INTERVAL=5
      - COMPOSE_PROJECT_DIR=/compose
      - COMPOSE_PROJECT_NAME=meshmonitor # Critical: Forces upgrader to use shared network
    command: /data/scripts/upgrade-watchdog.sh
    # Add simple healthcheck to ensure port 4404 is open
    healthcheck:
      test: ["CMD-SHELL", "node -e 'const net = require(\"net\"); const client = new net.Socket(); client.connect(4404, \"127.0.0.1\", () => { process.exit(0); }); client.on(\"error\", () => { process.exit(1); });'"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
    depends_on:
      - serial-bridge
    networks:
      - meshtastic_net

  # The generic serial bridge
  serial-bridge:
    image: ghcr.io/yeraze/meshtastic-serial-bridge:latest
    container_name: meshtastic-serial-bridge
    devices:
      - /dev/ttyACM0:/dev/ttyACM0
    environment:
      - SERIAL_DEVICE=/dev/ttyACM0
      - TCP_PORT=4403
    networks:
      - meshtastic_net

  # This proxy service (The Glue)
  mqtt-proxy:
    image: ghcr.io/ln4cy/mqtt-proxy:master
    container_name: mqtt-proxy
    restart: unless-stopped
    environment:
      - INTERFACE_TYPE=tcp
      - TCP_NODE_HOST=meshmonitor # Connects to meshmonitor by name
      - TCP_NODE_PORT=4404
    depends_on:
      meshmonitor:
        condition: service_healthy # Wait for port 4404 to be listening
    networks:
      - meshtastic_net

networks:
  meshtastic_net:
    driver: bridge
```

## Architecture

The proxy uses a factory pattern to support multiple interface types:

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  Meshtastic │ ◄─────► │  MQTT Proxy  │ ◄─────► │ MQTT Broker │
│    Node     │         │              │         │             │
└─────────────┘         └──────────────┘         └─────────────┘
   TCP/Serial          mqttClientProxy           MQTT Protocol
```

### Key Components

- **MQTTProxyMixin** - Common message handling logic
- **RawTCPInterface** - TCP connection implementation
- **RawSerialInterface** - Serial connection implementation
- **Factory Pattern** - Dynamic interface selection

## How It Works

1. **Node → MQTT**: Proxy receives `mqttClientProxyMessage` from node and publishes to MQTT broker
2. **MQTT → Node**: Proxy subscribes to MQTT topics and forwards messages to node as `mqttClientProxyMessage`
3. **Transparent Operation**: Node firmware handles encryption, channel mapping, and routing

## Requirements

- Python 3.9+
- Docker & Docker Compose
- Meshtastic node with MQTT enabled and `proxy_to_client_enabled: true`

### Python Dependencies

- meshtastic==2.7.5
- paho-mqtt==2.1.0
- pubsub==4.0.7
- protobuf>=3.20.0,<6.0.0

## Troubleshooting

### Connection Issues

**TCP Connection Fails:**
- Verify node IP and port
- Check firewall rules
- Ensure node is running

**Serial Connection Fails:**
- Check device path (`ls /dev/tty*`)
- Verify device permissions
- Ensure privileged mode is enabled

### MQTT Issues

**No MQTT Traffic:**
- Verify MQTT is enabled on node: `meshtastic --get mqtt`
- Check `proxy_to_client_enabled: true`
- Verify MQTT broker is accessible

**Messages Not Appearing:**
- Check MQTT broker logs
- Verify channel configuration
- Review proxy logs for errors

## Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python mqtt-proxy.py
```

### Building Docker Image

```bash
docker compose build
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project source code is released under the **MIT License**.

### Dependency Licenses
Users should be aware that the Docker image built from this repository bundles several third-party dependencies, including:

*   **[meshtastic-python](https://github.com/meshtastic/python)**: Licensed under **GPLv3**.
*   **[paho-mqtt](https://github.com/eclipse/paho.mqtt.python)**: Licensed under **EPL-2.0 / BSD**.

**Note:** Due to the inclusion of `meshtastic` (GPLv3), compiled binaries or Docker images distributed from this project are effectively subject to the terms of the GPLv3.

## Acknowledgments

- Built for the [Meshtastic](https://meshtastic.org/) project
- Compatible with [MeshMonitor](https://github.com/Yeraze/meshmonitor)
- Implements the mqttClientProxyMessage protocol from Meshtastic firmware

## Support

- **Issues**: [GitHub Issues](https://github.com/LN4CY/mqtt-proxy/issues)
- **Meshtastic Discord**: [Join](https://discord.gg/meshtastic)
- **Documentation**: See [CONFIG.md](CONFIG.md) for detailed configuration

## Roadmap

- [ ] **BLE Interface Support** - Requires custom bleak implementation (see [meshtastic-ble-bridge](https://github.com/Yeraze/meshtastic-ble-bridge) for reference)
- [ ] Metrics and monitoring endpoints
- [ ] Web UI for configuration
- [ ] Multi-node support

---

**Status**: Production Ready ✅  
**Version**: 1.0.0  
**Last Updated**: 2025-12-22
