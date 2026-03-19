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