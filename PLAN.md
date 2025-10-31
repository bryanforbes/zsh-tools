# Canonical Grammar Plan (Zsh Tools)

Authoritative plan for building a canonical, machine‑readable grammar for Zsh and generating multiple tools (Tree‑sitter parser, LSP schema, linter, formatter, docs, tests) from it.

## Goals

- Single source of truth: a canonical grammar definition (CGD) for Zsh 5.9+.
- Option‑aware grammar: represent syntax gated by Zsh options (e.g., EXTENDED_GLOB, RC_EXPAND_PARAM, KSH_ARRAYS).
- Sub‑grammars: parameter expansion, arithmetic, conditionals, globs, strings, prompt escapes, history expansion.
- Generators: emit Tree‑sitter grammar, LSP parse schema, linter and formatter rules, docs, and test corpus.
- Provenance: link rules/tokens to Zsh C source (file + line) for traceability.

Non‑goals (for now)

- Full semantic evaluation or runtime behaviors (e.g., word splitting) — these are lint/format passes, not grammar.
- Perfect coverage of every module initially — focus on core language, expand iteratively.

## Architecture (Layers)

1. Source Extraction (clang AST + heuristics)

- Parse `vendor/zsh/Src/*.c` with libclang.
- Extract: token enums, grammar‑like functions, precedence, option checks, and notable macros.
- Output: raw extraction JSON (structural facts; permissive shape).

2. Canonical Grammar Definition (CGD)

- Normalize the raw extraction into a stable, language‑agnostic schema.
- Merge manual enrichments for complex tokens (heredoc, quoting) and sub‑grammars.
- Output: `zsh-grammar/zsh_canonical_grammar.json` (primary artifact).

3. Generators (from CGD)

- Tree‑sitter grammar + queries
- LSP parse schema
- Linter rules (AST matchers + diagnostics + fix‑its)
- Formatter rules (indent/newline/spacing policies)
- Docs and generated tests from corpus/examples

4. Assembly & Validation

- Build parser; run corpus tests and language bindings tests (Node/Rust/Go/Python).
- Measure performance; adjust ambiguity/precedence.

## CGD Schema (v0)

Top‑level

- meta: name, version, source URL, generated_at, zsh_version.
- tokens: map token_id → { pattern | kind, mode?, aliases?, meta? }.
- rules: map rule_id → rule object (see constructs below).
- options: map option_name → [affected_rule_ids | feature_tags].
- subgrammars: list of subgrammar ids (e.g., parameter, arith, cond, glob, string, prompt, history).
- injections: where subgrammars can appear in others (host_rule, child_subgrammar, selector/field).
- diagnostics: optional rule‑attached lints ({id, severity, msg, when?, fix?}).
- constraints: disambiguation hints (precedence, associativity, preference, error_recovery).
- provenance: per rule/token, {file, line} from Zsh source.

Rule constructs (mutually composable)

- sequence: [elements]
- choice: [elements]
- optional: element
- repeat: { of: element, min?: 0|1, max?: n|null, sep?: token_id }
- prec: { value: number, of: element }
- assoc: { left|right, of: element }
- field: { name: string, of: element }
- alias: { as: string, of: element }
- ref: string (reference to token/rule/subgrammar)

Example (illustrative)

```json
{
    "meta": { "name": "Zsh", "version": "5.9+" },
    "tokens": {
        "IF": { "pattern": "if" },
        "THEN": { "pattern": "then" },
        "FI": { "pattern": "fi" },
        "NAME": { "pattern": "[_A-Za-z][_A-Za-z0-9]*" }
    },
    "rules": {
        "compound_list": { "repeat": { "of": "term", "sep": ";" } },
        "if_clause": {
            "sequence": [
                "IF",
                "compound_list",
                "THEN",
                "compound_list",
                { "optional": ["ELSE", "compound_list"] },
                "FI"
            ]
        }
    },
    "options": {
        "EXTENDED_GLOB": ["glob_pattern_extensions"],
        "RC_EXPAND_PARAM": ["param_expansion_flags"]
    },
    "subgrammars": [
        "parameter",
        "arith",
        "cond",
        "glob",
        "string",
        "prompt",
        "history"
    ]
}
```

## Generators and Outputs

- gen_treesitter.py
    - Inputs: CGD
    - Outputs: `tree-sitter-zsh/grammar.js`, `tree-sitter-zsh/src/node-types.json`, `tree-sitter-zsh/queries/{highlights,injections,locals}.scm`
    - Notes: map CGD constructs → Tree‑sitter DSL; encode precedence/assocs; generate queries from token/rule metadata

- gen_lsp_schema.py
    - Output: `zsh-grammar/out/zsh.lsp.json`
    - Contents: node kinds, parents/children, fields, token set, precedence; highlight token map

- gen_linter_rules.py
    - Output: `zsh-grammar/out/zsh_linter_rules.json`
    - Contents: rule matchers + constraints; option‑gated diagnostics; suggested fixes (simple transforms)

- gen_formatter_rules.py
    - Output: `zsh-grammar/out/zsh_formatter_rules.json`
    - Contents: per‑node formatting policy (indent, newline, spacing, line‑wrap hints, stable ordering)

- gen_docs.py
    - Output: `zsh-grammar/out/docs/*.md`
    - Contents: human‑readable reference (tokens, rules, options, subgrammars), provenance links

- gen_tests.py
    - Output: `tree-sitter-zsh/corpus/generated/*`
    - Contents: corpus cases from vendor Zsh tests and CGD examples

## Source Extraction (clang) specifics

- Library: `clang.cindex` (libclang). Configure path once:
    - macOS (Homebrew): `/opt/homebrew/opt/llvm/lib/libclang.dylib`
    - Linux: typically `/usr/lib/llvm-XX/lib/libclang.so`
- Include paths / args:
    - `-I vendor/zsh/Src`
    - `-std=c99` (or as needed)
    - `-DZSH_VERSION="5.9"`
- Targets:
    - Priority: `parse.c`, `lex.c`, `subst.c`, `params.c`, `cond.c`, `string.c`, `text.c`, `glob.c`, `prompt.c`, `zsh.h`
    - Optional: module sources providing syntax extensions
- Emitted facts:
    - Function defs with signatures and locations
    - Token‑like macros/enums
    - Option checks around syntax branches (heuristic tagging)

## Repository Layout and Paths

- Input sources: `vendor/zsh/Src/*`
- Canonical artifacts: `zsh-grammar/zsh_canonical_grammar.json` (CGD)
- Generators (scripts): `zsh-grammar/src/zsh_grammar/*.py`
- TS outputs: `tree-sitter-zsh/grammar.js`, `tree-sitter-zsh/src/node-types.json`, `tree-sitter-zsh/queries/*`
- Tooling outputs: `zsh-grammar/out/{zsh.lsp.json,zsh_linter_rules.json,zsh_formatter_rules.json,docs/*}`

## Commands (per AGENTS guide)

- Install deps
    - JS: `pnpm install`
    - Python: `uv sync`
- Lint/format
    - JS: `pnpm lint`, `pnpm exec prettier -w .`
    - Python: `uv run ruff check . && uv run ruff format .`; types: `uv run basedpyright`
- Build & test parser
    - Build C lib: `make -C tree-sitter-zsh`
    - WASM: `pnpm exec tree-sitter build --wasm`
    - Rust: `(cd tree-sitter-zsh && cargo build)`
    - All tests: `pnpm -r test`
    - Single grammar test: `pnpm exec tree-sitter test -f "<name|path>"` in `tree-sitter-zsh/`
    - Node: `node --test --test-name-pattern="<name>" tree-sitter-zsh/bindings/node/binding_test.js`
    - Rust: `(cd tree-sitter-zsh && cargo test)`
    - Go: `(cd tree-sitter-zsh && go test ./bindings/go -run TestCanLoadGrammar)`
    - Python: `(cd tree-sitter-zsh/bindings/python && python -m unittest tests.test_binding.TestLanguage.test_can_load_grammar)`

## Testing Strategy

- Corpus: leverage `vendor/zsh/Test/*` and real‑world scripts
- Positive/negative examples per rule (from CGD examples)
- Ambiguity checks: monitor node and error counts; adjust precedence/assoc
- Bindings tests: verify grammar loads and parses across Node/Rust/Go/Python

## Limitations & Mitigations

- Tree‑sitter constraints: bounded lookahead; encode precedence explicitly
- Shell ambiguity: use `prec`/`assoc` and selective conflicts; keep error recovery conservative
- Semantics beyond parsing (e.g., word splitting): handled in linter/formatter layers, not grammar
- Platform variance: libclang path and include dirs must be configured per system

## Immediate Implementation Notes

- Initialize rule lists/maps before mutation in enrichers to avoid KeyError/type issues.
- Wrap libclang parse in error handling; continue on file errors and collect stats.
- Ensure CGD includes provenance for functions/tokens used to seed rules.

## Roadmap

1. Finalize CGD schema (lock v0 fields and constructs)
2. Adapt extractor to emit CGD (`zsh-grammar/zsh_canonical_grammar.json`)
3. Implement Tree‑sitter generator and initial queries
4. Add corpus and bindings tests; ensure parser builds across targets
5. Implement linter and formatter generators; basic rules/policies
6. Generate docs and seed examples; iterate on option gates
7. Wire CI to regenerate and validate on changes or Zsh bumps

## Decision Record (initial)

- Source of truth: CGD JSON checked into `zsh-grammar/`
- Option gates: modeled in CGD; generators may bake defaults or expose variants
- Subgrammars: modeled as first‑class entities with injection points
- Provenance required for every generated rule/token when available

## Raw Extraction JSON

Purpose

- Faithful, low-level snapshot of Zsh syntax signals from C sources before normalization into CGD.
- Producer: `zsh-grammar/src/zsh_grammar/extract_zsh_raw.py`
- Output: `zsh-grammar/zsh_raw_extraction.json`
- Consumers: CGD mapper, diagnostics tooling, provenance docs.

Top-level fields

- meta
    - zsh_version: string (e.g., "5.9")
    - source_dir: path to vendor/zsh/Src
    - clang_args: list of compile flags used
    - libclang_path: string or null
    - generated_at: ISO timestamp
- files: [{ path, parsed, error, stats: { functions, enums, macros } }]
- functions: [{ name, return_type, params: [{name,type}], location: {file,line,column}, usr }]
- enums: [{ name|null, location, constants: [{name,value|null}], is_token_enum: bool }]
- macros: [{ name, value|null, function_like: bool, location }]
- tokens: { from_enums: [TOKEN...], from_macros: [TOKEN...] }
- option_occurrences: { OPTION_NAME: [{ file, line, column, in_function|null }] }
- errors: [string]

Example (abridged)

```json
{
    "meta": {
        "zsh_version": "5.9",
        "source_dir": "vendor/zsh/Src",
        "clang_args": ["-Ivendor/zsh/Src", "-std=c99", "-DZSH_VERSION=\"5.9\""],
        "libclang_path": "/opt/homebrew/opt/llvm/lib/libclang.dylib",
        "generated_at": "2025-10-26T20:15:00Z"
    },
    "files": [
        {
            "path": "Src/parse.c",
            "parsed": true,
            "error": null,
            "stats": { "functions": 42, "enums": 1, "macros": 8 }
        }
    ],
    "functions": [
        {
            "name": "par_list",
            "return_type": "void",
            "params": [],
            "location": { "file": "Src/parse.c", "line": 123, "column": 1 },
            "usr": "c:@F@par_list"
        }
    ],
    "enums": [
        {
            "name": "tokentype",
            "location": { "file": "Src/lex.c", "line": 10, "column": 1 },
            "constants": [{ "name": "IF", "value": 257 }],
            "is_token_enum": true
        }
    ],
    "macros": [
        {
            "name": "HEREDOC",
            "value": null,
            "function_like": false,
            "location": { "file": "Src/lex.c", "line": 200, "column": 1 }
        }
    ],
    "tokens": {
        "from_enums": ["IF", "THEN", "FI"],
        "from_macros": ["HEREDOC"]
    },
    "option_occurrences": {
        "EXTENDED_GLOB": [
            {
                "file": "Src/lex.c",
                "line": 456,
                "column": 8,
                "in_function": "zshlex"
            }
        ]
    },
    "errors": []
}
```

Module

- Path: `zsh-grammar/src/zsh_grammar/extract_zsh_raw.py`
- Usage: `mise //zsh-grammar:extract-raw-grammar`
- Options: `--zsh-version 5.9`, `--verbose`

Notes

- Uses `TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD` to capture macro definitions and tokens.
- Option occurrences are best-effort token scans; future enhancement can analyze `isset(...)` sites and preprocessor trees.
- Provenance via `{file,line,column}` is preserved for functions, enums, and macros.

## Next Steps

- Start on CGD schema file and adjust current extractor to emit it.
- Create skeletons for generator scripts under `zsh-grammar/src/zsh_grammar/`.
