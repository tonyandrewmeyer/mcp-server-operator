# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.
#
# The integration tests use the Jubilant library. See https://documentation.ubuntu.com/jubilant/

import logging
import pathlib

import jubilant
import pytest

logger = logging.getLogger(__name__)


def _find_repo_root() -> pathlib.Path:
    """Walk up from this file to find the repository root (contains Makefile)."""
    path = pathlib.Path(__file__).resolve().parent
    while path != path.parent:
        if (path / "Makefile").exists():
            return path
        path = path.parent
    raise FileNotFoundError("Could not find repository root")


@pytest.fixture(scope="module")
def principal_charm():
    """Return the path to the pre-built demo principal charm."""
    demo_dir = _find_repo_root() / "demo" / "principal"
    charm_paths = list(demo_dir.glob("*.charm"))
    if not charm_paths:
        pytest.skip("No demo-principal .charm file found; build it first")
    return charm_paths[0]


def test_deploy(charm: pathlib.Path, principal_charm: pathlib.Path, juju: jubilant.Juju):
    """Deploy the subordinate charm alongside a principal and verify it goes active."""
    juju.deploy(principal_charm.resolve(), app="demo-principal")
    juju.deploy(charm.resolve(), app="mcp-server")
    juju.integrate("demo-principal:mcp", "mcp-server:mcp")
    juju.wait(jubilant.all_active, timeout=300)

    status = juju.status()
    assert status.apps["mcp-server"].app_status.current == "active"
