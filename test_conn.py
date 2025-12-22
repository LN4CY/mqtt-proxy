from meshtastic.tcp_interface import TCPInterface
import time
import logging
import sys

# Configure logging to stdout
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

print('Connecting to 192.168.50.50:4404...')
try:
    iface = TCPInterface('192.168.50.50', 4404)
    print('Connected!')
    
    # Wait for node info (optional)
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
