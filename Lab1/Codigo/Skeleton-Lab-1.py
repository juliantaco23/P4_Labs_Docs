from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.util import irange,dumpNodeConnections
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import OVSSwitch, OVSBridge 
from mininet.nodelib import LinuxBridge

class CustomTopo(Topo):
	def __init__(self,**opts):
		Topo.__init__(self, **opts)
		try:
            #Please insert your code here
            #We recommend to use the method self.addSwitch('s%s'%i, cls=OVSBridge, stp=True)
            #cls and stp parameters allows Mininet to use switchs that build a Spanning Tree

			


		except Exception as e:
			return e

def runNet():
	topo=CustomTopo()
	return topo

if __name__ == '__main__':
	setLogLevel('info')
	runNet()
