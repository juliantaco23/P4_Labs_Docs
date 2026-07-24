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
# Esperar: 4 confirmaciones table_add para s1, 3 para s2 (sin DUPLICATE_ENTRY).
# IMPORTANTE: s1-commands.txt y s2-commands.txt no deben tener líneas en blanco
# entre comandos — simple_switch_CLI repite el último comando en cada línea vacía.
```

### Verificación de forwarding (sin firewall)

> **No usar `ping`**: el switch P4 descarta los paquetes ARP (sin tabla ARP),
> y h1/h3 están en subredes distintas (/26 vs /24) sin gateway configurado.
> Usar sendp/tcpdump en su lugar.

```
mininet> xterm h3
# En h3:
tcpdump -i eth0 -n not ip6

# En Mininet:
mininet> h1 python3 send_legit.py &
```
Esperar en h3: paquetes `10.0.1.1.XXXXX > 10.0.6.1.80` llegando ~2/s (SYN + ACK).
Confirma que h1→h3 funciona con las reglas de forwarding activas.

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
# Lanzar ataque desde h2 (en background)
mininet> h2 python3 send_attack.py --pps 50 --duration 20 &

# En h3 (xterm): debería NO ver paquetes de 10.0.1.82
mininet> h1 python3 send_legit.py &
# En h3: los paquetes de h1 (10.0.1.1) siguen llegando (subred diferente)
```
Esperar: h3 ve paquetes de `10.0.1.1` pero ninguno de `10.0.1.82` ✅

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
| `DUPLICATE_ENTRY` al instalar reglas | Líneas en blanco en s1-commands.txt/s2-commands.txt | Ya corregido: los archivos no tienen líneas vacías entre comandos |
| `Invalid Syntax` al cargar comandos | Caracteres Unicode en comentarios (`─`) | Ya corregido: comentarios usan solo ASCII |
| `ping h3` no funciona desde h1 | Switch descarta ARP; subredes distintas sin gateway | Usar `send_legit.py` + tcpdump para verificar conectividad (no ping) |

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

## Pipeline del sistema RL (separación ML ↔ P4)

A diferencia del ejercicio DT (donde el ML ocurría completamente offline), en RL hay
**aprendizaje activo durante la ejecución**. Los tres componentes interactúan en un
bucle cerrado continuo.

### Los tres componentes y sus roles

```
┌─────────────────────────────────────────────────────────────────┐
│  SWITCH (P4 — syn_flood_rl.p4)                                  │
│                                                                 │
│  Plano de datos:                                                │
│    synReg[1]       ← cuenta paquetes SYN entrantes             │
│    synAckRstReg[1] ← cuenta paquetes SYN-ACK/ACK/RST          │
│    firewall (LPM)  ← instalada/modificada por el agente        │
│    ip_forward (exact) ← reglas estáticas de routing            │
│                                                                 │
│  Por cada paquete TCP:                                          │
│    si syn==1 → synReg++                                         │
│    si ack==1 o synack==1 → synAckRstReg++                      │
│    si firewall.match → toBlock=1 → drop                        │
└──────────────────┬──────────────────────────────────────────────┘
                   │  register_read (subprocess CLI)
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  CONTROLLER (Python — controller.py)                            │
│                                                                 │
│  Bucle cada <interval> segundos:                                │
│    1. Leer synReg y synAckRstReg                                │
│    2. Calcular estado s = ratio_to_state(syn, synack)           │
│    3. Si estado == 0 → no hay ataque, continuar                 │
│    4. action = q_table.choose_action(s)                         │
│    5. Ejecutar acción (table_add / table_delete firewall)       │
│    6. Esperar, resetear registros, re-leer                      │
│    7. reward = compute_reward(action, syn_before, syn_after...) │
│    8. q_table.update(s, action, reward, s')                     │
│    9. q_table.decay_epsilon()                                   │
└──────────────────┬──────────────────────────────────────────────┘
                   │  actualiza Q-table en memoria
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  Q-TABLE (Python — q_table.py)                                  │
│                                                                 │
│  Matriz numpy: 13 estados × 4 acciones                          │
│  Inicializada con valores aleatorios pequeños [−0.05, +0.05]   │
│  Actualizada con ecuación de Bellman por cada episodio          │
│                                                                 │
│  Hiperparámetros: α=0.2, γ=0.9, ε=0.4 (decae 0.05 c/20 pasos) │
└─────────────────────────────────────────────────────────────────┘
```

### Formulación MDP (Markov Decision Process)

El problema se formaliza como un MDP de horizonte finito:

| Componente MDP | Implementación |
|----------------|----------------|
| **Estado** s | `ratio_to_state(synReg, synAckRstReg)` → entero [0, 12] |
| **Acción** a | {0=block_all, 1=block_attacker, 2=no_action, 3=block_both} |
| **Transición** T(s, a, s') | Determinada por el efecto de la regla firewall en el tráfico real — estocástica (el ataque puede variar) |
| **Reward** R(s, a, s') | +15 si ataque detenido con legítimo circulando; +5 parcial; -2 sin efecto; -10 si bloqueó tráfico legítimo |
| **Política** π | ε-greedy sobre la Q-table |
| **Objetivo** | Maximizar reward acumulado descontado: $\sum_t \gamma^t r_t$ |

### Discretización del estado

El estado continuo (ratio SYN/SYN-ACK) se convierte a un entero:

```python
ratio = syn_count / synack_count
state = int(min(ratio, 12))
```

- Estado 0: ratio < 1 → tráfico normal
- Estado 1-11: ratio creciente → ataque moderado a severo
- Estado 12: ratio > 12 o synack=0 → ataque masivo (ningún handshake completado)

Esta discretización es necesaria porque Q-Learning clásico usa una tabla (no una red neuronal) — requiere espacio de estados finito y manejable.

### Ciclo de un episodio

1. **Observar**: leer registros del switch vía `register_read` (Thrift CLI subprocess)
2. **Discretizar**: `ratio_to_state(syn, synack)` → estado actual s
3. **Decidir**: `choose_action(s)` → acción a (ε-greedy)
4. **Actuar**: `table_add` o `table_delete` en la tabla `firewall` del switch
5. **Esperar**: `time.sleep(interval)` → el tráfico responde al cambio
6. **Resetear**: `register_reset` → acumular solo el efecto de la acción
7. **Observar de nuevo**: leer registros nuevos → estado siguiente s'
8. **Recompensar**: `compute_reward(action, syn_before, syn_after, synack_after)`
9. **Aprender**: `update(s, a, r, s')` → actualizar Q(s, a) con Bellman
10. **Explorar menos**: `decay_epsilon()` → ε decrece con el tiempo

### No hay "entrenamiento offline" — todo es online

A diferencia del DT:
- La Q-table **empieza con valores aleatorios** (no hay modelo pre-entrenado)
- El agente **aprende mientras la red está siendo atacada**
- Cada episodio modifica la Q-table
- Después de suficientes episodios, Q(s=1..12, a=1) converge a valores altos (acción correcta: bloquear solo al atacante)
- No hay un dataset de training — el "dataset" es el tráfico real observado

---

## Base teórica necesaria

### 1. Q-Learning y la ecuación de Bellman

Q-Learning es un algoritmo de RL **model-free** y **off-policy**. Aprende la función de valor acción Q(s, a) — la recompensa esperada total si se toma la acción a en el estado s y se sigue la política óptima después.

**Ecuación de Bellman (actualización)**:

$$Q(s, a) \leftarrow Q(s, a) + \alpha \left[ r + \gamma \cdot \max_{a'} Q(s', a') - Q(s, a) \right]$$

Donde:
- $\alpha$ = learning rate (0.2): cuánto peso dar al nuevo aprendizaje vs. el anterior
- $\gamma$ = discount factor (0.9): cuánto importan los rewards futuros vs. los inmediatos
- $r$ = reward inmediato recibido
- $\max_{a'} Q(s', a')$ = el mejor Q del siguiente estado (Bootstrap)

### 2. Política ε-greedy

Resuelve el dilema **exploración vs. explotación**:
- Con probabilidad ε → acción aleatoria (exploración: descubrir si hay mejores acciones)
- Con probabilidad 1-ε → `argmax Q(s, ·)` (explotación: usar el conocimiento actual)

ε empieza alto (0.4 = 40% aleatorio) y decae con el tiempo → el agente explora al principio y explota cuando ya aprendió.

### 3. SYN Flood como problema de RL

El ataque SYN Flood explota el three-way handshake TCP:
- El atacante envía miles de SYN sin completar el handshake (no envía ACK)
- El servidor reserva recursos (half-open connections) por cada SYN
- Sin SYN-ACK correspondiente, el ratio SYN/SYN-ACK crece → estado del agente aumenta

El switch P4 puede **contar** paquetes SYN y SYN-ACK en registros. Esta observación pasiva (sin interceptar el tráfico) es el mecanismo de telemetría del agente.

### 4. Registers en P4 como mecanismo de observación

Los registros P4 (`register<T>(size) regName`) son arrays de memoria estática en el switch que el pipeline puede leer/escribir. En este ejercicio:
- Son **escritos** por el pipeline P4 en tiempo de ejecución (por cada paquete TCP)
- Son **leídos** por el controlador Python via `simple_switch_CLI` (Thrift) — fuera del datapath
- Son el puente entre el plano de datos (velocidad de línea) y el plano de control (inteligencia ML)

### 5. Firewall dinámico con LPM

La tabla `firewall` usa LPM (Longest Prefix Match) sobre `srcAddr`. Esto permite bloquear subredes completas con una sola regla:
- `table_add firewall block 10.0.1.64/26 => 1` → bloquea IPs 10.0.1.64 a 10.0.1.127
- `table_delete firewall <handle>` → elimina la regla → desbloquea
- El handle es el identificador asignado por bmv2 al insertar la regla — hay que conservarlo para poder eliminar después

La separación entre h1 (10.0.1.0/26) y h2 (10.0.1.64/26) en subredes distintas es **deliberada** — es lo que hace que el problema sea resoluble: el agente puede bloquear selectivamente al atacante sin afectar al usuario legítimo.

---

## Aporte de RL + P4 vs. enfoques anteriores

### Comparación con DT y enfoques previos

| Aspecto | Labs P4 previos (MRI/ECN/MySec) | DT en P4 | RL + P4 (este lab) |
|---------|----------------------------------|---------|-------------------|
| Tipo de inteligencia | Ninguna — reglas fijas | Supervisada offline | Aprendizaje por refuerzo online |
| ¿Aprende durante la ejecución? | No | No | **Sí** |
| Modelo pre-entrenado necesario | No | Sí | No — empieza desde cero |
| Fuente de conocimiento | El diseñador | Dataset histórico etiquetado | Interacción con el entorno |
| Plano de datos como sensor | No (solo forwarding) | No | **Sí** — registers como telemetría |
| Plano de control dinámico | No (reglas fijas) | No (reglas fijas post-instalación) | **Sí** — reglas cambian por episodio |
| Adaptación a condiciones no vistas | No | Limitada (árbol fijo) | **Sí** — el agente ajusta su Q-table |
| Latencia de decisión | Nanosegundos (datapath) | Nanosegundos (datapath) | Segundos (loop control) + ns (acción) |

### Qué aporta concretamente

1. **Bucle cerrado plano de datos ↔ control**: por primera vez en los labs, el switch no es solo un forwarder — es también un **sensor** (registers) que retroalimenta al agente. El plano de datos observa, el plano de control decide, el plano de datos ejecuta la decisión.

2. **Mitigación autónoma sin reglas predefinidas**: un firewall tradicional requiere que el administrador defina explícitamente qué IPs bloquear. El agente RL descubre por sí solo que `10.0.1.64/26` es la subred correcta a bloquear — basándose solo en el feedback de los registros.

3. **Tolerancia a la incertidumbre**: el entorno es estocástico (el atacante puede variar la tasa de envío). El agente aprende una política robusta que funciona aunque el ratio SYN/SYN-ACK no sea exactamente el mismo cada vez.

4. **Concepto de reward shaping**: el diseño de la función de reward es un problema no trivial. El ejercicio muestra que:
   - Reward mal diseñado → agente aprende comportamiento subóptimo
   - La penalización de acción 0 (block_all=-10) es **hardcoded** como garantía de no bloquear tráfico legítimo, independientemente del estado

5. **Online learning vs. offline learning**: la distinción pedagógica clave entre DT (frozen model) y RL (living model). En producción, el RL es apropiado cuando el entorno cambia y no se dispone de datos etiquetados históricos suficientes.

---

## Notas para el LaTeX (LabML.tex)

- El ejercicio RL es la **actividad del estudiante** del LabML (DT es el ejercicio guiado).
- Los 5 TODOs de `q_table.py` y 4 de `controller.py` están pensados para que el estudiante entienda los mecanismos de Q-Learning antes de ver el sistema completo funcionando.
- La secuencia pedagógica recomendada:
  1. Completar `q_table.py` (lógica RL pura — sin P4)
  2. Completar `controller.py` (interfaz P4 — sin ML)
  3. Integrar y validar con el ataque real
- La función de reward es intencionalemente discutible — hay varias formas válidas de diseñarla. Puede usarse como pregunta de reflexión en el lab.
- El P4 (`syn_flood_rl.p4`) **no tiene TODOs** — está completo. El reto es Python.
- El paper base es QCMP (Zheng et al., 2023, ACM SIGCOMM FIRA) — aborda load balancing con RL, pero la adaptación cambia el problema a mitigación de SYN Flood para mayor claridad pedagógica.
- Instrucciones de color: verde=bash, azul=Python, rojo=Mininet, naranja=P4.
- **Diagrama recomendado**: el bucle de control (switch → registers → controller → q_table → firewall rules → switch) debe ilustrarse con un diagrama de ciclo en el LaTeX.


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
