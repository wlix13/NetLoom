# Configuration

This document covers NetLoom's configuration options, workdir structure, and customization.

## Workdir Structure

The working directory (default: `.labs_configs`) contains all generated artifacts:

```
.labs_configs/
├── configs/           # Generated configurations (ready for deployment)
│   ├── R1/
│   │   ├── etc/
│   │   │   ├── hostname
│   │   │   ├── sysctl.d/
│   │   │   │   └── 99-netloom.conf
│   │   │   └── systemd/
│   │   │       └── network/
│   │   │           ├── eth1.network
│   │   │           └── eth2.network
│   │   └── _debug.json    # Debug info (when debug mode enabled)
│   ├── R2/
│   │   └── ...
│   └── ...
├── saved/             # Configs pulled from VMs (after `save` command)
│   ├── R1/
│   │   └── ...
│   └── ...
└── drives/            # Config-drive VMDKs
    ├── R1-cfg.vmdk
    ├── R2-cfg.vmdk
    └── ...
```

### configs/

Generated configuration files ready for deployment. Structure mirrors the target filesystem:

- `etc/hostname` - Node hostname
- `etc/sysctl.d/99-netloom.conf` - Kernel parameters
- `etc/systemd/network/*.network` - networkd interface configs

### saved/

Configurations pulled from running VMs using the `save` command. Preserves any manual changes made inside VMs.

### drives/

Config-drive VMDK files attached to each VM. These are FAT-formatted virtual disks containing the node's configuration.

## VirtualBox Settings

### Base VM

| Option         | Default            | Description                            |
| -------------- | ------------------ | -------------------------------------- |
| `--base-vm`    | `Labs-Base`        | Name for the imported base VM          |
| `--snapshot`   | `golden`           | Snapshot name for linked clones        |
| `--ova`        | -                  | Path to base OVA (required for `init`) |
| `--basefolder` | VirtualBox default | VM storage location                    |

### VM Hardware

Configure in topology `defaults.vbox`:

```yaml
defaults:
  vbox:
    paravirt_provider: kvm # Paravirtualization
    chipset: ich9 # Chipset type
    ioapic: true # I/O APIC
    hpet: true # High Precision Event Timer
```

### Network Adapters

- **NIC 1** - NAT (management, unchanged from base)
- **NIC 2+** - Internal networks (topology links)

Internal network names follow the pattern: `<topology-id>-<nodeA>-<nodeB>`

## Template Customization

### Available Template Sets

List available templates:

```bash
netloom --topology lab.yaml list-templates
```

Built-in sets:

- `networkd` - systemd-networkd configuration (default)
- `bird` - BIRD Internet Routing Daemon configuration (auto-rendered when engine=bird)
- `nftables` - nftables firewall configuration (auto-rendered when firewall is configured)
- `wireguard` - WireGuard VPN configuration (auto-rendered when WireGuard is configured)

### Automatic Template Rendering

When generating configurations, NetLoom automatically renders additional template sets based on node configuration:

- **BIRD templates** are rendered when `routing.engine: bird` is set
- **nftables templates** are rendered when `services.firewall` is configured
- **WireGuard templates** are rendered when `services.wireguard` is configured

### Creating Custom Templates

1. Create a new directory in `netloom/templates/`:

```
netloom/templates/
└── my-templates/
    ├── custom-hostname.j2
    └── my-config.j2
```

2. Use in generation:

```bash
netloom --topology lab.yaml gen --templates my-templates
```

### Template Variables

Templates receive these variables:

| Variable   | Type             | Description                   |
| ---------- | ---------------- | ----------------------------- |
| `node`     | InternalNode     | Current node being configured |
| `topology` | InternalTopology | Full topology                 |

**Node properties:**

```jinja2
{{ node.name }}              {# Node name #}
{{ node.role }}              {# router, switch, host #}
{{ node.interfaces }}        {# List of interfaces #}
{{ node.vlans }}             {# List of VLAN interfaces #}
{{ node.tunnels }}           {# List of IP tunnels #}
{{ node.bridge }}            {# Bridge configuration #}
{{ node.sysctl }}            {# Merged sysctl settings #}
{{ node.routing }}           {# Routing configuration #}
{{ node.services }}          {# Services configuration #}
```

**Interface properties:**

```jinja2
{% for iface in node.interfaces %}
{{ iface.name }}             {# eth1, eth2, etc. #}
{{ iface.ip }}               {# IP in CIDR notation #}
{{ iface.gateway }}          {# Gateway IP #}
{{ iface.peer_node }}        {# Connected node name #}
{{ iface.configured }}       {# Whether to generate config #}
{% endfor %}
```

**VLAN properties:**

```jinja2
{% for vlan in node.vlans %}
{{ vlan.id }}                {# VLAN ID (1-4094) #}
{{ vlan.parent }}            {# Parent interface (eth1) #}
{{ vlan.name }}              {# Interface name (eth1.100) #}
{{ vlan.ip }}                {# IP in CIDR notation #}
{{ vlan.gateway }}           {# Gateway IP #}
{% endfor %}
```

**Tunnel properties:**

```jinja2
{% for tunnel in node.tunnels %}
{{ tunnel.name }}            {# Tunnel interface name #}
{{ tunnel.type }}            {# ipip, gre, or sit #}
{{ tunnel.local }}           {# Local endpoint IP #}
{{ tunnel.remote }}          {# Remote endpoint IP #}
{{ tunnel.ip }}              {# IP in CIDR notation #}
{% endfor %}
```

**Routing properties:**

```jinja2
{{ node.routing.engine }}        {# bird, frr, or none #}
{{ node.routing.router_id }}     {# Router ID #}
{{ node.routing.static_routes }} {# List of static routes #}
{{ node.routing.ospf_enabled }}  {# OSPF enabled #}
{{ node.routing.ospf_areas }}    {# List of OSPF areas #}
{{ node.routing.rip }}           {# RIP configuration #}
{{ node.routing.rip.enabled }}   {# RIP enabled #}
{{ node.routing.rip.version }}   {# RIP version (1 or 2) #}
{{ node.routing.rip.interfaces }} {# Interfaces in RIP #}
```

### Output Path Mapping

Template filenames determine output locations:

| Template Pattern | Output Path                          |
| ---------------- | ------------------------------------ |
| `hostname.j2`    | `etc/hostname`                       |
| `*.network.j2`   | `etc/systemd/network/<name>.network` |
| `sysctl.conf.j2` | `etc/sysctl.d/99-netloom.conf`       |
| `*.conf.j2`      | `etc/<name>.conf`                    |

### Shared Macros

Common macros are in `templates/_base/_macros.j2`:

```jinja2
{% import '_base/_macros.j2' as macros %}

{{ macros.some_helper() }}
```

## Configuration Examples

### VLAN Configuration

Create VLAN interfaces on physical interfaces:

```yaml
nodes:
  - name: SW1
    role: switch
    vlans:
      - id: 100
        parent: eth1
        ip: "10.100.0.1/24"
      - id: 200
        parent: eth1
        ip: "10.200.0.1/24"
```

Generated files:
- `etc/systemd/network/11-eth1.100.netdev` - VLAN interface definition
- `etc/systemd/network/11-eth1.100.network` - VLAN IP configuration
- `etc/systemd/network/09-eth1-vlan.network` - Parent interface with VLAN association

### RIP Routing Configuration

Configure RIP routing with BIRD:

```yaml
nodes:
  - name: R1
    role: router
    interfaces:
      - ip: "10.0.1.1/24"
      - ip: "10.0.2.1/24"
    routing:
      engine: bird
      router_id: "1.1.1.1"
      rip:
        enabled: true
        version: 2
        interfaces:
          - eth1
          - eth2
```

Generated files:
- `etc/bird/bird.conf` - Main BIRD configuration
- `etc/bird/conf.d/rip.conf` - RIP protocol configuration

### OSPF Routing Configuration

Configure OSPF with multiple areas:

```yaml
nodes:
  - name: R1
    role: router
    interfaces:
      - ip: "10.0.1.1/24"
      - ip: "10.0.2.1/24"
    routing:
      engine: bird
      router_id: "1.1.1.1"
      ospf:
        enabled: true
        areas:
          - id: "0.0.0.0"
            interfaces: ["eth1"]
          - id: "0.0.0.1"
            interfaces: ["eth2"]
```

### Bridge with STP Configuration

Configure a bridge with Spanning Tree Protocol:

```yaml
nodes:
  - name: SW1
    role: switch
    bridge:
      name: br0
      stp: true
    interfaces:
      - configured: false  # Managed by bridge
      - configured: false
```

Generated files:
- `etc/systemd/network/05-br0.netdev` - Bridge interface definition
- `etc/systemd/network/06-br0.network` - Bridge network configuration
- `etc/systemd/network/07-eth1-bridge.network` - Bridge port configurations

### IPIP Tunnel Configuration

Create an IPIP tunnel between two routers:

```yaml
nodes:
  - name: R1
    role: router
    interfaces:
      - ip: "203.0.113.1/24"
    tunnels:
      - name: tun0
        type: ipip
        local: "203.0.113.1"
        remote: "198.51.100.1"
        ip: "10.255.0.1/30"
```

Generated files:
- `etc/systemd/network/25-tun0.netdev` - Tunnel interface definition
- `etc/systemd/network/25-tun0.network` - Tunnel IP configuration

### Firewall (ACL) Configuration

Configure nftables firewall rules:

```yaml
nodes:
  - name: H1
    role: host
    interfaces:
      - ip: "10.0.1.10/24"
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
          - action: accept
            proto: icmp
          - action: drop
            src: "0.0.0.0/0"
```

Generated files:
- `etc/nftables.conf` - nftables configuration with rules

### WireGuard VPN Configuration

Configure WireGuard VPN:

```yaml
nodes:
  - name: R1
    role: router
    services:
      wireguard:
        private_key: "generated-private-key"
        address: "10.200.0.1/24"
        listen_port: 51820
        peers:
          - public_key: "peer-public-key"
            allowed_ips: "10.200.0.2/32"
            endpoint: "203.0.113.2:51820"
```

Generated files:
- `etc/wireguard/wg0.conf` - WireGuard interface configuration

## Environment Variables

NetLoom respects standard VirtualBox environment variables:

| Variable            | Description                        |
| ------------------- | ---------------------------------- |
| `VBOX_USER_HOME`    | VirtualBox configuration directory |
| `VBOX_INSTALL_PATH` | VirtualBox installation path       |

## Debug Mode

Debug mode outputs additional information:

- `_debug.json` files in each node's config directory
- Detailed console output during operations

Debug mode is enabled by default during development.

## Multiple Topologies

You can run multiple topologies simultaneously:

```bash
# Each topology uses its own VMs
netloom --topology lab1.yaml --workdir .lab1 create
netloom --topology lab2.yaml --workdir .lab2 create
```

Considerations:

- Use different workdirs to avoid conflicts
- All topologies share the same base VM
- Internal network names include topology ID for isolation

## Performance Tips

### Linked Clones

NetLoom uses linked clones by default:

- **Pros**: Fast creation, minimal disk usage
- **Cons**: Depends on base snapshot, slightly slower I/O

### Config-Drive Size

Default config-drive size is 128 MB, sufficient for most configurations. Increase if needed for large config files.

### Parallel Operations

VM operations are performed sequentially to avoid VirtualBox conflicts. For large topologies, consider:

- Splitting into smaller independent topologies
- Using the `--workdir` option for parallel development
