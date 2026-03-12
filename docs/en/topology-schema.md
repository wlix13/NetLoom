# Topology Schema Reference

This document describes the YAML schema for defining network topologies in NetLoom.

## Overview

A topology file has four main sections:

```yaml
meta:        # Required - Topology metadata
  id: "lab-id"
  name: "Lab Name"

networks:    # Required - Named L2 network segments
  - name: "lan1"

defaults:    # Optional - Global defaults for all nodes
  ip_forwarding: false

nodes:       # Required - Node definitions
  - name: A
    role: router
    interfaces:
      eth1:
        network: lan1
        ip: "10.0.0.1/24"
```

## Meta

Topology metadata. **Required**.

| Field         | Type   | Required | Description                        |
|---------------|--------|----------|------------------------------------|
| `id`          | string | Yes      | Unique identifier for the topology |
| `name`        | string | Yes      | Human-readable name                |
| `description` | string | No       | Optional description               |

```yaml
meta:
  id: "campus-network"
  name: "Campus Network Lab"
  description: "Multi-site campus network with OSPF routing"
```

## Networks

Named L2 network segments. **Required**. Each network maps to a VirtualBox internal network.
Interfaces on different nodes that share the same `network` name are connected at L2.

| Field  | Type   | Required | Description         |
|--------|--------|----------|---------------------|
| `name` | string | Yes      | Unique network name |

```yaml
networks:
  - name: r1-r2       # Link between R1 and R2
  - name: r2-r3       # Link between R2 and R3
  - name: lan         # Shared LAN segment
```

## Defaults

Global defaults applied to all nodes. **Optional**.

| Field           | Type    | Default | Description                       |
|-----------------|---------|---------|-----------------------------------|
| `ip_forwarding` | boolean | `false` | Enable IP forwarding on all nodes |
| `sysctl`        | object  | -       | Global kernel parameters          |
| `vbox`          | object  | -       | VirtualBox VM settings            |

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

| Field               | Type    | Default | Description                                                                           |
|---------------------|---------|---------|---------------------------------------------------------------------------------------|
| `paravirt_provider` | string  | `kvm`   | Paravirtualization provider: `default`, `legacy`, `minimal`, `hyperv`, `kvm`, `none`  |
| `chipset`           | string  | `ich9`  | Chipset type: `piix3`, `ich9`                                                         |
| `ioapic`            | boolean | `true`  | Enable I/O APIC                                                                       |
| `hpet`              | boolean | `true`  | Enable High Precision Event Timer                                                     |

```yaml
defaults:
  vbox:
    paravirt_provider: kvm
    chipset: ich9
```

## Nodes

Node definitions. **Required**.

| Field        | Type   | Default    | Description                           |
|--------------|--------|------------|---------------------------------------|
| `name`       | string | *required* | Unique node name                      |
| `role`       | string | `host`     | Node role: `router`, `switch`, `host` |
| `sysctl`     | object | -          | Node-specific kernel parameters       |
| `interfaces` | object | -          | Named interface configurations (map)  |
| `vlans`      | array  | -          | VLAN interface configurations         |
| `tunnels`    | array  | -          | IP tunnel configurations              |
| `bridges`    | array  | -          | Bridge configurations                 |
| `routing`    | object | -          | Routing daemon configuration          |
| `services`   | object | -          | Service configurations                |
| `commands`   | array  | -          | Raw shell commands                    |

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

Interface configurations as a **named map** (key = interface name). This replaces the old ordered list.

| Field        | Type    | Default    | Description                                                                      |
|--------------|---------|------------|----------------------------------------------------------------------------------|
| `network`    | string  | -          | Name of the L2 network this interface connects to. Omit for loopback interfaces. |
| `kind`       | string  | `physical` | Interface kind: `physical` or `loopback`                                         |
| `ip`         | string  | -          | IP address in CIDR notation (e.g., `10.0.1.1/24`)                                |
| `gateway`    | string  | -          | Default gateway IP                                                               |
| `dhcp`       | boolean | `false`    | Enable DHCP on this interface                                                    |
| `mtu`        | integer | -          | MTU override. Uses OS default if omitted.                                        |
| `mac`        | string  | -          | Static MAC address (e.g., `02:00:00:00:00:01`). Auto-generated if omitted.       |
| `configured` | boolean | `true`     | If `false`, no config file is generated                                          |

```yaml
interfaces:
  lo0:
    kind: loopback
    ip: "10.255.1.1/32"
  eth1:
    network: r1-r2
    ip: "10.0.12.1/24"
  eth2:
    network: lan
    ip: "10.0.1.1/24"
    mtu: 9000
  eth3:
    network: mgmt
    dhcp: true
  eth4:
    network: transit
    configured: false    # unmanaged - no config file generated
```

!!! info "Interface kinds"
    - `physical` interfaces get a VirtualBox NIC when `network` is set.
    - `loopback` interfaces are OS-only: no VirtualBox NIC, no MAC address, and the `.link` template is skipped. Loopback interfaces must not have `network` set.

#### How interface renaming works

Linux kernel names NICs unpredictably (`enp0s3`, `enp0s8`, …). NetLoom ensures each interface gets the exact name you defined in YAML through a two-step mechanism:

1. **MAC assignment** — every physical interface receives a MAC address, either the one you specified via `mac` or one that is **deterministically generated** from the seed `<topology-id>-<node-name>-<interface-name>`. Because the seed is stable, the same MAC is reproduced on every config regeneration.

2. **`.link` rename file** — a systemd-networkd `.link` file is generated for each physical interface:

    ```ini
    # Rename interface to eth1 based on MAC 02:ab:cd:ef:01:02
    [Match]
    MACAddress=02:ab:cd:ef:01:02

    [Link]
    Name=eth1
    ```

    udev processes this file on boot and renames the kernel interface to the name you chose before any network configuration is applied.

3. **`.network` config** — the IP/MTU/DHCP settings then use `Name=eth1` in their `[Match]` section, so they apply to the correctly-named interface regardless of kernel enumeration order.

Loopback interfaces skip step 1 and 2 entirely — they are brought up as normal OS loopbacks with no VirtualBox NIC involved.

### vlans

VLAN (802.1Q) interface configurations.

| Field     | Type    | Required | Description                                                         |
|-----------|---------|----------|---------------------------------------------------------------------|
| `id`      | integer | Yes      | VLAN ID (1-4094)                                                    |
| `parent`  | string  | Yes      | Parent interface name (e.g., `eth1`)                                |
| `name`    | string  | No       | Custom interface name (e.g., `vlan5`). Defaults to `{parent}.{id}`. |
| `ip`      | string  | No       | IP address in CIDR notation                                         |
| `gateway` | string  | No       | Default gateway IP                                                  |

```yaml
vlans:
  - id: 100
    parent: eth1
    ip: "10.100.0.1/24"
  - id: 200
    parent: eth1
    name: vlan-mgmt         # custom interface name instead of "eth1.200"
    ip: "10.200.0.1/24"
    gateway: "10.200.0.254"
```

### tunnels

IP tunnel configurations (IPIP, GRE, SIT).

| Field    | Type   | Default    | Description                                          |
|----------|--------|------------|------------------------------------------------------|
| `name`   | string | `tun0`     | Tunnel interface name                                |
| `type`   | string | `ipip`     | Tunnel type: `ipip`, `gre`, `sit`                    |
| `local`  | string | *required* | Local endpoint IP address                            |
| `remote` | string | *required* | Remote endpoint IP address                           |
| `ip`     | string | -          | IP address in CIDR notation for the tunnel interface |

```yaml
tunnels:
  - name: tun0
    type: ipip
    local: "203.0.113.1"
    remote: "198.51.100.1"
    ip: "10.255.0.1/30"
```

### bridges

Bridge configurations. Each bridge groups interfaces and/or VLANs into one L2 domain.
Multiple bridges are supported on a single node (e.g., for VLAN-segmented switching).

| Field        | Type    | Default | Description                                                                                      |
|--------------|---------|---------|--------------------------------------------------------------------------------------------------|
| `name`       | string  | `br0`   | Bridge interface name                                                                            |
| `stp`        | boolean | `false` | Enable Spanning Tree Protocol                                                                    |
| `members`    | array   | -       | Interface or VLAN names that are bridge ports. If omitted, all non-loopback interfaces are used. |
| `configured` | boolean | `true`  | If `false`, no config file is generated                                                          |

```yaml
# Simple bridge — all interfaces become members automatically
- name: SW1
  role: switch
  interfaces:
    eth1:
      network: net1
    eth2:
      network: net2
  bridges:
    - name: br0
      stp: true

# VLAN-segmented bridge — explicit members
- name: SW2
  role: switch
  interfaces:
    eth1:
      network: access1
    eth2:
      network: access2
    eth3:
      network: trunk
  vlans:
    - id: 5
      parent: eth3
      name: vlan5
    - id: 7
      parent: eth3
      name: vlan7
  bridges:
    - name: br5
      members: [eth1, vlan5]
    - name: br7
      members: [eth2, vlan7]
```

### routing

Routing daemon configuration.

| Field        | Type    | Default | Description                             |
|--------------|---------|---------|-----------------------------------------|
| `engine`     | string  | -       | Routing daemon: `bird`, `frr`, `none`   |
| `router_id`  | string  | -       | Router ID (usually an IP)               |
| `static`     | array   | -       | Static routes (list of objects)         |
| `ospf`       | object  | -       | OSPF configuration                      |
| `rip`        | object  | -       | RIP configuration                       |
| `configured` | boolean | `true`  | If `false`, no config file is generated |

#### Static Routes

Static routes are objects with `destination` and `gateway` fields:

```yaml
routing:
  engine: bird
  static:
    - destination: "10.0.0.0/8"
      gateway: "192.168.1.1"
    - destination: "0.0.0.0/0"
      gateway: "10.0.1.254"
```

#### OSPF Configuration

| Field     | Type    | Default | Description           |
|-----------|---------|---------|-----------------------|
| `enabled` | boolean | `false` | Enable OSPF           |
| `areas`   | array   | -       | OSPF area definitions |

**OSPF Area:**

| Field        | Type   | Default   | Description             |
|--------------|--------|-----------|-------------------------|
| `id`         | string | `0.0.0.0` | Area ID                 |
| `interfaces` | array  | -         | Interfaces in this area |

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

| Field        | Type    | Default | Description                     |
|--------------|---------|---------|---------------------------------|
| `enabled`    | boolean | `false` | Enable RIP                      |
| `version`    | integer | `2`     | RIP version (1 or 2)            |
| `interfaces` | array   | -       | Interfaces participating in RIP |

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

| Field         | Type    | Description                 |
|---------------|---------|-----------------------------|
| `http_server` | integer | HTTP server port            |
| `wireguard`   | object  | WireGuard VPN configuration |
| `firewall`    | object  | Firewall configuration      |

#### WireGuard

| Field         | Type    | Description           |
|---------------|---------|-----------------------|
| `private_key` | string  | WireGuard private key |
| `listen_port` | integer | UDP listen port       |
| `address`     | string  | Interface IP address  |
| `peers`       | array   | Peer configurations   |

**WireGuard Peer:**

| Field         | Type   | Description             |
|---------------|--------|-------------------------|
| `public_key`  | string | Peer's public key       |
| `allowed_ips` | string | Allowed IP ranges       |
| `endpoint`    | string | Peer endpoint (IP:port) |

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

| Field   | Type   | Description                         |
|---------|--------|-------------------------------------|
| `impl`  | string | Firewall implementation: `nftables` |
| `rules` | array  | Firewall rules                      |

**Firewall Rule:**

| Field    | Type    | Description                             |
|----------|---------|-----------------------------------------|
| `action` | string  | Rule action: `accept`, `drop`, `reject` |
| `src`    | string  | Source IP/network                       |
| `dst`    | string  | Destination IP/network                  |
| `proto`  | string  | Protocol (`tcp`, `udp`, `icmp`)         |
| `dport`  | integer | Destination port                        |

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

networks:
  - name: r1-r2
  - name: r2-r3
  - name: r1-sw1
  - name: sw1-h1
  - name: sw1-h2

nodes:
  - name: R1
    role: router
    interfaces:
      lo0:
        kind: loopback
        ip: "10.255.1.1/32"
      eth1:
        network: r1-r2
        ip: "10.0.12.1/24"
      eth2:
        network: r1-sw1
        ip: "10.0.1.1/24"
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
      eth1:
        network: r1-r2
        ip: "10.0.12.2/24"
      eth2:
        network: r2-r3
        ip: "10.0.23.1/24"
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
      eth1:
        network: r2-r3
        ip: "10.0.23.2/24"
    routing:
      engine: bird
      router_id: "3.3.3.3"
      static:
        - destination: "0.0.0.0/0"
          gateway: "10.0.23.1"

  - name: SW1
    role: switch
    interfaces:
      eth1:
        network: r1-sw1
      eth2:
        network: sw1-h1
      eth3:
        network: sw1-h2
    bridges:
      - name: br0
        stp: true

  - name: H1
    role: host
    interfaces:
      eth1:
        network: sw1-h1
        ip: "10.0.1.10/24"
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
      eth1:
        network: sw1-h2
        ip: "10.0.1.20/24"
        gateway: "10.0.1.1"
```
