# Topology Schema Reference

This document describes the YAML schema for defining network topologies in NetLoom.

## Overview

A topology file has four main sections:

```yaml
meta:        # Required - Topology metadata
  id: "lab-id"
  name: "Lab Name"

defaults:    # Optional - Global defaults for all nodes
  ip_forwarding: false

links:       # Required - Physical connections between nodes
  - endpoints: ["A", "B"]

nodes:       # Required - Node definitions
  - name: A
    role: router
```

## Meta

Topology metadata. **Required**.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier for the topology |
| `name` | string | Yes | Human-readable name |
| `description` | string | No | Optional description |

```yaml
meta:
  id: "campus-network"
  name: "Campus Network Lab"
  description: "Multi-site campus network with OSPF routing"
```

## Defaults

Global defaults applied to all nodes. **Optional**.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ip_forwarding` | boolean | `false` | Enable IP forwarding on all nodes |
| `sysctl` | object | - | Global kernel parameters |
| `vbox` | object | - | VirtualBox VM settings |

### sysctl

Kernel parameters applied to all nodes:

```yaml
defaults:
  sysctl:
    net.core.somaxconn: 1024
    net.ipv4.tcp_syncookies: 1
```

### vbox

VirtualBox-specific VM settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `paravirt_provider` | string | `kvm` | Paravirtualization provider: `default`, `legacy`, `minimal`, `hyperv`, `kvm`, `none` |
| `chipset` | string | `ich9` | Chipset type: `piix3`, `ich9` |
| `ioapic` | boolean | `true` | Enable I/O APIC |
| `hpet` | boolean | `true` | Enable High Precision Event Timer |

```yaml
defaults:
  vbox:
    paravirt_provider: kvm
    chipset: ich9
```

## Links

Physical connections between nodes. **Required**.

Each link connects exactly two nodes. The order of links determines interface assignment (eth1, eth2, etc.).

| Field | Type | Description |
|-------|------|-------------|
| `endpoints` | array[2] | Exactly two node names |

```yaml
links:
  - endpoints: ["R1", "R2"]    # R1.eth1 <-> R2.eth1
  - endpoints: ["R2", "R3"]    # R2.eth2 <-> R3.eth1
  - endpoints: ["R1", "S1"]    # R1.eth2 <-> S1.eth1
```

!!! info "Interface Assignment"
    Interfaces are assigned in order of link appearance. The first link for a node creates `eth1`, the second creates `eth2`, and so on.

## Nodes

Node definitions. **Required**.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | *required* | Unique node name |
| `role` | string | `host` | Node role: `router`, `switch`, `host` |
| `sysctl` | object | - | Node-specific kernel parameters |
| `interfaces` | array | - | Interface configurations |
| `vlans` | array | - | VLAN interface configurations |
| `tunnels` | array | - | IP tunnel configurations |
| `bridge` | object | - | Bridge configuration (for switches) |
| `routing` | object | - | Routing daemon configuration |
| `services` | object | - | Service configurations |
| `commands` | array | - | Raw shell commands |

### Node Roles

- **router** - L3 device with IP forwarding, may run routing protocols
- **switch** - L2 device with bridging
- **host** - End device (workstation, server)

```yaml
nodes:
  - name: R1
    role: router

  - name: SW1
    role: switch

  - name: PC1
    role: host
```

### interfaces

Interface configurations. Order matches link assignment order.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ip` | string | - | IP address in CIDR notation (e.g., `10.0.1.1/24`) |
| `gateway` | string | - | Default gateway IP |
| `configured` | boolean | `true` | If `false`, no config file is generated |

```yaml
interfaces:
  - ip: "10.0.1.1/24"           # eth1
  - ip: "10.0.2.1/24"           # eth2
    gateway: "10.0.2.254"
  - configured: false           # eth3 - unmanaged
```

### vlans

VLAN (802.1Q) interface configurations.

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | VLAN ID (1-4094) |
| `parent` | string | Parent interface name (e.g., `eth1`) |
| `ip` | string | IP address in CIDR notation |
| `gateway` | string | Default gateway IP |

```yaml
vlans:
  - id: 100
    parent: eth1
    ip: "10.100.0.1/24"
  - id: 200
    parent: eth1
    ip: "10.200.0.1/24"
    gateway: "10.200.0.254"
```

### tunnels

IP tunnel configurations (IPIP, GRE, SIT).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | `tun0` | Tunnel interface name |
| `type` | string | `ipip` | Tunnel type: `ipip`, `gre`, `sit` |
| `local` | string | *required* | Local endpoint IP address |
| `remote` | string | *required* | Remote endpoint IP address |
| `ip` | string | - | IP address in CIDR notation for the tunnel interface |

```yaml
tunnels:
  - name: tun0
    type: ipip
    local: "203.0.113.1"
    remote: "198.51.100.1"
    ip: "10.255.0.1/30"
```

### bridge

Bridge configuration for switch nodes.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | `br0` | Bridge interface name |
| `stp` | boolean | `false` | Enable Spanning Tree Protocol |
| `configured` | boolean | `true` | If `false`, no config file is generated |

```yaml
- name: SW1
  role: switch
  bridge:
    name: br0
    stp: true
  interfaces:
    - configured: false  # Managed by bridge
    - configured: false
```

### routing

Routing daemon configuration.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `engine` | string | - | Routing daemon: `bird`, `frr`, `none` |
| `router_id` | string | - | Router ID (usually an IP) |
| `static` | array | - | Static routes |
| `ospf` | object | - | OSPF configuration |
| `rip` | object | - | RIP configuration |
| `configured` | boolean | `true` | If `false`, no config file is generated |

#### Static Routes

```yaml
routing:
  engine: bird
  static:
    - "10.0.0.0/8 via 192.168.1.1"
    - "0.0.0.0/0 via 10.0.1.254"
```

#### OSPF Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `false` | Enable OSPF |
| `areas` | array | - | OSPF area definitions |

**OSPF Area:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | string | `0.0.0.0` | Area ID |
| `interfaces` | array | - | Interfaces in this area |

```yaml
routing:
  engine: bird
  router_id: "192.168.1.1"
  ospf:
    enabled: true
    areas:
      - id: "0.0.0.0"
        interfaces: ["eth1", "eth2"]
      - id: "0.0.0.1"
        interfaces: ["eth3"]
```

#### RIP Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `false` | Enable RIP |
| `version` | integer | `2` | RIP version (1 or 2) |
| `interfaces` | array | - | Interfaces participating in RIP |

```yaml
routing:
  engine: bird
  router_id: "192.168.1.1"
  rip:
    enabled: true
    version: 2
    interfaces: ["eth1", "eth2"]
```

### services

Service configurations.

| Field | Type | Description |
|-------|------|-------------|
| `http_server` | integer | HTTP server port |
| `wireguard` | object | WireGuard VPN configuration |
| `firewall` | object | Firewall configuration |

#### WireGuard

| Field | Type | Description |
|-------|------|-------------|
| `private_key` | string | WireGuard private key |
| `listen_port` | integer | UDP listen port |
| `address` | string | Interface IP address |
| `peers` | array | Peer configurations |

**WireGuard Peer:**

| Field | Type | Description |
|-------|------|-------------|
| `public_key` | string | Peer's public key |
| `allowed_ips` | string | Allowed IP ranges |
| `endpoint` | string | Peer endpoint (IP:port) |

```yaml
services:
  wireguard:
    private_key: "..."
    listen_port: 51820
    address: "10.200.0.1/24"
    peers:
      - public_key: "..."
        allowed_ips: "10.200.0.2/32"
        endpoint: "192.168.1.2:51820"
```

#### Firewall

| Field | Type | Description |
|-------|------|-------------|
| `impl` | string | Firewall implementation: `nftables` |
| `rules` | array | Firewall rules |

**Firewall Rule:**

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | Rule action: `accept`, `drop`, `reject` |
| `src` | string | Source IP/network |
| `dst` | string | Destination IP/network |
| `proto` | string | Protocol (tcp, udp, icmp) |
| `dport` | integer | Destination port |

```yaml
services:
  firewall:
    impl: nftables
    rules:
      - action: accept
        proto: tcp
        dport: 22
      - action: accept
        proto: tcp
        dport: 80
      - action: drop
        src: "0.0.0.0/0"
```

### commands

Raw shell commands executed on the node. Use for edge cases not covered by other options.

```yaml
commands:
  - "systemctl enable bird"
  - "echo 'custom config' > /etc/custom.conf"
```

## Complete Example

```yaml
meta:
  id: "enterprise-lab"
  name: "Enterprise Network Lab"
  description: "Multi-router enterprise network with OSPF"

defaults:
  ip_forwarding: true
  sysctl:
    net.core.somaxconn: 1024

links:
  - endpoints: ["R1", "R2"]
  - endpoints: ["R2", "R3"]
  - endpoints: ["R1", "SW1"]
  - endpoints: ["SW1", "H1"]
  - endpoints: ["SW1", "H2"]

nodes:
  - name: R1
    role: router
    interfaces:
      - ip: "10.0.12.1/24"
      - ip: "10.0.1.1/24"
    routing:
      engine: bird
      router_id: "1.1.1.1"
      ospf:
        enabled: true
        areas:
          - id: "0.0.0.0"
            interfaces: ["eth1", "eth2"]

  - name: R2
    role: router
    interfaces:
      - ip: "10.0.12.2/24"
      - ip: "10.0.23.1/24"
    routing:
      engine: bird
      router_id: "2.2.2.2"
      ospf:
        enabled: true
        areas:
          - id: "0.0.0.0"
            interfaces: ["eth1", "eth2"]

  - name: R3
    role: router
    interfaces:
      - ip: "10.0.23.2/24"
    routing:
      engine: frr
      router_id: "3.3.3.3"
      static:
        - "0.0.0.0/0 via 10.0.23.1"

  - name: SW1
    role: switch
    bridge:
      name: br0
      stp: true
    interfaces:
      - configured: false
      - configured: false
      - configured: false

  - name: H1
    role: host
    interfaces:
      - ip: "10.0.1.10/24"
        gateway: "10.0.1.1"
    services:
      http_server: 8080
      firewall:
        impl: nftables
        rules:
          - action: accept
            proto: tcp
            dport: 8080
          - action: accept
            proto: icmp
          - action: drop
            src: "0.0.0.0/0"

  - name: H2
    role: host
    interfaces:
      - ip: "10.0.1.20/24"
        gateway: "10.0.1.1"
```
