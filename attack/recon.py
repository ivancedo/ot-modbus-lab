"""Asset recon - a quick sweep of the process bus.

Walks the known station addresses and reads a register off each one. It's just
a connectivity check: proof that this container is on the network and can speak
Modbus to the stations. Nothing noisy, nothing that changes state - but it's
exactly the kind of probing the Zeek rule next door is tuned to notice.
"""
from pymodbus.client import ModbusTcpClient

STATIONS = {
    "conveyor":    "172.20.0.10",
    "temperature": "172.20.0.11",
    "heater":      "172.20.0.12",
    "pressure":    "172.20.0.13",
    "relief":      "172.20.0.14",
}

for name, host in STATIONS.items():
    client = ModbusTcpClient(host, port=502)
    if not client.connect():
        print(f"{name:12} {host}  unreachable")
        continue
    rr = client.read_input_registers(0, 1)
    if rr.isError():
        print(f"{name:12} {host}  no answer")
    else:
        print(f"{name:12} {host}  up (IR0={rr.registers[0]})")
    client.close()
