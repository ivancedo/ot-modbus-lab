import asyncio
import logging

from pymodbus.datastore import (
    ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext)
from pymodbus.server import StartAsyncTcpServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)-11s | %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger("temperature")

AMBIENT = 20    # degrees C we settle back to with the heat off
TARGET = 70     # soak temperature the master is waiting for


def step(temp, heating):
    temp += 2 if heating else -1
    return max(AMBIENT, min(80, temp))


async def process(store):
    temp = AMBIENT
    hot = False
    while True:
        heating = store.getValues(1, 0)[0]           # CO0 HEAT
        temp = step(temp, heating)
        store.setValues(4, 0, [temp * 10])           # IR0 temperature, tenths of C

        at_temp = temp >= TARGET
        if at_temp != hot:
            log.info("reached soak temperature" if at_temp else "cooling down")
            hot = at_temp
        store.setValues(2, 0, [int(at_temp)])        # DI0 AT_TEMP

        await asyncio.sleep(1)


async def main():
    store = ModbusSlaveContext(
        co=ModbusSequentialDataBlock(0, [0] * 8),
        di=ModbusSequentialDataBlock(0, [0] * 8),
        ir=ModbusSequentialDataBlock(0, [AMBIENT * 10] + [0] * 7),
        hr=ModbusSequentialDataBlock(0, [0] * 8))
    context = ModbusServerContext(slaves=store, single=True)

    asyncio.create_task(process(store))
    log.info("online - CO0=HEAT, IR0=temperature, DI0=AT_TEMP")
    await StartAsyncTcpServer(context=context, address=("0.0.0.0", 502))


if __name__ == "__main__":
    asyncio.run(main())
