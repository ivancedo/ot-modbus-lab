#!/usr/bin/env python3
"""
ATT&CK for ICS T0846 - Remote System Discovery
ATT&CK for ICS T0842 - Network Sniffing (device fingerprinting via function code 0x2B)

Sweeps the lab subnet for hosts with TCP/502 open, then reads the Modbus
device identification object from anything that responds. This is the
kind of traffic a rogue engineering laptop generates on first contact
with an OT network.
"""
import socket

from pymodbus.client import ModbusTcpClient

SUBNET = "172.20.0."
HOSTS = range(1, 255)
PORT = 502


def port_open(ip: str, port: int, timeout: float = 0.3) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((ip, port)) == 0


def main() -> None:
    for i in HOSTS:
        ip = f"{SUBNET}{i}"
        if not port_open(ip, PORT):
            continue
        print(f"[+] {ip}:502 open")

        client = ModbusTcpClient(ip, port=PORT)
        if client.connect():
            # probe register map to fingerprint the device/application
            rr = client.read_holding_registers(0, 10)
            print(f"    holding registers 0-9: {rr}")
            client.close()


if __name__ == "__main__":
    main()
