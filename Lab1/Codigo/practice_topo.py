from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel
class CustomTopo(Topo):
    def __init__(self, **opts):
        Topo.__init__(self, **opts)
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        h4 = self.addHost('h4')
        s1 = self.addSwitch('s1')
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)
        self.addLink(h4, s1)
        
def runNet():
  topo = CustomTopo()
  net = Mininet(topo)
  net.start()
  net.pingAll()
  net.stop()
if __name__ == '__main__':
  setLogLevel('info')
  runNet()
