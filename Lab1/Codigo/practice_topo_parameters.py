from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import dumpNodeConnections

class CustomTopo(Topo):
    def __init__(self, **opts):
        Topo.__init__(self, **opts)
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        h4 = self.addHost('h4')
        s1 = self.addSwitch('s1')
        self.addLink(h1, s1, bw=10, delay='1ms', loss=0.1,
        max_queue_size=1000, use_htb=True)
        self.addLink(h2, s1, bw=50, delay='3ms', loss=0.1,
        max_queue_size=1000, use_htb=True)
        self.addLink(h3, s1, bw=100, delay='10ms', loss=0.1,
        max_queue_size=1000, use_htb=True)
        self.addLink(h4, s1, bw=80, delay='50ms', loss=0.1,
        max_queue_size=1000, use_htb=True)
        
def runNet():
  topo = CustomTopo()
  net = Mininet(topo, host=CPULimitedHost, link=TCLink)
  net.start()
  dumpNodeConnections(net.hosts)
  net.pingAll()
  h1, h4 = net.get('h1', 'h4')
  net.iperf((h1, h4))
  net.stop()
if __name__ == '__main__':
  setLogLevel('info')
  runNet()
