
import sys
import os

try:
    import meshtastic
    from meshtastic import mesh_pb2
    print("Meshtastic imported:", meshtastic.__file__)
except ImportError:
    print("Meshtastic library not found")
    sys.exit(1)

# Check for crypto module
try:
    from meshtastic import crypto
    print("Crypto module found:", crypto)
except ImportError:
    print("No direct 'meshtastic.crypto' module found.")

# Try to find where encryption happens
# Usually it's in the Node or Interface class, or a helper
# Check dir(meshtastic)
print("Dir(meshtastic):", dir(meshtastic))

# Probe for default key generation
# AQ== (base64) -> \x01
default_key_bytes = b'\x01' + b'\x00'*15 # Guessing 16 bytes? Or 32?
print("Default key bytes (Guess 16):", default_key_bytes.hex())

# Check dependencies
try:
    import cryptography
    print("Cryptography lib:", cryptography.__version__)
except ImportError:
    print("Cryptography lib not found")

try:
    import Crypto
    print("PyCryptodome:", Crypto.__file__)
except ImportError:
    print("PyCryptodome not found")
