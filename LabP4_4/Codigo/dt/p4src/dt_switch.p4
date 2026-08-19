/* dt_switch.p4
 *
 * Implementation of a Decision Tree inside a programmable P4 switch.
 * The tree classifies TCP traffic based on three packet features:
 *   Feature 1: IP Protocol      (hdr.ipv4.protocol)
 *   Feature 2: TCP Source Port  (hdr.tcp.srcPort)
 *   Feature 3: TCP Dest Port    (hdr.tcp.dstPort)
 *
 * Each table (feature1_exact, feature2_exact, feature3_exact) assigns an
 * integer ("action select") to each feature according to the tree's thresholds.
 * The ipv4_exact table combines the three values to determine the output port.
 *
 * Based on: Xiong & Zilberman, "Do Switches Dream of Machine Learning?
 * Toward In-Network Classification" (2019), via the IIsy artifact and the
 * GITA ONOSP4-tutorial DecisionTrees2 exercise.
 *
 * Adaptation for the TFG project — Internet of the Future, Universidad de Antioquia.
 * P4Runtime/ONOS dependency removed; rules are installed via
 * simple_switch_CLI (file s1-commands.txt).
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
     * TO-DO [1]: Add the EtherType field (bit<16>).
     *            This field indicates the encapsulated Layer 3 protocol.
     * ─────────────────────────────────────────────────────────────────
     * SOLUTION: Declare the field as bit<16> etherType.
     */
    bit<16> etherType;
}

// ── IPv4 ─────────────────────────────────────────────────────────────────
header ipv4_t {
    /*
     * TO-DO [2]: Define all IPv4 header fields (RFC 791).
     *            Remember: version (4b), ihl (4b), diffserv (8b),
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
     * TO-DO [3]: Define all TCP header fields (RFC 793).
     *            srcPort (16b), dstPort (16b), seqNo (32b), ackNo (32b),
     *            dataOffset (4b), res (3b), ecn (3b), flags urg/ack/psh/
     *            rst/syn/fin (1b each), window (16b), checksum (16b),
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

// ── Metadata (partial outputs from the decision tree) ───────────────────
// Each field stores the bucket assigned by its feature table.
// Combining them in ipv4_exact yields the final classification.
struct metadata {
    bit<14> action_select1;   // output of feature1_exact (IP proto)
    bit<14> action_select2;   // output of feature2_exact (TCP src port)
    bit<14> action_select3;   // output of feature3_exact (TCP dst port)
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
         * TO-DO [4]: Define transitions based on the etherType field:
         *            - If IPv4 (TYPE_IPV4 = 0x0800) → parse_ipv4
         *            - Otherwise → accept
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
         * TO-DO [5]: Define transitions based on hdr.ipv4.protocol:
         *            - If TCP (6) → parse_tcp
         *            - Otherwise → accept
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
    // Used by ipv4_exact to rewrite the destination MAC and select the output port.
    action ipv4_forward(macAddr_t dstAddr, egressSpec_t port) {
        standard_metadata.egress_spec = port;
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    // ── Feature actions ───────────────────────────────────────────────────
    // Each action receives the bucket value assigned to the packet by the tree
    // and stores it in the corresponding metadata field.

    action set_actionselect1(bit<14> featurevalue1) {
        meta.action_select1 = featurevalue1;
    }

    action set_actionselect2(bit<14> featurevalue2) {
        meta.action_select2 = featurevalue2;
    }

    action set_actionselect3(bit<14> featurevalue3) {
        /*
         * TO-DO [6]: Implement this action.
         *            Store the featurevalue3 argument in the
         *            action_select3 field of the metadata struct.
         * ─────────────────────────────────────────────────────────────
         * SOLUTION:
         */
        meta.action_select3 = featurevalue3;
    }

    // ── Feature tables ────────────────────────────────────────────────────
    // Each table represents a decision tree node for one feature.
    // The "range" match type allows expressing value intervals [min, max].

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
             * TO-DO [7]: Define the key for this table using the
             *            TCP destination port (hdr.tcp.dstPort).
             *            The match type must be "range" to
             *            express value intervals.
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

    // ── Decision table: combines the three feature selects ────────────────
    // The key is the combination (range, range, range) of the three
    // metadata values. Each decision tree entry generates one row here.
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
            // Step 1: classify Feature 1 (IP protocol) for all IP packets
            feature1_exact.apply();

            /*
             * TO-DO [8]: Implement the logic for Features 2 and 3.
             *
             *   - If the packet is TCP (hdr.tcp.isValid()):
             *       • Apply feature2_exact (TCP src port → action_select2)
             *       • Apply feature3_exact (TCP dst port → action_select3)
             *
             *   - If the packet is NOT TCP (e.g. ICMP):
             *       • Assign action_select2 = 1 (default value)
             *       • Assign action_select3 = 1 (default value)
             *
             *   Rationale: features 2 and 3 are TCP ports. For non-TCP
             *   packets these fields do not exist in the header,
             *   so bucket 1 is assigned (the "default" branch of the tree).
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

        // Step 2: the final table combines the three selects to decide the destination
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
