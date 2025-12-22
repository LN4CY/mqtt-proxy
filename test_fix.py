from meshtastic.stream_interface import StreamInterface
from meshtastic.tcp_interface import TCPInterface
import time
import logging
import sys
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

# --- MONKEY PATCH START ---
print("Applying monkey patch for StreamInterface._writeBytes...")
original_writeBytes = StreamInterface._writeBytes

def patched_writeBytes(self, b):
    # If self.stream is an integer (file descriptor), use os.write
    if isinstance(self.stream, int):
        # logger.debug(f"Patched write to fd {self.stream}")
        try:
            os.write(self.stream, b)
        except Exception as e:
            print(f"Error writing to fd {self.stream}: {e}")
        return

    # Otherwise call original (handles None or file-like objects)
    return original_writeBytes(self, b)

StreamInterface._writeBytes = patched_writeBytes
# --- MONKEY PATCH END ---

print('Connecting to 192.168.50.50:4404...')
try:
    iface = TCPInterface('192.168.50.50', 4404)
    print('Connected!')
    
    start = time.time()
    while not iface.localNode.nodeNum:
        if time.time() - start > 10:
             print("Timeout waiting for identity")
             break
        time.sleep(1)
        
    print(f"Node ID: {iface.localNode.nodeNum}")
    
    time.sleep(2)
    iface.close()
    print('Closed')
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
