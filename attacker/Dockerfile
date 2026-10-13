FROM python:3.12-slim

RUN pip install --no-cache-dir pymodbus==3.6.9 scapy==2.5.0

WORKDIR /app
COPY scripts/ ./scripts/

# No CMD: this container stays idle (tty+stdin_open in compose).
# Run attacks manually with: docker exec -it attacker python scripts/<name>.py
CMD ["sleep", "infinity"]
