/* syn_flood_rl.p4
 *
 * P4 switch for the Reinforcement Learning (RL) exercise.
 *
 * Features:
 *   1. Basic IPv4 forwarding (ip_forward table, exact match).
 *   2. Dynamic firewall (firewall table, LPM on srcAddr).
 *      The RL agent installs/removes entries dynamically to block attacker subnets.
 *   3. Packet counters in registers:
 *      synReg[1]       accumulates incoming SYN packets.
 *      synAckRstReg[1] accumulates SYN-ACK/ACK/RST packets.
 *      The RL agent reads these registers periodically via simple_switch_CLI
 *      to compute the attack rate.
 *
 * Reference: Zheng, C. et al. "QCMP: Load Balancing via In-Network
 * Reinforcement Learning". ACM SIGCOMM FIRA Workshop, 2023.
 */

#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x0800;
const bit<8>  IP_PROTO_TCP = 6;

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    /*
     * TO-DO [1]: Add the EtherType field (bit<16>).
     *            This field identifies the encapsulated Layer 3 protocol
     *            (e.g., 0x0800 = IPv4, 0x0806 = ARP).
     * ─────────────────────────────────────────────────────────────────
     * SOLUTION:
     */
    bit<16>   etherType;
}

header ipv4_t {
    /*
     * TO-DO [2]: Define all IPv4 header fields (RFC 791).
     *            version (4b), ihl (4b), diffserv (8b), totalLen (16b),
     *            identification (16b), flags (3b), fragOffset (13b),
     *            ttl (8b), protocol (8b), hdrChecksum (16b),
     *            srcAddr (32b), dstAddr (32b).
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

header tcp_t {
    /*
     * TO-DO [3]: Define all TCP header fields (RFC 793).
     *            srcPort (16b), dstPort (16b), seqNo (32b), ackNo (32b),
     *            dataOffset (4b), res (3b), ecn (3b),
     *            urg/ack/psh/rst/syn/fin flags (1b each),
     *            window (16b), checksum (16b), urgentPtr (16b).
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

struct metadata {
    bit<32> cntSyn;
    bit<32> cntSynAck;
    bit<1>  toBlock;
}

struct headers {
    ethernet_t ethernet;
    ipv4_t     ipv4;
    tcp_t      tcp;
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
         *            - IPv4 (TYPE_IPV4 = 0x0800) → parse_ipv4
         *            - Any other value            → accept
         * ─────────────────────────────────────────────────────────────────
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
         *            - TCP (IP_PROTO_TCP = 6) → parse_tcp
         *            - Any other value          → accept
         * ─────────────────────────────────────────────────────────────────
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

    // Packet counters for SYN / SYN-ACK telemetry
    // The RL agent reads these periodically:
    //   simple_switch_CLI --thrift-port 9090 <<< "register_read MyIngress.synReg 1"
    //
    // Index 1 is the active slot (index 0 reserved for future use).
    register<bit<32>>(2) synReg;
    register<bit<32>>(2) synAckRstReg;

    action drop() {
        mark_to_drop(standard_metadata);
    }

    // Firewall action: marks the packet for drop
    // The firewall table uses LPM on srcAddr; the RL agent installs
    // entries to block attacker IP ranges (e.g. 10.0.1.64/26).
    action block(bit<1> enabled) {
        meta.toBlock = enabled;
    }

    // Forwarding action
    action forward(bit<9> port, macAddr_t dstMac) {
        hdr.ethernet.dstAddr          = dstMac;
        standard_metadata.egress_spec = port;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    // Dynamic firewall table (installed/modified by the RL agent)
    // The Python controller calls simple_switch_CLI to add/delete entries.
    // LPM allows blocking entire subnets with a single rule.
    table firewall {
        key = {
            hdr.ipv4.srcAddr : lpm;
        }
        actions = {
            block;
            NoAction;
        }
        default_action = NoAction();
    }

    // IPv4 forwarding table (static rules from s1-commands.txt)
    table ip_forward {
        key = {
            hdr.ipv4.dstAddr : exact;
        }
        actions = {
            forward;
            drop;
        }
        default_action = drop();
    }

    apply {
        if (hdr.ipv4.isValid()) {
            // 1. Check firewall: is the source IP blocked?
            firewall.apply();

            if (meta.toBlock == 1) {
                // Packet blocked by RL agent decision → drop
                drop();
            } else {
                // 2. Normal forwarding
                ip_forward.apply();

                /*
                 * TO-DO [6] (RL-specific): Implement the TCP packet counter logic.
                 *
                 *   After forwarding, count TCP packets for RL telemetry:
                 *   - If hdr.tcp is valid AND (syn==1 AND ack==0):
                 *       Read synReg[1], increment by 1, write back.
                 *       This counts incoming SYN packets (potential flood).
                 *   - Else if hdr.tcp is valid AND (ack==1):
                 *       Read synAckRstReg[1], increment by 1, write back.
                 *       This counts ACK/SYN-ACK/RST packets (legit responses).
                 *
                 *   The RL controller reads these two registers to compute the
                 *   SYN excess (syn - synack) and determine the attack state.
                 * ─────────────────────────────────────────────────────────────────
                 * SOLUTION:
                 */
                if (hdr.tcp.isValid()) {
                    if (hdr.tcp.syn == 1 && hdr.tcp.ack == 0) {
                        // Pure SYN packet → possible SYN flood
                        synReg.read(meta.cntSyn, (bit<32>)1);
                        meta.cntSyn = meta.cntSyn + 1;
                        synReg.write((bit<32>)1, meta.cntSyn);
                    } else if (hdr.tcp.ack == 1) {
                        // ACK / SYN-ACK / RST → legitimate response traffic
                        synAckRstReg.read(meta.cntSynAck, (bit<32>)1);
                        meta.cntSynAck = meta.cntSynAck + 1;
                        synAckRstReg.write((bit<32>)1, meta.cntSynAck);
                    }
                }
            }
        }
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
