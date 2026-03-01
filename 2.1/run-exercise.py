#!/usr/bin/env python3
"""
Exercise-2.1 — ARP Responder dinámico (sin ONOS)

Sin ONOS, las entradas ARP se instalan manualmente via CLI (el mismo P4
que aprendería dinámicamente con la app Java ArpResponder).

Topología:  h1 ── s1 ── h2

Uso:
  1. Compilar P4:
       p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json \
           --p4runtime-files p4src/build/p4info.txt p4src/sw_gita.p4

  2. Ejecutar topología:
       sudo python3 run_exercise.py

  3. En otra terminal, instalar reglas:
       simple_switch_CLI --thrift-port 9090 < s1-commands.txt

  4. En la CLI de Mininet:
       mininet> h1 arping -c 1 10.0.0.2
       mininet> pingall
"""

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from p4_mininet import P4Switch, P4Host

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.link import TCLink

JSON_PATH = os.path.join(os.path.dirname(__file__), 'p4src', 'build', 'bmv2.json')


class Exercise21Topo(Topo):
    def build(self):
        s1 = self.addSwitch('s1',
                            cls=P4Switch,
                            json_path=JSON_PATH,
                            thrift_port=9090)

        h1 = self.addHost('h1', cls=P4Host,
                          ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', cls=P4Host,
                          ip='10.0.0.2/24', mac='00:00:00:00:00:02')

        self.addLink(h1, s1, bw=2, delay='10ms', loss=5, use_htb=True)
        self.addLink(h2, s1, bw=5, delay='1ms', loss=2, use_htb=True)


def main():
    if not os.path.isfile(JSON_PATH):
        print("ERROR: No se encontró %s" % JSON_PATH)
        print("Compilar primero:")
        print("  mkdir -p p4src/build")
        print("  p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json \\")
        print("      --p4runtime-files p4src/build/p4info.txt p4src/sw_gita.p4")
        sys.exit(1)

    net = Mininet(topo=Exercise21Topo(), controller=None, link=TCLink)
    net.start()

    print("\n" + "=" * 60)
    print("Topología activa.  En otra terminal ejecutar:")
    print("  simple_switch_CLI --thrift-port 9090 < s1-commands.txt")
    print("Luego aquí:  h1 arping -c 1 10.0.0.2")
    print("             pingall")
    print("=" * 60 + "\n")

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    main()
