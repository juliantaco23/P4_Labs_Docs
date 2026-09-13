from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel
from mininet.node import OVSBridge

class CustomTopo(Topo):
    def __init__ (self, n=5, **opts):
        Topo.__init__ (self, **opts)
        # Crear hosts
        hosts = []
        for i in range(1, n+1):
            hosts.append(self.addHost('h%d' % i))
        
        # Crear switches
        switches = []
        for i in range(1, n+1):
            switches.append(self.addSwitch('s%d' % i, cls=OVSBridge, stp=True))

        # Conectar host a switch
        for i in range(n):
            self.addLink(hosts[i], switches[i])
            # Conectar switches en malla
            for i in range(n):
                for j in range(i+1, n):
                    self.addLink(switches[i], switches[j])

def runNet():
    topo = CustomTopo(5)
    net = Mininet(topo)
    net.start()
    net.pingAll()
    net.stop()

if __name__ == '__main__':
  setLogLevel('info')
  runNet()
