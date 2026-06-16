/* dt_switch.p4
 *
 * Implementación de un Árbol de Decisión dentro de un switch P4 programable.
 * El árbol clasifica tráfico TCP en función de tres features del paquete:
 *   Feature 1: IP Protocol      (hdr.ipv4.protocol)
 *   Feature 2: TCP Source Port  (hdr.tcp.srcPort)
 *   Feature 3: TCP Dest Port    (hdr.tcp.dstPort)
 *
 * Cada tabla (feature1_exact, feature2_exact, feature3_exact) asigna un
 * valor entero ("action select") a cada feature según los umbrales del árbol.
 * La tabla ipv4_exact combina los tres valores para determinar el puerto de salida.
 *
 * Basado en: Xiong & Zilberman, "Toward Smarter, Adaptive... Programmable
 * Data Planes" (2021), adaptado del repositorio GITA ONOSP4-tutorial.
 *
 * Adaptación para el proyecto TFG — Internet del Futuro, Universidad de Antioquia.
 * Se elimina la dependencia de ONOS/P4Runtime; las reglas se instalan mediante
 * simple_switch_CLI (archivo s1-commands.txt).
 */

#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x0800;
const bit<8>  IP_PROTO_TCP  = 6;
const bit<8>  IP_PROTO_ICMP = 1;

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

// ── Ethernet ─────────────────────────────────────────────────────────────
header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    /*
     * TO-DO [1]: Añade el campo EtherType (bit<16>).
     *            Este campo indica el protocolo de capa 3 encapsulado.
     * ─────────────────────────────────────────────────────────────────
     * SOLUTION: El campo se declara como bit<16> etherType.
     */
    bit<16> etherType;
}

// ── IPv4 ─────────────────────────────────────────────────────────────────
header ipv4_t {
    /*
     * TO-DO [2]: Define todos los campos del encabezado IPv4 (RFC 791).
     *            Recuerda: version (4b), ihl (4b), diffserv (8b),
     *            totalLen (16b), identification (16b), flags (3b),
     *            fragOffset (13b), ttl (8b), protocol (8b),
     *            hdrChecksum (16b), srcAddr (32b), dstAddr (32b).
     * ─────────────────────────────────────────────────────────────────
     * SOLUTION:
     */
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}

// ── TCP ──────────────────────────────────────────────────────────────────
header tcp_t {
    /*
     * TO-DO [3]: Define todos los campos del encabezado TCP (RFC 793).
     *            srcPort (16b), dstPort (16b), seqNo (32b), ackNo (32b),
     *            dataOffset (4b), res (3b), ecn (3b), flags urg/ack/psh/
     *            rst/syn/fin (1b c/u), window (16b), checksum (16b),
     *            urgentPtr (16b).
     * ─────────────────────────────────────────────────────────────────
     * SOLUTION:
     */
    bit<16> srcPort;
    bit<16> dstPort;
    bit<32> seqNo;
    bit<32> ackNo;
    bit<4>  dataOffset;
    bit<3>  res;
    bit<3>  ecn;
    bit<1>  urg;
    bit<1>  ack;
    bit<1>  psh;
    bit<1>  rst;
    bit<1>  syn;
    bit<1>  fin;
    bit<16> window;
    bit<16> checksum;
    bit<16> urgentPtr;
}

// ── Metadata (salidas parciales del árbol de decisión) ───────────────────
// Cada campo almacena el "bucket" asignado por su feature table.
// Al combinarlos en ipv4_exact se obtiene la clasificación final.
struct metadata {
    bit<14> action_select1;   // resultado de feature1_exact (IP proto)
    bit<14> action_select2;   // resultado de feature2_exact (TCP src port)
    bit<14> action_select3;   // resultado de feature3_exact (TCP dst port)
}

struct headers {
    ethernet_t   ethernet;
    ipv4_t       ipv4;
    tcp_t        tcp;
}

/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        /*
         * TO-DO [4]: Define las transiciones según el campo etherType:
         *            - Si es IPv4 (TYPE_IPV4 = 0x0800) → parse_ipv4
         *            - En cualquier otro caso → accept
         * ─────────────────────────────────────────────────────────
         * SOLUTION:
         */
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            default:   accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        /*
         * TO-DO [5]: Define las transiciones según hdr.ipv4.protocol:
         *            - Si es TCP (6) → parse_tcp
         *            - En cualquier otro caso → accept
         * ─────────────────────────────────────────────────────────
         * SOLUTION:
         */
        transition select(hdr.ipv4.protocol) {
            IP_PROTO_TCP: parse_tcp;
            default:      accept;
        }
    }

    state parse_tcp {
        packet.extract(hdr.tcp);
        transition accept;
    }
}

/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply { }
}

/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    action drop() {
        mark_to_drop(standard_metadata);
    }

    // ── Forwarding L2/L3 ─────────────────────────────────────────────────
    // Usada por ipv4_exact para reescribir la MAC destino y seleccionar el puerto.
    action ipv4_forward(macAddr_t dstAddr, egressSpec_t port) {
        standard_metadata.egress_spec = port;
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    // ── Feature actions ───────────────────────────────────────────────────
    // Cada acción recibe el valor de "bucket" asignado al paquete por el árbol
    // y lo almacena en el campo correspondiente de metadata.

    action set_actionselect1(bit<14> featurevalue1) {
        meta.action_select1 = featurevalue1;
    }

    action set_actionselect2(bit<14> featurevalue2) {
        meta.action_select2 = featurevalue2;
    }

    action set_actionselect3(bit<14> featurevalue3) {
        /*
         * TO-DO [6]: Implementa esta acción.
         *            Debe almacenar el argumento featurevalue3 en el campo
         *            action_select3 de la estructura de metadata.
         * ─────────────────────────────────────────────────────────────
         * SOLUTION:
         */
        meta.action_select3 = featurevalue3;
    }

    // ── Feature tables ────────────────────────────────────────────────────
    // Cada tabla representa un nodo del árbol de decisión para un feature.
    // El tipo de matching "range" permite expresar intervalos [min, max].

    table feature1_exact {
        key = {
            hdr.ipv4.protocol : range;   // Feature 1: IP protocol
        }
        actions = {
            NoAction;
            set_actionselect1;
        }
        size = 1024;
        @name("feature1_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    table feature2_exact {
        key = {
            hdr.tcp.srcPort : range;     // Feature 2: TCP source port
        }
        actions = {
            NoAction;
            set_actionselect2;
        }
        size = 1024;
        @name("feature2_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    table feature3_exact {
        key = {
            /*
             * TO-DO [7]: Define la clave de esta tabla usando el
             *            puerto destino TCP (hdr.tcp.dstPort).
             *            El tipo de matching debe ser "range" para
             *            poder expresar intervalos de valores.
             * ─────────────────────────────────────────────────────
             * SOLUTION:
             */
            hdr.tcp.dstPort : range;     // Feature 3: TCP destination port
        }
        actions = {
            NoAction;
            set_actionselect3;
        }
        size = 1024;
        @name("feature3_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    // ── Decision table: combina los tres feature selects ─────────────────
    // La clave es la combinación (range, range, range) de los tres valores
    // de metadata. Cada entrada del árbol de decisión genera una fila aquí.
    table ipv4_exact {
        key = {
            meta.action_select1 : range;
            meta.action_select2 : range;
            meta.action_select3 : range;
        }
        actions = {
            ipv4_forward;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = drop();
        @name("ipv4_exact_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    apply {
        if (hdr.ipv4.isValid()) {
            // Paso 1: clasificar Feature 1 (IP protocol) para todos los paquetes IP
            feature1_exact.apply();

            /*
             * TO-DO [8]: Implementa la lógica para Features 2 y 3.
             *
             *   - Si el paquete es TCP (hdr.tcp.isValid()):
             *       • Aplica feature2_exact (TCP src port → action_select2)
             *       • Aplica feature3_exact (TCP dst port → action_select3)
             *
             *   - Si el paquete NO es TCP (ej. ICMP):
             *       • Asigna action_select2 = 1 (valor por defecto)
             *       • Asigna action_select3 = 1 (valor por defecto)
             *
             *   Justificación: las features 2 y 3 son puertos TCP. Para
             *   paquetes no-TCP estos campos no existen en el encabezado,
             *   por lo que se asigna el bucket 1 (rama "default" del árbol).
             * ──────────────────────────────────────────────────────────────
             * SOLUTION:
             */
            if (hdr.tcp.isValid()) {
                feature2_exact.apply();
                feature3_exact.apply();
            } else {
                meta.action_select2 = 1;
                meta.action_select3 = 1;
            }
        }

        // Paso 2: la tabla final combina los tres selects para decidir el destino
        ipv4_exact.apply();
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply { }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.tcp);
    }
}

/*************************************************************************
***********************  S W I T C H  ************************************
*************************************************************************/

V1Switch(
    MyParser(),
    MyVerifyChecksum(),
    MyIngress(),
    MyEgress(),
    MyComputeChecksum(),
    MyDeparser()
) main;
