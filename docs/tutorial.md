# Tutorial: Add MCP support to your Juju charm

In this tutorial you will take an existing Juju machine charm and give it
the ability to expose tools, prompts, and resources to MCP clients (such as
LLM agents and Claude Code). By the end you will have a working principal
charm that publishes MCP definitions over a relation and an MCP server
subordinate that serves them over HTTP.

## Prerequisites

You will need:

* **Juju 3.6+** with a bootstrapped machine controller.
* **An existing machine charm** built with the ops framework. The charm must
  already pack and deploy successfully. This tutorial uses a charm called
  `my-app` as the running example — substitute your own charm name
  throughout.
* **charmcraft** installed (`sudo snap install charmcraft --classic`).
* **curl** or **httpie** for verifying the MCP endpoint.

The tutorial assumes you are comfortable with ops charm authoring and the
Juju CLI but have no prior experience with the Model Context Protocol.


## 1. Add the `mcp` relation to your charm metadata

Open your charm's `charmcraft.yaml` and add an `mcp` relation under the
`provides` key. The interface name must be `mcp`:

```yaml
provides:
  mcp:
    interface: mcp
```

The MCP server charm is a subordinate that attaches to your principal via
this relation. You do not need to declare `scope: container` on the provider
side — the subordinate's metadata handles that.


## 2. Add the charm library dependency

The `charmlibs-interfaces-mcp` package contains the dataclass models and the
`McpProvider` helper you will use in your charm code.

Add it to the `dependencies` list in your `pyproject.toml`:

```toml
[project]
dependencies = [
    "ops>=3,<4",
    "charmlibs-interfaces-mcp",
]
```

If your charm still uses a `requirements.txt` or `PYDEPS` file instead, add
the line `charmlibs-interfaces-mcp` there.


## 3. Import the library

At the top of your `src/charm.py`, import the `mcp` module. Following the
project import convention, import the module rather than individual classes:

```python
from charmlibs.interfaces import mcp
```

You will then refer to classes as `mcp.McpProvider`, `mcp.Tool`,
`mcp.ExecHandler`, and so on.


## 4. Initialise `McpProvider` in your charm

In your charm's `__init__`, create an `McpProvider` instance and observe the
`mcp_relation_joined` event. The provider needs to publish definitions
whenever a new MCP server subordinate joins the relation:

```python
import logging
import ops
from charmlibs.interfaces import mcp

logger = logging.getLogger(__name__)


class MyAppCharm(ops.CharmBase):

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self.mcp = mcp.McpProvider(self, "mcp")
        framework.observe(self.on.mcp_relation_joined, self._on_mcp_relation_joined)
        # ... your existing observers ...
```

The first argument to `McpProvider` is the charm instance; the second is the
relation name you declared in `charmcraft.yaml`.


## 5. Define a simple exec tool

Create a tool that runs `uname -a` on the machine and returns the output.
Tools with no input parameters use a plain command list:

```python
    def _on_mcp_relation_joined(self, event: ops.RelationJoinedEvent) -> None:
        """Publish MCP definitions when the MCP server subordinate joins."""
        definitions = mcp.McpDefinitions(
            tools=[
                mcp.Tool(
                    name="system-info",
                    description="Get basic system information (hostname, OS, kernel)",
                    handler=mcp.ExecHandler(command=["uname", "-a"], timeout=10),
                ),
            ],
        )
        self.mcp.set_definitions(definitions)
```

Key points:

* `mcp.ExecHandler` runs a command on the machine. The `command` is a list
  of arguments — never a shell string. This avoids shell injection.
* `timeout` is in seconds. The default is 60.
* Because `system-info` takes no input, you can omit `input_schema`
  entirely; it defaults to an empty object schema.
* `set_definitions` publishes the data on the relation app data bag. Only
  the leader unit writes relation data, and `McpProvider` handles that check
  internally.


## 6. Add a tool with input parameters

Now add a `disk-usage` tool that accepts a `path` parameter from the MCP
client. Use `{{path}}` template substitution in the command list:

```python
        definitions = mcp.McpDefinitions(
            tools=[
                mcp.Tool(
                    name="system-info",
                    description="Get basic system information (hostname, OS, kernel)",
                    handler=mcp.ExecHandler(command=["uname", "-a"], timeout=10),
                ),
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
                    handler=mcp.ExecHandler(
                        command=["df", "-h", "{{path}}"], timeout=10
                    ),
                ),
            ],
        )
        self.mcp.set_definitions(definitions)
```

The `input_schema` follows the JSON Schema format that MCP uses to describe
tool parameters. When an MCP client calls `disk-usage` with
`{"path": "/var"}`, the server replaces `{{path}}` in the command with
`/var` and executes `["df", "-h", "/var"]`. Each substituted value becomes a
discrete argv element — there is no shell interpolation.


## 7. Add a prompt

Prompts are reusable instruction templates that MCP clients can retrieve and
fill in. Add a `diagnose-system` prompt with an optional `focus` argument:

```python
        definitions = mcp.McpDefinitions(
            tools=[
                # ... tools from the previous steps ...
            ],
            prompts=[
                mcp.Prompt(
                    name="diagnose-system",
                    description="Diagnose system health and suggest improvements",
                    template=(
                        "Please diagnose the system health"
                        "{% if focus %}, focusing on {{focus}}{% endif %}. "
                        "Use the available tools to gather information, then "
                        "provide a summary of findings and recommendations."
                    ),
                    arguments=[
                        mcp.PromptArgument(
                            name="focus",
                            description="Area to focus on (disk, memory, network, general)",
                            required=False,
                        ),
                    ],
                ),
            ],
        )
```

* `template` is a string that the MCP client receives. It can contain
  `{{param}}` placeholders that match the declared `arguments`.
* `PromptArgument` describes each parameter. Set `required=False` for
  optional arguments.


## 8. Add a resource

Resources are read-only data endpoints that MCP clients can fetch. Add a
resource that exposes the contents of `/etc/os-release`:

```python
        definitions = mcp.McpDefinitions(
            tools=[
                # ... tools from the previous steps ...
            ],
            prompts=[
                # ... prompts from the previous step ...
            ],
            resources=[
                mcp.Resource(
                    uri="config://os-release",
                    name="OS Release Info",
                    description="Contents of /etc/os-release",
                    handler=mcp.ExecHandler(command=["cat", "/etc/os-release"]),
                ),
            ],
        )
```

* `uri` is a stable identifier that MCP clients use to request the
  resource. Use a scheme that makes sense for your domain (e.g.
  `config://`, `file://`, `metrics://`).
* `mime_type` defaults to `text/plain`. Set it explicitly if your resource
  returns JSON or another format.
* The `handler` works the same as for tools — `ExecHandler` or
  `HttpHandler`.


## 9. Putting it all together

Here is the complete charm code with all definitions in one place:

```python
#!/usr/bin/env python3
"""My App charm with MCP support."""

import logging

import ops

from charmlibs.interfaces import mcp

logger = logging.getLogger(__name__)

MCP_DEFINITIONS = mcp.McpDefinitions(
    tools=[
        mcp.Tool(
            name="system-info",
            description="Get basic system information (hostname, OS, kernel)",
            handler=mcp.ExecHandler(command=["uname", "-a"], timeout=10),
        ),
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
            handler=mcp.ExecHandler(command=["df", "-h", "{{path}}"], timeout=10),
        ),
    ],
    prompts=[
        mcp.Prompt(
            name="diagnose-system",
            description="Diagnose system health and suggest improvements",
            template=(
                "Please diagnose the system health"
                "{% if focus %}, focusing on {{focus}}{% endif %}. "
                "Use the available tools to gather information, then "
                "provide a summary of findings and recommendations."
            ),
            arguments=[
                mcp.PromptArgument(
                    name="focus",
                    description="Area to focus on (disk, memory, network, general)",
                    required=False,
                ),
            ],
        ),
    ],
    resources=[
        mcp.Resource(
            uri="config://os-release",
            name="OS Release Info",
            description="Contents of /etc/os-release",
            handler=mcp.ExecHandler(command=["cat", "/etc/os-release"]),
        ),
    ],
)


class MyAppCharm(ops.CharmBase):
    """A charm that exposes system tools via MCP."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        self.mcp = mcp.McpProvider(self, "mcp")
        framework.observe(self.on.start, self._on_start)
        framework.observe(self.on.mcp_relation_joined, self._on_mcp_relation_joined)

    def _on_start(self, event: ops.StartEvent) -> None:
        self.unit.status = ops.ActiveStatus()

    def _on_mcp_relation_joined(self, event: ops.RelationJoinedEvent) -> None:
        """Publish MCP definitions when the MCP server subordinate joins."""
        self.mcp.set_definitions(MCP_DEFINITIONS)


if __name__ == "__main__":  # pragma: nocover
    ops.main(MyAppCharm)
```

Note that the definitions are declared as a module-level constant. This
keeps the handler method short and makes the definitions easy to find when
reading the code.


## 10. Deploy and test

Pack your charm and the MCP server charm, then deploy them together.

### Pack and deploy

```bash
# Pack your principal charm.
cd my-app
charmcraft pack

# Deploy it.
juju deploy ./my-app_ubuntu-24.04-amd64.charm

# Deploy the MCP server subordinate.
juju deploy mcp-server

# Integrate the two charms. This creates the mcp relation and triggers
# the relation-joined event in your charm.
juju integrate my-app:mcp mcp-server:mcp
```

Wait for both units to settle:

```bash
juju status --watch 5s
```

Once both units show `active/idle`, the MCP server is running on the same
machine as your principal.

### Verify the endpoint

The MCP server listens on port 8081 by default. Find the machine IP from
`juju status`, then test with curl:

```bash
# List available tools (MCP uses JSON-RPC over HTTP).
curl -s http://<MACHINE_IP>:8081/mcp \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | python3 -m json.tool
```

You should see a response containing your `system-info` and `disk-usage`
tools.

To call a tool:

```bash
curl -s http://<MACHINE_IP>:8081/mcp \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "system-info",
            "arguments": {}
        }
    }' | python3 -m json.tool
```

To call the parameterised tool:

```bash
curl -s http://<MACHINE_IP>:8081/mcp \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "disk-usage",
            "arguments": {"path": "/"}
        }
    }' | python3 -m json.tool
```


## Next steps

You now have a working MCP integration. Here are some directions to explore:

* **Authentication** — Set a bearer token with `juju config mcp-server
  auth-token=<token>` to require clients to authenticate.
* **Ingress and reverse proxy** — Integrate with `haproxy` via the
  `reverse-proxy` relation to expose the MCP endpoint through a load
  balancer. Use the `path-prefix` config option to namespace the endpoint.
* **TLS** — Integrate with a TLS certificates provider via the
  `certificates` relation to serve MCP over HTTPS.
* **OAuth** — Integrate with an OAuth provider via the `oauth` relation for
  token-based authentication using an identity provider.
* **Rate limiting** — Set `juju config mcp-server rate-limit=60` to cap
  requests per minute.
* **HTTP handlers** — Use `mcp.HttpHandler` instead of `mcp.ExecHandler` to
  proxy tool calls to a local HTTP API on your workload, rather than
  executing shell commands.

See the [integration schema reference](integration-schema.md) for the
complete specification of the relation data format.
