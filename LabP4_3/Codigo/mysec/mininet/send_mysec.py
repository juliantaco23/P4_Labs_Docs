#!/usr/bin/env python3
"""
send_mysec.py — Prueba del ejercicio 3 (MySec in-switch timestamp)

Envía un paquete MySec (IP proto 169) desde h1 hacia h2.
El paquete viaja: h1 → s1 → s2 → s1 → h1
S1 y S2 escriben sus timestamps en los campos de la cabecera mysec_t.
Al retornar, se imprimen los valores de latencia calculados.

Uso desde la CLI de Mininet:
    mininet> h1 python3 mininet/send_mysec.py
"""

from scapy.all import *
import sys

# ── Constantes de la topología ───────────────────────────────────────────────
SRC_MAC  = "00:00:00:00:00:01"  # h1
DST_MAC  = "00:00:00:00:00:02"  # h2 (sólo como dirección de destino inicial)
SRC_IP   = "10.0.0.1"
DST_IP   = "10.0.0.2"
IFACE    = "eth0"               # interfaz de h1 en Mininet
TIMEOUT  = 3                    # segundos esperando respuesta

# ── Definición de la cabecera MySec ─────────────────────────────────────────
# Debe coincidir exactamente con mysec_t en main.p4:
#   bit<4>  ingress_port
#   bit<4>  egres_port
#   bit<48> process_time_sw1
#   bit<48> process_time_sw2
#   bit<48> egress_time_sw1
#   bit<48> ingress_back_time_sw1
#   bit<48> total
#   bit<48> th
class MySec(Packet):
    name = "MySec"
    fields_desc = [
        BitField("ingress_port",           0, 4),
        BitField("egres_port",             0, 4),
        BitField("process_time_sw1",       0, 48),
        BitField("process_time_sw2",       0, 48),
        BitField("egress_time_sw1",        0, 48),
        BitField("ingress_back_time_sw1",  0, 48),
        BitField("total",                  0, 48),
        BitField("th",                     0, 48),
    ]


def print_mysec(pkt):
    """Imprime los campos de timestamp del paquete de respuesta."""
    if MySec in pkt:
        m = pkt[MySec]
        print("\n" + "=" * 60)
        print("  MySec — Resultados de latencia in-switch")
        print("=" * 60)
        print(f"  process_time_sw1      : {m.process_time_sw1} ns  (latencia egress S1)")
        print(f"  process_time_sw2      : {m.process_time_sw2} ns  (latencia egress S2)")
        print(f"  egress_time_sw1       : {m.egress_time_sw1}  (timestamp egress S1)")
        print(f"  ingress_back_time_sw1 : {m.ingress_back_time_sw1}")
        print(f"  total                 : {m.total}")
        print(f"  th                    : {m.th}")
        print("=" * 60)
        if m.process_time_sw1 == 0 and m.process_time_sw2 == 0:
            print("  ⚠  Ambos tiempos son 0 — el paquete no recorrió el camino esperado")
            print("     Verificar reglas TS_table en s1 y s2")
        else:
            print("  ✓  Timestamps registrados correctamente")
        print()
    else:
        print("  ⚠  El paquete recibido no contiene cabecera MySec")
        pkt.show()


def main():
    # Construcción del paquete:
    # Flags iniciales: ingress_port=1, egres_port=2
    # Esto dispara el branch correcto en el egress de s1 (camino de ida)
    pkt = (
        Ether(src=SRC_MAC, dst=DST_MAC) /
        IP(src=SRC_IP, dst=DST_IP, proto=169) /
        MySec(ingress_port=1, egres_port=2)
    )

    print(f"\nEnviando paquete MySec por {IFACE}...")
    pkt.show2()

    # srp1: envía y espera una respuesta en capa 2
    resp = srp1(pkt, iface=IFACE, timeout=TIMEOUT, verbose=False)

    if resp is None:
        print(f"\n  ✗  No se recibió respuesta en {TIMEOUT}s")
        print("     Verificar:")
        print("       1. Reglas instaladas:  simple_switch_CLI --thrift-port 9090 < s1-commands.txt")
        print("                              simple_switch_CLI --thrift-port 9091 < s2-commands.txt")
        print("       2. pingall funciona antes de enviar MySec")
        sys.exit(1)

    print("\nPaquete recibido:")
    resp.show2()
    print_mysec(resp)


if __name__ == "__main__":
    main()
