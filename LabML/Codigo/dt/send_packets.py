#!/usr/bin/env python3
"""
send_packets.py — Traffic generator for the DT exercise.

Sends TCP packets with varying source/destination port combinations
to exercise all branches of the ML-generated L3 Decision Tree
encoded in the switch (see tree_L3_generado.txt and s1-commands.txt).

Run from inside Mininet (on h1):
    mininet> h1 python3 send_packets.py

The switch classifies each packet using the DT rules and forwards
it to h2, h3, or h4 accordingly. Use tcpdump on each destination
host to verify correct classification.

L3 Tree classification (src_port thresholds: [547, 1899, 3071, 49280, 60633],
                        dst_port thresholds: [67, 1917]):
    src_port in [0, 547]    + dst_port in [0, 67]      → Class 1 (Sensors)      → h2
    src_port in [0, 3071]    (other combinations)       → Class 4 (Others)       → h2
    src_port in [3072,49280] + dst_port in [0, 1917]    → Class 3 (Video)        → h3
    src_port in [3072,49280] + dst_port in [1918,65535] → Class 0 (Smart-Static) → h4
    src_port in [49281,60633] (any dst_port)            → Class 4 (Others)       → h2
    src_port in [60634,65535] (any dst_port)            → Class 3 (Video)        → h3
    non-TCP (ICMP, etc.)                                → default bucket         → h2
"""

from scapy.all import *
import random
import time

# Destination IP — the switch redirects based on DT classification
# The actual destination IP is irrelevant; egress port is determined by the DT
DST_IP = "10.0.1.100"   # fictitious IP; switch determines egress port
SRC_IP = "10.0.1.1"

print("=== DT Traffic Generator — UNSW IoT L3 Tree ===")
print("Sending packets across all branches of the decision tree...\n")

# ── Scenario 1: Class 1 (Sensors) → h2 ───────────────────────────────────────
# sport=100  → bucket 1 (0–547)    → sel2=1
# dport=50   → bucket 1 (0–67)     → sel3=1
# ipv4_exact: 1→1 1→3 1→3 → h2
print("[1] TCP sport=100,  dport=50    → Class 1 (Sensors)       — expected: h2")
for _ in range(5):
    pkt = IP(src=SRC_IP, dst=DST_IP) / TCP(sport=100, dport=50, flags="S")
    send(pkt, verbose=False)
time.sleep(1)

# ── Scenario 2: Class 4 (Others) low src port → h2 ───────────────────────────
# sport=2000 → bucket 3 (1900–3071) → sel2=3
# dport=500  → bucket 2 (68–1917)   → sel3=2
# ipv4_exact: 1→1 1→3 1→3 → h2
print("[2] TCP sport=2000, dport=500   → Class 4 (Others)        — expected: h2")
for _ in range(5):
    pkt = IP(src=SRC_IP, dst=DST_IP) / TCP(sport=2000, dport=500, flags="S")
    send(pkt, verbose=False)
time.sleep(1)

# ── Scenario 3: Class 3 (Video) medium src port → h3 ─────────────────────────
# sport=10000 → bucket 4 (3072–49280) → sel2=4
# dport=100   → bucket 2 (68–1917)    → sel3=2
# ipv4_exact: 1→1 4→4 1→2 → h3
print("[3] TCP sport=10000, dport=100  → Class 3 (Video)         — expected: h3")
for _ in range(5):
    pkt = IP(src=SRC_IP, dst=DST_IP) / TCP(sport=10000, dport=100, flags="S")
    send(pkt, verbose=False)
time.sleep(1)

# ── Scenario 4: Class 0 (Smart-Static) → h4 ──────────────────────────────────
# sport=10000 → bucket 4 (3072–49280) → sel2=4
# dport=5000  → bucket 3 (1918–65535) → sel3=3
# ipv4_exact: 1→1 4→4 3→3 → h4
print("[4] TCP sport=10000, dport=5000 → Class 0 (Smart-Static)  — expected: h4")
for _ in range(5):
    pkt = IP(src=SRC_IP, dst=DST_IP) / TCP(sport=10000, dport=5000, flags="S")
    send(pkt, verbose=False)
time.sleep(1)

# ── Scenario 5: Class 3 (Video) high src port → h3 ───────────────────────────
# sport=62000 → bucket 6 (60634–65535) → sel2=6
# dport=80    → bucket 2 (68–1917)     → sel3=2
# ipv4_exact: 1→1 6→6 1→3 → h3
print("[5] TCP sport=62000, dport=80   → Class 3 (Video)         — expected: h3")
for _ in range(5):
    pkt = IP(src=SRC_IP, dst=DST_IP) / TCP(sport=62000, dport=80, flags="S")
    send(pkt, verbose=False)
time.sleep(1)

# ── Scenario 6: Class 4 (Others) high-ephemeral src port → h2 ────────────────
# sport=55000 → bucket 5 (49281–60633) → sel2=5
# dport=8080  → bucket 3 (1918–65535)  → sel3=3
# ipv4_exact: 1→1 5→5 1→3 → h2
print("[6] TCP sport=55000, dport=8080 → Class 4 (Others)        — expected: h2")
for _ in range(5):
    pkt = IP(src=SRC_IP, dst=DST_IP) / TCP(sport=55000, dport=8080, flags="S")
    send(pkt, verbose=False)
time.sleep(1)

# ── Scenario 7: Non-TCP (ICMP) → default bucket → h2 ─────────────────────────
# Non-TCP forces action_select2=1 and action_select3=1 (TO-DO [8] else branch)
# → sel1=1, sel2=1, sel3=1 → ipv4_exact: 1→1 1→3 1→3 → h2
print("[7] ICMP (non-TCP)              → default bucket          — expected: h2")
for _ in range(5):
    pkt = IP(src=SRC_IP, dst=DST_IP) / ICMP()
    send(pkt, verbose=False)
time.sleep(1)

# ── Scenario 8: Random traffic mix ───────────────────────────────────────────
print("[8] Random mix — 20 TCP packets with random port combinations")
for _ in range(20):
    sport = random.randint(0, 65535)
    dport = random.randint(0, 65535)
    pkt = IP(src=SRC_IP, dst=DST_IP) / TCP(sport=sport, dport=dport, flags="S")
    send(pkt, verbose=False)

print("\nDone. Verify traffic distribution with tcpdump on h2, h3, h4.")
print("\nExpected approximate distribution (based on UNSW IoT dataset class ratios):")
print("  h2 (Classes 1+4 — Sensors+Others): ~80% of real traffic")
print("  h3 (Class 3     — Video):          ~16% of real traffic")
print("  h4 (Class 0     — Smart-Static):    ~5% of real traffic")
