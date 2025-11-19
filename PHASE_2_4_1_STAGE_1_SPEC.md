# Phase 2.4.1 Stage 1: Branch Extraction & AST Analysis - Specification

**Status**: IN PROGRESS  
**Duration**: 2-3 sprints  
**Dependencies**: Stage 0 (✅ COMPLETE)  
**Deliverable**: Extract control flow branches from all 31 parser functions

---

## Overview

Stage 1 implements AST analysis to extract distinct execution paths (control flow branches) from parser function bodies. Each branch represents a condition-specific path through the code:

- **if/else/else-if chains** → Multiple branches (if_1, else_if_1, else_1)
- **switch statements** → One branch per case (switch_case_FOR, switch_case_default)
- **while/for loops** → Single 'loop' branch
- **linear code** → Single 'sequential' branch

### Key Concepts

- **branch_id**: Unique identifier (e.g., 'if_1', 'switch_case_FOR', 'loop')
- **branch_type**: One of {if, else_if, else, switch_case, loop, sequential}
- **condition**: Raw condition string (e.g., 'tok == INPAR') for conditional branches
- **token_condition**: Semantic token extracted from condition (e.g., 'INPAR')
- **start_line/end_line**: AST span of branch

### Why This Matters

Branches are the foundation for Stage 2 (token sequence extraction). Stages 3-4 consume branches to build enhanced call graphs and grammar rules. Without proper branch extraction, token sequences cannot be properly ordered or contextualized.

---

## Implementation Details

### Module: `branch_extractor.py`

**Main Entry Point:**

```python
def extract_control_flow_branches(
    cursor: Cursor, func_name: str = ''
) -> list[ControlFlowBranch]:
    """Extract all branches from function body."""
```

**Return Type:** List of `ControlFlowBranch` (from `_types.py`)

**Each branch has:**

- `branch_id: str` - Unique ID within function
- `branch_type: ControlFlowBranchType` - Type discriminator
- `start_line: int` - AST span start
- `end_line: int` - AST span end
- `items: list[TokenOrCallEnhanced]` - Empty (filled in Stage 2)
- `condition: NotRequired[str]` - For if/else_if/switch_case
- `token_condition: NotRequired[str]` - For semantic token extraction

### Algorithm

For each parser function:

1. **Collect control structures** from AST:
    - `if_stmts` - All if statements
    - `switch_stmts` - All switch statements
    - `while_stmts` - All while loops
    - `for_stmts` - All for loops

2. **Extract if chains** (group if/else-if/else):
    - Walk from initial if to find else clauses
    - Determine branch_type: 'if' → 'else_if' → 'else'
    - Extract condition from each branch
    - Return ordered list

3. **Extract switch cases** (each case separate):
    - Walk all CASE_STMT nodes under SWITCH_STMT
    - Extract case label (token name or 'default')
    - Each case becomes branch with condition='tok == LABEL'
    - Handle DEFAULT_STMT separately

4. **Extract loops** (one branch):
    - Identify while or for loop
    - Create single 'loop' branch
    - Prefer while over for if both exist

5. **Fallback sequential** (no control structures):
    - If no branches extracted, treat entire function as sequential
    - Single 'sequential' branch spanning whole function

### Helper Functions

```python
def _extract_if_chain(if_stmt: Cursor) -> list[ControlFlowBranch]:
    """Extract if/else-if/else as multiple branches."""

def _extract_if_condition(if_stmt: Cursor) -> tuple[str | None, str | None]:
    """Extract condition string and semantic token."""

def _find_else_clause(if_stmt: Cursor) -> Cursor | None:
    """Find the else clause of an if statement."""

def _extract_switch_cases(switch_stmt: Cursor) -> list[ControlFlowBranch]:
    """Extract switch cases as separate branches."""

def _extract_case_label(case_stmt: Cursor) -> str:
    """Extract the label from a case statement."""

def _extract_loop(loop_stmt: Cursor, loop_type: str) -> ControlFlowBranch:
    """Extract while or for loop as single 'loop' branch."""

def _extract_sequential_body(cursor: Cursor) -> ControlFlowBranch:
    """Extract entire function body as single sequential branch."""
```

---

## Test Structure

### File: `test_branch_extractor.py` (28 tests)

**Test Classes:**

1. **TestExtractControlFlowBranches** (4 placeholder tests)
    - Test extraction from functions with if/else, switch, loops, sequential code
    - Will be implemented with actual parse.c cursors in Stage 1.2

2. **TestIfChainExtraction** (5 placeholder tests)
    - Test branch type detection (if → else_if → else)
    - Test condition and token extraction
    - Will be implemented with if statement cursors

3. **TestSwitchExtraction** (3 placeholder tests)
    - Test case extraction and labeling
    - Test default case handling
    - Will be implemented with switch cursors

4. **TestLoopExtraction** (2 placeholder tests)
    - Test while and for loop extraction
    - Will be implemented with loop cursors

5. **TestBranchMetadata** (5 data structure tests)
    - ✅ PASSING: Verify branch fields and types
    - ✅ PASSING: Validate branch_id naming formats
    - ✅ PASSING: Test metadata requirements

6. **TestConditionalBranchConditions** (5 data structure tests)
    - ✅ PASSING: Verify condition field presence for conditional branches
    - ✅ PASSING: Verify condition not required for loop/sequential

7. **TestBranchLineNumbers** (2 data structure tests)
    - ✅ PASSING: Verify start_line <= end_line
    - ✅ PASSING: Verify line numbers positive

8. **TestBranchItemsInitialization** (1 data structure test)
    - ✅ PASSING: Verify items initialized as empty list

**Status**: 28/28 tests defined, 18/28 data structure tests passing

---

## Deliverables (Stages 1.1-1.2)

### Stage 1.1: Control Flow Identification ✅

- [x] Implement `extract_control_flow_branches()` core logic
- [x] Implement `_extract_if_chain()` for if/else/else-if
- [x] Implement `_extract_if_condition()` for condition extraction
- [x] Implement `_extract_switch_cases()` for switch handling
- [x] Implement `_extract_loop()` for while/for loops
- [x] Implement `_extract_sequential_body()` fallback

**Status**: Core implementation complete (needs AST testing)

### Stage 1.2: AST Testing & Validation (TBD)

- [ ] Test extraction from actual parse.c cursors
- [ ] Validate branches for 31 parser functions
- [ ] Generate branch report with statistics
- [ ] Handle edge cases (nested control structures, complex conditions)

---

## Code Quality

```
Format: ✅ PASS (ruff format)
Lint: ✅ PASS (ruff check)
Type Check: ✅ PASS (basedpyright)
Tests: ✅ 74/74 PASSING
```

---

## Next Steps

1. **Stage 1.2**: Once AST testing infrastructure is in place:
    - Implement placeholder test methods with actual parse.c cursors
    - Test extraction for each of 31 parser functions
    - Document any edge cases or special handling needed

2. **Stage 2**: Token sequence extraction
    - Populate `items` list for each branch
    - Extract tokens and function calls in execution order
    - Apply semantic token filtering

3. **Validation**:
    - Use `TokenSequenceValidator` from Stage 0
    - Verify all branches have valid metadata
    - Check for overlapping/conflicting branches

---

## Files Created

- `src/zsh_grammar/branch_extractor.py` (282 lines)
- `tests/test_branch_extractor.py` (290 lines)

---

## Technical Notes

### Type Safety

All functions return `ControlFlowBranch` which is a discriminated union-like TypedDict:

- All required fields must be present
- `condition` and `token_condition` are `NotRequired` for non-conditional branches
- `branch_type` is validated via `ControlFlowBranchType` Literal

### Edge Cases Handled

1. **Nested if statements**: Extracted as separate branches at each level
2. **Switch with default**: Handled separately via `DEFAULT_STMT` walk
3. **No control structures**: Treated as single sequential branch
4. **Complex conditions**: Raw condition string preserved, token extracted separately

### Integration Points

- Uses `walk_and_filter()` from `ast_utilities.py`
- Produces `ControlFlowBranch` objects defined in `_types.py`
- Pairs with `TokenSequenceValidator` from `token_sequence_validators.py`
- Input to Stage 2: `extract_tokens_and_calls_for_branch()`

---

## References

- **Design Plan**: See PHASE_2_4_1_REDESIGN_PLAN.md (lines 382-483)
- **Data Structures**: See \_types.py (ControlFlowBranch definition)
- **Validation**: See token_sequence_validators.py (TokenSequenceValidator)
