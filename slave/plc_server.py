import asyncio
import logging

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server import StartAsyncTcpServer

# Professional log format shared by every component: wall-clock timestamp,
# fixed-width level, logger name, then the message.
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-11s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt=DATE_FORMAT)

log = logging.getLogger("plc.server")       # Lifecycle / server events
proc_log = logging.getLogger("plc.process")  # Simulated process behaviour
io_log = logging.getLogger("plc.io")         # Client writes hitting the data model

LOW_LEVEL_PCT = 10.0    # Low level alarm threshold (%)
HIGH_LEVEL_PCT = 90.0   # High level alarm threshold (%)
PUMP_FILL_PCT_S = 0.5   # Inflow when the pump is ON (%/s)
FAUCET_DRAIN_PCT_S = 0.3  # Outflow when the faucet is ON (%/s)
TICK_SECONDS = 1        # Simulation time step (s)
HEARTBEAT_TICKS = 15    # Emit a process snapshot every N ticks

# Human-readable names for the coil / holding-register addresses a client can
# write, keyed by Modbus address, for clearer log lines.
COIL_NAMES = {0: "PUMP", 1: "FAUCET"}


class LoggingSlaveContext(ModbusSlaveContext):
    """Slave context that logs every *client-originated* write.

    Writes land here as ``setValues(function_code, address, values)``. Coil
    writes (FC 5/15) and holding-register writes (FC 6/16) are the only ones a
    Modbus client can issue; our own process simulation instead writes input
    registers / discrete inputs, so those never reach this branch. That makes
    these the security-relevant events in the lab (operator *or* attacker
    commands reaching the PLC), so they are logged at WARNING.

    ``armed`` stays False during startup initialisation so the boot-time writes
    are not mistaken for client traffic.
    """

    WRITE_FCS = {5: "coil", 15: "coil", 6: "holding-reg", 16: "holding-reg"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.armed = False

    def setValues(self, fc_as_hex, address, values):
        if self.armed and fc_as_hex in self.WRITE_FCS:
            kind = self.WRITE_FCS[fc_as_hex]
            reg = "CO" if kind == "coil" else "HR"
            for offset, value in enumerate(values):
                addr = address + offset
                name = COIL_NAMES.get(addr) if kind == "coil" else None
                where = f"{reg}{addr}" + (f" ({name})" if name else "")
                io_log.warning("CLIENT WRITE  fc=%-2d %-14s <- %s",
                               fc_as_hex, where, value)
        super().setValues(fc_as_hex, address, values)


def build_context() -> tuple[ModbusServerContext, ModbusSlaveContext]:
    # Define the MODBUS data model
    store = LoggingSlaveContext(
        di = ModbusSequentialDataBlock(0, [0] * 100),   # 2
        co = ModbusSequentialDataBlock(0, [0] * 100),   # 1
        hr = ModbusSequentialDataBlock(0, [0] * 100),   # 3
        ir = ModbusSequentialDataBlock(0, [0] * 100)    # 4
    )

    # Set initial values (before arming, so these are not logged as client writes)
    store.setValues(1, 0, [0])      # Pump OFF on startup
    store.setValues(1, 1, [0])      # Faucet OFF on startup
    store.setValues(4, 0, [500])    # Tank level 50% on startup
    store.setValues(4, 1, [0])      # Water flow dummy value on startup
    store.setValues(2, 0, [0])      # Low alarm OFF on startup
    store.setValues(2, 1, [0])      # High alarm OFF on startup

    store.armed = True              # From now on, log client writes

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
    tick = 0
    # Previous-state trackers so we only log on change, not every tick.
    prev_pump = prev_faucet = None
    prev_low = prev_high = 0
    prev_clamp = None  # None / "EMPTY" / "FULL"

    proc_log.info("Process simulation started (initial level %.1f%%)", level)

    while True:
        tick += 1

        # Read CO0/CO1 and get if the pump and faucet are ON/OFF
        pump_on = bool(store.getValues(1, 0, count=1)[0])
        faucet_on = bool(store.getValues(1, 1, count=1)[0])

        # Log actuator state changes (driven by whatever last wrote the coils)
        if pump_on != prev_pump:
            proc_log.info("Pump %s", "ON" if pump_on else "OFF")
            prev_pump = pump_on
        if faucet_on != prev_faucet:
            proc_log.info("Faucet %s", "ON" if faucet_on else "OFF")
            prev_faucet = faucet_on

        # Net flow rate = inflow - outflow (%/s, may be negative)
        rate = (PUMP_FILL_PCT_S if pump_on else 0.0) - (FAUCET_DRAIN_PCT_S if faucet_on else 0.0)

        # Adjust the tank level with the net rate over this tick
        level += rate * TICK_SECONDS
        level = max(0.0, min(100.0, level))

        # Log tank hitting / leaving a physical limit
        clamp = "FULL" if level >= 100.0 else "EMPTY" if level <= 0.0 else None
        if clamp != prev_clamp:
            if clamp:
                proc_log.warning("Tank %s (level clamped at %.0f%%)", clamp, level)
            else:
                proc_log.info("Tank no longer at a limit (level %.1f%%)", level)
            prev_clamp = clamp

        low = 1 if level < LOW_LEVEL_PCT else 0
        high = 1 if level > HIGH_LEVEL_PCT else 0

        # Log alarm set / clear transitions
        if low != prev_low:
            (proc_log.warning if low else proc_log.info)(
                "LOW-LEVEL alarm %s (level %.1f%%, threshold %.0f%%)",
                "SET" if low else "CLEARED", level, LOW_LEVEL_PCT)
            prev_low = low
        if high != prev_high:
            (proc_log.warning if high else proc_log.info)(
                "HIGH-LEVEL alarm %s (level %.1f%%, threshold %.0f%%)",
                "SET" if high else "CLEARED", level, HIGH_LEVEL_PCT)
            prev_high = high

        # Set the new values (level as 0.1%, flow rate as signed 0.01%/s)
        store.setValues(4, 0, [int(level * 10)])
        store.setValues(4, 1, [int(round(rate * 100)) & 0xFFFF])
        store.setValues(2, 0, [low])
        store.setValues(2, 1, [high])

        # Periodic heartbeat so the log shows the process is alive and healthy
        if tick % HEARTBEAT_TICKS == 0:
            proc_log.info(
                "state | level=%5.1f%% flow=%+6.2f%%/s pump=%-3s faucet=%-3s "
                "low=%d high=%d",
                level, rate, "ON" if pump_on else "OFF",
                "ON" if faucet_on else "OFF", low, high)

        # Wait for the next scan
        await asyncio.sleep(TICK_SECONDS)


async def main() -> None:
    # Startup banner summarising the simulated plant and its setpoints
    log.info("=" * 60)
    log.info("Simulated Water-Tank PLC  (Modbus/TCP)")
    log.info("  low alarm  < %.0f%%   high alarm > %.0f%%", LOW_LEVEL_PCT, HIGH_LEVEL_PCT)
    log.info("  pump +%.1f%%/s   faucet -%.1f%%/s   tick %ds",
             PUMP_FILL_PCT_S, FAUCET_DRAIN_PCT_S, TICK_SECONDS)
    log.info("  CO0=PUMP  CO1=FAUCET  IR0=level  IR1=flow  DI0=low  DI1=high")
    log.info("=" * 60)

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