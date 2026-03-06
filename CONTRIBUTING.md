# Contributing

Thanks for your interest in contributing to the MCP Server Charm!

## Development setup

```bash
# Clone the repo
git clone https://github.com/tonyandrewmeyer/mcp-server-operator.git
cd mcp-server-operator

# Install pre-commit hooks
pre-commit install

# Install charm dependencies
cd charm && uv sync --all-groups

# Install workload dependencies
cd workload && uv sync --all-groups
```

## Running checks

```bash
# Format code
make format

# Run linter
make lint

# Run type checker
make typecheck

# Run all checks (format, lint, typecheck)
make check

# Run tests
make test
```

## Code style

- **Formatter/linter:** [ruff](https://docs.astral.sh/ruff/)
- **Type checker:** [ty](https://github.com/astral-sh/ty)
- **Tests:** [pytest](https://docs.pytest.org/)
- Pre-commit hooks enforce formatting and linting on every commit.

## Commit messages

- Use imperative mood ("Add feature" not "Added feature")
- Keep the first line under 72 characters
- Reference issues where relevant

## Pull requests

1. Create a feature branch from `main`
2. Make your changes with tests
3. Ensure all checks pass (`make check && make test`)
4. Open a PR against `main`

## Project structure

```
mcp-charm/
├── charm/                    # Juju charm (ops framework)
│   ├── charmcraft.yaml       # Charm metadata
│   ├── pyproject.toml        # Charm dependencies and tool config
│   ├── tox.ini               # Charm test environments
│   ├── src/
│   │   ├── charm.py          # Charm event handlers
│   │   └── mcp_server.py     # Workload management (install/start/stop)
│   └── tests/
├── workload/                 # MCP server process (runs on the machine)
│   ├── pyproject.toml        # Workload dependencies and tool config
│   └── src/
│       └── server.py         # The actual MCP server
├── docs/                     # Documentation
├── Makefile                  # Top-level dev commands
└── .pre-commit-config.yaml   # Pre-commit hooks
```

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
