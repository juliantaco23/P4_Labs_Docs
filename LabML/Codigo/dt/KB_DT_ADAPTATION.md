# Knowledge Base: Decision Trees in P4 — Adaptación y Validación

## Origen y referencias

| Item | Valor |
|---|---|
| Fuente original | `ONOSP4-tutorial/DecisionTrees2/` (GITA, Universidad de Antioquia) |
| Paper base | Xiong, J. & Zilberman, N. (2021). *Toward Smarter, Adaptive Forwarding in P4 Programmable Networks*. |
| Repositorio GITA | https://github.com/grupogita/ONOSP4-tutorial |
| Destino adaptado | `P4_Labs_Docs/LabML/Codigo/dt/` |
| Rol en LabML | Ejercicio guiado (el estudiante completa los TO-DO del código P4) |

---

## Resumen conceptual

Un Árbol de Decisión (DT) clasifica muestras comparando secuencialmente los valores
de sus *features* contra umbrales fijos. La idea clave del ejercicio es que las
**match/action tables con tipo de matching `range`** en P4 son equivalentes
computacionalmente a los nodos de decisión del árbol.

Arquitectura del clasificador en el switch:

```
Paquete entrante
    │
    ▼
[feature1_exact]  hdr.ipv4.protocol → action_select1 (bucket: 1, 2 o 3)
    │
    ▼
[feature2_exact]  hdr.tcp.srcPort   → action_select2 (bucket: 1, 2 o 3)
    │
    ▼
[feature3_exact]  hdr.tcp.dstPort   → action_select3 (bucket: 1 o 2)
    │
    ▼
[ipv4_exact]      (select1, select2, select3) → ipv4_forward(dstMac, port)
```

Cada feature table asigna un entero ("bucket") al valor del campo. La tabla final
`ipv4_exact` combina los tres buckets para decidir el puerto de salida.

---

## Decisiones de adaptación

### 1. Eliminación de ONOS / P4Runtime

**Original**: El ejercicio usa ONOS como controlador SDN y P4Runtime/gRPC para instalar
reglas. Requiere una aplicación Java compilada con Maven.

**Adaptación**: Se reemplaza completamente por `simple_switch` + `simple_switch_CLI`.
- Las reglas se instalan desde `s1-commands.txt` via stdin.
- No se necesita ONOS, Stratum, ni Java.
- La topología se define en `mininet/topo.py` (estilo p4lang/tutorials).

### 2. P4 program: `simple_switch.p4-DT.TODO` → `dt_switch.p4`

El archivo original (`simple_switch.p4-DT.TODO`) tiene dos problemas para el enfoque sin ONOS:
1. Incluye cabeceras `cpu_in_header_t` / `cpu_out_header_t` para packet-in/packet-out (ONOS).
2. Usa una tabla `acl_table` con ternary matching (solo necesaria para ONOS).

**Adaptado**: Se eliminan los headers de CPU y la tabla ACL. El programa resultante
(`dt_switch.p4`) es más limpio y más fácil de entender pedagógicamente.

Los TO-DO del archivo original se preservan como comentarios en el código completo para
mantener visibilidad de los puntos de acción del estudiante.

### 3. Topología: `topology.json` + `s1-runtime.json` → `mininet/topo.py`

**Original**: 1 switch, 4 hosts en `pod_topo/topology.json`. Las reglas de runtime
en `s1-runtime.json` (formato P4Runtime JSON).

**Adaptado**: `mininet/topo.py` sigue el mismo patrón que los ejercicios previos (MRI, ECN).
- 1 switch (s1, thrift port 9090), 4 hosts (h1–h4).
- MACs predecibles: `08:00:00:00:01:0X`.
- IPs: `10.0.1.X/26` (todos en la misma /26).

### 4. Reglas `rules-dt.sh.EXAMPLE` → `s1-commands.txt`

El archivo original usa here-strings de bash (`<<< "comando"`). Se convierte al
formato stdin de simple_switch_CLI (una línea por comando, sin prefijos de shell).

**Nota sobre range tables en simple_switch_CLI**:
```
# Formato:
table_add <tabla> <acción> <min>-><max> => <param> <priority>

# Ejemplo:
table_add MyIngress.feature2_exact MyIngress.set_actionselect2 0->1023 => 1 10
```
La prioridad (último campo) es obligatoria para tables con `range` matching.
Mayor número = mayor prioridad. Usar 10 como valor estándar.

---

## TO-DO del estudiante (puntos de acción en dt_switch.p4)

| TO-DO | Línea aprox. | Descripción |
|---|---|---|
| [1] | ~35 | Añadir campo `bit<16> etherType` en `ethernet_t` |
| [2] | ~46 | Definir todos los campos del encabezado IPv4 (RFC 791) |
| [3] | ~63 | Definir todos los campos del encabezado TCP (RFC 793) |
| [4] | ~116 | Añadir transición `TYPE_IPV4: parse_ipv4` en `parse_ethernet` |
| [5] | ~126 | Añadir transición `IP_PROTO_TCP: parse_tcp` en `parse_ipv4` |
| [6] | ~170 | Implementar body de `set_actionselect3`: asignar `meta.action_select3 = featurevalue3` |
| [7] | ~205 | Definir key de `feature3_exact`: `hdr.tcp.dstPort : range` |
| [8] | ~235 | Implementar bloque `if (hdr.tcp.isValid())` con apply de features 2 y 3; else asignar selects = 1 |

---

## Dataset para la actividad del estudiante

Los árboles pre-entrenados del repositorio original están en:
- `ONOSP4-tutorial/DecisionTrees2/L3/` — árboles de profundidad 3
- `ONOSP4-tutorial/DecisionTrees2/L4/` — árboles de profundidad 4

**Dataset de origen**: tráfico IoT (referencia [48] del paper Xiong & Zilberman).
Las features extraídas son: `IP_proto`, `TCP_srcPort`, `TCP_dstPort`.

**No se requiere descargar nada adicional** — los archivos L3/L4 contienen las reglas
del árbol en formato texto directamente. El estudiante solo necesita traducirlas al
formato `table_add` de simple_switch_CLI.

---

## Pasos de validación

### Compilación
```bash
cd P4_Labs_Docs/LabML/Codigo/dt
mkdir -p p4src/build
p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/dt_switch.p4
# Esperar: sin errores. Si hay errores de "empty header", revisar TO-DO [2]/[3].
```

### Arranque de topología
```bash
sudo python3 mininet/topo.py
# Esperar: prompt "mininet>" sin errores de BMv2.
```

### Instalación de reglas
```bash
# En segunda terminal:
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
# Esperar: 10 líneas "table_add ... handle X" (sin errores).
```

### Verificación de clasificación
```
mininet> xterm h2 h3 h4
```
- En h2: `tcpdump -i eth0 -n`
- En h3: `tcpdump -i eth0 -n`
- En h4: `tcpdump -i eth0 -n`

```
mininet> h1 python3 send_packets.py
```

**Resultados esperados**:
| Escenario | Puerto src | Puerto dst | Host receptor |
|---|---|---|---|
| ICMP | — | — | h2 (Clase A, non-TCP) |
| TCP sport=80, dport=443 | well-known | well-known | h3 (Clase B) |
| TCP sport=55000, dport=80 | ephemeral | well-known | h3 (Clase B) |
| TCP sport=60000, dport=8080 | ephemeral | alto | h4 (Clase C) |
| TCP random | random | random | h3 o h4 según dstPort |

### Verificación de contadores
```bash
simple_switch_CLI --thrift-port 9090 <<< "counter_read feature1_table_counter 0"
simple_switch_CLI --thrift-port 9090 <<< "counter_read ipv4_exact_table_counter 0"
```

---

## Problemas conocidos y soluciones

| Problema | Causa probable | Solución |
|---|---|---|
| `p4c` error: "header has no fields" | TO-DO [2] o [3] no implementados | Añadir campos a `ipv4_t` y `tcp_t` |
| Ningún paquete llega a h2/h3/h4 | Reglas no instaladas o error de compilación | Verificar `s1-commands.txt` y recompilar |
| `table_add` falla con "priority" error | Falta el campo de prioridad en range tables | Añadir un entero al final de cada `table_add` |
| TCPdump no captura en el host receptor | Feature tables no matchean | Revisar rangos en `s1-commands.txt` |
| BMv2 muere inmediatamente | JSON inválido | Recompilar con `p4c-bm2-ss` |

---

## Lo que el estudiante NO debe ver

El archivo `p4src/dt_switch.p4` contiene **la solución completa** con los TO-DO
visibles como comentarios. Para la versión del estudiante, se debería entregar
únicamente el código con los TO-DO sin las líneas de `SOLUTION:`.

Para generar la versión de estudiante (TO-DO only):
```bash
grep -v "SOLUTION:" p4src/dt_switch.p4 | sed 's/^     \* \─.*$//' > student/dt_switch.p4
```
(O simplemente eliminar manualmente el bloque entre `SOLUTION:` y la siguiente línea de código.)

---

## Referencia bibliográfica verificada

```bibtex
@inproceedings{xiong2019toward,
  title={Toward Smarter, Adaptive Forwarding in Software-Defined Networks:
         A Decision Tree Approach},
  author={Xiong, Zhaoqi and Zilberman, Noa},
  booktitle={Proc. ACM SOSR},
  year={2019}
}
```
Paper completo disponible: https://dl.acm.org/doi/10.1145/3314148.3314351
