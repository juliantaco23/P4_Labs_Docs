# MySec Exercise — Adaptation Knowledge Base

## Origen
- **Fuente original**: Ejercicio propio del curso "Internet del Futuro" (no deriva de p4lang/tutorials)
- **Destino**: `P4_Labs_Docs/LabP4_3/Codigo/mysec/`
- **Rol en LabP4_3**: Ejercicio de actividad del estudiante (el ejercicio guiado es MRI en `Codigo/mri/`)

---

## Resumen del Ejercicio

MySec implementa un protocolo de **medición de latencia in-switch** usando un campo personalizado en el header IP. El paquete viaja por un camino de "rebote": `h1 → s1 → s2 → s1 → h1`, y durante el trayecto los switches anotan timestamps en los campos del header `mysec_t`. Al regresar a h1, el paquete contiene los tiempos de procesamiento registrados.

**Conceptos clave**:
1. **IP protocolo personalizado**: protocolo 169 (no estándar). El parser siempre extrae el header `mysec_t` si el protocolo es 169.
2. **Header mysec_t**: 8 campos de timestamps/puertos (304 bits = 38 bytes).
3. **Ruta de rebote**: el paquete no llega a h2; s2 lo redirige de vuelta a s1 usando la tabla `TS_table`.
4. **Timestamps egress**: `standard_metadata.egress_global_timestamp` y `standard_metadata.ingress_global_timestamp` (nanosegundos) se leen en el pipeline de **egress**, no en ingress.
5. **Doble paso por s1**: el switch s1 procesa el paquete dos veces — en el camino de ida (h1→s2) y en el de vuelta (s2→h1). Cada pasada registra tiempos distintos.

---

## Topología

```
h1 (00:00:00:00:00:01 / 10.0.0.1) ─── s1 ─── s2 ─── h2 (00:00:00:00:00:02 / 10.0.0.2)
                                    port1  port2  port1  port2
```

| Elemento | Puerto s1 | Puerto s2 |
|----------|-----------|-----------|
| h1       | port1     | —         |
| s2 (desde s1) | port2 | port1   |
| h2       | —         | port2     |

- Links: h1─s1 (`bw=5, delay=5ms, loss=1%`), s1─s2 (`bw=5, delay=5ms, loss=1%`), s2─h2 (`bw=5, delay=5ms, loss=1%`).
- Hosts en la misma subred: `10.0.0.0/24`.

---

## Distinción crítica: `mysec.egres_port` ≠ puerto físico de salida

Esta confusión es la más frecuente al leer el código. Hay dos cosas completamente distintas con nombres parecidos:

| Variable | Tipo | Quién la usa | Para qué |
|----------|------|-------------|----------|
| `standard_metadata.egress_spec` | Metadato bmv2 | Infraestructura del switch | Decide el **puerto físico** por donde sale el paquete |
| `hdr.mysec.egres_port` | Campo del header MySec | El pipeline P4 | **Máquina de estado**: "¿cuál era el destino declarado cuando salió?" |

`mysec.egres_port = 1` en el egress de s1 (primer paso) **no hace que el paquete salga por port1**. El paquete ya fue dirigido a port2 (hacia s2) por `egress_spec=2`, que se fijó en ingress (TS_table). El pipeline egress de v1model no puede redirigir el paquete a otro puerto físico — llega demasiado tarde en la cadena. La modificación de `mysec.egres_port` solo escribe bytes en el header para que la condición de la siguiente pasada pueda distinguir el estado.

---

## Flujo del Paquete MySec

### Paquete inicial (enviado por send_mysec.py)
```
Ethernet(src=h1_MAC, dst=h2_MAC) / IP(proto=169) / MySec(ingress_port=1, egres_port=2)
```

### Paso 1 — s1 ingress (ida, puerto 1 → puerto 2)
- `TS_table`: (dst=h2_MAC, ingress_port=1) → `TimeStamp_port(2)` → **`egress_spec=2`** ← puerto físico decidido aquí

### Paso 2 — s1 egress (ida, `ingress_port=1` en contexto egress)
- `local_metadata.port1 = 2`
- Condición Check2: `ingress_port(1)==1 && mysec.ingress_port(1)==1 && mysec.egres_port(2)==2` → **TRUE**
  - `process_time_sw2 = egress_global_timestamp - ingress_global_timestamp` ← tiempo en s1 (ida)
  - `hdr.ethernet.dst_addr = 0x000000000001` (cambia destino a h1_MAC — el paquete SIGUE saliendo por port2 físico)
  - `mysec.ingress_port = 1, mysec.egres_port = 1` (marca de estado — NO es el puerto físico)

### Paso 3 — s2 ingress (rebote, puerto 1)
- dst=h1_MAC, ingress_port=1
- `TS_table`: (dst=h1_MAC, ingress_port=1) → `TimeStamp_port(1)` → `egress_spec=1` (rebota a s1)

### Paso 4 — s2 egress (rebote, `ingress_port=1`)
- Condición Check1: `ingress_port(1)==port1(2)` → 1≠2 → **FALSE**
- Condición Check2: `ingress_port(1)==1 && mysec.ingress_port(1)==1 && mysec.egres_port(1)==2` → egres_port=1≠2 → **FALSE**
- **Ninguna condición se cumple** → s2 no escribe timestamps. Solo reenvía el paquete.

### Paso 5 — s1 ingress (vuelta, puerto 2)
- dst=h1_MAC, ingress_port=2
- `TS_table`: (dst=h1_MAC, ingress_port=2) → `TimeStamp_port(1)` → `egress_spec=1` (hacia h1)

### Paso 6 — s1 egress (vuelta, `ingress_port=2`)
- `local_metadata.port1 = 2`
- Condición Check1: `ingress_port(2)==port1(2) && mysec.ingress_port(1)==1 && mysec.egres_port(1)==1` → **TRUE**
  - `process_time_sw1 = egress_global_timestamp - ingress_global_timestamp` ← tiempo en s1 (vuelta)
  - `hdr.mysec.egress_time_sw1 = egress_global_timestamp`
  - `mysec.ingress_port = 2, mysec.egres_port = 1`

### Paso 7 — h1 recibe el paquete
- Paquete regresa con `process_time_sw1` y `process_time_sw2` llenos.
- `send_mysec.py` usa `srp1()` para capturar y mostrar el resultado.

---

## Semántica de los Campos Medidos

| Campo | Qué mide | En qué switch | Cuándo |
|-------|----------|---------------|--------|
| `process_time_sw2` | Latencia egress en s1, camino de ida (h1→s2) | s1 | Primer paso de s1 |
| `process_time_sw1` | Latencia egress en s1, camino de vuelta (s2→h1) | s1 | Segundo paso de s1 |
| `egress_time_sw1` | Timestamp egress absoluto en s1, vuelta | s1 | Segundo paso de s1 |

> **Nota**: a pesar del nombre, `process_time_sw2` **no** se mide en s2. s2 actúa solo como reflector (no escribe timestamps). Ambos campos son latencias de s1 medidas en distintas direcciones del tráfico. El nombre refleja "el sw2 en el flujo" (el segundo en el camino), no el switch físico s2.

---

## Reglas de Control

### Modelo de forwarding: dos planos paralelos

MySec implementa **dos planos de forwarding independientes** según el protocolo IP:

| Tipo de paquete | Tabla usada | Tipo de forwarding |
|-----------------|-------------|-------------------|
| proto ≠ 169 (ping, TCP...) | `l2_exact_table` | L2 estándar (dst_MAC → puerto) |
| proto = 169 (MySec) | `TS_table` | Basado en contexto: (dst_MAC + ingress_port) → puerto |

Para paquetes MySec, `l2_exact_table` **no se consulta en absoluto** (el `if/else` en ingress lo excluye). El enrutamiento de MySec no es L2 estándar: la segunda clave `ingress_port` no existe en forwarding L2 convencional. Es enrutamiento basado en contexto de llegada. La telemetría (timestamps) se añade encima de ese forwarding en el pipeline de egress — son dos mecanismos separados.

### ¿Por qué s2 también necesita TS_table?

Porque el código es idéntico en ambos switches y el `apply()` del ingress dice:

```p4
if (hdr.ipv4.protocol != PROTOCOL_MYSEC) {
    l2_exact_table.apply();
} else {
    TS_table.apply();   // ← proto=169 SIEMPRE va aquí, en cualquier switch
}
```

Si s2 no tuviera entradas en `TS_table`, la default action es `drop` — el paquete muere en s2. En s2, TS_table no sirve para distinguir direcciones (solo pasa el paquete una vez), sino simplemente para tener una regla de reenvío válida para paquetes MySec.

### Propósito de TS_table vs l2_exact_table

Ambas tablas reenvían paquetes por un puerto de salida, pero difieren en **cuándo se usan y cuántas claves usan**:

| Tabla | Clave | Usada para |
|-------|-------|------------|
| `l2_exact_table` | `dst_MAC` (1 campo) | Paquetes estándar (proto ≠ 169) |
| `TS_table` | `(dst_MAC, ingress_port)` (2 campos) | Paquetes MySec (proto = 169) |

La clave de dos campos en `TS_table` es necesaria porque **el mismo switch s1 procesa el paquete dos veces** (ida y vuelta) y en cada dirección el paquete tiene la misma MAC destino potencial pero llega por un puerto diferente. Sin `ingress_port` como segunda clave, s1 no podría distinguir si está en el camino de ida o de vuelta.

Ejemplo en s1: cuando dst=h1_MAC llega por port2 (de s2, camino de vuelta), el switch debe enviarlo a port1 (hacia h1). Si solo se usa dst_MAC, no hay forma de saber que viene de vuelta y no de h1 mismo.

### s1-commands.txt
```
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:01 => 1
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:02 => 2
table_add IngressPipeImpl.TS_table IngressPipeImpl.TimeStamp_port 00:00:00:00:00:02 1 => 2
table_add IngressPipeImpl.TS_table IngressPipeImpl.TimeStamp_port 00:00:00:00:00:01 2 => 1
```

| Tabla | Clave (dst_MAC, ingress_port) | Acción | Descripción |
|-------|-------------------------------|--------|-------------|
| l2_exact_table | h1_MAC | set_egress_port(1) | Reenviar a h1 |
| l2_exact_table | h2_MAC | set_egress_port(2) | Reenviar a s2 |
| TS_table | h2_MAC, port1 | TimeStamp_port(2) | Paquete MySec hacia s2 |
| TS_table | h1_MAC, port2 | TimeStamp_port(1) | Paquete MySec que vuelve de s2 |

### s2-commands.txt
```
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:01 => 1
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:02 => 2
table_add IngressPipeImpl.TS_table IngressPipeImpl.TimeStamp_port 00:00:00:00:00:02 1 => 1
table_add IngressPipeImpl.TS_table IngressPipeImpl.TimeStamp_port 00:00:00:00:00:01 1 => 1
```

| Tabla | Clave (dst_MAC, ingress_port) | Acción | Descripción |
|-------|-------------------------------|--------|-------------|
| l2_exact_table | h1_MAC | set_egress_port(1) | Reenviar hacia s1 |
| l2_exact_table | h2_MAC | set_egress_port(2) | Reenviar a h2 |
| TS_table | h2_MAC, port1=1 | TimeStamp_port(1) | Paquete MySec de ida → rebota por port1 |
| TS_table | **h1_MAC, port1=1** | **TimeStamp_port(1)** | **Paquete MySec ya procesado → sigue rebotando** |

> **Ambas entradas de TS_table salen por port 1** — así es correcto. port1 de s2 conecta a s1; port2 conecta a h2. El protocolo MySec nunca debe entregar el paquete a h2 directamente (el rebote siempre va a s1). Si alguna entrada dijera `=> 2`, el paquete sería entregado a h2 en lugar de seguir el camino de rebote.

> **Código muerto**: la primera entrada `(h2_MAC, port1=1) => 1` **nunca se activa**. Cuando un paquete MySec llega a s2, ya tiene `dst_addr = h1_MAC` — s1 lo modifica en su pipeline de egress antes de que el paquete salga hacia s2. Sin embargo, la entrada es inofensiva (una tabla miss usaría la `default_action = drop`, y la entrada `h1_MAC` sí que coincide y reenvía correctamente).

> **Bug corregido**: la cuarta entrada en s2-commands.txt (`h1_MAC, port1 => 1`) **no existía** en el archivo original. Sin ella, el paquete con dst_addr=h1_MAC (modificado por s1 egress) no encontraba match en la TS_table de s2 y era **descartado** por la acción default `drop`. Esto impedía que el paquete regresara a s1 y h1 nunca recibía respuesta.

---

## Campos de Capas Estándar Modificados

**Ethernet** — único campo de capas estándar modificado por P4:
- `dst_addr` — modificado por s1 en egress (camino de ida): cambia de h2_MAC a h1_MAC para redirigir el paquete de vuelta

**IPv4** — **ningún campo estándar es modificado** por el pipeline MySec. El checksum está comentado (`/* update_checksum ... */`) porque ningún campo IPv4 cambia.

> Nota para el redactor: explorar por qué no se modifica `ttl` (el forwarding en MySec no hace decremento explícito). También se puede indagar si esto causa problemas con paquetes que rebotan muchas veces (el TTL no decrece, así que no hay protección contra loops en el encaminamiento).

---

## Historial de Bugs Corregidos

### Bug 1 — `net.staticArp()` antes de `net.start()` (topo.py)
**Síntoma**: `AttributeError: 'NoneType' object has no attribute 'intf'` al iniciar la topología.
**Causa**: `net.staticArp()` requiere que las interfaces de Mininet estén configuradas, lo que solo ocurre después de `net.start()`.
**Corrección**: mover `net.staticArp()` a después de `net.start()`:
```python
net.start()
net.staticArp()   # ← debe ir aquí
```

### Bug 2 — `clone_preserving_field_list` con lista de campos inline (main.p4)
**Síntoma**: Error de compilación con `p4c-bm2-ss`:
```
error: clone_preserving_field_list: field_list must be an integer
```
**Causa**: P4_16 / p4c-bm2-ss no admite la sintaxis `{ standard_metadata.ingress_port }` como argumento inline. Solo acepta un entero que referencia una anotación `@field_list(N)`.
**Corrección**:
1. Agregar `@field_list(1)` al campo `port1` de `local_metadata_t`
2. Cambiar la llamada a `clone_preserving_field_list(CloneType.I2E, CPU_CLONE_SESSION_ID, 1)`

### Bug 3 — s2-commands.txt sin entrada para h1_MAC en TS_table
**Síntoma**: el paquete MySec no regresa a h1. `send_mysec.py` reporta "No se recibió respuesta en 3s".
**Causa**: s1 modifica `dst_addr` a h1_MAC durante su primer paso por egress. Cuando el paquete llega a s2 con ese dst, no hay regla en TS_table → drop por default action.
**Corrección**: agregar a s2-commands.txt:
```
table_add IngressPipeImpl.TS_table IngressPipeImpl.TimeStamp_port 00:00:00:00:00:01 1 => 1
```

### Bugs 4-7 — p4_mininet.py (4 bugs estándar del entorno)
Ver KB_ECN_ADAPTATION.md para detalles completos. Mismos 4 bugs corregidos que en todos los demás ejercicios:
1. `if port == 0: continue` (antes filtraba incorrectamente)
2. `self.device_id = self.thrift_port - 9090` + `--device-id` en args
3. `subprocess.Popen` en lugar de `self.popen()`
4. `self.defaultIntf().rename("eth0")` en P4Host.config()

---

## Por qué send_mysec.py es OBLIGATORIO

El protocolo MySec usa IP proto 169 que no existe en ninguna herramienta de red estándar. Adicionalmente, el protocolo requiere que el paquete inicial tenga el header `mysec_t` con los valores exactos `ingress_port=1, egres_port=2` para activar el branch correcto en el egress de s1.

Sin `send_mysec.py`:
- Herramientas estándar (`ping`, `iperf`, `hping3`) generan paquetes con proto ≠ 169 → parser transita a `accept` sin extraer `mysec_t` → todo el pipeline MySec se ignora
- El resultado sería simplemente forwarding L2/L3 sin medición de timestamps

`send_mysec.py` usa `srp1()` (send-receive layer 2) para enviar el paquete y esperar la respuesta de vuelta en h1, imprimiendo los campos de timestamp al recibirla.

---

## Limitaciones del Diseño

1. **s2 no mide timestamps**: el diseño actual solo registra tiempos en s1 (dos pasadas). s2 actúa como reflector puro. Esto es coherente con el objetivo del ejercicio: medir la latencia de procesamiento de s1 desde dos ángulos (ida y vuelta). Para que s2 midiera se necesitarían: (a) condiciones similares en `EgressPipeImpl` de s2, y (b) campos adicionales en `mysec_t` — los actuales `process_time_sw1/sw2` ya están ocupados por s1. Los campos `ingress_back_time_sw1`, `total` y `th` están disponibles para esa extensión.

2. **Proceso de timestamp solo en egress**: `egress_global_timestamp - ingress_global_timestamp` en el pipeline egress mide la latencia desde que el paquete entra al switch (ingress) hasta que está en el pipeline de egress. No incluye el tiempo de encolado/dequeue.

3. **Precisión limitada por delay de links**: los links tienen `delay=5ms`, lo que introduce ruido en las mediciones. Los valores de `process_time_sw1/sw2` deben ser significativamente menores a 5 ms = 5,000,000 ns; de lo contrario, el delay del link está siendo incluido.

4. **`ingress_back_time_sw1`, `total`, `th`**: campos de extensión para que el estudiante implemente métricas adicionales (TODO en `EgressPipeImpl`). Están en 0 en la solución base. Ver sección "Métricas Adicionales — Actividad del Estudiante" para detalle.

5. **Proto 169 no es estándar IANA**: en un entorno real con routers estándar (Cisco, Juniper), el protocolo 169 sería tratado como desconocido y probablemente descartado por firewalls. La alternativa producción es **INT (In-band Network Telemetry)**, un estándar P4.org que usa mecanismos similares encapsulados en UDP/GRE para no alterar campos IP estándar. INT también tiene el concepto de "transit hop" (equivalente a s2 como reflector). El concepto de MySec es correcto; el mecanismo de transporte necesitaría INT para producción.

---

## Métricas Adicionales — Actividad del Estudiante

El TODO de la Parte 2 en `EgressPipeImpl` pide implementar tres campos que quedan en 0 en la solución base. Se activan en el branch Check1 (s1, camino de vuelta):

### Descripción de cada campo

| Campo | Tipo | Qué debe contener | Cómo calcularlo |
|-------|------|-------------------|-----------------|
| `ingress_back_time_sw1` | `bit<48>` | Timestamp absoluto de ingress en s1 en el camino de vuelta | `standard_metadata.ingress_global_timestamp` (en el branch Check1) |
| `total` | `bit<48>` | Suma del tiempo de procesamiento de s1 en ambas pasadas (ns) | `hdr.mysec.process_time_sw1 + hdr.mysec.process_time_sw2` |
| `th` | `bit<48>` usado como flag 0/1 | Indicador de umbral de latencia — el switch toma la decisión en el plano de datos | `if (hdr.mysec.total > UMBRAL) { th = 1; } else { th = 0; }` |

**Sobre `th` (threshold flag)**: aunque el tipo es `bit<48>` (mismo que el resto de campos del header por uniformidad), se usa como booleano. El switch evalúa si la latencia total supera un límite definido en el programa P4 y escribe el resultado directamente en el header. El receptor (h1) no necesita hacer el cálculo — la decisión ya viene tomada desde el plano de datos. Este patrón es relevante en producción para alertas en tiempo real sin involucrar al controlador: si `th=1`, el colector de telemetría sabe inmediatamente que ese flujo tuvo latencia anormal.

### Solución de referencia (no incluir en el enunciado del estudiante)
```p4
hdr.mysec.ingress_back_time_sw1 = standard_metadata.ingress_global_timestamp;
hdr.mysec.total = hdr.mysec.process_time_sw1 + hdr.mysec.process_time_sw2;
if (hdr.mysec.total > 5000) {
    hdr.mysec.th = 1;
} else {
    hdr.mysec.th = 0;
}
```

### Valores esperados con la solución de referencia (datos de validación)
Con `process_time_sw1 = 779 ns` y `process_time_sw2 = 1323 ns`:
- `ingress_back_time_sw1` = timestamp de ingress en s1 vuelta (valor absoluto, no comparable entre ejecuciones)
- `total = 779 + 1323 = 2102 ns`
- `th = 0` (2102 < 5000 — la latencia de bmv2 es baja en VM sin carga)

> **Nota de diseño**: el umbral de 5000 ns es orientativo para bmv2 en VM. En hardware P4 real (Tofino), la latencia típica es 1,000–5,000 ns y el umbral debería ajustarse según el SLA del servicio. La pedagogía del campo `th` es enseñar decisiones en el plano de datos basadas en métricas acumuladas.

---

## Diferencias con los Demás Ejercicios

| Aspecto | MySec | MRI | ECN | VLAN |
|---------|-------|-----|-----|------|
| Protocolo | IP proto 169 | IP Option 31 | ECN bits (TOS) | VLAN tag 802.1Q |
| Ruta del paquete | Bounce h1→s1→s2→s1→h1 | Forwarding lineal | Forwarding lineal | Forwarding con VLAN |
| Medición | Timestamps in-switch | Queue depth per-hop | Congestión ECN marking | DSCP marking |
| Número de switches | 2 | 3 | 2 | 2 |
| Script de prueba | `send_mysec.py` (srp1, L2) | `send.py` + `receive.py` | `send.py` + `receive.py` | `ping` + `tcpdump` |
| Control plane | `IngressPipeImpl.` | `MyIngress./MyEgress.` | `MyIngress./MyEgress.` | `IngressPipeImpl.` |
| table_set_default | No | Sí (swtrace) | No | No |

---

## Secuencia de Validación Completa

### Limpieza obligatoria
```bash
sudo pkill -9 simple_switch ; sudo mn --clean ; rm -f /tmp/bmv2-*-notifications.ipc
```

### Paso 1: Compilar
```bash
cd LabP4_3/Codigo/mysec
mkdir -p p4src/build
p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json \
    --p4runtime-files p4src/build/p4info.txt p4src/main.p4
```
Salida esperada: ningún error. Se generan `bmv2.json` y `p4info.txt`.

### Paso 2: Iniciar topología
```bash
sudo python3 mininet/topo.py
```
Esperar `mininet>`.

### Paso 3: Instalar reglas (otra terminal)
```bash
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
simple_switch_CLI --thrift-port 9091 < s2-commands.txt
```

### Paso 4: Verificar conectividad básica
```
mininet> pingall
```
**Esperado**: h1 ↔ h2 funciona (ARP estático + l2_exact_table). Resultado: `0% dropped`.

### Paso 5: Prueba MySec
```
mininet> h1 python3 mininet/send_mysec.py
```

**Salida esperada**:
```
Enviando paquete MySec por eth0...
###[ Ethernet ]### ...
###[ IP ]###  proto= 169 ...
###[ MySec ]###
  ingress_port = 1
  egres_port   = 2
  ...

Paquete recibido:
###[ Ethernet ]###  src=00:00:00:00:00:01  dst=00:00:00:00:00:01
###[ IP ]###  proto= 169
###[ MySec ]###
  ingress_port          = 2
  egres_port            = 1
  process_time_sw1      = <valor_ns>    # latencia s1 vuelta
  process_time_sw2      = <valor_ns>    # latencia s1 ida
  egress_time_sw1       = <timestamp>
  ingress_back_time_sw1 = 0
  total                 = 0
  th                    = 0

============================================================
  MySec — Resultados de latencia in-switch
============================================================
  process_time_sw1      : XXXX ns  (latencia egress S1)
  process_time_sw2      : XXXX ns  (latencia egress S1 ida)
  egress_time_sw1       : XXXXXXXXXX  (timestamp egress S1)
  ingress_back_time_sw1 : 0
  total                 : 0
  th                    : 0
============================================================
  ✓  Timestamps registrados correctamente
```

**Valores observados** en la validación (VM bmv2):
- `process_time_sw1 = 779 ns`, `process_time_sw2 = 1323 ns`
- `egress_time_sw1 = 41763658 ns` (timestamp absoluto desde inicio del switch)

**Rango típico en emulador bmv2**: 500 – 50,000 ns (0.5 – 50 µs)
- bmv2 es un **software switch** que corre en CPU de propósito general. El pipeline P4 se interpreta instrucción a instrucción, por lo que las latencias son órdenes de magnitud mayores que en hardware.
- `process_time_sw2 > process_time_sw1` es normal: el primer procesamiento tiene más overhead (acceso a tablas "frío").
- Ambos valores deben ser **significativamente menores a 5,000,000 ns (5 ms)** — el delay configurado en los links. Si se acercan a ese valor, el link delay está siendo incluido en la medición.

**En hardware P4 real (ASIC Tofino, Intel)**:
- Latencia de pipeline típica: 1 – 5 µs (1,000 – 5,000 ns)
- Latencia port-to-port total: < 1 µs en switches de datacenter
- Los campos `process_time_sw1/sw2` reflejarían tiempos mucho menores y más consistentes entre sí
- La variabilidad (jitter) sería también mucho menor al no competir con el scheduler del SO

- Si alguno es 0 → verificar s2-commands.txt (debe tener la cuarta entrada para h1_MAC)

### Indicadores de éxito
- `process_time_sw1 > 0` y `process_time_sw2 > 0`
- El paquete de respuesta tiene `ingress_port=2, egres_port=1` (modificados por s1)
- El `dst_addr` del Ethernet en la respuesta es h1_MAC (`00:00:00:00:00:01`)

### Indicadores de error
| Síntoma | Causa probable | Solución |
|---------|----------------|---------|
| "No se recibió respuesta" | s2-commands.txt sin entrada h1_MAC | Agregar 4ta entrada |
| `process_time_sw1=0, process_time_sw2=0` | Reglas no instaladas | Re-ejecutar CLI commands |
| Error compilación `field_list must be integer` | clone_preserving bug | Verificar fix en main.p4 |
| `AttributeError: 'NoneType'` al iniciar topo | staticArp antes de start | Verificar orden en topo.py |

---

## Notas para el LaTeX (LabP4_3.tex)

### Contextualización con INT (In-band Network Telemetry)

El redactor debe incluir una nota que conecte MRI y MySec con el estándar industrial. Texto sugerido:

> El estándar **INT (In-band Network Telemetry, P4.org)** aplica el mismo principio que MRI: un header stack que crece por salto, con roles diferenciados de *source* (nodo que inicia la telemetría), *transit* (cada switch intermedio que añade sus datos) y *sink* (receptor que extrae e interpreta). El ejercicio MRI implementa el mecanismo fundamental de INT; la versión de producción añade un formato estandarizado y encapsulación en UDP/GRE para ser compatible con redes heterogéneas donde no todos los nodos son P4. Empresas como Meta y Netflix despliegan INT en sus data centers donde toda la infraestructura de switching es P4-capable. MySec, por su parte, implementa un paradigma distinto al de INT: mide la latencia de un nodo individual mediante una ruta de rebote (OAM — Operations, Administration and Maintenance), análogo a lo que protocolos como ITU-T Y.1731 (Ethernet OAM) o BFD hacen en redes de producción. Mientras INT mide telemetría distribuida a lo largo de un camino, MySec/OAM mide el comportamiento de un punto de la red desde la perspectiva del flujo de retorno.

**Implicación para la narrativa del lab**: el lab cubre dos paradigmas complementarios de telemetría in-network:
- **Por camino** (MRI / INT): ¿qué pasó en cada hop del trayecto?
- **Por nodo** (MySec / OAM): ¿cuánto tarda este switch en procesar en cada dirección?

No reemplazar MySec con INT — son conceptualmente distintos y complementarios en el currículo.

---

- Este es el **ejercicio de actividad del estudiante** de LabP4_3
- El TODO del estudiante se encuentra en `EgressPipeImpl.apply()`:
  - Rellenar `local_metadata.port1` con el número de puerto correcto para identificar cada switch
  - Completar las ecuaciones de tiempo en los campos `process_time_sw1`, `process_time_sw2`
  - Completar la dirección MAC de destino en `dst_addr`
- Compilación requiere `--p4runtime-files` (a diferencia de MRI que no lo necesita)
- `send_mysec.py` debe ejecutarse como `h1 python3 mininet/send_mysec.py` (el script está en `mininet/`)
- Instrucciones de color: verde=bash, azul=Python, rojo=Mininet, naranja=P4
