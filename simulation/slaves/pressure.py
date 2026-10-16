import asyncio
import logging

from pymodbus.datastore import (
    ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext)
from pymodbus.server import StartAsyncTcpServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)-11s | %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger("pressure")

TARGET = 150      # kPa the batch is pressurised to
LIMIT = 200       # kPa we consider an overpressure event


def step(pressure, build, vent):
    if vent:
        pressure -= 10
    elif build:
        pressure += 6
    else:
        pressure -= 1
    return max(0, min(250, pressure))


async def process(store):
    pressure = 0
    at_target = False
    over = False
    while True:
        build = store.getValues(1, 0)[0]             # CO0 BUILD
        vent = store.getValues(1, 1)[0]              # CO1 VENT
        pressure = step(pressure, build, vent)
        store.setValues(4, 0, [pressure * 10])       # IR0 pressure, tenths of kPa

        if (pressure >= TARGET) != at_target:
            at_target = pressure >= TARGET
            log.info("at target pressure" if at_target else "pressure below target")
        store.setValues(2, 0, [int(at_target)])      # DI0 AT_PRESSURE

        if (pressure >= LIMIT) != over:
            over = pressure >= LIMIT
            log.warning("OVERPRESSURE %d kPa", pressure) if over else log.info("pressure back in range")
        store.setValues(2, 1, [int(over)])           # DI1 OVERPRESSURE

        await asyncio.sleep(1)


async def main():
    store = ModbusSlaveContext(
        co=ModbusSequentialDataBlock(0, [0] * 8),
        di=ModbusSequentialDataBlock(0, [0] * 8),
        ir=ModbusSequentialDataBlock(0, [0] * 8),
        hr=ModbusSequentialDataBlock(0, [0] * 8))
    context = ModbusServerContext(slaves=store, single=True)

    asyncio.create_task(process(store))
    log.info("online - CO0=BUILD, CO1=VENT, IR0=pressure, DI0=AT_PRESSURE, DI1=OVERPRESSURE")
    await StartAsyncTcpServer(context=context, address=("0.0.0.0", 502))


if __name__ == "__main__":
    asyncio.run(main())
