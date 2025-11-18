# Agent Guidelines for zsh-tools

## Environment

- **Clang Library**: `LIBCLANG_PREFIX` is set to `/opt/homebrew/opt/llvm` on macOS. Use in Python/Bash scripts that use clang.cindex:
    ```python
    import os
    from pathlib import Path
    import clang.cindex
    clang.cindex.Config.set_library_path(Path(os.environ['LIBCLANG_PREFIX']) / 'lib')
    ```

## Build/Lint/Test Commands

- **Setup**: `mise run dev` (installs deps for all tools)
- **Format** (**NOTE:** run the language-specific formatter after editing a file and before linting to avoid unnecessary lint errors):
    - **Python**: `mise //:ruff-format [--check] [<file1> <file2>]`
    - **JS/TS/Markdown**: `mise //:prettier [--check] [<file1> <file2>]`
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
    - **Individual files**: `mise //<project_name>:test <file1> <file2>` (file1 and file2 must be relative to the project root)
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
    - **Amp analysis commits**: Include thread reference and co-author at end of message:
        - `Amp-Thread-ID: https://ampcode.com/threads/T-<uuid>`
        - `Co-authored-by: Amp <amp@ampcode.com>`
    - Example subject: `fix(extraction): handle mod_import_function`
    - Example body: `Updated regex pattern to accept optional intermediate keywords\nlike 'mod_import_function' in parser function declarations.`

## Analysis Documentation

- **Phase documentation**: Analysis documents (CONDITIONAL_ANALYSIS.md, PHASE_3_ANALYSIS_INDEX.md, etc.) track research progress and findings
- **Status synchronization**: Always update EXTRACTION_STATUS.md and PARSER_FUNCTION_AUDIT.md when validation results change
- **Pre/post-fix tracking**: Distinguish between predicted outcomes in analysis and actual implementation results
- **Key patterns identified**:
    - Operator precedence hierarchies (recursive descent reliable)
    - Dual-mode functions (test builtin vs [[...]])
    - Error guard filtering (NULLTOK, synthetic tokens)
    - Context-sensitive token filtering (STRING semantic in par_cond_2)

## Phase 2.4.1 Implementation Strategy

### Documentation Organization

**Source of Truth**: `PHASE_2_4_1_REDESIGN_PLAN.md`

- Contains detailed specifications (algorithms, pseudocode, test cases)
- Update this when the plan changes or when implementation reveals architectural issues
- Each stage section (0-6) has complete algorithm descriptions

**Execution Tracker**: `TODOS.md`

- Tracks stage status (NOT STARTED → IN PROGRESS → COMPLETED)
- Deliverable checkboxes for progress visibility
- References plan document sections, does not duplicate content
- Update this to reflect progress and blockers

### Sync Protocol

1. **Plan Changes**: Update `PHASE_2_4_1_REDESIGN_PLAN.md` only
    - TODOS.md references it via cross-links (e.g., "See Stage N in REDESIGN_PLAN.md")
    - No need to update TODOS.md unless complexity metrics change

2. **Implementation Issues**: Post in thread, then update both
    - Document decision in REDESIGN_PLAN.md
    - Update stage status in TODOS.md (add notes if needed)
    - Include thread reference in commit message

3. **Stage Completion**: Update TODOS.md only
    - Check deliverable boxes as they complete
    - Add test coverage % and validation metrics
    - Keep one line summary of results

4. **PR Review Checklist**:
    - Verify implementation matches stage spec in REDESIGN_PLAN.md
    - Confirm all test cases from plan are implemented
    - Check TODOS.md stage is marked complete
    - Document any architectural deviations in PR body

### Stage Handoff

Before assigning a stage to a sub-agent:

1. Ensure previous stages are complete (check TODOS.md)
2. Point agent to their stage section in REDESIGN_PLAN.md
3. Point agent to QUICK_REFERENCE.md for workflow
4. Create feature branch: `feat/phase-2.4.1-stage-N`

During implementation, agent should:

1. Write tests first (pseudocode and test cases provided in plan)
2. Run: `mise //:ruff-format <file>`, `mise //:ruff --fix <file>`, `mise //:basedpyright <file>`
3. Run: `mise //<project_name>:test` to validate test suite
4. Post daily progress in thread with: stage, tasks completed, blockers (if any), test % coverage

### Key Files

| File                             | Purpose                   | When to Update                           |
| -------------------------------- | ------------------------- | ---------------------------------------- |
| `PHASE_2_4_1_REDESIGN_PLAN.md`   | Complete specification    | Plan changes, architectural decisions    |
| `PHASE_2_4_1_QUICK_REFERENCE.md` | Sub-agent workflow guide  | New patterns/tips discovered             |
| `PHASE_2_4_1_INDEX.md`           | Navigation index          | Document references change               |
| `TODOS.md`                       | Progress tracking         | After each deliverable, stage completion |
| `AGENTS.md`                      | This file (sync strategy) | Workflow improvements                    |
