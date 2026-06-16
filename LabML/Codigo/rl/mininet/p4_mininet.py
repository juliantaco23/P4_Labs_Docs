#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
p4_mininet.py — Minimal BMv2 simple_switch class for Mininet.
(Copia del módulo estándar del proyecto TFG.)
"""

import os
import time
import subprocess
from mininet.node import Switch, Host
from mininet.log import info, error


class P4Switch(Switch):
    """BMv2 simple_switch integrated with Mininet."""

    next_thrift_port = 9090

    def __init__(self, name,
                 sw_path='simple_switch',
                 json_path=None,
                 thrift_port=None,
                 log_console=False,
                 log_file=None,
                 pcap_dir=None,
                 **kwargs):
        Switch.__init__(self, name, **kwargs)
        self.sw_path = sw_path
        self.json_path = json_path

        if thrift_port is not None:
            self.thrift_port = thrift_port
        else:
            self.thrift_port = P4Switch.next_thrift_port
            P4Switch.next_thrift_port += 1

        self.device_id = self.thrift_port - 9090
        self.log_console = log_console
        self.log_file = log_file or '/tmp/%s.log' % self.name
        self.pcap_dir = pcap_dir

    def start(self, controllers):
        """Start simple_switch subprocess."""
        if self.json_path is None or not os.path.isfile(self.json_path):
            error("*** ERROR: BMv2 JSON not found: %s\n" % self.json_path)
            return

        args = [self.sw_path]
        for port, intf in self.intfs.items():
            if port == 0:
                continue
            args.extend(['-i', '%d@%s' % (port, intf.name)])

        args.extend(['--thrift-port', str(self.thrift_port)])
        args.extend(['--device-id', str(self.device_id)])

        if self.pcap_dir:
            if not os.path.isdir(self.pcap_dir):
                os.makedirs(self.pcap_dir)
            args.extend(['--pcap', self.pcap_dir])

        if self.log_console:
            args.append('--log-console')

        args.append(self.json_path)

        logfile = open(self.log_file, 'w')
        info("Starting %s @ thrift-port %d\n" % (self.name, self.thrift_port))
        self.bmv2popen = subprocess.Popen(args, stdout=logfile, stderr=logfile)
        time.sleep(1)
        if self.bmv2popen.poll() is not None:
            error("*** ERROR: %s exited immediately (code %d). Check: %s\n"
                  % (self.name, self.bmv2popen.returncode, self.log_file))

    def stop(self, deleteIntfs=True):
        if hasattr(self, 'bmv2popen') and self.bmv2popen is not None:
            self.bmv2popen.terminate()
            self.bmv2popen.wait()
            self.bmv2popen = None
        Switch.stop(self, deleteIntfs)


class P4Host(Host):
    """Host with TX/RX offload disabled."""

    def config(self, **params):
        r = super().config(**params)
        self.defaultIntf().rename("eth0")
        for off in ["rx", "tx", "sg"]:
            self.cmd("ethtool --offload eth0 %s off" % off)
        return r
