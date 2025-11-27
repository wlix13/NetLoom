# NetLoom

**Network Lab Topology Orchestrator**

NetLoom is a command-line utility for creating and managing network topologies for educational labs. It automates the provisioning of VirtualBox VMs, network configuration generation, and topology deployment.

## Key Features

- **Declarative Topology Definition** - Define your entire network lab in a single YAML file
- **VirtualBox Integration** - Automated VM cloning, network setup, and lifecycle management
- **Template-Based Configuration** - Generate networkd, routing, and service configs from Jinja2 templates
- **Multi-Role Support** - Configure routers, switches, and hosts with role-specific settings
- **Routing Protocol Support** - Built-in support for BIRD and FRR routing daemons with OSPF
- **Config Persistence** - Save and restore VM configurations between sessions

## Quick Start

```bash
# Install NetLoom
uv add netloom

# Deploy a topology
netloom --topology lab.yaml init      # Import base VM
netloom --topology lab.yaml create    # Create VM clones
netloom --topology lab.yaml gen       # Generate configs
netloom --topology lab.yaml attach    # Attach configs to VMs
netloom --topology lab.yaml start     # Start all VMs
```

## Documentation

<div class="grid cards" markdown>

- :material-rocket-launch:{ .lg .middle } **Getting Started**

  ***

  Installation, prerequisites, and your first topology deployment

  [:octicons-arrow-right-24: Getting started](getting-started.md)

- :material-console:{ .lg .middle } **CLI Reference**

  ***

  Complete reference for all commands and options

  [:octicons-arrow-right-24: Reference](cli-reference.md)

- :material-file-document:{ .lg .middle } **Topology Schema**

  ***

  YAML schema reference for defining network topologies

  [:octicons-arrow-right-24: Schema](topology-schema.md)

- :material-crane:{ .lg .middle } **Architecture**

  ***

  Internal design and component overview

  [:octicons-arrow-right-24: Architecture](architecture.md)

- :material-cog:{ .lg .middle } **Configuration**

  ***

  Workdir structure and customization options

  [:octicons-arrow-right-24: Configuration](configuration.md)

</div>

## Example Topology

```yaml
meta:
  id: "simple-lab"
  name: "Simple Network Lab"

links:
  - endpoints: ["R1", "R2"]
  - endpoints: ["R1", "H1"]

nodes:
  - name: R1
    role: router
    interfaces:
      - ip: "10.0.1.1/24"
      - ip: "192.168.1.1/24"

  - name: R2
    role: router
    interfaces:
      - ip: "10.0.1.2/24"

  - name: H1
    role: host
    interfaces:
      - ip: "192.168.1.10/24"
        gateway: "192.168.1.1"
```

## License

NetLoom is open source software. See the [GitHub repository](https://github.com/wlix13/NetLoom) for details.
