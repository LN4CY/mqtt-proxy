# MQTT Proxy Development - Task List

## ✅ Phase 1: TCP Proxy (Complete)

- [x] Initial proxy setup and connection
- [x] Fix AttributeError with TCPInterface instantiation
- [x] Implement channel mapping logic
- [x] Debug packet publishing to MQTT
- [x] Analyze iOS app source code for correct implementation
- [x] Implement mqttClientProxyMessage protocol (inbound)
- [x] Implement mqttClientProxyMessage protocol (outbound)
- [x] Simplify MQTT message forwarding
- [x] Test traceroutes on all channels
- [x] Test messages on all channels
- [x] Verify no duplicate messages
- [x] Production hardening (remove hardcoded values, pin dependencies)
- [x] Documentation (README, CONFIG, walkthrough)
- [x] Create git repository

## ✅ Phase 2: Multi-Interface Support (Complete)

### Refactoring
- [x] Extract common `_handleFromRadio()` logic into MQTTProxyMixin
- [x] Create interface factory pattern
- [x] Add `INTERFACE_TYPE` environment variable
- [x] Update main() to use factory
- [x] Update docker-compose.yml with new variables

### Serial Support
- [x] Create `RawSerialInterface` class
- [x] Add `SERIAL_PORT` configuration
- [ ] Test with USB-connected node
- [ ] Update documentation

### BLE Support
- [x] Create `RawBLEInterface` class
- [x] Add `BLE_ADDRESS` configuration
- [ ] Handle Docker BLE requirements (documentation)
- [ ] Test with BLE-connected node
- [ ] Update documentation

### Final Integration
- [ ] Test all three interface types
- [ ] Update README with interface examples
- [ ] Update CONFIG.md with new variables
- [ ] Merge feature branch to master
