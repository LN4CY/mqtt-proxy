import inspect
import meshtastic.stream_interface
import meshtastic.tcp_interface

print("---- StreamInterface.__init__ ----")
try:
    print(inspect.getsource(meshtastic.stream_interface.StreamInterface.__init__))
except Exception as e:
    print(f"Error dumping __init__: {e}")

print("---- StreamInterface.__reader (try 1) ----")
try:
    # Access private method via name mangling
    print(inspect.getsource(meshtastic.stream_interface.StreamInterface._StreamInterface__reader))
except Exception as e:
    print(f"Error dumping __reader via mangled name: {e}")

print("---- StreamInterface.__reader (try 2: traversing members) ----")
try:
    for name, method in inspect.getmembers(meshtastic.stream_interface.StreamInterface):
        if "reader" in name:
             print(f"Found method: {name}")
             # try to dump it
             # print(inspect.getsource(method))
except Exception as e:
    print(f"Error listing members: {e}")
