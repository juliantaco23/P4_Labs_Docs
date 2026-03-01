#!/usr/bin/env python3
"""
Exercise-4 — VLAN 802.1Q Tagging/Untagging entre 2 switches

Topología:
    h1 (VLAN 10) -+           +- h3 (VLAN 10)
                   s1 === s2
    h2 (VLAN 20) -+  trunk    +- h4 (VLAN 20)

  s1: port1=h1, port2=h2, port3=trunk
  s2: port1=h3, port2=h4, port3=trunk

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
       mininet> h1 ping h3   (misma VLAN 10 — OK)
       mininet> h2 ping h4   (misma VLAN 20 — OK)
       mininet> h1 ping h4   (cross-VLAN — debe FALLAR)
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


class Exercise4Topo(Topo):
    def build(self):
        # Switches
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
                          ip='10.10.10.1/29', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', cls=P4Host,
                          ip='20.20.20.1/26', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', cls=P4Host,
                          ip='10.10.10.2/29', mac='00:00:00:00:00:03')
        h4 = self.addHost('h4', cls=P4Host,
                          ip='20.20.20.2/26', mac='00:00:00:00:00:04')

        # Links (orden determina puerto en el switch)
        self.addLink(s1, h1, bw=5, delay='5ms', loss=1, use_htb=True)  # s1:port1
        self.addLink(s1, h2, bw=5, delay='5ms', loss=1, use_htb=True)  # s1:port2
        self.addLink(s2, h3, bw=5, delay='5ms', loss=1, use_htb=True)  # s2:port1
        self.addLink(s2, h4, bw=5, delay='5ms', loss=1, use_htb=True)  # s2:port2
        self.addLink(s1, s2, bw=5, delay='5ms', loss=1, use_htb=True)  # s1:port3, s2:port3 - trunk


def main():
    if not os.path.isfile(JSON_PATH):
        print("ERROR: No se encontro %s" % JSON_PATH)
        print("Compilar primero:")
        print("  mkdir -p p4src/build")
        print("  p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json \\")
        print("      --p4runtime-files p4src/build/p4info.txt p4src/main.p4")
        sys.exit(1)

    net = Mininet(topo=Exercise4Topo(), controller=None, link=TCLink)
    net.staticArp()
    net.start()

    print("\n" + "=" * 60)
    print("Topologia VLAN activa (2 switches).  En otra terminal:")
    print("  simple_switch_CLI --thrift-port 9090 < s1-commands.txt")
    print("  simple_switch_CLI --thrift-port 9091 < s2-commands.txt")
    print("")
    print("Verificar misma VLAN:  h1 ping h3  /  h2 ping h4")
    print("Verificar cross-VLAN (debe fallar):  h1 ping h4")
    print("=" * 60 + "\n")

    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel('info')
    main()
