from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


RenderFunc = Callable[[dict, Path], None]


@dataclass
class TemplateSet:
    name: str
    render: RenderFunc


_REGISTRY: dict[str, TemplateSet] = {}


def register_template_set(tpl_set: TemplateSet) -> None:
    _REGISTRY[tpl_set.name] = tpl_set


def get_template_set(name: str) -> TemplateSet:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown template set: {name!r}")
    return _REGISTRY[name]


def make_env(searchpaths: Iterable[str | Path]) -> Environment:
    return Environment(
        loader=FileSystemLoader([Path(p) for p in searchpaths]),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
