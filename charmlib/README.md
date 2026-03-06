# charmlibs-mcp

Charm library for the MCP (Model Context Protocol) Juju interface.

Provides `McpProvider` and `McpRequirer` classes that charm authors can use
to integrate with the `mcp` relation interface.

## Installation

```bash
pip install charmlibs-mcp
```

## Usage

### Provider (principal charm)

```python
import ops
from charmlibs.mcp import McpProvider, McpDefinitions, Tool, ExecHandler

class MyCharm(ops.CharmBase):
    def __init__(self, framework):
        super().__init__(framework)
        self.mcp = McpProvider(self, "mcp")
        framework.observe(self.on.mcp_relation_joined, self._on_mcp_joined)

    def _on_mcp_joined(self, event):
        self.mcp.set_definitions(McpDefinitions(
            tools=[
                Tool(
                    name="list-files",
                    description="List files in a directory",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "dir": {"type": "string", "description": "Directory path"},
                        },
                        "required": ["dir"],
                    },
                    handler=ExecHandler(command=["ls", "-la", "{{dir}}"]),
                ),
            ],
        ))
```

### Requirer (mcp-server charm)

```python
import ops
from charmlibs.mcp import McpRequirer

class McpServerCharm(ops.CharmBase):
    def __init__(self, framework):
        super().__init__(framework)
        self.mcp = McpRequirer(self, "mcp")

    def _on_relation_changed(self, event):
        definitions = self.mcp.collect_definitions()
        # definitions = {"tools": [...], "prompts": [...], "resources": [...]}
```

## Data models

All models are plain dataclasses (no pydantic):

- `Tool` — an MCP tool with name, description, input_schema, and handler
- `Prompt` — a prompt template with arguments
- `Resource` — a readable data source
- `ExecHandler` — runs a command on the machine
- `HttpHandler` — calls a local HTTP endpoint
- `McpDefinitions` — container for tools, prompts, and resources
