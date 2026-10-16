# OT Modbus/TCP Lab

A small lab that simulates a multi-stage batch process over Modbus/TCP, with a
container to probe it and a Zeek container to watch for that probing. The repo
is split into three parts: `simulation/` (the plant), `attack/` (the probe) and
`detection/` (Zeek).

## Docker and network

Everything runs on one Docker bridge, `br-otlab` (`172.20.0.0/24`), marked
`internal` so the lab can't reach the outside world.

| Container     | Address       | What it is                                      |
|---------------|---------------|-------------------------------------------------|
| conveyor      | 172.20.0.10   | slave - conveyor motor                          |
| temperature   | 172.20.0.11   | slave - temperature sensor                      |
| heater        | 172.20.0.12   | slave - heater                                  |
| pressure      | 172.20.0.13   | slave - pressure sensor                         |
| relief        | 172.20.0.14   | slave - relief valve                            |
| master        | 172.20.0.20   | the controller that drives the whole line       |
| attacker      | 172.20.0.30   | idle box for running `recon.py` by hand         |
| zeek          | host          | sniffs `br-otlab` and logs to `detection/zeek/logs` |

Zeek runs with `network_mode: host` because a sniffer sitting *on* a bridge
can't see the other containers' traffic - the bridge only forwards each frame
to its destination. From the host it sees everything.

```bash
docker compose up -d --build          # start the lab
docker compose logs -f master         # watch the batch run
docker exec -it attacker python recon.py       # probe the stations
docker exec zeek tail -f /logs/notice.log      # see Zeek flag the probe
```

## The Modbus simulation

Each of the five stations is a Modbus **slave** (server): it holds the data and
answers requests, but never starts a conversation. The **master**
(`simulation/masters/master.py`) is the only **client** - it does all the
reading and writing. So every arrow on the bus starts at the master and points
at a station; the stations never talk to each other.

Each station exposes the same small map:

- **IR0** - its one reading (position, temperature, pressure, ...). The station
  updates this itself every second; the master only reads it.
- **coils** - its commands (motor, heat, valve, ...). The master writes these.
- **DI** - status flags the station raises when a reading crosses a threshold
  (`IN_PLACE`, `AT_TEMP`, `AT_PRESSURE`, ...).

The master runs a recipe as a small state machine:

```
IDLE ──part in place──▶ HEATING ──at soak temp──▶ PRESSURIZING
  ▲                                                     │
  └──────── vented ◀── RELEASE ◀── at full pressure ────┘
```

In each state the master turns on the coils that state needs (run the conveyor,
enable the heater, open the valve) and watches one station's reading to decide
when to move on. Because every step waits on the reading from the stage before
it, the five stations behave as one chained process rather than five
independent loops - that's the point of the lab.

The attacker speaks the same protocol from off to the side: `recon.py` just
reads a register from each station to prove it's reachable. Zeek knows the
master is the only host that should be reading the line, so a read from any
other address shows up in `notice.log`.
