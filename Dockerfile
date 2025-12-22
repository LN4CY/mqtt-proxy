FROM python:3.9-slim

WORKDIR /app

# Install system dependencies including BlueZ for BLE support
RUN apt-get update && apt-get install -y \
    bluez \
    bluez-tools \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mqtt-proxy.py .
RUN chmod +x mqtt-proxy.py

CMD ["python3", "-u", "mqtt-proxy.py"]
