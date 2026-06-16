#!/usr/bin/env python3
"""
q_table.py — Implementación de Q-Learning para el ejercicio RL + P4.

Este módulo define la tabla Q y las funciones necesarias para el algoritmo
Q-Learning que el agente usa para aprender a mitigar un ataque SYN Flood.

Estado del entorno:
  El "estado" se define como el ratio SYN/SYN-ACK observado en el switch,
  discretizado en 13 niveles (0-12):
    - Estado 0: ratio < 1 (sin ataque)
    - Estado 1-11: ratios crecientes (ataque moderado → severo)
    - Estado 12: ratio muy alto (ataque masivo)

Acciones disponibles (ACTION_SPACE):
    0 → Bloquear subred 10.0.1.0/26  (bloquea h1 Y h2 — acción incorrecta)
    1 → Bloquear subred 10.0.1.64/26 (bloquea SOLO h2 — acción correcta)
    2 → No bloquear (o desbloquear)   (acción pasiva / reset)
    3 → Bloquear ambas subredes       (bloquea todo — subóptimo)

Referencia: Zheng, C. et al. "QCMP: Load Balancing via In-Network
Reinforcement Learning". ACM SIGCOMM FIRA Workshop, 2023.
"""

import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# Espacio de estados y acciones
# ─────────────────────────────────────────────────────────────────────────────
NUM_STATES  = 13   # Niveles de ratio SYN/SYN-ACK (0 a 12)
ACTION_SPACE = ('block_all', 'block_attacker', 'no_action', 'block_both')

# Subredes que corresponden a cada acción de bloqueo
ACTION_SUBNETS = {
    0: '10.0.1.0/26',    # Bloquea h1 Y h2 (incorrecta)
    1: '10.0.1.64/26',   # Bloquea SOLO h2 (correcta)
    2: None,             # Sin bloqueo
    3: None,             # Se usan las dos reglas anteriores
}

# ─────────────────────────────────────────────────────────────────────────────
# Clase Q-Table
# ─────────────────────────────────────────────────────────────────────────────

class QTable:
    """Tabla Q para Q-Learning con epsilon-greedy."""

    def __init__(self,
                 learning_rate: float = 0.2,
                 discount:      float = 0.9,
                 epsilon:       float = 0.4) -> None:
        """
        Parameters
        ----------
        learning_rate : float
            Tasa de aprendizaje alpha (α) de la ecuación de Bellman.
        discount : float
            Factor de descuento gamma (γ). Controla la importancia del
            reward futuro vs. el inmediato.
        epsilon : float
            Probabilidad de exploración (política ε-greedy).
        """
        self.lr      = learning_rate
        self.gamma   = discount
        self.epsilon = epsilon

        # Inicializar Q-table con valores pequeños aleatorios
        np.random.seed(42)
        self.q = np.random.rand(NUM_STATES, len(ACTION_SPACE)) * 0.1 - 0.05
        self.q = np.round(self.q, decimals=3)

        self.step_count = 0   # Contador de pasos para decaimiento de epsilon

    # ── Política ε-greedy ─────────────────────────────────────────────────────

    def choose_action(self, state: int) -> int:
        """
        Selecciona una acción según la política epsilon-greedy.

        TO-DO [A]: Implementa esta función.

            La política epsilon-greedy funciona así:
            - Con probabilidad epsilon → elige una acción ALEATORIA
              (exploración: el agente prueba acciones desconocidas).
            - Con probabilidad (1 - epsilon) → elige la acción con mayor
              valor Q para el estado actual (explotación: el agente usa
              lo que ya aprendió).

            Parámetros:
              state : int  →  estado actual (0 a NUM_STATES-1)

            Retorna:
              int  →  índice de la acción elegida (0 a len(ACTION_SPACE)-1)

            Pistas:
              - np.random.rand() genera un float uniforme en [0, 1).
              - np.argmax(array) retorna el índice del máximo.
              - np.random.randint(low, high) genera un entero aleatorio.
              - La Q-table está en self.q con shape (NUM_STATES, num_actions).
        ────────────────────────────────────────────────────────────────────
        SOLUTION:
        """
        if np.random.rand() < self.epsilon:
            # Exploración: acción aleatoria
            return np.random.randint(0, len(ACTION_SPACE))
        else:
            # Explotación: acción de mayor valor Q
            return int(np.argmax(self.q[state, :]))

    # ── Actualización Q (ecuación de Bellman) ─────────────────────────────────

    def update(self, state: int, action: int, reward: float, next_state: int) -> float:
        """
        Actualiza el valor Q(state, action) usando la ecuación de Bellman.

        TO-DO [B]: Implementa esta función.

            La ecuación de Bellman para Q-Learning es:

              Q(s, a) ← Q(s, a) + α * [r + γ * max_a'(Q(s', a')) - Q(s, a)]

            donde:
              s      = state       (estado actual)
              a      = action      (acción tomada)
              r      = reward      (recompensa recibida)
              s'     = next_state  (nuevo estado tras ejecutar la acción)
              α      = self.lr     (learning rate)
              γ      = self.gamma  (discount factor)

            Parámetros:
              state, action, reward, next_state : como se describe arriba.

            Retorna:
              float  →  el nuevo valor Q(state, action) tras la actualización.

            Pistas:
              - np.max(array) retorna el máximo valor de un array.
              - La fila de la Q-table para next_state es self.q[next_state, :].
        ────────────────────────────────────────────────────────────────────
        SOLUTION:
        """
        current_q    = self.q[state, action]
        max_future_q = np.max(self.q[next_state, :])
        new_q = current_q + self.lr * (reward + self.gamma * max_future_q - current_q)
        self.q[state, action] = round(new_q, 4)
        return new_q

    # ── Decaimiento de epsilon ────────────────────────────────────────────────

    def decay_epsilon(self) -> None:
        """
        Reduce epsilon gradualmente para favorecer explotación con el tiempo.

        TO-DO [C] (opcional / extensión): Implementa un esquema de decaimiento.
            Idea: después de cada N pasos, reduce epsilon en 0.05 hasta un
            mínimo de 0.05.  Usa self.step_count para llevar la cuenta.
        ────────────────────────────────────────────────────────────────────
        SOLUTION:
        """
        self.step_count += 1
        if self.step_count % 20 == 0 and self.epsilon > 0.05:
            self.epsilon = round(self.epsilon - 0.05, 2)

    def reset(self) -> None:
        """Reinicia la Q-table (útil tras un entrenamiento exitoso)."""
        np.random.seed(42)
        self.q = np.random.rand(NUM_STATES, len(ACTION_SPACE)) * 0.1 - 0.05
        self.q = np.round(self.q, decimals=3)
        self.epsilon    = 0.4
        self.step_count = 0

    def print_table(self) -> None:
        """Imprime la Q-table formateada."""
        header = "  State |" + " ".join(f" {a:>14}" for a in ACTION_SPACE)
        print(header)
        print("-" * len(header))
        for s in range(NUM_STATES):
            row = f"  {s:>5} |" + " ".join(f" {v:>14.4f}" for v in self.q[s, :])
            print(row)


# ─────────────────────────────────────────────────────────────────────────────
# Función de reward
# ─────────────────────────────────────────────────────────────────────────────

def compute_reward(action: int,
                   syn_before: int, syn_after: int,
                   synack_after: int) -> float:
    """
    Calcula el reward para el agente RL tras ejecutar una acción.

    TO-DO [D]: Implementa la función de reward.

        El objetivo del agente es mitigar el ataque SYN Flood sin
        bloquear tráfico legítimo.  Define las reglas de reward:

        Señales clave:
          - syn_before  : conteo SYN antes de la acción
          - syn_after   : conteo SYN después de la acción
          - synack_after: conteo SYN-ACK después (indica tráfico legítimo)
          - action      : la acción ejecutada (0, 1, 2 o 3)

        Criterios sugeridos:
          1. Si el ataque se detuvo (syn_after < umbral) Y hay tráfico
             legítimo (synack_after > 0) → reward ALTO positivo.
          2. Si el ataque bajó parcialmente → reward moderado.
          3. Si se bloqueó todo (acción 0: bloquea h1 y h2) → reward NEGATIVO
             (el agente perjudicó tráfico legítimo).
          4. Si no hubo cambio → reward pequeño negativo (inacción costosa).

        Retorna: float  →  el valor del reward (puede ser negativo).

    ────────────────────────────────────────────────────────────────────
    SOLUTION:
    """
    ATTACK_THRESHOLD = 50   # SYN packets que indican ataque activo

    if action == 0:
        # Acción incorrecta: bloquea todo, incluyendo tráfico legítimo
        return -10.0

    if syn_after < ATTACK_THRESHOLD and synack_after > 0:
        # Ataque detenido Y tráfico legítimo circulando → éxito
        return +15.0
    elif syn_after < syn_before:
        # Ataque reducido parcialmente
        return +5.0
    else:
        # Sin mejora
        return -2.0


# ─────────────────────────────────────────────────────────────────────────────
# Función auxiliar: discretización del ratio
# ─────────────────────────────────────────────────────────────────────────────

def ratio_to_state(syn_count: int, synack_count: int) -> int:
    """
    Convierte el ratio SYN/SYN-ACK en un estado discreto (0–12).

    Un ratio alto (muchos SYN, pocos SYN-ACK) indica ataque.
    Un ratio bajo o cero indica tráfico normal.

    TO-DO [E]: Implementa esta función.

        Lógica sugerida:
          - Si synack_count == 0 y syn_count > 0 → estado máximo (12).
          - Si synack_count == 0 y syn_count == 0 → estado 0 (sin tráfico).
          - Si ratio = syn/synack:
              - ratio < 1   → estado 0
              - ratio 1-2   → estado 1
              - ratio 2-3   → estado 2
              - ...
              - ratio > 12  → estado 12

        Retorna: int en [0, 12].
    ────────────────────────────────────────────────────────────────────
    SOLUTION:
    """
    if synack_count == 0:
        return 12 if syn_count > 0 else 0

    ratio = syn_count / synack_count
    state = int(min(ratio, 12))
    return state
