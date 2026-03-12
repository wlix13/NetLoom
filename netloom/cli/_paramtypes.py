"""Custom Click paramtypes with shell completion support."""

from pathlib import Path

import rich_click as click
from click.shell_completion import CompletionItem


def _parse_incomplete_path(incomplete: str) -> tuple[Path, str, str]:
    """Parse an incomplete path string into (parent_dir, prefix, stem_filter)."""

    path = Path(incomplete).expanduser() if incomplete else Path(".")
    if incomplete and not incomplete.endswith("/"):
        parent = path.parent
        prefix = (str(parent) + "/") if str(parent) != "." else ""
        stem_filter = path.name
    else:
        parent = path if incomplete else Path(".")
        prefix = incomplete if incomplete else ""
        stem_filter = ""
    return parent, prefix, stem_filter


def _file_completions(incomplete: str, extensions: set[str]) -> list[CompletionItem]:
    """Return completion items for files with the given extensions."""

    parent, prefix, stem_filter = _parse_incomplete_path(incomplete)
    completions: list[CompletionItem] = []
    try:
        for item in sorted(parent.iterdir(), key=lambda p: (p.is_file(), p.name)):
            if not item.name.startswith(stem_filter):
                continue
            if item.is_file() and item.suffix.lower() in extensions:
                completions.append(CompletionItem(prefix + item.name))
            elif item.is_dir():
                completions.append(CompletionItem(prefix + item.name + "/"))
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        pass

    return completions


class TopologyFileType(click.ParamType):
    name = "topology_file"

    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> list[CompletionItem]:
        return _file_completions(incomplete, {".yaml", ".yml"})

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
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

    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> list[CompletionItem]:
        return _file_completions(incomplete, {".ova"})

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
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

    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> list[CompletionItem]:
        parent, prefix, stem_filter = _parse_incomplete_path(incomplete)
        completions: list[CompletionItem] = []
        try:
            for item in sorted(parent.iterdir(), key=lambda p: p.name):
                if item.is_dir() and item.name.startswith(stem_filter):
                    completions.append(CompletionItem(prefix + item.name + "/"))
        except (FileNotFoundError, NotADirectoryError, PermissionError):
            pass

        return completions

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
        path = Path(value).expanduser()
        if self.must_exist and not path.exists():
            self.fail(f"Directory does not exist: {value}", param, ctx)
        if path.exists() and not path.is_dir():
            self.fail(f"Path exists but is not a directory: {value}", param, ctx)
        return str(path)


class TemplateSetType(click.ParamType):
    name = "template_set"

    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> list[CompletionItem]:
        try:
            app = ctx.obj["app"] if ctx and ctx.obj else None
            if app is None:
                from ..core.application import Application

                app = Application.current()
            templates = app.config.list_template_sets()
            return [CompletionItem(tpl) for tpl in templates if tpl.startswith(incomplete)]
        except Exception:
            return []

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
        if not (ctx and ctx.obj and "app" in ctx.obj):
            return value
        app = ctx.obj["app"]
        try:
            templates = app.config.list_template_sets()
        except Exception as e:
            self.fail(f"Failed to load template sets: {e}", param, ctx)
        if value not in templates:
            self.fail(f"Unknown template set '{value}'. Available: {', '.join(templates)}", param, ctx)
        return value


class NodeNameType(click.ParamType):
    name = "node_name"

    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> list[CompletionItem]:
        try:
            if ctx and ctx.obj and "internal" in ctx.obj:
                internal = ctx.obj["internal"]
                return [CompletionItem(n.name) for n in internal.nodes if n.name.startswith(incomplete)]
        except Exception:  # noqa: S110
            pass
        return []

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
        if not (ctx and ctx.obj and "internal" in ctx.obj):
            return value
        internal = ctx.obj["internal"]
        try:
            node_names = [n.name for n in internal.nodes]
        except Exception as e:
            self.fail(f"Failed to load node list: {e}", param, ctx)
        if value not in set(node_names):
            self.fail(f"Unknown node '{value}'. Available: {', '.join(node_names)}", param, ctx)
        return value
