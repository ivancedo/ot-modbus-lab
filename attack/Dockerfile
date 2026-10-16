FROM python:3.12-slim

RUN pip install --no-cache-dir pymodbus==3.6.9

WORKDIR /app
COPY recon.py .

# Container sits idle so you can run tools by hand:
#   docker exec -it attacker python recon.py
CMD ["sleep", "infinity"]
