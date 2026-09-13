#!/usr/bin/env python3
"""
Script de topologia para probar el firewall de POX
Crea diferentes topologias con hosts que coinciden con las reglas del firewall-policies.csv

Reglas del firewall:
1. 00:00:00:00:00:01 <-> 00:00:00:00:00:04
2. 00:00:00:00:00:02 <-> 00:00:00:00:00:03
3. 00:00:00:00:00:03 <-> 00:00:00:00:00:07
4. 00:00:00:00:00:06 <-> 00:00:00:00:00:05

Uso:
    sudo python3 test_firewall_topo.py single
    sudo python3 test_firewall_topo.py linear
    sudo python3 test_firewall_topo.py tree
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import sys


class FirewallTestTopoSingle(Topo):
    """
    Topologia Single: Un switch con 7 hosts
    Hosts bloqueados segun firewall-policies.csv:
    - h1 (00:00:00:00:00:01) <-> h4 (00:00:00:00:00:04)
    - h2 (00:00:00:00:00:02) <-> h3 (00:00:00:00:00:03)
    - h3 (00:00:00:00:00:03) <-> h7 (00:00:00:00:00:07)
    - h5 (00:00:00:00:00:05) <-> h6 (00:00:00:00:00:06)
    """
    def build(self):
        # Crear switch
        s1 = self.addSwitch('s1')
        
        # Crear 7 hosts y conectarlos al switch
        for i in range(1, 8):
            host = self.addHost('h%d' % i, 
                              mac='00:00:00:00:00:%02d' % i,
                              ip='10.0.0.%d/24' % i)
            self.addLink(host, s1)


class FirewallTestTopoLinear(Topo):
    """
    Topologia Linear: 3 switches en linea con hosts distribuidos
    s1 -- s2 -- s3
    |     |     |
    h1-h3 h4-h5 h6-h7
    
    Hosts bloqueados:
    - h1 <-> h4 (atraviesan switches)
    - h2 <-> h3 (mismo switch)
    - h3 <-> h7 (atraviesan todos los switches)
    - h5 <-> h6 (switches adyacentes)
    """
    def build(self):
        # Crear switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        
        # Conectar switches en linea
        self.addLink(s1, s2)
        self.addLink(s2, s3)
        
        # Hosts en s1: h1, h2, h3
        for i in range(1, 4):
            host = self.addHost('h%d' % i,
                              mac='00:00:00:00:00:%02d' % i,
                              ip='10.0.0.%d/24' % i)
            self.addLink(host, s1)
        
        # Hosts en s2: h4, h5
        for i in range(4, 6):
            host = self.addHost('h%d' % i,
                              mac='00:00:00:00:00:%02d' % i,
                              ip='10.0.0.%d/24' % i)
            self.addLink(host, s2)
        
        # Hosts en s3: h6, h7
        for i in range(6, 8):
            host = self.addHost('h%d' % i,
                              mac='00:00:00:00:00:%02d' % i,
                              ip='10.0.0.%d/24' % i)
            self.addLink(host, s3)


class FirewallTestTopoTree(Topo):
    """
    Topologia Tree (arbol): Estructura jerarquica
           s1 (root)
          /  \
        s2    s3
       / \    / \
      h1 h2  h3 h4
      
    Adicionalmente: h5, h6, h7 en s1
    
    Hosts bloqueados:
    - h1 <-> h4 (diferentes ramas)
    - h2 <-> h3 (diferentes ramas)
    - h3 <-> h7 (rama vs raiz)
    - h5 <-> h6 (misma rama raiz)
    """
    def build(self):
        # Switch raiz
        s1 = self.addSwitch('s1')
        
        # Switches de segundo nivel
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        
        # Conectar switches
        self.addLink(s1, s2)
        self.addLink(s1, s3)
        
        # Hosts en s2: h1, h2
        h1 = self.addHost('h1', mac='00:00:00:00:00:01', ip='10.0.0.1/24')
        h2 = self.addHost('h2', mac='00:00:00:00:00:02', ip='10.0.0.2/24')
        self.addLink(h1, s2)
        self.addLink(h2, s2)
        
        # Hosts en s3: h3, h4
        h3 = self.addHost('h3', mac='00:00:00:00:00:03', ip='10.0.0.3/24')
        h4 = self.addHost('h4', mac='00:00:00:00:00:04', ip='10.0.0.4/24')
        self.addLink(h3, s3)
        self.addLink(h4, s3)
        
        # Hosts adicionales en s1: h5, h6, h7
        for i in range(5, 8):
            host = self.addHost('h%d' % i,
                              mac='00:00:00:00:00:%02d' % i,
                              ip='10.0.0.%d/24' % i)
            self.addLink(host, s1)


def run_topology(topo_type):
    """Ejecuta la topologia especificada con controlador remoto POX"""
    
    # Seleccionar topologia
    topos = {
        'single': FirewallTestTopoSingle,
        'linear': FirewallTestTopoLinear,
        'tree': FirewallTestTopoTree
    }
    
    if topo_type not in topos:
        print("Error: Topologia no valida. Opciones: single, linear, tree")
        sys.exit(1)
    
    info('*** Creando topologia: %s\n' % topo_type)
    topo = topos[topo_type]()
    
    info('*** Creando red con controlador remoto POX\n')
    net = Mininet(
        topo=topo,
        switch=OVSKernelSwitch,
        controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6633),
        autoSetMacs=False,  # Usamos MACs personalizadas
        autoStaticArp=True   # Pre-configura ARP para evitar broadcasts innecesarios
    )
    
    info('*** Iniciando red\n')
    net.start()
    
    info('*** Configuracion de red:\n')
    for host in net.hosts:
        info('%s: IP=%s MAC=%s\n' % (host.name, host.IP(), host.MAC()))
    
    info('\n*** Reglas del firewall (bloqueadas):\n')
    info('  h1 (00:00:00:00:00:01) <-> h4 (00:00:00:00:00:04)\n')
    info('  h2 (00:00:00:00:00:02) <-> h3 (00:00:00:00:00:03)\n')
    info('  h3 (00:00:00:00:00:03) <-> h7 (00:00:00:00:00:07)\n')
    info('  h5 (00:00:00:00:00:05) <-> h6 (00:00:00:00:00:06)\n')
    
    info('\n*** Comandos sugeridos:\n')
    info('  pingall          - Prueba conectividad completa\n')
    info('  h1 ping h4       - Debe fallar (bloqueado)\n')
    info('  h2 ping h3       - Debe fallar (bloqueado)\n')
    info('  h1 ping h2       - Debe funcionar (permitido)\n')
    info('  dpctl dump-flows - Muestra reglas instaladas\n')
    info('  exit             - Salir\n\n')
    
    CLI(net)
    
    info('*** Deteniendo red\n')
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    
    run_topology(sys.argv[1])
