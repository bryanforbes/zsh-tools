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

## Git Conventions

- **Commit messages**: Use [conventional commits](https://www.conventionalcommits.org/) with 50/72 rule
  - Format: `<type>(<scope>): <description>`
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`
  - Scope: Optional, e.g., `(parser)`, `(extraction)`, `(grammar)`
  - **Subject line**: Max 50 characters, lowercase, no period, imperative mood
  - **Body**: Wrap at 72 characters, add after blank line if explanation needed
  - **Do not add**: Thread IDs or co-author lines to commits
  - Example subject: `fix(extraction): handle mod_import_function`
  - Example body: `Updated regex pattern to accept optional intermediate keywords\nlike 'mod_import_function' in parser function declarations.`
