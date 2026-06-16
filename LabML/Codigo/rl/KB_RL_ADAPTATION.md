# Knowledge Base: Reinforcement Learning + P4 — Adaptación y Validación

## Origen y referencias

| Item | Valor |
|---|---|
| Fuente original | `ONOSP4-tutorial/Demo-RL/` (GITA, Universidad de Antioquia) |
| Paper base | Zheng, C., Rienecker, B. & Zilberman, N. (2023). *QCMP: Load Balancing via In-Network Reinforcement Learning*. ACM SIGCOMM FIRA Workshop. |
| DOI | https://dl.acm.org/doi/abs/10.1145/3607504.3609291 |
| Destino adaptado | `P4_Labs_Docs/LabML/Codigo/rl/` |
| Rol en LabML | Ejercicio de actividad del estudiante (completa Q-table y controller) |

---

## Resumen conceptual

El ejercicio combina **Q-Learning** con un switch P4 para mitigar un ataque SYN Flood.

**Funcionamiento end-to-end**:
1. El switch P4 (s1) cuenta paquetes SYN y SYN-ACK/ACK en registros.
2. El agente RL (controller.py) lee periódicamente esos registros via `simple_switch_CLI`.
3. Calcula el ratio SYN/SYN-ACK → estado discretizado (0-12).
4. Elige una acción (bloquear subred A, bloquear subred B, o no hacer nada).
5. Instala/elimina una regla LPM en la tabla `firewall` del switch via CLI.
6. Observa el nuevo estado y calcula el reward.
7. Actualiza la Q-table con la ecuación de Bellman.

**Por qué funciona como RL**:
- El ambiente es el switch P4 (caja negra para el agente).
- El estado es observable via registros.
- La transición de estado es estocástica (el ataque puede variar).
- El agente aprende la política óptima por ensayo y error.

---

## Decisiones de adaptación respecto al Demo-RL original

### 1. Eliminación de P4Runtime / gRPC

**Original**: `initiate_rules.py` y `receive_counters.py` usan `p4runtime_lib` (gRPC/Protobuf).
Requieren `simple_switch_grpc` y conexiones a puertos 50051-50056.

**Adaptación**: Todo el control se hace via `simple_switch_CLI` (subprocess en Python).
- Lectura de registros: `register_read MyIngress.synReg 1`
- Instalación de reglas: `table_add MyIngress.firewall MyIngress.block 10.0.1.64/26 => 1`
- Eliminación de reglas: `table_delete MyIngress.firewall <handle>`
- Reset de registros: `register_reset MyIngress.synReg`

**Justificación pedagógica**: El estudiante ya conoce `simple_switch_CLI` de los ejercicios
anteriores. Usar la misma herramienta mantiene la coherencia del curso y baja la barrera
de entrada al concepto de control dinámico del plano de datos.

### 2. Eliminación de telemetría MRI

**Original**: El switch embebe contadores SYN/SYN-ACK en headers MRI (IP Option 31) para
transportarlos a un host de monitoreo (h4), que los reenvía al controlador.

**Adaptación**: El controlador lee los registros directamente del switch via Thrift/CLI.
Esto elimina:
- La complejidad de headers MRI en el P4
- El script `get_counters.py` en h4
- La dependencia de Scapy con IPOption_MRI

**El host h4** se mantiene en la topología como punto de monitoreo opcional (puede usar
tcpdump para observar el tráfico) pero ya no es necesario para el flujo principal del RL.

### 3. Reducción de topología: 6 switches → 2 switches

**Original**: Topología tipo pod con s1–s6 (estructura de data center).

**Adaptación**: 2 switches (s1 border + s2 server-side), 3 hosts funcionales + h4 moniteo.
Razón: la topología de 6 switches es para load balancing (el contexto del paper QCMP),
pero en este ejercicio el objetivo es mitigación de ataques, donde 2 switches son suficientes
para ilustrar el concepto sin añadir complejidad de configuración innecesaria.

### 4. Agente RL: `receive_counters.py` + `q_table.py` (original) → `controller.py` + `q_table.py` (nuevo)

El agente original distribuía la lógica en varios archivos con dependencias de P4Runtime.
En la adaptación, toda la lógica del agente está en 2 archivos claros:
- `controller.py`: interacción con el switch (leer/escribir), bucle RL principal.
- `q_table.py`: Q-table, epsilon-greedy, Bellman, reward, discretización de estado.

---

## TO-DO del estudiante

### En `q_table.py`:

| TO-DO | Función | Descripción |
|---|---|---|
| [A] | `choose_action()` | Política epsilon-greedy: con prob. ε → aleatorio, con 1-ε → argmax(Q[s]) |
| [B] | `update()` | Ecuación de Bellman: Q(s,a) ← Q(s,a) + α[r + γ·max Q(s',·) - Q(s,a)] |
| [C] | `decay_epsilon()` | Esquema de decaimiento: reducir ε en 0.05 cada 20 pasos, mínimo 0.05 |
| [D] | `compute_reward()` | Función de reward: +15 éxito, -10 bloqueo incorrecto, -2 sin efecto |
| [E] | `ratio_to_state()` | Discretizar ratio SYN/SYN-ACK en un entero de 0 a 12 |

### En `controller.py`:

| TO-DO | Función | Descripción |
|---|---|---|
| [1] | `run_cli_command()` | subprocess.run() con stdin=command → retorna stdout |
| [2] | `read_register()` | Construir comando + regex para extraer entero de la salida |
| [3] | `block_subnet()` | `table_add firewall block <cidr> => 1` + guardar handle |
| [4] | `unblock_subnet()` | `table_delete firewall <handle>` + limpiar diccionario |

---

## Pasos de validación

### Compilación
```bash
cd P4_Labs_Docs/LabML/Codigo/rl
mkdir -p p4src/build
p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/syn_flood_rl.p4
# Esperar: sin errores de compilación.
```

### Topología
```bash
sudo python3 mininet/topo.py
# Esperar: prompt mininet> con 2 switches y 4 hosts.
```

### Reglas de forwarding
```bash
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
simple_switch_CLI --thrift-port 9091 < s2-commands.txt
# Esperar: 4 + 3 confirmaciones table_add.
```

### Conectividad inicial (sin firewall)
```
mininet> h1 ping -c2 10.0.6.1    # debe funcionar
mininet> h2 ping -c2 10.0.6.1    # debe funcionar (aún sin reglas RL)
```

### Test de lectura de registros
```bash
simple_switch_CLI --thrift-port 9090 <<< "register_read MyIngress.synReg 1"
# Esperar: MyIngress.synReg[1]= 0  (cero al inicio)
```

### Test de instalación de regla firewall manual
```bash
simple_switch_CLI --thrift-port 9090 <<< "table_add MyIngress.firewall MyIngress.block 10.0.1.64/26 => 1"
# Esperar: "table_add ... ok (handle 0)" o similar
```

### Test de bloqueo
```
mininet> h2 ping -c2 10.0.6.1    # debe FALLAR (bloqueado por firewall)
mininet> h1 ping -c2 10.0.6.1    # debe FUNCIONAR (subred distinta)
```

### Eliminar regla de prueba
```bash
simple_switch_CLI --thrift-port 9090 <<< "table_delete MyIngress.firewall 0"
```

### Escenario completo con RL
```
# Terminal 1 (Mininet):
sudo python3 mininet/topo.py

# Terminal 2 (reglas):
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
simple_switch_CLI --thrift-port 9091 < s2-commands.txt

# Terminal 3 (agente RL):
python3 controller.py --interval 2 --episodes 100

# En Mininet:
mininet> h1 python3 send_legit.py &
mininet> h2 python3 send_attack.py &
```

**Indicador de éxito**: El agente imprime `*** Ataque MITIGADO ***` cuando detecta
que el estado vuelve a 0 con reward positivo. La Q-table final debe mostrar valores
altos para acción 1 (block_attacker) en estados ≥ 1.

---

## Problemas conocidos y soluciones

| Problema | Causa probable | Solución |
|---|---|---|
| `register_read` retorna 0 siempre | No hay paquetes llegando al switch | Verificar forwarding rules y que send_attack.py corre en h2 |
| `table_add firewall` falla | La tabla tiene `default_action = NoAction()` — puede requerir que la entrada sea única | Verificar que no hay otra regla LPM que solape |
| Agente siempre elige acción aleatoria | epsilon = 0.4 al inicio — normal. Esperar ≥ 20 episodios para el decaimiento | Es el comportamiento esperado al inicio |
| h1 también queda bloqueado | El agente eligió acción 0 (block_all) | La Q-table aprenderá que eso es incorrecto (reward -10) |
| BMv2 no actualiza registros entre resets | `register_reset` puede tardar un ciclo | Añadir `time.sleep(0.5)` después del reset |

---

## Lo que el estudiante NO debe ver en la entrega

Los archivos `q_table.py` y `controller.py` contienen las soluciones completas
con los TO-DO visibles. Para la versión del estudiante, entregar solo el esqueleto
con los TO-DO pero sin el bloque `SOLUTION:`.

**Nota de seguridad para futuras versiones**: El ejercicio de bloqueo de subredes
tiene implicaciones reales en redes de producción. El material está diseñado
para entornos de laboratorio aislados (Mininet). No ejecutar en redes físicas
sin autorización explícita.

---

## Dependencias de Python (instalar en la VM)

```bash
pip3 install numpy scapy
# numpy: para la Q-table (arrays)
# scapy: para send_attack.py y send_legit.py
```

No se requieren instalaciones adicionales: `subprocess` y `re` son módulos
estándar de Python 3.

---

## Referencias verificadas

```bibtex
@inproceedings{zheng2023qcmp,
  title={{QCMP: Load Balancing via In-Network Reinforcement Learning}},
  author={Zheng, Changgang and Rienecker, Benjamin and Zilberman, Noa},
  booktitle={Proceedings of the 2nd ACM SIGCOMM Workshop on Future of Internet
             Routing \& Addressing (FIRA '23)},
  pages={35--40},
  year={2023},
  doi={10.1145/3607504.3609291}
}
```
