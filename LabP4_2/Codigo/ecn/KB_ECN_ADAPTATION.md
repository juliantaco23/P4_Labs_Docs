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

---

## Bugs Encontrados y Corregidos en p4_mininet.py — HISTORIAL COMPLETO

Estos bugs fueron descubiertos durante la validación funcional de ECN (Abril 2026) y corregidos en **todos** los `p4_mininet.py` del repositorio (LabP4_1/Codigo/1, 2, 2.2 · LabP4_2/Codigo/ecn, VLAN · LabP4_3/Codigo/mri, mysec).

---

### Bug 1 — IPC socket compartido entre switches (CRÍTICO)

**Síntoma**: Solo el primer switch (s1) arrancaba correctamente. El segundo switch (s2) fallaba silenciosamente: no aparecía en `ps aux`, no existía `/tmp/s2.log`, y `simple_switch_CLI --thrift-port 9091` retornaba `Could not connect`.

**Causa raíz**: BMv2 (`simple_switch`) crea un socket nanomsg de notificaciones en `/tmp/bmv2-{device_id}-notifications.ipc`. El `device_id` por defecto es **0** para todos los switches. Entonces s1 bindea `/tmp/bmv2-0-notifications.ipc` y s2 intenta bindear el **mismo archivo** → `Address already in use` → s2 termina con código 1 inmediatamente.

El log de s2 mostraba:
```
Nanomsg returned a exception when trying to bind to address 'ipc:///tmp/bmv2-0-notifications.ipc'.
The exception is: Address already in use
```

**Solución aplicada**: Pasar `--device-id` único a cada switch, derivado del thrift_port:
```python
# En __init__():
self.device_id = self.thrift_port - 9090  # s1→0, s2→1, s3→2

# En start(), al construir args[]:
args.extend(['--thrift-port', str(self.thrift_port)])
args.extend(['--device-id', str(self.device_id)])
```

Esto genera sockets únicos:
- s1 (thrift 9090): `/tmp/bmv2-0-notifications.ipc`
- s2 (thrift 9091): `/tmp/bmv2-1-notifications.ipc`
- s3 (thrift 9092): `/tmp/bmv2-2-notifications.ipc`

---

### Bug 2 — self.popen() vs subprocess.Popen() (CRÍTICO)

**Síntoma**: Incluso después de corregir el Bug 1, s2 seguía fallando con código de salida 1.

**Causa raíz**: `self.popen()` es un método de `Mininet.Node` que internamente envuelve el comando con `mnexec -da <pid>` (`-d` = daemonize, `-a` = attach al namespace de red del nodo). En ciertos pares de versiones Mininet+BMv2, el proceso daemonizado del segundo switch se desconecta del namespace antes de que BMv2 pueda inicializarse, causando un fallo silencioso.

**Solución aplicada**: Reemplazar `self.popen()` por `subprocess.Popen()` directamente:
```python
# ANTES (problemático):
self.bmv2popen = self.popen(args, stdout=logfile, stderr=logfile)

# DESPUÉS (correcto):
self.bmv2popen = subprocess.Popen(args, stdout=logfile, stderr=logfile)
```
`subprocess.Popen` lanza `simple_switch` como hijo directo del proceso Python, sin la capa `mnexec`. BMv2 funciona correctamente así porque cada switch ya opera en su propio namespace de red (Mininet lo configura antes de llamar a `start()`).

Se agregó también una verificación inmediata de fallo:
```python
time.sleep(1)
if self.bmv2popen.poll() is not None:
    error("*** ERROR: %s exited immediately (code %d). Check: %s\n"
          % (self.name, self.bmv2popen.returncode, self.log_file))
```

---

### Bug 3 — Interfaz de loopback incluida en args de BMv2

**Síntoma** (descubierto analíticamente, potencial): La condición original para saltar el loopback era:
```python
if not intf.IP() and port == 0:
    continue
```
`lo` tiene IP `127.0.0.1`, por lo que `not intf.IP()` es `False`. La condición nunca se ejecutaba y BMv2 recibía `-i 0@lo` junto con las interfaces reales.

**Solución aplicada**:
```python
if port == 0:
    continue  # port 0 es siempre loopback en Mininet
```

---

### Bug 4 — Interfaces de host nombradas hX-eth0 en lugar de eth0

**Síntoma**: `receive.py` fallaba con `OSError: eth0: No such device`. `configure_hosts()` en los ejercicios L3 ejecutaba `route add ... dev eth0` y `arp -i eth0 ...` sobre una interfaz inexistente → rutas nunca configuradas → pingall 100% drop.

**Causa raíz**: Mininet nombra las interfaces de host como `h1-eth0`, `h2-eth0`, etc. por defecto. El código original de p4lang/tutorials renombraba la interfaz principal a `eth0` en `P4Host`. Nuestra implementación inicial de `P4Host` omitió ese paso.

**Solución aplicada**: Agregar `rename("eth0")` en `P4Host.config()`:
```python
class P4Host(Host):
    def config(self, **params):
        r = super().config(**params)
        self.defaultIntf().rename("eth0")  # send.py, receive.py y configure_hosts() esperan eth0
        for off in ["rx", "tx", "sg"]:
            self.cmd("ethtool --offload eth0 %s off" % off)
        return r
```
El rename también es necesario para deshabilitar TX/RX offload correctamente (antes se usaba `self.defaultIntf()` como nombre, que devolvía el objeto, no el string del nombre actualizado).

---

### Secuencia de diagnóstico para arranque de switches

Si un switch no arranca, seguir este orden:

```bash
# 1. Verificar cuántos procesos simple_switch hay
ps aux | grep simple_switch

# 2. Verificar qué puertos Thrift están activos
ss -tlnp | grep 909

# 3. Ver log del switch fallido
cat /tmp/s2.log    # o s3.log

# 4. Limpiar y reiniciar
sudo pkill -9 simple_switch
sudo mn --clean
# Eliminar sockets IPC residuales
rm -f /tmp/bmv2-*-notifications.ipc
```

---

### Validación ECN — Secuencia Corregida y Explicada

```bash
# Desde la carpeta del ejercicio:
cd /home/p4/P4_Labs_Docs/LabP4_2/Codigo/ecn

# Paso 1 — Compilar
mkdir -p p4src/build
p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json p4src/ecn.p4
chmod +x send.py receive.py

# Paso 2 — Levantar topología
sudo pkill -9 simple_switch ; sudo mn --clean
sudo python3 mininet/topo.py
```

En otra terminal (mientras Mininet CLI espera):
```bash
# Paso 3 — Instalar reglas (una por switch, no juntas)
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
simple_switch_CLI --thrift-port 9091 < s2-commands.txt
```

En Mininet CLI:
```
# Paso 4 — Verificar conectividad L3 entre subredes
# NOTA: h1↔h11 y h2↔h22 SIEMPRE fallan (mismo switch, sin ARP proxy)
# Solo importan los pares CRUZADOS:
mininet> h1 ping 10.0.2.2 -c3    # h1 → h2
mininet> h11 ping 10.0.2.22 -c3  # h11 → h22

# Paso 5 — Abrir xterms para h2 y h22
mininet> xterm h2 h22
```

En **xterm h22** (servidor iperf — generará congestión en el enlace bottleneck):
```bash
iperf -s -p 5001 -u
```

En **xterm h2** (sniff de paquetes — observará el cambio de TOS):
```bash
python3 /home/p4/P4_Labs_Docs/LabP4_2/Codigo/ecn/receive.py
```

En **Mininet CLI** — IMPORTANTE: dos comandos separados, no con `&` en la misma línea:
```
# Paso 6 — Generar congestión (h11 → h22 a 2Mbps, enlace es 0.5Mbps → cola supera ECN_THRESHOLD=10)
# Nota: -b 600k NO es suficiente (la cola no alcanza depth=10, ECN nunca marca → todos tos=0x1).
# Con 2Mbps la cola sí supera el threshold → se observan paquetes con tos=0x3. Algunos paquetes
# pueden descartarse cuando el buffer se llena completamente (esperado, no es error).
mininet> h11 iperf -c 10.0.2.22 -p 5001 -t 30 -u -b 2M &

# Paso 7 — Enviar tráfico ECN-observable (IMPORTANTE: usar IP directa, no nombre de host)
mininet> h1 python3 /home/p4/P4_Labs_Docs/LabP4_2/Codigo/ecn/send.py 10.0.2.2 "P4 is cool" 20
```

**Por qué NO usar `&` en la misma línea de Mininet CLI**: Mininet reemplaza nombres de host (`h1`, `h22`) por sus IPs antes de enviar al shell. Con `h11 iperf ... & h1 ./send.py ...`, el shell de h11 recibe `iperf ... & 10.0.1.1 ./send.py ...` y trata `10.0.1.1` como un comando → `command not found`.

**Por qué usar IP directa en send.py**: El argumento `10.0.2.2` es para `socket.gethostbyname()` dentro de send.py. Si se usa el nombre `h2`, Python intentaría resolverlo via DNS en el namespace del host → falla. La IP directa siempre funciona.

**Salida esperada en receive.py**:

El orden de tos=0x1 y tos=0x3 depende del momento en que la cola se satura:

```
# Escenario más frecuente (iperf satura el enlace antes del primer paquete de send.py):
got a packet  →  tos=0x3  (ECN=11 — cola ya congestionada al llegar el primer paquete)
got a packet  →  tos=0x3
...
got a packet  →  tos=0x1  (ECN=01 — iperf terminó, cola se vació)
got a packet  →  tos=0x1
```

Esto es correcto. Con 2Mbps en un enlace de 0.5Mbps, la cola se llena en ≈75ms — antes de que llegue el primer paquete de send.py (que arranca ~1s después del iperf). El orden `0x1 → 0x3 → 0x1` solo ocurre si send.py arranca mucho antes que iperf.

**Paquetes recibidos < 20 (pérdida esperada con 2Mbps, mejorable con 600k)**:
send.py envía 20 paquetes (confirmado por 20× "Sent 1 packets." en la salida). Los faltantes son **descartados en la cola de BMv2**, no marcados. Cuando la cola supera su capacidad máxima, los nuevos paquetes se descartan antes de entrar al pipeline de egress — nunca llegan a la lógica ECN. Esto demuestra que ECN solo puede marcar paquetes mientras el buffer tenga espacio; una vez lleno, la red vuelve a descartar igual que sin ECN.

Para una demo que evite drops, se podría usar `iperf -b 600k`, pero **esto no funciona**: con 600k el enlace de 500kbps se satura apenas un 20% → la cola nunca alcanza `ECN_THRESHOLD = 10` → ECN nunca marca → todos los paquetes llegan con `tos=0x1` → no hay nada que observar. La congestión con 2Mbps es necesaria para disparar el mecanismo ECN.

**Nota**: Aumentar el tamaño de la cola en BMv2 (`set_queue_depth 500` en la CLI) NO es la solución correcta — simula bufferbloat, que es exactamente el problema que ECN pretende resolver.

**Conclusión**: La configuración con 2Mbps es la correcta. Los descartes son un efecto secundario aceptable — lo pedagógicamente importante es observar el marcado `tos=0x3`, lo cual sí ocurre con 2Mbps.

**Sobre iperf en h22 — flag `-u` OBLIGATORIO**:
El servidor iperf debe ejecutarse con `-u` para recibir tráfico UDP. Sin `-u`, escucha TCP y h11's iperf UDP nunca es recibido (h22 muestra solo "Server listening" sin estadísticas). La congestión igual ocurre (h11 transmite UDP independientemente), pero el servidor no muestra estadísticas. Comando correcto:
```bash
# En xterm h22 — SIEMPRE con -u:
iperf -s -p 5001 -u
```

**Resultado de pingall validado**:
```
h1 -> h2 X h22      ← h11 falla (mismo switch, misma subred) — CORRECTO
h2 -> h1 h11 X      ← h22 falla (mismo switch, misma subred) — CORRECTO  
h11 -> X h2 h22     ← h1 falla (mismo switch, misma subred) — CORRECTO
h22 -> h1 X h11     ← h2 falla (mismo switch, misma subred) — CORRECTO
*** Results: 33% dropped (8/12 received)  ← CORRECTO
```
Los 4 pares que fallan son exactamente los pares dentro del mismo switch y misma subred. El switch solo hace L3 y no maneja ARP broadcasts. Los 8 pares cross-switch funcionan al 100%.

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
