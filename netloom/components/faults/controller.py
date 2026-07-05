"""Faults controller: fault selection, application and answer-key management."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from netloom.core.controller import BaseController

from .catalog import FaultCatalog, FaultDefinition, FaultTarget
from .errors import FaultNotApplicable, NoFaultsApplied, NotEnoughFaultCandidates, UnknownFaultType
from .models import RANDOM_FAULT_TYPE, FaultCategory, FaultReport, FaultSpec, FaultSpecEntry


if TYPE_CHECKING:
    from netloom.core.application import Application
    from netloom.models.internal import InternalTopology


ANSWER_KEY_FILENAME = "faults-applied.yaml"

_Plan = list[tuple[FaultDefinition, FaultTarget]]


class FaultsController(BaseController["Application"]):
    """Selects faults deterministically and applies them to an internal topology."""

    def __init__(self, app: Application) -> None:
        super().__init__(app)
        self.catalog = FaultCatalog()

    @property
    def answer_key_path(self) -> Path:
        return Path(self.app.workdir) / ANSWER_KEY_FILENAME

    # ── selection ─────────────────────────────────────────────────────────────

    def _definition(self, type_id: str) -> FaultDefinition:
        definition = self.catalog.get(type_id)
        if definition is None:
            raise UnknownFaultType(type_id, self.catalog.names())
        return definition

    def resolve(self, topo: InternalTopology, spec: FaultSpec) -> _Plan:
        """Turn spec entries into a concrete (definition, target) plan.

        Selection is deterministic for a given topology + spec (seed included);
        each (node, target) pair receives at most one fault.
        """
        rng = random.Random(spec.seed)  # noqa: S311 — reproducibility, not cryptography
        plan: _Plan = []
        used: set[tuple[str, str | None]] = set()

        for entry in spec.faults:
            if entry.type == RANDOM_FAULT_TYPE:
                plan.extend(self._pick_random(topo, entry, rng, used))
            else:
                plan.append(self._pick_explicit(topo, entry, rng, used))
        return plan

    def _pick_explicit(
        self,
        topo: InternalTopology,
        entry: FaultSpecEntry,
        rng: random.Random,
        used: set[tuple[str, str | None]],
    ) -> tuple[FaultDefinition, FaultTarget]:
        definition = self._definition(entry.type)
        targets = definition.find_targets(topo)
        if entry.node:
            targets = [t for t in targets if t.node == entry.node]
        if entry.target:
            targets = [t for t in targets if t.item == entry.target]
        targets = [t for t in targets if (t.node, t.item) not in used]
        if not targets:
            where = f" on node '{entry.node}'" if entry.node else " in this topology"
            raise FaultNotApplicable(entry.type, f"no applicable target{where}")
        target = rng.choice(targets)
        used.add((target.node, target.item))
        return definition, target

    def _pick_random(
        self,
        topo: InternalTopology,
        entry: FaultSpecEntry,
        rng: random.Random,
        used: set[tuple[str, str | None]],
    ) -> _Plan:
        definitions = [
            d
            for d in self.catalog.all()
            if (not entry.categories or d.category in entry.categories) and d.type_id not in entry.exclude
        ]
        pool: _Plan = [(d, t) for d in definitions for t in d.find_targets(topo) if (t.node, t.item) not in used]
        if len(pool) < entry.count:
            raise NotEnoughFaultCandidates(entry.count, len(pool))

        picked: _Plan = []
        for _ in range(entry.count):
            definition, target = pool[rng.randrange(len(pool))]
            picked.append((definition, target))
            used.add((target.node, target.item))
            pool = [(d, t) for d, t in pool if (t.node, t.item) != (target.node, target.item)]
        return picked

    # ── application ───────────────────────────────────────────────────────────

    def apply_spec(self, topo: InternalTopology, spec_path: str | Path) -> FaultReport:
        """Load *spec_path*, mutate *topo* in place and write the answer key."""
        spec = FaultSpec.from_yaml(spec_path)
        plan = self.resolve(topo, spec)
        rng = random.Random(spec.seed)  # noqa: S311 — reproducibility, not cryptography
        applied = [definition.apply(topo, target, rng) for definition, target in plan]

        report = FaultReport(
            topology_id=topo.id,
            seed=spec.seed,
            spec_file=str(spec_path),
            generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            faults=applied,
        )
        report.to_yaml(self.answer_key_path)
        return report

    # ── instructor tooling ────────────────────────────────────────────────────

    def generate_spec(
        self,
        topo: InternalTopology,
        count: int,
        seed: int | None = None,
        categories: list[FaultCategory] | None = None,
        exclude: list[str] | None = None,
    ) -> FaultSpec:
        """Randomly select *count* faults and return them as an explicit, editable spec."""
        if seed is None:
            seed = random.randrange(2**31)  # noqa: S311 — reproducibility, not cryptography
        probe = FaultSpec(
            seed=seed,
            faults=[
                FaultSpecEntry(
                    type=RANDOM_FAULT_TYPE,
                    count=count,
                    categories=categories or [],
                    exclude=exclude or [],
                )
            ],
        )
        plan = self.resolve(topo, probe)
        return FaultSpec(
            seed=seed,
            faults=[FaultSpecEntry(type=d.type_id, node=t.node, target=t.item) for d, t in plan],
        )

    def reveal(self) -> FaultReport:
        """Load the answer key written by the last ``--faults`` deployment."""
        path = self.answer_key_path
        if not path.exists():
            raise NoFaultsApplied(str(path))
        return FaultReport.from_yaml(path)

    def catalog_overview(self, topo: InternalTopology) -> list[tuple[FaultDefinition, int]]:
        """Return every catalog definition with its applicable-target count for *topo*."""
        return [(d, len(d.find_targets(topo))) for d in self.catalog.all()]
