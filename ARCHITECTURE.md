# Architecture (Layers) — Expanded

## 1. Source Extraction (clang AST + heuristics)

**Goal:** produce a machine-readable, provenance-rich `raw_extraction.json` describing the *facts* in the Zsh C source.

### Responsibilities

* Parse vendor/zsh `Src/*.c` with `libclang` (`clang.cindex`) using real build flags (from `compile_commands.json` generated with `bear`).
* Extract:

  * Function declarations/definitions (names, return type, params, file/line).
  * Enum declarations and enum constants (token names, values).
  * Macro definitions (macro name, expansion text).
  * Structs/typedefs (only where useful for semantic mapping).
  * `IfStmt` / preprocessor conditionals (detect `#if/#ifdef/#ifndef` around code).
  * Simple control flow inside parser functions (token comparisons, `isset(...)` calls).
* Output a permissive JSON `raw_extraction.json` with provenance fields:

  * `files[<path>].functions[]`, `files[<path>].enums[]`, `files[<path>].macros[]`, `metadata`.

### Scripts & files

* `extract/extract_zsh_syntax.py`

  * Inputs: `vendor/zsh` (plus `compile_commands.json`)
  * Output: `extract/zsh_raw_extraction.json`
* `extract/extract_zsh_relations.py`

  * Walks function ASTs to build `relations.json` (follows/calls, token checks, isset calls, simple CFG patterns).
  * Output: `extract/zsh_relations.json`

### Heuristics & notes

* Use `TranslationUnit` parsing; read `IfStmt` nodes and `BinaryOperator` comparisons to detect `tok == TOK_IF` patterns.
* Search for `isset(FOO)` and literal option names inside conditions.
* Also capture preprocessor guards by scanning the file for `#if/#ifdef/#endif` ranges and associating them with nearby functions (heuristic window), but keep these as suggestions, not absolute truths.
* Keep all extracted data *verbatim* (do not discard unknown or ambiguous cases). Add fields `confidence` and `notes` in the JSON where helpful.

---

## 2. Canonical Grammar Definition (CGD)

**Goal:** turn raw facts + relations into a stable, extensible, language-agnostic *Canonical Grammar Definition* (CGD) that is the single source of truth for generators.

### Top-level artifact

* `canonical/zsh_grammar.json` (primary artifact committed to git)

### Schema (high level)

(Full schema contained in `canonical/schema.py` as TypedDicts; condensed here)

* `languages: { <name>: { rules, tokens, includes, contexts, precedence, description } }`

  * `rules: { <rule_name>: RuleDef }`

    * `RuleDef` fields: `type`, `elements`, `follows`, `calls`, `contexts`, `meta`, `location`, `node_type`, `formatting`, `lint`, `tests`
  * `tokens: { <token_name>: TokenDef }`

    * `TokenDef` fields: `pattern`, `description`, `enter_mode`, `leave_mode`, `meta`, `origin_file`, `line`
* `contexts`: parser contexts / modes (e.g., `command`, `arith`, `string`)
* `lexer_modes`: mode definitions (which tokens are active, transitions)
* `option_effects`: mapping `OPTION -> {enables, disables, modifies, description}`
* `features`: versioned language features (since/until)
* `extension_points`: module hooks (Modules/*)
* `metadata`: provenance, zsh_version, generator, last_updated

(See `canonical/schema.py` for the exact TypedDict spec.)

### How CGD is produced

* `normalize/normalize_zsh_grammar.py` reads:

  * `extract/zsh_raw_extraction.json`
  * `extract/zsh_relations.json`
  * manual enrichment files (see below)
* Steps performed:

  1. Create language skeletons (`zsh`, `parameter`, `arith`, `cond`, `glob`, `string`, `prompt`, `history`).
  2. Add tokens from enums & macros into `languages.zsh.tokens`.
  3. For each function (from raw extraction):

     * Create a `RuleDef` with `location` (file/line), `meta.origin_file`.
     * Merge relation data: attach `follows` & `calls` from `relations.json` to that `RuleDef`.
     * If preprocessor guards or `isset()` detected, add `meta.variants` and create entries in `option_effects`.
  4. Inject hand-written enrichments (see next section) for:

     * complex tokens (HEREDOC, quoting),
     * recursive rules (parameter / arithmetic nesting),
     * glob qualifiers, prompt sequences, history expansions.
  5. Build `lexer_modes` and `contexts` by combining extraction + enrichment.
  6. Validate output against `canonical/schema.py` (type checks).

### Manual enrichment inputs

* `canonical/enrich/` directory holds small JSON/TOML/RCL files to add or override:

  * `heredoc.json`, `quotes.json`, `prompt.json`, `history.json`
  * `manual_rules.json` for trickier mappings
* These are intended to be small and auditable; keep them under version control.

---

## 3. Generators (from CGD)

**Goal:** generate *target artifacts* for each consumer: Tree-sitter grammar, LSP schema, linter rules, formatter rules, docs, tests.

### Generators & outputs

* `generators/gen_treesitter.py`

  * Input: `canonical/zsh_grammar.json`
  * Output: `tree-sitter-zsh/grammar.js`, external scanner C (`scanner.c`), highlight/query files.
  * Responsibilities: convert `RuleDef`/`TokenDef` → Tree-sitter grammar DSL; place recursive constructs appropriately; declare `externals` for HEREDOCs and nested expansions; generate `scanner.c` stub to be hand-tuned (or augmented automatically).
* `generators/gen_lsp_schema.py`

  * Input: CGD
  * Output: `lsp/zsh_schema.json` (token types, AST node types, contexts)
  * Responsibilities: produce token/type mapping for LSP diagnostics and folding.
* `generators/gen_linter_rules.py`

  * Input: CGD
  * Output: `linter/rules.json` (AST matchers, severity, fix-its)
  * Responsibilities: transform `meta.lint` fields into linter checks.
* `generators/gen_formatter_rules.py`

  * Input: CGD
  * Output: `formatter/rules.json` or formatter plugin code.
* `generators/gen_docs.py`

  * Input: CGD + `canonical/enrich/`
  * Output: `docs/grammar.md`, `docs/token_index.md`, `docs/option_effects.md`.
* `generators/gen_tests.py`

  * Input: CGD + `tests/corpus/`
  * Output: test manifests that map corpus files to grammar rules.

### External scanner

* The pipeline will generate a `scanner.c` starting point for Tree-sitter externals. The scanner must:

  * Track HEREDOC markers (start/end strings).
  * Manage nested `${...}` and `$((...))` detection and balancing to feed Tree-sitter tokens.
* Generated scanner code should be small and annotated; test harness will exercise it.

---

## 4. Assembly & Validation

**Goal:** compile a working parser and validate correctness & performance.

### Steps

1. `make tree-sitter`:

   * Run `tree-sitter generate` in `tree-sitter-zsh`.
   * Compile `scanner.c` into the parser so externals work.
2. Test harness:

   * `tests/corpus/` contains test groupings with expected parse outputs or golden snapshots.
   * Tools:

     * `tests/run_parsing_tests.py` — uses Node/wasm/rust bindings to parse sample files and compare trees.
     * `tests/run_format_tests.py` — apply formatting rules and check round-trip.
     * `tests/run_lint_tests.py` — run linter rules and verify diagnostics.
3. Performance checks:

   * Measure parse time for large scripts and the entire corpus; compare memory usage.
   * Watch for pathological cases that cause deep recursion; tune grammar or scanner.
4. CI gates:

   * Pull Request checks:

     * `make extract` (optional): regenerate raw_extraction if the Zsh source changed.
     * `python normalize/validate_schema.py canonical/zsh_grammar.json` — schema validation (type + required fields).
     * `node tree-sitter-zsh test` — basic parser generation test.
     * `pytest tests/` — full unit test coverage for generators & small parse tests.
5. Release:

   * Tag CGD changes. When CGD changes, mark generated artifacts version bump (e.g., `cgd-v1.2.0` → `tree-sitter-v1.2.0`).

---

# Repository Layout (recommended)

```
zsh-grammar/
├── ARCHITECTURE.md                # this file
├── zsh-grammar/
│   ├── canonical/
│   │   ├── schema.py                  # TypedDicts; single source of truth for CGD format
│   │   ├── enrich/                    # small hand-edits & augmentations
│   │   │   ├── heredoc.json
│   │   │   └── manual_rules.json
│   │   └── zsh_grammar.json       # generated canonical grammar
│   ├── extract/
│   │   ├── extract_zsh_syntax.py
│   │   ├── extract_zsh_relations.py
│   │   └── zsh_raw_extraction.json    # generated (in CI/artifacts)
│   ├── normalize/
│   │   └── normalize_zsh_grammar.py
│   └── generators/
│       ├── gen_treesitter.py
│       ├── gen_lsp_schema.py
│       ├── gen_linter_rules.py
│       └── gen_formatter_rules.py
├── tree-sitter-zsh/                # generated Tree-sitter grammar (gitignored or vendored)
├── tests/
│   ├── corpus/
│   ├── run_parsing_tests.py
│   └── pytest tests/...
├── docs/
│   └── grammar.md
└── CI/
    └── pipeline.yml
```

---

# Implementation & Operational Details (practical checklist)

### Build environment & reproducibility

* **Use `compile_commands.json`** for accurate `libclang` flags. Add a small guide:
    * `cd vendor/zsh && bear make` to produce `compile_commands.json`.
* **Pin libclang version** in CI (document the path for macOS vs Linux).
* **Lock generator library versions** in `pyproject.toml` or `requirements.txt`.

### Logging & provenance

* Always add `meta.generated_by`, `meta.generated_at`, `meta.source_commit` into `zsh_grammar.json`.
* For every derived rule, keep `location` pointing to the source function (file/line) and `confidence` score for inferred relationships.

### Manual editing flow

* Keep `canonical/enrich/` hand-curated, small, and strictly reviewed.
* Make all manual edits as PRs with tests linking to corpus examples showing the changed behavior.

### Diagnostics & debug tooling

* `tools/visualize_cgd.py` to render CGD to human-readable diagrams (rule call graphs, option effects).
* `tools/compare_cgd.py` to diff CGD between Zsh versions.

### Backward compatibility

* When CGD changes cause generator ABI shifts, publish generator version with migration notes.
* Keep old CGD snapshots in `canonical/versions/` for audits.

---

# Example Workflows

### Regenerate CGD from updated vendor/zsh

```bash
# inside repo root
mise //vendor:clean
mise //zsh-grammar:build:canonical
# validate
mise //zsh-grammar:validate-schema
```

### Generate Tree-sitter & test

```bash
mise //zsh-grammar:generate:treesitter
mise //tree-sitter-zsh:build:parser
mise '//tree-sitter-zsh:test:*'
```

---

# CI Recommendations

* Steps for each PR:

  1. Lint Python/JS.
  2. Validate `canonical/schema.py` + `canonical/zsh_grammar.json`.
  3. Run `generators/gen_treesitter.py` and ensure `tree-sitter generate` succeeds.
  4. Run lightweight parsing tests (a handful of corpus files) to ensure no syntax regressions.
* Full test (nightly):

  * Full corpus + performance benchmarks.

---

# Final Notes / Risks / Tradeoffs

* **Extraction confidence:** Not every conditional relationship can be inferred automatically. Expect some manual augmentation.
* **Complex macros / compile configs:** Some `#ifdef` logic is tricky; using `compile_commands.json` reduces false positives.
* **External scanner complexity:** HEREDOCs and nested expansions require careful scanner logic — expect an iterative development cycle with test harnesses.
* **Grammar ambiguity vs performance:** Tree-sitter grammars that are too permissive or ambiguous can be slow; be prepared to tweak precedence and refactor rules into external scanners.
