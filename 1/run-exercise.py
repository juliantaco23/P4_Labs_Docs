#!/usr/bin/env python3
import os, sys
from p4_mininet import P4Switch, P4Host
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.link import TCLink

JSON_PATH = os.path.join(os.path.dirname(__file__), 'p4src', 'build', 'bmv2.json')


class Exercise1Topo(Topo):
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
        sys.exit(1)

    net = Mininet(topo=Exercise1Topo(), controller=None, link=TCLink)
    net.staticArp()
    net.start()

    print("\n" + "=" * 60)
    print("Topología activa.  En otra terminal ejecutar:")
    print("  simple_switch_CLI --thrift-port 9090 < s1-commands.txt")
    print("Luego aquí:  pingall")
    print("=" * 60 + "\n")

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    main()
