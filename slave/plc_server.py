#!/usr/bin/env python3
"""
Simulated PLC (Modbus/TCP server) for the OT lab.

Models a tank-level pump station:
  - CO0: pump (fills the tank when ON)
  - HR0: target level setpoint (unused by control logic yet, write target for attacks)
  - IR0: tank level, 0-1000 (x10, e.g. 423 = 42.3%)
  - IR1: flow rate, L/min (crude proxy, nonzero only while pump runs)
  - DI0: low-level float switch (dry-run protection)
  - DI1: high-level float switch (overflow)

DI0/DI1 are never written directly by any client - they are derived each
second by simulate_process() from the current tank level, the same way a
real float switch reflects physical water level rather than being set by
an operator. This gives the lab a live process instead of static values,
so legitimate polling and illegitimate writes both produce visible,
meaningful Modbus traffic for Zeek to log.
"""
import asyncio
import logging

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server import StartAsyncTcpServer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("plc-server")

LOW_LEVEL_PCT = 10.0    # DI0 trips below this
HIGH_LEVEL_PCT = 90.0   # DI1 trips above this
FILL_RATE_PCT_S = 0.5   # tank level gain per second while pump runs
DRAIN_RATE_PCT_S = 0.2  # tank level loss per second while pump is off (natural usage)
TICK_SECONDS = 1


def build_context() -> tuple[ModbusServerContext, ModbusSlaveContext]:
    store = ModbusSlaveContext(
        di = ModbusSequentialDataBlock(0, [0] * 100),
        co = ModbusSequentialDataBlock(0, [0] * 100),
        hr = ModbusSequentialDataBlock(0, [0] * 100),
        ir = ModbusSequentialDataBlock(0, [0] * 100)
    )

    store.setValues(1, 0, [1])      # CO0: pump = ON
    store.setValues(3, 0, [500])    # HR0: setpoint = 50.0%
    store.setValues(4, 0, [1])      # IR0: tank level = 1.0%
    store.setValues(4, 1, [0])      # IR1: flow rate = 0 L/min
    store.setValues(2, 0, [0])      # DI0: low-level switch = clear
    store.setValues(2, 1, [0])      # DI1: high-level switch = clear

    context = ModbusServerContext(slaves=store, single=True)
    return context, store


def build_identity() -> ModbusDeviceIdentification:
    identity = ModbusDeviceIdentification()
    identity.VendorName = "Simulated PLCs Inc."
    identity.ProductCode = "SIM-PLC"
    identity.ProductName = "Simulated Modbus PLC"
    identity.ModelName = "pymodbus-lab"
    identity.MajorMinorRevision = "1.0"
    return identity


async def simulate_process(store: ModbusSlaveContext) -> None:
    """Background loop: derives tank level/flow/float-switches from pump state.

    Runs independently of any client request, the same way a real process
    keeps moving whether or not an HMI happens to be polling at that instant.
    """
    level = 25.0  # starting level, matches the seeded IR0 above
    while True:
        pump_on = bool(store.getValues(1, 0, count=1)[0])  # read CO0

        level += FILL_RATE_PCT_S if pump_on else -DRAIN_RATE_PCT_S
        level = max(0.0, min(100.0, level))

        flow = 10 if pump_on else 0  # crude proxy, L/min

        store.setValues(4, 0, [int(level * 10)])    # IR0: level x10
        store.setValues(4, 1, [flow])               # IR1: flow rate

        store.setValues(2, 0, [1 if level < LOW_LEVEL_PCT else 0])  # DI0
        store.setValues(2, 1, [1 if level > HIGH_LEVEL_PCT else 0]) # DI1

        await asyncio.sleep(TICK_SECONDS)


async def main() -> None:
    context, store = build_context()
    identity = build_identity()
    asyncio.create_task(simulate_process(store))
    log.info("Starting Modbus/TCP server on 0.0.0.0:502")
    await StartAsyncTcpServer(context=context, identity=identity, address=("0.0.0.0", 502))


if __name__ == "__main__":
    asyncio.run(main())