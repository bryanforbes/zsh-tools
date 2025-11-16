# Grammar Extraction TODOs

Status: **Phases 1-3, 4.3, and 5.2 COMPLETE** - Grammar extraction functional with 31 parser rules generated, lexer state variants embedded, and schema validated.

## Completed ✅

- [x] **Phase 1**: Parser symbol extraction - 31 parser functions extracted from `.syms` files, token mapping working
- [x] **Phase 2**: Call graph construction - 1165 functions analyzed, 50+ cycles detected and properly handled via `$ref`
- [x] **Phase 3**: Grammar rules generation - All 31 parser functions converted to grammar rules with source traceability
- [x] **Phase 4.3**: Embed Lexer State Changes as Conditions - 20 parser functions identified, Variant nodes embedded with lexer state conditions, descriptions auto-generated
- [x] **Phase 5.2**: Schema validation - Generated grammar passes JSON schema validation

## In Progress / Remaining

### High Priority 🔴

#### Phase 3.3: Control Flow Analysis for Optional/Repeat Patterns
- **Status**: Not implemented
- **Current**: All rules classified as leaf/ref/union based only on unique function calls
- **TODO**: Analyze control flow to detect:
  - While loops → `Repeat` nodes
  - If statements without else → `Optional` nodes
  - Conditional calls inside switch → distinguish union alternatives
- **Impact**: Grammar structure incomplete - no distinction between optional vs required elements
- **Files**: Enhance `_build_grammar_rules()` with control flow visitor

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
- Optional/Repeat structure from control flow analysis
- Control flow visitor for while/if/case pattern detection
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
- **Control Flow**: Grammar lacks Optional/Repeat structure; all rules appear equally required due to missing control flow analysis.
- **Testing**: No validation that generated grammar matches actual Zsh behavior on real code.
- **References**: No validation layer for `$ref` correctness or naming convention consistency.
