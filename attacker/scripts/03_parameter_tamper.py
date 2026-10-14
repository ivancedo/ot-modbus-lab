from pymodbus.client import ModbusTcpClient

PLC_HOST = "172.20.0.10"
PLC_PORT = 502
ROGUE_SETPOINT = 9999

client = ModbusTcpClient(PLC_HOST, port=PLC_PORT)
if client.connect():
    rr = client.write_register(0, ROGUE_SETPOINT)
    print(f"write_register(0, {ROGUE_SETPOINT}) -> {rr}")
    client.close()
else:
    print("connection failed")
