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

class CustomSlice (EventMixin):
    def __init__(self):
        self.listenTo(core.openflow)
        core.openflow_discovery.addListeners(self)

        self.adjacency = defaultdict(lambda:defaultdict(lambda:None))
        self.mac_to_port = {}

        self.portmap = {
            ('00-00-00-00-00-01', EthAddr('00:00:00:00:00:01'), EthAddr('00:00:00:00:00:05'), 200): '00-00-00-00-00-04',
            ('00-00-00-00-00-04', EthAddr('00:00:00:00:00:01'), EthAddr('00:00:00:00:00:05'), 200): '00-00-00-00-00-07',
            ('00-00-00-00-00-07', EthAddr('00:00:00:00:00:05'), EthAddr('00:00:00:00:00:01'), 200): '00-00-00-00-00-04',
            ('00-00-00-00-00-04', EthAddr('00:00:00:00:00:05'), EthAddr('00:00:00:00:00:01'), 200): '00-00-00-00-00-01',
            
            ('00-00-00-00-00-03', EthAddr('00:00:00:00:00:03'), EthAddr('00:00:00:00:00:06'), 80): '00-00-00-00-00-06',
            ('00-00-00-00-00-06', EthAddr('00:00:00:00:00:03'), EthAddr('00:00:00:00:00:06'), 80): '00-00-00-00-00-07',
            ('00-00-00-00-00-07', EthAddr('00:00:00:00:00:06'), EthAddr('00:00:00:00:00:03'), 80): '00-00-00-00-00-06',
            ('00-00-00-00-00-06', EthAddr('00:00:00:00:00:06'), EthAddr('00:00:00:00:00:03'), 80): '00-00-00-00-00-03',
            
            ('00-00-00-00-00-03', EthAddr('00:00:00:00:00:04'), EthAddr('00:00:00:00:00:06'), 80): '00-00-00-00-00-06',
            ('00-00-00-00-00-06', EthAddr('00:00:00:00:00:04'), EthAddr('00:00:00:00:00:06'), 80): '00-00-00-00-00-07',
            ('00-00-00-00-00-07', EthAddr('00:00:00:00:00:06'), EthAddr('00:00:00:00:00:04'), 80): '00-00-00-00-00-06',
            ('00-00-00-00-00-06', EthAddr('00:00:00:00:00:06'), EthAddr('00:00:00:00:00:04'), 80): '00-00-00-00-00-03',
        }

    def _handle_ConnectionUp(self, event):
        dpid = dpidToStr(event.dpid)
        log.debug("Switch %s has connected.", dpid)

    def _handle_LinkEvent (self, event):
        l = event.link
        sw1 = dpid_to_str(l.dpid1)
        sw2 = dpid_to_str(l.dpid2)
        self.adjacency[sw1][sw2] = l.port1
        self.adjacency[sw2][sw1] = l.port2

    def _handle_PacketIn (self, event):
        try:
            packet = event.parsed
        except AttributeError:
            return
            
        if not packet.parsed:
            return
            
        tcpp = event.parsed.find('tcp')
        udpp = event.parsed.find('udp')
        icmpp = event.parsed.find('icmp')

        this_dpid = dpid_to_str(event.dpid)
        self.mac_to_port[(this_dpid, packet.src)] = event.port

        def flood (message = None):
            msg = of.ofp_packet_out()
            msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
            msg.data = event.ofp
            msg.in_port = event.port
            event.connection.send(msg)

        def install_fwdrule(event,packet,outport):
            msg = of.ofp_flow_mod()
            msg.idle_timeout = 10
            msg.hard_timeout = 30
            msg.match = of.ofp_match.from_packet(packet, event.port)
            msg.actions.append(of.ofp_action_output(port = outport))
            msg.data = event.ofp
            msg.in_port = event.port
            event.connection.send(msg)

        def forward (message = None):
            this_dpid = dpid_to_str(event.dpid)

            if packet.dst.is_multicast:
                flood()
                return
            else:
                if icmpp is not None:
                    flood()
                    return
                    
                try:
                    if udpp is not None:
                        dst_port = udpp.dstport
                    elif tcpp is not None:
                        dst_port = tcpp.dstport
                    else:
                        install_fwdrule(event,packet,of.OFPP_FLOOD)
                        return
                    
                    next_dpid = self.portmap[(this_dpid, packet.src, packet.dst, dst_port)]
                    outport = self.adjacency[this_dpid][next_dpid]
                    install_fwdrule(event, packet, outport)

                except KeyError:
                    if (this_dpid, packet.dst) in self.mac_to_port:
                        outport = self.mac_to_port[(this_dpid, packet.dst)]
                        install_fwdrule(event, packet, outport)
                    else:
                        install_fwdrule(event,packet,of.OFPP_FLOOD)

        forward()

def launch():
    pox.openflow.discovery.launch()
    pox.openflow.spanning_tree.launch()

    core.registerNew(CustomSlice)
