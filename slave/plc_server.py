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

LOW_LEVEL_PCT = 10.0    # Low level alarm threshold (%)
HIGH_LEVEL_PCT = 90.0   # High level alarm threshold (%)
PUMP_FILL_PCT_S = 0.5   # Inflow when the pump is ON (%/s)
FAUCET_DRAIN_PCT_S = 0.3  # Outflow when the faucet is ON (%/s)
TICK_SECONDS = 1        # Simulation time step (s)


def build_context() -> tuple[ModbusServerContext, ModbusSlaveContext]:
    # Define the MODBUS data model
    store = ModbusSlaveContext(
        di = ModbusSequentialDataBlock(0, [0] * 100),   # 2
        co = ModbusSequentialDataBlock(0, [0] * 100),   # 1
        hr = ModbusSequentialDataBlock(0, [0] * 100),   # 3
        ir = ModbusSequentialDataBlock(0, [0] * 100)    # 4
    )

    # Set initial values
    store.setValues(1, 0, [0])      # Pump OFF on startup
    store.setValues(1, 1, [0])      # Faucet OFF on startup
    store.setValues(4, 0, [500])    # Tank level 50% on startup
    store.setValues(4, 1, [0])      # Water flow dummy value on startup
    store.setValues(2, 0, [0])      # Low alarm OFF on startup
    store.setValues(2, 1, [0])      # High alarm OFF on startup

    context = ModbusServerContext(slaves=store, single=True)
    return context, store


def build_identity() -> ModbusDeviceIdentification:
    # Set identity data
    identity = ModbusDeviceIdentification()
    identity.VendorName = "Simulated PLCs Inc."
    identity.ProductCode = "SIM-PLC"
    identity.ProductName = "Simulated Modbus PLC"
    identity.ModelName = "pymodbus-lab"
    identity.MajorMinorRevision = "1.0"
    return identity


async def simulate_process(store: ModbusSlaveContext) -> None:
    level = 50.0
    while True:
        # Read CO0/CO1 and get if the pump and faucet are ON/OFF
        pump_on = bool(store.getValues(1, 0, count=1)[0])
        faucet_on = bool(store.getValues(1, 1, count=1)[0])

        # Net flow rate = inflow - outflow (%/s, may be negative)
        rate = (PUMP_FILL_PCT_S if pump_on else 0.0) - (FAUCET_DRAIN_PCT_S if faucet_on else 0.0)

        # Adjust the tank level with the net rate over this tick
        level += rate * TICK_SECONDS
        level = max(0.0, min(100.0, level))

        # Set the new values (level as 0.1%, flow rate as signed 0.01%/s)
        store.setValues(4, 0, [int(level * 10)])
        store.setValues(4, 1, [int(round(rate * 100)) & 0xFFFF])
        store.setValues(2, 0, [1 if level < LOW_LEVEL_PCT else 0])
        store.setValues(2, 1, [1 if level > HIGH_LEVEL_PCT else 0])

        # Wait for the next scan
        await asyncio.sleep(TICK_SECONDS)


async def main() -> None:
    # Generate the data model
    context, store = build_context()

    # Generate the identity
    identity = build_identity()

    # Creates a task for the simulation
    asyncio.create_task(simulate_process(store))

    # Creates the TCP server
    log.info("Starting Modbus/TCP server on 0.0.0.0:502")
    await StartAsyncTcpServer(context=context, identity=identity, address=("0.0.0.0", 502))


if __name__ == "__main__":
    asyncio.run(main())