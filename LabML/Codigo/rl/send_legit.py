#!/usr/bin/env python3
"""
send_legit.py — Generador de tráfico legítimo desde h1.

Simula conexiones HTTP normales desde h1 (10.0.1.1, cliente legítimo) hacia h3.
El agente RL debe aprender que bloquear 10.0.1.0/26 también bloquea este tráfico
(acción 0 = incorrecta), mientras que bloquear 10.0.1.64/26 deja pasar a h1.

Ejecutar desde Mininet en h1:
    mininet> h1 python3 send_legit.py &
"""

import random
import time
from scapy.all import *

DST_IP   = '10.0.6.1'
DST_PORT = 80
IFACE    = 'eth0'

print(f"[LEGIT] Tráfico legítimo h1→h3 ({DST_IP}:{DST_PORT})")
print(f"[LEGIT] Envío continuo — Ctrl+C para detener\n")

try:
    while True:
        sport = random.randint(49152, 65535)
        # SYN
        pkt_syn = (Ether(src=get_if_hwaddr(IFACE), dst='ff:ff:ff:ff:ff:ff') /
                   IP(src='10.0.1.1', dst=DST_IP) /
                   TCP(sport=sport, dport=DST_PORT, flags='S'))
        send(pkt_syn, iface=IFACE, verbose=False)
        # ACK (simula el 3-way handshake completo)
        pkt_ack = (Ether(src=get_if_hwaddr(IFACE), dst='ff:ff:ff:ff:ff:ff') /
                   IP(src='10.0.1.1', dst=DST_IP) /
                   TCP(sport=sport, dport=DST_PORT, flags='A'))
        send(pkt_ack, iface=IFACE, verbose=False)
        time.sleep(0.5)   # 2 paquetes por segundo (tráfico normal)
except KeyboardInterrupt:
    print("\n[LEGIT] Detenido.")
