# OT Modbus/TCP Lab: Attack Simulation + Zeek Detection

A small, Raspberry Pi-friendly lab for researching OT protocol attacks and
detecting them with Zeek. Four containers on an isolated Docker bridge:

```
            br-otlab (172.20.0.0/24, internal)
┌──────────────┐  Modbus/TCP   ┌──────────────┐
│    master    │──────────────▶│    slave     │
│ 172.20.0.11  │   port 502    │ 172.20.0.10  │
└──────────────┘               └──────────────┘
       ▲                              ▲
       │                              │
┌──────────────┐                      │
│   attacker   │──────────────────────┘
│ 172.20.0.12  │
└──────────────┘

┌──────────────┐
│     zeek     │  network_mode: host, sniffing br-otlab
└──────────────┘
```

- **slave**: `pymodbus` Modbus/TCP server simulating a PLC (coils,
  discrete inputs, holding/input registers).
- **master**: benign poller, reads the PLC every 2s like a real HMI
  scan cycle. This is the traffic baseline.
- **attacker**: idle container with ready-made attack scripts, run
  on-demand via `docker exec`.
- **zeek**: sniffs the Docker bridge interface directly (containers on a
  bridge network are invisible to a 4th container on the same network -
  Linux bridges only forward unicast to the destination port).

## Why Modbus/TCP first

Zeek's `modbus` analyzer is built in, no third-party package needed. The
protocol has no auth, so detection has to be behavioral (who talks, how
often) rather than signature-based - a good first lesson for OT NSM.

## Prerequisites

- Docker + Docker Compose v2 (`docker compose version`)
- 64-bit Raspberry Pi OS (Bookworm or later) if running on a Pi
- Verify `zeek/zeek:latest` has an arm64 manifest before pulling on a Pi:
  `docker manifest inspect zeek/zeek:latest | grep arm64`

## Quick start

```bash
git clone https://github.com/ivancedo/ot-modbus-lab
cd ot-modbus-lab
docker compose up -d --build
```

Check the HMI is polling and the PLC is responding:

```bash
docker compose logs -f modbus-master
```

Check Zeek is seeing traffic:

```bash
docker exec zeek tail -f /logs/modbus.log
```

If `modbus.log` is empty after a minute, see **Troubleshooting** below.

## Running attacks

```bash
# T0846 - recon / device scan
docker exec -it attacker python scripts/01_recon_scan.py

# T0855 - unauthorized write (turns the simulated pump off)
docker exec -it attacker python scripts/02_unauthorized_write.py

# T0836 - parameter tampering (rogue setpoint)
docker exec -it attacker python scripts/03_parameter_tamper.py

# T0814 - denial of service via request flood
docker exec -it attacker python scripts/04_diagnostic_dos.py
```

Each script is commented with the MITRE ATT&CK for ICS technique it
demonstrates. See `attacker/scripts/`.

## Detections

`zeek/scripts/modbus-detect.zeek` implements two behavioral checks:

1. **Unauthorized_Modbus_Write** - any Modbus write from a source other
   than the known HMI address (`172.20.0.11`) raises a notice. Change
   `known_engineering_hosts` in the script if you re-IP the lab.
2. **Modbus_Request_Flood** - more than `flood_threshold` requests from
   one source within `flood_window` (SumStats-based rate detection).

Notices land in `zeek/logs/notice.log`:

```bash
docker exec zeek tail -f /logs/notice.log
```

Useful log fields for manual analysis:

```bash
# all writes, with function code and address
docker exec zeek zeek-cut -d ts id.orig_h id.resp_h func addr < /logs/modbus.log

# just notices
docker exec zeek zeek-cut -d ts note msg < /logs/notice.log
```

## Raspberry Pi (4GB) notes

- Skip Elastic/OpenSearch/Malcolm - the JVM alone will exceed what's
  comfortable here. Use `zeek-cut`/`jq` on the logs, or ship them to a
  lightweight stack (Loki + Grafana) if you want dashboards.
- Don't compile Zeek from source on-device; use the official image.
- Point `./zeek/logs` at a USB SSD if you'll run this for hours - continuous
  logging wears out SD cards.
- This compose file is sized for 4GB: 4 light containers, no JVM.

## Troubleshooting

**`modbus.log` is empty.**
Confirm the bridge name: `ip link show br-otlab` on the host. If Docker
picked a different name despite `driver_opts`, update the `-i` argument
in `docker-compose.yml`'s `zeek` command to match.

**Zeek logs show no entries despite tcpdump showing traffic.**
Check the `-C` flag is present (ignores checksum errors from veth TX
offload, which otherwise look like corrupt packets to Zeek).

**`attacker` can't reach `plc-server`.**
The network is `internal: true` (no egress), but inter-container traffic
on the bridge is unaffected. If you added host port mappings, `internal`
has to come off for those - that's expected, not a bug.

## Next steps

- Add DNP3 as a second protocol (also native in Zeek).
- Pull in public OT PCAPs (e.g. the ICS-pcap collection) and replay them
  through this same Zeek setup for a second source of ground truth.
- Add ICSNPP analyzers (`zkg install` on the host, mount the resulting
  packages into the Zeek site folder) for S7comm/EtherNet/IP/BACnet.

## References

- MITRE ATT&CK for ICS: <https://attack.mitre.org/matrices/ics/>
- Zeek Modbus analyzer: <https://docs.zeek.org/en/current/scripts/base/protocols/modbus/main.zeek.html>
- Modbus Application Protocol spec: <https://modbus.org/specs.php>
