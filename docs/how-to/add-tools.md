# How to add MCP tools to your charm

This guide shows how to declare MCP tools in a principal charm so that the
MCP server subordinate can serve them to clients.

## Prerequisites

- A principal charm using the `ops` framework.
- The `charmlibs-interfaces-mcp` package installed as a dependency.
- An `mcp` relation defined in your `charmcraft.yaml`:

```yaml
provides:
  mcp:
    interface: mcp
```

## Import the library

Throughout this guide, use the following import style:

```python
from charmlibs.interfaces import mcp
```

All data classes are then available as `mcp.Tool`, `mcp.ExecHandler`, and so on.

## Add a tool with an exec handler

An exec handler runs a command on the machine. Each element of the `command`
list becomes a discrete `argv` entry -- there is no shell interpolation.

```python
mcp.Tool(
    name="list-databases",
    description="List all PostgreSQL databases",
    handler=mcp.ExecHandler(
        command=["sudo", "-u", "postgres", "psql", "-l", "--csv"],
        timeout=10,
    ),
)
```

### Template substitution

Use `{{param}}` placeholders in the command list. At invocation time, each
placeholder is replaced with the corresponding argument value from the MCP
client. Values are validated against the tool's `input_schema` before
substitution.

```python
mcp.Tool(
    name="run-query",
    description="Run a read-only SQL query against a database",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "SQL SELECT query to run"},
            "database": {"type": "string", "description": "Target database name"},
        },
        "required": ["query", "database"],
    },
    handler=mcp.ExecHandler(
        command=[
            "sudo", "-u", "postgres", "psql",
            "-d", "{{database}}",
            "-c", "{{query}}",
            "--csv",
        ],
        timeout=30,
    ),
)
```

### Optional exec handler fields

| Field         | Default | Description                              |
|---------------|---------|------------------------------------------|
| `timeout`     | 60      | Maximum execution time in seconds.       |
| `user`        | `None`  | Run the command as this OS user.         |
| `working_dir` | `None`  | Working directory for the command.       |
| `env`         | `None`  | Extra environment variables (dict).      |

```python
mcp.ExecHandler(
    command=["my-tool", "--format", "json"],
    timeout=15,
    user="appuser",
    working_dir="/opt/myapp",
    env={"MY_VAR": "value"},
)
```

## Add a tool with an HTTP handler

An HTTP handler calls a local HTTP endpoint on the principal's workload.
This is useful when the principal already exposes a REST API.

```python
mcp.Tool(
    name="search-logs",
    description="Search application logs",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Max results"},
        },
        "required": ["query"],
    },
    handler=mcp.HttpHandler(
        url="http://localhost:8080/api/logs/search",
        method="POST",
        headers={"Content-Type": "application/json"},
        body_template='{"query": "{{query}}", "limit": {{limit}}}',
        timeout=15,
    ),
)
```

Template substitution works in both the `url` and `body_template` fields.

### Optional HTTP handler fields

| Field           | Default | Description                              |
|-----------------|---------|------------------------------------------|
| `method`        | `GET`   | HTTP method.                             |
| `headers`       | `None`  | Extra HTTP headers (dict).               |
| `body_template` | `None`  | Request body with `{{param}}` placeholders. |
| `timeout`       | 30      | Request timeout in seconds.              |

## Set the input schema

Every tool has an `input_schema` field that describes its parameters using
JSON Schema. If your tool takes no arguments, you can omit `input_schema`
entirely -- it defaults to an empty object schema:

```python
# No parameters needed -- input_schema can be omitted.
mcp.Tool(
    name="system-info",
    description="Get basic system information",
    handler=mcp.ExecHandler(command=["uname", "-a"]),
)
```

For tools that accept arguments, provide a JSON Schema object. List required
parameters in the `required` array:

```python
mcp.Tool(
    name="disk-usage",
    description="Show disk usage for a given path",
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Filesystem path to check",
            },
        },
        "required": ["path"],
    },
    handler=mcp.ExecHandler(command=["df", "-h", "{{path}}"]),
)
```

## Publish tools: set_tools() vs set_definitions()

The `McpProvider` class offers two approaches for publishing tools on the
relation.

### set_tools()

Use `set_tools()` when you only want to update the list of tools and leave
any existing prompts and resources unchanged:

```python
class MyCharm(ops.CharmBase):
    def __init__(self, framework):
        super().__init__(framework)
        self.mcp = mcp.McpProvider(self, "mcp")
        framework.observe(self.on.mcp_relation_joined, self._on_mcp_joined)

    def _on_mcp_joined(self, event):
        self.mcp.set_tools([
            mcp.Tool(
                name="list-databases",
                description="List all PostgreSQL databases",
                handler=mcp.ExecHandler(command=["sudo", "-u", "postgres", "psql", "-l", "--csv"]),
            ),
        ])
```

There are corresponding `set_prompts()` and `set_resources()` methods that
work the same way for their respective definition types.

### set_definitions()

Use `set_definitions()` when you want to publish tools, prompts, and resources
together in a single call. This replaces all definitions at once:

```python
self.mcp.set_definitions(mcp.McpDefinitions(
    tools=[
        mcp.Tool(
            name="list-databases",
            description="List all PostgreSQL databases",
            handler=mcp.ExecHandler(command=["sudo", "-u", "postgres", "psql", "-l", "--csv"]),
        ),
    ],
    prompts=[
        mcp.Prompt(
            name="analyse-database",
            description="Analyse database health",
            template="Please analyse the '{{database}}' database.",
            arguments=[
                mcp.PromptArgument(name="database", description="Database to analyse"),
            ],
        ),
    ],
    resources=[
        mcp.Resource(
            uri="config://postgresql/main",
            name="PostgreSQL Configuration",
            description="Current postgresql.conf contents",
            handler=mcp.ExecHandler(command=["cat", "/etc/postgresql/14/main/postgresql.conf"]),
        ),
    ],
))
```

### Which to use

| Method             | Replaces         | Preserves                      |
|--------------------|------------------|--------------------------------|
| `set_tools()`      | Tools only       | Existing prompts and resources |
| `set_prompts()`    | Prompts only     | Existing tools and resources   |
| `set_resources()`  | Resources only   | Existing tools and prompts     |
| `set_definitions()`| Everything       | Nothing -- full replacement    |

> **Note:** All of these methods must be called by the leader unit. Non-leader
> units are silently skipped.
