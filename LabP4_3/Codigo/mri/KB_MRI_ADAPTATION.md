a# MRI Exercise — Adaptation Knowledge Base

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
| Entradas MRI | Siempre 2 (swid=1, swid=2) | 2 ó 3 según ruta |
| Rutas posibles | h1→s1→s2→h2 (única) | h1→s1→s2→h2 o h1→s1→s3→...  |
| "Route Inspection" | No hay inspección de ruta: solo hay una | Demuestra que el **camino real** queda registrado |
| Valor INT | Reducido a "queue inspection" | Completo: path + queue per-hop |
| Enlace bottleneck | Observable pero sin contraste | Contraste: qdepth alto en s1→s2, bajo en s1→s3 |

MRI se llama "Multi-Hop **Route** Inspection" — con 2 switches hay un único camino, no hay "ruta" que inspeccionar. El tercer switch permite al estudiante verificar que el header stack refleja fielmente el camino tomado.

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
