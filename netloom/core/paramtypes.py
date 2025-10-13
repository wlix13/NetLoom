"""Custom Click paramtypes with shell completion support."""

from pathlib import Path
from typing import TYPE_CHECKING

import click


if TYPE_CHECKING:
    from click.shell_completion import CompletionItem


class TopologyFileType(click.ParamType):
    name = "topology_file"

    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> list["CompletionItem"]:
        """Provide shell completion for topology files."""

        path = Path(incomplete).expanduser() if incomplete else Path(".")
        parent = path.parent if path.name else path
        if not parent.exists():
            parent = Path(".")

        completions = []
        try:
            for item in parent.iterdir():
                if item.is_file() and item.suffix.lower() in (".yaml", ".yml"):
                    name = item.name
                    if incomplete and not name.startswith(Path(incomplete).name):
                        continue
                    completions.append(click.shell_completion.CompletionItem(name))
                elif item.is_dir() and (not incomplete or item.name.startswith(Path(incomplete).name)):
                    completions.append(click.shell_completion.CompletionItem(f"{item.name}/"))
        except PermissionError:
            pass

        return completions

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
        """Validate and convert the topology file."""

        path = Path(value).expanduser()
        if not path.exists():
            self.fail(f"Topology file does not exist: {value}", param, ctx)
        if not path.is_file():
            self.fail(f"Path is not a file: {value}", param, ctx)
        if path.suffix.lower() not in (".yaml", ".yml"):
            self.fail(f"Topology file must be a YAML file (.yaml or .yml): {value}", param, ctx)
        return str(path)


class OvaFileType(click.ParamType):
    name = "ova_file"

    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> list["CompletionItem"]:
        """Provide shell completion for OVA files."""

        path = Path(incomplete).expanduser() if incomplete else Path(".")
        parent = path.parent if path.name else path
        if not parent.exists():
            parent = Path(".")

        completions = []
        try:
            for item in parent.iterdir():
                if item.is_file() and item.suffix.lower() == ".ova":
                    name = item.name
                    if incomplete and not name.startswith(Path(incomplete).name):
                        continue
                    completions.append(click.shell_completion.CompletionItem(name))
                elif item.is_dir() and (not incomplete or item.name.startswith(Path(incomplete).name)):
                    completions.append(click.shell_completion.CompletionItem(f"{item.name}/"))
        except PermissionError:
            pass

        return completions

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
        """Validate and convert the OVA file path."""

        path = Path(value).expanduser()
        if not path.exists():
            self.fail(f"OVA file does not exist: {value}", param, ctx)
        if not path.is_file():
            self.fail(f"Path is not a file: {value}", param, ctx)
        if path.suffix.lower() != ".ova":
            self.fail(f"File must be an OVA file (.ova): {value}", param, ctx)
        return str(path)


class DirectoryType(click.ParamType):
    name = "directory"

    def __init__(self, must_exist: bool = False) -> None:
        super().__init__()
        self.must_exist = must_exist

    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> list["CompletionItem"]:
        """Provide shell completion for directory paths."""

        path = Path(incomplete).expanduser() if incomplete else Path(".")
        parent = path.parent if path.name else path
        if not parent.exists():
            parent = Path(".")

        completions = []
        try:
            for item in parent.iterdir():
                if item.is_dir():
                    name = item.name
                    if incomplete and not name.startswith(Path(incomplete).name):
                        continue
                    completions.append(click.shell_completion.CompletionItem(f"{name}/"))
        except PermissionError:
            pass

        return completions

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
        """Validate and convert the directory."""

        path = Path(value).expanduser()
        if self.must_exist and not path.exists():
            self.fail(f"Directory does not exist: {value}", param, ctx)
        if path.exists() and not path.is_dir():
            self.fail(f"Path exists but is not a directory: {value}", param, ctx)
        return str(path)


class TemplateSetType(click.ParamType):
    name = "template_set"

    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> list["CompletionItem"]:
        """Provide shell completion for template sets."""

        try:
            if ctx and ctx.obj and "app" in ctx.obj:
                app = ctx.obj["app"]
                templates = app.config.list_template_sets()
                return [click.shell_completion.CompletionItem(tpl) for tpl in templates if tpl.startswith(incomplete)]
        except Exception:  # noqa: S110
            pass

        try:
            from ..core.application import Application

            app = Application.current()
            templates = app.config.list_template_sets()
            return [click.shell_completion.CompletionItem(tpl) for tpl in templates if tpl.startswith(incomplete)]
        except Exception:  # noqa: S110
            return []

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
        """Validate template set."""

        try:
            if ctx and ctx.obj and "app" in ctx.obj:
                app = ctx.obj["app"]
                templates = app.config.list_template_sets()
                if value not in templates:
                    self.fail(
                        f"Unknown template set '{value}'. Available: {', '.join(templates)}",
                        param,
                        ctx,
                    )
        except Exception:  # noqa: S110
            pass

        return value


class NodeNameType(click.ParamType):
    name = "node_name"

    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> list["CompletionItem"]:
        """Provide shell completion for node names."""

        try:
            if ctx and ctx.obj and "internal" in ctx.obj:
                internal = ctx.obj["internal"]
                nodes = [node.name for node in internal.nodes]
                return [click.shell_completion.CompletionItem(name) for name in nodes if name.startswith(incomplete)]
        except Exception:  # noqa: S110
            pass

        return []

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
        """Validate node name."""

        try:
            if ctx and ctx.obj and "internal" in ctx.obj:
                internal = ctx.obj["internal"]
                node_names = [node.name for node in internal.nodes]
                if value not in node_names:
                    self.fail(
                        f"Unknown node '{value}'. Available nodes: {', '.join(node_names)}",
                        param,
                        ctx,
                    )
        except Exception:  # noqa: S110
            pass

        return value
