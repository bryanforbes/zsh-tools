# Grammar Extraction TODOs

Status: **Phases 1-3, 2.4 INFRASTRUCTURE, 4.3, and 5.2 COMPLETE BUT ARCHITECTURALLY FLAWED** - Grammar extraction appears functional with 31 parser rules generated, but fundamental architecture issue discovered: extraction is function-centric (call graphs) when grammar is token-sequence-centric. Phase 2.4 infrastructure exists but token sequences are never used to build rules. Current implementation cannot reconstruct semantic grammar comments like "INPAR list OUTPAR | INBRACE list OUTBRACE". **CRITICAL**: Phase 2.4.1 requires complete redesign, not incremental enhancement.

## Completed ✅

- [x] **Phase 1**: Parser symbol extraction - 31 parser functions extracted from `.syms` files, token mapping working
- [x] **Phase 1.4**: Multi-Value Token Enhancement - COMPLETE
    - [x] Token schema supports both single string and array of strings
    - [x] Tokens can represent multiple keywords (e.g., TYPESET: ["declare", "export", "float", "integer", "local", "readonly", "typeset"])
    - [x] Token matches field: `string | string[]` with minItems: 2 for arrays
    - Result: Flexible token matching for multi-keyword parser functions
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
- [x] **Phase 2.4 Infrastructure**: Token consumption pattern extraction - `TokenEdge` type created, `_extract_token_consumption_patterns()` analyzes tok == checks, `_integrate_token_patterns_into_rule()` prepared for phase 2.4.1, call graph extended with token_edges field
- [x] **Phase 4.3**: Embed Lexer State Changes as Conditions - 20 parser functions identified, Variant nodes embedded with lexer state conditions, descriptions auto-generated
- [x] **Phase 5.2**: Schema validation - Generated grammar passes JSON schema validation

## In Progress / Remaining

### Phase 2.4.1 Planning: REVIEWED ✅

- [x] **PHASE_2_4_1_PLANNING_COMPLETE.md** — Reviewed (5-10 min overview)
- [x] **PHASE_2_4_1_ARCHITECTURE_SHIFT.md** — Reviewed (technical justification)
- [x] **PHASE_2_4_1_REDESIGN_PLAN.md** — Reviewed (detailed implementation specs)
- [x] **PHASE_2_4_1_QUICK_REFERENCE.md** — Reviewed (sub-agent workflow guide)
- [x] **PHASE_2_4_1_INDEX.md** — Reviewed (navigation index)

**Status**: All planning documents reviewed and ready for implementation. Stage 0 ready to begin.

---

### Critical Priority 🔴🔴

#### FUNDAMENTAL ISSUE: Function-Centric vs Token-Sequence-Centric Grammar

- **Discovery**: Current extraction is function-centric (what calls what), but the actual grammar is token-sequence-centric (tokens surrounding recursive non-terminals)
- **Why it fails**:
    - `par_subsh()` calls `par_list()` → extracted grammar: `{'$ref': 'list'}`
    - Semantic grammar says: `INPAR list OUTPAR | INBRACE list OUTBRACE [ "always" ... ]`
    - Token sequences (INPAR/OUTPAR, INBRACE/OUTBRACE) are not function call alternatives; they're token-dependent control flow
    - The "always" block depends on STRING token matching, not a separate function call
- **Impact**: Extracted grammar is fundamentally incomplete and cannot reconstruct semantic grammar comments
- **Files Affected**: `construct_grammar.py` needs complete restructuring; `PLAN.md` Phase 2.4 and Phase 3 redefined
- **Solution Approach**: Replace function-centric call graph with token-sequence extraction from AST

#### Phase 2.4.1: Token-Sequence-Based Grammar Extraction (REDESIGN)

**Overall Status**: Ready for implementation (6 stages, 8-12 sprints estimated)

**Critical Facts:**

- Current extraction is function-centric (call graphs), needs token-sequence-centric
- Token infrastructure exists but is unused dead code
- Redesign requires ~40-60% rewrite of extraction logic (not incremental)
- Can be parallelized across 3-4 independent sub-agents
- Success criteria: ≥80% of functions reconstruct semantic grammar comments

---

##### Stage 0: Data Structure Redesign & Validation Framework

- **Status**: NOT STARTED
- **Duration**: 1-2 sprints
- **Dependencies**: None (can start immediately)
- **Agent Role**: Data architect + Test setup
- **Spec**: See `PHASE_2_4_1_REDESIGN_PLAN.md` Stage 0 (sections 0.1-0.3)
- **Deliverables**:
    - [ ] 0.1: TypedDict structures (TokenCheckEnhanced, ControlFlowBranch, FunctionNodeEnhanced)
    - [ ] 0.2: Test harness (test_par_subsh_token_sequences, test_par_if_token_sequences, test_par_case_token_sequences)
    - [ ] 0.3: Validation framework (TokenSequenceValidator class)
- **Output Files**:
    - Modified: `zsh_grammar/src/_types.py`
    - New: `zsh_grammar/tests/test_data_structures.py`
    - New: `zsh_grammar/tests/test_token_sequence_extraction.py`
    - New: `zsh_grammar/token_sequence_validators.py`

---

##### Stage 1: Branch Extraction & AST Analysis

- **Status**: NOT STARTED
- **Duration**: 2-3 sprints
- **Dependencies**: Stage 0
- **Agent Role**: AST analysis specialist
- **Spec**: See `PHASE_2_4_1_REDESIGN_PLAN.md` Stage 1 (sections 1.1-1.2)
- **Deliverables**:
    - [ ] 1.1: Identify control flow branches in AST
    - [ ] 1.2: Extract branch conditions
- **Output Files**:
    - New: `zsh_grammar/branch_extractor.py`
    - New: `zsh_grammar/tests/test_branch_extractor.py`

---

##### Stage 2: Token & Call Sequence Extraction

- **Status**: NOT STARTED
- **Duration**: 2-3 sprints
- **Dependencies**: Stage 0, Stage 1
- **Agent Role**: Token extraction specialist
- **Spec**: See `PHASE_2_4_1_REDESIGN_PLAN.md` Stage 2 (sections 2.1-2.3)
- **Deliverables**:
    - [ ] 2.1: Extract tokens and calls in order for each branch
    - [ ] 2.2: Handle synthetic tokens from string matching
    - [ ] 2.3: Merge branch items with sequence indices
- **Output Files**:
    - Modified: `zsh_grammar/token_extractors.py`
    - New: `zsh_grammar/tests/test_token_extraction_advanced.py`

---

##### Stage 3: Enhanced Call Graph Construction

- **Status**: NOT STARTED
- **Duration**: 1-2 sprints
- **Dependencies**: Stage 0, Stage 1, Stage 2
- **Agent Role**: Integration specialist
- **Spec**: See `PHASE_2_4_1_REDESIGN_PLAN.md` Stage 3 (sections 3.1-3.3)
- **Deliverables**:
    - [ ] 3.1: Build enhanced call graph with token_sequences
    - [ ] 3.2: Validate extracted sequences
    - [ ] 3.3: Compare enhanced graph with old call graph
- **Output Files**:
    - Modified: `zsh_grammar/control_flow.py`
    - New: `zsh_grammar/tests/test_enhanced_call_graph.py`

---

##### Stage 4: Rule Generation from Token Sequences

- **Status**: NOT STARTED
- **Duration**: 2-3 sprints
- **Dependencies**: Stage 0, Stage 3
- **Agent Role**: Grammar generator
- **Spec**: See `PHASE_2_4_1_REDESIGN_PLAN.md` Stage 4 (sections 4.1-4.4)
- **Deliverables**:
    - [ ] 4.1: Rewrite \_build_grammar_rules to consume token_sequences
    - [ ] 4.2: Model control flow branches as Union alternatives
    - [ ] 4.3: Model token sequences as Sequence nodes
    - [ ] 4.4: Model loops as Repeat; optional blocks as Optional
- **Output Files**:
    - Modified: `zsh_grammar/grammar_rules.py`
    - Modified: `zsh_grammar/construct_grammar.py`
    - New: `zsh_grammar/tests/test_grammar_rules_advanced.py`

---

##### Stage 5: Semantic Grammar Validation & Comparison

- **Status**: NOT STARTED
- **Duration**: 2-3 sprints
- **Dependencies**: Stage 0, Stage 4
- **Agent Role**: QA/Validation specialist
- **Spec**: See `PHASE_2_4_1_REDESIGN_PLAN.md` Stage 5 (sections 5.1-5.3)
- **Deliverables**:
    - [ ] 5.1: Extract semantic grammar comments from parse.c
    - [ ] 5.2: Compare extracted rules against documented grammar
    - [ ] 5.3: Generate validation report with coverage metrics
- **Output Files**:
    - New: `zsh_grammar/semantic_grammar_extractor.py`
    - New: `zsh_grammar/rule_comparison.py`
    - New: `zsh_grammar/validation_reporter.py`
    - New: `zsh_grammar/tests/test_semantic_grammar_extractor.py`
    - New: `zsh_grammar/tests/test_rule_comparison.py`
    - Report: `PHASE_2_4_1_VALIDATION_REPORT.md` (generated, committed)

---

##### Stage 6: Documentation & Integration

- **Status**: NOT STARTED
- **Duration**: 1 sprint
- **Dependencies**: All previous stages
- **Agent Role**: Documentation specialist
- **Spec**: See `PHASE_2_4_1_REDESIGN_PLAN.md` Stage 6 (section 6.1)
- **Deliverables**:
    - [ ] 6.1: Update TODOS.md (mark Phase 2.4.1 complete, document metrics)
    - [ ] 6.2: Update AGENTS.md (add Phase 2.4.1 workflow if needed)
    - [ ] 6.3: Create PHASE_2_4_1_COMPLETION.md (migration guide, before/after examples)
- **Output Files**:
    - Modified: `TODOS.md`
    - Modified: `AGENTS.md`
    - New: `PHASE_2_4_1_COMPLETION.md`

---

**Stage Dependencies:**

```
Stage 0 (required)
├── Stage 1 (AST analysis)
├── Stage 2 (token extraction)
│   └── Depends on: Stage 0, Stage 1
├── Stage 3 (integration)
│   └── Depends on: Stage 0, Stage 1, Stage 2
├── Stage 4 (rule generation)
│   └── Depends on: Stage 0, Stage 3
├── Stage 5 (validation)
│   └── Depends on: Stage 0, Stage 4
└── Stage 6 (documentation)
    └── Depends on: All previous
```

**Parallel Work Possible:**

- Stages 1-2 can run in parallel (both depend on Stage 0)
- Stage 3 can start once Stage 2 completes
- Stage 4 and 5 can run in parallel (both depend on Stage 3/0)
- Stage 6 only after all others complete

---

**Critical Success Criteria:**

- ✓ par_subsh rule: `Union[Sequence[INPAR, list, OUTPAR], Sequence[INBRACE, list, OUTBRACE, ...]]`
- ✓ Grammar comments from parse.c reconstructed in ≥80% of functions
- ✓ Call graph validation confirms all extracted functions are called
- ✓ Schema validation passing; no breaking changes

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

**What Works:**

- 31 parser functions → 31 rules generated (as function references only) ✅
- 100+ tokens extracted with string mappings ✅
- Source traceability (file/line/function) ✅
- Cycles properly broken via `$ref` ✅
- Token dispatch at dispatcher level (switch/case) ✅
    - 23 dispatcher rules have embedded token references
    - 30 explicit tokens extracted from both switch/case and inline conditionals
    - All extracted token references validated against core_symbols ✅
    - Reference consistency validation layer implemented ✅
    - Semantic tokens handled with descriptive placeholders ✅
- Schema validation passing ✅

**What's Broken (Fundamental Architecture Issue):**

- **Rules are function-centric, not token-sequence-centric**:
    - Example: `par_subsh()` → extracted rule is just `{'$ref': 'list'}`
    - Should be: `Union[Sequence[INPAR, list, OUTPAR], Sequence[INBRACE, list, OUTBRACE, Optional[ALWAYS, ...]]]`
    - Result: Grammar cannot be parsed by anyone unfamiliar with Zsh internals
- **Token sequences extracted but never used**:
    - `_extract_token_consumption_patterns()` collects tokens
    - `TokenEdge` records token names
    - But `_build_grammar_rules()` ignores all this and builds rules from call graph only
    - Infrastructure exists but is dead code
- **Cannot reconstruct semantic grammar comments**:
    - Parse.c has documented grammar: `INPAR list OUTPAR | INBRACE list OUTBRACE`
    - Extracted grammar has no equivalent
    - ✗ 0% of multi-token functions reconstruct documented semantic grammar
- **Token-based control flow not modeled**:
    - `if (otok == INPAR) ... par_list() ... else if (otok == INBRACE) ... par_list() ...`
    - Should create Union with token-based alternatives
    - Currently creates single-call reference; token-based dispatch is invisible
- **String matching treated as side effect**:
    - `tok == STRING && !strcmp(tokstr, "always")` controls optional block
    - Not modeled in grammar; just ignored in control flow analysis
    - Optional detection looks at if-statements, not token-based conditions

**Completed Enhancements (that don't help the core issue):**

- Phase 3.2.1: Inline conditional token extraction (if/else, bitwise, macros, ternary)
- Phase 3.2 new: Reference consistency validation (`_validate_all_refs`)
- Phase 1.4 enhancement: Token deduplication during extraction
- Semantic token support (STRING, ENVSTRING, ENVARRAY, NULLTOK, LEXERR)

**Critical Blocker:**

- Phase 2.4.1 (token sequence wrapping) is **not an enhancement to existing code**; it's a **complete architectural redesign**
- Current infrastructure (token edge extraction) is insufficient; needs ordered timelines with control flow branches
- `_build_grammar_rules()` must be rewritten to consume token sequences, not call graphs
- Estimated effort: 40-60% of extraction work needs rewrite

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

- **Phase 2.4 Infrastructure INCOMPLETE (Dead Code)**:
    - `TokenEdge` TypedDict defines token consumption metadata (token_name, position, line, context)
    - `_extract_token_consumption_patterns()` walks AST analyzing tok == TOKEN_NAME checks
    - Collected tokens stored in call_graph[func_name]['token_edges'] field
    - `_build_call_graph()` calls token extraction for all parser functions
    - **BUT**: `_build_grammar_rules()` completely ignores `token_edges` field
    - **Result**: Token infrastructure is dead code; rules are built from call graph alone
    - **Why extracted tokens don't help**:
        - `_extract_token_consumption_patterns()` collects individual tokens without ordering
        - No control flow branch grouping (if/else alternatives)
        - No sequencing information (which tokens come before/after function calls)
        - `_integrate_token_patterns_into_rule()` placeholder never called
    - **Phase 2.4.1 is complete redesign**: Must extract ordered timelines with branch context, not isolated tokens
