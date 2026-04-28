"""Config controller: template rendering and config-drive operations."""

from __future__ import annotations

from collections.abc import Iterator
from functools import cached_property
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

import orjson
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jinja2.exceptions import TemplateNotFound

from netloom.core.controller import BaseController
from netloom.core.enums import InterfaceKind, RoutingEngine
from netloom.templates.registry import TemplateRegistry, TemplateSetDescriptor


if TYPE_CHECKING:
    from netloom.core.application import Application
    from netloom.models.internal import InternalNode, InternalTopology


class ConfigController(BaseController["Application"]):
    """Renders Jinja2 templates and manages config-drive operations."""

    def __init__(self, app: Application) -> None:
        super().__init__(app)
        self.registry = TemplateRegistry()

    @cached_property
    def templates_dir(self) -> Path:
        with resources.as_file(resources.files("netloom") / "templates") as p:
            return p

    def get_env(self, extra_paths: list[Path] | None = None) -> Environment:
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
        """Return sorted list of registered template set names."""
        return self.registry.names()

    def rendered_sets(self, topo: InternalTopology) -> set[str]:
        """Return the union of applicable template set names across all nodes."""
        result: set[str] = set()
        for node in topo.nodes:
            for desc in self.registry.iter_applicable(node):
                result.add(desc.name)
        return result

    def generate(self, topo: InternalTopology, extra_paths: list[Path] | None = None) -> None:
        """Render all applicable template sets for each node in *topo*."""

        env = self.get_env(extra_paths)

        for node in topo.nodes:
            if not node.config_dir:
                continue

            outdir = Path(node.config_dir)
            outdir.mkdir(parents=True, exist_ok=True)
            context = {"node": node, "topology": topo}

            for desc in self.registry.iter_applicable(node):
                self._render_template_set(env, desc, context, outdir)

            self._generate_services_list(env, node, outdir)

            if self.app.debug:
                self._write_debug_json(node, outdir)

    def _render_template_set(
        self,
        env: Environment,
        desc: TemplateSetDescriptor,
        context: dict,
        outdir: Path,
    ) -> None:
        set_dir = self.templates_dir / desc.templates_subdir
        if not set_dir.exists():
            self.console.print(f"[yellow]Warning: Template set '{desc.name}' not found at '{set_dir}'[/yellow]")
            return

        node = context["node"]

        for template_file in set_dir.glob("*.j2"):
            template_name = f"{desc.templates_subdir}/{template_file.name}"
            template = env.get_template(template_name)
            template_stem = template_file.stem

            output_path = self._get_output_path(desc, template_stem, node, outdir)
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
        node: InternalNode,
        context: dict,
    ) -> Iterator[tuple[Path, dict]]:
        if "{iface}" in output_path_str:
            yield from self._iter_iface_items(template_stem, output_path_str, node, context)
        elif "{vlan}" in output_path_str:
            for vlan in node.vlans:
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
        node: InternalNode,
        context: dict,
    ) -> Iterator[tuple[Path, dict]]:
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
                is_link_template = template_stem == "interface.link"
                if is_link_template and (iface.kind == InterfaceKind.LOOPBACK or not iface.mac_address):
                    continue
                if not is_link_template and (iface.bridge_name is not None or iface.name in vlan_parents):
                    continue
                if is_link_template:
                    # Higher VBox slot → lower file priority → processed first by udev.
                    # Unwinds rename chains from the tail to avoid name-in-use conflicts.
                    slot = iface.vbox_nic_index if iface.vbox_nic_index is not None else 1
                    priority = 46 - slot
                    yield (
                        Path(output_path_str).parent / f"{priority:02d}-{iface.name}.link",
                        {**context, "iface": iface},
                    )
                else:
                    yield Path(output_path_str.replace("{iface}", iface.name)), {**context, "iface": iface}

    def _get_output_path(
        self,
        desc: TemplateSetDescriptor,
        template_stem: str,
        node: InternalNode,
        outdir: Path,
    ) -> Path | None:
        relative = desc.output_paths.get(template_stem)
        if relative is None:
            self.console.print(
                f"[yellow]Warning: no output path for template '{template_stem}' in set '{desc.name}'[/yellow]"
            )
            return None
        return outdir / relative

    def _generate_services_list(self, env: Environment, node: InternalNode, outdir: Path) -> None:
        try:
            template = env.get_template("services/services.list.j2")
            content = template.render(node=node)
            if content.strip():
                (outdir / "services.list").write_text(content, encoding="utf-8", newline="\n")
        except TemplateNotFound:
            services: list[str] = []
            if any(iface.configured for iface in node.interfaces) or node.bridges or node.vlans or node.tunnels:
                services.append("+ systemd-networkd")
            if node.routing and node.routing.ospf_enabled:
                if node.routing.engine == RoutingEngine.FRR:
                    services.append("+ frr")
                elif node.routing.engine == RoutingEngine.BIRD:
                    services.append("+ bird")
            if node.services and node.services.firewall:
                services.append("- iptables")
                services.append("+ nftables")
            if node.services and node.services.wireguard:
                services.append("+ wg-quick@wg0")
            if services:
                (outdir / "services.list").write_text("\n".join(services) + "\n", encoding="utf-8", newline="\n")

    def _write_debug_json(self, node: InternalNode, outdir: Path) -> None:
        (outdir / "_node.json").write_bytes(
            orjson.dumps(
                {
                    "name": node.name,
                    "role": node.role,
                    "interfaces": [
                        {"name": iface.name, "ip": iface.ip, "gateway": iface.gateway, "peer": iface.peer_node}
                        for iface in node.interfaces
                    ],
                },
                option=orjson.OPT_INDENT_2,
            )
        )

    def attach(self, topo: InternalTopology) -> None:
        """Copy generated configs into each node's config medium."""
        for node in topo.nodes:
            if not node.config_dir:
                continue
            self.app.hypervisor.inject_configs(node, Path(node.config_dir))

    def save(self, topo: InternalTopology) -> None:
        """Pull changed files from config media back to saved directory."""
        for node in topo.nodes:
            if not node.saved_configs_dir:
                continue
            saved = Path(node.saved_configs_dir)
            copied = self.app.hypervisor.extract_configs(node, saved)
            if copied:
                self.console.print(f"  [green]{node.name}[/green]: {len(copied)} file(s)")
                for f in copied:
                    self.console.print(f"    - {f.relative_to(saved)}")
            else:
                self.console.print(f"  [yellow]{node.name}[/yellow]: no files found")

    def restore(self, topo: InternalTopology) -> None:
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
