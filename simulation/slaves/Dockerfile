FROM python:3.12-slim

RUN pip install --no-cache-dir pymodbus==3.6.9

WORKDIR /app
COPY *.py .

EXPOSE 502/tcp