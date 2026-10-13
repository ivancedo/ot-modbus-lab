FROM python:3.12-slim

RUN pip install --no-cache-dir pymodbus==3.6.9

WORKDIR /app
COPY hmi_poller.py .

CMD ["python", "hmi_poller.py"]
