# CLI Reference

Complete reference for all NetLoom commands and options.

/// tip
Enable [shell completion](shell-completion.md) for faster command entry with tab completion.
///

## Global Options

All commands require the `--topology` option and accept these global options:

| Option         | Type   | Default            | Description                                           |
| -------------- | ------ | ------------------ | ----------------------------------------------------- |
| `--topology`   | Path   | _required_         | Path to topology YAML file                            |
| `--workdir`    | Path   | `.labs_configs`    | Working directory for generated configs and artifacts |
| `--basefolder` | Path   | VirtualBox default | VirtualBox VM base folder                             |
| `--ova`        | Path   | -                  | Path to base OVA (used on first init)                 |
| `--base-vm`    | String | `Labs-Base`        | Name for the imported base VM                         |
| `--snapshot`   | String | `golden`           | Snapshot name used for linked clones                  |
| `--debug`      | Flag   | false              | Enable debug output (writes `_node.json` per node)    |
| `-h, --help`   | -      | -                  | Show help message                                     |

## Commands

The CLI is organized into three groups:

- **Pipeline commands** (`up`, `down`) — run multiple steps in sequence
- **Step commands** (`steps <cmd>`) — run individual step one at a time
- **Management commands** (`save`, `restore`, `list-templates`, `show`) — inspect and manage configs

---

## Pipeline Commands

### up

Bring a topology up in one shot: create VMs, generate configs, attach them, and start.

```bash
netloom --topology lab.yaml up
```

**Options:**

| Option      | Type | Default | Description                                          |
| --------    | ---- | ------- | ---------------------------------------------------- |
| `--init`    | Flag | false   | Also run `init` (import OVA, take snapshot) first    |
| `--yes, -y` | Flag | false   | Skip confirmation prompt                             |

**Pipeline:** `(init →) create → gen → attach → start`

```bash
# First-time deployment including base VM import
netloom --topology lab.yaml --ova base.ova up --init

# Subsequent deployments (base VM already exists)
netloom --topology lab.yaml up
```

---

### down

Tear a topology down: stop all VMs, then destroy them.

```bash
netloom --topology lab.yaml down
```

**Options:**

| Option      | Type | Default | Description                    |
| ----------- | ---- | ------- | ------------------------------ |
| `--all`     | Flag | false   | Also destroy the base VM       |
| `--yes, -y` | Flag | false   | Skip confirmation prompt       |

**Pipeline:** `stop → destroy`

---

## Step Commands

Individual steps are grouped under the `steps` subcommand. Use these when you need fine-grained control.

```bash
netloom --topology lab.yaml steps <command>
```

**Typical order:** `init → create → gen → attach → start`

### steps init

Import base OVA and take a snapshot.

```bash
netloom --topology lab.yaml --ova base.ova steps init
```

**What it does:**

1. Imports the OVA file as a new VM (named by `--base-vm`)
2. Creates a snapshot (named by `--snapshot`) for linked cloning
3. Initializes the workdir structure

/// note
Only run `init` once per base image. The base VM is reused across all topologies.
///

---

### steps create

Create linked clones for all topology nodes and attach empty config-drives.

```bash
netloom --topology lab.yaml steps create
```

**What it does:**

1. Creates a linked clone for each node in the topology
2. Configures VirtualBox internal networks for each link
3. Attaches an empty config-drive VMDK to each VM

---

### steps gen

Generate configuration files for all nodes (or a single node).

```bash
netloom --topology lab.yaml steps gen
```

**Options:**

| Option        | Type   | Default | Description                       |
| ------------- | ------ | ------- | -------------------------------   |
| `--node, -n`  | String | -       | Generate config for one node only |

**What it does:**

1. Renders Jinja2 templates for each node based on topology config
2. Generates networkd configs, hostname, sysctl settings, etc.
3. Auto-detects and renders additional template sets per node:
    - `bird` — when `routing.engine` is `bird`
    - `nftables` — when `services.firewall` is configured
    - `wireguard` — when `services.wireguard` is configured
4. Outputs to `<workdir>/configs/<node>/`

```bash
# Generate for all nodes
netloom --topology lab.yaml steps gen

# Generate only for R1
netloom --topology lab.yaml steps gen --node R1
```

---

### steps attach

Copy generated configs into each node's config-drive.

```bash
netloom --topology lab.yaml steps attach
```

**What it does:**

1. Mounts each VM's config-drive VMDK
2. Copies configs from `<workdir>/configs/<node>/` to the config-drive
3. Unmounts the config-drive

---

### steps start

Start all topology VMs.

```bash
netloom --topology lab.yaml steps start
```

**What it does:**

1. Starts each VM in headless mode
2. VMs boot and apply configs from their config-drives

---

### steps stop

Send stop signals to all topology VMs.

```bash
netloom --topology lab.yaml steps stop
```

**What it does:**

1. Sends ACPI power button event to each VM
2. VMs perform graceful shutdown

---

### steps destroy

Stop and remove all topology VMs.

```bash
netloom --topology lab.yaml steps destroy
```

**Options:**

| Option      | Type | Default | Description                             |
| ----------- | ---- | ------- | --------------------------------------- |
| `--all`     | Flag | false   | Also destroy the base (golden) VM       |
| `--yes, -y` | Flag | false   | Skip confirmation prompt                |

**What it does:**

1. Powers off all topology VMs
2. Unregisters and deletes VM files
3. With `--all`: also destroys the base VM

/// warning
Using `--all` will require re-running `init` with the OVA for future deployments.
///

---

## Management Commands

### save

Pull changed files from each node's config-drive back to the host.

```bash
netloom --topology lab.yaml save
```

**What it does:**

1. Mounts each VM's config-drive
2. Copies contents to `<workdir>/saved/<node>/`
3. Preserves any changes made inside the VM

---

### restore

Restore last saved configs into the staging area.

```bash
netloom --topology lab.yaml restore
```

**What it does:**

1. Copies saved configs from `<workdir>/saved/<node>/`
2. Overwrites `<workdir>/configs/<node>/`
3. Ready for `steps attach` to deploy to VMs

---

### list-templates

List available template sets.

```bash
netloom --topology lab.yaml list-templates
```

**Output example:**

```bash
Available template sets:
  - networkd
  - bird
  - nftables
  - wireguard
```

---

### show

Display topology information.

```bash
netloom --topology lab.yaml show
```

**Options:**

| Option          | Type   | Default | Description                          |
| --------------- | ------ | ------- | ------------------------------------ |
| `--node, -n`    | String | -       | Show only this node                  |
| `--routing, -r` | Flag   | false   | Show routing config (static/OSPF/RIP)|
| `--services, -s`| Flag   | false   | Show services config                 |
| `--bridges, -b` | Flag   | false   | Show bridge config                   |
| `--vlans, -v`   | Flag   | false   | Show VLAN config                     |
| `--tunnels, -t` | Flag   | false   | Show tunnel config                   |
| `--sysctl, -y`  | Flag   | false   | Show sysctl settings                 |
| `--all, -a`     | Flag   | false   | Show all sections                    |
| `--map, -m`     | Flag   | false   | Show network connectivity table      |
| `--graph, -g`   | Flag   | false   | Draw topology as a tree diagram      |

```bash
netloom --topology lab.yaml show              # node summary table
netloom --topology lab.yaml show --map        # network connectivity table
netloom --topology lab.yaml show --graph      # tree diagram
netloom --topology lab.yaml show -n R1 -r     # routing info for R1
netloom --topology lab.yaml show -n R1 --all  # all details for R1
```

---

## Usage Examples

### Deploy a New Topology

```bash
# First deployment — import base OVA and bring everything up
netloom --topology lab.yaml --ova base.ova up --init

# Subsequent deployments — base VM already exists
netloom --topology lab.yaml up
```

### Update Configurations

```bash
# After editing topology YAML — regenerate and reattach
netloom --topology lab.yaml steps gen
netloom --topology lab.yaml steps attach
# Reboot VMs or re-apply configs manually
```

### Tear Down

```bash
# Stop and destroy topology VMs
netloom --topology lab.yaml down

# Also remove the base VM
netloom --topology lab.yaml down --all
```

### Custom Workdir

```bash
netloom --topology lab.yaml --workdir ./lab1-work up
```

### Multiple Topologies

```bash
# Each topology uses its own VMs but shares the base
netloom --topology lab1.yaml up
netloom --topology lab2.yaml up
```
