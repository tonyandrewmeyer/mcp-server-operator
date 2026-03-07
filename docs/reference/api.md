# Charm Library API Reference

This document describes the public API of the `charmlibs-interfaces-mcp`
package. Install it with:

```bash
pip install charmlibs-interfaces-mcp
```

Import the library as a module:

```python
from charmlibs.interfaces import mcp
```

All classes are then available under the `mcp.` prefix (e.g. `mcp.Tool`,
`mcp.McpProvider`).

---

## Provider and Requirer

### `mcp.McpProvider`

Manages the provider side of the `mcp` relation. The provider is typically a
principal charm that wants to expose tools, prompts, and resources to an MCP
server subordinate.

```python
from charmlibs.interfaces import mcp

class MyCharm(ops.CharmBase):
    def __init__(self, framework):
        super().__init__(framework)
        self.mcp_provider = mcp.McpProvider(self, "mcp")
```

#### Constructor

```python
mcp.McpProvider(charm: ops.CharmBase, relation_name: str = "mcp")
```

| Parameter | Type | Description |
|---|---|---|
| `charm` | `ops.CharmBase` | The charm instance. |
| `relation_name` | `str` | Name of the relation endpoint. Defaults to `"mcp"`. |

#### Methods

**`set_definitions(definitions: mcp.McpDefinitions) -> None`**

Publish a complete set of MCP definitions on all current relations. Writes the
definitions as a JSON string to the app data bag. Must be called by the leader
unit.

**`set_tools(tools: list[mcp.Tool]) -> None`**

Publish only tools, preserving any existing prompts and resources on the
relation.

**`set_prompts(prompts: list[mcp.Prompt]) -> None`**

Publish only prompts, preserving any existing tools and resources on the
relation.

**`set_resources(resources: list[mcp.Resource]) -> None`**

Publish only resources, preserving any existing tools and prompts on the
relation.

---

### `mcp.McpRequirer`

Manages the requirer side of the `mcp` relation. The requirer is typically the
mcp-server subordinate charm that reads tool/prompt/resource definitions from
all related provider charms.

```python
from charmlibs.interfaces import mcp

class McpServerCharm(ops.CharmBase):
    def __init__(self, framework):
        super().__init__(framework)
        self.mcp_requirer = mcp.McpRequirer(self, "mcp")
```

#### Constructor

```python
mcp.McpRequirer(charm: ops.CharmBase, relation_name: str = "mcp")
```

| Parameter | Type | Description |
|---|---|---|
| `charm` | `ops.CharmBase` | The charm instance. |
| `relation_name` | `str` | Name of the relation endpoint. Defaults to `"mcp"`. |

#### Methods

**`has_definitions() -> bool`**

Return `True` if any related provider has published definitions on the
relation.

**`collect_definitions() -> dict[str, Any]`**

Collect and merge MCP definitions from all related providers. Returns a dict
with keys `tools`, `prompts`, and `resources`, each containing a list of
definition dicts merged from every provider relation.

---

## Data Models

All data models are plain `dataclasses.dataclass` instances (no Pydantic).

### `mcp.McpDefinitions`

The complete set of MCP definitions for a relation.

```python
mcp.McpDefinitions(
    tools: list[mcp.Tool] = [],
    prompts: list[mcp.Prompt] = [],
    resources: list[mcp.Resource] = [],
)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `tools` | `list[mcp.Tool]` | `[]` | Tool declarations. |
| `prompts` | `list[mcp.Prompt]` | `[]` | Prompt declarations. |
| `resources` | `list[mcp.Resource]` | `[]` | Resource declarations. |

#### Methods

| Method | Return type | Description |
|---|---|---|
| `to_dict()` | `dict[str, Any]` | Serialise to a dict suitable for JSON encoding. |
| `to_json()` | `str` | Serialise to a JSON string. |
| `is_empty()` | `bool` | Return `True` if there are no definitions. |
| `from_dict(data)` | `McpDefinitions` | Class method. Create an instance from a dict (e.g. parsed from JSON). |
| `from_json(raw)` | `McpDefinitions` | Class method. Create an instance from a JSON string. |

---

### `mcp.Tool`

An MCP tool declaration.

```python
mcp.Tool(
    name: str,
    description: str,
    handler: mcp.ExecHandler | mcp.HttpHandler,
    input_schema: dict[str, Any] = {"type": "object", "properties": {}, "required": []},
)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | *required* | Unique tool name (lowercase, hyphens allowed). |
| `description` | `str` | *required* | Human-readable description of what the tool does. |
| `handler` | `ExecHandler \| HttpHandler` | *required* | How to execute this tool. |
| `input_schema` | `dict[str, Any]` | Empty object schema | JSON Schema for the tool's input parameters. |

#### Methods

| Method | Return type | Description |
|---|---|---|
| `to_dict()` | `dict[str, Any]` | Serialise to a dict suitable for JSON encoding. |

---

### `mcp.Prompt`

An MCP prompt declaration.

```python
mcp.Prompt(
    name: str,
    description: str,
    template: str,
    arguments: list[mcp.PromptArgument] = [],
)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | *required* | Unique prompt name. |
| `description` | `str` | *required* | Human-readable description. |
| `template` | `str` | *required* | Prompt text with `{{arg}}` placeholders. |
| `arguments` | `list[PromptArgument]` | `[]` | Prompt arguments. |

#### Methods

| Method | Return type | Description |
|---|---|---|
| `to_dict()` | `dict[str, Any]` | Serialise to a dict suitable for JSON encoding. |

---

### `mcp.PromptArgument`

An argument to an MCP prompt.

```python
mcp.PromptArgument(
    name: str,
    description: str,
    required: bool = True,
)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | *required* | Argument name (must match a `{{name}}` placeholder in the template). |
| `description` | `str` | *required* | Human-readable description. |
| `required` | `bool` | `True` | Whether the argument is required. |

#### Methods

| Method | Return type | Description |
|---|---|---|
| `to_dict()` | `dict[str, Any]` | Serialise to a dict suitable for JSON encoding. |

---

### `mcp.Resource`

An MCP resource declaration.

```python
mcp.Resource(
    uri: str,
    name: str,
    description: str,
    handler: mcp.ExecHandler | mcp.HttpHandler,
    mime_type: str = "text/plain",
)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `uri` | `str` | *required* | Resource URI (unique identifier, e.g. `config://myapp`). |
| `name` | `str` | *required* | Human-readable name. |
| `description` | `str` | *required* | What this resource provides. |
| `handler` | `ExecHandler \| HttpHandler` | *required* | How to fetch the resource content. |
| `mime_type` | `str` | `"text/plain"` | MIME type of the content. |

#### Methods

| Method | Return type | Description |
|---|---|---|
| `to_dict()` | `dict[str, Any]` | Serialise to a dict suitable for JSON encoding. |

---

## Handler Types

### `mcp.ExecHandler`

Handler that runs a command on the machine. The `command` list supports
`{{param}}` template substitution. Each substituted value becomes a discrete
argv element (no shell interpolation).

```python
mcp.ExecHandler(
    command: list[str],
    timeout: int = 60,
    user: str | None = None,
    working_dir: str | None = None,
    env: dict[str, str] | None = None,
)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `command` | `list[str]` | *required* | Command as an argv list. Supports `{{param}}` substitution. |
| `timeout` | `int` | `60` | Maximum execution time in seconds. |
| `user` | `str \| None` | `None` | OS user to run the command as. |
| `working_dir` | `str \| None` | `None` | Working directory for the command. |
| `env` | `dict[str, str] \| None` | `None` | Extra environment variables. |

The `type` field is set automatically to `"exec"` and is not a constructor
parameter.

#### Methods

| Method | Return type | Description |
|---|---|---|
| `to_dict()` | `dict[str, Any]` | Serialise to a dict suitable for JSON encoding. |

---

### `mcp.HttpHandler`

Handler that calls a local HTTP endpoint. The `url` and `body_template`
support `{{param}}` template substitution.

```python
mcp.HttpHandler(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body_template: str | None = None,
    timeout: int = 30,
)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `url` | `str` | *required* | URL to call (typically localhost). |
| `method` | `str` | `"GET"` | HTTP method. |
| `headers` | `dict[str, str] \| None` | `None` | Extra HTTP headers. |
| `body_template` | `str \| None` | `None` | Request body with `{{param}}` substitution. |
| `timeout` | `int` | `30` | Request timeout in seconds. |

The `type` field is set automatically to `"http"` and is not a constructor
parameter.

#### Methods

| Method | Return type | Description |
|---|---|---|
| `to_dict()` | `dict[str, Any]` | Serialise to a dict suitable for JSON encoding. |
