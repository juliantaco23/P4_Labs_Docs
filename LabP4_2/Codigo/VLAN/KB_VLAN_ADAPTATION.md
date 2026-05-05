# VLAN Exercise — Adaptation Knowledge Base

## Origen
- **Fuente original**: Ejercicio diseñado para el curso "Internet del Futuro" (Trabajo de Grado — Julian Tamara)
- **Destino**: `P4_Labs_Docs/LabP4_2/Codigo/VLAN/`
- **Rol en LabP4_2**: Ejercicio de actividad del estudiante (el ejercicio guiado es ECN en `Codigo/ecn/`)

---

## Resumen del Ejercicio

El ejercicio implementa VLAN 802.1Q sobre switches P4. Dos switches P4 dividen cuatro hosts en dos VLANs (VLAN 10 y VLAN 20). El switch de acceso añade la etiqueta VLAN 802.1Q al tráfico entrante y la elimina al entregarlo al host destino. El enlace entre switches actúa como trunk (lleva tráfico de ambas VLANs etiquetado). Adicionalmente, el campo DSCP del header IPv4 se marca según la VLAN para habilitar QoS downstream.

**Conceptos clave del ejercicio**:
1. Tagging 802.1Q: el estudiante programa la lógica que inserta/extrae el header VLAN en el pipeline P4
2. Aislamiento de VLANs: tráfico cross-VLAN se descarta mediante `@defaultonly drop` en `extract_vlan_tag`
3. Marcado DSCP según VLAN: el estudiante asocia una clase de tráfico a cada VLAN modificando `hdr.ipv4.dscp`
4. Recálculo de checksum IPv4 cuando se modifica el campo DSCP

---

### Por qué DSCP y el tag VLAN no son lo mismo (análisis pedagógico)

A primera vista podría parecer que marcar `hdr.ipv4.dscp` es redundante — el tag VLAN `vid` ya identifica la VLAN. La diferencia fundamental es el **alcance**:

**El tag VLAN 802.1Q se destruye antes de llegar al destino.** El pipeline P4 llama a `hdr.vlan_802_1q.setInvalid()` en el switch de egreso antes de entregar el paquete al host receptor. h3 y h4 nunca ven el campo `vid` — desaparece completamente en el switch. El tag VLAN es un mecanismo local entre switches, invisible para los extremos y para cualquier dispositivo fuera de la LAN.

**El campo DSCP vive en el header IPv4 y viaja de extremo a extremo.** Cuando el paquete llega a h3, su header IP conserva `dscp=10`. Cualquier router, firewall o dispositivo QoS en la ruta posterior puede leer ese campo y aplicar políticas de tráfico (priorización, policing, shaping) sin necesidad de conocer nada sobre la topología VLAN original. Ese es el modelo **DiffServ** (RFC 2474): se clasifica el tráfico en el borde de la red (switch de acceso, con contexto VLAN), se marca en el campo IP para que el núcleo de la red pueda actuar sin contexto L2.

Si el campo `vid` viajara hasta el destino, ambos mecanismos serían equivalentes — pero no lo hace.

**Sobre el checksum IPv4**: el recálculo es necesario **únicamente porque se añade el marcado DSCP**. Sin esa modificación, el ejercicio VLAN no altera ningún campo del header IPv4 (no hay routing, no se decrementa TTL), y el checksum original seguiría siendo válido. La `ComputeChecksumImpl` vacía era correcta para la versión sin DSCP. Al modificar `hdr.ipv4.dscp`, el checksum se invalida porque DSCP forma parte del byte TOS que entra en el cálculo de suma de verificación. Los hosts receptores descartan silenciosamente paquetes con checksum incorrecto, por lo que sin este paso el ping funcionaría aparentemente (ICMP llegaría) pero tráfico TCP/UDP podría comportarse incorrectamente dependiendo del OS.

---

## Topología

```
  h1 (VLAN 10) ─ port1 ─┐                 ┌─ port1 ─ h3 (VLAN 10)
                          s1 ══ trunk ══ s2
  h2 (VLAN 20) ─ port2 ─┘  port3   port3  └─ port2 ─ h4 (VLAN 20)
```

### Asignación de Puertos
```
s1: port1 = h1,  port2 = h2,  port3 = trunk hacia s2
s2: port1 = h3,  port2 = h4,  port3 = trunk hacia s1
```

### Direcciones
| Host | IP | Máscara | MAC | VLAN |
|------|----|---------|-----|------|
| h1 | 10.10.10.1 | /29 | 00:00:00:00:00:01 | 10 |
| h2 | 20.20.20.1 | /26 | 00:00:00:00:00:02 | 20 |
| h3 | 10.10.10.2 | /29 | 00:00:00:00:00:03 | 10 |
| h4 | 20.20.20.2 | /26 | 00:00:00:00:00:04 | 20 |

### Parámetros de Enlace
Todos los enlaces: `bw=5 Mbps, delay=5ms, loss=1%` (configurados via TCLink en topo.py).

### VLANs Definidas
```p4
const bit<12> VLAN_10 = 0x00a;  // VLAN ID 10 en hexadecimal
const bit<12> VLAN_20 = 0x014;  // VLAN ID 20 en hexadecimal
```

### DSCP por VLAN (complemento de QoS)
```p4
const bit<6> DSCP_VLAN_10 = 10;  // AF11 — clase de tráfico para VLAN 10
const bit<6> DSCP_VLAN_20 = 20;  // AF22 — clase de tráfico para VLAN 20
```

---

## Flujo de Paquetes P4

### Dirección: host → trunk (tagging)
1. Paquete llega del host con `ether_type = IPv4` (0x0800)
2. El bloque `apply` detecta `ether_type == ETHERTYPE_IPV4` → aplica `set_vlan_tag`
3. `set_vlan_tag` hace match sobre `src_addr` del host → llama `add_vlan_tag(port=3)`
4. `add_vlan_tag` construye el header VLAN:
   - `hdr.vlan_802_1q.setValid()`
   - Asigna `vid` según `ingress_port` (port1→VLAN_10, port2→VLAN_20)
   - Marca `hdr.ipv4.dscp` según VLAN (VLAN_10→10, VLAN_20→20)
   - Mueve `ether_type` al campo interno del VLAN header
   - Establece `ether_type = 0x8100` (TPID VLAN) en ethernet
   - Fija `egress_spec = port3` (trunk)
5. El deparser emite: ethernet (con ether_type=0x8100) + vlan_802_1q + ipv4

### Dirección: trunk → host (untagging)
1. Paquete llega del trunk con `ether_type = 0x8100` (VLAN etiquetado)
2. El parser extrae `hdr.vlan_802_1q`
3. El bloque `apply` detecta `ether_type == ETHERTYPE_VLAN` → aplica `extract_vlan_tag`
4. `extract_vlan_tag` hace match sobre `(dst_addr, vid)`:
   - Si coincide → `set_egress_port(port=1 o 2)` → reenvía al host correcto
   - Si no hay match (cross-VLAN o MAC desconocida) → `@defaultonly drop`
5. `hdr.ethernet.ether_type` se restaura al valor del header VLAN interno (`IPv4`)
6. `hdr.vlan_802_1q.setInvalid()` elimina el header VLAN
7. El deparser emite: ethernet (con ether_type=0x0800) + ipv4

### Aislamiento cross-VLAN
El aislamiento es consecuencia directa de la tabla `extract_vlan_tag`: solo existen entradas para pares `(MAC_destino, VID)` válidos dentro de la misma VLAN. Un paquete de VLAN 10 dirigido a una MAC de VLAN 20 no tiene match → `@defaultonly drop`.

---

## Reglas de Control Plane (simple_switch_CLI)

### s1-commands.txt
```
# Tagging: host → trunk
table_add IngressPipeImpl.set_vlan_tag IngressPipeImpl.add_vlan_tag 00:00:00:00:00:01 => 3
table_add IngressPipeImpl.set_vlan_tag IngressPipeImpl.add_vlan_tag 00:00:00:00:00:02 => 3

# Untagging: trunk → host
table_add IngressPipeImpl.extract_vlan_tag IngressPipeImpl.set_egress_port 00:00:00:00:00:01 10 => 1
table_add IngressPipeImpl.extract_vlan_tag IngressPipeImpl.set_egress_port 00:00:00:00:00:02 20 => 2
```

### s2-commands.txt
```
# Tagging: host → trunk
table_add IngressPipeImpl.set_vlan_tag IngressPipeImpl.add_vlan_tag 00:00:00:00:00:03 => 3
table_add IngressPipeImpl.set_vlan_tag IngressPipeImpl.add_vlan_tag 00:00:00:00:00:04 => 3

# Untagging: trunk → host
table_add IngressPipeImpl.extract_vlan_tag IngressPipeImpl.set_egress_port 00:00:00:00:00:03 10 => 1
table_add IngressPipeImpl.extract_vlan_tag IngressPipeImpl.set_egress_port 00:00:00:00:00:04 20 => 2
```

**Nota clave sobre la tabla `extract_vlan_tag`**: el segundo campo de match es el VID como entero decimal en el CLI (`10` = VLAN 10, `20` = VLAN 20). La CLI confirma el match como `EXACT-00:0a` (hex) y `EXACT-00:14` (hex) respectivamente.

---

## Diferencias clave con el ejercicio ECN

| Aspecto | ECN | VLAN |
|---------|-----|------|
| Capa | L3 (IPv4 LPM) | L2 (MAC exact) |
| Configuración de hosts | `configure_hosts()` (rutas, ARP manual) | `net.staticArp()` (ARP automático entre todos los hosts) |
| Número de tablas P4 | 1 (`ipv4_lpm`) | 2 (`set_vlan_tag`, `extract_vlan_tag`) |
| Prefijo de tabla en CLI | `MyIngress.` | `IngressPipeImpl.` |
| Protocolo a nivel control | Thrift CLI | Thrift CLI |
| Verificación de marcado | `tos` en Scapy (ECN field) | `tos` en tcpdump (DSCP field) |

### Por qué este ejercicio usa `staticArp()` y no `configure_hosts()`
VLAN es un ejercicio L2 puro — los switches no hacen enrutamiento IPv4. Las IPs son solo para que los hosts puedan hacer ping entre ellos. `net.staticArp()` pobla las tablas ARP de todos los hosts con las MACs de todos los demás, evitando la necesidad de ARP broadcast (que el switch P4 no procesa). No se necesitan rutas ni gateways.

---

## Bugs Encontrados y Corregidos

### Bug 1 — `clone_preserving_field_list` con inline field list (error de compilación)
**Síntoma**: `p4c-bm2-ss` retorna:
```
error: argument used for directionless parameter 'index' must be a compile-time constant
clone_preserving_field_list(CloneType.I2E, 99, { standard_metadata.ingress_port });
```
**Causa**: La sintaxis `{ campo }` como tercer argumento es una "inline field list" no soportada en esta versión del compilador. El tercer argumento debe ser un índice constante (`bit<8>`) que referencia anotaciones `@field_list(N)` en los structs de metadatos.

**Solución aplicada**:
1. Anotar el campo en `local_metadata_t` con `@field_list(1)`:
   ```p4
   struct local_metadata_t {
       @field_list(1)
       bit<9>    port1;
       ...
   }
   ```
2. Cambiar la llamada a usar el índice constante:
   ```p4
   action clone_to_cpu() {
       clone_preserving_field_list(CloneType.I2E, CPU_CLONE_SESSION_ID, 1);
   }
   ```

### Bug 2 — `net.staticArp()` llamado antes de `net.start()` en topo.py
**Síntoma**: Las entradas ARP nunca se configuraban, aunque `staticArp()` no reportaba error.
**Causa**: Los namespaces de red de los hosts no existen hasta que se llama `net.start()`. `staticArp()` ejecuta `arp -s ...` en el namespace de cada host — si el namespace no existe, el comando falla silenciosamente.
**Solución**: Llamar `net.staticArp()` después de `net.start()`:
```python
net = Mininet(topo=Exercise4Topo(), controller=None, link=TCLink)
net.start()
net.staticArp()  # DESPUÉS de start() — los namespaces ya existen
```

### Bugs en p4_mininet.py (compartidos con todos los ejercicios)
Ver `KB_ECN_ADAPTATION.md` sección "Bugs Encontrados y Corregidos en p4_mininet.py" para el historial completo de los 4 bugs corregidos (IPC socket, subprocess.Popen, loopback, interface rename).

---

## Validación Funcional — Secuencia Completa

```bash
# Desde la carpeta del ejercicio:
cd /home/p4/P4_Labs_Docs/LabP4_2/Codigo/VLAN

# Paso 1 — Limpiar ejecuciones anteriores
sudo pkill -9 simple_switch ; sudo mn --clean ; rm -f /tmp/bmv2-*-notifications.ipc

# Paso 2 — Compilar
mkdir -p p4src/build
p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json --p4runtime-files p4src/build/p4info.txt p4src/main.p4

# Paso 3 — Levantar topología
sudo python3 mininet/topo.py
```

En otra terminal (mientras Mininet CLI espera):
```bash
# Paso 4 — Instalar reglas en ambos switches
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
simple_switch_CLI --thrift-port 9091 < s2-commands.txt
```

En Mininet CLI:
```
# Paso 5 — Verificar aislamiento VLAN con pingall
mininet> pingall

# Paso 6 — Verificar conectividad intra-VLAN
mininet> h1 ping h3 -c3    # VLAN 10 → VLAN 10 — DEBE FUNCIONAR
mininet> h2 ping h4 -c3    # VLAN 20 → VLAN 20 — DEBE FUNCIONAR

# Paso 7 — Verificar aislamiento cross-VLAN
mininet> h1 ping h4 -c3    # VLAN 10 → VLAN 20 — DEBE FALLAR (100% drop)
mininet> h2 ping h3 -c3    # VLAN 20 → VLAN 10 — DEBE FALLAR (100% drop)

# Paso 8 — Verificar marcado DSCP (abrir xterm para captura)
mininet> xterm h3 h4
```

En **xterm h3** (destino VLAN 10):
```bash
tcpdump -i eth0 -v -c 10
# Buscar en la salida: tos 0x28  ← DSCP=10, ECN=0 → TOS = (10<<2)|0 = 40 = 0x28
```

En **xterm h4** (destino VLAN 20):
```bash
tcpdump -i eth0 -v -c 10
# Buscar en la salida: tos 0x50  ← DSCP=20, ECN=0 → TOS = (20<<2)|0 = 80 = 0x50
```

En **Mininet CLI** (mientras tcpdump escucha):
```
mininet> h1 ping h3 -c5    # genera tráfico hacia h3 → debe mostrar tos 0x28 en xterm h3
mininet> h2 ping h4 -c5    # genera tráfico hacia h4 → debe mostrar tos 0x50 en xterm h4
```

---

## Salidas Esperadas

### pingall (validado)
```
h1 -> X h3 X       h1 solo alcanza h3 (misma VLAN 10, switch distinto) ✓
h2 -> X X h4       h2 solo alcanza h4 (misma VLAN 20, switch distinto) ✓
h3 -> h1 X X       h3 solo alcanza h1 (misma VLAN 10, switch distinto) ✓
h4 -> X h2 X       h4 solo alcanza h2 (misma VLAN 20, switch distinto) ✓
*** Results: 66% dropped (4/12 received)
```

**Por qué 66% drop**: 12 pares totales, 4 conectados (h1↔h3 y h2↔h4 en ambas direcciones), 8 fallan (4 cross-VLAN + 4 mismo-switch sin ruta). Los pares del mismo switch (h1↔h2 en s1, h3↔h4 en s2) también fallan: el switch P4 no tiene una tabla de forwarding L2 estándar — solo procesa según VLAN tag, y el tráfico hacia el mismo switch no tiene entrada en las tablas porque `set_vlan_tag` envía todo al trunk (port3) y `extract_vlan_tag` necesita que el paquete llegue por el trunk.

### Reglas instaladas (salida CLI — validada)
```
# s1: set_vlan_tag entries
EXACT-00:00:00:00:00:01  →  add_vlan_tag  runtime: 00:03  (port3)
EXACT-00:00:00:00:00:02  →  add_vlan_tag  runtime: 00:03  (port3)

# s1: extract_vlan_tag entries
EXACT-00:00:00:00:00:01 + EXACT-00:0a  →  set_egress_port  runtime: 00:01  (port1=h1)
EXACT-00:00:00:00:00:02 + EXACT-00:14  →  set_egress_port  runtime: 00:02  (port2=h2)
```

### Marcado DSCP esperado (tcpdump -v)
```
# Paquetes de h1 hacia h3 (VLAN 10):
IP (tos 0x28, ...)  10.10.10.1 > 10.10.10.2: ICMP echo request
#                     ^^^^
#                   DSCP=10, ECN=0 → TOS = 40 = 0x28

# Paquetes de h2 hacia h4 (VLAN 20):
IP (tos 0x50, ...)  20.20.20.1 > 20.20.20.2: ICMP echo request
#                     ^^^^
#                   DSCP=20, ECN=0 → TOS = 80 = 0x50
```

**Referencia rápida de TOS para DSCP**:

| VLAN | DSCP (decimal) | DSCP (binario) | TOS byte (hex) | Clase DSCP |
|------|---------------|---------------|----------------|------------|
| 10 | 10 | 001010 | 0x28 | AF11 |
| 20 | 20 | 010100 | 0x50 | AF22 |

Fórmula: `TOS_hex = (DSCP << 2)` cuando ECN=0.

**Nota importante**: El marcado DSCP ocurre SOLO en el switch de acceso ingreso (cuando `add_vlan_tag` procesa el paquete). El switch de egreso (`extract_vlan_tag`) no modifica el DSCP — el campo ya viene marcado en el paquete etiquetado por el trunk. Por eso se observa en el receptor (h3/h4), no en el emisor (h1/h2).

---

## Notas sobre la acl_table y el comportamiento sin entradas

`acl_table` se aplica al inicio del bloque `apply` (antes de la lógica VLAN). Sus acciones son `send_to_cpu`, `clone_to_cpu`, y `drop`. No se instala ninguna entrada ACL en este ejercicio (`s1-commands.txt` y `s2-commands.txt` no tienen entradas `acl_table`).

Con una tabla vacía y sin `default_action` declarada, la acción por defecto es `NoAction` — el paquete continúa al siguiente bloque `apply()` sin modificación. Esto es correcto y esperado.

---

## TODOs del Estudiante en main.p4

El archivo `p4src/main.p4` incluye los siguientes bloques TODO que el estudiante debe completar (la solución ya está presente en el archivo de solución):

1. **Constantes VLAN** (sección de defines): Elegir VIDs hexadecimales únicos (000-FFF)
2. **Constantes DSCP** (sección de defines): Elegir valores DSCP para cada VLAN (0-63)
3. **Parser `parse_vlan`**: Dirigir al parser de IPv4 después de extraer el header VLAN
4. **`add_vlan_tag` — DSCP marking**: Marcar `hdr.ipv4.dscp` según `ingress_port`, usando las constantes DSCP definidas
5. **`apply` block — untagging**: Llamar `hdr.vlan_802_1q.setInvalid()` para eliminar el header VLAN
6. **`ComputeChecksumImpl`**: Agregar `update_checksum` para recalcular `hdr.ipv4.hdr_checksum` cuando se modifica DSCP

---

## Notas para el LaTeX (LabP4_2.tex — sección de actividad del estudiante)

- Este es el **ejercicio de actividad** de LabP4_2 (el estudiante lo implementa)
- El prefijo de tablas en CLI es `IngressPipeImpl.` (no `MyIngress.`)
- El ejercicio NO usa `configure_hosts()` — usa `net.staticArp()` (ejercicio L2, no L3)
- Las IPs de los hosts son solo para verificación con ping; el switch no enruta IPv4
- El enlace trunk entre switches es bidireccional: s1-port3 ↔ s2-port3
- La verificación principal son dos niveles: (1) aislamiento por ping, (2) marcado DSCP por tcpdump
- El orden de `addLink()` en topo.py determina los números de puerto — debe coincidir con los comandos CLI
- Color de instrucciones en LaTeX: verde=bash, rojo=Mininet, naranja=P4
