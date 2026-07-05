"""Integration tests that spin up real VirtualBox VMs.

Excluded by default (``-m 'not integration'`` in addopts). Run with:

    NETLOOM_LAB=1 uv run --group tests pytest -m integration

Requirements: VirtualBox installed, a base OVA imported (or --ova pointing at
one), and enough RAM for the example topology.
"""

import os

import pytest


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("NETLOOM_LAB") != "1",
        reason="set NETLOOM_LAB=1 to run VM integration tests",
    ),
]


def test_up_status_down_roundtrip():
    """Planned harness: full lifecycle against real VirtualBox.

    Roadmap:
    1. ``netloom up --yes`` on schemas/example.yaml with a scratch workdir
    2. poll ``InfrastructureController.status`` until every node is RUNNING
    3. open the tcp-serial console of R1 and wait for a login prompt
    4. exec ``ping -c1`` H1 → H2 over serial — connectivity smoke
    5. broken-lab variant: deploy with --faults, assert the faulted pair
       does NOT ping, then fix the config in-VM and assert recovery
    6. ``netloom down --yes``; assert VMs are gone

    Deliberately unimplemented until a CI-capable VirtualBox runner exists.
    """
    pytest.skip("VM integration harness not implemented yet — see docstring roadmap")
