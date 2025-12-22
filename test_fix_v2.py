from meshtastic.tcp_interface import TCPInterface
import time
import logging
import sys

# Configure logging to stdout
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

print('Connecting to 192.168.50.50:4404 using correct keyword args...')
try:
    # ROOT CAUSE FIX: Pass portNumber as keyword arg, leaving debugOut as None (or explicit)
    # Previous code passed 4404 as 2nd arg which is debugOut!
    iface = TCPInterface('192.168.50.50', portNumber=4404, debugOut=sys.stdout)
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
