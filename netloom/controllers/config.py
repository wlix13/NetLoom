"""Config controller for template rendering and config-drive operations."""

from collections.abc import Iterator
from functools import cached_property
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

import orjson
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jinja2.exceptions import TemplateError

from ..core.controller import BaseController
from ..core.enums import InterfaceKind, RoutingEngine, TemplateSet
from ..data import copy_from_configdrive, copy_tree_to_configdrive


if TYPE_CHECKING:
    from ..core.application import Application
    from ..models.internal import InternalNode, InternalTopology


class ConfigController(BaseController["Application"]):
    """Controller for configuration generation and management."""

    # Maps template stem → output path relative to outdir.
    # Placeholders {iface}, {vlan}, {tunnel}, {bridge} are expanded per-item
    # by _iter_render_items / _iter_iface_items.
    _OUTPUT_PATHS: dict[str, str] = {
        # networkd templates
        "hostname": "etc/hostname",
        "interface.link": "etc/systemd/network/10-{iface}.link",
        "interface.network": "etc/systemd/network/10-{iface}.network",
        "routes.network": "etc/systemd/network/20-routes.network",
        "sysctl.conf": "etc/sysctl.d/99-netloom.conf",
        # VLAN templates
        "vlan.netdev": "etc/systemd/network/11-{vlan}.netdev",
        "vlan.network": "etc/systemd/network/11-{vlan}.network",
        "vlan-parent.network": "etc/systemd/network/09-{iface}-vlan.network",
        # Bridge templates
        "bridge.netdev": "etc/systemd/network/05-{bridge}.netdev",
        "bridge.network": "etc/systemd/network/06-{bridge}.network",
        "bridge-port.network": "etc/systemd/network/07-{iface}-bridge.network",
        # Tunnel templates
        "tunnel.netdev": "etc/systemd/network/25-{tunnel}.netdev",
        "tunnel.network": "etc/systemd/network/25-{tunnel}.network",
        # BIRD templates
        "bird.conf": "etc/bird/bird.conf",
        "static.conf": "etc/bird/conf.d/static.conf",
        "rip.conf": "etc/bird/conf.d/rip.conf",
        "ospf.conf": "etc/bird/conf.d/ospf.conf",
        # nftables templates
        "nftables.conf": "etc/nftables.conf",
        # WireGuard templates
        "wg0.conf": "etc/wireguard/wg0.conf",
    }

    def __init__(self, app: "Application") -> None:
        super().__init__(app)
        self._env: Environment | None = None

    @cached_property
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
            self._render_template_set(env, TemplateSet.NETWORKD, context, outdir)

            # Render BIRD templates if routing is configured with bird engine
            if node.routing and node.routing.engine == RoutingEngine.BIRD and node.routing.configured:
                self._render_template_set(env, TemplateSet.BIRD, context, outdir)

            # Render nftables templates if firewall is configured
            if node.services and node.services.firewall:
                self._render_template_set(env, TemplateSet.NFTABLES, context, outdir)

            # Render WireGuard templates if WireGuard is configured
            if node.services and node.services.wireguard:
                self.console.print(
                    f"  [yellow]Warning: WireGuard private key for '{node.name}' "
                    "will be written to config drive in plaintext.[/yellow]"
                )
                self._render_template_set(env, TemplateSet.WIREGUARD, context, outdir)

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
            if output_path is None:
                continue

            for resolved_path, item_context in self._iter_render_items(template_stem, str(output_path), node, context):
                content = template.render(item_context)
                if content.strip():
                    resolved_path.parent.mkdir(parents=True, exist_ok=True)
                    resolved_path.write_text(content, encoding="utf-8", newline="\n")

    def _iter_render_items(
        self,
        template_stem: str,
        output_path_str: str,
        node: "InternalNode",
        context: dict,
    ) -> Iterator[tuple[Path, dict]]:
        """Yield ``(resolved_output_path, render_context)`` for each item to render."""

        if "{iface}" in output_path_str:
            yield from self._iter_iface_items(template_stem, output_path_str, node, context)
        elif "{vlan}" in output_path_str:
            for vlan in node.vlans:
                # Bridge-member VLANs are configured by bridge-port.network; skip their .network file
                if template_stem == "vlan.network" and vlan.bridge_name is not None:
                    continue
                yield Path(output_path_str.replace("{vlan}", vlan.name)), {**context, "vlan": vlan}
        elif "{tunnel}" in output_path_str:
            for tunnel in node.tunnels:
                yield Path(output_path_str.replace("{tunnel}", tunnel.name)), {**context, "tunnel": tunnel}
        elif "{bridge}" in output_path_str:
            for bridge in node.bridges:
                if bridge.configured:
                    yield Path(output_path_str.replace("{bridge}", bridge.name)), {**context, "bridge": bridge}
        else:
            yield Path(output_path_str), context

    def _iter_iface_items(
        self,
        template_stem: str,
        output_path_str: str,
        node: "InternalNode",
        context: dict,
    ) -> Iterator[tuple[Path, dict]]:
        """Yield ``(resolved_path, context)`` for per-interface template expansion."""

        if "vlan-parent" in template_stem:
            parent_ifaces = {vlan.parent for vlan in node.vlans}
            for iface in node.interfaces:
                if iface.name in parent_ifaces:
                    yield Path(output_path_str.replace("{iface}", iface.name)), {**context, "iface": iface}

        elif "bridge-port" in template_stem:
            for iface in node.interfaces:
                if iface.bridge_name is not None:
                    yield Path(output_path_str.replace("{iface}", iface.name)), {**context, "iface": iface}
            for vlan in node.vlans:
                if vlan.bridge_name is not None:
                    yield Path(output_path_str.replace("{iface}", vlan.name)), {**context, "iface": vlan}

        else:
            vlan_parents = {vlan.parent for vlan in node.vlans}
            for iface in node.interfaces:
                if not iface.configured:
                    continue
                # Skip .link generation for loopbacks or interfaces without a MAC
                is_link_template = template_stem == "interface.link"
                if is_link_template and (iface.kind == InterfaceKind.LOOPBACK or not iface.mac_address):
                    continue
                # Bridge-member interfaces are fully configured by bridge-port.network; skip their .network file
                # VLAN parent interfaces are fully configured by vlan-parent.network; skip their .network file
                if not is_link_template and (iface.bridge_name is not None or iface.name in vlan_parents):
                    continue
                yield Path(output_path_str.replace("{iface}", iface.name)), {**context, "iface": iface}

    def _get_output_path(self, template_stem: str, node: "InternalNode", outdir: Path) -> Path | None:
        """Map template stem to output file path."""

        relative = self._OUTPUT_PATHS.get(template_stem)
        if relative is None:
            return None
        return outdir / relative

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
        except TemplateError:
            services = []

            # systemd-networkd for any network configuration
            if any(iface.configured for iface in node.interfaces) or node.bridges or node.vlans or node.tunnels:
                services.append("+ systemd-networkd")

            # routing daemon
            if node.routing and node.routing.ospf_enabled:
                if node.routing.engine == RoutingEngine.FRR:
                    services.append("+ frr")
                elif node.routing.engine == RoutingEngine.BIRD:
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
                    self.console.print(f"    - {f.relative_to(saved)}")
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
