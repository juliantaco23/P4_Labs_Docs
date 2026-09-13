from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.revent import *
from pox.lib.util import dpidToStr
from pox.lib.addresses import EthAddr
import csv
import os

log = core.getLogger()
policyFile = "%s/pox/pox/misc/firewall-policies.csv" % os.environ['HOME']

class Firewall(EventMixin):
    def __init__(self):
        self.listenTo(core.openflow)
        log.info("Firewall module enabled")
    
    def _handle_ConnectionUp(self, event):
        """Se ejecuta cuando un switch se conecta al controlador"""
        log.info("Switch connected: %s" % dpidToStr(event.dpid))
        log.info("Installing firewall rules on %s" % dpidToStr(event.dpid))
        
        rule_count = 0
        try:
            with open(policyFile, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    mac_0 = EthAddr(row['mac_0'])
                    mac_1 = EthAddr(row['mac_1'])
                    
                    # Bloquear trafico de mac_0 a mac_1
                    msg1 = of.ofp_flow_mod()
                    msg1.priority = 100
                    msg1.match.dl_src = mac_0
                    msg1.match.dl_dst = mac_1
                    # actions vacio = DROP
                    event.connection.send(msg1)
                    
                    # Bloquear trafico de mac_1 a mac_0
                    msg2 = of.ofp_flow_mod()
                    msg2.priority = 100
                    msg2.match.dl_src = mac_1
                    msg2.match.dl_dst = mac_0
                    # actions vacio = DROP
                    event.connection.send(msg2)
                    
                    log.info("Blocking %s <-> %s" % (mac_0, mac_1))
                    rule_count += 2
                    
            log.info("Installed %d firewall rules on %s" % (rule_count, dpidToStr(event.dpid)))
        except Exception as e:
            log.error("Error reading policy file %s: %s" % (policyFile, e))
            import traceback
            traceback.print_exc()

def launch():
    core.registerNew(Firewall)