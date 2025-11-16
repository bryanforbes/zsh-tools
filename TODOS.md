# Grammar Extraction TODOs

Status: **Phases 1-3 (including 3.2 and 3.3), 4.3, and 5.2 COMPLETE** - Grammar extraction functional with 31 parser rules generated, token dispatch integrated into dispatcher rules, optional/repeat patterns detected via control flow analysis, lexer state variants embedded, and schema validated.

## Completed ✅

- [x] **Phase 1**: Parser symbol extraction - 31 parser functions extracted from `.syms` files, token mapping working
- [x] **Phase 2**: Call graph construction - 1165 functions analyzed, 50+ cycles detected and properly handled via `$ref`
- [x] **Phase 3**: Grammar rules generation - All 31 parser functions converted to grammar rules with source traceability
- [x] **Phase 3.2**: Integrate Token Dispatch into Grammar Rules - COMPLETE
  - [x] Dispatcher switch/case tokens extracted (for, while, case, if, etc.)
  - [x] Inline conditional token matching (if/else, bitwise, ternary) extracted via Phase 3.2.1
  - [x] Token references validated against core_symbols
  - [x] Reference consistency validation layer implemented (new)
  - [x] Semantic tokens (STRING, ENVSTRING, ENVARRAY, NULLTOK, LEXERR) handled with descriptive placeholders
  - [x] Token deduplication in extraction (Phase 1.4 enhancement)
  - Result: 30 explicit tokens, 23 dispatcher rules with embedded token references
- [x] **Phase 3.3**: Control Flow Analysis for Optional/Repeat Patterns - 12 patterns detected (9 optional, 3 repeat), AST control flow visitor implemented
- [x] **Phase 4.3**: Embed Lexer State Changes as Conditions - 20 parser functions identified, Variant nodes embedded with lexer state conditions, descriptions auto-generated
- [x] **Phase 5.2**: Schema validation - Generated grammar passes JSON schema validation

## In Progress / Remaining

### High Priority 🔴

#### Phase 5.3: Real-World Grammar Testing

- **Status**: Not started
- **TODO**: Validate grammar against actual Zsh code:
    1. Run Zsh test suite (`vendor/zsh/Tests/`) through grammar validator
    2. Compare with realistic examples from zsh-users/zsh-completions
    3. Test complex nested constructs (for/if/case combinations)
    4. Identify over-permissive rules (accepts invalid syntax) and under-permissive (rejects valid)
- **Impact**: No confidence that grammar reflects actual Zsh parsing
- **Success Criteria**: ≥80% of test suite scripts validate correctly

### Medium Priority 🟡

#### Phase 1.4: Multi-Value Token Enhancement

- **Status**: Partially working
- **Current**: Token mapping extracts token names and text values, but may not properly list all keywords
- **TODO**: Enhance to properly handle multi-value tokens with `matches` array
- **Example**: TYPESET should have `matches: ["declare", "export", "float", "integer", "local", "readonly", "typeset"]`
- **Files**: Enhance `_build_token_mapping()` to aggregate keywords mapping to same token

#### Phase 2.3.5: Tail Recursion vs Mutual Recursion

- **Status**: Cycles detected but not classified
- **Current**: `_detect_cycles()` finds all cycles uniformly via DFS
- **TODO**: Distinguish:
    - Tail recursion: A calls A at end → can model as Repeat
    - Mutual recursion: A calls B, B calls A → requires Ref to break cycle
- **Impact**: Better grammar structure and documentation
- **Files**: Enhance `_detect_cycles()` with tail call analysis

#### Phase 3.2: Reference Consistency Validation

- **Status**: Works in practice, not formally verified
- **Current**: Rules reference each other, tokens are defined, but no validation layer
- **TODO**: Implement validation that all `$ref` match defined symbols
- **Checks**:
    - All token references use SCREAMING_SNAKE_CASE
    - All rule references use lowercase
    - No missing or circular references
- **Files**: New `_validate_refs()` function

#### Phase 5.4: Provenance Tracking

- **Status**: Not implemented
- **TODO**: Add `source.auto_generated` flag and merge logic for manual overrides
- **Features**:
    1. Mark which rules are auto-extracted vs manually curated
    2. Implement merge strategy for conflicting versions
    3. Enable future regeneration while preserving manual edits
- **Files**: Enhance `_construct_grammar()` merge logic

### Low Priority 🟢

#### Appendix: Doc Comment Extraction

- Extract leading comments from parser functions in `parse.c`
- Populate `description` fields in grammar output
- Fallback: Generate from function name + handler behavior

#### Appendix: Function Pointer / Jump Table Detection

- Identify dispatch tables (e.g., builtin function tables)
- Add edges to call graph for table-driven calls
- Mark with `[jump_table]` annotation

#### Appendix: Inline Parsing Pattern Detection

- Find direct token matching within function bodies (not delegated to other functions)
- Create synthetic symbols for inline patterns
- Example: Redirection parsing without separate `par_redir` delegation

---

## Current Output Quality

**Grammar Coverage:**

- 31 parser functions → 31 rules generated ✅
- 100+ tokens extracted with string mappings ✅
- Source traceability (file/line/function) ✅
- Cycles properly broken via `$ref` ✅
- Token dispatch fully integrated ✅
  - 23 dispatcher rules have embedded token references
  - 30 explicit tokens extracted from both switch/case and inline conditionals
  - All extracted token references validated against core_symbols ✅
  - Reference consistency validation layer implemented ✅
  - Semantic tokens handled with descriptive placeholders ✅
- Schema validation passing ✅

**Completed Enhancements:**

- Phase 3.2.1: Inline conditional token extraction (if/else, bitwise, macros, ternary)
- Phase 3.2 new: Reference consistency validation (`_validate_all_refs`)
- Phase 1.4 enhancement: Token deduplication during extraction
- Semantic token support (STRING, ENVSTRING, ENVARRAY, NULLTOK, LEXERR)

**Missing:**

- Tail recursion vs mutual recursion classification
- Multi-value token aggregation verification (PARTIAL)
- Real-world test validation (Phase 5.3)
- Provenance tracking with auto_generated flags (Phase 5.4)
- Doc comment extraction from C source

---

## Notes

- **Token Dispatch (Phase 3.2)**: COMPLETE. Extracts tokens from both:
  1. Switch/case dispatcher statements (original Phase 3.2)
  2. Inline conditionals - if/else, bitwise checks (&, |), comparison (==, !=), ternary operators (?:), macros (ISTOK, ISUNSET), compound conditions (&&, ||) (Phase 3.2.1)
  - 30 explicit tokens extracted, 23 dispatcher rules with embedded token references
  - 5 semantic tokens (STRING, ENVSTRING, ENVARRAY, NULLTOK, LEXERR) represented with descriptive placeholders

- **Reference Consistency Validation (Phase 3.2 new)**: New `_validate_all_refs()` function walks entire grammar graph and validates:
  - All `$ref` point to defined symbols
  - Token references use SCREAMING_SNAKE_CASE
  - Rule references use lowercase naming
  - Catches naming consistency violations

- **Semantic Tokens**: Tokens without concrete text representations (STRING, ENVSTRING, etc.) are now properly supported with semantic placeholders like `<string>`, `<env_string>`, etc.

- **Lexer States**: Successfully embedded as Variant nodes with condition constraints. 20 functions identified and integrated.

- **Cycle Handling**: Currently all cycles handled uniformly via `$ref`. Distinguishing tail vs mutual recursion could enable better Repeat modeling for tail-recursive patterns.

- **Control Flow**: Phase 3.3 successfully detects Optional patterns (if without else: 9 cases) and Repeat patterns (while/for loops: 3 cases). AST control flow visitor analyzes parser functions and wraps detected patterns in Optional/Repeat nodes.

- **Testing**: No validation that generated grammar matches actual Zsh behavior on real code.

- **Token Deduplication**: Phase 1.4 enhancement prevents duplicate entries in token text arrays during extraction from multiple sources.
