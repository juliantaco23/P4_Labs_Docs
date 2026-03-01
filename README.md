# Documentación de Laboratorios P4 — BMv2 + Mininet (sin ONOS)

> **GITA** – Grupo de Investigación en Telecomunicaciones Aplicadas  
> Entorno de prácticas para familiarización con **P4** usando **BMv2 (simple_switch)** y **Mininet**.
>
> Las reglas se insertan manualmente con `simple_switch_CLI`, sin depender de un controlador SDN específico.

---

## Requisitos previos (todas las prácticas)

| Componente | Versión |
|---|---|
| Ubuntu VM | 20.04 LTS |
| p4c | `p4c-bm2-ss` (compilador P4 para BMv2) |
| BMv2 | `simple_switch` + `simple_switch_CLI` |
| Mininet | 2.3+ |
| Python 3 | 3.8+ |
| Scapy | `pip3 install scapy` (para pruebas MySec, Ex-3) |

### Instalación rápida

Se usa la **VM oficial de p4lang** (Ubuntu 20.04) que ya trae `p4c`, `BMv2`, `Mininet` y todas las dependencias preinstaladas:

1. Descargar la VM desde: https://github.com/p4lang/tutorials/releases
2. Importar en VirtualBox/VMware
3. Usuario: `p4` / Contraseña: `p4`

La VM incluye:
- `p4c-bm2-ss` (compilador P4 → BMv2 JSON)
- `simple_switch` + `simple_switch_CLI`
- Mininet 2.3+
- Python 3.8+
- Scapy

> **Nota:** El método anterior de instalación vía paquetes APT de p4lang (`download.opensuse.org`) está **deprecado** y ya no se mantiene. La VM oficial es el método soportado.

### Flujo de trabajo general

```
1. Compilar P4         →  p4c-bm2-ss genera bmv2.json
2. Levantar topología  →  sudo python3 mininet/topo.py   (arranca Mininet + simple_switch)
3. Instalar reglas     →  simple_switch_CLI < s1-commands.txt  (en otra terminal)
4. Probar              →  pingall / ping / Scapy  (en la CLI de Mininet)
```

### Nota sobre archivos heredados

El repositorio puede contener archivos del enfoque anterior (Docker + ONOS) como referencia: `docker-compose.yml`, `Makefile`, `netcfg.json`, `stratum2.py`, `flows*`, `run_exercise.py`. Estos archivos **no son necesarios** para el flujo actual basado en `mininet/topo.py` + `simple_switch_CLI`.

---

## Archivos compartidos

### `mininet/p4_mininet.py` (dentro de cada ejercicio)

Módulo Python con dos clases auxiliares que usa `mininet/topo.py` de cada ejercicio:

| Clase | Función |
|---|---|
| `P4Switch` | Subclase de Mininet `Switch` que levanta un proceso `simple_switch` con el JSON compilado. Expone un puerto thrift para recibir comandos de `simple_switch_CLI`. |
| `P4Host` | Subclase de Mininet `Host` que desactiva TX/RX/SG checksum offload para compatibilidad con BMv2. |

---

## Exercise-1 — L2 Forwarding Básico

### Objetivo
Primera aproximación al desarrollo P4. Se programa un switch BMv2 que reenvía tramas Ethernet según la dirección MAC destino, usando una tabla `l2_exact_table` cuyas entradas se insertan con `simple_switch_CLI`.

### Topología
```
  h1 (10.0.0.1/24) ── s1 ── h2 (10.0.0.2/24)
       MAC 01              MAC 02
```
- 1 switch (`s1`, thrift port 9090), 2 hosts
- Links: h1-s1 2 Mbps / 10 ms / 5% loss, h2-s1 5 Mbps / 1 ms / 2% loss
- P4: `p4src/main.p4`

### Conceptos clave
- Parser de Ethernet + IPv4
- Tabla `l2_exact_table` con acción `set_egress_port`
- ARP estático (`net.staticArp()`) — no hay procesamiento ARP en P4

### Archivos del ejercicio
| Archivo | Función |
|---|---|
| `p4src/main.p4` | Programa P4 con TODOs del estudiante |
| `mininet/topo.py` | Topología Mininet con `P4Switch` (ejecutar con sudo) |
| `mininet/p4_mininet.py` | Clases `P4Switch` y `P4Host` para BMv2 |
| `s1-commands.txt` | Reglas para `simple_switch_CLI` |

### Reglas instaladas (`s1-commands.txt`)
```
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:01 => 1
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:02 => 2
```

### Paso a paso
```bash
cd Exercise-1
mkdir -p p4src/build
p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json --p4runtime-files p4src/build/p4info.txt p4src/main.p4

# Terminal 1: topología
sudo python3 mininet/topo.py

# Terminal 2: reglas
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
```

### Verificación
| Paso | Comando | Resultado esperado |
|---|---|---|
| 1 | Compilación sin errores | `p4c-bm2-ss` termina sin error |
| 2 | `mininet> pingall` | `h1 → h2: 0% dropped` |
| 3 | `simple_switch_CLI` → `table_dump IngressPipeImpl.l2_exact_table` | 2 entradas visibles |

---

## Exercise-2 — Switch con ARP Responder (estático)

### Objetivo
Extender el switch L2 para que responda solicitudes ARP usando mapeos IP→MAC estáticos configurados como entradas de tabla. Cuando llega un ARP Request, el switch genera un ARP Reply directamente en el data plane.

### Topología
```
  h1 (10.0.0.1/24) ── s1 ── h2 (10.0.0.2/24)
       MAC 01              MAC 02
```
- 1 switch, 2 hosts (sin `staticArp` — ARP se resuelve en el data plane)
- P4: `p4src/main.p4`

### Conceptos clave
- Header ARP (`arp_t`) con campos RFC 826
- Tabla `arp_exact` con acción `arp_reply` (genera respuesta ARP en el data plane)
- Parser con `select(hdr.ethernet.ether_type)` → IPv4 / ARP
- Deparser emite `hdr.arp`

### Reglas instaladas (`s1-commands.txt`)
```
# L2 forwarding
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:01 => 1
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:02 => 2
# ARP: quien pregunte por 10.0.0.1 recibe MAC 01, por 10.0.0.2 recibe MAC 02
table_add IngressPipeImpl.arp_exact IngressPipeImpl.arp_reply 10.0.0.1 => 00:00:00:00:00:01
table_add IngressPipeImpl.arp_exact IngressPipeImpl.arp_reply 10.0.0.2 => 00:00:00:00:00:02
```

### Paso a paso
```bash
cd Exercise-2
mkdir -p p4src/build
p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json \
    --p4runtime-files p4src/build/p4info.txt p4src/main.p4

# Terminal 1: topología
sudo python3 mininet/topo.py

# Terminal 2: reglas
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
```

### Verificación
| Paso | Comando | Resultado esperado |
|---|---|---|
| 1 | `mininet> h1 arping -c 1 10.0.0.2` | ARP reply recibido (sin timeout) |
| 2 | `mininet> pingall` | 0% packet loss |
| 3 | `table_dump IngressPipeImpl.arp_exact` | 2 entradas ARP |

---

## Exercise-2.1 — ARP Responder (sw_gita.p4)

### Objetivo
Mismo concepto que Exercise-2 pero usando el archivo `sw_gita.p4`. El estudiante completa los TODOs de P4 (header ARP, parser, arp_reply action, arp_exact table). Las reglas se insertan manualmente.

> **Nota:** En el enfoque original con ONOS, este ejercicio incluía una app Java (`ArpResponder`) que aprendía MACs dinámicamente. Sin ONOS, las mismas entradas se insertan estáticamente con `simple_switch_CLI`.

### Topología
```
  h1 (10.0.0.1/24, MAC 01)
     │ 2 Mbps, 10 ms, 5% loss
     s1
     │ 5 Mbps, 1 ms, 2% loss
  h2 (10.0.0.2/24, MAC 02)
```
- 1 switch, 2 hosts con enlaces asimétricos (TCLink)
- P4: `p4src/sw_gita.p4`

### TODOs del estudiante (solo P4)
1. Definir constantes ARP (HTYPE, PTYPE, etc.)
2. Definir `header arp_t`
3. Modificar `parse_ethernet` para transicionar a `parse_arp` cuando `ether_type == ARP`
4. Implementar `parse_arp` (extract + select op_code)
5. Implementar `action arp_reply` (swap MAC/IP, cambiar opcode)
6. Definir `table arp_exact`
7. Incluir `hdr.arp` en el deparser

### Reglas instaladas (`s1-commands.txt`)
```
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:01 => 1
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:02 => 2
table_add IngressPipeImpl.arp_exact IngressPipeImpl.arp_reply 10.0.0.1 => 00:00:00:00:00:01
table_add IngressPipeImpl.arp_exact IngressPipeImpl.arp_reply 10.0.0.2 => 00:00:00:00:00:02
```

### Verificación
| Paso | Comando | Resultado esperado |
|---|---|---|
| 1 | Compilación `sw_gita.p4` sin errores | `p4c-bm2-ss` OK |
| 2 | `mininet> h1 arping -c 1 10.0.0.2` | ARP reply recibido |
| 3 | `mininet> pingall` | 0% loss (con tolerancia por TCLink loss%) |

---

## Exercise-2.2 — Filtrado de Sesiones TCP

### Objetivo
Programar un switch que filtre paquetes TCP que no pertenecen a una sesión registrada. El data plane genera un RST (reset) para paquetes TCP no autorizados. Las sesiones permitidas se registran manualmente en la tabla `tcp_sessions`.

> **Nota:** En el enfoque original con ONOS, la app Java (`TCPSessionManager`) interceptaba paquetes SYN y registraba la sesión dinámicamente. Sin ONOS, cada sesión TCP permitida debe insertarse manualmente (o usando `add_tcp_session.sh`).

### Topología
```
  h1 (10.0.0.1/24, MAC 01)
     │ 5 Mbps, 5 ms, 1% loss
     s1
     │ 5 Mbps, 5 ms, 1% loss
  h2 (10.0.0.2/24, MAC 02)
```
- 1 switch, 2 hosts
- P4: `p4src/sw_gita.p4`

### TODOs del estudiante (solo P4)
1. Definir `header tcp_t` con flags individuales (syn, ack, rst, etc.)
2. Modificar `parse_ipv4` para transicionar a `parse_tcp` cuando `protocol == TCP`
3. Definir `table tcp_sessions` con key `{src_ip, src_port, dst_ip, dst_port}`
4. Implementar lógica apply: si `tcp_sessions.hit` → forward; si no → generar RST reply

### Reglas base (`s1-commands.txt`)
```
# L2 + ARP (siempre necesarios)
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:01 => 1
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:02 => 2
table_add IngressPipeImpl.arp_exact IngressPipeImpl.arp_reply 10.0.0.1 => 00:00:00:00:00:01
table_add IngressPipeImpl.arp_exact IngressPipeImpl.arp_reply 10.0.0.2 => 00:00:00:00:00:02
```

### Agregar sesiones TCP permitidas
Usar el script helper `add_tcp_session.sh`:
```bash
# Permitir SSH (puerto 22) de h1 a h2 con puerto origen 12345
./add_tcp_session.sh 10.0.0.1 12345 10.0.0.2 22
```

Esto ejecuta los dos `table_add` necesarios (ida y vuelta):
```
table_add IngressPipeImpl.tcp_sessions NoAction 10.0.0.1 12345 10.0.0.2 22 =>
table_add IngressPipeImpl.tcp_sessions NoAction 10.0.0.2 22 10.0.0.1 12345 =>
```

### Verificación
| Paso | Comando | Resultado esperado |
|---|---|---|
| 1 | Compilación `sw_gita.p4` OK | Sin errores |
| 2 | Instalar reglas base + sesión TCP de prueba | OK |
| 3 | `mininet> h2 /usr/sbin/sshd &` → `h1 ssh h2` (solo si sesión registrada) | Conexión OK |
| 4 | Enviar TCP sin sesión registrada | Switch responde con RST |
| 5 | `table_dump IngressPipeImpl.tcp_sessions` | Sesiones visibles |

---

## Exercise-3 — Medición de Timestamps entre Switches

### Objetivo
Medir tiempos de procesamiento en una cadena de 2 switches usando un protocolo custom **MySec** (IP protocol 169). Un paquete MySec viaja h1→s1→s2→s1→h1, y en cada salto el pipeline de egress registra timestamps de procesamiento.

### Topología
```
  h1 (10.0.0.1/24)              h2 (10.0.0.2/24)
     │                             │
     s1 ──────────────────── s2
   port1:h1                  port1:s1
   port2:s2                  port2:h2
   thrift:9090               thrift:9091
```
- 2 switches, 2 hosts
- P4: `p4src/main.p4`
- Links: 5 Mbps / 5 ms / 1% loss

### Protocolo MySec
```
mysec_t {
  ingress_port (4b)          // Estado: puerto de ingreso actual
  egres_port (4b)            // Estado: puerto de egreso actual
  process_time_sw1 (48b)     // Tiempo procesamiento en S1
  process_time_sw2 (48b)     // Tiempo procesamiento en S2
  egress_time_sw1 (48b)      // Timestamp egreso de S1
  ingress_back_time_sw1 (48b)// Timestamp re-ingreso a S1
  total (48b)                // Tiempo total round-trip
  th (48b)                   // Threshold
}
```

### Recorrido del paquete MySec
1. **h1 → s1** (ingress port 1): `TS_table` envía a port 2 (hacia s2)
2. **s1 → s2** (ingress port 1 en s2): `TS_table` *rebota* a port 1 (back to s1). Egress registra `process_time_sw2` y cambia `dst MAC` a h1
3. **s2 → s1** (ingress port 2 en s1): `TS_table` envía a port 1 (back to h1). Egress registra `process_time_sw1` y `egress_time_sw1`
4. **s1 → h1**: Paquete llega con todos los timestamps rellenados

### Reglas necesarias

**s1-commands.txt** (thrift port 9090):
```
# L2 (tráfico normal)
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:01 => 1
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:02 => 2
# MySec routing
table_add IngressPipeImpl.TS_table IngressPipeImpl.TimeStamp_port 00:00:00:00:00:02 1 => 2
table_add IngressPipeImpl.TS_table IngressPipeImpl.TimeStamp_port 00:00:00:00:00:01 2 => 1
```

**s2-commands.txt** (thrift port 9091):
```
# L2 (tráfico normal)
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:01 => 1
table_add IngressPipeImpl.l2_exact_table IngressPipeImpl.set_egress_port 00:00:00:00:00:02 => 2
# MySec: rebotar paquete de vuelta a s1
table_add IngressPipeImpl.TS_table IngressPipeImpl.TimeStamp_port 00:00:00:00:00:02 1 => 1
```

### Paso a paso
```bash
cd Exercise-3
mkdir -p p4src/build
p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json \
    --p4runtime-files p4src/build/p4info.txt p4src/main.p4

# Terminal 1: topología
sudo python3 mininet/topo.py

# Terminal 2: reglas en ambos switches
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
simple_switch_CLI --thrift-port 9091 < s2-commands.txt
```

### Script de prueba MySec (Scapy en h1)
```python
from scapy.all import *

class MySec(Packet):
    name = "MySec"
    fields_desc = [
        BitField("ingress_port", 1, 4),
        BitField("egres_port", 1, 4),
        BitField("process_time_sw1", 0, 48),
        BitField("process_time_sw2", 0, 48),
        BitField("egress_time_sw1", 0, 48),
        BitField("ingress_back_time_sw1", 0, 48),
        BitField("total", 0, 48),
        BitField("th", 1000000, 48),
    ]

pkt = Ether(src="00:00:00:00:00:01", dst="00:00:00:00:00:02") / \
      IP(proto=169, src="10.0.0.1", dst="10.0.0.2") / \
      MySec()

sendp(pkt, iface="h1-eth0")
```

### Verificación
| Paso | Comando | Resultado esperado |
|---|---|---|
| 1 | `mininet> pingall` | h1↔h2 OK (tráfico normal via `l2_exact_table`) |
| 2 | `mininet> h1 python3 send_mysec.py` | Paquete MySec enviado |
| 3 | `mininet> h1 tcpdump -i h1-eth0 -c 1 ip proto 169` | Paquete de retorno con proto 169 |
| 4 | Inspeccionar timestamps en el paquete de retorno | `process_time_sw1` y `process_time_sw2` > 0 |

---

## Exercise-4 — VLAN 802.1Q Tagging/Untagging

### Objetivo
Segmentar tráfico entre dos switches usando VLANs. Los hosts envían tráfico sin tag; al llegar al switch local, se añade un tag VLAN 802.1Q según el puerto de ingreso. El trunk entre switches transporta tramas taggeadas. Al llegar al switch remoto, se quita el tag y se reenvía al host correcto.

### Topología
```
  VLAN 10 (0x00a)               VLAN 10 (0x00a)
  h1 (10.10.10.1/29, MAC 01)   h3 (10.10.10.2/29, MAC 03)
    │ port1                        │ port1
    s1 ──── trunk (port3) ──── s2
    │ port2                        │ port2
  h2 (20.20.20.1/26, MAC 02)   h4 (20.20.20.2/26, MAC 04)
  VLAN 20 (0x014)               VLAN 20 (0x014)

  s1 thrift: 9090              s2 thrift: 9091
```
- 2 switches, 4 hosts
- P4: `p4src/main.p4`
- Links: 5 Mbps / 5 ms / 1% loss

### Lógica VLAN
| Tabla | Cuándo | Acción |
|---|---|---|
| `set_vlan_tag` | Paquete IPv4 sin tag (desde host local) | `setValid()` vlan header, asigna VID según ingress port (1→VLAN_10, 2→VLAN_20), envía a port 3 (trunk) |
| `extract_vlan_tag` | Paquete 802.1Q taggeado (desde trunk) | Lee `dst_addr + vid`, reenvía al host local, ejecuta `setInvalid()` para quitar tag |

### Headers P4
```
header vlan_802_1q_t {
  bit<3>  pri;        // Priority Code Point
  bit<1>  cfi;        // Drop Eligible Indicator
  bit<12> vid;        // VLAN Identifier
  bit<16> ether_type; // Encapsulated EtherType
}
```

### Reglas necesarias

**s1-commands.txt** (thrift port 9090):
```
# Desde access ports → agregar VLAN tag → trunk (port 3)
table_add IngressPipeImpl.set_vlan_tag IngressPipeImpl.add_vlan_tag 00:00:00:00:00:01 => 3
table_add IngressPipeImpl.set_vlan_tag IngressPipeImpl.add_vlan_tag 00:00:00:00:00:02 => 3
# Desde trunk → extraer VLAN tag → host correcto
table_add IngressPipeImpl.extract_vlan_tag IngressPipeImpl.set_egress_port 00:00:00:00:00:01 10 => 1
table_add IngressPipeImpl.extract_vlan_tag IngressPipeImpl.set_egress_port 00:00:00:00:00:02 20 => 2
```

**s2-commands.txt** (thrift port 9091):
```
table_add IngressPipeImpl.set_vlan_tag IngressPipeImpl.add_vlan_tag 00:00:00:00:00:03 => 3
table_add IngressPipeImpl.set_vlan_tag IngressPipeImpl.add_vlan_tag 00:00:00:00:00:04 => 3
table_add IngressPipeImpl.extract_vlan_tag IngressPipeImpl.set_egress_port 00:00:00:00:00:03 10 => 1
table_add IngressPipeImpl.extract_vlan_tag IngressPipeImpl.set_egress_port 00:00:00:00:00:04 20 => 2
```

### Paso a paso
```bash
cd Exercise-4
mkdir -p p4src/build
p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json \
    --p4runtime-files p4src/build/p4info.txt p4src/main.p4

# Terminal 1: topología
sudo python3 mininet/topo.py

# Terminal 2: reglas
simple_switch_CLI --thrift-port 9090 < s1-commands.txt
simple_switch_CLI --thrift-port 9091 < s2-commands.txt
```

### Verificación
| Paso | Comando | Resultado esperado |
|---|---|---|
| 1 | `mininet> h1 ping h3` | OK — ambos en VLAN 10 |
| 2 | `mininet> h2 ping h4` | OK — ambos en VLAN 20 |
| 3 | `mininet> h1 ping h4` | **FALLA** — cross-VLAN, sin match en `extract_vlan_tag` |
| 4 | `mininet> h1 ping h2` | **FALLA** — ambos en s1 pero VLANs distintas |
| 5 | Captura en trunk: `s1 tcpdump -i s1-eth5 -e` | Tramas con ethertype `0x8100` (802.1Q) |
| 6 | `table_dump IngressPipeImpl.set_vlan_tag` | 2 entradas por switch |

---

## Resumen de Puertos Thrift

| Ejercicio | Switches | Thrift Ports |
|---|---|---|
| Exercise-1 | s1 | 9090 |
| Exercise-2 | s1 | 9090 |
| Exercise-2.1 | s1 | 9090 |
| Exercise-2.2 | s1 | 9090 |
| Exercise-3 | s1, s2 | 9090, 9091 |
| Exercise-4 | s1, s2 | 9090, 9091 |

## Estructura de archivos por ejercicio

```
Exercise-N/
├── mininet/
│   ├── topo.py               ← Topología Mininet (ejecutar con sudo)
│   └── p4_mininet.py         ← Clases P4Switch y P4Host para BMv2
├── p4src/
│   ├── main.p4  (o sw_gita.p4)    ← Programa P4 (TODOs del estudiante)
│   └── build/                      ← Directorio generado por p4c
│       ├── bmv2.json               ← JSON compilado para simple_switch
│       └── p4info.txt              ← Información P4Runtime
├── s1-commands.txt                 ← Reglas para s1
└── s2-commands.txt                 ← Reglas para s2 (solo Ex-3, Ex-4)
```

## Referencia rápida: `simple_switch_CLI`

```bash
# Conectar al switch s1 (thrift port 9090)
simple_switch_CLI --thrift-port 9090

# Comandos útiles dentro de la CLI:
table_dump <table_name>              # Ver entradas de una tabla
table_add <table> <action> <match_fields> => <action_params>
table_delete <table> <entry_handle>  # Borrar una entrada
table_clear <table>                  # Vaciar tabla
counter_read <counter_name> <index>  # Leer contadores
```

## Troubleshooting común

| Problema | Solución |
|---|---|
| `p4c-bm2-ss: command not found` | Verificar que se está usando la VM oficial p4lang (https://github.com/p4lang/tutorials/releases) |
| `simple_switch: command not found` | Verificar que se está usando la VM oficial p4lang (https://github.com/p4lang/tutorials/releases) |
| `ERROR: No se encontró bmv2.json` | Compilar primero: `p4c-bm2-ss --p4v 16 -o p4src/build/bmv2.json ...` |
| `Thrift could not connect` | Verificar que `mininet/topo.py` está corriendo. Esperar 2s tras arrancar. |
| `pingall` falla tras instalar reglas | 1) Verificar MAC addresses en las reglas. 2) Revisar port numbers (addLink orden = port asignado). 3) `table_dump` para confirmar entradas. |
| `Error: Invalid table name` | Usar nombre completo con prefijo de control block: `IngressPipeImpl.l2_exact_table` |
| Switch no procesa ARP (Ex-2+) | Si se usa `staticArp()` en `topo.py`, ARP no pasa por el data plane. Verificar que Ex-2+ NO usa `staticArp()`. |
| `Import p4_mininet failed` | Verificar que `p4_mininet.py` está en la carpeta `mininet/` del ejercicio, junto a `topo.py`. |
| `Permission denied` al correr topología | Mininet requiere `sudo python3 mininet/topo.py`. |
| Múltiples ejercicios en paralelo | Cada ejercicio abre thrift ports 9090(+9091). Cerrar el anterior antes de correr otro. |
