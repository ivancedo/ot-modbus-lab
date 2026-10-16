import asyncio
import logging

from pymodbus.datastore import (
    ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext)
from pymodbus.server import StartAsyncTcpServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)-11s | %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger("heater")


def step(power, enabled):
    power += 10 if enabled else -20
    return max(0, min(100, power))


async def process(store):
    power = 0
    hot = False
    while True:
        enabled = store.getValues(1, 0)[0]           # CO0 ENABLE
        power = step(power, enabled)
        store.setValues(4, 0, [power * 10])          # IR0 element output, tenths of %

        ready = power >= 90
        if ready != hot:
            log.info("element at full power" if ready else "element winding down")
            hot = ready
        store.setValues(2, 0, [int(ready)])          # DI0 HOT

        await asyncio.sleep(1)


async def main():
    store = ModbusSlaveContext(
        co=ModbusSequentialDataBlock(0, [0] * 8),
        di=ModbusSequentialDataBlock(0, [0] * 8),
        ir=ModbusSequentialDataBlock(0, [0] * 8),
        hr=ModbusSequentialDataBlock(0, [0] * 8))
    context = ModbusServerContext(slaves=store, single=True)

    asyncio.create_task(process(store))
    log.info("online - CO0=ENABLE, IR0=element, DI0=HOT")
    await StartAsyncTcpServer(context=context, address=("0.0.0.0", 502))


if __name__ == "__main__":
    asyncio.run(main())
