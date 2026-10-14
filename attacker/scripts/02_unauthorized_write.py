from pymodbus.client import ModbusTcpClient

PLC_HOST = "172.20.0.10"
PLC_PORT = 502

client = ModbusTcpClient(PLC_HOST, port=PLC_PORT)
if client.connect():
    rr = client.write_coil(0, False)
    print(f"write_coil(0, False) -> {rr}")
    client.close()
else:
    print("connection failed")
