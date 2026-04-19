 # ECN Exercise — Adaptation Knowledge Base

## Origen
- **Fuente original**: `p4lang/tutorials/exercises/ecn`
- **Repositorio**: https://github.com/p4lang/tutorials
- **Destino adaptado**: `P4_Labs_Docs/LabP4_2/Codigo/ecn/`
- **Rol en LabP4_2**: Ejercicio guiado (el ejercicio de actividad del estudiante es VLAN+DSCP en `Codigo/4/`)

---

## Resumen del Ejercicio

ECN (Explicit Congestion Notification) permite a los switches señalizar congestión sin descartar paquetes. Cuando un host soporta ECN, envía paquetes con `ipv4.ecn = 1` o `2` (ECN-Capable Transport). Si la profundidad de la cola en un switch supera un umbral (`ECN_THRESHOLD = 10`), el switch marca `ipv4.ecn = 3` (Congestion Experienced). El receptor puede informar al emisor para reducir la tasa de envío.

**Concepto clave del ejercicio**: El estudiante debe modificar el header IPv4 para separar el campo TOS (8 bits) en diffserv (6 bits) + ecn (2 bits), y programar la lógica de egreso que compara `standard_metadata.enq_qdepth` con el umbral.

---

## Decisiones de Diseño

### 1. Reducción de 3 switches a 2 switches

**Original (p4lang)**:
```
  h11 ─┐              ┌─ h22
       s1 ═══(bw)═══ s2
  h1  ─┘  \        /  └─ h2
            s3 ── h3
```
3 switches en triángulo, 5 hosts. s3/h3 proporcionan una ruta alternativa no congestionada.

**Adaptado**:
```
  h1  (10.0.1.1)  ─┐                ┌─ h2  (10.0.2.2)
                     s1 ═══════════ s2
  h11 (10.0.1.11) ─┘  0.5 Mbps      └─ h22 (10.0.2.22)
```
2 switches, 4 hosts.

**Justificación**: El concepto fundamental de ECN (cola congestionada → marcado de bits) solo requiere UN enlace cuello de botella compartido por múltiples flujos. s3/h3 solo servían para demostrar que una ruta alternativa NO marca ECN, lo cual es pedagógicamente marginal y obvio. Con 2 switches:
- Se mantiene la misma situación-problema: h1→h2 (baja tasa, UDP+ECN) y h11→h22 (alta tasa, iperf) comparten el enlace s1-s2 de 0.5 Mbps
- Se reduce la complejidad de configuración (2 switches en vez de 3)
- Se mantiene consistencia con el ejercicio de VLAN (Exercise-4) que también usa 2 switches
- Los estudiantes reutilizan el mismo modelo mental de la topología

### 2. Migración de P4Runtime/gRPC a simple_switch_CLI

**Infraestructura original (p4lang)**:
- `simple_switch_grpc` como target BMv2
- `sX-runtime.json` con formato P4Runtime para instalar reglas (table entries con match/action en JSON)
- `topology.json` como descriptor de topología leído por un script Python genérico (`utils/run_exercise.py`)
- `Makefile` que invoca `make run` para compilar + levantar Mininet + instalar reglas automáticamente
- Dependencias: gRPC, protobuf, P4Runtime client library

**Infraestructura adaptada (curso)**:
- `simple_switch` como target BMv2 (sin gRPC)
- `sN-commands.txt` con comandos de `simple_switch_CLI` en formato `table_add`
- `mininet/topo.py` como script Python independiente con clase de topología Mininet
- `mininet/p4_mininet.py` con clase `P4Switch` que arranca `simple_switch` directamente
- Compilación manual: `p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/ecn.p4`
- Instalación manual: `simple_switch_CLI --thrift-port 909X < sN-commands.txt`
- Sin Makefile, sin scripts de automatización
- Dependencias mínimas: p4c, bmv2, mininet (solo paquetes estándar de la VM p4lang)

### 3. Enrutamiento L3 con reescritura de MACs

Este ejercicio introduce un modelo de forwarding diferente a los ejercicios anteriores del curso:
- **Ejercicios 1-4**: Forwarding L2 basado en MAC destino (tablas `exact` sobre `dst_addr`)
- **ECN**: Forwarding L3 basado en IPv4 LPM (tabla `lpm` sobre `hdr.ipv4.dstAddr`) con reescritura de MACs

La acción `ipv4_forward` reescribe las direcciones MAC en cada salto:
```p4
action ipv4_forward(macAddr_t dstAddr, egressSpec_t port) {
    standard_metadata.egress_spec = port;
    hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;  // MAC anterior → src
    hdr.ethernet.dstAddr = dstAddr;                // MAC siguiente salto → dst
    hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
}
```

Esto requiere configuración especial en los hosts (no basta con `net.staticArp()`):
- Cada host tiene un gateway virtual con MAC estática
- Se configuran rutas default y entradas ARP en `topo.py::configure_hosts()`

---

## Archivos: Viejo vs Nuevo

### Archivos ELIMINADOS (infraestructura P4Runtime)
| Archivo | Razón |
|---------|-------|
| `Makefile` | Invocaba `make run` con infraestructura P4Runtime. Reemplazado por compilación/ejecución manual |
| `s1-runtime.json` | Reglas P4Runtime JSON. Reemplazado por `s1-commands.txt` |
| `s2-runtime.json` | Reglas P4Runtime JSON. Reemplazado por `s2-commands.txt` |
| `s3-runtime.json` | Switch s3 eliminado (topología reducida a 2 switches) |
| `topology.json` | Descriptor de topología para `utils/run_exercise.py`. Reemplazado por `mininet/topo.py` |

### Archivos CREADOS
| Archivo | Descripción |
|---------|-------------|
| `mininet/topo.py` | Topología Mininet con 2 switches, 4 hosts, enlace bottleneck 0.5 Mbps. Configura rutas/ARP L3 en hosts |
| `mininet/p4_mininet.py` | Clase `P4Switch` para `simple_switch` (idéntica a la usada en otros ejercicios) |
| `s1-commands.txt` | 3 reglas LPM: h1/32→port1, h11/32→port2, 10.0.2.0/24→port3 |
| `s2-commands.txt` | 3 reglas LPM: h2/32→port1, h22/32→port2, 10.0.1.0/24→port3 |

### Archivos MOVIDOS
| Origen | Destino | Razón |
|--------|---------|-------|
| `ecn.p4` (raíz) | `p4src/ecn.p4` | Consistencia con estructura `p4src/` del curso |

### Archivos SIN MODIFICAR
| Archivo | Nota |
|---------|------|
| `p4src/ecn.p4` | Skeleton P4 con TODOs. Código v1model puro, compatible con simple_switch sin cambios |
| `solution/ecn.p4` | Solución de referencia. También v1model puro, sin cambios necesarios |
| `send.py` | Envía paquetes UDP con `tos=1` (ECN=01) via Scapy. Funciona con cualquier topología |
| `receive.py` | Captura paquetes y muestra `tos`. Sin dependencia de infraestructura |
| `README.md` | Documentación original p4lang (referencia) |
| `setup.png` | Diagrama de topología original (referencia visual, topología adaptada difiere) |

---

## Topología Detallada

### Asignación de Puertos
```
s1: port1 = h1,  port2 = h11,  port3 = s2
s2: port1 = h2,  port2 = h22,  port3 = s1
```

### Direcciones
| Host | IP | MAC | Subred | Gateway | Gateway MAC |
|------|----|-----|--------|---------|-------------|
| h1 | 10.0.1.1/24 | 08:00:00:00:01:01 | 10.0.1.0/24 | 10.0.1.254 | 08:00:00:00:01:00 |
| h11 | 10.0.1.11/24 | 08:00:00:00:01:11 | 10.0.1.0/24 | 10.0.1.254 | 08:00:00:00:01:00 |
| h2 | 10.0.2.2/24 | 08:00:00:00:02:02 | 10.0.2.0/24 | 10.0.2.254 | 08:00:00:00:02:00 |
| h22 | 10.0.2.22/24 | 08:00:00:00:02:22 | 10.0.2.0/24 | 10.0.2.254 | 08:00:00:00:02:00 |

### Reglas de Forwarding (simple_switch_CLI)

**s1-commands.txt**:
```
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.1.1/32 => 08:00:00:00:01:01 1
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.1.11/32 => 08:00:00:00:01:11 2
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.2.0/24 => 08:00:00:00:02:00 3
```

**s2-commands.txt**:
```
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.2.2/32 => 08:00:00:00:02:02 1
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.2.22/32 => 08:00:00:00:02:22 2
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.1.0/24 => 08:00:00:00:01:00 3
```

Lógica: Cada switch tiene reglas /32 para hosts locales (entrega directa) y una regla /24 para reenviar tráfico a la otra subred a través del enlace trunk (port 3).

### Configuración de Hosts (en topo.py)
```bash
# Hosts en s1
route add default gw 10.0.1.254 dev eth0
arp -i eth0 -s 10.0.1.254 08:00:00:00:01:00

# Hosts en s2
route add default gw 10.0.2.254 dev eth0
arp -i eth0 -s 10.0.2.254 08:00:00:00:02:00
```

El gateway virtual (10.0.X.254) no existe como tal; es simplemente una IP que los hosts usan para el ARP. La MAC del gateway (08:00:00:00:0X:00) aparece como dstAddr en los paquetes hacia el switch, y el P4 la reescribe en cada salto.

---

## Flujo de Congestión ECN

1. **h2** ejecuta `./receive.py` → escucha UDP:4321
2. **h22** ejecuta `iperf -s -u` → escucha iperf UDP
3. **h1** ejecuta `./send.py 10.0.2.2 "P4 is cool" 30` → envía 1 pkt/seg con `tos=1` (ECN=01)
4. **h11** ejecuta `iperf -c 10.0.2.22 -t 15 -u` → inunda el enlace s1-s2
5. El tráfico iperf llena la cola en el puerto de egreso de s1 (port3 → s2)
6. Cuando `enq_qdepth >= ECN_THRESHOLD (10)`, el pipeline de egreso de s1 marca `ecn = 3`
7. **h2** observa que `tos` cambia de `0x1` (sin congestión) a `0x3` (congestión detectada)
8. Cuando iperf termina, la cola se vacía y `tos` vuelve a `0x1`

---

## Conversión de Formato: sX-runtime.json → sX-commands.txt

### Formato Original (P4Runtime JSON)
```json
{
  "table": "MyIngress.ipv4_lpm",
  "match": { "hdr.ipv4.dstAddr": ["10.0.1.1", 32] },
  "action_name": "MyIngress.ipv4_forward",
  "action_params": { "dstAddr": "08:00:00:00:01:01", "port": 2 }
}
```

### Formato Adaptado (simple_switch_CLI)
```
table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward 10.0.1.1/32 => 08:00:00:00:01:01 2
```

**Patrón de conversión**:
```
table_add <table> <action> <match_value>/<prefix_len> => <action_param_1> <action_param_2> ...
```

- El nombre de tabla y acción se usan directamente (con prefijo del control block)
- Match LPM: `IP/prefix`
- Match exact: valor directo
- Separador `=>` entre match fields y action params
- Action params en el orden que aparecen en la declaración P4 de la acción

---

## Compatibilidad P4: simple_switch_grpc vs simple_switch

El código P4 de ECN (`ecn.p4` y `solution/ecn.p4`) es **100% compatible con simple_switch** sin modificaciones porque:

1. **Pipeline**: Usa `V1Switch()` (v1model) — soportado por ambos targets
2. **Acciones**: Solo usa `mark_to_drop()`, asignaciones directas, `update_checksum()` — todas son primitivas estándar de v1model
3. **Metadata**: `standard_metadata.enq_qdepth` y `standard_metadata.egress_spec` son campos estándar de v1model
4. **Sin P4Runtime externs**: No usa `@controller_header`, `digest`, `clone_preserving_field_list` con parámetros P4Runtime, ni ningún extern específico de gRPC
5. **Sin annotations P4Runtime**: No tiene `@name`, `@id`, ni otras annotations que solo tengan efecto con P4Runtime

La diferencia entre `simple_switch` y `simple_switch_grpc` es solo el mecanismo de control plane (Thrift CLI vs gRPC). El plano de datos P4 es idéntico.

---

## Notas para el LaTeX (LabP4_2.tex)

- Este es el **ejercicio guiado** de LabP4_2
- Los TODOs del estudiante en `ecn.p4` son:
  1. Separar `bit<8> tos` en `bit<6> diffserv` + `bit<2> ecn` en el header `ipv4_t`
  2. Implementar la lógica de egreso: `if (ecn == 1 || ecn == 2) && (enq_qdepth >= ECN_THRESHOLD) → ecn = 3`
  3. Actualizar el bloque de checksum para usar `diffserv` y `ecn` en vez de `tos`
- La compilación se hace con: `p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/ecn.p4`
- Instrucciones de color: verde=bash, azul=Python, rojo=Mininet, naranja=P4
- Flujo de validación: compilar → levantar topo → instalar reglas CLI → abrir xterms → ejecutar receive/iperf/send → observar cambio de tos
