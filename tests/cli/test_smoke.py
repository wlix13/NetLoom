"""CLI smoke tests through Click's test runner (no VMs, real templates)."""

from collections.abc import Iterator

import pytest
from click.testing import CliRunner

from netloom.core.application import Application
from tests.conftest import DEFAULT_COMPONENTS, EXAMPLE_TOPOLOGY


pytestmark = pytest.mark.component


@pytest.fixture
def cli() -> Iterator:
    """The real CLI group bound to a fresh Application singleton.

    Re-registering after the module-level registration in ``netloom.cli`` is
    harmless (controllers are replaced, commands stay attached), and it is
    required for every test after the first, which starts from a reset app.
    """
    Application.reset()
    from netloom.cli import cli as cli_group

    application = Application.current()
    for component_cls in DEFAULT_COMPONENTS:
        application.register(component_cls)
    yield cli_group
    Application.reset()


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _base_args(tmp_path) -> list[str]:
    return ["--topology", str(EXAMPLE_TOPOLOGY), "--workdir", str(tmp_path / "wd")]


def test_show_renders_topology(cli, runner, tmp_path):
    result = runner.invoke(cli, [*_base_args(tmp_path), "show"])
    assert result.exit_code == 0, result.output
    assert "Example Lab Topology" in result.output


def test_missing_topology_file_is_usage_error(cli, runner):
    result = runner.invoke(cli, ["--topology", "no-such-lab.yaml", "show"])
    assert result.exit_code == 2
    captured = result.output
    try:
        captured += result.stderr
    except (ValueError, AttributeError):
        pass  # older click mixes stderr into output already
    assert "does not exist" in captured


def test_faults_catalog_lists_types(cli, runner, tmp_path):
    result = runner.invoke(cli, [*_base_args(tmp_path), "faults", "catalog"])
    assert result.exit_code == 0, result.output
    assert "wrong-ip-address" in result.output


def test_broken_lab_generate_deploy_reveal(cli, runner, tmp_path):
    spec_path = tmp_path / "lab.faults.yaml"
    workdir = tmp_path / "wd"

    generate = runner.invoke(
        cli,
        [*_base_args(tmp_path), "faults", "generate", "--count", "3", "--seed", "42", "-o", str(spec_path)],
    )
    assert generate.exit_code == 0, generate.output
    assert spec_path.is_file()

    deploy = runner.invoke(cli, [*_base_args(tmp_path), "--faults", str(spec_path), "steps", "gen"])
    assert deploy.exit_code == 0, deploy.output
    assert "Broken-lab mode: 3 fault(s) injected" in deploy.output
    assert (workdir / "faults-applied.yaml").is_file()

    reveal = runner.invoke(cli, [*_base_args(tmp_path), "faults", "reveal", "--answers"])
    assert reveal.exit_code == 0, reveal.output
    assert "seed=42" in reveal.output


def test_reveal_without_deploy_fails_cleanly(cli, runner, tmp_path):
    result = runner.invoke(cli, [*_base_args(tmp_path), "faults", "reveal"])
    assert result.exit_code != 0
