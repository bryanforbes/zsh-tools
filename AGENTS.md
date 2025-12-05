# Agent Guidelines for zsh-tools

## Environment

- **Clang Library**: `LIBCLANG_PREFIX` is set to `/opt/homebrew/opt/llvm` on macOS. Use in Python/Bash scripts that use
  clang.cindex:

  ```python
  import os
  from pathlib import Path
  import clang.cindex
  clang.cindex.Config.set_library_path(Path(os.environ['LIBCLANG_PREFIX']) / 'lib')
  ```

## Build/Lint/Test Commands

- **Setup**: `mise run dev` (installs deps for all tools)
- **Format** (**NOTE:** run the language-specific formatter after editing a file and before linting to avoid unnecessary
  lint errors):
  - **Python**: `mise //:ruff-format [--check] [<file1> <file2>]`
  - **JS/TS/Markdown**: `mise //:prettier [--check] [<file1> <file2>]`
  - **C/C++**: `mise //:clang-format [--check] [<file1> <file2>]`
  - **All files**: `mise //:format`
- **Lint**:
  - **Python**:
    - `mise //:ruff [--fix] [<file1> <file2>]`
    - `mise //:basedpyright [<file1> <file2>]`
  - **JS/TS**: `mise //:eslint [--fix] [<file1> <file2>]`
  - **All files**: `mise //:lint`
- **Test**:
  - **All projects**: `mise run //:test`
  - **Individual project**: `mise //<project_name>:test`
  - **Individual files**: `mise //<project_name>:test <file1> <file2>` (file1 and file2 must be relative to the project
    root)
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
  - Use `# pyright: ignore[<rule>]` for specific exceptions only
  - **DO NOT** use `# type: ignore[<rule>]` because basedpyright has been configured not to recognize it
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
  - **Amp analysis commits**: Include thread reference and co-author at end of message:
    - `Amp-Thread-ID: https://ampcode.com/threads/T-<uuid>`
    - `Co-authored-by: Amp <amp@ampcode.com>`
    - If there are multiple amp threads, they should all be ordered by ascending date, one line each, before the
      co-author line
  - Example subject: `fix(extraction): handle mod_import_function`
  - Example body:
    ```text
    Updated regex pattern to accept optional intermediate keywords
    like 'mod_import_function' in parser function declarations.
    ```
