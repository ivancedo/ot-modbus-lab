import logging
import select
import sys
import time

from pymodbus.client import ModbusTcpClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("hmi-client")

PLC_HOST = "172.20.0.10"    # MODBUS/TCP server address
PLC_PORT = 502              # MODBUS/TCP port
POLL_INTERVAL_SEC = 2       # Polling time step (s)


def read_command() -> str | None:
    # Non-blocking read of an operator command from stdin
    if select.select([sys.stdin], [], [], 0)[0]:
        return sys.stdin.readline().strip().lower()
    return None


def apply_command(client: ModbusTcpClient, cmd: str) -> None:
    # Turn the pump ON/OFF by writing CO0
    if cmd in ("on", "1"):
        client.write_coil(0, True)
        log.info("Operator command: pump ON")
    elif cmd in ("off", "0"):
        client.write_coil(0, False)
        log.info("Operator command: pump OFF")
    else:
        log.warning("Unknown command %r (use on/off)", cmd)


def poll_once(client: ModbusTcpClient) -> None:
    # Read IR0, IR1, DI0, DI1 and CO0
    rr_ir = client.read_input_registers(0, 2)
    rr_di = client.read_discrete_inputs(0, 2)
    rr_co = client.read_coils(0, 1)

    # Check there is no error
    if rr_ir.isError() or rr_di.isError() or rr_co.isError():
        log.warning("Poll error: ir=%s di=%s co=%s", rr_ir, rr_di, rr_co)
        return

    # Calculate real values
    level = rr_ir.registers[0] / 10.0
    flow = rr_ir.registers[1]
    low_switch = rr_di.bits[0]
    high_switch = rr_di.bits[1]
    pump = rr_co.bits[0]

    # Log the real values
    log.info(
        "level=%.1f%% flow=%dL/min pump=%s low_switch=%s high_switch=%s",
        level, flow, pump, low_switch, high_switch,
    )


def main() -> None:
    # Create the MODBUS/TCP client
    client = ModbusTcpClient(PLC_HOST, port=PLC_PORT)

    # Poll data continuously, applying operator commands between scans
    while True:
        if client.connect():
            poll_once(client)
            cmd = read_command()
            if cmd:
                apply_command(client, cmd)
        else:
            log.warning("Could not connect to PLC at %s:%s", PLC_HOST, PLC_PORT)
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()