# Knowledge Base: Decision Trees in P4 — Adaptación y Validación

## Origen y referencias

| Item | Valor |
|---|---|
| Fuente original | `ONOSP4-tutorial/DecisionTrees2/` (GITA, Universidad de Antioquia) |
| Paper base | Xiong, J. & Zilberman, N. (2021). *Toward Smarter, Adaptive Forwarding in P4 Programmable Networks*. |
| Repositorio GITA | https://github.com/grupogita/ONOSP4-tutorial |
| Destino adaptado | `P4_Labs_Docs/LabML/Codigo/dt/` |
| Rol en LabML | Ejercicio 3 — guiado (el estudiante completa los TO-DO del código P4) |

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
[feature1_exact]  hdr.ipv4.protocol → action_select1 (bucket: 1)
    │                                 ▲ en dataset UNSW: solo 1 bucket
    ▼
[feature2_exact]  hdr.tcp.srcPort   → action_select2 (bucket: 1–6)
    │
    ▼
[feature3_exact]  hdr.tcp.dstPort   → action_select3 (bucket: 1–3)
    │
    ▼
[ipv4_exact]      (select1, select2, select3) → ipv4_forward(dstMac, port)
```

Cada feature table asigna un entero ("bucket") al valor del campo. La tabla final
`ipv4_exact` combina los tres buckets para decidir el puerto de salida.

---

## Árbol generado — fuente de verdad del ejercicio

> **Todos los archivos del ejercicio usan los árboles generados por `ML_Pipeline_DT.ipynb`
> entrenado con el dataset real UNSW IoT Traffic Traces.
> Los árboles originales del repositorio GITA NO se usan.**

Los árboles se encuentran en:
- `tree_L3_generado.txt` — árbol L3 (`max_depth=3`), **usado en el ejercicio guiado**
- `tree_L4_generado.txt` — árbol L4 (`max_depth=4`), referencia para ejercicio avanzado

### Árbol L3 — thresholds y reglas

```
ip_proto  = [];                                 ← sin split (dataset es TCP/UDP)
src_port  = [547, 1899, 3071, 49280, 60633];    ← 6 buckets
dst_port  = [67, 1917];                         ← 3 buckets

Reglas (formato get_lineage):
  when src_port<=547  and dst_port<=67             → Class 1 (Sensors)      → h2
  when src_port in (547, 3071] and dst_port<=67    → Class 4 (Others)       → h2
  when src_port<=3071 and dst_port in (67, 1917]   → Class 4 (Others)       → h2
  when src_port<=3071 and dst_port>1917            → Class 4 (Others)       → h2
  when src_port in (3071, 49280] and dst_port<=1917 → Class 3 (Video)       → h3
  when src_port in (3071, 49280] and dst_port>1917  → Class 0 (Smart-Static)→ h4
  when src_port in (49280, 60633]                  → Class 4 (Others)       → h2
  when src_port>60633                              → Class 3 (Video)        → h3
```

### Buckets de features en s1-commands.txt

| Feature | Bucket | Rango | Protocolo típico |
|---|---|---|---|
| ip_proto | 1 | 0–255 | Todos (sin discriminación) |
| src_port | 1 | 0–547 | Puertos bajos / well-known |
| src_port | 2 | 548–1899 | Registered ports bajos |
| src_port | 3 | 1900–3071 | Registered ports medios |
| src_port | 4 | 3072–49280 | Registered/ephemeral medios |
| src_port | 5 | 49281–60633 | Ephemeral altos |
| src_port | 6 | 60634–65535 | Ephemeral más altos |
| dst_port | 1 | 0–67 | Well-known (FTP, SSH, DNS, DHCP) |
| dst_port | 2 | 68–1917 | Registered medios |
| dst_port | 3 | 1918–65535 | Registered altos / ephemeral |

### Mapeo clase → host en la topología

| Clase | IoT Device Type | Host receptor | Puerto | MAC |
|---|---|---|---|---|
| 0 — Smart-Static | Hubs, enchufes inteligentes | h4 | 4 | 08:00:00:00:01:04 |
| 1 — Sensors | Sensores de movimiento, alarmas | h2 | 2 | 08:00:00:00:01:02 |
| 3 — Video | Cámaras IP, Smart TV | h3 | 3 | 08:00:00:00:01:03 |
| 4 — Others | Tráfico no clasificado | h2 | 2 | 08:00:00:00:01:02 |
| non-TCP | ICMP, etc. | h2 | 2 | 08:00:00:00:01:02 |

> **Nota:** La clase 2 (Audio) no aparece en las hojas del árbol L3 porque
> representa solo el ~2.9% del dataset y el algoritmo CART la absorbe en
> la clase mayoritaria (4 — Others) al optimizar la impureza de Gini.

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

**Las reglas en `s1-commands.txt` corresponden al árbol generado por nuestro
propio pipeline ML (`ML_Pipeline_DT.ipynb`), no al árbol del repositorio GITA.**

**Nota sobre range tables en simple_switch_CLI**:
```
# Formato:
table_add <tabla> <acción> <min>-><max> => <param> <priority>

# Ejemplo:
table_add MyIngress.feature2_exact MyIngress.set_actionselect2 3072->49280 => 4 10
```
La prioridad (último campo) es obligatoria para tables con `range` matching.
Mayor número = mayor prioridad. Usar 10 como valor estándar para reglas no solapadas.

### 5. Dataset: original GITA → UNSW IoT Traffic Traces (dataset real)

**Original**: El repositorio GITA usa árboles pre-entrenados cuyos thresholds
provienen de 12 ejecuciones independientes sobre diferentes días del dataset.

**Adaptación**: Se usa el pipeline completo de `ML_Pipeline_DT.ipynb`:
- Dataset: UNSW IoT Traffic Traces (Sivanathan et al., 2018) — 20 días, 21M+ paquetes
- Entrenamiento único (todos los días concatenados, SEED=42)
- Árbol L3: accuracy ~84.3% en test set

**Diferencias observadas vs. árboles GITA:**
- `ip_proto` no genera splits (el dataset real tiene casi exclusivamente TCP y UDP)
- La clase 2 (Audio, ~2.9% del dataset) no aparece en hojas del árbol L3
- 8 reglas de clasificación vs. variación en los 12 árboles GITA

---

## Notebooks del ejercicio y roles

| Notebook | Estudiante recibe | Propósito |
|---|---|---|
| `ML_Pipeline_DT.ipynb` | ✅ Sí | Pipeline completo: carga, entrenamiento, visualización, extracción de reglas en formato get_lineage |
| `Traduction_Functions.ipynb` | ❌ No | Herramienta del docente: convierte la salida de get_lineage a comandos `table_add`. El estudiante debe realizar esta traducción manualmente como parte de la actividad |
| `PCAP_Processing.ipynb` | ❌ No | Solo referencia interna: documenta el procesamiento de PCAPs a CSV con tshark. El estudiante recibe los CSV directamente |

**Tarea del estudiante**: Dado `tree_L3_generado.txt` (salida de `ML_Pipeline_DT.ipynb`),
traducir las reglas al formato `table_add` de `simple_switch_CLI`, implementar los
TO-DO en `dt_switch.p4`, e instalar las reglas resultantes.

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

## Pasos de validación

### Compilación
```bash
cd P4_Labs_Docs/LabML/Codigo/dt
mkdir -p p4src/build
p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/dt_switch.p4
# Esperado: sin errores. Si hay errores de "empty header", revisar TO-DO [2]/[3].
```

### Arranque de topología
```bash
sudo python3 mininet/topo.py
# Esperado: prompt "mininet>" sin errores de BMv2.
```

### Instalación de reglas
```bash
# En segunda terminal:
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
# Esperado: 14 líneas "table_add ... handle X" (sin errores).
# (1 + 6 + 3 + 5 = 15 reglas: 1 proto, 6 srcPort, 3 dstPort, 5 ipv4_exact)
```

### Verificación de clasificación (send_packets.py)

```
mininet> xterm h2 h3 h4
# En cada xterm: tcpdump -i eth0 -n
mininet> h1 python3 send_packets.py
```

**Resultados esperados** (basados en el árbol L3 generado):

| Escenario | sport | dport | Clase predicha | Host receptor |
|---|---|---|---|---|
| 1 | 100 | 50 | Class 1 (Sensors) | h2 |
| 2 | 2000 | 500 | Class 4 (Others) | h2 |
| 3 | 10000 | 100 | Class 3 (Video) | h3 |
| 4 | 10000 | 5000 | Class 0 (Smart-Static) | h4 |
| 5 | 62000 | 80 | Class 3 (Video) | h3 |
| 6 | 55000 | 8080 | Class 4 (Others) | h2 |
| 7 | ICMP (non-TCP) | — | default (sel2=1,sel3=1) | h2 |
| 8 | random | random | mix proporcional | h2/h3/h4 |

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
| `rules-extracted.txt` tiene IPs en vez de MACs | Bug en Traduction_Functions.ipynb | No usar `rules-extracted.txt` directamente; usar `s1-commands.txt` como referencia |

---

## Nota sobre rules-extracted.txt

El archivo `rules-extracted.txt` es la salida bruta de `Traduction_Functions.ipynb` y
**tiene los siguientes defectos conocidos** que lo hacen NO apto para uso directo:

1. **Formato incorrecto**: usa bash here-strings (`simple_switch_CLI <<< "..."`)
   en lugar del formato stdin de una línea por comando.
2. **Parámetro MAC incorrecto**: usa direcciones IPv4 en hex (ej. `0x0a000103`)
   donde `ipv4_forward` espera una dirección MAC de 48 bits (ej. `08:00:00:00:01:03`).

**El archivo `s1-commands.txt` es la referencia correcta y validada.**
`rules-extracted.txt` solo sirve como intermediario de inspección del proceso de
traducción. El estudiante debe llegar a un resultado equivalente a `s1-commands.txt`.

---

## Lo que el estudiante NO debe ver

El archivo `p4src/dt_switch.p4` contiene **la solución completa** con los TO-DO
visibles como comentarios. Para la versión del estudiante, se debería entregar
únicamente el código con los TO-DO sin las líneas de `SOLUTION:`.

Para generar la versión de estudiante (TO-DO only):
```bash
grep -v "SOLUTION:" p4src/dt_switch.p4 | sed 's/^     \* \─.*$//' > student/dt_switch.p4
```
---

