#!/usr/bin/env python3
"""
Exercise-2.2 — Filtrado de Sesiones TCP

El switch filtra paquetes TCP que no pertenecen a una sesión registrada
y genera un RST para conexiones no autorizadas.

Topología:  h1 ── s1 ── h2

Uso:
  1. Compilar P4:
       mkdir -p p4src/build
       p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json \
           --p4runtime-files p4src/build/p4info.txt p4src/sw_gita.p4

  2. Ejecutar topología (desde la carpeta del ejercicio):
       sudo python3 mininet/topo.py

  3. En otra terminal, instalar reglas base:
       simple_switch_CLI --thrift-port 9090 < s1-commands.txt

  4. Para probar filtrado TCP:
       - Registrar sesion SSH (ver add_tcp_session.sh)
       - mininet> h2 /usr/sbin/sshd &
       - mininet> h1 ssh 10.0.0.2
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


class Exercise22Topo(Topo):
    def build(self):
        # Switch
        s1 = self.addSwitch('s1',
                            cls=P4Switch,
                            json_path=JSON_PATH,
                            thrift_port=9090)

        # Hosts
        h1 = self.addHost('h1', cls=P4Host,
                          ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', cls=P4Host,
                          ip='10.0.0.2/24', mac='00:00:00:00:00:02')

        # Links
        self.addLink(h1, s1, bw=5, delay='5ms', loss=1, use_htb=True)
        self.addLink(h2, s1, bw=5, delay='5ms', loss=1, use_htb=True)


def main():
    if not os.path.isfile(JSON_PATH):
        print("ERROR: No se encontro %s" % JSON_PATH)
        print("Compilar primero:")
        print("  mkdir -p p4src/build")
        print("  p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json \\")
        print("      --p4runtime-files p4src/build/p4info.txt p4src/sw_gita.p4")
        sys.exit(1)

    # No staticArp() — ARP se resuelve en el data plane
    net = Mininet(topo=Exercise22Topo(), controller=None, link=TCLink)
    net.start()

    # Deshabilitar IPv6 para evitar trafico innecesario (debe ir post-start)
    for h in net.hosts:
        h.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        h.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        h.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")

    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel('info')
    main()
