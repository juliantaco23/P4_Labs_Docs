#!/usr/bin/env python3
"""
Exercise-3 — Medición de Timestamps entre 2 Switches (MySec)

Topología:  h1 ── s1 ── s2 ── h2

El protocolo MySec (IP proto 169) viaja h1->s1->s2->s1->h1 midiendo
tiempos de procesamiento en cada switch.

Uso:
  1. Compilar P4:
       mkdir -p p4src/build
       p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json \
           --p4runtime-files p4src/build/p4info.txt p4src/main.p4

  2. Ejecutar topología (desde la carpeta del ejercicio):
       sudo python3 mininet/topo.py

  3. En otra terminal, instalar reglas en ambos switches:
       simple_switch_CLI --thrift-port 9090 < s1-commands.txt
       simple_switch_CLI --thrift-port 9091 < s2-commands.txt

  4. Verificar en la CLI de Mininet:
       mininet> pingall
       mininet> h1 python3 send_mysec.py
"""

import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p4_mininet import P4Switch, P4Host

from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.link import TCLink

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, '..', 'p4src', 'build', 'bmv2.json')


class Exercise3Topo(Topo):
    def build(self):
        # Switches: s1 (thrift 9090), s2 (thrift 9091)
        s1 = self.addSwitch('s1',
                            cls=P4Switch,
                            json_path=JSON_PATH,
                            thrift_port=9090)
        s2 = self.addSwitch('s2',
                            cls=P4Switch,
                            json_path=JSON_PATH,
                            thrift_port=9091)

        # Hosts
        h1 = self.addHost('h1', cls=P4Host,
                          ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', cls=P4Host,
                          ip='10.0.0.2/24', mac='00:00:00:00:00:02')

        # Links:  h1-s1 (s1:port1), s1-s2 (s1:port2, s2:port1), s2-h2 (s2:port2)
        self.addLink(h1, s1, bw=5, delay='5ms', loss=1, use_htb=True)
        self.addLink(s1, s2, bw=5, delay='5ms', loss=1, use_htb=True)
        self.addLink(s2, h2, bw=5, delay='5ms', loss=1, use_htb=True)


def main():
    if not os.path.isfile(JSON_PATH):
        print("ERROR: No se encontro %s" % JSON_PATH)
        print("Compilar primero:")
        print("  mkdir -p p4src/build")
        print("  p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json \\")
        print("      --p4runtime-files p4src/build/p4info.txt p4src/main.p4")
        sys.exit(1)

    net = Mininet(topo=Exercise3Topo(), controller=None, link=TCLink)
    net.staticArp()
    net.start()

    print("\n" + "=" * 60)
    print("Topologia activa (2 switches).  En otra terminal:")
    print("  simple_switch_CLI --thrift-port 9090 < s1-commands.txt")
    print("  simple_switch_CLI --thrift-port 9091 < s2-commands.txt")
    print("")
    print("Verificar:  pingall")
    print("MySec test: h1 python3 send_mysec.py")
    print("=" * 60 + "\n")

    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel('info')
    main()
