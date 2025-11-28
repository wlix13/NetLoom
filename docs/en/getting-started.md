# Getting Started

This guide walks you through installing NetLoom and deploying your first network topology.

## Prerequisites

Before using NetLoom, ensure you have:

- **Python 3.13+** - NetLoom requires Python 3.13 or later
- **VirtualBox** - Oracle VirtualBox for VM management
- **Base OVA** - A prepared Linux OVA image (see [Preparing a Base Image](#preparing-a-base-image))

## Installation

### Using uv (Recommended)

```bash
uv tool install netloom
```

### Using pip

```bash
pip install netloom
```

### From Source

```bash
git clone https://github.com/wlix13/NetLoom.git
cd NetLoom
uv sync
```

## Your First Topology

### 1. Create a Topology File

Create a file named `lab.yaml`:

```yaml
meta:
  id: "my-first-lab"
  name: "My First Network Lab"
  description: "A simple two-router topology"

links:
  - endpoints: ["R1", "R2"]

nodes:
  - name: R1
    role: router
    interfaces:
      - ip: "10.0.1.1/24"

  - name: R2
    role: router
    interfaces:
      - ip: "10.0.1.2/24"
```

### 2. Initialize the Environment

Import the base OVA and create a golden snapshot:

```bash
netloom --topology lab.yaml --ova base.ova init
```

This command:

- Imports the base OVA as `Labs-Base` VM
- Takes a `golden` snapshot for linked cloning

/// note
You only need to run `init` once per base image. Subsequent topologies can reuse the same base VM.
///

### 3. Create the VMs

Create linked clones for each node in the topology:

```bash
netloom --topology lab.yaml create
```

This creates VMs named after your topology nodes (R1, R2) as linked clones of the base VM.

### 4. Generate Configurations

Generate network configurations for all nodes:

```bash
netloom --topology lab.yaml gen
```

Generated configs are stored in `.labs_configs/configs/<node>/` by default.

### 5. Attach Configurations

Copy the generated configs to each VM's config-drive:

```bash
netloom --topology lab.yaml attach
```

### 6. Start the Topology

Start all VMs:

```bash
netloom --topology lab.yaml start
```

Your network lab is now running! You can access each VM through VirtualBox or SSH.

## Complete Workflow

Here's the typical workflow in one view:

```bash
# First-time setup (once per base image)
netloom --topology lab.yaml --ova base.ova init

# Deploy a topology
netloom --topology lab.yaml create
netloom --topology lab.yaml gen
netloom --topology lab.yaml attach
netloom --topology lab.yaml start

# Make changes and redeploy configs
netloom --topology lab.yaml gen
netloom --topology lab.yaml attach

# Save changes made inside VMs
netloom --topology lab.yaml save

# Stop and destroy when done
netloom --topology lab.yaml stop
netloom --topology lab.yaml destroy
```

## Preparing a Base Image

NetLoom requires a base OVA with:

1. **Linux OS** - Debian/Ubuntu recommended
2. **systemd-networkd** - For network configuration
3. **Config-drive support** - Mount point at `/mnt/config` or similar
4. **Optional**: BIRD or FRR for routing scenarios

The base image should:

- Have a single network interface (eth0) for management
- Support additional interfaces (eth1, eth2, ...) for topology links
- Auto-apply configs from the config-drive on boot

## Next Steps

- Learn about all available [CLI Commands](cli-reference.md)
- Explore the [Topology Schema](topology-schema.md) for advanced configurations
- Understand the [Architecture](architecture.md) for customization
