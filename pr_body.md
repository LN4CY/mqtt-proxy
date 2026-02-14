## Overview
This PR addresses communication failures and health check loopholes encountered after a `meshmonitor` upgrade. The root cause was a race condition where the MQTT handler was initialized before the virtual node provided its configuration, causing the proxy to sit idle while incorrectly reporting as "healthy".

## Key Changes
- **MQTT Lifecycle**: Centralized MQTT initialization in `_init_mqtt`. Startup is now deferred until **after** `_wait_for_config()` successfully completes, ensuring credentials and root topics are available.
- **Improved Health Monitoring**:
    - The health check now detects if a Meshtastic interface is active but the MQTT handler is uninitialized.
    - Added type safety for telemetry counters to prevent crashes in the watchdog logic.
- **Robustness**: Moved `os` and `sys` imports to the top level in `mqtt-proxy.py` to ensure consistency and fix related bugs.
- **Test Suite**:
    - Resolved `ModuleNotFoundError` in tests by fixing `sys.path`.
    - Added new test cases to verify the "MQTT handler uninitialized" failure state.
    - Fixed mocking issues in `test_meshtastic_extended.py`.

## Verification Results
- 19 automated tests passed (`test_proxy_health.py`, `test_meshtastic_extended.py`, `test_mqtt_proxy.py`).
- Verified that connection loss during the upgrade triggers the expected watchdog restart.
