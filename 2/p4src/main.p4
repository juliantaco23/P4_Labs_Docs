#include <core.p4>
#include <v1model.p4>

#define CPU_PORT 255
#define CPU_CLONE_SESSION_ID 99

typedef bit<9>   port_num_t;
typedef bit<48>  mac_addr_t;
typedef bit<32>  ipv4_addr_t;


const bit<16> ETHERTYPE_IPV4    = 0x0800;

// Exercise 2 TO-DO: Define a symbolic constant for ARP ethertype
const bit<16> ETHERTYPE_ARP    = 0x0806;

/*
    Exercise 2 TO-DO: Define symbolic constants for different ARP fields.
    Refer to RFC 826 for the sizes and reference values.
*/
/*
    ARP constants per RFC 826:
    HTYPE  = 1      → Ethernet hardware type
    PTYPE  = 0x0800 → IPv4 protocol type
    HLEN   = 6      → MAC address is 6 bytes (48 bits)
    PLEN   = 4      → IPv4 address is 4 bytes (32 bits)
    REQ    = 1      → ARP Request operation code
    REPLY  = 2      → ARP Reply operation code
*/
const bit<16> ARP_HTYPE = 0x0001; // Ethernet Hardware type is 1
const bit<16> ARP_PTYPE = 0x0800; // IPv4 Protocol type
const bit<8>  ARP_HLEN  = 6;     // MAC address length in bytes
const bit<8>  ARP_PLEN  = 4;     // IPv4 address length in bytes
const bit<16> ARP_REQ   = 1;     // ARP Request
const bit<16> ARP_REPLY = 2;     // ARP Reply


//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
//+++++++++++++++++++++++++++ HEADER DEFINITIONS ++++++++++++++++++++++++++
//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

header ethernet_t {
        mac_addr_t  dst_addr;
        mac_addr_t  src_addr;
        bit<16>    ether_type;
}

/*
  Exercise 2 TO-DO: Define a type for the header of an ARP packet.
  Remember that an ARP packet contains the following fields:
  Hardware Type, Prtocol Type, Hardware Length, Protocol Length,
  Operation Code, Source Hardware Address, Source Protocol Address,
  Target Hardware Address and Target Potocol Address.
  Refer to RFC 826 for the details on each of these fields


  ARP packet header per RFC 826.
  Field order and bit widths match the wire format exactly:
    h_type  : hardware type (16b)  — 1 for Ethernet
    p_type  : protocol type (16b)  — 0x0800 for IPv4
    h_len   : hw addr length (8b)  — 6 bytes for MAC
    p_len   : proto addr length (8b)— 4 bytes for IPv4
    oper    : operation (16b)      — 1=request, 2=reply
    src_mac : sender hardware addr (48b)
    src_ip  : sender protocol addr (32b)
    dst_mac : target hardware addr (48b)
    dst_ip  : target protocol addr (32b) ← used as key in arp_exact table
*/
header arp_t {
    bit<16>      h_type;   // Hardware type
    bit<16>      p_type;   // Protocol type
    bit<8>       h_len;    // Hardware address length
    bit<8>       p_len;    // Protocol address length
    bit<16>      oper;     // Operation: ARP_REQ or ARP_REPLY
    mac_addr_t   src_mac;  // Sender Hardware Address (SHA)
    ipv4_addr_t  src_ip;   // Sender Protocol Address (SPA)
    mac_addr_t   dst_mac;  // Target Hardware Address (THA)
    ipv4_addr_t  dst_ip;   // Target Protocol Address (TPA)
}

header ipv4_t {
        bit<4>    version;
        bit<4>    ihl;
        bit<6>    dscp;
        bit<2>    ecn;
        bit<16>   total_len;
        bit<16>   identification;
        bit<3>    flags;
        bit<13>   frag_offset;
        bit<8>    ttl;
        bit<8>    protocol;
        bit<16>   hdr_checksum;
        ipv4_addr_t src_addr;
        ipv4_addr_t dst_addr;
}


@controller_header("packet_in")
header cpu_in_header_t {
        port_num_t  ingress_port;
        bit<7>      _pad;
}

@controller_header("packet_out")
header cpu_out_header_t {
        port_num_t  egress_port;
        bit<7>      _pad;
}


struct parsed_headers_t {
        ethernet_t ethernet;
        /*
                Exercise 2 TO-DO: Include the ARP header in the set of
                headers recognized by this switch
        */
        // ARP header added for Exercise 2 — parsed when ether_type == 0x0806
        arp_t arp;
        ipv4_t ipv4;
        cpu_out_header_t cpu_out;
        cpu_in_header_t cpu_in;
}


struct local_metadata_t {
        @field_list(1)
        bit<9>    port1;
        bit<9>    port2;
}


//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
//+++++++++++++++++++++++++++++++++ PARSER ++++++++++++++++++++++++++++++++
//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


parser ParserImpl (packet_in packet,
                   out parsed_headers_t hdr,
                   inout local_metadata_t local_metadata,
                   inout standard_metadata_t standard_metadata){

        state start {
                transition select(standard_metadata.ingress_port) {
                        CPU_PORT: parse_packet_out;
                        default: parse_ethernet;
                }
        }

        state parse_packet_out {
                packet.extract(hdr.cpu_out);
                transition parse_ethernet;
        }


        /*
                Exercise 2 TO-DO: Perform three changes to the parse_ethernet
                state:
                1. Create a transition selection based on the ether_type field
                   of the ethernet header
                2. For IPv4 packets, transition to the parse_ipv4 state
                3. For ARP packets, trasition to the parse_arp state.
                Note: Leave the parse_ipv4 state as default transition
        */

        // parse_ethernet: after extracting the Ethernet header, branch on
        // EtherType so that IPv4 and ARP packets reach their own parse states.
        // All other frame types are accepted but no further header is parsed.
        state parse_ethernet {
                packet.extract(hdr.ethernet);
                transition select(hdr.ethernet.ether_type) {
                        ETHERTYPE_IPV4: parse_ipv4;
                        ETHERTYPE_ARP:  parse_arp;
                        default:        accept;
                }
        }


        state parse_ipv4 {
                packet.extract(hdr.ipv4);
                transition accept;
        }

        // parse_arp: extract the ARP header then select on the operation code.
        // Only ARP Requests (oper == 1) are accepted for processing in the
        // ingress pipeline. ARP Replies and anything else are also accepted
        // (the parser cannot drop) but the arp_exact table won't match them.
        state parse_arp {
                packet.extract(hdr.arp);
                transition select(hdr.arp.oper) {
                        ARP_REQ: accept;
                        default: accept;
                }
        }
}

//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
//++++++++++++++++++++++++++++++++ CHECKSUM +++++++++++++++++++++++++++++++
//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

control VerifyChecksumImpl(inout parsed_headers_t hdr,
                           inout local_metadata_t local_metadata){

        apply { /* EMPTY */ }
}

//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
//+++++++++++++++++++++++++++ INGRESS PROCESSING ++++++++++++++++++++++++++
//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

control IngressPipeImpl(inout parsed_headers_t    hdr,
                        inout local_metadata_t    local_metadata,
                        inout standard_metadata_t standard_metadata){

        // --- DROP  -----------------------------------------------------------
        action drop() {
                mark_to_drop(standard_metadata);
        }

        // --- CPU  ------------------------------------------------------------
        action send_to_cpu() {
                standard_metadata.egress_spec = CPU_PORT;
        }

        action clone_to_cpu() {
                clone_preserving_field_list(CloneType.I2E, CPU_CLONE_SESSION_ID,1);
        }

        // --- ACL TABLE  ------------------------------------------------------

        table acl_table {
                key = {
                        standard_metadata.ingress_port: ternary;
                        hdr.ethernet.dst_addr:          ternary;
                        hdr.ethernet.src_addr:          ternary;
                        hdr.ethernet.ether_type:        ternary;
                }

                actions = {
                        send_to_cpu;
                        clone_to_cpu;
                        drop;
                }

                @name("acl_table_counter")
                counters = direct_counter(CounterType.packets_and_bytes);
        }


        // --- l2_exact_table --------------------------------------------------
        action set_egress_port(port_num_t port_num){
                standard_metadata.egress_spec = port_num;
        }



        table l2_exact_table {
                key = {
                        hdr.ethernet.dst_addr: exact;
                }

                actions = {
                        set_egress_port;
                        @defaultonly drop;
                }

                @name("l2_exact_counter")
                counters = direct_counter(CounterType.packets_and_bytes);

        }


        /*
                Exercise 2 TO-DO: Create an action to build an ARP reply.
                The name of this action will be arp_reply.
                This action will receive a MAC address provided by the
                table match. Keep in mind the following things for this
                action

                1. The operation code is the one corresponding to an ARP
                   reply.
                2. The Target Hardware Address will be set to the source
                   MAC address.
                3. The Source Hardware Address will be set to the MAC address
                   provided by the table match (i.e. the parameter of the
                   action).
                4. The Source Protocol Address will be set to the
                   Target Protocol Address contained in the request
                5. The destination address of the Ethernet header will be set
                   to its source address (to create a reply).
                6. The source address of the Ethernet header will be set to
                   the MAC address provided by the table match (i.e. the
                   parameter of the action).
                7. Return the reply to the same port where it came from by
                   setting the egress_spec field of the standard_metadata
                   structure. (Hint: The ingress port is available in the
                   ingress_port field of this structure, and it has been set
                   at the ParserImpl)
        */


        // arp_reply: transforms an ARP Request into an ARP Reply in-place.
        // request_mac is the MAC address the table lookup resolved for the
        // queried IP (hdr.arp.dst_ip).  The action performs 7 assignments:
        //
        //   ARP operation  : REQUEST(1) → REPLY(2)
        //   THA            : set to old SHA (who was asking)
        //   TPA            : set to old SPA (the requester’s IP) — uses tmp field
        //   SHA            : set to request_mac (the answer MAC)
        //   SPA            : set to old TPA (the IP being replied about)
        //   Ethernet dst   : set to old Ethernet src (send back to requester)
        //   Ethernet src   : set to request_mac
        //   egress_spec    : set to ingress_port (return to sender’s port)
        //
        // NOTE: IP swap needs a temporary because P4 assignments are sequential.
        action arp_reply(mac_addr_t request_mac) {
                // 1. Mark as reply
                hdr.arp.oper            = ARP_REPLY;
                // 2. THA ← old SHA (requester’s MAC)
                hdr.arp.dst_mac         = hdr.arp.src_mac;
                // 3. SHA ← request_mac (our MAC — the answer)
                hdr.arp.src_mac         = request_mac;
                // 4. IP swap: save old SPA before overwriting
                local_metadata.arp_tmp_ip = hdr.arp.src_ip;
                // 5. SPA ← old TPA (the IP we are claiming ownership of)
                hdr.arp.src_ip          = hdr.arp.dst_ip;
                // 6. TPA ← old SPA (send the reply to the requester’s IP)
                hdr.arp.dst_ip          = local_metadata.arp_tmp_ip;
                // 7. Ethernet: flip src/dst, set src to request_mac
                hdr.ethernet.dst_addr   = hdr.ethernet.src_addr;
                hdr.ethernet.src_addr   = request_mac;
                // 8. Return reply to the same port the request arrived on
                standard_metadata.egress_spec = standard_metadata.ingress_port;
        }


        /*
                Exercise 2 TO-DO: Define the arp_exact table. This table
                will be composed of a key to match the Target Protocol Address
                field of the ARP header, in exact way. The actions for this
                table will be the arp_reply, and the drop action. The drop
                action will be the default action
        */


        // arp_exact: matches the Target Protocol Address (TPA) of an ARP
        // Request exactly.  A successful match means the switch knows the MAC
        // for that IP and can generate the ARP Reply itself without involving
        // the controller.  Unmatched ARPs are dropped by the default action.
        table arp_exact {
                key = {
                        // TPA = hdr.arp.dst_ip (the IP being queried)
                        hdr.arp.dst_ip: exact;
                }
                actions = {
                        arp_reply;
                        @defaultonly drop;
                }
                @name("arp_exact_counter")
                counters = direct_counter(CounterType.packets_and_bytes);
                default_action = drop();
        }




        // --- APPLY -----------------------------------------------------------


        apply {

                if (hdr.cpu_out.isValid()) {
                        standard_metadata.egress_spec = hdr.cpu_out.egress_port;
                        hdr.cpu_out.setInvalid();
                        exit;
                }

                //l2_exact_table.apply();

        /*
                Exercise 2 TO-DO: Modify the apply block according to the
                following algorithm:
                1. If the packet contains valid Ethernet and IPv4 headers,
                   then apply the l2_exact_table which will forward packets
                   according the destination MAC address.
                2. Otherwise, if the packet contains an Ethernet frame,
                   apply the arp_exact table in order to reply ARP requests.
                Hint 1: You might want to comment out the non-conditioned
                application of l2_exact_table.
                Hint 2: For Step 2, you need to check the value of the field
                containing the type of content of the frame.

        */


                // Algorithm (Exercise 2):
                // Branch 1 \u2014 IPv4 unicast: both Ethernet and IPv4 headers must be
                //   valid. The l2_exact_table forwards based on destination MAC.
                // Branch 2 \u2014 ARP: only the Ethernet header is valid and its
                //   ether_type signals ARP (0x0806). The arp_exact table looks up
                //   the target IP and generates an ARP reply in-switch, so the
                //   request never has to go to the controller or to the host.
                // acl_table always runs so that LLDP/BDDP/ARP-to-CPU entries
                //   inserted by ONOS can still clone/send packets to the CPU.
                if (hdr.ethernet.isValid() && hdr.ipv4.isValid()) {
                        // IPv4 packet \u2014 forward by destination MAC
                        l2_exact_table.apply();
                } else if (hdr.ethernet.isValid() &&
                           hdr.ethernet.ether_type == ETHERTYPE_ARP) {
                        // ARP Request \u2014 reply in-switch if we know the MAC
                        arp_exact.apply();
                }

                acl_table.apply();

        }
}


//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
//++++++++++++++++++++++++++++ EGRESS PROCESSING ++++++++++++++++++++++++++
//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


control EgressPipeImpl (inout parsed_headers_t hdr,
                        inout local_metadata_t local_metadata,
                        inout standard_metadata_t standard_metadata){


        // --- APPLY ---------------------------------------------------

        apply {

                if (standard_metadata.egress_port == CPU_PORT) {
                        hdr.cpu_in.setValid();
                        hdr.cpu_in.ingress_port=standard_metadata.ingress_port;
                        exit;
                }
        }

}


//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
//++++++++++++++++++++++++++++++++ CHECKSUM +++++++++++++++++++++++++++++++
//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


control ComputeChecksumImpl(inout parsed_headers_t hdr,
                            inout local_metadata_t local_metadata) {
        apply { /* EMPTY */ }
}


//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
//++++++++++++++++++++++++++++++++ DEPARSER +++++++++++++++++++++++++++++++
//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


control DeparserImpl(packet_out packet, in parsed_headers_t hdr) {
        apply {
                packet.emit(hdr.cpu_in);
                packet.emit(hdr.ethernet);

        /*
                Exercise 1 TO-DO: In order to get a successfull response,
                modify this method to emit a packet containing an ipv4
                header.
        */

        packet.emit(hdr.ipv4);

        /*
                Exercise 2 TO-DO: Include the ARP header in outgoing packets
                where applicable
        */
        packet.emit(hdr.arp);

        }
}


//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
//+++++++++++++++++++++++++++++++++ SWITCH ++++++++++++++++++++++++++++++++
//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


V1Switch(
        ParserImpl(),
        VerifyChecksumImpl(),
        IngressPipeImpl(),
        EgressPipeImpl(),
        ComputeChecksumImpl(),
        DeparserImpl()
) main