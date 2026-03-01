#!/usr/bin/python

import argparse
import sys

from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import Host
from mininet.topo import Topo
from mininet.link import TCLink

sys.path.insert(0, '/mininet')
from stratum2 import StratumBmv2Switch

CPU_PORT = 255


class TutorialTopo(Topo):
    def __init__(self, *args, **kwargs):
        Topo.__init__(self, *args, **kwargs)

        # Switch
        s1 = self.addSwitch('s1',
                            cls=StratumBmv2Switch,
                            cpuport=CPU_PORT,
                            onosdevid="device:s1",
                            json="/workdir/p4src/build/bmv2.json")

        # Hosts
        h1 = self.addHost('h1',
                          mac='00:00:00:00:00:01',
                          ip='10.0.0.1/24')
        h2 = self.addHost('h2',
                          mac='00:00:00:00:00:02',
                          ip='10.0.0.2/24')

        # Links
        self.addLink(h1, s1,
                     bw=2,
                     delay='10000us',
                     loss=5,
                     use_htb=True)
        self.addLink(h2, s1,
                     bw=5,
                     delay='1ms',
                     loss=2,
                     use_htb=True)


def main():
    net = Mininet(topo=TutorialTopo(), controller=None, link=TCLink)
    net.staticArp()
    net.start()
    CLI(net)
    net.stop()
    print('#' * 80)
    print('ATTENTION: Mininet was stopped! Perhaps accidentally?')
    print('No worries, it will restart automatically in a few seconds...')
    print('To access again the Mininet CLI, use `make mn-cli`')
    print('To detach from the CLI (without stopping), press Ctrl-D')
    print('To permanently quit Mininet, use `make stop`')
    print('#' * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Mininet topology script for Exercise 1')
    args = parser.parse_args()
    setLogLevel('info')
    main()
