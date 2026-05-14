# MRI Exercise — Adaptation Knowledge Base

## Origen
- **Fuente original**: `p4lang/tutorials/exercises/mri`
- **Repositorio**: https://github.com/p4lang/tutorials
- **Destino adaptado**: `P4_Labs_Docs/LabP4_3/Codigo/mri/`
- **Rol en LabP4_3**: Ejercicio guiado (el ejercicio de actividad del estudiante es MySec+extensiones en `Codigo/3/`)

---

## Resumen del Ejercicio

MRI (Multi-Hop Route Inspection) es una versión simplificada de INT (In-Band Network Telemetry). Cada switch que un paquete atraviesa **agrega** su ID y la profundidad de cola (`qdepth`) a un header stack creciente dentro del paquete. En destino, el receptor lee la secuencia completa de switches y sus estados de cola, obteniendo visibilidad del camino recorrido y la congestión en cada punto.

**Conceptos clave del ejercicio**:
1. **IP Options**: MRI usa IPv4 Option type 31 para señalar la presencia de headers MRI
2. **Header stacks**: `switch_t[MAX_HOPS]` — estructura de tamaño variable que crece en cada salto
3. **Parser recursivo**: `parse_swtrace` se llama a sí mismo hasta que `remaining == 0`
4. **Egress processing**: la tabla `swtrace` ejecuta `add_swtrace(swid)` que hace `push_front(1)` al stack
5. **Actualización de longitudes**: cada switch incrementa `ihl += 2`, `totalLen += 8`, `optionLength += 8`

---

## Decisiones de Diseño

### 1. Mantener 3 switches (NO reducir a 2)

**Justificación**: A diferencia de ECN donde s3/h3 eran pedagógicamente marginales, en MRI los 3 switches son **fundamentales**:

| Aspecto | Con 2 switches | Con 3 switches |
|---------|----------------|----------------|
| Entradas MRI por paquete | Siempre 2 (swid=1, swid=2) | **Siempre 2**, pero el par varía según la ruta |
| Rutas posibles | h1→s1→s2→h2 (única) | h1→s1→s2→h2 **y** h1→s1→s3→h3 (rutas distintas) |
| "Route Inspection" | No hay inspección de ruta: solo hay una | El header stack refleja cuál camino tomó el paquete |
| Valor INT | Reducido a "queue inspection" | Completo: **qué switches** + queue per-hop |
| Enlace bottleneck | Observable pero sin contraste | Contraste: qdepth alto en s1→s2, bajo en s1→s3 |

**Aclaración crítica**: con esta topología y estas tablas de ruteo, **ningún paquete individual pasa por los 3 switches a la vez**. Siempre hay exactamente 2 swtraces. Lo que cambia es *qué par de switches* aparece:
- h1→h2: `{swid=1, swid=2}` (ruta s1→s2)
- h1→h3: `{swid=1, swid=3}` (ruta s1→s3)
- h2→h3: `{swid=2, swid=3}` (ruta s2→s3)

Esto es el "Route" en Multi-Hop Route Inspection: el header stack permite saber **qué nodos estuvo en el camino**, no cuántos.

**Impacto en consistencia con Exercise 3**: Exercise 3 (MySec) usa 2 switches porque su mecánica es un protocolo de bounce (h1→s1→s2→s1→h1) que requiere exactamente 2 switches. MRI es forwarding lineal con path recording. Las topologías diferentes están justificadas por objetivos diferentes.

### 2. Migración de P4Runtime/gRPC a simple_switch_CLI

Mismo patrón que ECN (ver KB_ECN_ADAPTATION.md). Resumen:
- `simple_switch_grpc` → `simple_switch`
- `sX-runtime.json` (P4Runtime JSON) → `sN-commands.txt` (CLI commands)
- `topology.json` + `utils/run_exercise.py` → `mininet/topo.py` independiente
- `Makefile` eliminado
- Compilación y ejecución manual

### 3. Nuevo comando: table_set_default

MRI introduce un patrón nuevo respecto a ECN: la tabla `swtrace` en egress NO tiene entradas match (no tiene `key`). En su lugar, usa un **default_action** que asigna el `swid` del switch. 

**Formato P4Runtime (original)**:
```json
{
  "table": "MyEgress.swtrace",
  "default_action": true,
  "action_name": "MyEgress.add_swtrace",
  "action_params": { "swid": 1 }
}
```

**Formato simple_switch_CLI (adaptado)**:
```
table_set_default MyEgress.swtrace MyEgress.add_swtrace 1
```

Este es el primer ejercicio del curso que usa `table_set_default`. Los ejercicios anteriores (1, 2, 2.2, 4, ECN) solo usaban `table_add`.

### 4. Reordenamiento de puertos vs original

**Original (topology.json)**:
- s1: port1=h11, port2=h1, port3=s2, port4=s3
- s2: port1=h22, port2=h2, port3=s1, port4=s3

**Adaptado (topo.py)**:
- s1: port1=h1, port2=h11, port3=s2, port4=s3
- s2: port1=h2, port2=h22, port3=s1, port4=s3

Se reordenaron los hosts para que h1 esté en port1 (no h11) y h2 en port1 (no h22). Los commands.txt reflejan este nuevo mapeo. Esto hace la topología más intuitiva y consistente con ECN donde se usó el mismo criterio.

---

## Archivos: Viejo vs Nuevo

### Archivos ELIMINADOS (infraestructura P4Runtime)
| Archivo | Razón |
|---------|-------|
| `Makefile` | Invocaba `make run` con infraestructura P4Runtime |
| `s1-runtime.json` | Reglas P4Runtime JSON → reemplazado por `s1-commands.txt` |
| `s2-runtime.json` | Reglas P4Runtime JSON → reemplazado por `s2-commands.txt` |
| `s3-runtime.json` | Reglas P4Runtime JSON → reemplazado por `s3-commands.txt` |
| `topology.json` | Descriptor de topología → reemplazado por `mininet/topo.py` |

### Archivos CREADOS
| Archivo | Descripción |
|---------|-------------|
| `mininet/topo.py` | Topología Mininet con 3 switches, 5 hosts, enlace bottleneck 0.5 Mbps, rutas/ARP L3 |
| `mininet/p4_mininet.py` | Clase `P4Switch` para `simple_switch` (copia estándar del curso) |
| `s1-commands.txt` | `table_set_default swtrace swid=1` + 4 reglas LPM |
| `s2-commands.txt` | `table_set_default swtrace swid=2` + 4 reglas LPM |
| `s3-commands.txt` | `table_set_default swtrace swid=3` + 3 reglas LPM |

### Archivos MOVIDOS
| Origen | Destino | Razón |
|--------|---------|-------|
| `mri.p4` (raíz) | `p4src/mri.p4` | Consistencia con estructura `p4src/` del curso |

### Archivos SIN MODIFICAR
| Archivo | Nota |
|---------|------|
| `p4src/mri.p4` | Skeleton con TODOs. v1model puro, compatible con simple_switch |
| `solution/mri.p4` | Solución de referencia. v1model puro |
| `send.py` | Define `IPOption_MRI` y `SwitchTrace` en Scapy para crear paquetes con IP Option 31 |
| `receive.py` | Define los mismos dissectors para parsear los headers MRI recibidos |
| `README.md` | Documentación original p4lang (referencia) |
| `setup.png` | Diagrama topología original |

---

## Por qué send.py y receive.py son NECESARIOS en MRI

MRI usa **IP Options** (IPv4 Option type 31) con un header stack personalizado (`mri_t` + `switch_t[]`). Esto no existe en ningún protocolo real:

1. **send.py es obligatorio**: Define la clase Scapy `IPOption_MRI` con `count=0` y `swtraces=[]`. Sin este paquete especialmente construido:
   - Los paquetes estándar (`ping`, `iperf`, `hping3`) no tienen IP Options → `hdr.ipv4.ihl == 5` → el parser transita directamente a `accept` → `hdr.mri` nunca es válido → la lógica de egreso `if (hdr.mri.isValid())` nunca ejecuta → **ningún switch agrega su trace**

2. **receive.py es obligatorio**: Define los mismos dissectors Scapy (`SwitchTrace`, `IPOption_MRI`) para poder **parsear e imprimir** los headers MRI que los switches agregaron. Sin estos dissectors:
   - `pkt.show2()` mostraría los bytes de IP Options como datos raw (hex dump)
   - El estudiante no podría ver `swid=1, qdepth=42` sino algo como `\x00\x00\x00\x01\x00\x00\x00\x2a`

**Comparación con otros ejercicios del curso**:

| Ejercicio | ¿Necesita scripts Scapy? | Por qué |
|-----------|--------------------------|---------|
| Ex-1 (L2) | No | `ping` genera frames Ethernet estándar |
| Ex-2 (ARP) | No | `ping` dispara ARP |
| Ex-2.2 (TCP) | No | `iperf`/`wget` generan TCP estándar |
| Ex-4 (VLAN) | No | `ping` genera IPv4 estándar; tags son transparentes |
| ECN | **Sí** | `send.py` envía con `tos=1` (ECN-capable); `receive.py` muestra TOS por paquete |
| Exercise-3 (MySec) | **Sí** | IP proto 169 no existe en ninguna herramienta; `send_mysec.py` crea el paquete |
| MRI | **Sí** | IP Option 31 (MRI) no existe; `send.py`/`receive.py` crean y parsean el header stack |

---

## Topología Detallada

### Asignación de Puertos
```
s1: port1 = h1,  port2 = h11,  port3 = s2 (bottleneck), port4 = s3
s2: port1 = h2,  port2 = h22,  port3 = s1 (bottleneck), port4 = s3
s3: port1 = h3,  port2 = s1,   port3 = s2
```

### Direcciones
| Host | IP | MAC | Gateway | Gateway MAC |
|------|----|-----|---------|-------------|
| h1 | 10.0.1.1/24 | 08:00:00:00:01:01 | 10.0.1.254 | 08:00:00:00:01:00 |
| h11 | 10.0.1.11/24 | 08:00:00:00:01:11 | 10.0.1.254 | 08:00:00:00:01:00 |
| h2 | 10.0.2.2/24 | 08:00:00:00:02:02 | 10.0.2.254 | 08:00:00:00:02:00 |
| h22 | 10.0.2.22/24 | 08:00:00:00:02:22 | 10.0.2.254 | 08:00:00:00:02:00 |
| h3 | 10.0.3.3/24 | 08:00:00:00:03:03 | 10.0.3.254 | 08:00:00:00:03:00 |

### Reglas de Forwarding

**s1-commands.txt**:
```
table_set_default MyEgress.swtrace MyEgress.add_swtrace 1
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.1.1/32 => 08:00:00:00:01:01 1
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.1.11/32 => 08:00:00:00:01:11 2
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.2.0/24 => 08:00:00:00:02:00 3
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.3.0/24 => 08:00:00:00:03:00 4
```

**s2-commands.txt**:
```
table_set_default MyEgress.swtrace MyEgress.add_swtrace 2
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.2.2/32 => 08:00:00:00:02:02 1
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.2.22/32 => 08:00:00:00:02:22 2
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.1.0/24 => 08:00:00:00:01:00 3
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.3.0/24 => 08:00:00:00:03:00 4
```

**s3-commands.txt**:
```
table_set_default MyEgress.swtrace MyEgress.add_swtrace 3
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.3.3/32 => 08:00:00:00:03:03 1
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.1.0/24 => 08:00:00:00:01:00 2
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.2.0/24 => 08:00:00:00:02:00 3
```

### Conversión de table_set_default

**Formato P4Runtime**:
```json
{
  "table": "MyEgress.swtrace",
  "default_action": true,
  "action_name": "MyEgress.add_swtrace",
  "action_params": { "swid": 1 }
}
```

**Formato simple_switch_CLI**:
```
table_set_default MyEgress.swtrace MyEgress.add_swtrace 1
```

Patrón: `table_set_default <table> <action> <param1> <param2> ...`

---

## Compatibilidad P4: simple_switch_grpc vs simple_switch

El código P4 de MRI es **100% compatible con simple_switch** porque:
1. Usa `V1Switch()` (v1model)
2. Las operaciones usadas (`push_front`, `setValid`, header stacks, `verify()`) son primitivas estándar de v1model
3. `standard_metadata.deq_qdepth` es un campo estándar
4. No usa P4Runtime externs, annotations, ni digest
5. La tabla `swtrace` sin key + default_action funciona idénticamente en ambos targets

---

## Diferencias entre MRI y ECN (ambos ejercicios de p4lang)

### Propósito conceptual distinto

| Aspecto | ECN | MRI |
|---------|-----|-----|
| ¿Qué señala? | "Hubo congestión en algún punto" | "En cada switch X, la cola tenía Y celdas" |
| ¿Dónde queda el registro? | En 2 bits del campo TOS existente | En un header stack que crece por salto |
| ¿Se puede saber QUÉ switch congestionó? | **No** — solo hay 1 bit de marca global | **Sí** — cada switch escribe su propio swid |
| ¿Se acumula por switch? | **No** — un switch posterior puede sobrescribir | **Sí** — push_front garantiza que todos los registros coexisten |
| Tamaño del paquete | **No cambia** — flip de bits en campo existente | **Crece** — +8 bytes por switch atravesado |
| Modelo de telemetría | Pasivo (marca un campo existente) | Activo (inyecta datos nuevos en el paquete) |

### Qué es nuevo en MRI que no existía en ECN

| Concepto P4 nuevo | En ECN | En MRI |
|-------------------|--------|--------|
| **Header stacks** `switch_t[MAX_HOPS]` | No | ✓ arrays de headers |
| **`push_front`** | No | ✓ agregar al stack en runtime |
| **`setValid()`** obligatorio | No | ✓ P4_16 spec tras push_front |
| **Parser recursivo** (`parse_swtrace` loop) | No | ✓ estado que se llama a sí mismo |
| **IP Options** (`ihl > 5` para detectar) | No | ✓ campo `ihl` como señal de parser |
| **`table_set_default`** con parámetros | No | ✓ default action sin clave de match |
| **Múltiples campos de longitud coordinados** | No | ✓ `ihl` + `totalLen` + `optionLength` sincronizados |
| Egress marking | ✓ (ecn field) | ✓ (push_front al stack) |
| `deq_qdepth` | ✓ (como umbral) | ✓ (como dato a registrar) |

En ECN, `deq_qdepth` se usa para **tomar una decisión** (marcar o no marcar). En MRI, se usa como **dato a incluir en el paquete** — telemetría real, no solo señalización.

| Aspecto | ECN | MRI |
|---------|-----|-----|
| Topología adaptada | 2 switches | 3 switches |
| Switches en original | 3 (s3 redundante) | 3 (s3 esencial) |
| Mecanismo INT | Bit marking (ecn field) | Header stacking (push_front) |
| Headers custom | Ninguno (solo split TOS) | ipv4_option_t, mri_t, switch_t[9] |
| Tabla egress | Sin tabla (inline check) | `swtrace` con table_set_default |
| Parser | Simple (Ethernet→IPv4) | Recursivo (parse_swtrace loop) |
| send.py necesidad | Semi-necesario (tos=1) | Obligatorio (IP Option 31) |
| receive.py necesidad | Semi-necesario (grep tos) | Obligatorio (parse MRI headers) |

---

## Secuencia de Validación Completa

### Limpieza obligatoria antes de iniciar
```bash
sudo pkill -9 simple_switch ; sudo mn --clean ; rm -f /tmp/bmv2-*-notifications.ipc
```

### Paso 1: Compilar
```bash
cd LabP4_3/Codigo/mri
mkdir -p p4src/build
p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/mri.p4
```
Salida esperada: ningún error. El archivo `p4src/build/bmv2.json` debe existir.

### Paso 2: Iniciar la topología
```bash
sudo python3 mininet/topo.py
```
Esperar que aparezca `mininet>`.

### Paso 3: Instalar reglas (en otra terminal)
```bash
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
simple_switch_CLI --thrift-port 9091 < s2-commands.txt
simple_switch_CLI --thrift-port 9092 < s3-commands.txt
```
Cada comando imprime `"Done"` por cada regla instalada.

### Paso 4: Verificar conectividad básica (sin MRI)
Desde la CLI de Mininet:
```
mininet> pingall
```
**Resultado esperado** (sin MRI — solo ping estándar sin IP Option):
- h1 ↔ h11: **FAIL** (misma subred, sin ARP → LPM falla en broadcast)
- h2 ↔ h22: **FAIL** (mismo motivo)
- Todos los pares cross-switch (h1↔h2, h1↔h22, h1↔h3, h11↔h2, h11↔h22, h11↔h3, h2↔h3, h22↔h3): **OK**
- Porcentaje drop: `20%` (4 de 20 pares totales — con 5 hosts son 5×4=20 pings dirigidos; 4 fallan: h1↔h11 y h2↔h22 misma subred, sin reglas ARP ni broadcast en el switch P4)

> **Nota**: los paquetes `ping` sin IP Option nunca activan el egress MRI (ihl==5 → accept directamente). Para ver MRI hay que usar `send.py`.

### Paso 5: Prueba MRI con send.py

**Terminal h2** (receptor):
```
mininet> h2 ./receive.py &
```

**Terminal h1** (emisor — 3 paquetes con 1 seg de pausa):
```
mininet> h1 ./send.py 10.0.2.2 "P4 is cool" 3
```

**Salida esperada en h2** (para cada paquete recibido):
```
got a packet
###[ Ethernet ]###
  ...
###[ IP ]###
  version   = 4
  ihl       = 10       # 6 (inicial: 5 base + 1 por IP Option vacía) + 2 (s1) + 2 (s2) = 10
  ...
  options   \
   |###[ MRI ]###
   |  copy_flag= 0
   |  optclass = 0
   |  option   = 31
   |  length   = 20    # 4 (ipv4_option header) + 2 (mri count) + 2*8B (2 swtraces)
   |  count    = 2
   |  swtraces \
   |   |###[ SwitchTrace ]###
   |   |  swid     = 2        # s2 agrega primero en egress (push_front)
   |   |  qdepth   = 0        # cola vacía
   |   |###[ SwitchTrace ]###
   |   |  swid     = 1        # s1 agrega (push_front mueve s1 al frente)
   |   |  qdepth   = 0
```

> **Observación clave — orden LIFO**: los swtraces están en **orden inverso al camino físico**. `push_front` agrega al índice 0 desplazando los existentes:
> 1. s1 egress: push_front → stack = `[swid=1]`
> 2. s2 egress: push_front → stack = `[swid=2, swid=1]` ← swid=2 queda primero
>
> En la salida siempre aparece primero el **último switch en el camino** (destino) y último el switch de origen. Esto es correcto por diseño: la pila refleja el camino en reversa.

### Paso 6: Prueba de congestión con iperf (MRI + qdepth)

**Terminal h22** (servidor UDP):
```
mininet> h22 iperf -s -u &
```

**Terminal h11** (cliente UDP — genera congestión en el enlace s1↔s2):
```
mininet> h11 iperf -c 10.0.2.22 -t 15 -u &
```

**Terminal h2** (receptor MRI):
```
mininet> h2 ./receive.py &
```

**Terminal h1** (emisor MRI — 30 paquetes):
```
mininet> h1 ./send.py 10.0.2.2 "P4 is cool" 30
```

**Salida esperada (validada)**: los primeros paquetes tienen `qdepth=0`. Cuando el tráfico iperf satura el bottleneck s1→s2 (0.5 Mbps), el `qdepth` de swid=1 sube bruscamente y luego baja cuando iperf termina:

| Paquete # | swid=1 qdepth | swid=2 qdepth | Estado |
|-----------|---------------|---------------|--------|
| 1–3 | 0 | 1 | Iperf recién iniciando |
| 4 | **61** | 1 | Cola saturada: 61×80 = 4.880 bytes |
| 5 | 56 | 1 | Cola drenando |
| 6 | 51 | 0 | |
| 7 | 45 | 1 | |
| 8 | 42 | 0 | |
| 9–30 | **0** | 0 | Iperf terminó (15s), cola vacía |

- `qdepth` se mide en **celdas de 80 bytes** (bmv2). qdepth=61 → 4.880 bytes en cola.
- swid=**1** tiene qdepth alto porque la congestión está en el **puerto3 de salida de s1** (hacia s2, bottleneck).
- swid=**2** tiene qdepth ≈0 porque el link s2→h2 no tiene límite de ancho de banda → sin congestión.
- El salto 0→61 es brusco porque iperf UDP por defecto envía a **1 Mbps** (el doble del bottleneck de 0.5 Mbps), llenando la cola casi instantáneamente.
- swid **no cambia** entre paquetes: es un identificador estático configurado en el control plane.

**h22 iperf servidor**: muestra solo el banner de inicio durante la ejecución. El resumen final (datagramas recibidos, % packet loss) aparece al terminar los 15s. Dado que iperf envía a 1 Mbps sobre un link de 0.5 Mbps, se espera ~50% packet loss en h22.

**h11 iperf cliente — verificación matemática**:
```
0.0-15.0 sec  1.88 MBytes  1.05 Mbits/sec  — Sent 1338 datagrams
```
- 1.338 datagramas × 1.470 bytes = 1.966.860 bytes ≈ **1,88 MBytes** ✓
- 1.966.860 × 8 / 15s = **1.048.992 bps ≈ 1,05 Mbits/sec** ✓
- 1,05 Mbps > 0,5 Mbps (bottleneck) → confirma saturación → explica el qdepth elevado en s1

### Paso 7: Demostrar "Route Inspection" — envío hacia h3

Este paso es **el que justifica los 3 switches**. Hasta aquí solo hemos visto la ruta s1→s2. Ahora enviamos hacia h3 para mostrar que el header stack registra una ruta diferente: s1→s3.

**Terminal h3** (receptor — abrir xterm si es posible):
```
mininet> h3 ./receive.py &
```

**Terminal h1** (emisor — 3 paquetes):
```
mininet> h1 ./send.py 10.0.3.3 "P4 route" 3
```

**Salida esperada en h3**:
```
got a packet
###[ IP ]###
     ihl       = 10
     len       = 58
     ttl       = 62
     \options   \
      |###[ MRI ]###
      |  length    = 20
      |  count     = 2
      |  \swtraces  \
      |   |###[ SwitchTrace ]###
      |   |  swid      = 3        # ← s3, NO s2
      |   |  qdepth    = 0
      |   |###[ SwitchTrace ]###
      |   |  swid      = 1
      |   |  qdepth    = 0
```

**Comparación de rutas** — este es el valor pedagógico del tercer switch:

| Destino | Ruta física | swtraces observados |
|---------|-------------|---------------------|
| h2 (10.0.2.2) | h1 → s1 → s2 → h2 | `{swid=2, swid=1}` |
| h3 (10.0.3.3) | h1 → s1 → s3 → h3 | `{swid=3, swid=1}` |

El mismo código P4, las mismas reglas de default action en los switches — pero **el header stack resultante es diferente según la ruta tomada**. Esto es imposible de demostrar con solo 2 switches (hay una única ruta posible).

### setValid() después de push_front — CRÍTICO

En bmv2 >= 1.11 (conforme a P4_16 spec), los elementos empujados por `push_front` quedan **inválidos** hasta que se llama explícitamente `setValid()`. Sin esta llamada, los campos `swid` y `qdepth` no se escriben y el paquete puede comportarse de forma inesperada.

```p4
hdr.swtraces.push_front(1);
hdr.swtraces[0].setValid();   // ← OBLIGATORIO en bmv2 >= 1.11
hdr.swtraces[0].swid = swid;
```

En bmv2 < 1.11 (comportamiento P4_14 heredado), `push_front` marcaba automáticamente el elemento como válido. El entorno del laboratorio usa bmv2 estándar de Ubuntu 20.04 donde esta llamada es necesaria.

### send.py — argumentos y comportamiento
```
./send.py <dst_ip> "<message>" <count>
```
- `count`: número de paquetes a enviar
- Hay un `sleep(1)` entre paquetes → los paquetes llegan 1 por segundo a h2
- El paquete inicial tiene `count=0, swtraces=[]` → la opción MRI existe pero sin trazas
- Cada switch incrementa `count` y agrega un swtrace

### Campos de capas estándar modificados por MRI

**IPv4** — modificados en `add_swtrace` (egress, por cada switch):
- `ihl` += 2 por switch (8 bytes = 2 words de 32 bits)
- `totalLen` += 8 por switch
- `hdrChecksum` — recalculado en `MyComputeChecksum` (porque `ihl` y `totalLen` cambian en egress)
- `optionLength` += 8 por switch (campo dentro de `ipv4_option_t`)

**IPv4** — modificados en `ipv4_forward` (ingress, forwarding estándar):
- `ttl` -= 1 por switch (decremento estándar L3)

**Ethernet** — modificados en `ipv4_forward` (ingress):
- `srcAddr` ← valor anterior de `dstAddr`
- `dstAddr` ← MAC del próximo salto

> Nota para el redactor: explorar la interacción entre `ihl`/`totalLen` y el recálculo del checksum: ambos campos se modifican en el pipeline de **egress** pero `MyComputeChecksum` corre después, por lo que el checksum siempre refleja los valores finales. El campo `optionLength` es redundante con `totalLen` pero necesario para que el receptor parsee correctamente el bloque de IP Options.

### Valores concretos observados en validación
| Campo | Inicial (send.py) | En h2 (2 switches) | Cálculo |
|-------|-------------------|--------------------|---------|
| `ihl` | 6 | 10 | 6 + 2×2 |
| `len` (`totalLen`) | 42 | 58 | 42 + 2×8 |
| `length` (`optionLength`) | 4 | 20 | 4 + 2×8 |
| `count` | 0 | 2 | 0 + 2 |
| `ttl` | 64 | 62 | 64 − 2 |
| `swtraces` | [] | [swid=2 qdepth=0, swid=1 qdepth=0] | push_front orden inverso |

---

## Notas para el LaTeX (LabP4_3.tex)

- Este es el **ejercicio guiado** de LabP4_3
- Los TODOs del estudiante en `mri.p4` son:
  1. **parse_ipv4_option**: Extraer `ipv4_option`, transitar a `parse_mri` si option==31
  2. **parse_mri**: Extraer `mri`, setear `remaining`, transitar a `parse_swtrace`
  3. **parse_swtrace**: Extraer `swtraces.next`, decrementar `remaining`, loop
  4. **add_swtrace (egress)**: Incrementar count, push_front(1), setValid(), setear swid+qdepth, actualizar ihl/totalLen/optionLength
  5. **egress apply**: Condicionar swtrace.apply() a `hdr.mri.isValid()`
  6. **deparser**: Emitir ipv4_option, mri, swtraces
- Compilación: `p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/mri.p4`
- 3 switches → 3 archivos de comandos + thrift ports 9090/9091/9092
- Instrucciones de color: verde=bash, azul=Python, rojo=Mininet, naranja=P4
