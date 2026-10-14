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
            rr = client.read_holding_registers(0, 10)
            print(f"    holding registers 0-9: {rr}")
            client.close()


if __name__ == "__main__":
    main()
