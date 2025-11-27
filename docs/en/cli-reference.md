# CLI Reference

Complete reference for all NetLoom commands and options.

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
| `-h, --help`   | -      | -                  | Show help message                                     |

## Commands

### init

Import base OVA and create a golden snapshot.

```bash
netloom --topology lab.yaml --ova base.ova init
```

**What it does:**

1. Imports the OVA file as a new VM (named by `--base-vm`)
2. Creates a snapshot (named by `--snapshot`) for linked cloning
3. Initializes the workdir structure

/// note
Only run `init` once per base image. The base VM is reused across all topologies.
///

---

### create

Create linked clones for all topology nodes and attach empty config-drives.

```bash
netloom --topology lab.yaml create
```

**What it does:**

1. Creates a linked clone for each node in the topology
2. Configures VirtualBox internal networks for each link
3. Attaches an empty config-drive ISO to each VM

---

### gen

Generate configuration files for all nodes.

```bash
netloom --topology lab.yaml gen
```

**Options:**

| Option        | Type   | Default    | Description              |
| ------------- | ------ | ---------- | ------------------------ |
| `--templates` | String | `networkd` | Template set name to use |

**What it does:**

1. Renders Jinja2 templates for each node based on topology config
2. Generates networkd configs, hostname, sysctl settings, etc.
3. Outputs to `<workdir>/configs/<node>/`

**Available template sets:**

- `networkd` - systemd-networkd configuration (default)

Use `list-templates` to see all available template sets.

---

### attach

Copy generated configs into each node's config-drive.

```bash
netloom --topology lab.yaml attach
```

**What it does:**

1. Mounts each VM's config-drive ISO
2. Copies configs from `<workdir>/configs/<node>/` to the config-drive
3. Unmounts the config-drive

---

### start

Start all topology VMs.

```bash
netloom --topology lab.yaml start
```

**What it does:**

1. Starts each VM in headless mode
2. VMs boot and apply configs from their config-drives

---

### stop

Send ACPI shutdown signal to all topology VMs.

```bash
netloom --topology lab.yaml stop
```

**What it does:**

1. Sends ACPI power button event to each VM
2. VMs perform graceful shutdown

---

### destroy

Stop and remove all topology VMs.

```bash
netloom --topology lab.yaml destroy
```

**Options:**

| Option  | Type | Default | Description                       |
| ------- | ---- | ------- | --------------------------------- |
| `--all` | Flag | false   | Also destroy the base (golden) VM |

**What it does:**

1. Powers off all topology VMs
2. Unregisters and deletes VM files
3. With `--all`: also destroys the base VM

/// warning
Using `--all` will require re-running `init` with the OVA for future deployments.
///

---

### save

Pull changed files from config-drive back to host.

```bash
netloom --topology lab.yaml save
```

**What it does:**

1. Mounts each VM's config-drive
2. Copies contents to `<workdir>/saved/<node>/`
3. Preserves any changes made inside the VM

---

### restore

Restore last saved configs into staging area.

```bash
netloom --topology lab.yaml restore
```

**What it does:**

1. Copies saved configs from `<workdir>/saved/<node>/`
2. Overwrites `<workdir>/configs/<node>/`
3. Ready for `attach` to deploy to VMs

---

### list-templates

List available template sets.

```bash
netloom --topology lab.yaml list-templates
```

**Output example:**

```
Available template sets:
  - networkd
```

---

### show

Display topology information.

```bash
netloom --topology lab.yaml show
```

**Output example:**

```
Topology: My Lab (my-lab)
A sample network topology

Nodes: 3
  R1 (router)
    eth1 [10.0.1.1/24] -> R2
    eth2 [192.168.1.1/24] -> H1
  R2 (router)
    eth1 [10.0.1.2/24] -> R1
  H1 (host)
    eth1 [192.168.1.10/24] -> R1

Links: 2
  R1/eth1 <-> R2/eth1
  R1/eth2 <-> H1/eth1
```

## Usage Examples

### Deploy a New Topology

```bash
# First deployment with new base image
netloom --topology lab.yaml --ova base.ova init
netloom --topology lab.yaml create
netloom --topology lab.yaml gen
netloom --topology lab.yaml attach
netloom --topology lab.yaml start
```

### Update Configurations

```bash
# After editing topology YAML
netloom --topology lab.yaml gen
netloom --topology lab.yaml attach
# Reboot VMs or re-apply configs manually
```

### Custom Workdir

```bash
# Use a specific directory for this lab
netloom --topology lab.yaml --workdir ./lab1-work create
```

### Multiple Topologies

```bash
# Each topology uses its own VMs but shares the base
netloom --topology lab1.yaml create
netloom --topology lab2.yaml create
```
