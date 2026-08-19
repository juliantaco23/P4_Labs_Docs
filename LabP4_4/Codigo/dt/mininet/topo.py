#!/usr/bin/env python3
"""
DT (Decision Tree in P4) — Topología: 1 switch, 4 hosts

Topología:
    h1 (10.0.1.1/26) ──port1──┐
    h2 (10.0.1.2/26) ──port2──┤ s1
    h3 (10.0.1.3/26) ──port3──┤ (thrift 9090)
    h4 (10.0.1.4/26) ──port4──┘

Todos los hosts están en la misma subred 10.0.1.0/26.
El switch P4 clasifica el tráfico TCP usando un árbol de decisión
codificado en sus match/action tables (feature1_exact, feature2_exact,
feature3_exact) y luego decide el puerto de salida en ipv4_exact.

Uso:
  1. Compilar P4:
       mkdir -p p4src/build
       p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/dt_switch.p4

  2. Ejecutar topología (desde la carpeta del ejercicio):
       sudo python3 mininet/topo.py

  3. En otra terminal, instalar reglas:
       simple_switch_CLI --thrift-port 9090 < s1-commands.txt

  4. Prueba:
       mininet> h1 python3 send_packets.py
       mininet> xterm h2 h3 h4
       # En h2/h3/h4: tcpdump -i eth0 -n
"""

import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p4_mininet import P4Switch, P4Host

from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.topo import Topo

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH  = os.path.join(SCRIPT_DIR, '..', 'p4src', 'build', 'bmv2.json')


class DTTopo(Topo):
    def build(self):
        # Switch
        s1 = self.addSwitch('s1',
                             cls=P4Switch,
                             json_path=JSON_PATH,
                             thrift_port=9090)

        # Hosts — todos en 10.0.1.0/26
        h1 = self.addHost('h1', cls=P4Host,
                           ip='10.0.1.1/26',
                           mac='08:00:00:00:01:01')
        h2 = self.addHost('h2', cls=P4Host,
                           ip='10.0.1.2/26',
                           mac='08:00:00:00:01:02')
        h3 = self.addHost('h3', cls=P4Host,
                           ip='10.0.1.3/26',
                           mac='08:00:00:00:01:03')
        h4 = self.addHost('h4', cls=P4Host,
                           ip='10.0.1.4/26',
                           mac='08:00:00:00:01:04')

        # Links — el orden define el número de puerto en s1
        self.addLink(s1, h1)   # s1:port1
        self.addLink(s1, h2)   # s1:port2
        self.addLink(s1, h3)   # s1:port3
        self.addLink(s1, h4)   # s1:port4


def main():
    setLogLevel('info')
    topo = DTTopo()
    net  = Mininet(topo=topo, controller=None)
    net.start()

    # Desactivar offloads en interfaces del switch
    for sw in net.switches:
        for intf in sw.intfList():
            if intf.name != 'lo':
                sw.cmd('ethtool --offload %s rx off tx off sg off' % intf.name)

    print("\n=== Topología DT lista ===")
    print("Instala las reglas en otra terminal:")
    print("  simple_switch_CLI --thrift-port 9090 < s1-commands.txt\n")

    CLI(net)
    net.stop()


if __name__ == '__main__':
    main()
