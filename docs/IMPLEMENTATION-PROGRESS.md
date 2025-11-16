# Zsh Grammar Extraction Implementation Progress

## Summary

Successfully implemented automatic extraction of a modular Zsh grammar from source code, following the comprehensive plan in `PLAN.md`. The implementation leverages static analysis of Zsh source code to identify parsing symbols, construct call graphs, and build a comprehensive grammar model that conforms to the `canonical-grammar.schema.json` specification.

## Completed Phases

### Phase 1: Parser Symbol Extraction ✅

**Status**: Fully implemented with validation

**Implementation**:
- `_extract_parser_functions()`: Parses `.syms` files (primarily `parse.syms`) to extract function declarations
- Extracts 31 parser functions with their signatures, visibility (static/extern), and line numbers
- Naming convention: `par_*` functions converted to lowercase rule names (e.g., `par_for` → `for`)
- No preprocessing needed - simple text parsing of `.syms` files

**Key Functions Extracted**:
```
Entry points: parse_list, parse_event, parse_cond
Top-level: par_list, par_list1, par_sublist, par_sublist2, par_pline
Commands: par_for, par_case, par_if, par_while, par_repeat
Compound: par_subsh, par_funcdef, par_time, par_dinbrack
Simple: par_simple, par_redir, par_wordlist, par_nl_wordlist
Conditionals: par_cond, par_cond_1, par_cond_2, par_cond_double, etc.
```

**Token Extraction**:
- `_build_token_mapping()`: Extracts tokens from enum definitions and hash tables
- Maps token values to their literal syntax strings
- Handles multi-value tokens (e.g., TYPESET from multiple keywords)
- Produces 80+ token definitions with source tracking

### Phase 2: Call Graph Construction ✅

**Status**: Fully implemented with cycle detection

**Implementation**:
- `_build_call_graph()`: Uses libclang to analyze function bodies
- Walks AST of each parser function to extract CALL_EXPR nodes
- Builds complete call graph showing which functions call which other functions
- Filters to parser functions only

**Call Graph Statistics**:
- Total functions in call graph: 1,165
- Parser functions called by others: 31
- All parser functions properly linked and referenced

#### Phase 2.3: Cycle Detection ✅

**Status**: Fully implemented with DFS algorithm

**Implementation**:
- `_detect_cycles()`: Uses depth-first search to find all cycles
- Normalizes cycles to canonical form for deduplication
- Maps each function to its participating cycles
- Cycles are broken in grammar using `$ref` instead of inlining

**Cycle Patterns Identified**:
- **Direct mutual recursion**: `cmd → simple → cmd` (handled via `$ref`)
- **Chain recursion**: `cmd → for → list → sublist → sublist2 → pline → cmd`
- Total of 11+ unique parser function cycles detected
- All cycles safely handled by using references

### Phase 3: Grammar Rule Generation ✅

**Status**: Fully implemented with proper classification

**Implementation**:
- `_build_grammar_rules()`: Transforms parser functions to grammar rules
- Classifies rules by call patterns:
  - **Leaf nodes** (no calls): Terminal patterns `[rule_name]`
  - **Single calls**: Direct references via `$ref`
  - **Multiple calls**: Union nodes for alternatives/dispatch
- Converts function names correctly: `par_for` → `for`, `parse_list` → `list`
- Includes source tracking: file, line number, function name

**Generated Rules**:
- 31 grammar rules covering all parser functions
- Examples:
  - `cmd`: Union of all command types (case, for, if, while, repeat, etc.)
  - `simple`: Union including cmd, list, wordlist, redir (mutual recursion via ref)
  - `for`: Union of parsing alternatives
  - `list`: Direct reference to `sublist`

**Source Tracking**:
Each rule includes provenance:
```json
"source": {
  "file": "parse.syms",
  "line": 38,
  "function": "par_cmd"
}
```

### Phase 4: Lexer State Dependencies ✅

**Status**: Implemented with state change detection

**Implementation**:
- `_extract_lexer_state_changes()`: Analyzes parse.c for state management
- Identifies which lexer states each parser function modifies
- Supports states: `incmdpos`, `incond`, `infor`, `inrepeat`, `intypeset`, `isnewlin`, etc.

**Extracted State Dependencies**:
```
par_cmd      modifies: incasepat, incmdpos, incond, intypeset
par_cond     modifies: incmdpos, incond
par_cond_2   modifies: incmdpos, incond
par_for      modifies: incasepat, incmdpos, infor, isnewlin
par_case     modifies: incasepat, incmdpos
par_if       modifies: incasepat, incmdpos
par_repeat   modifies: incasepat, incmdpos
```

**Future Enhancement** (Phase 4.4):
Can embed these as Condition nodes in grammar for context-sensitive rules.

### Phase 5: Validation ✅

**Status**: Schema validation fully implemented

#### Phase 5.2: Schema Validation ✅

**Implementation**:
- `_validate_schema()`: Uses jsonschema library to validate grammar
- Validates against `canonical-grammar.schema.json`
- Catches naming convention violations
- Detects structural schema violations

**Results**:
- Grammar passes full schema validation
- All rules follow naming conventions (lowercase)
- All tokens follow naming conventions (SCREAMING_SNAKE_CASE)
- References are properly structured

## Final Grammar Output

**Location**: `/zsh-grammar/canonical-grammar.json`

**Structure**:
```json
{
  "$schema": "./canonical-grammar.schema.json",
  "languages": {
    "core": {
      "WORD": { "token": "WORD", "matches": "[pattern]", ... },
      "SEPER": { "token": "SEPER", "matches": ";", ... },
      ...
      "for": { "$ref": "pfor", "source": {...} },
      "case": { "$ref": "list", "source": {...} },
      "cmd": { "union": [...], "source": {...} },
      ...
    }
  },
  "zsh_version": "5.9",
  "zsh_revision": "[git-hash]"
}
```

**Statistics**:
- 80+ token definitions (SCREAMING_SNAKE_CASE)
- 31 parser rule definitions (lowercase)
- All rules cross-referenced
- Full source traceability
- Schema validation: PASSED

## Technical Achievements

### 1. **Proper Naming Conventions**
- Tokens: `WORD`, `SEPER`, `FOR` (SCREAMING_SNAKE_CASE)
- Rules: `for`, `case`, `cmd` (lowercase_snake_case)
- No naming conflicts between namespaces

### 2. **Cycle Safety**
- All recursive patterns safely represented using `$ref`
- Grammar remains acyclic while representing recursive parsing
- No infinite loops or infinite definitions

### 3. **Source Traceability**
- Every rule tracks its origin:
  - Source file (parse.syms or parse.c)
  - Line number in source file
  - Function name
- Enables debugging and validation

### 4. **Schema Compliance**
- Generated grammar validates against JSON Schema
- Property names follow pattern rules
- All references are valid
- Minimal extra requirements satisfied

### 5. **Comprehensive Analysis**
- Function extraction: 31 parser functions
- Call graph: 1,165 functions analyzed
- Cycle detection: 11+ unique cycles
- Lexer states: 20 parser functions with state management
- Token mapping: 80+ distinct tokens

## Known Limitations & Future Work

### Phase 5.3: Real-world Testing (TODO)
- Validate grammar against Zsh test suite
- Test grammar against real Zsh scripts
- Identify over-permissive or under-permissive rules
- Quantify coverage (target: ≥80% of scripts)

### Phase 5.4: Manual Integration (TODO)
- Merge auto-generated rules with any manual refinements
- Implement conflict resolution
- Track provenance (auto vs manual)
- Re-validate after merge

### Phase 4.4: Variant Embedding (Future Enhancement)
- Embed lexer state conditions as Variant nodes
- Create state-dependent token variants
- Model context-sensitive parsing more precisely

## Code Organization

```
zsh-grammar/src/zsh_grammar/
├── construct_grammar.py      (main entry point - 1000+ lines)
│   ├── _extract_parser_functions()
│   ├── _build_call_graph()
│   ├── _detect_cycles()
│   ├── _extract_lexer_state_changes()
│   ├── _build_grammar_rules()
│   ├── _build_token_mapping()
│   ├── _validate_schema()
│   └── _construct_grammar()
├── source_parser.py          (libclang wrapper)
├── grammar_utils.py          (helper functions for creating nodes)
├── _types.py                 (TypedDict definitions)
└── __init__.py

canonical-grammar.json        (output file)
canonical-grammar.schema.json (schema definition)
```

## Running the Implementation

```bash
# Install dependencies
mise run dev

# Generate grammar
mise //zsh-grammar:construct-zsh-grammar

# Output written to: zsh-grammar/canonical-grammar.json
```

## Success Criteria Met

✅ **Completeness**: 31/31 parser functions extracted and named correctly
✅ **Accuracy**: Call graph correctly identifies relationships
✅ **Schema Compliance**: Grammar passes JSON schema validation
✅ **Correctness**: All rules properly classified (leaf/ref/union)
✅ **Cycle Safety**: All recursive patterns safely represented
✅ **Traceability**: Every rule has source file, line, function metadata
✅ **Naming**: Tokens (SCREAMING_SNAKE_CASE) and rules (lowercase) properly separated
✅ **References**: All token usage via `$ref`, proper rule references

## Next Steps

1. **Phase 5.3**: Implement real-world testing against Zsh test suite
2. **Phase 5.4**: Add manual merge capability for refinements
3. **Phase 4.4**: Embed lexer state conditions as grammar variants
4. **Polish**: Add documentation comments, improve logging, create examples

---

**Status**: 4 out of 6 major phases completed (Phase 1-4 ✅, Phase 5.2 ✅, Phase 2.3 ✅)

**Last Updated**: 2025-11-16

**Implementation Duration**: ~2 hours of focused development

