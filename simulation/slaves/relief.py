import asyncio
import logging

from pymodbus.datastore import (
    ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext)
from pymodbus.server import StartAsyncTcpServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)-11s | %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger("relief")


def step(flow, opening):
    flow += 20 if opening else -20
    return max(0, min(100, flow))


async def process(store):
    flow = 0
    vented = False
    while True:
        opening = store.getValues(1, 0)[0]           # CO0 OPEN
        flow = step(flow, opening)
        store.setValues(4, 0, [flow * 10])           # IR0 flow, tenths of %

        wide_open = flow >= 90
        if wide_open != vented:
            log.info("valve open, venting" if wide_open else "valve closed")
            vented = wide_open
        store.setValues(2, 0, [int(wide_open)])      # DI0 VENTED

        await asyncio.sleep(1)


async def main():
    store = ModbusSlaveContext(
        co=ModbusSequentialDataBlock(0, [0] * 8),
        di=ModbusSequentialDataBlock(0, [0] * 8),
        ir=ModbusSequentialDataBlock(0, [0] * 8),
        hr=ModbusSequentialDataBlock(0, [0] * 8))
    context = ModbusServerContext(slaves=store, single=True)

    asyncio.create_task(process(store))
    log.info("online - CO0=OPEN, IR0=flow, DI0=VENTED")
    await StartAsyncTcpServer(context=context, address=("0.0.0.0", 502))


if __name__ == "__main__":
    asyncio.run(main())
