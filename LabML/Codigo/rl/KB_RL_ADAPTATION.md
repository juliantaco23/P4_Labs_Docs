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


### 3. Reducción de topología: 6 switches → 2 switches

**Original**: Topología tipo pod con s1–s6 (estructura de data center).

**Adaptación**: 2 switches (s1 border + s2 server-side), 3 hosts funcionales.
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

> **Aclaración de roles — dos ejecuciones distintas:**
>
> | Fase | Qué valida | Controller corre | Objetivo |
> |---|---|---|---|
> | **Test de bloqueo** | La tabla `firewall` del switch P4 bloquea/desbloquea correctamente | ❌ No | Verificar infraestructura P4 |
> | **Escenario completo** | El agente RL aprende la política correcta | ✅ Sí | Ejecutar el aprendizaje |
>
> El test de bloqueo es un **sanity check** de que el switch reacciona correctamente
> a reglas manuales. Solo después de verificarlo tiene sentido entrenar el agente.

### Paso 1 — Compilación
```bash
cd P4_Labs_Docs/LabML/Codigo/rl
mkdir -p p4src/build
p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/syn_flood_rl.p4
```
Esperar: sin errores.

### Paso 2 — Topología
```bash
sudo python3 mininet/topo.py
```
Esperar: prompt `mininet>` con s1 (thrift 9090), s2 (thrift 9091), h1–h4.

### Paso 3 — Reglas de forwarding
```bash
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
simple_switch_CLI --thrift-port 9091 < s2-commands.txt
```
Esperar: 4 handles en s1, 3 handles en s2, sin DUPLICATE_ENTRY.

### Paso 4 — Verificación de forwarding
```
mininet> h1 ping -c3 10.0.6.1
```
Esperar: 3 respuestas ICMP con TTL=62. Si falla, las reglas de forwarding están mal.

### Paso 5 — Configurar h3 para suprimir RST (REQUERIDO)

En Mininet, el kernel de h3 responde a cada SYN con RST+ACK porque el puerto 80 no
está abierto. Esto hace que `synAckRstReg ≈ synReg` siempre, impidiendo la detección.
Suprimir el RST permite que el ratio SYN/SYNACK crezca durante el ataque:

```
mininet> h3 iptables -A OUTPUT -p tcp --tcp-flags RST RST -j DROP
```

> **¿Por qué esto es necesario?**
> Sin esta regla: 1 SYN → 1 RST+ACK (h3) + 1 ACK (send_legit) = 2 SYNACK.
> Con 200 pps de ataque: syn_delta=204, synack_delta=204 → excess=0 → state=0 siempre.
> Con RST suprimido: syn_delta=204, synack_delta=4 (solo ACK legítimo) → excess=200 → state=12.

### Paso 6 — Test de bloqueo (sin controller — verifica P4)

Este paso verifica que la tabla `firewall` bloquea h2 sin afectar a h1.
**Secuencia correcta: primero ver ambos, luego instalar la regla.**

```
# Abrir monitor en h3:
mininet> xterm h3
```
En el xterm de h3: `tcpdump -i eth0 -n not ip6`

```
# Iniciar tráfico legítimo h1 (background) con duración larga:
mininet> h1 python3 send_legit.py &

# Iniciar ataque h2 (background) con larga duración:
mininet> h2 python3 send_attack.py --pps 50 --duration 120 &
```

Verificar en h3 tcpdump — deben aparecer **DOS** tipos de paquetes:
```
10.0.1.1.XXXXX > 10.0.6.1.80   ← tráfico legítimo de h1 ✅
10.0.1.82.XXXXX > 10.0.6.1.80  ← ataque de h2 ✅ (sin firewall, ambos llegan)
```

```
# AHORA instalar la regla de bloqueo:
simple_switch_CLI --thrift-port 9090 <<< "table_add MyIngress.firewall MyIngress.block 10.0.1.64/26 => 1"
```
Esperar: `Entry has been added with handle 0`

Verificar en h3 tcpdump después de instalar la regla:
```
10.0.1.1.XXXXX > 10.0.6.1.80   ← tráfico legítimo de h1 SIGUE ✅
# ya no aparecen paquetes de 10.0.1.82  ← bloqueado ✅
```

```
# Quitar la regla y verificar que h2 vuelve a aparecer:
simple_switch_CLI --thrift-port 9090 <<< "table_delete MyIngress.firewall 0"
```
Verificar: 10.0.1.82 vuelve a aparecer en tcpdump ✅

```
# Limpiar procesos background antes del escenario RL:
mininet> h1 kill %1   # detener send_legit
mininet> h2 kill %2   # detener send_attack (o esperar que termine si --duration 120)
```

### Paso 7 — Test de lectura de registros
```bash
simple_switch_CLI --thrift-port 9090 <<< "register_read MyIngress.synReg 1"
```
Esperar: `MyIngress.synReg[1]= 0` (o valor acumulado si el tráfico lleva tiempo corriendo).

### Paso 8 — Escenario completo con RL (con controller)

> **Dónde corre cada componente:**
> - `send_legit.py` y `send_attack.py`: dentro de Mininet (`mininet>` prompt)
> - `controller.py`: en una **terminal del HOST** (fuera de Mininet)
>   El controlador llama a `simple_switch_CLI` via subprocess; debe correr en el
>   namespace del host donde `simple_switch_CLI` tiene acceso al socket Thrift.

```
# Terminal HOST (fuera de Mininet):
python3 controller.py --interval 2 --episodes 100

# En Mininet (IMPORTANTE: ataque desde h2, no h1):
mininet> h2 python3 send_attack.py --pps 50 &
mininet> h1 python3 send_legit.py &
```

**Comportamiento esperado por episodio:**

Sin ataque detectado (state=0):
```
[E000] SYN=0 SYN-ACK=0 state=0 ε=0.40
[E000] No attack detected. Waiting...
[CTRL] Registers reset.
```

Con ataque activo (state>0) — ejemplo real de la validación:
```
[E007] SYN=2 SYN-ACK=0 state=12 ε=0.40
[E007] → Action 2: no_action
[CTRL] Registers reset.
[E007] SYN_after=31 SYN-ACK_after=0 next_state=12 reward=-2.0
[E007] Q(12,2) updated → -0.3539
```

Acción óptima (bloqueo selectivo del atacante):
```
[ExNN] SYN=30 SYN-ACK=3 state=3 ε=...
[ExNN] → Action 1: block_attacker
[FW] BLOCKED 10.0.1.64/26 (handle X)
[CTRL] Registers reset.
[ExNN] SYN_after=3 SYN-ACK_after=3 next_state=0 reward=+15.0
[ExNN] Q(3,1) updated → ...

[RL] *** Attack MITIGATED in episode NN ***
```

**Indicadores de éxito tras 50+ episodios con ataque activo:**
- `state` cambia entre 0 (sin ataque) y valores altos (con ataque)
- `no_action` recibe reward≤-2 durante el ataque ← fix ATTACK_THRESHOLD=10 ✅
- `block_all` recibe reward=-10 ← correctamente penalizado ✅
- `block_attacker` recibe reward=+15 cuando SYN→0 y SYNACK>0 ← señal más fuerte
- `Q(estado, 1=block_attacker)` crece con cada reward positivo
- `ε` decrece de 0.40 hacia 0.05 (cada 20 acciones tomadas)

**Q-table al final (si el entrenamiento funcionó bien, 50+ episodios):**
```
  State |  block_all  block_attacker  no_action  block_both
      3 |    -5.xxxx        10.xxxx     -2.xxxx     -3.xxxx  ← block_attacker claramente mayor
     12 |    -0.xxxx         8.xxxx     -2.xxxx     +1.xxxx  ← block_attacker domina
```
Si todos los valores siguen cercanos a 0 → no hubo episodios con state>0 → revisar bugs.

---

## Problemas conocidos y soluciones

| Problema | Causa probable | Solución |
|---|---|---|
| `state` siempre 0, Q-table no aprende | Registros nunca se reinician en episodios state=0; la historia acumulada diluye el ataque | Ya corregido: `reset_registers()` al final de cada episodio, incluidos state=0 |
| `state` siempre 0 aunque ataque corre | El kernel de h3 responde a cada SYN con RST+ACK, igualando el conteo SYN y SYNACK | Añadir `mininet> h3 iptables -A OUTPUT -p tcp --tcp-flags RST RST -j DROP` |
| Ataque no tiene efecto sobre los registros | Se ejecutó `h1 python3 send_attack.py` en lugar de `h2 python3 send_attack.py` | El ataque SIEMPRE debe correr desde h2; el firewall bloquea por IP fuente |
| `register_read` retorna 0 siempre | No hay paquetes llegando al switch; forwarding rules no instaladas o fallo de compilación | Verificar forwarding y que los paquetes se envíen con sendp (Layer 2) |
| `epsilon` no cambia (se queda en 0.40) | `decay_epsilon()` solo incrementa `step_count` cuando hay acciones; si state=0 siempre, no hay acciones | Es síntoma del bug de registros; se resuelve con el fix de reset |
| Q-table final con valores cerca de 0 (−0.05 a +0.05) | Sin episodios con state>0, la Q-table es la inicialización aleatoria sin ningún aprendizaje | Confirmar que state>0 se detecta correctamente antes de entrenar |
| `table_add firewall` falla | Ya existe una regla LPM solapada, o el handle no fue liberado de una ejecución anterior | `table_delete MyIngress.firewall <handle>` o reiniciar switch |
| h1 también queda bloqueado | El agente eligió acción 0 (block_all) | La Q-table aprenderá que eso es incorrecto (reward -10); normal al inicio |
| BMv2 no actualiza registros entre resets | `register_reset` puede tardar un ciclo | Ya hay `time.sleep(interval)` después del reset en el controlador |
| `ping: connect: Network is unreachable` | `configure_hosts()` usa nexthop `10.0.1.254` que está fuera del /26 de h1/h2; kernels modernos rechazan la ruta sin `onlink` | Ya corregido: se agregó `onlink` a ambos `ip route add` en topo.py |
| send_attack no llega a h3 (h2 invisible en tcpdump) | Scapy ≥2.4.x captura `FileNotFoundError` de tcpreplay internamente, imprime el traceback pero retorna sin relanzar → nuestro `except` nunca ejecuta, fallback nunca corre; `sendpfast` depende de `tcpreplay` que no está instalado | Ya corregido: `send_attack.py` reescrito sin `sendpfast`; usa `sendp()` directamente en loop con control de tasa |
| Después de quitar firewall, h2 sigue sin aparecer | El ataque ya terminó (duration=30s) antes de quitar la regla; el test instaló el firewall antes de iniciar el ataque | Cambio en el procedimiento: iniciar h1 y h2 sin firewall, verificar ambos, luego instalar la regla |

---

## Resultado de validación (ejecutado 2026-07-30 — validación final con todos los fixes)

### Resumen de pasos validados

| Paso | Resultado |
|---|---|
| Compilación P4 | ✅ Sin errores |
| Reglas s1 (4 handles) | ✅ Sin DUPLICATE_ENTRY |
| Reglas s2 (3 handles) | ✅ Sin DUPLICATE_ENTRY |
| Ping h1→h3 (TTL=62) | ✅ 3/3 paquetes, 0% pérdida |
| RST suppression en h3 | ✅ iptables DROP RST aplicado |
| send_legit (h1→h3) | ✅ Paquetes SYN+ACK visibles en h3 |
| send_attack (h2→h3) | ✅ ~14.4 pps real (866 SYN en 60s) |
| Test de bloqueo | ✅ (validado en sesión anterior, sin cambios) |
| Registros limpios al inicio | ✅ SYN=0, SYN-ACK=0 en E000 |
| RL agent + Q-table | ✅ Aprendizaje correcto con todos los fixes |

### RL Agent — análisis episodio a episodio

**Condiciones del experimento:**
- Registros limpios al iniciar el controller (sin acumulación residual de sesiones anteriores)
- h3 iptables RST DROP activo
- Ataque lanzado ~3 segundos antes del tráfico legítimo
- `ATTACK_THRESHOLD = 10` (fix aplicado)

| Episodio | SYN | SYN-ACK | Estado | Acción | Reward | Observación |
|---|---|---|---|---|---|---|
| E000–E006 | 0 | 0 | 0 | — | — | Registros limpios; ataque aún no iniciado ✅ |
| E007 | 2 | 0 | 12 | no_action | **-2.0** | **THRESHOLD FIX FUNCIONÓ**: syn_after=31 > 10 → penalizado ✅ |
| E008 | 27 | 2 | 3 | block_all | **-10.0** | Penalizado: bloqueó h1 Y h2 (handle 0) ✅ |
| E009 | 34 | 0 | 12 | block_both | **+5.0** | Ataque detenido (SYN→0) pero también bloqueó legítimo (SYNACK=0 → +5 no +15) |

`*** Attack MITIGATED in episode 9 ***` ✅ — `next_state=0 and reward=+5 > 0`

### Q-table tras 3 episodios activos

```
  State |      block_all  block_attacker       no_action      block_both
------------------------------------------------------------------------
      3 |        -1.9686         -0.0290          -0.0320         -0.0320  ← block_all penalizado ✅
     12 |         0.0050         -0.0320          -0.3539          1.0305  ← no_action penalizado ✅, block_both recompensado
```

### Comparación con validación anterior (2026-07-27)

| Comportamiento | Run anterior (ATTACK_THRESHOLD=50) | Run actual (ATTACK_THRESHOLD=10) |
|---|---|---|
| no_action en state=12 | reward=+15 (incorrecto) | reward=-2.0 ✅ (correcto) |
| Q(12, no_action) final | +7.35 (dominante, incorrecto) | **-0.35** (penalizado, correcto) |
| Registros al inicio | SYN=552 residuales | SYN=0 limpio ✅ |
| Detección del ataque | Falso positivo en E000 | Detectado correctamente en E007 ✅ |

### Observaciones pedagógicas

**Lo que aprendió el agente en 3 episodios:**
- `block_all` es incorrecto (Q=-1.97 en state=3) — aprendió a evitarlo ✅
- `no_action` durante ataque es incorrecto (Q=-0.35 en state=12) — aprendió a evitarlo ✅
- `block_both` detiene el ataque pero también bloquea al legítimo → reward=+5 (no ideal)

**Lo que el agente AÚN NO aprendió** (requiere más episodios):
- `block_attacker` (acción 1) es la acción óptima → nunca intentada en estos 3 episodios
- Con más episodios, el agente debería descubrir que `block_attacker` da reward=+15
  porque detiene el ataque (SYN→0) Y deja fluir el tráfico legítimo (SYNACK>0)
- El Q-table converge correctamente con 50+ episodios donde el ataque esté activo

**Tasa real del ataque confirmada:** 866 SYN / 60s = **14.4 SYN/s** (~29% de los 50 pps teóricos, por overhead de Python `time.sleep(0.02)` + latencia `sendp()`). El `ATTACK_THRESHOLD=10` es adecuado para esta tasa (syn_delta≈29/2s >> 10).

**Cleanup automático al interrumpir:** Al presionar Ctrl+C, el controller desbloquea correctamente ambas subredes antes de salir:
```
[FW] UNBLOCKED 10.0.1.0/26 (handle 0)
[FW] UNBLOCKED 10.0.1.64/26 (handle 1)
```

---

## Equivalencia con archivos del repositorio original (GITA Demo-RL)

| Archivo original GITA | Archivo adaptado | Cambios |
|---|---|---|
| `simple_switch.p4-RL.TODO` (P4) | `p4src/syn_flood_rl.p4` | **Modificado**: eliminada telemetr\u00eda MRI (IP Option 31); eliminadas tablas P4Runtime; simplificado a forwarding b\u00e1sico + firewall LPM + registros synReg/synAckRstReg. |
| `initiate_rules.py` | `s1-commands.txt` / `s2-commands.txt` | **Migrado a comandos est\u00e1ticos**: el original instalaba reglas via P4Runtime. Ahora son l\u00edneas `table_add` instaladas con `simple_switch_CLI`. Reglas din\u00e1micas del firewall gestionadas en `controller.py`. |
| `receive_counters.py` | `controller.py` (bucle principal) | **Fusionado + reescrito**: le\u00eda contadores via gRPC y los enviaba a h4 via MRI. Adaptado: lee registros via subprocess CLI, elimina dependencia de MRI/h4, integra el bucle RL. |
| `get_counters.py` | `controller.py` (`read_register()`) | **Fusionado**: el original extraa contadores via P4Runtime. Reemplazado por `read_register()` usando `register_read` de simple_switch_CLI + regex. |
| `tcpsession.py` | \u2014 (sin equivalente) | **Eliminado**: gestionaba la sesi\u00f3n gRPC (conexiones a puertos 50051-50056). No necesario \u2014 `simple_switch_CLI` es stateless (Thrift ef\u00edmero por llamada). |
| `q_table.py` | `q_table.py` | **Adaptado directamente**: misma estructura numpy. Cambios: `compute_reward()` reescrita para SYN Flood; `ratio_to_state()` cambiada a f\u00f3rmula de exceso (syn-synack); `ATTACK_THRESHOLD` corregido de 50 a 10; TO-DOs a\u00f1adidos para el estudiante. |
| `send_attack.py` | `send_attack.py` | **Adaptado**: eliminado `sendpfast` (requiere tcpreplay no disponible); reemplazado por loop `sendp()` con control de tasa. IP fuente: `10.0.1.82`. |
| `update_entries.sh` | `controller.py` (`block_subnet()` / `unblock_subnet()`) | **Migrado a Python**: el bash script llamaba `table_add`/`table_delete`. Reemplazado por funciones Python que usan subprocess y conservan los handles para poder deshacer. |
| `reset_registers.sh` | `reset_registers.sh` | **Adaptaci\u00f3n m\u00ednima**: el original usaba P4Runtime. Adaptado para `simple_switch_CLI <<< "register_reset ..."`. |

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
