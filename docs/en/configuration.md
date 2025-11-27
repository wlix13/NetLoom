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
