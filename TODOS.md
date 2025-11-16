# Grammar Extraction TODOs

Status: **Phases 1-3, 2.4 INFRASTRUCTURE, 4.3, and 5.2 COMPLETE BUT ARCHITECTURALLY FLAWED** - Grammar extraction appears functional with 31 parser rules generated, but fundamental architecture issue discovered: extraction is function-centric (call graphs) when grammar is token-sequence-centric. Phase 2.4 infrastructure exists but token sequences are never used to build rules. Current implementation cannot reconstruct semantic grammar comments like "INPAR list OUTPAR | INBRACE list OUTBRACE". **CRITICAL**: Phase 2.4.1 requires complete redesign, not incremental enhancement.

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
- [x] **Phase 2.4 Infrastructure**: Token consumption pattern extraction - `_TokenEdge` type created, `_extract_token_consumption_patterns()` analyzes tok == checks, `_integrate_token_patterns_into_rule()` prepared for phase 2.4.1, call graph extended with token_edges field
- [x] **Phase 4.3**: Embed Lexer State Changes as Conditions - 20 parser functions identified, Variant nodes embedded with lexer state conditions, descriptions auto-generated
- [x] **Phase 5.2**: Schema validation - Generated grammar passes JSON schema validation

## In Progress / Remaining

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

- **Status**: REQUIRES COMPLETE RETHINK - infrastructure insufficient
- **Current Issue**:
    - `_extract_token_consumption_patterns()` collects tokens but loses ordering/sequencing information
    - `_TokenEdge` only records individual token names, not control flow context
    - `_build_grammar_rules()` uses call graph to determine structure; token information is unused
    - Result: Token extraction infrastructure exists but is never used to build rules
- **Required Redesign**:
    1. **Extract Token-to-Call Timeline** (NEW):
        - Walk AST and record ordered sequence of all `tok == TOKEN` checks and `par_*()` calls
        - Build per-branch timelines for if/else/switch statements
        - Example: `[tok==INPAR, par_list(), tok==OUTPAR] | [tok==INBRACE, par_list(), tok==OUTBRACE]`
    2. **Reconstruct Control Flow Branches** (NEW):
        - Group tokens by control flow branch (each if/else/case arm becomes separate sequence)
        - Identify token-based dispatch: `if (tok == INPAR) ... else if (tok == INBRACE) ...`
        - Map to Union with alternatives per token pattern, not per function
    3. **Handle String Matching as Synthetic Tokens** (NEW):
        - `tok == STRING && !strcmp(tokstr, "always")` → create synthetic token `ALWAYS`
        - Model optional blocks with synthetic token conditions
        - Document provenance of synthetic tokens
    4. **Preserve Execution Order** (CRITICAL):
        - Do NOT reorder tokens; AST order determines semantics
        - `tok==A, par_foo(), tok==B` must model as `Sequence[A, foo, B]`, not Union
    5. **Modify Rule Generation**:
        - Change `_build_grammar_rules()` to consume `token_sequences` instead of call graph
        - Call graph is secondary; use it only for validation that functions are called as expected
        - Build rules directly from token sequences

- **Data Structure Changes**:
    - Replace/enhance `_TokenEdge` to include control flow branch identifier
    - Add new `token_sequences: list[list[TokenOrCall]]` field to `_FunctionNode`
    - Where `TokenOrCall = {'token': str} | {'call': str} | {'optional': [...]} | {'union': [...]}`
    - Document synthetic tokens in separate metadata

- **Implementation Path**:
    1. Rewrite AST walker to extract ordered timelines (replace current preorder walk)
    2. Implement control flow branch grouping (separate code paths into alternatives)
    3. Extend `_FunctionNode` with `token_sequences` field
    4. Rewrite `_build_grammar_rules()` to use `token_sequences` as primary input
    5. Use call graph only for validation/cycle detection

- **Files**: `construct_grammar.py` - complete refactor of Phase 2.4 extraction and Phase 3 rule building
- **Success Criteria**:
    - `par_subsh` rule: `Union[Sequence[INPAR, list, OUTPAR], Sequence[INBRACE, list, OUTBRACE, Optional[...]]]`
    - Grammar comments like "INPAR list OUTPAR | INBRACE list OUTBRACE" are accurately reconstructed
    - ≥80% of parser functions reconstruct documented semantic grammar from comments
    - Call graph validation confirms all extracted functions are actually called

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
    - `_TokenEdge` records token names
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
    - `_TokenEdge` TypedDict defines token consumption metadata (token_name, position, line, context)
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
