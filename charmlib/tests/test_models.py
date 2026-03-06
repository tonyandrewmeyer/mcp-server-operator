# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

import json

from charmlibs.mcp import (
    ExecHandler,
    HttpHandler,
    McpDefinitions,
    Prompt,
    PromptArgument,
    Resource,
    Tool,
)


class TestExecHandler:
    def test_to_dict_minimal(self):
        handler = ExecHandler(command=["echo", "hello"])
        d = handler.to_dict()
        assert d == {"type": "exec", "command": ["echo", "hello"]}

    def test_to_dict_full(self):
        handler = ExecHandler(
            command=["psql", "-c", "{{query}}"],
            timeout=30,
            user="postgres",
            working_dir="/tmp",
            env={"PGPASSWORD": "secret"},
        )
        d = handler.to_dict()
        assert d["type"] == "exec"
        assert d["timeout"] == 30
        assert d["user"] == "postgres"
        assert d["working_dir"] == "/tmp"
        assert d["env"] == {"PGPASSWORD": "secret"}

    def test_type_is_always_exec(self):
        handler = ExecHandler(command=["ls"])
        assert handler.type == "exec"


class TestHttpHandler:
    def test_to_dict_minimal(self):
        handler = HttpHandler(url="http://localhost:8080/api")
        d = handler.to_dict()
        assert d == {"type": "http", "url": "http://localhost:8080/api"}

    def test_to_dict_full(self):
        handler = HttpHandler(
            url="http://localhost:8080/api",
            method="POST",
            headers={"Content-Type": "application/json"},
            body_template='{"q": "{{query}}"}',
            timeout=10,
        )
        d = handler.to_dict()
        assert d["method"] == "POST"
        assert d["headers"] == {"Content-Type": "application/json"}
        assert d["body_template"] == '{"q": "{{query}}"}'
        assert d["timeout"] == 10


class TestTool:
    def test_to_dict(self):
        tool = Tool(
            name="list-files",
            description="List files",
            handler=ExecHandler(command=["ls", "{{dir}}"]),
            input_schema={
                "type": "object",
                "properties": {"dir": {"type": "string"}},
                "required": ["dir"],
            },
        )
        d = tool.to_dict()
        assert d["name"] == "list-files"
        assert d["handler"]["type"] == "exec"
        assert d["input_schema"]["required"] == ["dir"]

    def test_default_input_schema(self):
        tool = Tool(
            name="info",
            description="Get info",
            handler=ExecHandler(command=["uname", "-a"]),
        )
        assert tool.input_schema == {"type": "object", "properties": {}, "required": []}


class TestPrompt:
    def test_to_dict(self):
        prompt = Prompt(
            name="diagnose",
            description="Diagnose system",
            template="Diagnose {{area}} issues.",
            arguments=[
                PromptArgument(name="area", description="Area to check"),
            ],
        )
        d = prompt.to_dict()
        assert d["name"] == "diagnose"
        assert len(d["arguments"]) == 1
        assert d["arguments"][0]["required"] is True

    def test_no_arguments(self):
        prompt = Prompt(
            name="general",
            description="General prompt",
            template="Do a general check.",
        )
        assert prompt.to_dict()["arguments"] == []


class TestResource:
    def test_to_dict(self):
        resource = Resource(
            uri="config://app",
            name="App Config",
            description="Application configuration",
            handler=ExecHandler(command=["cat", "/etc/app/config"]),
            mime_type="application/json",
        )
        d = resource.to_dict()
        assert d["uri"] == "config://app"
        assert d["mime_type"] == "application/json"

    def test_default_mime_type(self):
        resource = Resource(
            uri="config://app",
            name="App Config",
            description="Config",
            handler=ExecHandler(command=["cat", "/etc/app/config"]),
        )
        assert resource.mime_type == "text/plain"


class TestMcpDefinitions:
    def test_to_json_roundtrip(self):
        defs = McpDefinitions(
            tools=[
                Tool(
                    name="test",
                    description="A test tool",
                    handler=ExecHandler(command=["echo", "hi"]),
                ),
            ],
            prompts=[
                Prompt(name="p", description="A prompt", template="Do {{thing}}."),
            ],
            resources=[
                Resource(
                    uri="config://x",
                    name="X",
                    description="X config",
                    handler=HttpHandler(url="http://localhost/x"),
                ),
            ],
        )
        raw = defs.to_json()
        parsed = json.loads(raw)
        assert len(parsed["tools"]) == 1
        assert len(parsed["prompts"]) == 1
        assert len(parsed["resources"]) == 1

    def test_from_json(self):
        raw = json.dumps(
            {
                "tools": [
                    {
                        "name": "t",
                        "description": "tool",
                        "input_schema": {"type": "object", "properties": {}, "required": []},
                        "handler": {"type": "exec", "command": ["echo"]},
                    }
                ],
                "prompts": [],
                "resources": [],
            }
        )
        defs = McpDefinitions.from_json(raw)
        assert len(defs.tools) == 1
        assert defs.tools[0].name == "t"
        assert isinstance(defs.tools[0].handler, ExecHandler)

    def test_from_dict_http_handler(self):
        data = {
            "tools": [
                {
                    "name": "api",
                    "description": "Call API",
                    "handler": {"type": "http", "url": "http://localhost/api"},
                }
            ],
        }
        defs = McpDefinitions.from_dict(data)
        assert isinstance(defs.tools[0].handler, HttpHandler)

    def test_is_empty(self):
        assert McpDefinitions().is_empty()
        assert not McpDefinitions(
            tools=[Tool(name="t", description="d", handler=ExecHandler(command=["ls"]))]
        ).is_empty()

    def test_from_json_full_roundtrip(self):
        """Verify to_json → from_json → to_json produces equivalent output."""
        original = McpDefinitions(
            tools=[
                Tool(
                    name="query",
                    description="Run query",
                    handler=ExecHandler(command=["psql", "-c", "{{q}}"], timeout=30),
                    input_schema={
                        "type": "object",
                        "properties": {"q": {"type": "string"}},
                        "required": ["q"],
                    },
                ),
            ],
            prompts=[
                Prompt(
                    name="analyse",
                    description="Analyse DB",
                    template="Analyse {{db}}.",
                    arguments=[PromptArgument(name="db", description="Database")],
                ),
            ],
            resources=[
                Resource(
                    uri="config://pg",
                    name="PG Config",
                    description="PostgreSQL config",
                    handler=ExecHandler(command=["cat", "/etc/pg.conf"]),
                ),
            ],
        )
        roundtripped = McpDefinitions.from_json(original.to_json())
        assert json.loads(roundtripped.to_json()) == json.loads(original.to_json())
