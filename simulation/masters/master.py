import logging
import time

from pymodbus.client import ModbusTcpClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)-11s | %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger("master")

STATIONS = {
    "conveyor":    {"host": "172.20.0.10", "coils": ["MOTOR"]},
    "temperature": {"host": "172.20.0.11", "coils": ["HEAT"]},
    "heater":      {"host": "172.20.0.12", "coils": ["ENABLE"]},
    "pressure":    {"host": "172.20.0.13", "coils": ["BUILD", "VENT"]},
    "relief":      {"host": "172.20.0.14", "coils": ["OPEN"]},
}

PART_IN_PLACE = 99     # conveyor position, %
SOAK_TEMP = 70         # temperature, C
FULL_PRESSURE = 150    # pressure, kPa
VENTED_PRESSURE = 10   # pressure, kPa

clients = {name: ModbusTcpClient(cfg["host"], port=502) for name, cfg in STATIONS.items()}


def read_value(name):
    c = clients[name]
    if not c.connect():
        return None
    rr = c.read_input_registers(0, 1)
    return None if rr.isError() else rr.registers[0] / 10.0


def set_coil(name, index, on):
    c = clients[name]
    if c.connect():
        c.write_coil(index, on)


RECIPE = {
    "IDLE": {"conveyor": {"MOTOR": True}},
    "HEATING": {"heater": {"ENABLE": True}, "temperature": {"HEAT": True}},
    "PRESSURIZING": {"heater": {"ENABLE": True}, "temperature": {"HEAT": True}, "pressure": {"BUILD": True}},
    "RELEASE": {"pressure": {"VENT": True}, "relief": {"OPEN": True}},
}


def advance(state, pv):
    if state == "IDLE" and pv["conveyor"] >= PART_IN_PLACE:
        return "HEATING"
    if state == "HEATING" and pv["temperature"] >= SOAK_TEMP:
        return "PRESSURIZING"
    if state == "PRESSURIZING" and pv["pressure"] >= FULL_PRESSURE:
        return "RELEASE"
    if state == "RELEASE" and pv["pressure"] <= VENTED_PRESSURE:
        return "IDLE"
    return state


def main():
    log.info("batch master up - recipe IDLE -> HEATING -> PRESSURIZING -> RELEASE")
    state = "IDLE"
    coils = {n: {c: False for c in cfg["coils"]} for n, cfg in STATIONS.items()}

    while True:
        pv = {name: read_value(name) for name in STATIONS}
        if None in pv.values():
            log.warning("waiting for stations: %s",
                        ", ".join(n for n, v in pv.items() if v is None))
            time.sleep(1)
            continue

        wanted = RECIPE.get(state, {})
        for name, cfg in STATIONS.items():
            for index, coil in enumerate(cfg["coils"]):
                on = wanted.get(name, {}).get(coil, False)
                if on != coils[name][coil]:
                    set_coil(name, index, on)
                    log.info("%s.%s -> %s", name, coil, "ON" if on else "OFF")
                    coils[name][coil] = on

        log.info("%-12s | conv %3.0f%%  temp %2.0fC  elem %3.0f%%  press %3.0fkPa  flow %3.0f%%",
                 state, pv["conveyor"], pv["temperature"], pv["heater"],
                 pv["pressure"], pv["relief"])

        nxt = advance(state, pv)
        if nxt != state:
            log.info(">>> %s -> %s", state, nxt)
            state = nxt

        time.sleep(1)


if __name__ == "__main__":
    main()
