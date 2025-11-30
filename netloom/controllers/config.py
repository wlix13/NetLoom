"""Config controller for template rendering and config-drive operations."""

from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

import orjson
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..core.controller import BaseController
from ..data import copy_from_configdrive, copy_tree_to_configdrive


if TYPE_CHECKING:
    from ..core.application import Application
    from ..models.internal import InternalNode, InternalTopology


class ConfigController(BaseController["Application"]):
    """Controller for configuration generation and management."""

    def __init__(self, app: "Application") -> None:
        super().__init__(app)
        self._env: Environment | None = None

    @property
    def templates_dir(self) -> Path:
        """Get the templates directory path."""

        with resources.as_file(resources.files("netloom") / "templates") as templates_path:
            return templates_path

    def get_env(self, extra_paths: list[Path] | None = None) -> Environment:
        """Get or create the Jinja2 environment."""

        search_paths = [self.templates_dir]
        if extra_paths:
            search_paths.extend(extra_paths)

        return Environment(
            loader=FileSystemLoader([str(p) for p in search_paths]),
            autoescape=True,
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def list_template_sets(self) -> list[str]:
        """List available template sets."""

        sets = []
        if self.templates_dir.exists():
            for item in self.templates_dir.iterdir():
                if item.is_dir() and not item.name.startswith("_"):
                    sets.append(item.name)
        return sorted(sets)

    def generate(
        self,
        topo: "InternalTopology",
        extra_paths: list[Path] | None = None,
    ) -> None:
        """Generate configs for all nodes using a template set."""

        env = self.get_env(extra_paths)

        for node in topo.nodes:
            if not node.config_dir:
                continue

            outdir = Path(node.config_dir)
            outdir.mkdir(parents=True, exist_ok=True)

            context = {
                "node": node,
                "topology": topo,
            }

            # Render the primary template set
            self._render_template_set(env, "networkd", context, outdir)

            # Render BIRD templates if routing is configured with bird engine
            if node.routing and node.routing.engine == "bird" and node.routing.configured:
                self._render_template_set(env, "bird", context, outdir)

            # Render nftables templates if firewall is configured
            if node.services and node.services.firewall:
                self._render_template_set(env, "nftables", context, outdir)

            # Render WireGuard templates if WireGuard is configured
            if node.services and node.services.wireguard:
                self._render_template_set(env, "wireguard", context, outdir)

            self._generate_services_list(env, node, outdir)

            if self.app.debug:
                self._write_debug_json(node, outdir)

    def _render_template_set(
        self,
        env: Environment,
        template_set: str,
        context: dict,
        outdir: Path,
    ) -> None:
        """Render all templates in a template set."""

        set_dir = self.templates_dir / template_set
        if not set_dir.exists():
            self.console.print(f"[yellow]Warning: Template set '{template_set}' not found[/yellow]")
            return

        node = context["node"]

        for template_file in set_dir.glob("*.j2"):
            template_name = f"{template_set}/{template_file.name}"
            template = env.get_template(template_name)
            template_stem = template_file.stem

            output_path = self._get_output_path(template_stem, node, outdir)
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path_str = str(output_path)

                # Per-interface templates
                if "{iface}" in output_path_str:
                    # VLAN parent interface templates
                    if "vlan-parent" in template_stem:
                        # Only render for interfaces that have VLANs configured
                        parent_ifaces = {vlan.parent for vlan in node.vlans}
                        for iface in node.interfaces:
                            if iface.name in parent_ifaces:
                                iface_context = {**context, "iface": iface}
                                content = template.render(iface_context)
                                if content.strip():
                                    iface_path = Path(output_path_str.replace("{iface}", iface.name))
                                    iface_path.parent.mkdir(parents=True, exist_ok=True)
                                    iface_path.write_text(content, encoding="utf-8", newline="\n")
                    # Bridge port templates
                    elif "bridge-port" in template_stem:
                        if node.bridge and node.bridge.configured:
                            for iface in node.interfaces:
                                iface_context = {**context, "iface": iface}
                                content = template.render(iface_context)
                                if content.strip():
                                    iface_path = Path(output_path_str.replace("{iface}", iface.name))
                                    iface_path.parent.mkdir(parents=True, exist_ok=True)
                                    iface_path.write_text(content, encoding="utf-8", newline="\n")
                    # Regular interface templates
                    else:
                        for iface in node.interfaces:
                            if not iface.configured:
                                continue

                            # TODO: Make more modular skip
                            # Skip .link generation for interfaces without MAC or loopback
                            if template_stem == "interface.link":
                                if iface.name == "lo" or not iface.mac_address:
                                    continue

                            iface_context = {**context, "iface": iface}
                            content = template.render(iface_context)
                            iface_path = Path(output_path_str.replace("{iface}", iface.name))
                            iface_path.parent.mkdir(parents=True, exist_ok=True)
                            iface_path.write_text(content, encoding="utf-8", newline="\n")

                # Per-VLAN templates
                elif "{vlan}" in output_path_str:
                    for vlan in node.vlans:
                        vlan_context = {**context, "vlan": vlan}
                        content = template.render(vlan_context)
                        if content.strip():
                            vlan_path = Path(output_path_str.replace("{vlan}", vlan.name))
                            vlan_path.parent.mkdir(parents=True, exist_ok=True)
                            vlan_path.write_text(content, encoding="utf-8", newline="\n")

                # Per-tunnel templates
                elif "{tunnel}" in output_path_str:
                    for tunnel in node.tunnels:
                        tunnel_context = {**context, "tunnel": tunnel}
                        content = template.render(tunnel_context)
                        if content.strip():
                            tunnel_path = Path(output_path_str.replace("{tunnel}", tunnel.name))
                            tunnel_path.parent.mkdir(parents=True, exist_ok=True)
                            tunnel_path.write_text(content, encoding="utf-8", newline="\n")

                # Per-bridge templates
                elif "{bridge}" in output_path_str:
                    if node.bridge and node.bridge.configured:
                        bridge_context = {**context}
                        content = template.render(bridge_context)
                        if content.strip():
                            bridge_path = Path(output_path_str.replace("{bridge}", node.bridge.name))
                            bridge_path.parent.mkdir(parents=True, exist_ok=True)
                            bridge_path.write_text(content, encoding="utf-8", newline="\n")

                # Regular templates
                else:
                    content = template.render(context)
                    if content.strip():
                        output_path.write_text(content, encoding="utf-8", newline="\n")

    def _get_output_path(self, template_stem: str, node: "InternalNode", outdir: Path) -> Path | None:
        """Map template stem to output file path."""

        path_map = {
            # networkd templates
            "hostname": outdir / "etc" / "hostname",
            "interface.link": outdir / "etc" / "systemd" / "network" / "10-{iface}.link",
            "interface.network": outdir / "etc" / "systemd" / "network" / "10-{iface}.network",
            "routes.network": outdir / "etc" / "systemd" / "network" / "20-routes.network",
            "sysctl.conf": outdir / "etc" / "sysctl.d" / "99-netloom.conf",
            # VLAN templates
            "vlan.netdev": outdir / "etc" / "systemd" / "network" / "11-{vlan}.netdev",
            "vlan.network": outdir / "etc" / "systemd" / "network" / "11-{vlan}.network",
            "vlan-parent.network": outdir / "etc" / "systemd" / "network" / "09-{iface}-vlan.network",
            # Bridge templates
            "bridge.netdev": outdir / "etc" / "systemd" / "network" / "05-{bridge}.netdev",
            "bridge.network": outdir / "etc" / "systemd" / "network" / "06-{bridge}.network",
            "bridge-port.network": outdir / "etc" / "systemd" / "network" / "07-{iface}-bridge.network",
            # Tunnel templates
            "tunnel.netdev": outdir / "etc" / "systemd" / "network" / "25-{tunnel}.netdev",
            "tunnel.network": outdir / "etc" / "systemd" / "network" / "25-{tunnel}.network",
            # BIRD templates
            "bird.conf": outdir / "etc" / "bird" / "bird.conf",
            "static.conf": outdir / "etc" / "bird" / "conf.d" / "static.conf",
            "rip.conf": outdir / "etc" / "bird" / "conf.d" / "rip.conf",
            "ospf.conf": outdir / "etc" / "bird" / "conf.d" / "ospf.conf",
            # nftables templates
            "nftables.conf": outdir / "etc" / "nftables.conf",
            # WireGuard templates
            "wg0.conf": outdir / "etc" / "wireguard" / "wg0.conf",
        }
        """Mapping of template stems to output paths."""

        return path_map.get(template_stem)

    def _generate_services_list(
        self,
        env: Environment,
        node: "InternalNode",
        outdir: Path,
    ) -> None:
        """Generate services.list for the VM agent."""

        try:
            template = env.get_template("services/services.list.j2")
            content = template.render(node=node)
            if content.strip():
                (outdir / "services.list").write_text(content, encoding="utf-8", newline="\n")
        except Exception:
            services = []

            # systemd-networkd for configured interfaces
            if any(iface.configured for iface in node.interfaces):
                services.append("+ systemd-networkd")

            # routing daemon
            if node.routing and node.routing.ospf_enabled:
                if node.routing.engine == "frr":
                    services.append("+ frr")
                elif node.routing.engine == "bird":
                    services.append("+ bird")

            # firewall
            if node.services and node.services.firewall:
                services.append("- iptables")
                services.append("+ nftables")

            # wireGuard
            if node.services and node.services.wireguard:
                services.append("+ wg-quick@wg0")

            if services:
                (outdir / "services.list").write_text("\n".join(services) + "\n", encoding="utf-8", newline="\n")

    def _write_debug_json(self, node: "InternalNode", outdir: Path) -> None:
        """Write debug JSON with node info."""

        (outdir / "_node.json").write_bytes(
            orjson.dumps(
                {
                    "name": node.name,
                    "role": node.role,
                    "interfaces": [
                        {
                            "name": iface.name,
                            "ip": iface.ip,
                            "gateway": iface.gateway,
                            "peer": iface.peer_node,
                        }
                        for iface in node.interfaces
                    ],
                },
                option=orjson.OPT_INDENT_2,
            ),
        )

    def attach(self, topo: "InternalTopology") -> None:
        """Copy generated configs into each node's config-drive."""

        infra = self.app.infrastructure

        for node in topo.nodes:
            if not node.config_dir:
                continue
            cfg = infra.get_configdrive(node)
            copy_tree_to_configdrive(cfg, Path(node.config_dir))

    def save(self, topo: "InternalTopology") -> None:
        """Pull changed files from config-drives back to saved directory."""

        infra = self.app.infrastructure

        for node in topo.nodes:
            if not node.saved_configs_dir:
                continue
            saved = Path(node.saved_configs_dir)
            cfg = infra.get_configdrive(node)
            copied = copy_from_configdrive(cfg, saved)

            if copied:
                self.console.print(f"  [green]{node.name}[/green]: {len(copied)} file(s)")
                for f in copied:
                    rel = f.relative_to(saved)
                    self.console.print(f"    - {rel}")
            else:
                self.console.print(f"  [yellow]{node.name}[/yellow]: no files found")

    def restore(self, topo: "InternalTopology") -> None:
        """Restore saved configs into the staging config_dir."""

        for node in topo.nodes:
            if not node.saved_configs_dir or not node.config_dir:
                continue
            saved = Path(node.saved_configs_dir)
            if not saved.exists():
                continue
            target = Path(node.config_dir)
            target.mkdir(parents=True, exist_ok=True)
            for p in saved.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(saved)
                    dst = target / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(p.read_bytes())
