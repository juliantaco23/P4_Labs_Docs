from pox.core import core
from collections import defaultdict

import pox.openflow.libopenflow_01 as of
import pox.openflow.discovery
import pox.openflow.spanning_tree

from pox.lib.revent import *
from pox.lib.util import dpid_to_str
from pox.lib.util import dpidToStr
from pox.lib.addresses import IPAddr, EthAddr
from collections import namedtuple
import os

log = core.getLogger()


class TopologySlice (EventMixin):

    def __init__(self):
        self.listenTo(core.openflow)
        log.debug("Enabling Slicing Module")
        
        
    def _handle_ConnectionUp(self, event):
        
        dpid = dpidToStr(event.dpid)
        log.debug("Switch %s has come up.", dpid)
        
        if dpid == "00-00-00-00-00-01":
            msg = of.ofp_flow_mod()
            msg.match.in_port = 3
            msg.actions.append(of.ofp_action_output(port=1))
            event.connection.send(msg)
            
            msg = of.ofp_flow_mod()
            msg.match.in_port = 1
            msg.actions.append(of.ofp_action_output(port=3))
            event.connection.send(msg)
            
            msg = of.ofp_flow_mod()
            msg.match.in_port = 4
            msg.actions.append(of.ofp_action_output(port=2))
            event.connection.send(msg)
            
            msg = of.ofp_flow_mod()
            msg.match.in_port = 2
            msg.actions.append(of.ofp_action_output(port=4))
            event.connection.send(msg)
            
        elif dpid == "00-00-00-00-00-02":
            msg = of.ofp_flow_mod()
            msg.match.in_port = 1
            msg.actions.append(of.ofp_action_output(port=2))
            event.connection.send(msg)
            
            msg = of.ofp_flow_mod()
            msg.match.in_port = 2
            msg.actions.append(of.ofp_action_output(port=1))
            event.connection.send(msg)
            
        elif dpid == "00-00-00-00-00-03":
            msg = of.ofp_flow_mod()
            msg.match.in_port = 3
            msg.actions.append(of.ofp_action_output(port=1))
            event.connection.send(msg)
            
            msg = of.ofp_flow_mod()
            msg.match.in_port = 1
            msg.actions.append(of.ofp_action_output(port=3))
            event.connection.send(msg)
            
            msg = of.ofp_flow_mod()
            msg.match.in_port = 4
            msg.actions.append(of.ofp_action_output(port=2))
            event.connection.send(msg)
            
            msg = of.ofp_flow_mod()
            msg.match.in_port = 2
            msg.actions.append(of.ofp_action_output(port=4))
            event.connection.send(msg)
            
        elif dpid == "00-00-00-00-00-04":
            msg = of.ofp_flow_mod()
            msg.match.in_port = 1
            msg.actions.append(of.ofp_action_output(port=2))
            event.connection.send(msg)
            
            msg = of.ofp_flow_mod()
            msg.match.in_port = 2
            msg.actions.append(of.ofp_action_output(port=1))
            event.connection.send(msg)

        

def launch():
    pox.openflow.discovery.launch()
    pox.openflow.spanning_tree.launch()

    core.registerNew(TopologySlice)
