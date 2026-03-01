#!/usr/bin/env python3
"""
Exercise-1 — L2 Forwarding Básico

Topología:  h1 ── s1 ── h2

Uso:
  1. Compilar P4:
       mkdir -p p4src/build
       p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json \
           --p4runtime-files p4src/build/p4info.txt p4src/main.p4

  2. Ejecutar topología (desde la carpeta del ejercicio):
       sudo python3 mininet/topo.py

  3. En otra terminal, instalar reglas:
       simple_switch_CLI --thrift-port 9090 < s1-commands.txt

  4. En la CLI de Mininet:
       mininet> pingall
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


class Exercise1Topo(Topo):
    def build(self):
        # Switch
        s1 = self.addSwitch('s1',
                            cls=P4Switch,
                            json_path=JSON_PATH,
                            thrift_port=9090)

        # Hosts
        h1 = self.addHost('h1', cls=P4Host,
                          mac='00:00:00:00:00:01',
                          ip='10.0.0.1/24')
        h2 = self.addHost('h2', cls=P4Host,
                          mac='00:00:00:00:00:02',
                          ip='10.0.0.2/24')

        # Links
        self.addLink(h1, s1, bw=2, delay='10ms', loss=5, use_htb=True)
        self.addLink(h2, s1, bw=5, delay='1ms', loss=2, use_htb=True)


def main():
    if not os.path.isfile(JSON_PATH):
        print("ERROR: No se encontró %s" % JSON_PATH)
        print("Compilar primero:")
        print("  mkdir -p p4src/build")
        print("  p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json \\")
        print("      --p4runtime-files p4src/build/p4info.txt p4src/main.p4")
        sys.exit(1)

    net = Mininet(topo=Exercise1Topo(), controller=None, link=TCLink)
    net.staticArp()
    net.start()

    print("\n" + "=" * 60)
    print("Topologia activa.  En otra terminal ejecutar:")
    print("  simple_switch_CLI --thrift-port 9090 < s1-commands.txt")
    print("Luego aqui:  pingall")
    print("=" * 60 + "\n")

    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel('info')
    main()
