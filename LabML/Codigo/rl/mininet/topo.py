#!/usr/bin/env python3
"""
RL SYN Flood — Topology: 2 switches, 3 hosts

Topology:
    h1 (10.0.1.1/26)   ──port1──┐               ┌──port1── h3 (10.0.6.1/24)
    h2 (10.0.1.82/26)  ──port2──┤ s1 ──port3→port2── s2
                                 (thrift 9090)  (thrift 9091)

Subnet diagram:
  - h1: 10.0.1.1  → subnet 10.0.1.0/26   (legitimate client)
  - h2: 10.0.1.82 → subnet 10.0.1.64/26  (SYN Flood attacker)
  - h3: 10.0.6.1  → subnet 10.0.6.0/24   (HTTP server)

The RL agent (controller.py) runs on the host where Mininet is located and communicates
with s1 via simple_switch_CLI (Thrift port 9090).

Agent actions:
  - Action 0: Block 10.0.1.0/26  → blocks h1 AND h2 (INCORRECT → negative reward)
  - Action 1: Block 10.0.1.64/26 → blocks only h2  (CORRECT  → positive reward)
  - Action 2: Do nothing (initial state / unblock)

Usage:
  1. Compile P4:
       mkdir -p p4src/build
       p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/syn_flood_rl.p4

  2. Run the topology:
       sudo python3 mininet/topo.py

  3. Install forwarding rules (in another terminal):
       simple_switch_CLI --thrift-port 9090 < s1-commands.txt
       simple_switch_CLI --thrift-port 9091 < s2-commands.txt

  4. Launch the attack (from h2 in Mininet):
       mininet> h2 python3 send_attack.py &

  5. Launch the RL agent (in another terminal on the host):
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

        # Links s1 — port assigned in addLink order (1-indexed)
        self.addLink(s1, h1)   # s1:port1
        self.addLink(s1, h2)   # s1:port2
        self.addLink(s1, s2)   # s1:port4 <-> s2:port1  (inter-switch)
        # Links s2
        self.addLink(s2, h3)   # s2:port2  (server host)


def configure_hosts(net):
    """Configure static routes and ARP entries on the hosts."""
    # h1 and h2 use s1 as gateway to 10.0.6.0/24
    # The 'onlink' flag is required because 10.0.1.254 is outside h1/h2's /26 subnet;
    # without it, the kernel silently rejects the route on modern kernels.
    for hname in ('h1', 'h2'):
        h = net.get(hname)
        h.cmd('ip route add 10.0.6.0/24 via 10.0.1.254 dev eth0 onlink 2>/dev/null || true')
        h.cmd('arp -i eth0 -s 10.0.1.254 08:00:00:00:01:00')

    # h3 (server) uses s2 as gateway toward 10.0.1.0/25
    # 10.0.6.254 is within h3's /24 subnet, onlink is not strictly required.
    h3 = net.get('h3')
    h3.cmd('ip route add 10.0.1.0/25 via 10.0.6.254 dev eth0 onlink 2>/dev/null || true')
    h3.cmd('arp -i eth0 -s 10.0.6.254 08:00:00:00:06:00')


def main():
    setLogLevel('info')
    topo = SynFloodTopo()
    net  = Mininet(topo=topo, controller=None)
    net.start()

    configure_hosts(net)

    print("\n=== RL SYN Flood topology ready ===")
    print("Install forwarding rules in other terminals:")
    print("  simple_switch_CLI --thrift-port 9090 < s1-commands.txt")
    print("  simple_switch_CLI --thrift-port 9091 < s2-commands.txt\n")
    print("Then launch the attack from h2 and the RL agent from the host.\n")

    CLI(net)
    net.stop()


if __name__ == '__main__':
    main()
