#!/usr/bin/env python3
"""
send_legit.py -- Legitimate traffic generator from h1.

Simulates normal HTTP connections from h1 (10.0.1.1, legitimate client) to h3.
The RL agent must learn that blocking 10.0.1.0/26 also blocks this traffic
(action 0 = incorrect), while blocking 10.0.1.64/26 still lets h1 through.

Run from Mininet on h1:
    mininet> h1 python3 send_legit.py &
"""

import random
import time
from scapy.all import *

DST_IP   = '10.0.6.1'
DST_PORT = 80
IFACE    = 'eth0'

print(f"[LEGIT] Legitimate traffic h1→h3 ({DST_IP}:{DST_PORT})")
print(f"[LEGIT] Sending continuously -- Ctrl+C to stop\n")

try:
    while True:
        sport = random.randint(49152, 65535)
        # SYN
        pkt_syn = (Ether(src=get_if_hwaddr(IFACE), dst='ff:ff:ff:ff:ff:ff') /
                   IP(src='10.0.1.1', dst=DST_IP) /
                   TCP(sport=sport, dport=DST_PORT, flags='S'))
        sendp(pkt_syn, iface=IFACE, verbose=False)
        # ACK (simulates completed 3-way handshake)
        pkt_ack = (Ether(src=get_if_hwaddr(IFACE), dst='ff:ff:ff:ff:ff:ff') /
                   IP(src='10.0.1.1', dst=DST_IP) /
                   TCP(sport=sport, dport=DST_PORT, flags='A'))
        sendp(pkt_ack, iface=IFACE, verbose=False)
        time.sleep(0.5)   # ~2 packets per second (normal traffic rate)
except KeyboardInterrupt:
    print("\n[LEGIT] Stopped.")
