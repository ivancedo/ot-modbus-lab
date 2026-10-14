#!/usr/bin/env python3
"""
Benign HMI/poller for the OT lab.
Polls the PLC at a fixed interval, like a real HMI scan cycle, so the
network has a realistic baseline to contrast against the attacker's
traffic. This is also what you tune later to study detection of
polling-interval drift.
"""
import logging
import time

from pymodbus.client import ModbusTcpClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("hmi-client")

PLC_HOST = "172.20.0.10"
PLC_PORT = 502
POLL_INTERVAL_SEC = 2  # fixed scan cycle; change this to study interval-drift detection


def poll_once(client: ModbusTcpClient) -> None:
    # read input registers 0-1 (tank level x10, flow rate L/min)
    rr_ir = client.read_input_registers(0, 2)
    # read discrete inputs 0-1 (low-level switch, high-level switch)
    rr_di = client.read_discrete_inputs(0, 2)
    # read coil 0 (pump state)
    rr_co = client.read_coils(0, 1)

    if rr_ir.isError() or rr_di.isError() or rr_co.isError():
        log.warning("Poll error: ir=%s di=%s co=%s", rr_ir, rr_di, rr_co)
        return

    level = rr_ir.registers[0] / 10.0
    flow = rr_ir.registers[1]
    low_switch = rr_di.bits[0]
    high_switch = rr_di.bits[1]
    pump = rr_co.bits[0]

    log.info(
        "level=%.1f%% flow=%dL/min pump=%s low_switch=%s high_switch=%s",
        level, flow, pump, low_switch, high_switch,
    )


def main() -> None:
    client = ModbusTcpClient(PLC_HOST, port=PLC_PORT)
    while True:
        if client.connect():
            poll_once(client)
        else:
            log.warning("Could not connect to PLC at %s:%s", PLC_HOST, PLC_PORT)
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()