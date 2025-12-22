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
git clone https://github.com/yourusername/meshtastic-mqtt-proxy.git
cd meshtastic-mqtt-proxy
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

MIT License - see LICENSE file for details

## Acknowledgments

- Built for the [Meshtastic](https://meshtastic.org/) project
- Compatible with [MeshMonitor](https://github.com/Yeraze/meshmonitor)
- Implements the mqttClientProxyMessage protocol from Meshtastic firmware

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/meshtastic-mqtt-proxy/issues)
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
