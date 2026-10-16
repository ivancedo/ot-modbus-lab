import asyncio
import logging

from pymodbus.datastore import (
    ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext)
from pymodbus.server import StartAsyncTcpServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)-11s | %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger("conveyor")


def step(position, motor_on):
    position += 5 if motor_on else -10
    return max(0, min(100, position))


async def process(store):
    position = 0
    in_place = False
    while True:
        motor_on = store.getValues(1, 0)[0]          # CO0 MOTOR
        position = step(position, motor_on)
        store.setValues(4, 0, [position * 10])       # IR0 position, tenths of %

        parked = position >= 99
        if parked != in_place:
            log.info("part %s", "parked, IN_PLACE" if parked else "on the move")
            in_place = parked
        store.setValues(2, 0, [int(parked)])         # DI0 IN_PLACE

        await asyncio.sleep(1)


async def main():
    store = ModbusSlaveContext(
        co=ModbusSequentialDataBlock(0, [0] * 8),
        di=ModbusSequentialDataBlock(0, [0] * 8),
        ir=ModbusSequentialDataBlock(0, [0] * 8),
        hr=ModbusSequentialDataBlock(0, [0] * 8))
    context = ModbusServerContext(slaves=store, single=True)

    asyncio.create_task(process(store))
    log.info("online - CO0=MOTOR, IR0=position, DI0=IN_PLACE")
    await StartAsyncTcpServer(context=context, address=("0.0.0.0", 502))


if __name__ == "__main__":
    asyncio.run(main())
