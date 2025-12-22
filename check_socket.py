import socket
import time

try:
    print("Connecting to meshmonitor:4404...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(("meshmonitor", 4404))
    print("Connected. Waiting for data...")
    data = s.recv(1024)
    print(f"Received {len(data)} bytes: {data}")
    # print hex
    if data:
        print(f"Hex: {data.hex()}")
    s.close()
except Exception as e:
    print(f"Error: {e}")
