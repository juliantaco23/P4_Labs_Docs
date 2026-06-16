[comment]: # (SPDX-License-Identifier: Apache-2.0)

# Decision Trees in P4 — Exercise Guide

## Introduction

This exercise explores one of the most elegant ideas in programmable networking:
**implementing Machine Learning inference directly inside a P4 data plane switch**,
with zero controller involvement during classification.

A Decision Tree is a hierarchical classifier that splits data based on feature thresholds.
In a P4 switch, **Match/Action tables with range matching** are computationally equivalent
to the decision nodes of a tree: each table entry represents a conditional branch.

**Core concept** (Xiong & Zilberman, 2021):
```
sklearn DT node: "if TCP.srcPort <= 1023 → class A"
P4 range rule:   feature2_exact | srcPort: 0->1023 => set_actionselect2(1)
```

By chaining three feature tables and one decision table, the switch can classify
millions of packets per second using a pre-trained ML model.

## Topology

```
h1 (10.0.1.1/26) ──port1──┐
h2 (10.0.1.2/26) ──port2──┤ s1  (thrift port 9090)
h3 (10.0.1.3/26) ──port3──┤
h4 (10.0.1.4/26) ──port4──┘
```

h1 is the traffic generator. h2, h3, h4 receive traffic depending on
which class the DT assigns to each packet.

## Step 1: Compile the P4 program

```bash
mkdir -p p4src/build
p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/dt_switch.p4
```

Expected: no errors. If you get "header has no fields", check TO-DO [2] (ipv4_t).

## Step 2: Start the topology

```bash
sudo python3 mininet/topo.py
```

You should see the Mininet prompt. Leave this terminal open.

## Step 3: Install the decision tree rules

In a second terminal:

```bash
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
```

You should see `table_add` confirmations for all entries.

## Step 4: Generate traffic and observe classification

In the Mininet terminal, open xterms for the receiver hosts:

```
mininet> xterm h2 h3 h4
```

In each xterm, start tcpdump:
```bash
tcpdump -i eth0 -n
```

Then send traffic from h1:
```
mininet> h1 python3 send_packets.py
```

Expected results:
- h2 receives: ICMP packets and non-TCP traffic (Class A)
- h3 receives: TCP with well-known destination ports (0–1023) (Class B)
- h4 receives: TCP with high destination ports (1024–65535) (Class C)

## Step 5: Inspect the DT table counters

After sending traffic, read the counters:

```bash
simple_switch_CLI --thrift-port 9090 <<< "counter_read feature1_table_counter 0"
simple_switch_CLI --thrift-port 9090 <<< "counter_read feature2_table_counter 0"
simple_switch_CLI --thrift-port 9090 <<< "counter_read feature3_table_counter 0"
```

## Student Activity

After completing the guided exercise, modify the decision tree to use a **different dataset**.
Use the L3 or L4 pre-trained trees in the original `DecisionTrees2/L3/` and `DecisionTrees2/L4/`
folders (in the ONOSP4-tutorial repository). Translate the tree rules into new `s1-commands.txt`
entries and verify the classification.

**Hint**: Each line of the pre-trained tree is a leaf node. Map each threshold to a range entry
in the corresponding feature table. The final class maps to a forwarding action in `ipv4_exact`.
