import socket
import time

HOST = '192.168.50.50'
PORT = 4404

try:
    print(f"Connecting to {HOST}:{PORT}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((HOST, PORT))
    print("Connected!")
    
    # Send some bytes just to see if it accepts
    # Meshtastic checks for magic bytes?
    # START1 = 0x94
    # START2 = 0xc3
    # HEADER_LEN = 4
    # proto_header = b'\x94\xc3\x00\x00' 
    # s.send(proto_header)
    
    time.sleep(1)
    s.close()
    print("Closed")
except Exception as e:
    print(f"Error: {e}")
