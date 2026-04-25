#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
p4_mininet.py — Minimal BMv2 simple_switch class for Mininet.

This module provides P4Switch (a Mininet Switch subclass) that starts
BMv2 simple_switch as the underlying datapath.  It does NOT require
ONOS, Stratum, nor any external controller.

After Mininet starts, use simple_switch_CLI to install table entries:

    simple_switch_CLI --thrift-port <port> < s1-commands.txt

Typical thrift ports: s1 → 9090, s2 → 9091, etc.

Prerequisites (bare-metal Ubuntu 20.04):
    sudo apt-get install -y p4lang-bmv2 p4lang-p4c mininet
    # Or build from source:
    #   https://github.com/p4lang/behavioral-model
    #   https://github.com/p4lang/p4c
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
        """
        Parameters
        ----------
        name : str
            Switch name (e.g. 's1').
        sw_path : str
            Path to simple_switch binary (default: 'simple_switch').
        json_path : str
            Path to compiled BMv2 JSON (e.g. 'p4src/build/bmv2.json').
        thrift_port : int
            Thrift RPC port for simple_switch_CLI (auto-assigned if None).
        log_console : bool
            If True, print BMv2 log to stdout (verbose).
        log_file : str
            Path to write BMv2 log.  Defaults to /tmp/<name>.log.
        pcap_dir : str
            If set, write per-port pcap files to this directory.
        """
        Switch.__init__(self, name, **kwargs)
        self.sw_path = sw_path
        self.json_path = json_path

        if thrift_port is not None:
            self.thrift_port = thrift_port
        else:
            self.thrift_port = P4Switch.next_thrift_port
            P4Switch.next_thrift_port += 1

        # device_id determines the nanomsg IPC socket path:
        # /tmp/bmv2-{device_id}-notifications.ipc
        # Must be unique per switch to avoid "Address already in use".
        self.device_id = self.thrift_port - 9090

        self.log_console = log_console
        self.log_file = log_file or '/tmp/%s.log' % self.name
        self.pcap_dir = pcap_dir

    def start(self, controllers):
        """Start simple_switch subprocess."""
        if self.json_path is None or not os.path.isfile(self.json_path):
            error("*** ERROR: BMv2 JSON not found: %s\n" % self.json_path)
            error("    Run:  p4c-bm2-ss -o <output.json> <program.p4>\n")
            return

        args = [self.sw_path]

        # Map Mininet interfaces to BMv2 port numbers
        for port, intf in self.intfs.items():
            if port == 0:
                continue  # skip loopback (lo always has IP, original check was wrong)
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
        info("⚡ Starting %s @ thrift-port %d\n" % (self.name, self.thrift_port))
        info("   cmd: %s\n" % ' '.join(str(a) for a in args))
        self.bmv2popen = subprocess.Popen(args, stdout=logfile, stderr=logfile)
        time.sleep(1)  # Give BMv2 time to initialize
        if self.bmv2popen.poll() is not None:
            error("*** ERROR: %s exited immediately (code %d). Check: %s\n"
                  % (self.name, self.bmv2popen.returncode, self.log_file))

    def stop(self, deleteIntfs=True):
        """Stop simple_switch."""
        if hasattr(self, 'bmv2popen') and self.bmv2popen is not None:
            self.bmv2popen.terminate()
            self.bmv2popen.wait()
            self.bmv2popen = None
        Switch.stop(self, deleteIntfs)

    def install_rules(self, commands_file):
        """Install table entries from a commands file via simple_switch_CLI."""
        if not os.path.isfile(commands_file):
            error("*** Commands file not found: %s\n" % commands_file)
            return False
        info("📋 Installing rules from %s → %s (thrift %d)\n"
             % (commands_file, self.name, self.thrift_port))
        result = subprocess.run(
            ['simple_switch_CLI', '--thrift-port', str(self.thrift_port)],
            stdin=open(commands_file, 'r'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            error("*** Error installing rules: %s\n" % result.stderr.decode())
            return False
        return True


class P4Host(Host):
    """Host with TX/RX offload disabled (avoids checksum issues with BMv2)."""

    def config(self, **params):
        r = super().config(**params)
        for off in ["rx", "tx", "sg"]:
            self.cmd("ethtool --offload %s %s off" % (self.defaultIntf(), off))
        return r
