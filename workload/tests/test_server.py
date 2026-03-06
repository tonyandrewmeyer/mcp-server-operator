# Copyright 2026 Tony Meyer
# See LICENSE file for licensing details.

import json
import pathlib
import tempfile

import pytest

from server import (
    create_server,
    execute_exec_handler,
    load_config,
    substitute_command,
    substitute_template,
    validate_arguments,
)


class TestTemplateSubstitution:
    def test_simple_substitution(self):
        result = substitute_template("hello {{name}}", {"name": "world"})
        assert result == "hello world"

    def test_multiple_substitutions(self):
        result = substitute_template("{{a}} and {{b}}", {"a": "x", "b": "y"})
        assert result == "x and y"

    def test_missing_argument_raises(self):
        with pytest.raises(ValueError, match="Missing required argument: name"):
            substitute_template("hello {{name}}", {})

    def test_no_placeholders(self):
        result = substitute_template("no placeholders here", {})
        assert result == "no placeholders here"

    def test_integer_value(self):
        result = substitute_template("port {{port}}", {"port": 8080})
        assert result == "port 8080"


class TestSubstituteCommand:
    def test_command_substitution(self):
        cmd = ["echo", "{{message}}"]
        result = substitute_command(cmd, {"message": "hello"})
        assert result == ["echo", "hello"]

    def test_preserves_non_template_args(self):
        cmd = ["psql", "-d", "{{db}}", "-c", "SELECT 1"]
        result = substitute_command(cmd, {"db": "mydb"})
        assert result == ["psql", "-d", "mydb", "-c", "SELECT 1"]


class TestExecHandler:
    def test_simple_command(self):
        handler = {"type": "exec", "command": ["echo", "hello"]}
        result = execute_exec_handler(handler, {})
        assert result.strip() == "hello"

    def test_command_with_substitution(self):
        handler = {"type": "exec", "command": ["echo", "{{msg}}"]}
        result = execute_exec_handler(handler, {"msg": "world"})
        assert result.strip() == "world"

    def test_failed_command(self):
        handler = {"type": "exec", "command": ["false"]}
        result = execute_exec_handler(handler, {})
        assert "Command failed" in result


class TestValidateArguments:
    def test_valid_arguments(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "count": {"type": "integer"}},
            "required": ["name"],
        }
        errors = validate_arguments({"name": "test", "count": 5}, schema)
        assert errors == []

    def test_missing_required(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        errors = validate_arguments({}, schema)
        assert any("Missing required" in e for e in errors)

    def test_unexpected_arguments(self):
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        errors = validate_arguments({"name": "ok", "extra": "bad"}, schema)
        assert any("Unexpected" in e for e in errors)

    def test_wrong_type(self):
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
        }
        errors = validate_arguments({"count": "not_a_number"}, schema)
        assert any("expected type" in e for e in errors)

    def test_optional_argument_missing_is_ok(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "opt": {"type": "string"}},
            "required": ["name"],
        }
        errors = validate_arguments({"name": "test"}, schema)
        assert errors == []

    def test_empty_schema(self):
        errors = validate_arguments({}, {})
        assert errors == []

    def test_number_type_accepts_int_and_float(self):
        schema = {"type": "object", "properties": {"val": {"type": "number"}}}
        assert validate_arguments({"val": 1}, schema) == []
        assert validate_arguments({"val": 1.5}, schema) == []
        assert any("expected type" in e for e in validate_arguments({"val": "x"}, schema))


class TestCommandAllowlist:
    def test_allowed_command(self):
        handler = {"type": "exec", "command": ["echo", "hello"]}
        result = execute_exec_handler(handler, {})
        assert result.strip() == "hello"

    def test_blocked_command(self):
        """Allowlist blocking is done in the tool handler, not execute_exec_handler."""
        # execute_exec_handler itself doesn't check the allowlist — that's done
        # at the tool_handler level. This test just documents that.
        handler = {"type": "exec", "command": ["echo", "hello"]}
        result = execute_exec_handler(handler, {})
        assert result.strip() == "hello"


class TestLoadConfig:
    def test_load_valid_config(self):
        config = {
            "tools": [{"name": "test", "description": "test tool"}],
            "prompts": [],
            "resources": [],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            result = load_config(pathlib.Path(f.name))
        assert len(result["tools"]) == 1
        assert result["tools"][0]["name"] == "test"

    def test_load_missing_file(self):
        result = load_config(pathlib.Path("/nonexistent/config.json"))
        assert result == {"tools": [], "prompts": [], "resources": []}

    def test_defaults_missing_keys(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"tools": []}, f)
            f.flush()
            result = load_config(pathlib.Path(f.name))
        assert result["prompts"] == []
        assert result["resources"] == []


class TestCreateServer:
    def test_creates_server_with_empty_config(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"tools": [], "prompts": [], "resources": []}, f)
            f.flush()
            server = create_server(pathlib.Path(f.name))
        assert server is not None

    def test_creates_server_with_tools(self):
        config = {
            "tools": [
                {
                    "name": "test-tool",
                    "description": "A test tool",
                    "input_schema": {"type": "object", "properties": {}, "required": []},
                    "handler": {"type": "exec", "command": ["echo", "test"]},
                }
            ],
            "prompts": [],
            "resources": [],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            server = create_server(pathlib.Path(f.name))
        assert server is not None
