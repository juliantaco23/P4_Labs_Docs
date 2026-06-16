#!/usr/bin/env python3
"""
RL SYN Flood — Topología: 2 switches, 3 hosts

Topología:
    h1 (10.0.1.1/26)   ──port1──┐               ┌──port1── h3 (10.0.6.1/24)
    h2 (10.0.1.82/26)  ──port2──┤ s1 ──port3→2── s2
                                 │ (thrift 9090)  (thrift 9091)
                                 └──port4── h4 (10.0.4.1/24)  [monitoring]

Esquema de subredes:
  - h1: 10.0.1.1  → subred 10.0.1.0/26   (cliente legítimo)
  - h2: 10.0.1.82 → subred 10.0.1.64/26  (atacante SYN Flood)
  - h3: 10.0.6.1  → subred 10.0.6.0/24   (servidor HTTP)
  - h4: 10.0.4.1  → subred 10.0.4.0/24   (host de monitoreo del agente RL)

El agente RL (controller.py) corre en el host donde está Mininet y se comunica
con s1 vía simple_switch_CLI (puerto thrift 9090).

Acciones del agente:
  - Acción 0: Bloquear 10.0.1.0/26  → bloquea h1 Y h2 (INCORRECTO → reward negativo)
  - Acción 1: Bloquear 10.0.1.64/26 → bloquea solo h2  (CORRECTO  → reward positivo)
  - Acción 2: No hacer nada (estado inicial / desbloquear)

Uso:
  1. Compilar P4:
       mkdir -p p4src/build
       p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/syn_flood_rl.p4

  2. Ejecutar topología:
       sudo python3 mininet/topo.py

  3. Instalar reglas de forwarding (en otra terminal):
       simple_switch_CLI --thrift-port 9090 < s1-commands.txt
       simple_switch_CLI --thrift-port 9091 < s2-commands.txt

  4. Lanzar el ataque (desde h2 en Mininet):
       mininet> h2 python3 send_attack.py &

  5. Lanzar el agente RL (en otra terminal del host):
       python3 controller.py
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
JSON_PATH  = os.path.join(SCRIPT_DIR, '..', 'p4src', 'build', 'bmv2.json')


class SynFloodTopo(Topo):
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
        # h1: cliente legítimo — en subred 10.0.1.0/26 (host bits 0-63)
        h1 = self.addHost('h1', cls=P4Host,
                           ip='10.0.1.1/26',
                           mac='08:00:00:00:01:01')
        # h2: atacante — en subred 10.0.1.64/26 (host bits 64-127)
        h2 = self.addHost('h2', cls=P4Host,
                           ip='10.0.1.82/26',
                           mac='08:00:00:00:01:52')   # 0x52 = 82
        # h3: servidor HTTP
        h3 = self.addHost('h3', cls=P4Host,
                           ip='10.0.6.1/24',
                           mac='08:00:00:00:06:01')
        # h4: host de monitoreo (accede a contadores del switch)
        h4 = self.addHost('h4', cls=P4Host,
                           ip='10.0.4.1/24',
                           mac='08:00:00:00:04:01')

        # Links s1
        self.addLink(s1, h1)             # s1:port1
        self.addLink(s1, h2)             # s1:port2
        self.addLink(s1, h4)             # s1:port4 (monitoreo)
        # Link inter-switch
        self.addLink(s1, s2)             # s1:port3 ↔ s2:port2
        # Links s2
        self.addLink(s2, h3)             # s2:port1


def configure_hosts(net):
    """Configurar rutas estáticas en los hosts."""
    # h1 y h2 usan s1 como gateway para 10.0.6.0/24
    for hname in ('h1', 'h2'):
        h = net.get(hname)
        h.cmd('ip route add 10.0.6.0/24 via 10.0.1.254 dev eth0 2>/dev/null || true')
        h.cmd('arp -i eth0 -s 10.0.1.254 08:00:00:00:01:00')

    # h3 (servidor) usa s2 como gateway hacia 10.0.1.0/25
    h3 = net.get('h3')
    h3.cmd('ip route add 10.0.1.0/25 via 10.0.6.254 dev eth0 2>/dev/null || true')
    h3.cmd('arp -i eth0 -s 10.0.6.254 08:00:00:00:06:00')


def main():
    setLogLevel('info')
    topo = SynFloodTopo()
    net  = Mininet(topo=topo, controller=None)
    net.start()

    configure_hosts(net)

    print("\n=== Topología RL SYN Flood lista ===")
    print("Instala las reglas en otras terminales:")
    print("  simple_switch_CLI --thrift-port 9090 < s1-commands.txt")
    print("  simple_switch_CLI --thrift-port 9091 < s2-commands.txt\n")
    print("Luego lanza el ataque desde h2 y el agente RL desde el host.\n")

    CLI(net)
    net.stop()


if __name__ == '__main__':
    main()
