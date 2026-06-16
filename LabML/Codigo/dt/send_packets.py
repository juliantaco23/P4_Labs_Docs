#!/usr/bin/env python3
"""
send_packets.py — Generador de tráfico TCP para el ejercicio DT.

Envía paquetes TCP con combinaciones variadas de source/destination ports
para ejercitar las distintas ramas del árbol de decisión codificado en el switch.

Ejecutar desde dentro de Mininet (en h1):
    mininet> h1 python3 send_packets.py

El switch clasificará cada paquete y lo enviará al host destino correspondiente
(h2, h3 o h4) según las reglas instaladas.  Observa en los xterms de h2/h3/h4
con tcpdump para verificar qué clase de tráfico llega a cada host.
"""

from scapy.all import *
import random
import time

# Destino genérico — el switch redirige según clasificación DT
# No importa mucho la IP de destino en este ejercicio;
# lo que importa son los puertos TCP.
DST_IP   = "10.0.1.100"   # IP ficticia; el switch decide el puerto de salida
SRC_IP   = "10.0.1.1"

print("=== DT Traffic Generator ===")
print("Enviando paquetes TCP con combinaciones de puertos variadas...\n")

# ── Escenario 1: src well-known + dst well-known → Clase B → h3 ──────────────
print("[1] TCP src=80 dst=443 (well-known → well-known) — espera: h3")
for _ in range(5):
    pkt = IP(src=SRC_IP, dst=DST_IP) / TCP(sport=80, dport=443, flags="S")
    send(pkt, verbose=False)
time.sleep(1)

# ── Escenario 2: src ephemeral + dst well-known → Clase B → h3 ───────────────
print("[2] TCP src=55000 dst=80 (ephemeral → well-known) — espera: h3")
for _ in range(5):
    pkt = IP(src=SRC_IP, dst=DST_IP) / TCP(sport=55000, dport=80, flags="S")
    send(pkt, verbose=False)
time.sleep(1)

# ── Escenario 3: src ephemeral + dst alto → Clase C → h4 ─────────────────────
print("[3] TCP src=60000 dst=8080 (ephemeral → alto) — espera: h4")
for _ in range(5):
    pkt = IP(src=SRC_IP, dst=DST_IP) / TCP(sport=60000, dport=8080, flags="S")
    send(pkt, verbose=False)
time.sleep(1)

# ── Escenario 4: ICMP (non-TCP) → Clase A → h2 ───────────────────────────────
print("[4] ICMP (non-TCP) — espera: h2")
for _ in range(5):
    pkt = IP(src=SRC_IP, dst=DST_IP) / ICMP()
    send(pkt, verbose=False)
time.sleep(1)

# ── Escenario 5: tráfico aleatorio (mezcla) ───────────────────────────────────
print("[5] Mezcla aleatoria de 20 paquetes TCP con puertos random")
for _ in range(20):
    sport = random.randint(0, 65535)
    dport = random.randint(0, 65535)
    pkt = IP(src=SRC_IP, dst=DST_IP) / TCP(sport=sport, dport=dport, flags="S")
    send(pkt, verbose=False)

print("\nListo. Verifica la distribución con tcpdump en h2, h3, h4.")
