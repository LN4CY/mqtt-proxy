from meshtastic.tcp_interface import TCPInterface
import time
import logging
import sys
from google.protobuf.message import DecodeError

# Monkey-patch to suppress DecodeError
original_handleFromRadio = TCPInterface._handleFromRadio

def patched_handleFromRadio(self, fromRadio):
    try:
        original_handleFromRadio(self, fromRadio)
    except DecodeError as e:
        print(f"Warning: Suppressed Protobuf Decode Error: {e}")
    except Exception as e:
        print(f"Warning: Suppressed General Error: {e}")

TCPInterface._handleFromRadio = patched_handleFromRadio

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

print('Connecting to 192.168.50.50:4404 to list channels...')
try:
    iface = TCPInterface('192.168.50.50', portNumber=4404, debugOut=sys.stdout)
    print('Connected!')
    
    print('Connected! Waiting for node identity and channels...')
    
    start = time.time()
    while True:
        # Wait up to 30 seconds
        if time.time() - start > 30:
             print("Timeout waiting for identity/channels")
             break
        
        if iface.localNode.nodeNum and iface.localNode.channels:
            # We have both identity and channels
            break
            
        time.sleep(1)
        
    node = iface.localNode
    print(f"Node ID: {node.nodeNum}")
    
    if node.channels:
        print("\n--- Channel Listing ---")
        for c in node.channels:
            name = c.settings.name if c.settings else "None"
            print(f"Index {c.index}: '{name}' (Role: {c.role})")
    else:
        print("No channels found on node object (or timeout).")

    iface.close()
    print('Closed')
except Exception as e:
    print(f"Error: {e}")
    # import traceback
    # traceback.print_exc()
