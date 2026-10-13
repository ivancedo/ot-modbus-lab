FROM python:3.12-slim

# pymodbus>=3.6 ships an asyncio server; pin a known-good version for reproducibility
RUN pip install --no-cache-dir pymodbus==3.6.9

WORKDIR /app
COPY plc_server.py .

EXPOSE 502/tcp

CMD ["python", "plc_server.py"]
