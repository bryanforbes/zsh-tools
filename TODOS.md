# Grammar Extraction TODOs

Status: **Phases 1-3 (including 3.3), 4.3, and 5.2 COMPLETE** - Grammar extraction functional with 31 parser rules generated, optional/repeat patterns detected via control flow analysis, lexer state variants embedded, and schema validated. **Phase 3.2 (Token Dispatch Integration) pending** - identified as high priority for canonical grammar completeness.

## Completed ✅

- [x] **Phase 1**: Parser symbol extraction - 31 parser functions extracted from `.syms` files, token mapping working
- [x] **Phase 2**: Call graph construction - 1165 functions analyzed, 50+ cycles detected and properly handled via `$ref`
- [x] **Phase 3**: Grammar rules generation - All 31 parser functions converted to grammar rules with source traceability
- [x] **Phase 3.3**: Control Flow Analysis for Optional/Repeat Patterns - 12 patterns detected (9 optional, 3 repeat), AST control flow visitor implemented
- [x] **Phase 4.3**: Embed Lexer State Changes as Conditions - 20 parser functions identified, Variant nodes embedded with lexer state conditions, descriptions auto-generated
- [x] **Phase 5.2**: Schema validation - Generated grammar passes JSON schema validation

## In Progress / Remaining

### High Priority 🔴

#### Phase 3.2: Integrate Token Dispatch into Grammar Rules

- **Status**: Not started
- **TODO**: Embed `token_to_rules` mappings into grammar rules to show which tokens trigger which alternatives
- **Current**: Token-to-rule mappings extracted but only used for validation, not integrated into rule structure
- **Implementation**:
    1. Pass `token_to_rules` to `_build_grammar_rules()` alongside call graph
    2. For dispatcher functions (e.g., `par_cmd()` with switch statements), include token references in union
    3. Example: `cmd` rule should include `{'$ref': 'FOR'}`, `{'$ref': 'CASE'}`, etc. alongside rule refs
    4. Document explicit tokens vs. default/catch-all cases in rule descriptions
    5. Validate all token references exist in `core_symbols`
- **Why this matters**: Zsh source comments document grammar as `event : ENDINPUT | SEPER | sublist`, showing tokens are first-class grammar elements, not metadata
- **Files**: Modify `_build_grammar_rules()` in `construct_grammar.py`
- **Impact**: Improves canonical grammar completeness; aligns with source documentation
- **Success Criteria**: All dispatcher rules include both token and subrule references in unions

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
- Schema validation passing ✅

**Missing:**

- Tail recursion vs mutual recursion classification
- Reference consistency validation layer
- Multi-value token aggregation verification (PARTIAL)
- Real-world test validation
- Provenance tracking with auto_generated flags
- Doc comment extraction from C source

---

## Notes

- **Lexer States**: Successfully embedded as Variant nodes with condition constraints. 20 functions identified and integrated.
- **Cycle Handling**: Currently all cycles handled uniformly via `$ref`. Distinguishing tail vs mutual recursion could enable better Repeat modeling for tail-recursive patterns.
- **Control Flow**: Phase 3.3 successfully detects Optional patterns (if without else: 9 cases) and Repeat patterns (while/for loops: 3 cases). AST control flow visitor analyzes parser functions and wraps detected patterns in Optional/Repeat nodes.
- **Testing**: No validation that generated grammar matches actual Zsh behavior on real code.
- **References**: No validation layer for `$ref` correctness or naming convention consistency.
