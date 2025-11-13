# Agent Guidelines for zsh-tools

## Build/Lint/Test Commands

- **Setup**: `mise run dev` (installs deps for all tools)
- **Lint JS**: `pnpm run lint` (eslint)
- **Lint Python**: `ruff check` and `basedpyright`
- **Format**: `prettier --write .` and `ruff format`
- **Test**: `mise run test` (runs tests across all packages)
- **Single test**: `cd <package> && pnpm run test` or `cd <package> && python -m pytest <test_file>`

## Architecture

- **Monorepo**: Mixed JS/Python with mise + pnpm + uv
- **Python packages**: zsh-grammar (main package)
- **JS tools**: ESLint, Prettier, TypeScript (minimal config)
- **Submodules**: vendor/zsh (Zsh source code)
- **Tool management**: mise with platform-specific configs

## Code Style

- **Python**: See [docs/python-conventions.md](docs/python-conventions.md) for detailed rules
    - Python 3.14+ (unpublished), 3.10+ (published), strict ruff + basedpyright
    - `from __future__ import annotations` required, built-in generics, collections.abc protocols
    - Zero lint/type errors, ruff formatting, full type hints, no typing.Any
- **JS/TS**: ESLint + Prettier, single quotes, 2-space indent, ES modules
- **Imports**: `from __future__ import annotations` required in Python
- **Error handling**: Standard Python exceptions, no bare excepts
- **Naming**: snake_case for Python, camelCase for JS, PascalCase for classes
- **Types**: Strict typing enabled, no type ignores without rules
