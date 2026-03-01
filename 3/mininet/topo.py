#!/usr/bin/python

import argparse

from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import Host
from mininet.topo import Topo

from mininet.node import RemoteController
from mininet.link import TCLink
from mininet.node import CPULimitedHost

import sys

sys.path.insert(0, '/mininet')
from stratum2 import StratumBmv2Switch

CPU_PORT = 255


class TutorialTopo(Topo):

    def __init__(self, *args, **kwargs):
        Topo.__init__(self, *args, **kwargs)
        
        #Switches
        s1 = self.addSwitch('s1', cls=StratumBmv2Switch, cpuport=CPU_PORT)
        s2 = self.addSwitch('s2', cls=StratumBmv2Switch, cpuport=CPU_PORT)
        
        #Hosts
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')

        #Links: h1-s1 (s1:port1), s1-s2 (s1:port2, s2:port1), s2-h2 (s2:port2)
        self.addLink('h1', 's1', bw=5, delay='5ms', loss=1, use_htb=True)
        self.addLink('s1', 's2', bw=5, delay='5ms', loss=1, use_htb=True)
        self.addLink('s2', 'h2', bw=5, delay='5ms', loss=1, use_htb=True)






def main():
	net = Mininet(topo=TutorialTopo(), controller=None, link=TCLink)
	net.staticArp() #Avoiding ARP process
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
        description='Mininet topology script for 2x2 fabric with stratum_bmv2 and IPv4 hosts')
    args = parser.parse_args()
    setLogLevel('info')

    main()
