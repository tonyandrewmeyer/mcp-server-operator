# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Initial project documentation: README, ROADMAP, PLAN, CONTRIBUTING
- Integration schema reference (`docs/integration-schema.md`)
- Apache 2.0 license
- Charm skeleton via `charmcraft init --profile machine` in `charm/`
- Workload project skeleton in `workload/`
- `pyproject.toml` for both charm and workload (ruff, ty, pytest)
- `tox.ini` for charm test environments
- Pre-commit config (ruff, codespell, trailing whitespace, etc.)
- Top-level `Makefile` for format/lint/typecheck/test
- `.gitignore`
- This changelog
