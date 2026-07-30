#!/usr/bin/env python3
"""
q_table.py -- Q-Learning implementation for the RL + P4 exercise.

Defines the Q-table and the functions needed by the Q-Learning algorithm
that the agent uses to learn to mitigate a SYN Flood attack.

Environment state:
  The "state" is defined as the SYN excess (syn - synack) observed on
  the switch, discretized into 13 levels (0-12):
    - State 0: no excess (no attack)
    - States 1-11: increasing excess (moderate -> severe attack)
    - State 12: large excess or no synack (massive attack)

Available actions (ACTION_SPACE):
    0 -> Block subnet 10.0.1.0/26  (blocks h1 AND h2 -- incorrect action)
    1 -> Block subnet 10.0.1.64/26 (blocks ONLY h2  -- correct action)
    2 -> No block (or unblock)      (passive action / reset)
    3 -> Block both subnets         (blocks all -- suboptimal)

Reference: Zheng, C. et al. "QCMP: Load Balancing via In-Network
Reinforcement Learning". ACM SIGCOMM FIRA Workshop, 2023.
"""

import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# State and action space
# ─────────────────────────────────────────────────────────────────────────────
NUM_STATES  = 13   # Discrete SYN-excess levels (0 to 12)
ACTION_SPACE = ('block_all', 'block_attacker', 'no_action', 'block_both')

# Subnets corresponding to each blocking action
ACTION_SUBNETS = {
    0: '10.0.1.0/26',    # Blocks h1 AND h2 (incorrect)
    1: '10.0.1.64/26',   # Blocks ONLY h2   (correct)
    2: None,             # No block
    3: None,             # Both rules above are used
}

# ─────────────────────────────────────────────────────────────────────────────
# Q-Table class
# ─────────────────────────────────────────────────────────────────────────────

class QTable:
    """Q-Table for Q-Learning with epsilon-greedy policy."""

    def __init__(self,
                 learning_rate: float = 0.2,
                 discount:      float = 0.9,
                 epsilon:       float = 0.4) -> None:
        """
        Parameters
        ----------
        learning_rate : float
            Learning rate alpha (α) of the Bellman equation.
        discount : float
            Discount factor gamma (γ). Controls the importance of future
            reward vs. immediate reward.
        epsilon : float
            Exploration probability (epsilon-greedy policy).
        """
        self.lr      = learning_rate
        self.gamma   = discount
        self.epsilon = epsilon

        # Initialize Q-table with small random values
        np.random.seed(42)
        self.q = np.random.rand(NUM_STATES, len(ACTION_SPACE)) * 0.1 - 0.05
        self.q = np.round(self.q, decimals=3)

        self.step_count = 0   # Step counter for epsilon decay

    # ── ε-greedy policy ─────────────────────────────────────────────────────

    def choose_action(self, state: int) -> int:
        """
        Select an action according to the epsilon-greedy policy.

            The epsilon-greedy policy works as follows:
            - With probability epsilon → choose a RANDOM action
              (exploration: the agent tries unknown actions).
            - With probability (1 - epsilon) → choose the action with the highest
              Q-value for the current state (exploitation: the agent uses
              what it has already learned).

            Parameters:
              state : int  →  current state (0 to NUM_STATES-1)

            Returns:
              int  →  index of the chosen action (0 to len(ACTION_SPACE)-1)

        """
        if np.random.rand() < self.epsilon:
            # Exploration: random action
            return np.random.randint(0, len(ACTION_SPACE))
        else:
            # Exploitation: action with highest Q-value
            return int(np.argmax(self.q[state, :]))

    # ── Q-update (Bellman equation) ───────────────────────────────────────────

    def update(self, state: int, action: int, reward: float, next_state: int) -> float:
        """
        Update Q(state, action) using the Bellman equation.
            The Bellman equation for Q-Learning is:

              Q(s, a) ← Q(s, a) + α * [r + γ * max_a'(Q(s', a')) - Q(s, a)]

            where:
              s      = state       (current state)
              a      = action      (action taken)
              r      = reward      (reward received)
              s'     = next_state  (new state after executing the action)
              α      = self.lr     (learning rate)
              γ      = self.gamma  (discount factor)

            Parameters:
              state, action, reward, next_state: as described above.

            Returns:
              float → the new Q(state, action) value after the update.
        """
        current_q    = self.q[state, action]
        max_future_q = np.max(self.q[next_state, :])
        new_q = current_q + self.lr * (reward + self.gamma * max_future_q - current_q)
        self.q[state, action] = round(new_q, 4)
        return new_q

    # ── Epsilon decay ────────────────────────────────────────────────

    def decay_epsilon(self) -> None:
        """
        Gradually reduce epsilon to favor exploitation over time.
            Idea: after every N steps, reduce epsilon by 0.05 down to
            a minimum of 0.05. Use self.step_count to track steps.
        """
        self.step_count += 1
        if self.step_count % 20 == 0 and self.epsilon > 0.05:
            self.epsilon = round(self.epsilon - 0.05, 2)

    def reset(self) -> None:
        """Reset the Q-table to initial random values."""
        np.random.seed(42)
        self.q = np.random.rand(NUM_STATES, len(ACTION_SPACE)) * 0.1 - 0.05
        self.q = np.round(self.q, decimals=3)
        self.epsilon    = 0.4
        self.step_count = 0

    def print_table(self) -> None:
        """Print the Q-table in formatted form."""
        header = "  State |" + " ".join(f" {a:>14}" for a in ACTION_SPACE)
        print(header)
        print("-" * len(header))
        for s in range(NUM_STATES):
            row = f"  {s:>5} |" + " ".join(f" {v:>14.4f}" for v in self.q[s, :])
            print(row)


# ─────────────────────────────────────────────────────────────────────────────
# Reward function for the RL agent
# ─────────────────────────────────────────────────────────────────────────────

def compute_reward(action: int,
                   syn_before: int, syn_after: int,
                   synack_after: int) -> float:
    """
    Calculate the reward for the RL agent after executing an action.

        The agent’s goal is to mitigate the SYN Flood attack without
        blocking legitimate traffic.  Define the reward rules:

        Key signals:
          - syn_before  : SYN count before the action
          - syn_after   : SYN count after the action
          - synack_after: SYN-ACK count after (indicates legitimate traffic)
          - action      : the action taken (0, 1, 2, or 3)

        Suggested criteria:
          1. If the attack was stopped (syn_after < threshold) AND there is
             legitimate traffic (synack_after > 0) → HIGH positive reward.
          2. If the attack was partially mitigated → moderate reward.
          3. If everything was blocked (action 0: blocks h1 and h2) → NEGATIVE reward
             (the agent disrupted legitimate traffic).
          4. If there was no change → small negative reward (inaction was costly).

        Returns: float  →  the reward value (may be negative).
    """
    ATTACK_THRESHOLD = 10    # SYN packets per interval indicating active attack
                               # Calibrated for ~14.5 SYN/s actual rate with --pps 50

    if action == 0:
        # Incorrect action: blocks all traffic including legitimate
        return -10.0

    if syn_after < ATTACK_THRESHOLD and synack_after > 0:
        # Attack stopped AND legitimate traffic flowing -> success
        return +15.0
    elif syn_after < syn_before:
        # Attack partially reduced
        return +5.0
    else:
        # No improvement
        return -2.0


# ─────────────────────────────────────────────────────────────────────────────
# Auxiliary function: state discretization
# ─────────────────────────────────────────────────────────────────────────────

def ratio_to_state(syn_count: int, synack_count: int) -> int:
    """
    Convert the SYN excess to a discrete state (0–12).

    A high ratio (many SYNs, few SYN-ACKs) indicates an attack.
    A low or zero ratio indicates normal traffic.

        Suggested logic:
          - If synack_count == 0 and syn_count > 0 → maximum state (12).
          - If synack_count == 0 and syn_count == 0 → state 0 (no traffic).
          - If syn_count <= synack_count → state 0 (normal or legitimate traffic).
          - If syn_count > synack_count → there is a SYN excess (attack).
              Discretize the excess: state = min((syn - synack) // 10 + 1, 12)

        Why excess and not a direct ratio:
          In Mininet, h3 responds to every SYN with an RST+ACK (port 80 closed).
          This causes syn/synack → 1.0 even during the attack.
          Using the excess (syn - synack) detects the attack when the RSTs cannot
          absorb the volume of the SYN flood.

        Returns: int in [0, 12].
    """
    if synack_count == 0:
        return 12 if syn_count > 0 else 0

    if syn_count <= synack_count:
        return 0   # Normal traffic: SYN-ACK/RST absorbs all SYNs
    # SYN excess over SYNACK → attack detected
    excess = syn_count - synack_count
    return min(int(excess / 10) + 1, 12)


