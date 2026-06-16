#!/usr/bin/env python3
"""
controller.py — Agente de Aprendizaje por Refuerzo para mitigación de SYN Flood.

Este script implementa el bucle principal del agente RL que interactúa con
el switch P4 (s1) usando simple_switch_CLI via subprocesos.

Arquitectura:
  - El agente lee los registros synReg y synAckRstReg de s1 periodicamente.
  - Calcula el estado (ratio SYN/SYN-ACK discretizado).
  - Elige una acción según la política epsilon-greedy (Q-table).
  - Ejecuta la acción (instala/elimina regla de firewall en s1).
  - Observa el nuevo estado y calcula el reward.
  - Actualiza la Q-table.

Comunicación con el switch (simple_switch_CLI):
  Lectura de registro:
    simple_switch_CLI --thrift-port 9090 <<< "register_read MyIngress.synReg 1"

  Instalación de regla:
    simple_switch_CLI --thrift-port 9090 <<< "table_add MyIngress.firewall MyIngress.block 10.0.1.64/26 => 1"

  Eliminación de regla:
    simple_switch_CLI --thrift-port 9090 <<< "table_delete MyIngress.firewall <handle>"

Uso:
  python3 controller.py
  python3 controller.py --port 9090 --interval 2 --episodes 100

Referencia: Zheng, C. et al. "QCMP: Load Balancing via In-Network
Reinforcement Learning". ACM SIGCOMM FIRA Workshop, 2023.
"""

import argparse
import re
import subprocess
import sys
import time

import numpy as np

from q_table import (QTable, compute_reward, ratio_to_state,
                     ACTION_SUBNETS, ACTION_SPACE)

# ─────────────────────────────────────────────────────────────────────────────
# Constantes de configuración
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_THRIFT_PORT = 9090
DEFAULT_INTERVAL    = 2     # segundos entre lecturas
DEFAULT_EPISODES    = 200   # número de pasos de entrenamiento
ATTACK_THRESHOLD    = 50    # SYN packets que indican ataque activo


# ─────────────────────────────────────────────────────────────────────────────
# Funciones de interacción con el switch (simple_switch_CLI)
# ─────────────────────────────────────────────────────────────────────────────

def run_cli_command(command: str, thrift_port: int = DEFAULT_THRIFT_PORT) -> str:
    """
    Ejecuta un comando en simple_switch_CLI y retorna la salida como string.

    TO-DO [1]: Implementa esta función.

        Usa subprocess.run() para ejecutar:
            simple_switch_CLI --thrift-port <thrift_port>
        enviando <command> como entrada estándar (stdin).

        Captura tanto stdout como stderr.
        Retorna la salida stdout decodificada como string.

        Si el proceso falla (returncode != 0), imprime un mensaje de error
        y retorna una cadena vacía.

        Pista:
          result = subprocess.run(
              ['simple_switch_CLI', '--thrift-port', str(thrift_port)],
              input=command,
              capture_output=True,
              text=True
          )
    ────────────────────────────────────────────────────────────────────────────
    SOLUTION:
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
    Lee el valor de un registro del switch.

    TO-DO [2]: Implementa esta función.

        1. Construye el comando CLI:
               "register_read <register_name> <index>"
           Ejemplo: "register_read MyIngress.synReg 1"

        2. Llama a run_cli_command() con ese comando.

        3. La salida de simple_switch_CLI tiene el formato:
               "MyIngress.synReg[1]= 42\n"
           Usa una expresión regular para extraer el entero:
               re.search(r'=\s*(\d+)', output)

        4. Retorna el entero extraído.  Si no se encuentra, retorna 0.

        Pista para la regex: r'=\s*(\d+)'  captura el número después de '='.
    ────────────────────────────────────────────────────────────────────────────
    SOLUTION:
    """
    cmd    = f'register_read {register_name} {index}'
    output = run_cli_command(cmd, thrift_port)
    match  = re.search(r'=\s*(\d+)', output)
    return int(match.group(1)) if match else 0


def reset_registers(thrift_port: int = DEFAULT_THRIFT_PORT) -> None:
    """Reinicia los registros de conteo del switch a cero."""
    run_cli_command('register_reset MyIngress.synReg',       thrift_port)
    run_cli_command('register_reset MyIngress.synAckRstReg', thrift_port)
    print("[CTRL] Registers reset.")


# ─────────────────────────────────────────────────────────────────────────────
# Gestión del firewall dinámico
# ─────────────────────────────────────────────────────────────────────────────

# Rastrea los handles de las entradas de firewall instaladas (para poder borrarlas)
_firewall_handles: dict[str, int] = {}


def block_subnet(subnet_cidr: str, thrift_port: int = DEFAULT_THRIFT_PORT) -> None:
    """
    Instala una regla de bloqueo en la tabla firewall para la subred indicada.

    TO-DO [3]: Implementa esta función.

        El comando CLI para añadir una regla LPM es:
            "table_add MyIngress.firewall MyIngress.block <subnet_cidr> => 1"

        Ejemplo:
            "table_add MyIngress.firewall MyIngress.block 10.0.1.64/26 => 1"

        La salida de table_add incluye la línea:
            "table_add ... ok (handle X)"
        donde X es el handle entero de la entrada.

        Extrae el handle con regex: r'handle (\d+)'
        Guárdalo en _firewall_handles[subnet_cidr] para poder borrarlo después.

        Imprime un mensaje informativo indicando qué subred se bloqueó.
    ────────────────────────────────────────────────────────────────────────────
    SOLUTION:
    """
    if subnet_cidr in _firewall_handles:
        print(f"[FW] {subnet_cidr} ya está bloqueada.")
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
    Elimina la regla de bloqueo para la subred indicada.

    TO-DO [4]: Implementa esta función.

        Si subnet_cidr está en _firewall_handles:
            Construye el comando:
                "table_delete MyIngress.firewall <handle>"
            Llama a run_cli_command() con ese comando.
            Elimina la entrada de _firewall_handles.
            Imprime un mensaje de desbloqueo.

        Si no está registrada, imprime que ya estaba libre.
    ────────────────────────────────────────────────────────────────────────────
    SOLUTION:
    """
    if subnet_cidr not in _firewall_handles:
        print(f"[FW] {subnet_cidr} no estaba bloqueada.")
        return

    handle = _firewall_handles.pop(subnet_cidr)
    cmd    = f'table_delete MyIngress.firewall {handle}'
    run_cli_command(cmd, thrift_port)
    print(f"[FW] UNBLOCKED {subnet_cidr} (handle {handle})")


def unblock_all(thrift_port: int = DEFAULT_THRIFT_PORT) -> None:
    """Elimina todas las reglas de firewall activas."""
    for subnet in list(_firewall_handles.keys()):
        unblock_subnet(subnet, thrift_port)


# ─────────────────────────────────────────────────────────────────────────────
# Bucle principal del agente RL
# ─────────────────────────────────────────────────────────────────────────────

def execute_action(action: int, thrift_port: int) -> None:
    """
    Ejecuta la acción elegida por el agente sobre la tabla firewall.

    Mapa de acciones:
        0 → Bloquear 10.0.1.0/26  (bloquea h1 Y h2 — acción incorrecta)
        1 → Bloquear 10.0.1.64/26 (bloquea SOLO h2 — acción correcta)
        2 → Desbloquear todo       (acción pasiva)
        3 → Bloquear ambas subredes (agresivo)
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
    Bucle principal del agente Q-Learning.

    En cada episodio:
      1. Lee los registros synReg y synAckRstReg del switch.
      2. Calcula el estado actual (ratio discretizado).
      3. Si no hay ataque (state == 0), espera al siguiente ciclo.
      4. Elige una acción (epsilon-greedy).
      5. Ejecuta la acción (instala/elimina regla firewall).
      6. Espera un intervalo y re-lee los registros (observa el efecto).
      7. Calcula el reward.
      8. Actualiza la Q-table.
      9. Decae epsilon.
     10. Resetea los contadores para el siguiente ciclo.
    """
    agent = QTable(learning_rate=0.2, discount=0.9, epsilon=0.4)

    print(f"\n[RL] Agente iniciado. Puerto thrift: {thrift_port}")
    print(f"[RL] Episodios: {episodes}, Intervalo: {interval}s\n")

    for episode in range(episodes):
        # ── Paso 1-2: leer estado actual ──────────────────────────────────────
        syn_before    = read_register('MyIngress.synReg',       1, thrift_port)
        synack_before = read_register('MyIngress.synAckRstReg', 1, thrift_port)
        state         = ratio_to_state(syn_before, synack_before)

        print(f"[E{episode:03d}] SYN={syn_before} SYN-ACK={synack_before} "
              f"state={state} ε={agent.epsilon:.2f}")

        # ── Paso 3: si no hay ataque, esperar ─────────────────────────────────
        if state == 0:
            print(f"[E{episode:03d}] Sin ataque detectado. Esperando...")
            time.sleep(interval)
            continue

        # ── Paso 4: elegir acción ─────────────────────────────────────────────
        action = agent.choose_action(state)
        print(f"[E{episode:03d}] → Acción {action}: {ACTION_SPACE[action]}")

        # ── Paso 5: ejecutar acción ───────────────────────────────────────────
        execute_action(action, thrift_port)

        # ── Paso 6: observar efecto ───────────────────────────────────────────
        time.sleep(interval)
        reset_registers(thrift_port)
        time.sleep(interval)

        syn_after    = read_register('MyIngress.synReg',       1, thrift_port)
        synack_after = read_register('MyIngress.synAckRstReg', 1, thrift_port)
        next_state   = ratio_to_state(syn_after, synack_after)

        # ── Paso 7: calcular reward ───────────────────────────────────────────
        reward = compute_reward(action, syn_before, syn_after, synack_after)

        print(f"[E{episode:03d}] SYN_after={syn_after} SYN-ACK_after={synack_after} "
              f"next_state={next_state} reward={reward:+.1f}")

        # ── Paso 8: actualizar Q-table ────────────────────────────────────────
        new_q = agent.update(state, action, reward, next_state)
        print(f"[E{episode:03d}] Q({state},{action}) actualizado → {new_q:.4f}")

        # ── Paso 9: decaer epsilon ────────────────────────────────────────────
        agent.decay_epsilon()

        # ── Éxito: mostrar tabla Q si el ataque fue mitigado ──────────────────
        if next_state == 0 and reward > 0:
            print(f"\n[RL] *** Ataque MITIGADO en episodio {episode} ***\n")
            agent.print_table()

        # ── Paso 10: reset para siguiente ciclo ───────────────────────────────
        reset_registers(thrift_port)
        time.sleep(interval)

    print("\n[RL] Entrenamiento finalizado.")
    agent.print_table()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Agente RL para mitigación de SYN Flood en switch P4')
    parser.add_argument('--port',     type=int,   default=DEFAULT_THRIFT_PORT,
                        help='Puerto thrift de s1 (default: 9090)')
    parser.add_argument('--interval', type=float, default=DEFAULT_INTERVAL,
                        help='Segundos entre ciclos del agente (default: 2)')
    parser.add_argument('--episodes', type=int,   default=DEFAULT_EPISODES,
                        help='Número de episodios de entrenamiento (default: 200)')
    args = parser.parse_args()

    try:
        run_rl_agent(args.port, args.interval, args.episodes)
    except KeyboardInterrupt:
        print('\n[RL] Interrumpido por el usuario. Desbloqueando subredes...')
        unblock_all(args.port)


if __name__ == '__main__':
    main()
