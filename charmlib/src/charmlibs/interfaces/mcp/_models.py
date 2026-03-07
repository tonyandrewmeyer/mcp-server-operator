# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

"""Data models for MCP relation data.

All models are plain dataclasses.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any


@dataclasses.dataclass
class ExecHandler:
    """Handler that runs a command on the machine.

    The ``command`` list supports ``{{param}}`` template substitution.
    Each substituted value becomes a discrete argv element (no shell
    interpolation).
    """

    command: list[str]
    timeout: int = 60
    user: str | None = None
    working_dir: str | None = None
    env: dict[str, str] | None = None
    type: str = dataclasses.field(default="exec", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a dict suitable for JSON encoding."""
        d: dict[str, Any] = {"type": self.type, "command": self.command}
        if self.timeout != 60:
            d["timeout"] = self.timeout
        if self.user is not None:
            d["user"] = self.user
        if self.working_dir is not None:
            d["working_dir"] = self.working_dir
        if self.env is not None:
            d["env"] = self.env
        return d


@dataclasses.dataclass
class HttpHandler:
    """Handler that calls a local HTTP endpoint.

    The ``url`` and ``body_template`` support ``{{param}}`` template
    substitution.
    """

    url: str
    method: str = "GET"
    headers: dict[str, str] | None = None
    body_template: str | None = None
    timeout: int = 30
    type: str = dataclasses.field(default="http", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a dict suitable for JSON encoding."""
        d: dict[str, Any] = {"type": self.type, "url": self.url}
        if self.method != "GET":
            d["method"] = self.method
        if self.headers is not None:
            d["headers"] = self.headers
        if self.body_template is not None:
            d["body_template"] = self.body_template
        if self.timeout != 30:
            d["timeout"] = self.timeout
        return d


@dataclasses.dataclass
class Tool:
    """An MCP tool declaration."""

    name: str
    description: str
    handler: ExecHandler | HttpHandler
    input_schema: dict[str, Any] = dataclasses.field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "required": [],
        }
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a dict suitable for JSON encoding."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "handler": self.handler.to_dict(),
        }


@dataclasses.dataclass
class PromptArgument:
    """An argument to an MCP prompt."""

    name: str
    description: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a dict suitable for JSON encoding."""
        return {
            "name": self.name,
            "description": self.description,
            "required": self.required,
        }


@dataclasses.dataclass
class Prompt:
    """An MCP prompt declaration."""

    name: str
    description: str
    template: str
    arguments: list[PromptArgument] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a dict suitable for JSON encoding."""
        return {
            "name": self.name,
            "description": self.description,
            "template": self.template,
            "arguments": [a.to_dict() for a in self.arguments],
        }


@dataclasses.dataclass
class Resource:
    """An MCP resource declaration."""

    uri: str
    name: str
    description: str
    handler: ExecHandler | HttpHandler
    mime_type: str = "text/plain"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a dict suitable for JSON encoding."""
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mime_type": self.mime_type,
            "handler": self.handler.to_dict(),
        }


@dataclasses.dataclass
class McpDefinitions:
    """The complete set of MCP definitions for a relation."""

    tools: list[Tool] = dataclasses.field(default_factory=list)
    prompts: list[Prompt] = dataclasses.field(default_factory=list)
    resources: list[Resource] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a dict suitable for JSON encoding."""
        return {
            "tools": [t.to_dict() for t in self.tools],
            "prompts": [p.to_dict() for p in self.prompts],
            "resources": [r.to_dict() for r in self.resources],
        }

    def to_json(self) -> str:
        """Serialise to a JSON string."""
        return json.dumps(self.to_dict())

    def is_empty(self) -> bool:
        """Return True if there are no definitions."""
        return not self.tools and not self.prompts and not self.resources

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> McpDefinitions:
        """Create an instance from a dict (e.g. parsed from JSON).

        This is a shallow reconstruction — handler dicts are not converted
        back to ExecHandler/HttpHandler instances.  Use this when you need
        to inspect definitions that were read from a relation but do not
        need the typed handler objects.
        """
        tools = [
            Tool(
                name=t["name"],
                description=t["description"],
                input_schema=t.get("input_schema", {}),
                handler=_handler_from_dict(t["handler"]),
            )
            for t in data.get("tools", [])
        ]
        prompts = [
            Prompt(
                name=p["name"],
                description=p["description"],
                template=p["template"],
                arguments=[
                    PromptArgument(
                        name=a["name"],
                        description=a["description"],
                        required=a.get("required", True),
                    )
                    for a in p.get("arguments", [])
                ],
            )
            for p in data.get("prompts", [])
        ]
        resources = [
            Resource(
                uri=r["uri"],
                name=r["name"],
                description=r["description"],
                handler=_handler_from_dict(r["handler"]),
                mime_type=r.get("mime_type", "text/plain"),
            )
            for r in data.get("resources", [])
        ]
        return cls(tools=tools, prompts=prompts, resources=resources)

    @classmethod
    def from_json(cls, raw: str) -> McpDefinitions:
        """Create an instance from a JSON string."""
        return cls.from_dict(json.loads(raw))


def _handler_from_dict(data: dict[str, Any]) -> ExecHandler | HttpHandler:
    """Reconstruct a handler dataclass from a dict."""
    handler_type = data.get("type", "exec")
    if handler_type == "http":
        return HttpHandler(
            url=data["url"],
            method=data.get("method", "GET"),
            headers=data.get("headers"),
            body_template=data.get("body_template"),
            timeout=data.get("timeout", 30),
        )
    return ExecHandler(
        command=data["command"],
        timeout=data.get("timeout", 60),
        user=data.get("user"),
        working_dir=data.get("working_dir"),
        env=data.get("env"),
    )
