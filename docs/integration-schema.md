# MCP Integration Schema Reference

This document defines the data schema that a principal charm must provide on the `mcp` relation's app data bag.

## Top-level structure

The principal charm sets a JSON string on the relation app data bag under the key `"mcp_definitions"`. The JSON has this structure:

```json
{
  "tools": [...],
  "prompts": [...],
  "resources": [...]
}
```

All three fields are optional. If omitted, they default to empty lists.

## Tools

Each tool declares a function that MCP clients can invoke.

```json
{
  "name": "tool-name",
  "description": "Human-readable description of what this tool does",
  "input_schema": {
    "type": "object",
    "properties": {
      "param1": {"type": "string", "description": "A parameter"},
      "param2": {"type": "integer", "description": "Another parameter"}
    },
    "required": ["param1"]
  },
  "handler": { ... }
}
```

| Field          | Type   | Required | Description |
|----------------|--------|----------|-------------|
| `name`         | string | yes      | Unique tool name (lowercase, hyphens OK) |
| `description`  | string | yes      | What the tool does |
| `input_schema` | object | yes      | JSON Schema for the tool's input parameters |
| `handler`      | object | yes      | How to execute this tool (see Handler types) |

## Prompts

Each prompt declares a reusable prompt template.

```json
{
  "name": "prompt-name",
  "description": "Human-readable description",
  "arguments": [
    {
      "name": "arg1",
      "description": "Argument description",
      "required": true
    }
  ],
  "template": "Analyze the {{arg1}} and provide recommendations."
}
```

| Field         | Type   | Required | Description |
|---------------|--------|----------|-------------|
| `name`        | string | yes      | Unique prompt name |
| `description` | string | yes      | What the prompt is for |
| `arguments`   | list   | no       | List of prompt arguments |
| `template`    | string | yes      | Prompt text with `{{arg}}` placeholders |

## Resources

Each resource declares a readable data source.

```json
{
  "uri": "config://myapp",
  "name": "My App Configuration",
  "description": "Current application configuration",
  "mime_type": "text/plain",
  "handler": { ... }
}
```

| Field         | Type   | Required | Description |
|---------------|--------|----------|-------------|
| `uri`         | string | yes      | Resource URI (unique identifier) |
| `name`        | string | yes      | Human-readable name |
| `description` | string | yes      | What this resource provides |
| `mime_type`   | string | no       | MIME type of content (default: `text/plain`) |
| `handler`     | object | yes      | How to fetch the resource content |

## Handler types

### `exec` — Run a shell command

```json
{
  "type": "exec",
  "command": ["sudo", "-u", "postgres", "psql", "-d", "{{database}}", "-c", "{{query}}"],
  "timeout": 30,
  "user": "root",
  "working_dir": "/tmp",
  "env": {"PGPASSWORD": "secret"}
}
```

| Field         | Type   | Required | Default | Description |
|---------------|--------|----------|---------|-------------|
| `type`        | string | yes      |         | Must be `"exec"` |
| `command`     | list   | yes      |         | Command as argv list. Supports `{{param}}` substitution. |
| `timeout`     | int    | no       | 60      | Max execution time in seconds |
| `user`        | string | no       | root    | Run command as this OS user |
| `working_dir` | string | no       |         | Working directory for the command |
| `env`         | object | no       |         | Extra environment variables |

**Template substitution:** `{{param_name}}` in the command array elements is replaced with the corresponding value from the MCP tool call arguments. Each substituted value becomes a discrete argv element — there is no shell interpolation. Values are validated against `input_schema` before substitution.

### `http` — Call a local HTTP endpoint

```json
{
  "type": "http",
  "url": "http://localhost:8080/api/query",
  "method": "POST",
  "headers": {"Content-Type": "application/json"},
  "body_template": "{\"query\": \"{{query}}\", \"database\": \"{{database}}\"}",
  "timeout": 30
}
```

| Field           | Type   | Required | Default | Description |
|-----------------|--------|----------|---------|-------------|
| `type`          | string | yes      |         | Must be `"http"` |
| `url`           | string | yes      |         | URL to call (typically localhost) |
| `method`        | string | no       | GET     | HTTP method |
| `headers`       | object | no       |         | Extra HTTP headers |
| `body_template` | string | no       |         | Request body with `{{param}}` substitution |
| `timeout`       | int    | no       | 30      | Request timeout in seconds |

## Complete example

Here is a full example of what a PostgreSQL charm might set on the relation:

```json
{
  "tools": [
    {
      "name": "list-databases",
      "description": "List all PostgreSQL databases",
      "input_schema": {"type": "object", "properties": {}, "required": []},
      "handler": {
        "type": "exec",
        "command": ["sudo", "-u", "postgres", "psql", "-l", "--csv"],
        "timeout": 10
      }
    },
    {
      "name": "run-query",
      "description": "Run a read-only SQL query against a database",
      "input_schema": {
        "type": "object",
        "properties": {
          "query": {"type": "string", "description": "SQL SELECT query to run"},
          "database": {"type": "string", "description": "Target database name"}
        },
        "required": ["query", "database"]
      },
      "handler": {
        "type": "exec",
        "command": ["sudo", "-u", "postgres", "psql", "-d", "{{database}}", "-c", "{{query}}", "--csv"],
        "timeout": 30
      }
    }
  ],
  "prompts": [
    {
      "name": "analyze-database",
      "description": "Analyze database health and performance",
      "arguments": [
        {"name": "database", "description": "Database to analyze", "required": true}
      ],
      "template": "Please analyze the health and performance of the '{{database}}' PostgreSQL database. List all tables with their sizes, check for bloat, and identify any potential issues."
    }
  ],
  "resources": [
    {
      "uri": "config://postgresql/main",
      "name": "PostgreSQL Configuration",
      "description": "Current postgresql.conf contents",
      "mime_type": "text/plain",
      "handler": {
        "type": "exec",
        "command": ["cat", "/etc/postgresql/14/main/postgresql.conf"]
      }
    }
  ]
}
```
