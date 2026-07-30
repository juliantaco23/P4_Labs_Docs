#!/usr/bin/env python3
"""
controller.py -- Reinforcement Learning agent for SYN Flood mitigation.

Implements the main RL agent loop that interacts with the P4 switch (s1)
using simple_switch_CLI via subprocess calls.

Architecture:
  - Reads synReg and synAckRstReg registers from s1 periodically.
  - Computes the state (discretized SYN excess).
  - Chooses an action using epsilon-greedy policy (Q-table).
  - Executes the action (installs/removes firewall rule on s1).
  - Observes the new state and computes the reward.
  - Updates the Q-table via the Bellman equation.

Usage:
  python3 controller.py
  python3 controller.py --port 9090 --interval 2 --episodes 100

Reference: Zheng, C. et al. "QCMP: Load Balancing via In-Network
Reinforcement Learning". ACM SIGCOMM FIRA Workshop, 2023.
"""

import argparse
import re
import subprocess
import sys
import time
from typing import Dict

import numpy as np

from q_table import (QTable, compute_reward, ratio_to_state,
                     ACTION_SUBNETS, ACTION_SPACE)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration constants
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_THRIFT_PORT = 9090
DEFAULT_INTERVAL    = 2     # seconds between register reads
DEFAULT_EPISODES    = 200   # number of training episodes
ATTACK_THRESHOLD    = 10    # SYN count threshold indicating active attack
                             # Calibrated for ~14.5 SYN/s actual rate (sendp at --pps 50)


# ─────────────────────────────────────────────────────────────────────────────
# Switch interaction functions (simple_switch_CLI)
# ─────────────────────────────────────────────────────────────────────────────

def run_cli_command(command: str, thrift_port: int = DEFAULT_THRIFT_PORT) -> str:
    """
    Execute a command in simple_switch_CLI and return the output as a string.
    """
    result = subprocess.run(
        ['simple_switch_CLI', '--thrift-port', str(thrift_port)],
        input=command,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"[CLI ERROR] {result.stderr.strip()}", file=sys.stderr)
        return ''
    return result.stdout


def read_register(register_name: str, index: int,
                  thrift_port: int = DEFAULT_THRIFT_PORT) -> int:
    """
    Read the value of a switch register.

    TO-DO [1]: Implement this function.

        1. Build the CLI command
           Example: "register_read MyIngress.synReg 1"

        2. Call run_cli_command() with that command.

        3. simple_switch_CLI output format:
               "MyIngress.synReg[1]= 42\n"
           Use a regex to extract the integer:
               re.search(r'=\s*(\d+)', output)

        4. Return the extracted integer. Return 0 if not found.

        Regex hint: r'=\s*(\d+)'  captures the number after '='.
    ────────────────────────────────────────────────────────────────────────────
    SOLUTION:
    """
    cmd    = f'register_read {register_name} {index}'
    output = run_cli_command(cmd, thrift_port)
    match  = re.search(r'=\s*(\d+)', output)
    return int(match.group(1)) if match else 0


def reset_registers(thrift_port: int = DEFAULT_THRIFT_PORT) -> None:
    """Reset the packet counters on the switch to zero."""
    run_cli_command('register_reset MyIngress.synReg',       thrift_port)
    run_cli_command('register_reset MyIngress.synAckRstReg', thrift_port)
    print("[CTRL] Registers reset.")


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic firewall management
# ─────────────────────────────────────────────────────────────────────────────

# Tracks handles of installed firewall entries (needed to delete them later)
_firewall_handles: Dict[str, int] = {}


def block_subnet(subnet_cidr: str, thrift_port: int = DEFAULT_THRIFT_PORT) -> None:
    """
    Install a blocking rule in the firewall table for the given subnet.

    TO-DO [2]: Implement this function.

        The CLI command to add an LPM rule
        Example:
            "table_add MyIngress.firewall MyIngress.block 10.0.1.64/26 => 1"

        The table_add output includes:
            "table_add ... ok (handle X)"
        where X is the integer handle of the entry.

        Extract the handle with: r'handle (\d+)'
        Store it in _firewall_handles[subnet_cidr] so it can be deleted later.

        Print a message indicating which subnet was blocked.
    ────────────────────────────────────────────────────────────────────────────
    SOLUTION:
    """
    if subnet_cidr in _firewall_handles:
        print(f"[FW] {subnet_cidr} already blocked.")
        return

    cmd    = f'table_add MyIngress.firewall MyIngress.block {subnet_cidr} => 1'
    output = run_cli_command(cmd, thrift_port)
    match  = re.search(r'handle (\d+)', output)
    if match:
        handle = int(match.group(1))
        _firewall_handles[subnet_cidr] = handle
        print(f"[FW] BLOCKED {subnet_cidr} (handle {handle})")
    else:
        print(f"[FW] ERROR blocking {subnet_cidr}: {output.strip()}", file=sys.stderr)


def unblock_subnet(subnet_cidr: str, thrift_port: int = DEFAULT_THRIFT_PORT) -> None:
    """
    Remove the blocking rule for the given subnet.

    TO-DO [3]: Implement this function.

        If subnet_cidr is in _firewall_handles:
            Build the command
            Example: "table_delete MyIngress.firewall 1"
            Call run_cli_command() with that command.
            Remove the entry from _firewall_handles.
            Print an unblock message.

        If not registered, print that it was already free.
    ────────────────────────────────────────────────────────────────────────────
    SOLUTION:
    """
    if subnet_cidr not in _firewall_handles:
        print(f"[FW] {subnet_cidr} was not blocked.")
        return

    handle = _firewall_handles.pop(subnet_cidr)
    cmd    = f'table_delete MyIngress.firewall {handle}'
    run_cli_command(cmd, thrift_port)
    print(f"[FW] UNBLOCKED {subnet_cidr} (handle {handle})")


def unblock_all(thrift_port: int = DEFAULT_THRIFT_PORT) -> None:
    """Remove all active firewall rules."""
    for subnet in list(_firewall_handles.keys()):
        unblock_subnet(subnet, thrift_port)


# ─────────────────────────────────────────────────────────────────────────────
# Main RL agent loop
# ─────────────────────────────────────────────────────────────────────────────

def execute_action(action: int, thrift_port: int) -> None:
    """
    Execute the action chosen by the agent on the firewall table.

    Action map:
        0 → Block 10.0.1.0/26   (blocks h1 AND h2 — incorrect action)
        1 → Block 10.0.1.64/26  (blocks ONLY h2   — correct action)
        2 → Unblock all          (passive action)
        3 → Block both subnets   (aggressive)
    """
    if action == 0:
        unblock_all(thrift_port)
        block_subnet('10.0.1.0/26', thrift_port)
    elif action == 1:
        unblock_all(thrift_port)
        block_subnet('10.0.1.64/26', thrift_port)
    elif action == 2:
        unblock_all(thrift_port)
    elif action == 3:
        block_subnet('10.0.1.0/26',  thrift_port)
        block_subnet('10.0.1.64/26', thrift_port)


def run_rl_agent(thrift_port: int, interval: float, episodes: int) -> None:
    """
    Main Q-Learning agent loop.

    Each episode:
      1. Read synReg and synAckRstReg registers from the switch.
      2. Compute current state (discretized SYN excess).
      3. If no attack (state == 0), wait for the next cycle.
      4. Choose an action (epsilon-greedy).
      5. Execute the action (install/remove firewall rule).
      6. Wait an interval and re-read registers (observe the effect).
      7. Compute the reward.
      8. Update the Q-table.
      9. Decay epsilon.
     10. Reset counters for the next cycle.
    """
    agent = QTable(learning_rate=0.2, discount=0.9, epsilon=0.4)

    print(f"\n[RL] Agent started. Thrift port: {thrift_port}")
    print(f"[RL] Episodes: {episodes}, Interval: {interval}s\n")

    for episode in range(episodes):
        # ── Step 1-2: read current state ──────────────────────────────────────
        # TO-DO [5] : The register names and index below must match
        #            the declarations in syn_flood_rl.p4.
        #            - 'MyIngress.synReg'       counts incoming SYN packets
        #            - 'MyIngress.synAckRstReg' counts ACK/SYN-ACK/RST packets
        #            - Index 1: the active slot (index 0 is reserved)
        # ─────────────────────────────────────────────────────────────────────
        syn_before    = read_register('MyIngress.synReg',       1, thrift_port)
        synack_before = read_register('MyIngress.synAckRstReg', 1, thrift_port)
        state         = ratio_to_state(syn_before, synack_before)

        print(f"[E{episode:03d}] SYN={syn_before} SYN-ACK={synack_before} "
              f"state={state} ε={agent.epsilon:.2f}")

        # ── Step 3: if no attack, wait and reset ─────────────────────────────
        if state == 0:
            print(f"[E{episode:03d}] No attack detected. Waiting...")
            time.sleep(interval)
            reset_registers(thrift_port)   # reset so next episode sees only the last interval
            continue

        # ── Step 4: choose action ─────────────────────────────────────────────
        action = agent.choose_action(state)
        print(f"[E{episode:03d}] → Action {action}: {ACTION_SPACE[action]}")

        # ── Step 5: execute action ───────────────────────────────────────────
        execute_action(action, thrift_port)

        # ── Step 6: observe effect ───────────────────────────────────────────
        time.sleep(interval)
        reset_registers(thrift_port)
        time.sleep(interval)

        syn_after    = read_register('MyIngress.synReg',       1, thrift_port)
        synack_after = read_register('MyIngress.synAckRstReg', 1, thrift_port)
        next_state   = ratio_to_state(syn_after, synack_after)

        # ── Step 7: compute reward ───────────────────────────────────────────
        reward = compute_reward(action, syn_before, syn_after, synack_after)

        print(f"[E{episode:03d}] SYN_after={syn_after} SYN-ACK_after={synack_after} "
              f"next_state={next_state} reward={reward:+.1f}")

        # ── Step 8: update Q-table ────────────────────────────────────────
        new_q = agent.update(state, action, reward, next_state)
        print(f"[E{episode:03d}] Q({state},{action}) updated → {new_q:.4f}")

        # ── Step 9: decay epsilon ────────────────────────────────────────────
        agent.decay_epsilon()

        # ── Success: show Q-table if attack was mitigated ──────────────────
        if next_state == 0 and reward > 0:
            print(f"\n[RL] *** Attack MITIGATED in episode {episode} ***\n")
            agent.print_table()

        # ── Step 10: reset for next cycle ───────────────────────────────
        reset_registers(thrift_port)
        time.sleep(interval)

    print("\n[RL] Training complete.")
    agent.print_table()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='RL agent for SYN Flood mitigation on a P4 switch')
    parser.add_argument('--port',     type=int,   default=DEFAULT_THRIFT_PORT,
                        help='Thrift port of s1 (default: 9090)')
    parser.add_argument('--interval', type=float, default=DEFAULT_INTERVAL,
                        help='Seconds between agent cycles (default: 2)')
    parser.add_argument('--episodes', type=int,   default=DEFAULT_EPISODES,
                        help='Number of training episodes (default: 200)')
    args = parser.parse_args()

    try:
        run_rl_agent(args.port, args.interval, args.episodes)
    except KeyboardInterrupt:
        print('\n[RL] Interrupted by user. Unblocking all subnets...')
        unblock_all(args.port)


if __name__ == '__main__':
    main()



