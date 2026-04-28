"""Template set registry: register and discover Jinja2 template sets."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from netloom.models.internal import InternalNode


@dataclass
class TemplateSetDescriptor:
    """Describes one Jinja2 template set.

    *output_paths* maps template stems to paths relative to a node's config
    output directory.  Path values may contain ``{iface}``, ``{vlan}``,
    ``{tunnel}`` or ``{bridge}`` placeholders; these are expanded per-item by
    ``ConfigController._iter_render_items``.

    *condition* is called with the ``InternalNode`` being rendered.  The set is
    skipped entirely when it returns ``False``, replacing the hard-coded
    ``if`` chains that previously lived in ``ConfigController.generate``.

    *templates_subdir* defaults to *name* (i.e. ``templates/networkd/``).
    Override when the template files live in a different subdirectory.
    """

    name: str
    output_paths: dict[str, str]
    condition: Callable[[InternalNode], bool] = field(default=lambda _: True)
    templates_subdir: str = ""

    def __post_init__(self) -> None:
        if not self.templates_subdir:
            self.templates_subdir = self.name


class TemplateRegistry:
    """Registry of available template sets."""

    def __init__(self) -> None:
        self._sets: dict[str, TemplateSetDescriptor] = {}

    def register(self, desc: TemplateSetDescriptor) -> None:
        """Add or replace a template set descriptor."""
        self._sets[desc.name] = desc

    def get(self, name: str) -> TemplateSetDescriptor | None:
        """Return the descriptor for *name*, or ``None``."""
        return self._sets.get(name)

    def names(self) -> list[str]:
        """Sorted list of registered template set names."""
        return sorted(self._sets)

    def iter_applicable(self, node: InternalNode) -> Iterator[TemplateSetDescriptor]:
        """Yield every descriptor whose condition is satisfied for *node*."""
        for desc in self._sets.values():
            if desc.condition(node):
                yield desc
