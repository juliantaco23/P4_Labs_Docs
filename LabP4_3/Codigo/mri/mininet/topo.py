#!/usr/bin/env python3
"""
MRI — Multi-Hop Route Inspection (3 switches, adaptado de p4lang/tutorials)

Topología:
    h1  (10.0.1.1)  ─┐                  ┌─  h2  (10.0.2.2)
                       s1 ═══(0.5M)═══ s2
    h11 (10.0.1.11) ─┘  \            /  └─  h22 (10.0.2.22)
                          s3 ── h3
                        (10.0.3.3)

  s1: port1=h1, port2=h11, port3=s2(bottleneck), port4=s3
  s2: port1=h22, port2=h2, port3=s1(bottleneck), port4=s3
  s3: port1=h3, port2=s1, port3=s2

Uso:
  1. Compilar P4:
       mkdir -p p4src/build
       p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/mri.p4

  2. Ejecutar topología (desde la carpeta del ejercicio):
       sudo python3 mininet/topo.py

  3. En otra terminal, instalar reglas en los tres switches:
       simple_switch_CLI --thrift-port 9090 < s1-commands.txt
       simple_switch_CLI --thrift-port 9091 < s2-commands.txt
       simple_switch_CLI --thrift-port 9092 < s3-commands.txt

  4. Prueba de MRI:
       - En h2:   ./receive.py
       - En h22:  iperf -s -u
       - En h1:   ./send.py 10.0.2.2 "P4 is cool" 30
       - En h11:  iperf -c 10.0.2.22 -t 15 -u
       - Observar en h2: count=2 (swid=1, swid=2) con qdepth
         creciendo en s1 durante la congestión.
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


class MRITopo(Topo):
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
        s3 = self.addSwitch('s3',
                            cls=P4Switch,
                            json_path=JSON_PATH,
                            thrift_port=9092)

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

        # Host en s3 (subred 10.0.3.0/24)
        h3 = self.addHost('h3', cls=P4Host,
                          ip='10.0.3.3/24',
                          mac='08:00:00:00:03:03')

        # Links — el orden determina el número de puerto en cada switch
        # s1: port1=h1, port2=h11
        self.addLink(s1, h1)                                  # s1:port1
        self.addLink(s1, h11)                                 # s1:port2
        # s2: port1=h2, port2=h22
        self.addLink(s2, h2)                                  # s2:port1
        self.addLink(s2, h22)                                 # s2:port2
        # s3: port1=h3
        self.addLink(s3, h3)                                  # s3:port1
        # Inter-switch links
        self.addLink(s1, s2, bw=0.5, use_htb=True)           # s1:port3, s2:port3 (bottleneck)
        self.addLink(s1, s3)                                  # s1:port4, s3:port2
        self.addLink(s3, s2)                                  # s3:port3, s2:port4


def configure_hosts(net):
    """Configurar rutas y ARP estáticos para enrutamiento L3 entre subredes."""

    # Hosts en s1: gateway virtual 10.0.1.254 → MAC 08:00:00:00:01:00
    for hname in ('h1', 'h11'):
        h = net.get(hname)
        h.cmd('route add default gw 10.0.1.254 dev eth0')
        h.cmd('arp -i eth0 -s 10.0.1.254 08:00:00:00:01:00')

    # Hosts en s2: gateway virtual 10.0.2.254 → MAC 08:00:00:00:02:00
    for hname in ('h2', 'h22'):
        h = net.get(hname)
        h.cmd('route add default gw 10.0.2.254 dev eth0')
        h.cmd('arp -i eth0 -s 10.0.2.254 08:00:00:00:02:00')

    # Host en s3: gateway virtual 10.0.3.254 → MAC 08:00:00:00:03:00
    h3 = net.get('h3')
    h3.cmd('route add default gw 10.0.3.254 dev eth0')
    h3.cmd('arp -i eth0 -s 10.0.3.254 08:00:00:00:03:00')


def main():
    if not os.path.isfile(JSON_PATH):
        print("ERROR: No se encontro %s" % JSON_PATH)
        print("Compilar primero:")
        print("  mkdir -p p4src/build")
        print("  p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/mri.p4")
        sys.exit(1)

    net = Mininet(topo=MRITopo(), controller=None, link=TCLink)
    net.start()
    configure_hosts(net)

    print("\n" + "=" * 60)
    print("Topologia MRI activa (3 switches).  En otra terminal:")
    print("  simple_switch_CLI --thrift-port 9090 < s1-commands.txt")
    print("  simple_switch_CLI --thrift-port 9091 < s2-commands.txt")
    print("  simple_switch_CLI --thrift-port 9092 < s3-commands.txt")
    print("")
    print("Prueba MRI:")
    print("  h2:  ./receive.py")
    print("  h22: iperf -s -u")
    print("  h1:  ./send.py 10.0.2.2 \"P4 is cool\" 30")
    print("  h11: iperf -c 10.0.2.22 -t 15 -u")
    print("  -> Observar swid y qdepth en h2")
    print("=" * 60 + "\n")

    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel('info')
    main()
