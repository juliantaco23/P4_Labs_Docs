#!/usr/bin/env python3
"""
ECN — Explicit Congestion Notification (2 switches, adaptado de p4lang/tutorials)

Topología:
    h1  (10.0.1.1)  ─┐                 ┌─  h2  (10.0.2.2)
                       s1 ════════════ s2
    h11 (10.0.1.11) ─┘   0.5 Mbps      └─  h22 (10.0.2.22)
                          (bottleneck)

  s1: port1=h1, port2=h11, port3=s2
  s2: port1=h2, port2=h22, port3=s1

Uso:
  1. Compilar P4:
       mkdir -p p4src/build
       p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/ecn.p4

  2. Ejecutar topología (desde la carpeta del ejercicio):
       sudo python3 mininet/topo.py

  3. En otra terminal, instalar reglas en ambos switches:
       simple_switch_CLI --thrift-port 9090 < s1-commands.txt
       simple_switch_CLI --thrift-port 9091 < s2-commands.txt

  4. Prueba de ECN:
       - En h2:   ./receive.py
       - En h22:  iperf -s -u
       - En h1:   ./send.py 10.0.2.2 "P4 is cool" 30
       - En h11:  iperf -c 10.0.2.22 -t 15 -u
       - Observar que tos cambia de 0x1 a 0x3 en h2 cuando la cola
         en s1 (egreso hacia s2) supera ECN_THRESHOLD.
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


class ECNTopo(Topo):
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

        # Hosts en s1 (subred 10.0.1.0/24)
        h1 = self.addHost('h1', cls=P4Host,
                          ip='10.0.1.1/24',
                          mac='08:00:00:00:01:01')
        h11 = self.addHost('h11', cls=P4Host,
                           ip='10.0.1.11/24',
                           mac='08:00:00:00:01:11')

        # Hosts en s2 (subred 10.0.2.0/24)
        h2 = self.addHost('h2', cls=P4Host,
                          ip='10.0.2.2/24',
                          mac='08:00:00:00:02:02')
        h22 = self.addHost('h22', cls=P4Host,
                           ip='10.0.2.22/24',
                           mac='08:00:00:00:02:22')

        # Links a hosts (sin restriccion de ancho de banda)
        self.addLink(s1, h1)                                 # s1:port1
        self.addLink(s1, h11)                                # s1:port2
        self.addLink(s2, h2)                                 # s2:port1
        self.addLink(s2, h22)                                # s2:port2

        # Enlace bottleneck s1-s2: 512 kbps
        self.addLink(s1, s2, bw=0.5, use_htb=True)          # s1:port3, s2:port3


def configure_hosts(net):
    """Configurar rutas y ARP estáticos para enrutamiento L3 entre subredes."""

    # Gateway virtual en s1: 10.0.1.254 -> MAC 08:00:00:00:01:00
    for hname in ('h1', 'h11'):
        h = net.get(hname)
        h.cmd('route add default gw 10.0.1.254 dev eth0')
        h.cmd('arp -i eth0 -s 10.0.1.254 08:00:00:00:01:00')

    # Gateway virtual en s2: 10.0.2.254 -> MAC 08:00:00:00:02:00
    for hname in ('h2', 'h22'):
        h = net.get(hname)
        h.cmd('route add default gw 10.0.2.254 dev eth0')
        h.cmd('arp -i eth0 -s 10.0.2.254 08:00:00:00:02:00')


def main():
    if not os.path.isfile(JSON_PATH):
        print("ERROR: No se encontro %s" % JSON_PATH)
        print("Compilar primero:")
        print("  mkdir -p p4src/build")
        print("  p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/ecn.p4")
        sys.exit(1)

    net = Mininet(topo=ECNTopo(), controller=None, link=TCLink)
    net.start()
    configure_hosts(net)

    print("\n" + "=" * 60)
    print("Topologia ECN activa (2 switches).  En otra terminal:")
    print("  simple_switch_CLI --thrift-port 9090 < s1-commands.txt")
    print("  simple_switch_CLI --thrift-port 9091 < s2-commands.txt")
    print("")
    print("Prueba ECN:")
    print("  h2:  ./receive.py")
    print("  h22: iperf -s -u")
    print("  h1:  ./send.py 10.0.2.2 \"P4 is cool\" 30")
    print("  h11: iperf -c 10.0.2.22 -t 15 -u")
    print("  -> Observar tos 0x1 -> 0x3 en h2 durante congestion")
    print("=" * 60 + "\n")

    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel('info')
    main()
