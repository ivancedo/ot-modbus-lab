#!/usr/bin/env python3
"""
Simulated PLC (Modbus/TCP server) for the OT lab.
Exposes coils, discrete inputs, holding registers and input registers
with plausible starting values, so legitimate polling and illegitimate
writes both produce visible Modbus traffic for Zeek to log.
"""
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


def build_context() -> ModbusServerContext:
    # 100 addresses per table, arbitrary but enough for lab scenarios
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0] * 100),   # discrete inputs (read-only, sensors)
        co=ModbusSequentialDataBlock(0, [0] * 100),   # coils (read/write, actuators)
        hr=ModbusSequentialDataBlock(0, [0] * 100),   # holding registers (read/write, setpoints)
        ir=ModbusSequentialDataBlock(0, [0] * 100),   # input registers (read-only, measurements)
    )
    # seed a couple of "process values" so polling returns something meaningful
    store.setValues(4, 0, [250])   # IR0: simulated temperature x10 (25.0C)
    store.setValues(3, 0, [100])   # HR0: simulated setpoint
    store.setValues(1, 0, [1])     # CO0: "pump running" = ON

    # single-slave context; unit_id checks disabled since this lab has one device
    context = ModbusServerContext(slaves=store, single=True)
    return context


def build_identity() -> ModbusDeviceIdentification:
    identity = ModbusDeviceIdentification()
    identity.VendorName = "OT-Lab"
    identity.ProductCode = "SIM-PLC"
    identity.ProductName = "Simulated Modbus PLC"
    identity.ModelName = "pymodbus-lab"
    identity.MajorMinorRevision = "1.0"
    return identity


async def main() -> None:
    context = build_context()
    identity = build_identity()
    log.info("Starting Modbus/TCP server on 0.0.0.0:502")
    await StartAsyncTcpServer(context=context, identity=identity, address=("0.0.0.0", 502))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
