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
    - Use `# pyright: ignore[<rule>]` for specific exceptions only
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

## Phase 2.4.1: Token-Sequence-Based Grammar Extraction ✅ COMPLETE

Phase 2.4.1 has been fully implemented across 6 stages with 167 tests passing and 0 lint/type errors. The extraction architecture has been successfully redesigned from function-centric (call graphs) to token-sequence-centric (ordered token+call sequences).

### What Was Completed

**All 6 Stages Delivered:**

- **Stage 0**: Data structures & validators (18 tests)
- **Stage 1**: Branch extraction from AST (80/80 tests, 81% coverage)
- **Stage 2**: Token & call sequence extraction (95/95 tests, 73% coverage)
- **Stage 3**: Enhanced call graph construction (26/26 tests, 82% coverage)
- **Stage 4**: Rule generation from token sequences (27/27 tests, 100% quality)
- **Stage 5**: Semantic grammar validation & comparison (19/19 tests)
- **Stage 6**: Documentation & integration (COMPLETE)

### Key Implementation Files

**New Files Created:**

- `zsh_grammar/src/zsh_grammar/branch_extractor.py` — Control flow branch extraction
- `zsh_grammar/src/zsh_grammar/token_extractors.py` — Enhanced token sequence extraction
- `zsh_grammar/src/zsh_grammar/enhanced_call_graph.py` — Token-aware call graph builder
- `zsh_grammar/src/zsh_grammar/grammar_rules.py` — Rewritten rule generation from token sequences
- `zsh_grammar/src/zsh_grammar/semantic_grammar_extractor.py` — Parse.c semantic grammar extraction
- `zsh_grammar/src/zsh_grammar/rule_comparison.py` — Validation against documented grammar
- `zsh_grammar/src/zsh_grammar/validation_reporter.py` — Coverage metrics reporting
- `zsh_grammar/token_sequence_validators.py` — Validation framework
- `PHASE_2_4_1_COMPLETION.md` — Migration guide and examples

**Modified Files:**

- `zsh_grammar/src/zsh_grammar/_types.py` — Added enhanced TypedDict structures
- `zsh_grammar/src/zsh_grammar/control_flow.py` — Added build_call_graph_enhanced
- `zsh_grammar/src/zsh_grammar/construct_grammar.py` — Integrated enhanced extraction

### Key Metrics

- **Test Coverage**: 167 total tests passing
- **Code Quality**: 0 ruff violations, 0 basedpyright errors
- **Architecture**: Successfully transitioned from call-graph to token-sequence model
- **Validation**: Semantic grammar reconstruction verified

### Rules Example: par_subsh

**Before (Function-Centric):**

```json
{ "$ref": "list" }
```

**After (Token-Sequence-Centric):**

```json
{
    "union": [
        {
            "sequence": [
                { "$ref": "INPAR" },
                { "$ref": "list" },
                { "$ref": "OUTPAR" }
            ]
        },
        {
            "sequence": [
                { "$ref": "INBRACE" },
                { "$ref": "list" },
                { "$ref": "OUTBRACE" }
            ]
        }
    ]
}
```

### Data Structures

**ControlFlowBranch**: Represents one execution path (if/else/switch case/loop)

```python
{
    'branch_id': 'if_1',
    'branch_type': 'if',
    'condition': 'tok == INPAR',
    'token_condition': 'INPAR',
    'start_line': 100,
    'end_line': 150,
    'items': [TokenOrCallEnhanced, ...]
}
```

**TokenOrCallEnhanced**: Discriminated union with branch context

- TokenCheckEnhanced: `{'kind': 'token', 'token_name': 'INPAR', 'branch_id': 'if_1', ...}`
- FunctionCallEnhanced: `{'kind': 'call', 'func_name': 'par_list', 'branch_id': 'if_1', ...}`
- SyntheticTokenEnhanced: `{'kind': 'synthetic_token', 'token_name': 'ALWAYS', ...}`

**FunctionNodeEnhanced**: Enhanced function node with token sequences

- `token_sequences: list[ControlFlowBranch]` — Multiple branches with ordered tokens/calls
- `has_loops: bool` — Whether function contains loops
- `is_optional: bool` — Whether main logic is optional

### Testing Strategy

**All stages use TDD:**

1. Test cases written first (provided in REDESIGN_PLAN.md)
2. Implementation follows pseudocode from plan
3. Frequent validation: `mise //:ruff-format`, `mise //:ruff --fix`, `mise //:basedpyright`
4. Full test suite: `mise run //:test`

### Integration Notes

- Old `build_call_graph()` kept for validation; deprecated
- New `build_call_graph_enhanced()` is primary source
- `_build_grammar_rules()` rewritten to consume token_sequences
- Schema validation passing; no breaking changes
- All existing tests still passing

### For Future Maintenance

1. **Debugging**: See `PHASE_2_4_1_COMPLETION.md` for workflow examples
2. **Validation**: Run `mise run //:test` to verify all stages
3. **Documentation**: Key concepts in REDESIGN_PLAN.md (Stages 0-6)
4. **Extending**: Follow patterns in token_extractors.py for new branch types
