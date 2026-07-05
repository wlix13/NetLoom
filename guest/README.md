# NetLoom guest-side tooling

Components that live **inside the lab base image** (ALT Linux), packaged the
same way as `livecd-fetch-cdrom`. They are the guest half of NetLoom's
config-drive contract:

```
host (netloom)                      guest (this folder)
──────────────                      ───────────────────
steps gen  → render configs
steps attach → write config drive → livecd-fetch-cdrom      (boot: drive → /etc)
                                    netloom-save-config     (runtime/shutdown: /etc → drive)
save [--sync] ← read config drive ←
```

## netloom-save-config (new)

Copies the managed config paths (`/etc/systemd/network`, `/etc/bird`,
`/etc/wireguard`, `/etc/sysctl.d`, `/etc/nftables.conf`, `/etc/hostname`)
back onto the config drive, so the host-side `netloom save` sees what the
student actually changed — not just what was originally injected.

Three units:

- `netloom-save-config.service` — oneshot that runs the copy; triggered by
  the timer or manually (and by `netloom save --sync` over the serial
  console, which runs the same script path).
- `netloom-save-config.timer` — periodic safety net (every 2 min) so work
  survives a hard poweroff.
- `netloom-save-config-shutdown.service` — ExecStop hook that runs one final
  copy during a clean shutdown, while filesystems are still mounted.

Enable in the image:

```
systemctl enable netloom-save-config.timer netloom-save-config-shutdown.service
```

Safety: the guest mounts the drive read-write only for the duration of the
copy. The host must only read the drive while the VM is powered off (plain
`netloom save`) or immediately after a `--sync` run completed its unmount.

## livecd-fetch-cdrom (patched reference)

Drop-in replacement for the script in your existing package, with two fixes:

1. **Mount by label.** NetLoom now formats config drives with the FAT volume
   label `NETLOOM`, so the script prefers `/dev/disk/by-label/NETLOOM` and
   only falls back to probing `vdb`/`sdb`/`sdb1`. This also makes the same
   image work under QEMU/KVM (virtio disks appear as `/dev/vdb`, not `sdb`).
2. **No `--now` during early boot.** The original `systemctl enable --now`
   runs inside a unit that blocks `sysinit.target`, while starting most
   services requires `basic.target` → ordering deadlock; the boot hangs
   until timeout, which is why a VM restart "fixed" it. The patch enables
   the unit and queues the start with `systemctl start --no-block`, so the
   service starts as soon as its own dependencies are up, without blocking
   early boot. (Plain `enable` alone is not enough: units enabled during
   early boot do not join the already-computed initial transaction.)

Optional hardening (not applied, your call): mount with `fmask=0177` for
paths like `/etc/wireguard` so private keys don't end up world-readable —
`wg-quick` only warns, but it's noise students will ask about.
