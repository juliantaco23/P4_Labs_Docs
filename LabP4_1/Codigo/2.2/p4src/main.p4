#include <core.p4>
#include <v1model.p4>

// Description taken from NGSDN-TUTORIAL
// CPU_PORT specifies the P4 port number associated to controller packet-in and
// packet-out. All packets forwarded via this port will be delivered to the
// controller as P4Runtime PacketIn messages. Similarly, PacketOut messages from
// the controller will be seen by the P4 pipeline as coming from the CPU_PORT.
#define CPU_PORT 255

// Description taken from NGSDN-TUTORIAL
// CPU_CLONE_SESSION_ID specifies the mirroring session for packets to be cloned
// to the CPU port. Packets associated with this session ID will be cloned to
// the CPU_PORT as well as being transmitted via their egress port (set by the
// bridging/routing/acl table). For cloning to work, the P4Runtime controller
// needs first to insert a CloneSessionEntry that maps this session ID to the
// CPU_PORT.
#define CPU_CLONE_SESSION_ID 99

// Type aliases defined for convenience
typedef bit<9>   port_num_t;
typedef bit<48>  mac_addr_t;
typedef bit<32>  ipv4_addr_t;
typedef bit<16>  l4_port_t;


const bit<16> ETHERTYPE_IPV4 = 0x0800;
const bit<16> ETHERTYPE_ARP = 0x0806;

// Exercise 2.2 TO-DO: Define the symbolic constant for the TCP protocol
// number, i.e. the value carried in the protocol field of the IPv4 header
// for a TCP segment (see RFC 793).

const bit<16> ARP_HTYPE = 0x0001; //Ethernet Hardware type is 1
const bit<16> ARP_PTYPE = ETHERTYPE_IPV4; //Protocol used for ARP is IPV4
const bit<8>  ARP_HLEN  = 6; //Ethernet address size is 6 bytes
const bit<8>  ARP_PLEN  = 4; //IP address size is 4 bytes
const bit<16> ARP_REQ = 1; //Operation 1 is request
const bit<16> ARP_REPLY = 2; //Operation 2 is reply


// Type definition for convenience. Counters are defined as 32 bits
typedef bit<32> PacketCounter_t;

const bit<4> MAX_PORT = 15;


//------------------------------------------------------------------------------
// HEADER DEFINITIONS
//------------------------------------------------------------------------------

header ethernet_t {
    mac_addr_t  dst_addr;
    mac_addr_t  src_addr;
    bit<16>     ether_type;
}


/*
  ARP packet header per RFC 826.
  Field order and bit widths match the wire format exactly:
    h_type  : hardware type (16b)  - 1 for Ethernet
    p_type  : protocol type (16b)  - 0x0800 for IPv4
    h_len   : hw addr length (8b)  - 6 bytes for MAC
    p_len   : proto addr length (8b)- 4 bytes for IPv4
    op_code : operation (16b)      - 1=request, 2=reply
    src_mac : sender hardware addr (48b)
    src_ip  : sender protocol addr (32b)
    dst_mac : target hardware addr (48b)
    dst_ip  : target protocol addr (32b) - used as key in arp_exact table
*/
header arp_t {
  bit<16>   h_type;
  bit<16>   p_type;
  bit<8>    h_len;
  bit<8>    p_len;
  bit<16>   op_code;
  mac_addr_t src_mac;
  bit<32> src_ip;
  mac_addr_t dst_mac;
  bit<32> dst_ip;
  }


header ipv4_t {
    bit<4>   version;
    bit<4>   ihl;
    bit<6>   dscp;
    bit<2>   ecn;
    bit<16>  total_len;
    bit<16>  identification;
    bit<3>   flags;
    bit<13>  frag_offset;
    bit<8>   ttl;
    bit<8>   protocol;
    bit<16>  hdr_checksum;
    bit<32>  src_addr;
    bit<32>  dst_addr;
}

/*
    Exercise 2.2 TO-DO: Define the TCP header according RFC 793. 
    For the definition of this header, you might omit the options
    fields since it is considered for this exercise. Also, it is
    recommended to create individual fields for the six operation
    bits of the protocol. Keep in mind that these fields must be
    defined in order.

    The rest of the program (ComputeChecksumImpl) already refers to
    the fields of this header, so the names and the order below are
    mandatory. The widths of the fields that make up the first part
    of the header must add up to 16 bits, since they are packed
    together in the same 16-bit word of the TCP header:

        src_port    bit<16>   source port
        dst_port    bit<16>   destination port
        seq_no      bit<32>   sequence number
        ack_no      bit<32>   acknowledgment number
        data_offset bit<4>    data offset (header length in 32-bit words)
        res         bit<3>    reserved
        ecn         bit<3>    ECN / NS bits
        urg         bit<1>    URG flag
        ack         bit<1>    ACK flag
        psh         bit<1>    PSH flag
        rst         bit<1>    RST flag
        syn         bit<1>    SYN flag
        fin         bit<1>    FIN flag
        window      bit<16>   window size
        checksum    bit<16>   checksum
        urgent_ptr  bit<16>   urgent pointer
*/
header tcp_t {
    // Exercise 2.2 TO-DO: define the RFC 793 TCP fields listed above.
}

// Description taken from NGSDN-TUTORIAL
// Packet-in header. Prepended to packets sent to the CPU_PORT and used by the
// P4Runtime server (Stratum) to populate the PacketIn message metadata fields.
// Here we use it to carry the original ingress port where the packet was
// received.
@controller_header("packet_in")
header cpu_in_header_t {
    port_num_t  ingress_port;
    bit<7>      _pad;
}

// Description taken from NGSDN-TUTORIAL
// Packet-out header. Prepended to packets received from the CPU_PORT. Fields of
// this header are populated by the P4Runtime server based on the P4Runtime
// PacketOut metadata fields. Here we use it to inform the P4 pipeline on which
// port this packet-out should be transmitted.
@controller_header("packet_out")
header cpu_out_header_t {
    port_num_t  egress_port;
    bit<7>      _pad;
}

struct parsed_headers_t {
    cpu_out_header_t cpu_out;
    cpu_in_header_t cpu_in;
    ethernet_t ethernet;
    arp_t arp;
    ipv4_t ipv4;
    // Exercise 2.2 TO-DO: add the TCP header instance.
}

struct local_metadata_t {
        @field_list(1)
        port_num_t ingress_port;

        bit<1>  is_tcp_syn;
        bit<16> tcp_src_port;
        bit<16> tcp_dst_port;
        bit<32> ip_src_addr;
        bit<32> ip_dst_addr;
        mac_addr_t eth_src_addr;
        mac_addr_t eth_dst_addr;
        bit<32> tcp_seq_no;
        bit<16> l4Len;
}


//------------------------------------------------------------------------------
// INGRESS PIPELINE
//------------------------------------------------------------------------------

parser ParserImpl (packet_in packet,
                   out parsed_headers_t hdr,
                   inout local_metadata_t local_metadata,
                   inout standard_metadata_t standard_metadata)
{
    state start {
        local_metadata.ingress_port = standard_metadata.ingress_port;
        transition select(standard_metadata.ingress_port) {
            CPU_PORT: parse_packet_out;
            default: parse_ethernet;
        }
    }

    state parse_packet_out {
        packet.extract(hdr.cpu_out);
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.ether_type){
            ETHERTYPE_IPV4: parse_ipv4;
            ETHERTYPE_ARP: parse_arp;
            default: accept;
        }
    }

    state parse_arp {
        packet.extract(hdr.arp);
        transition select(hdr.arp.op_code) {
                ARP_REQ: accept;
        }
    }

    /* 
        Exercise 2.2 TO-DO: Modify the parse_ipv4 to consider the following things:
        1. Do a transition on the protocol field of the IPv4 header
        2. If the datagram contans a TCP packet, transition to a state to parse it.
        3. By default, all the remaining IPv4 traffic should be accepted
    */

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        // Exercise 2.2 TO-DO: add the protocol transition described above.

    }

    /*
        Exercise 2.2 TO-DO: Define the parse_tcp state. It must:
        1. Extract the TCP header from the packet.
        2. Compute local_metadata.l4Len, i.e. the length of the TCP
           segment in bytes. It is obtained from the IPv4 header as
           total_len minus the length of the IPv4 header in bytes
           (ihl * 4).
        3. Copy into local_metadata the TCP values that the ingress
           control needs later on: is_tcp_syn, tcp_src_port,
           tcp_dst_port, tcp_seq_no, ip_src_addr, ip_dst_addr,
           eth_src_addr and eth_dst_addr.
    */
    // Exercise 2.2 TO-DO: define parse_tcp and preserve needed metadata.


}


control VerifyChecksumImpl(inout parsed_headers_t hdr,
                           inout local_metadata_t meta)
{
    // Description taken from NGSDN-TUTORIAL
    // Not used here. We assume all packets have valid checksum, if not, we let
    // the end hosts detect errors.
    apply { /* EMPTY */ }
}


control IngressPipeImpl (inout parsed_headers_t    hdr,
                         inout local_metadata_t    local_metadata,
                         inout standard_metadata_t standard_metadata) {

    // Two counters are created: One for the match in the creation of
    // TCP sessions and other to account the rejections
    counter((bit<32>)MAX_PORT, CounterType.packets) session_counter;
    counter((bit<32>)1, CounterType.packets) rejects_counter;


    // Drop action shared by many tables.
    action drop() {
        mark_to_drop(standard_metadata);
    }


    // *** L2 BRIDGING
    //
    // --- l2_exact_table (for unicast entries) --------------------------------

    action set_egress_port(port_num_t port_num) {
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
        const default_action = drop;
        // The @name annotation is used here to provide a name to this table
        // counter, as it will be needed by the compiler to generate the
        // corresponding P4Info entity.
        @name("l2_exact_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    // *** ACL
    //
    // Description taken from NGSDN-TUTORIAL
    // Provides ways to override a previous forwarding decision, for example
    // requiring that a packet is cloned/sent to the CPU, or dropped.
    //
    action send_to_cpu() {
        standard_metadata.egress_spec = CPU_PORT;
    }

    action clone_to_cpu() {
        clone_preserving_field_list(CloneType.I2E, CPU_CLONE_SESSION_ID,1);
    }

    table acl_table {
        key = {
            standard_metadata.ingress_port: ternary;
            hdr.ethernet.dst_addr:          ternary;
            hdr.ethernet.src_addr:          ternary;
            hdr.ethernet.ether_type:        ternary;
            hdr.ipv4.protocol:              ternary;
        }
        actions = {
            send_to_cpu;
            clone_to_cpu;
            drop;
        }
        @name("acl_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    action arp_reply(mac_addr_t request_mac) {
      //update operation code from request to reply
      hdr.arp.op_code = ARP_REPLY;

      //reply's dst_mac is the request's src mac
      hdr.arp.dst_mac = hdr.arp.src_mac;

      //reply's dst_ip is the request's src ip
      hdr.arp.src_mac = request_mac;

      //reply's src ip is the request's dst ip
      hdr.arp.src_ip = hdr.arp.dst_ip;

      //update ethernet header
      hdr.ethernet.dst_addr = hdr.ethernet.src_addr;
      hdr.ethernet.src_addr = request_mac;

      //send it back to the same port
      standard_metadata.egress_spec = standard_metadata.ingress_port;

    }

    table arp_exact {
      key = {
        hdr.arp.dst_ip: exact;
      }
      actions = {
        arp_reply;
        drop;
      }
      size = 1024;
      default_action = drop;
    }


    /*
        Exercise 2.2 TO-DO: Create a table to record the TCP Sessions validated
        by the controller. The table must be named tcp_sessions and its key
        contains the IP addresses and the TCP ports, all of them matched
        exactly and in this order:
            1. hdr.ipv4.src_addr
            2. hdr.tcp.src_port
            3. hdr.ipv4.dst_addr
            4. hdr.tcp.dst_port
        The only action of the table is the special NoAction action, so a
        match means "this session is registered and the packet can be
        forwarded". The default action must be drop, so that any packet
        belonging to a session that was not registered by the controller is
        silently discarded in the data plane.
    */
    // Exercise 2.2 TO-DO: implement tcp_sessions.


    apply {

        if (hdr.cpu_out.isValid()) {
            standard_metadata.egress_spec = hdr.cpu_out.egress_port;
            hdr.cpu_out.setInvalid();
            exit;
        }

        /* Exercise 2.2 TO-DO: Process the packets.
           Complete the instructions indicated below.
        */

        // Exercise 2.2 TO-DO: add the TCP branch as the first branch of the
        // chain below. If the packet carries a TCP segment, apply the
        // tcp_sessions table: a match means the session is registered and the
        // packet is forwarded with l2_exact_table, while a miss is dropped by
        // the default action of the table.

        if (hdr.ethernet.isValid() && hdr.ipv4.isValid()) {
                l2_exact_table.apply();
        } else if (hdr.ethernet.ether_type == ETHERTYPE_ARP) {
                arp_exact.apply();
        } else {
                // Otherwise, if the packet does not match anything, mark it to drop it.
                mark_to_drop(standard_metadata);
        }

        // Apply the exact table so that controller takes care
        acl_table.apply();
    }
}


control EgressPipeImpl (inout parsed_headers_t hdr,
                        inout local_metadata_t local_metadata,
                        inout standard_metadata_t standard_metadata) {
    apply {

        if (standard_metadata.egress_port == CPU_PORT) {
            hdr.cpu_in.setValid();
            hdr.cpu_in.ingress_port = local_metadata.ingress_port;
            exit;
        }

    }
}


control ComputeChecksumImpl(inout parsed_headers_t hdr,
                            inout local_metadata_t local_metadata)
{
    apply {

        update_checksum(
            hdr.ipv4.isValid(),
            { 
                hdr.ipv4.version,
                hdr.ipv4.ihl,
                hdr.ipv4.dscp,
                hdr.ipv4.ecn,
                hdr.ipv4.total_len,
                hdr.ipv4.identification,
                hdr.ipv4.flags,
                hdr.ipv4.frag_offset,
                hdr.ipv4.ttl,
                hdr.ipv4.protocol,
                hdr.ipv4.src_addr,
                hdr.ipv4.dst_addr 
            },
            hdr.ipv4.hdr_checksum,
            HashAlgorithm.csum16);

        update_checksum_with_payload(
            hdr.tcp.isValid(),
            { 
                hdr.ipv4.src_addr,
                hdr.ipv4.dst_addr,
                8w0,
                hdr.ipv4.protocol,
                local_metadata.l4Len,
                hdr.tcp.src_port,
                hdr.tcp.dst_port,
                hdr.tcp.seq_no,
                hdr.tcp.ack_no,
                hdr.tcp.data_offset,
                hdr.tcp.res,
                hdr.tcp.ecn,
                hdr.tcp.urg,
                hdr.tcp.ack,
                hdr.tcp.psh,
                hdr.tcp.rst,
                hdr.tcp.syn,
                hdr.tcp.fin,
                hdr.tcp.window,
                hdr.tcp.urgent_ptr
            },
            hdr.tcp.checksum, HashAlgorithm.csum16);      

    }
}


control DeparserImpl(packet_out packet, in parsed_headers_t hdr) {
    apply {
        packet.emit(hdr.cpu_in);
        packet.emit(hdr.ethernet);
        packet.emit(hdr.arp);
        packet.emit(hdr.ipv4);
        // Exercise 2.2 TO-DO: emit TCP where applicable.
    }
}


V1Switch(
    ParserImpl(),
    VerifyChecksumImpl(),
    IngressPipeImpl(),
    EgressPipeImpl(),
    ComputeChecksumImpl(),
    DeparserImpl()
) main;
