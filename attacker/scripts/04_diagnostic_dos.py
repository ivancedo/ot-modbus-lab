from pymodbus.client import ModbusTcpClient

PLC_HOST = "172.20.0.10"
PLC_PORT = 502
REQUESTS = 2000

client = ModbusTcpClient(PLC_HOST, port=PLC_PORT)
if client.connect():
    for _ in range(REQUESTS):
        client.read_holding_registers(0, 1)
    print(f"sent {REQUESTS} back-to-back read requests")
    client.close()
else:
    print("connection failed")
