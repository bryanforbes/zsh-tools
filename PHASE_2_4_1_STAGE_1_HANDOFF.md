# Stage 1 → Stage 2 Handoff Guide

**Prepared for**: Stage 2 Agent (Token & Call Sequence Extraction)  
**Date**: Nov 18, 2025  
**Status**: ✅ Ready

---

## What You're Receiving

### Core Extraction Module

**File**: `zsh-grammar/src/zsh_grammar/branch_extractor.py` (282 lines)

```python
def extract_control_flow_branches(
    cursor: Cursor, func_name: str = ''
) -> list[ControlFlowBranch]
```

**Returns**: List of branches with this structure:

```python
ControlFlowBranch = {
    'branch_id': str,              # 'if_1', 'else_if_1', 'loop', etc.
    'branch_type': str,            # 'if' | 'else_if' | 'else' | 'switch_case' | 'loop' | 'sequential'
    'condition': str | None,       # 'tok == INPAR' (for conditional branches)
    'token_condition': str | None, # 'INPAR' (semantic token)
    'start_line': int,             # First line of branch in AST
    'end_line': int,               # Last line of branch in AST
    'items': list,                 # ✅ EMPTY - your job to populate!
}
```

### Test Fixtures

**File**: `zsh-grammar/tests/conftest.py` (150 lines)

Pytest fixtures ready to use:

```python
# Session-scoped (loaded once per test run)
@pytest.fixture(scope='session')
def parse_c_ast() -> TranslationUnit
    """Parsed parse.c AST"""

@pytest.fixture(scope='session')
def parser_functions_ast() -> dict[str, Cursor]
    """Dict of all parser functions: {'par_if': Cursor, ...}"""

# Function-scoped (fresh cursor per test)
@pytest.fixture
def par_if(parser_functions_ast) -> Cursor
@pytest.fixture
def par_case(parser_functions_ast) -> Cursor
@pytest.fixture
def par_while(parser_functions_ast) -> Cursor
# ... and 4 more
```

### Existing Test Suite

**File**: `zsh-grammar/tests/test_branch_extractor.py` (445 lines)

- 34 tests already passing
- All tests use fixtures above
- Ready for Stage 2 tests to add to this file

### Documentation

1. **PHASE_2_4_1_STAGE_1_FINAL_SUMMARY.md**: Overall Stage 1 overview
2. **PHASE_2_4_1_STAGE_1_3_REPORT.md**: Detailed AST testing results
3. **PHASE_2_4_1_STAGE_1_3_COMPLETION.md**: Technical implementation details
4. **PHASE_2_4_1_REDESIGN_PLAN.md**: Stage 2 specification (see sections 2.1-2.3)
5. **PHASE_2_4_1_QUICK_REFERENCE.md**: Workflow guide

---

## What You Need to Build

### Stage 2 Tasks

#### 2.1: Extract Tokens and Calls for Each Branch

**Input**: One ControlFlowBranch with start_line/end_line

**Output**: Populate branch['items'] with ordered sequence

```python
def extract_tokens_and_calls_for_branch(
    cursor: Cursor,
    branch: ControlFlowBranch,
    func_name: str,
) -> list[TokenOrCallEnhanced]:
    """
    Extract tokens and function calls in order for a specific branch.

    Example output:
    [
        {'kind': 'token', 'token_name': 'INPAR', 'line': 1631,
         'is_negated': False, 'branch_id': 'if_1', 'sequence_index': 0},
        {'kind': 'call', 'func_name': 'par_list', 'line': 1635,
         'branch_id': 'if_1', 'sequence_index': 1},
        {'kind': 'token', 'token_name': 'OUTPAR', 'line': 1650,
         'is_negated': False, 'branch_id': 'if_1', 'sequence_index': 2},
    ]
    """
```

**Algorithm**:

1. Walk AST nodes in branch's line range (start_line to end_line)
2. Identify token checks: `tok == TOKEN_NAME` or `tok != TOKEN_NAME`
3. Identify function calls: `par_*()` or `parse_*()`
4. Sort by line number to preserve execution order
5. Assign sequence_index (0, 1, 2, ..., n-1)
6. Set branch_id to match branch

**Subtasks**:

- Extract tokens from binary operators (==, !=)
- Extract function calls from call expressions
- Filter error guards (`YYERROR` patterns)
- Handle negation (`tok !=`)

#### 2.2: Handle String Matching as Synthetic Tokens

**Pattern**: `tok == STRING && !strcmp(tokstr, "always")`

**Convert to**: Synthetic token `ALWAYS`

```python
def extract_synthetic_tokens_for_branch(
    cursor: Cursor,
    branch: ControlFlowBranch,
) -> list[SyntheticTokenEnhanced]:
    """
    Extract synthetic tokens from string matching conditions.

    Example:
    Input: tok == STRING && !strcmp(tokstr, "always")
    Output: SyntheticTokenEnhanced = {
        'kind': 'synthetic_token',
        'token_name': 'ALWAYS',
        'line': 1632,
        'condition': 'tok == STRING && strcmp(tokstr, "always")',
        'branch_id': 'if_1',
        'sequence_index': -1,  # Will be reindexed
        'is_optional': False,  # Depends on enclosing if structure
    }
    """
```

**Algorithm**:

1. Find compound conditions with `strcmp(tokstr, "value")`
2. Extract string value (e.g., "always" → ALWAYS)
3. Create synthetic token with uppercase name
4. Determine `is_optional` based on enclosing if (has else or not)
5. Store line number and original condition for traceability

#### 2.3: Merge Branch Items with Sequence Indices

**Input**: Tokens + calls + synthetics (all with sequence_index = -1)

**Output**: Single ordered list with correct indices (0, 1, 2, ...)

```python
def merge_branch_items(
    tokens: list[TokenOrCallEnhanced],
    synthetics: list[SyntheticTokenEnhanced],
) -> list[TokenOrCallEnhanced]:
    """
    Merge tokens, calls, and synthetics into unified sequence.

    Steps:
    1. Combine all items
    2. Sort by line number
    3. Re-assign sequence_index (0, 1, 2, ..., n-1)
    4. Validate line monotonicity
    5. Return merged list
    """
```

---

## How to Test Your Work

### Unit Tests

Add tests to `zsh-grammar/tests/test_branch_extractor.py`:

```python
def test_extract_tokens_and_calls_sequential(self, par_subsh: Cursor) -> None:
    """Extract ordered tokens from simple function."""
    branches = extract_control_flow_branches(par_subsh, 'par_subsh')

    # Call Stage 2 function on first branch
    items = extract_tokens_and_calls_for_branch(par_subsh, branches[0], 'par_subsh')

    # Validate structure
    assert len(items) >= 3
    assert items[0]['kind'] == 'token'
    assert items[0]['token_name'] == 'INPAR'
    assert items[0]['sequence_index'] == 0
```

### Integration Tests

```python
def test_extract_tokens_preserves_order(self, par_if: Cursor) -> None:
    """Tokens should be sorted by line number."""
    branches = extract_control_flow_branches(par_if, 'par_if')

    for branch in branches:
        items = extract_tokens_and_calls_for_branch(par_if, branch, 'par_if')
        lines = [item['line'] for item in items]
        assert lines == sorted(lines), f"Non-monotonic lines: {lines}"
```

### Validation

```bash
# Run all tests
mise run //:test

# Run just Stage 2 tests
mise run //:test -- zsh-grammar/tests/test_branch_extractor.py::TestTokenExtraction -v

# Check code quality
mise //:ruff zsh-grammar/src/zsh_grammar/token_extractors.py
mise //:basedpyright zsh-grammar/src/zsh_grammar/token_extractors.py
mise //:ruff-format zsh-grammar/src/zsh_grammar/token_extractors.py
```

---

## Key Files to Understand

### Stage 1 Implementation

1. **branch_extractor.py**: Main extraction logic
    - Read: All 7 helper functions
    - Understand: How branches are identified and structured

2. **conftest.py**: Test fixtures
    - Use: For all your Stage 2 tests
    - Reference: When adding new test functions

3. **\_types.py**: Type definitions
    - Study: `ControlFlowBranch`, `TokenOrCallEnhanced`, `SyntheticTokenEnhanced`
    - Reference: For TypedDict structures

4. **token_sequence_validators.py**: Validation framework
    - Use: To validate your extracted sequences
    - Study: What constraints must be satisfied

### Reference Documentation

1. **PHASE_2_4_1_REDESIGN_PLAN.md**: Detailed specs for Stage 2 (sections 2.1-2.3)
2. **PHASE_2_4_1_STAGE_1_FINAL_SUMMARY.md**: Overview and context
3. **PHASE_2_4_1_QUICK_REFERENCE.md**: Workflow tips and patterns

---

## Environment Setup

### Clang Library Path

Set environment variable before running tests:

```bash
export LIBCLANG_PREFIX=/opt/homebrew/opt/llvm
# or for Linux:
export LIBCLANG_PREFIX=/usr/lib/llvm-15
```

### Running Tests

```bash
# Install dependencies (if needed)
mise run dev

# Run all tests
mise run //:test

# Run with coverage
mise run //:test -- --cov=zsh_grammar

# Run specific test class
mise run //:test -- zsh-grammar/tests/test_branch_extractor.py::YourTestClass -v
```

---

## What's Already Tested

✅ **From Stage 1.3**:

- Branch extraction on par_if, par_case, par_while, par_for, par_subsh, par_simple, par_cond
- Control flow identification (if/else/switch/loop/sequential)
- Condition string extraction
- Semantic token identification
- Line number ranges
- Empty items initialization

❌ **NOT yet done (your job)**:

- Token extraction from AST
- Function call identification in execution order
- Synthetic token generation from string matching
- Sequence index assignment
- Merging and validation

---

## Success Criteria

For Stage 2 to be complete:

✅ All tokens extracted in execution order (sorted by line number)  
✅ Function calls identified and included in sequences  
✅ Sequence indices contiguous (0, 1, 2, ..., n-1)  
✅ Branch IDs consistent within each branch  
✅ Synthetic tokens generated from strcmp patterns  
✅ All tests passing (existing + new)  
✅ 0 lint errors, 0 type errors  
✅ Code formatted per project standards

---

## Questions & Common Patterns

### Q: How do I find tokens in the AST?

Look for binary operators checking `tok == TOKEN_NAME`:

```python
for node in cursor.walk_preorder():
    if node.kind == CursorKind.BINARY_OPERATOR:
        tokens = list(node.get_tokens())
        # tokens[0] = 'tok'
        # tokens[1] = '==' or '!='
        # tokens[2] = 'TOKEN_NAME'
```

### Q: How do I identify function calls?

Look for call expressions within the branch:

```python
for node in cursor.walk_preorder():
    if node.kind == CursorKind.CALL_EXPR:
        # node.spelling gives function name
        if node.spelling.startswith(('par_', 'parse_')):
            # This is a parser function call
```

### Q: How do I distinguish error guards?

Error guards have this pattern: `if (tok != EXPECTED) YYERROR(...)`

Filter them out:

```python
def _is_error_guard(node: Cursor) -> bool:
    """Check if token check is an error guard (not semantic)."""
    # Look for YYERROR/YYERRORV in following tokens
    for check_node in node.get_parent().walk_preorder():
        tokens = [t.spelling for t in check_node.get_tokens()]
        if 'YYERROR' in tokens:
            return True
    return False
```

### Q: How do I handle negation (`tok !=`)?

Store `is_negated: bool` in TokenCheck:

```python
token_check = {
    'kind': 'token',
    'token_name': 'INPAR',
    'line': 100,
    'is_negated': False,  # or True if tok !=
    'branch_id': 'if_1',
    'sequence_index': 0,
}
```

---

## Files You'll Likely Modify

1. **zsh_grammar/token_extractors.py** (173 lines, currently unused)
    - Add `extract_tokens_and_calls_for_branch()`
    - Add `extract_synthetic_tokens_for_branch()`
    - Add `merge_branch_items()`
    - Add helper functions for token/call identification

2. **zsh_grammar/tests/test_branch_extractor.py** (445 lines)
    - Add TestTokenExtraction class with tests
    - Add test methods for synthetic tokens
    - Add tests for merging and reindexing

3. **zsh_grammar/tests/test_token_sequence_extraction.py** (174 lines)
    - May need to update placeholder tests to use Stage 2 functions

---

## Handoff Checklist

- [x] Read PHASE_2_4_1_STAGE_1_FINAL_SUMMARY.md
- [x] Read PHASE_2_4_1_REDESIGN_PLAN.md (Stage 2 sections)
- [x] Understand branch_extractor.py module
- [x] Review conftest.py fixtures
- [x] Study \_types.py type definitions
- [x] Review existing tests in test_branch_extractor.py
- [x] Set up LIBCLANG_PREFIX environment variable
- [x] Run `mise run //:test` to verify baseline

---

## Next Steps

1. **Understand the problem**: Read PHASE_2_4_1_REDESIGN_PLAN.md Stage 2 sections carefully
2. **Design your solution**: Before coding, outline the algorithm for token extraction
3. **Implement token extraction**: Start with basic `tok == TOKEN_NAME` patterns
4. **Implement function calls**: Add support for `par_*()` and `parse_*()`
5. **Handle edge cases**: Error guards, negation, complex conditions
6. **Add synthetic tokens**: Implement strcmp pattern detection
7. **Merge and validate**: Implement sequence merging and index assignment
8. **Test thoroughly**: Write tests for each function and edge case
9. **Code quality**: Format, lint, type-check, then commit

**Estimated effort**: 2-3 sprints  
**Testing framework**: Ready (conftest.py + fixtures)  
**Support**: See PHASE_2_4_1_QUICK_REFERENCE.md for patterns and tips

---

## Good Luck!

You're continuing work that builds on a solid foundation. Stage 1 provides clean branch extraction and verified AST traversal. Your job is to populate the items for each branch with ordered token and call sequences.

**Ready?** Let's extract some tokens!
