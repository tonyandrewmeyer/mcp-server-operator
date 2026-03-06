# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

import json

import ops
from ops import testing

from charmlibs.interfaces.mcp import ExecHandler, McpDefinitions, McpProvider, McpRequirer, Tool


class ProviderCharm(ops.CharmBase):
    """Minimal charm that uses McpProvider."""

    META = {
        "name": "test-provider",
        "provides": {"mcp": {"interface": "mcp"}},
    }

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self.mcp = McpProvider(self, "mcp")


class RequirerCharm(ops.CharmBase):
    """Minimal charm that uses McpRequirer."""

    META = {
        "name": "test-requirer",
        "subordinate": True,
        "requires": {"mcp": {"interface": "mcp", "scope": "container"}},
    }

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self.mcp = McpRequirer(self, "mcp")


SAMPLE_DEFINITIONS = McpDefinitions(
    tools=[
        Tool(
            name="hello",
            description="Say hello",
            handler=ExecHandler(command=["echo", "hello"]),
        ),
    ],
)


class TestMcpProvider:
    def test_set_definitions_writes_to_relation(self):
        ctx = testing.Context(ProviderCharm, meta=ProviderCharm.META)
        relation = testing.Relation(endpoint="mcp")
        state = testing.State(relations=[relation], leader=True)

        with ctx(ctx.on.relation_joined(relation), state) as mgr:
            mgr.charm.mcp.set_definitions(SAMPLE_DEFINITIONS)
            state_out = mgr.run()

        rel = state_out.get_relation(relation.id)
        raw = rel.local_app_data["mcp_definitions"]
        # relation.save() JSON-encodes the value, so the raw value is a
        # JSON string containing another JSON string.  Decode twice.
        parsed = json.loads(json.loads(raw))
        assert len(parsed["tools"]) == 1
        assert parsed["tools"][0]["name"] == "hello"

    def test_set_definitions_skipped_if_not_leader(self):
        ctx = testing.Context(ProviderCharm, meta=ProviderCharm.META)
        relation = testing.Relation(endpoint="mcp")
        state = testing.State(relations=[relation], leader=False)

        with ctx(ctx.on.relation_joined(relation), state) as mgr:
            mgr.charm.mcp.set_definitions(SAMPLE_DEFINITIONS)
            state_out = mgr.run()

        rel = state_out.get_relation(relation.id)
        assert "mcp_definitions" not in rel.local_app_data

    def test_set_tools_convenience(self):
        ctx = testing.Context(ProviderCharm, meta=ProviderCharm.META)
        relation = testing.Relation(endpoint="mcp")
        state = testing.State(relations=[relation], leader=True)

        tools = [
            Tool(name="t1", description="Tool 1", handler=ExecHandler(command=["ls"])),
            Tool(name="t2", description="Tool 2", handler=ExecHandler(command=["df"])),
        ]
        with ctx(ctx.on.relation_joined(relation), state) as mgr:
            mgr.charm.mcp.set_tools(tools)
            state_out = mgr.run()

        rel = state_out.get_relation(relation.id)
        parsed = json.loads(json.loads(rel.local_app_data["mcp_definitions"]))
        assert len(parsed["tools"]) == 2


class TestMcpRequirer:
    def test_has_definitions_false_when_empty(self):
        ctx = testing.Context(RequirerCharm, meta=RequirerCharm.META)
        relation = testing.SubordinateRelation(endpoint="mcp")
        state = testing.State(relations=[relation])

        with ctx(ctx.on.relation_changed(relation), state) as mgr:
            assert not mgr.charm.mcp.has_definitions()

    def test_has_definitions_true_when_data_present(self):
        ctx = testing.Context(RequirerCharm, meta=RequirerCharm.META)
        relation = testing.SubordinateRelation(
            endpoint="mcp",
            remote_app_data={"mcp_definitions": SAMPLE_DEFINITIONS.to_json()},
        )
        state = testing.State(relations=[relation])

        with ctx(ctx.on.relation_changed(relation), state) as mgr:
            assert mgr.charm.mcp.has_definitions()

    def test_collect_definitions_merges(self):
        ctx = testing.Context(RequirerCharm, meta=RequirerCharm.META)
        relation = testing.SubordinateRelation(
            endpoint="mcp",
            remote_app_data={"mcp_definitions": SAMPLE_DEFINITIONS.to_json()},
        )
        state = testing.State(relations=[relation])

        with ctx(ctx.on.relation_changed(relation), state) as mgr:
            result = mgr.charm.mcp.collect_definitions()

        assert len(result["tools"]) == 1
        assert result["tools"][0]["name"] == "hello"
        assert result["prompts"] == []
        assert result["resources"] == []

    def test_collect_definitions_empty_when_no_data(self):
        ctx = testing.Context(RequirerCharm, meta=RequirerCharm.META)
        relation = testing.SubordinateRelation(endpoint="mcp")
        state = testing.State(relations=[relation])

        with ctx(ctx.on.relation_changed(relation), state) as mgr:
            result = mgr.charm.mcp.collect_definitions()

        assert result == {"tools": [], "prompts": [], "resources": []}
