from meshtastic.tcp_interface import TCPInterface
import logging
import sys
import traceback

# Monkey patch logging to print exception traceback
old_error = logging.Logger.error
def new_error(self, msg, *args, **kwargs):
    if "Unexpected exception" in str(msg) or "Unexpected OSError" in str(msg):
        print("!!! CAPTURED EXCEPTION IN LOGGER !!!")
        print(f"Message: {msg}")
        # The exception object might be formatted into the string in the caller
        # e.g. logger.error(f"... {ex}")
        # In that case we can't get the object easily unless we inspect the frame.
        
        # However, we can just print the stack of THE LOGGER CALL.
        # This tells us WHERE the error was caught (end of __reader), but not where it originated.
        # But wait! If we are inside the exception handler, sys.exc_info() should work!
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if exc_type:
            print("Found active exception info:")
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        else:
            print("No active exception info found via sys.exc_info()")

    old_error(self, msg, *args, **kwargs)

logging.Logger.error = new_error
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

print("Connecting to 192.168.50.50:4404...")
try:
    iface = TCPInterface('192.168.50.50', 4404)
    print("Connected!")
    import time
    time.sleep(2)
    iface.close()
except:
    pass
