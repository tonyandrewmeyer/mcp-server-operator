# charmlibs-interfaces-mcp

Charm library for the MCP (Model Context Protocol) Juju interface.

Provides `McpProvider` and `McpRequirer` classes that charm authors can use
to integrate with the `mcp` relation interface.

## Installation

```bash
pip install charmlibs-interfaces-mcp
```

## Usage

### Provider (principal charm)

```python
import ops
from charmlibs.interfaces import mcp

class MyCharm(ops.CharmBase):
    def __init__(self, framework):
        super().__init__(framework)
        self.mcp = mcp.McpProvider(self, "mcp")
        framework.observe(self.on["mcp"].relation_joined, self._on_mcp_joined)

    def _on_mcp_joined(self, event: ops.RelationJoinedEvent):
        self.mcp.set_definitions(mcp.McpDefinitions(
            tools=[
                mcp.Tool(
                    name="list-files",
                    description="List files in a directory",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "dir": {"type": "string", "description": "Directory path"},
                        },
                        "required": ["dir"],
                    },
                    handler=mcp.ExecHandler(command=["ls", "-la", "{{dir}}"]),
                ),
            ],
        ))
```

### Requirer (mcp-server charm)

# CLAUDE: something seems missing here, why is there no observe call for relation-changed?

```python
import ops
from charmlibs.interfaces import mcp

class McpServerCharm(ops.CharmBase):
    def __init__(self, framework):
        super().__init__(framework)
        self.mcp = mcp.McpRequirer(self, "mcp")

    def _on_relation_changed(self, event: ops.RelationChangedEvent):
        definitions = self.mcp.collect_definitions()
        # definitions = {"tools": [...], "prompts": [...], "resources": [...]}
```

## Data models

All models are plain dataclasses:

- `Tool` — an MCP tool with name, description, input_schema, and handler
- `Prompt` — a prompt template with arguments
- `Resource` — a readable data source
- `ExecHandler` — runs a command on the machine
- `HttpHandler` — calls a local HTTP endpoint
- `McpDefinitions` — container for tools, prompts, and resources
