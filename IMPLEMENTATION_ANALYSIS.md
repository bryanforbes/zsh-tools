# TODOS.md Implementation Analysis

**Date**: November 16, 2025  
**Status**: Phases 1-3, 4.3, and 5.2 VERIFIED IMPLEMENTED

---

## Summary

This analysis cross-references TODOS.md claims against actual code in `construct_grammar.py` and the generated `canonical-grammar.json`. The project has **successfully implemented** most core phases, with specific gaps in control flow analysis and real-world testing.

---

## ✅ IMPLEMENTED ITEMS

### **Phase 1: Parser Symbol Extraction**

- **Status**: ✅ COMPLETE & VERIFIED
- **Location**: `_extract_parser_functions()` (lines 133-206)
- **Evidence**:
    - Extracts 31 parser functions from `parse.syms`
    - Parses pattern: `[LE](static|extern) (?:\w+\s+)*(\w+) ([a-z_][a-z0-9_]*) _\(\(([^)]*)\)\);`
    - Handles intermediate keywords like `mod_import_function`
    - Returns `FunctionNode` with visibility, signature, file/line tracking
    - Grammar output confirms: 31 rules generated with source traceability

### **Phase 2: Call Graph Construction**

- **Status**: ✅ COMPLETE & VERIFIED
- **Location**: `_build_call_graph()` (lines 227-254)
- **Evidence**:
    - Parses all `.c` files with libclang
    - Extracts function definitions and call expressions
    - Builds call graph with 1165+ functions analyzed
    - Detects conditions (isset checks, option flags) at lines 209-224
    - `_detect_conditions()` collects OPTION references and boolean checks

### **Phase 3: Grammar Rules Generation**

- **Status**: ✅ COMPLETE & VERIFIED
- **Location**: `_build_grammar_rules()` (lines 417-480)
- **Evidence**:
    - Converts 31 parser functions to 31 grammar rules
    - Classification heuristics working:
        - **No calls** → terminal/leaf (e.g., `create_terminal()`)
        - **1 call** → direct reference (e.g., `create_ref()`)
        - **Multiple calls** → union alternatives (e.g., `create_union()`)
    - Source traceability: file, line, function stored in each rule
    - Grammar contains rules: `list`, `event`, `cond`, `cmd`, `for`, `case`, `if`, `while`, `repeat`, etc.

### **Phase 2.3 (Cycle Detection)**

- **Status**: ✅ COMPLETE & VERIFIED
- **Location**: `_detect_cycles()` (lines 330-382)
- **Evidence**:
    - DFS-based cycle detection (normalized to canonical form)
    - 50+ cycles detected in call graph
    - Cycles properly broken via `$ref` in output (not inlined)
    - Example cycles: `par_event ↔ par_list`, `par_cond_1 ↔ par_cond_2`

### **Phase 4.3: Embed Lexer State Changes as Conditions** ✅

- **Status**: ✅ COMPLETE & VERIFIED (NOT just detected)
- **Location**: `_embed_lexer_state_conditions()` (lines 483-650)
- **Evidence**:
    - **20 parser functions** identified that modify lexer state
    - State changes embedded as **Variant nodes** in output
    - Example from `canonical-grammar.json` for `for` rule:
        ```json
        {
          "variant": { "union": [...] },
          "condition": { "lexstate": "INCMDPOS" },
          "description": "for sets lexer state INCMDPOS",
          "source": { "file": "parse.c", "line": 1090, "function": "par_for" }
        }
        ```
    - Maps: incmdpos → INCMDPOS, incond → INCOND, infor → INFOR, etc.
    - Functions with state changes: `par_cmd`, `par_list`, `par_cond`, `par_for`, `par_case`, etc.
    - **Main rule union includes base + variant for each state change**
    - Description added automatically: `"for (modifies lexer states: INCMDPOS, INFOR, ISNEWLIN, INCASEPAT)"`

### **Phase 5.2: Schema Validation**

- **Status**: ✅ COMPLETE & VERIFIED
- **Location**: `_validate_schema()` (lines 1004-1027)
- **Evidence**:
    - Uses `jsonschema.validate()` with `canonical-grammar.schema.json`
    - Comprehensive validation output in main()
    - Generated grammar passes validation (confirmed: `Schema validation: PASSED`)
    - Validates against both schema structure and instance data

### **Supporting Infrastructure**

- **Token Mapping**: ✅ `_build_token_mapping()` (lines 683-721)
    - Extracts 100+ tokens from `lextok` enum and hash table
    - Maps text matches to tokens
    - Handles multi-value tokens (some with multiple text representations)
- **Completeness Validation**: ✅ `_validate_completeness()` (lines 855-960)
    - Validates all expected rules are referenced
    - Categorizes unreferenced rules (entry points vs orphaned)
    - Reports dispatch references and call graph references

---

## ❌ NOT IMPLEMENTED

### **Phase 3.3: Control Flow Analysis for Optional/Repeat Patterns**

- **Status**: ❌ NOT IMPLEMENTED
- **Expected**: Analyze while loops → `Repeat` nodes; if statements → `Optional` nodes
- **Evidence**:
    - Zero `optional` nodes in grammar output (verified with jq)
    - Zero `repeat` nodes in grammar output (verified with jq)
    - No functions for control flow visitor: no `_analyze_control_flow()`, no `_detect_loops()`, no `_classify_optional()`
    - Rules only distinguish based on unique function calls, not control structure
    - **Impact**: Grammar lacks Optional/Repeat structure; all rules appear equally required

### **Phase 5.3: Real-World Grammar Testing**

- **Status**: ❌ NOT IMPLEMENTED
- **Expected**:
    - Run Zsh test suite through grammar validator
    - Compare against realistic zsh-completions examples
    - Test nested constructs (for/if/case combinations)
- **Evidence**:
    - No test files found in codebase
    - No validation against `vendor/zsh/Tests/` examples
    - No utility functions for parsing real Zsh code
    - **Impact**: No confidence grammar reflects actual Zsh parsing behavior

### **Phase 2.3.5: Tail Recursion vs Mutual Recursion Classification**

- **Status**: ❌ NOT IMPLEMENTED
- **Expected**: Distinguish tail recursion (A→A at end) from mutual recursion (A→B→A)
- **Evidence**:
    - `_detect_cycles()` treats all cycles uniformly
    - No tail call analysis: no `_is_tail_call()`, no `_analyze_tail_calls()`
    - Both types use same `$ref` handling
    - **Impact**: Cycles documented but not optimized for tail recursion patterns

### **Phase 3.2: Reference Consistency Validation**

- **Status**: ❌ NOT IMPLEMENTED
- **Expected**: Validate all `$ref` match defined symbols; check naming conventions
- **Evidence**:
    - No `_validate_refs()` function (confirmed: ImportError when attempted)
    - No checks for SCREAMING_SNAKE_CASE token refs or lowercase rule refs
    - No detection of missing or circular references
    - **Impact**: Silent failure if rules reference undefined symbols

### **Phase 5.4: Provenance Tracking**

- **Status**: ❌ NOT IMPLEMENTED
- **Expected**: `source.auto_generated` flag + merge logic for manual overrides
- **Evidence**:
    - Zero occurrences of `auto_generated` in codebase
    - No provenance system: no `_mark_provenance()`, no `_merge_overrides()`
    - No regeneration-safe merge strategy
    - **Impact**: Cannot preserve manual edits across regeneration cycles

### **Appendix: Doc Comment Extraction**

- **Status**: ❌ NOT IMPLEMENTED
- **Expected**: Extract leading comments from parse.c functions
- **Evidence**:
    - No docstring extraction logic
    - No `_extract_comments()` function
    - Descriptions currently auto-generated only for lexer state variants
    - **Impact**: Grammar lacks semantic documentation from original C code

### **Appendix: Function Pointer / Jump Table Detection**

- **Status**: ❌ NOT IMPLEMENTED
- **Expected**: Identify dispatch tables (builtin function tables) and add call edges
- **Evidence**:
    - No dispatch table analysis
    - No synthetic symbol generation for jumps
    - No `[jump_table]` annotation support
    - **Impact**: Incomplete call graph for table-driven dispatch patterns

### **Appendix: Inline Parsing Pattern Detection**

- **Status**: ❌ NOT IMPLEMENTED
- **Expected**: Find direct token matching within function bodies
- **Evidence**:
    - No inline pattern detection
    - No synthetic rule generation for inline parsing
    - Only delegates to other functions (no inline pattern synthesis)
    - **Impact**: Missing rules for inline parsing behavior

---

## Verification Methodology

| Item      | Evidence Method                                                | Result                             |
| --------- | -------------------------------------------------------------- | ---------------------------------- |
| Phase 1   | `_extract_parser_functions()` + grammar rule count             | ✅ 31/31 rules                     |
| Phase 2   | `_build_call_graph()` + function analysis logs                 | ✅ 1165 functions                  |
| Phase 3   | Grammar rule generation + source traceability                  | ✅ All rules have source info      |
| Phase 2.3 | `_detect_cycles()` output + call graph structure               | ✅ 50+ cycles detected             |
| Phase 4.3 | JQ query for variant nodes + `_embed_lexer_state_conditions()` | ✅ 20 functions, variants embedded |
| Phase 5.2 | `_validate_schema()` + jsonschema pass                         | ✅ Schema validation passed        |
| Phase 3.3 | JQ count of optional/repeat nodes + function search            | ❌ Zero found                      |
| Phase 5.3 | Grep for test files + test utilities                           | ❌ None found                      |

---

## Architecture Notes

- **Fully working pipeline**: Parse → Extract → Analyze → Generate → Validate
- **Strengths**: Cycle handling via refs, lexer state integration, comprehensive source tracking
- **Gaps**: No control flow analysis, no real-world validation, no reference validation layer
- **Biggest limitation**: Phase 3.3 would require AST visitor for control flow (while/if/switch analysis)

---

## Recommendations for Next Steps

1. **High Priority**: Implement Phase 3.3 (control flow analysis) to properly classify Optional/Repeat
2. **High Priority**: Implement Phase 5.3 (real-world testing) against zsh test suite
3. **Medium**: Add Phase 3.2 (reference validation) as a post-generation check
4. **Medium**: Implement Phase 5.4 (provenance) to enable safe regeneration with manual edits
5. **Low**: Appendix items (doc extraction, jump tables, inline patterns) for completeness
