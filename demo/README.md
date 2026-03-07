## Demo: MCP Server Charm

This demo shows the MCP server charm in action with a simple principal charm
that exposes system tools, a prompt, and a resource over the Model Context
Protocol. By the end of this walkthrough you will have a running MCP server
that you can query with `curl` or connect to from an MCP client such as
Claude Code.


### Prerequisites

- **Juju 3.6+** with a bootstrapped machine controller (e.g. LXD).
- **charmcraft** installed (`sudo snap install charmcraft --classic`).
- **curl** or an MCP client (Claude Code, etc.) for interacting with the
  server.


### What the demo deploys

- **demo-principal** — a minimal charm that provides three tools
  (`system-info`, `disk-usage`, `list-files`), one prompt
  (`diagnose-system`), and one resource (`os-release`).
- **mcp-server** — the subordinate charm that runs the MCP server on the
  same machine as the principal, serving all declared definitions over
  streamable HTTP.


### Step 1: Pack the charms

```bash
# From the repo root — pack the MCP server subordinate charm.
make pack

# Pack the demo principal charm.
cd demo/principal
charmcraft pack
cd ../..
```

After packing you should have `charm/mcp-server_amd64.charm` and
`demo/principal/demo-principal_amd64.charm`.


### Step 2: Deploy

```bash
juju add-model mcp-demo

juju deploy ./demo/principal/demo-principal_amd64.charm demo-principal
juju deploy ./charm/mcp-server_amd64.charm mcp-server

# Create the mcp relation — this triggers the principal to publish its
# tool/prompt/resource definitions and the subordinate to start serving them.
juju integrate demo-principal:mcp mcp-server:mcp

# Wait for the MCP server to become active.
juju wait-for application mcp-server --query='status.current=="active"' --timeout=120
```


### Step 3: Verify the MCP server is running

```bash
# Get the unit's IP address.
UNIT_IP=$(juju status --format=json | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(list(d['applications']['mcp-server']['units'].values())[0]['public-address'])
")

# Check health.
curl http://$UNIT_IP:8081/health

# List available tools via MCP protocol (JSON-RPC over streamable HTTP).
curl -X POST http://$UNIT_IP:8081/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

The `tools/list` response should include `system-info`, `disk-usage`, and
`list-files`.


### Step 4: Call a tool

```bash
# Call the system-info tool (no parameters).
curl -X POST http://$UNIT_IP:8081/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"system-info","arguments":{}}}'

# Call disk-usage with a path parameter.
curl -X POST http://$UNIT_IP:8081/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"disk-usage","arguments":{"path":"/"}}}'

# Call list-files with a directory parameter.
curl -X POST http://$UNIT_IP:8081/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"list-files","arguments":{"directory":"/tmp"}}}'
```


### Step 5: Connect Claude Code (optional)

Claude Code can connect to the MCP server as a remote MCP endpoint. Add the
following to your Claude Code MCP server configuration
(`.claude/settings.json` or the project-level `.mcp.json`):

```json
{
  "mcpServers": {
    "juju-demo": {
      "type": "url",
      "url": "http://<UNIT_IP>:8081/mcp"
    }
  }
}
```

Replace `<UNIT_IP>` with the address from Step 3. Once configured, Claude
Code will automatically discover the available tools, prompts, and resources
and can invoke them during a conversation.


### Cleanup

```bash
echo "mcp-demo" | juju destroy-model mcp-demo --force --no-wait --destroy-storage
```


### Next steps

- Read the [tutorial](../docs/tutorial.md) for a step-by-step guide to
  adding MCP support to your own charm.
- See the [integration schema reference](../docs/integration-schema.md) for
  the complete specification of the relation data format.
- Explore the configuration options (authentication, rate limiting, TLS,
  ingress) in the [configuration reference](../docs/reference/config.md).
