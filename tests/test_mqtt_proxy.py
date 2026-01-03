
import os
import sys
import pytest
from unittest.mock import MagicMock, patch, ANY

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

# Load mqtt-proxy
mqtt_proxy = load_module("mqtt_proxy", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mqtt-proxy.py"))

class TestMQTTProxy:

    @patch('paho.mqtt.client.Client')
    def test_on_mqtt_connect_success(self, mock_mqtt_client_class):
        """Test successful MQTT connection callback"""
        client = mock_mqtt_client_class.return_value
        
        # Mock global current_mqtt_cfg
        mock_cfg = MagicMock()
        mock_cfg.root = "msh"
        mqtt_proxy.current_mqtt_cfg = mock_cfg
        mqtt_proxy.my_node_id = "1234abcd"

        # Test with success code 0
        mqtt_proxy.on_mqtt_connect(client, None, None, 0)
        
        # Verify subscription calls
        # Topic wildcard: msh/#
        expected_topic = "msh/#"
        client.subscribe.assert_called_with(expected_topic)
        
        # Verify status publish
        expected_stat_topic = "msh/2/stat/!1234abcd"
        client.publish.assert_called_with(expected_stat_topic, payload="online", retain=True)

    def test_environment_variables_defaults(self):
        """Test that default environment variables are set correctly"""
        # Check module level constants
        assert mqtt_proxy.TCP_NODE_HOST == "localhost"
        assert mqtt_proxy.TCP_NODE_PORT == 4403
        assert mqtt_proxy.POLL_INTERVAL == 1

    @patch('meshtastic.tcp_interface.TCPInterface')
    def test_mqtt_message_processing(self, mock_tcp_interface):
        """Test processing of an incoming MQTT message"""
        client = MagicMock()
        userdata = None
        
        # Create a mock message
        # Use a DIFFERENT node ID in the topic to avoid loop protection (ignoring own messages)
        message = MagicMock()
        message.topic = "msh/2/c/LongFast/!anothernode"
        message.payload = b"test_payload"
        
        # We need a mock interface to be present
        mqtt_proxy.iface = mock_tcp_interface.return_value
        # Mock sendToRadioImpl which is what is called
        mqtt_proxy.iface._sendToRadioImpl = MagicMock()
        
        # Call the callback
        mqtt_proxy.on_mqtt_message_callback(client, userdata, message)
        
        # Verify the interface._sendToRadioImpl was called
        mqtt_proxy.iface._sendToRadioImpl.assert_called_once()
        
        # Verify content of call
        args, _ = mqtt_proxy.iface._sendToRadioImpl.call_args
        to_radio = args[0]
        assert to_radio.HasField("mqttClientProxyMessage")
        assert to_radio.mqttClientProxyMessage.topic == message.topic
        assert to_radio.mqttClientProxyMessage.data == message.payload

    def test_proxy_mixin_handle_from_radio(self):
        """Test the MQTTProxyMixin receiving a message from radio to publish to MQTT"""
        # Create a dummy class that inherits from the Mixin to test it
        class TestInterface(mqtt_proxy.MQTTProxyMixin):
             # Mock super() behavior to avoid actual library calls
             def _handleFromRadio(self, fromRadio):
                 super()._handleFromRadio(fromRadio)

        # Mock the mqtt_client global
        mock_mqtt_client = MagicMock()
        mqtt_proxy.mqtt_client = mock_mqtt_client
        
        # Instantiate test interface
        interface = TestInterface()
        
        # We need to mock super() call inside the mixin. 
        # Since we can't easily mock super() in the mixin definition without reloading,
        # we'll assume the basic functionality logic is:
        # 1. Check if HasField("mqttClientProxyMessage")
        # 2. Publish to MQTT
        
        # Create a FromRadio protobuf with mqttClientProxyMessage
        from meshtastic import mesh_pb2
        from_radio = mesh_pb2.FromRadio()
        mqtt_msg = from_radio.mqttClientProxyMessage
        mqtt_msg.topic = "msh/2/json/LongFast"
        mqtt_msg.data = b"payload"
        mqtt_msg.retained = False
        
        # We need to patch the super() call in the module's Mixin or just handle the exception it throws
        # because the Mixin calls super()._handleFromRadio which won't exist in our standalone TestInterface
        # unless we inherit from something else. But strict unit testing the Mixin requires ensuring it calls super.
        
        # Simplest approach: Patch 'super' in the module or allow it to fail/mock.
        # But we really want to test the `if decoded.HasField("mqttClientProxyMessage")` block.
        
        # Let's use patch.object on the mixin itself? No, mixin is a class.
        
        # We will wrap the call in a try/except to ignore the super() failure, 
        # OR we can mock the super() by making TestInterface inherit from a Mock that has _handleFromRadio
        
        class MockParent:
            def _handleFromRadio(self, packet):
                pass
                
        class TestInterfaceWithParent(mqtt_proxy.MQTTProxyMixin, MockParent):
            pass
            
        interface = TestInterfaceWithParent()
        
        # Execute
        interface._handleFromRadio(from_radio)
        
        # Verify MQTT publish
        mock_mqtt_client.publish.assert_called_with("msh/2/json/LongFast", b"payload", retain=False)

    @patch('paho.mqtt.client.Client')
    def test_handle_sigint(self, mock_client):
        """Test clean shutdown on SIGINT"""
        # Setup mocks
        mqtt_proxy.mqtt_client = mock_client.return_value
        mqtt_proxy.iface = MagicMock()
        mqtt_proxy.running = True
        
        # Simulate SIGINT catch
        # The function doesn't raise SystemExit, it just sets running=False and closes things
        mqtt_proxy.handle_sigint(None, None)
            
        assert mqtt_proxy.running == False
        # Verify close calls
        mqtt_proxy.iface.close.assert_called()
        mqtt_proxy.mqtt_client.disconnect.assert_called()

    def test_on_connection_lost(self):
        """Test reaction to Meshtastic connection loss"""
        # Setup mock interface
        mock_iface = MagicMock()
        mqtt_proxy.iface = mock_iface
        
        # Call on_connection_lost
        mqtt_proxy.on_connection_lost(mock_iface)
        
        # Verify it attempts to close (which triggers restart loop in main)
        mock_iface.close.assert_called_once()

    @patch('socket.socket')
    def test_create_interface(self, mock_socket):
        """Test interface factory"""
        # Test TCP (default in mock/env)
        mqtt_proxy.INTERFACE_TYPE = "tcp"
        try:
            iface = mqtt_proxy.create_interface()
            assert isinstance(iface, mqtt_proxy.TCPInterface)
        except Exception as e:
            pytest.fail(f"create_interface raised exception: {e}")

        # Check serial
        with patch('meshtastic.serial_interface.SerialInterface') as mock_serial:
            mqtt_proxy.INTERFACE_TYPE = "serial"
            mqtt_proxy.create_interface()
            mock_serial.assert_called_with(mqtt_proxy.SERIAL_PORT)

        # Test invalid
        mqtt_proxy.INTERFACE_TYPE = "unknown"
        with pytest.raises(ValueError):
            mqtt_proxy.create_interface()
        # Check params (based on defaults in module)
        # TCPInterface(host, portNumber=...)
        # We can't easily check args of instantiated object unless we mock the class init
        
        with patch('meshtastic.serial_interface.SerialInterface') as mock_serial:
            mqtt_proxy.INTERFACE_TYPE = "serial"
            mqtt_proxy.create_interface()
            mock_serial.assert_called_with(mqtt_proxy.SERIAL_PORT)

        # Test invalid
        mqtt_proxy.INTERFACE_TYPE = "unknown"
        with pytest.raises(ValueError):
            mqtt_proxy.create_interface()

    def test_on_mqtt_disconnect(self):
        """Test MQTT disconnect callback"""
        mqtt_proxy.mqtt_connected = True
        
        # Graceful
        mqtt_proxy.on_mqtt_disconnect(None, None, 0)
        assert mqtt_proxy.mqtt_connected == False
        
        # Unexpected
        with patch.object(mqtt_proxy.logger, 'warning') as mock_warn:
            mqtt_proxy.on_mqtt_disconnect(None, None, 1)
            assert mqtt_proxy.mqtt_connected == False
            mock_warn.assert_called()

    def test_on_connection(self):
        """Test Meshtastic connection established callback"""
        mock_iface = MagicMock()
        mock_node = MagicMock()
        mock_node.nodeNum = 0x1234abcd
        # Setup node.nodeId
        mock_node.nodeId = "!1234abcd"
        
        # Channels
        mock_channel = MagicMock()
        mock_channel.index = 0
        mock_channel.settings.name = "LongFast"
        mock_channel.role = "PRIMARY"
        mock_node.channels = [mock_channel]
        
        # Module Config (MQTT)
        mock_mqtt = MagicMock()
        mock_mqtt.enabled = True
        mock_mqtt.address = "1.2.3.4"
        mock_mqtt.port = 1883
        mock_mqtt.username = "user"
        mock_mqtt.password = "pass"
        mock_mqtt.root = "msh"
        
        mock_node.moduleConfig.mqtt = mock_mqtt
        mock_iface.localNode = mock_node
        
        # We need to mock mqtt.Client to verify it is initialized and connected
        with patch('paho.mqtt.client.Client') as mock_client_cls:
            mock_client = mock_client_cls.return_value
            
            mqtt_proxy.on_connection(mock_iface)
            
            # Verify node ID parsing works
            assert mqtt_proxy.my_node_id == "1234abcd"
            
            # Verify Client setup
            mock_client.username_pw_set.assert_called_with("user", "pass")
            mock_client.connect.assert_called_with("1.2.3.4", 1883, 60)
            mock_client.loop_start.assert_called()

    @patch('paho.mqtt.client.Client')
    def test_on_receive_legacy(self, mock_client_cls):
        """Test legacy on_receive logic (Mesh Packet -> MQTT 'ServiceEnvelope')"""
        # Setup global mqtt client
        mqtt_proxy.mqtt_client = mock_client_cls.return_value
        mqtt_proxy.mqtt_client.publish.return_value.rc = 0
        
        # Setup config
        mqtt_proxy.current_mqtt_cfg = MagicMock()
        mqtt_proxy.current_mqtt_cfg.root = "msh"
        mqtt_proxy.my_node_id = "test_gateway"
        
        # Setup Interface and Node for channel lookup
        mock_iface = MagicMock()
        mock_node = MagicMock()
        c0 = MagicMock()
        c0.index = 0
        c0.settings.name = "LongFast"
        mock_node.channels = [c0]
        mock_iface.localNode = mock_node
        mqtt_proxy.iface = mock_iface
        
        # Create a mock packet
        packet = MagicMock()
        # Ensure it has SerializeToString
        # We assign it as an attribute that is also a mock
        packet.SerializeToString = MagicMock(return_value=b"mock_protobuf")
        
        # We need to make sure the hasattr check works on the instance
        # MagicMock(spec=...) might be better but let's try this
        # If the code checks type(packet), we might see a warning but it shouldn't fail unless it returns.
        # Code: if not hasattr(...): return
        
        packet.channel = 0
        setattr(packet, "from", 123456789) 
        packet.to = 0xFFFFFFFF
        
        # Verify call
        mqtt_proxy.on_receive(packet, mock_iface)
        
        # Expected topic construction: msh/2/e/LongFast/!075bcd15 (hex of 123456789)
        # 123456789 = 0x075BCD15
        expected_from = "!{:08x}".format(123456789)
        expected_topic = f"msh/2/e/LongFast/{expected_from}"
        
        # The payload is a serialized ServiceEnvelope
        # We can't match exact bytes easily without constructing a real protobuf
        # So we match using ANY or just check topic
        mqtt_proxy.mqtt_client.publish.assert_called()
        args, kwargs = mqtt_proxy.mqtt_client.publish.call_args
        assert args[0] == expected_topic
        # retain should be False by default for generic packets
        # assert kwargs.get('retain') == False # retain might not be in kwargs if positional

