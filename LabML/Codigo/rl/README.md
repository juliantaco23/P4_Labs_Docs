[comment]: # (SPDX-License-Identifier: Apache-2.0)

# Reinforcement Learning + P4 — Exercise Guide

## Introduction

This exercise combines **Q-Learning** (a model-free Reinforcement Learning algorithm)
with a P4-programmable switch to build an adaptive defense against **SYN Flood attacks**.

The P4 switch counts SYN and SYN-ACK packets using registers. A Python controller
periodically reads these counters, calculates the attack ratio, and dynamically
installs firewall rules to block the attacker's subnet — all while keeping
legitimate traffic flowing.

Key insight: the firewall table in P4 is modified **at runtime** by the RL agent,
turning the data plane into an adaptive, learning-capable element.

## Topology

```
h1 (10.0.1.1/26)   ──port1──┐                ┌──port1── h3 (10.0.6.1)  [server]
h2 (10.0.1.82/26)  ──port2──┤ s1 ──port3─2── s2
                              └──port4── h4   (monitoring)
```

- **h1** (10.0.1.1): legitimate client, in subnet 10.0.1.0/26
- **h2** (10.0.1.82): attacker, in subnet **10.0.1.64/26**
- **h3** (10.0.6.1): HTTP server
- **h4** (10.0.4.1): monitoring host

The agent learns that blocking **10.0.1.64/26** stops the attack (h2) while
preserving legitimate traffic from h1 (in 10.0.1.0/26).

## Step 1: Compile the P4 program

```bash
cd P4_Labs_Docs/LabML/Codigo/rl
mkdir -p p4src/build
p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/syn_flood_rl.p4
```

## Step 2: Start the topology

```bash
sudo python3 mininet/topo.py
```

## Step 3: Install forwarding rules

In two separate terminals:

```bash
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
simple_switch_CLI --thrift-port 9091 < s2-commands.txt
```

## Step 4: Verify normal connectivity

```
mininet> h1 ping -c2 10.0.6.1
mininet> h2 ping -c2 10.0.6.1
```

Both pings should succeed (no firewall rules installed yet).

## Step 5: Start legitimate traffic (h1)

```
mininet> h1 python3 send_legit.py &
```

## Step 6: Start the RL agent (on the host machine, not in Mininet)

```bash
python3 controller.py --port 9090 --interval 2 --episodes 100
```

The agent will print the current state (SYN/SYN-ACK ratio) and epsilon each cycle.

## Step 7: Launch the SYN Flood attack (h2)

```
mininet> h2 python3 send_attack.py &
```

Watch the agent detect the attack (state > 0) and choose actions.
After a few episodes, it should learn to block 10.0.1.64/26 (action 1).

## Step 8: Verify mitigation

Read the registers manually to confirm the counters reset:

```bash
simple_switch_CLI --thrift-port 9090 <<< "register_read MyIngress.synReg 1"
simple_switch_CLI --thrift-port 9090 <<< "register_read MyIngress.synAckRstReg 1"
```

Check that h1 can still reach the server (blocked action 0 would prevent this).

## Student TODOs

Complete the following functions in `q_table.py` and `controller.py`:

| File | Function | TO-DO |
|------|----------|-------|
| `q_table.py` | `choose_action()` | Epsilon-greedy policy |
| `q_table.py` | `update()` | Bellman equation |
| `q_table.py` | `decay_epsilon()` | Epsilon decay schedule |
| `q_table.py` | `compute_reward()` | Reward function design |
| `q_table.py` | `ratio_to_state()` | State discretization |
| `controller.py` | `run_cli_command()` | subprocess call to CLI |
| `controller.py` | `read_register()` | Parse CLI register output |
| `controller.py` | `block_subnet()` | Install LPM firewall rule |
| `controller.py` | `unblock_subnet()` | Delete firewall rule by handle |
