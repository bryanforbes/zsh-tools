# Phase 2.4.1 Redesign Plan: Token-Sequence-Based Grammar Extraction

## Executive Summary

Phase 2.4.1 redesigns the grammar extraction architecture from function-centric (call graphs) to token-sequence-centric (ordered token+call sequences). This enables reconstruction of semantic grammar comments from parse.c and properly models token-based control flow.

**Critical Facts:**

- Current extraction is fundamentally broken: cannot reconstruct "INPAR list OUTPAR | INBRACE list OUTBRACE" patterns
- Token extraction infrastructure exists but is unused dead code
- Redesign requires ~40-60% rewrite of extraction logic (not incremental enhancement)
- Estimated effort: 8-12 sprints of focused work
- Can be parallelized across 3-4 independent sub-agents

**Success Criteria:**

- ✓ par_subsh rule: `Union[Sequence[INPAR, list, OUTPAR], Sequence[INBRACE, list, OUTBRACE, ...]]`
- ✓ Grammar comments from parse.c reconstructed in ≥80% of functions
- ✓ Call graph validation confirms all extracted functions are called
- ✓ Schema validation passes; no breaking changes to grammar output format

---

## Architecture Overview

### Current State (Function-Centric)

```
parse.c (semantic grammar comments)
    ↓
AST → Call Graph {func: [calls]} → Grammar Rules {rule: {'$ref': called_func}}
    ↑
Lost: Token sequences, branch ordering, string matching conditions
```

**Problem:** Rules don't capture tokens surrounding function calls.

### Target State (Token-Sequence-Centric)

```
parse.c (semantic grammar comments)
    ↓
AST → Token Sequences {func: [[TokenOrCall], [TokenOrCall], ...]}
    → Branch Analysis {if/else/switch alternatives}
    → Control Flow Patterns {optional, repeat}
    ↓
Grammar Rules {rule: Sequence|Union|Optional|Repeat with tokens}
    ↓
Validation {call graph confirms semantic structure}
```

**Benefit:** Rules capture complete token+call pattern; can reconstruct semantic grammar.

---

## Phase Breakdown (Implementation Stages)

### Stage 0: Data Structure Redesign & Validation Framework

**Agent Role**: Data architect + Test setup  
**Duration**: 1-2 sprints  
**Dependencies**: None  
**Deliverable**: Type definitions, test harness

#### 0.1: Define Enhanced TypedDict Structures

**Current Issues:**

- `TokenEdge`: Records isolated tokens, loses branch/sequence context
- `FunctionNode`: Has `token_edges` but `_build_grammar_rules()` ignores it
- No representation for ordered sequences with control flow context

**New Data Structures:**

```python
# In _types.py, replace/enhance existing types:

class TokenCheckEnhanced(TypedDict):
    """Token check in ordered sequence with branch context."""
    kind: Literal['token']
    token_name: str
    line: int
    is_negated: bool
    branch_id: str  # NEW: identifies which control flow branch
    sequence_index: int  # NEW: position in ordered sequence

class FunctionCallEnhanced(TypedDict):
    """Function call in sequence."""
    kind: Literal['call']
    func_name: str
    line: int
    branch_id: str  # NEW
    sequence_index: int  # NEW

class SyntheticTokenEnhanced(TypedDict):
    """Synthetic token from string matching."""
    kind: Literal['synthetic_token']
    token_name: str
    line: int
    condition: str
    branch_id: str  # NEW
    sequence_index: int  # NEW
    is_optional: bool  # NEW: controls whether to wrap in Optional

# Ordered sequence: mix of tokens and calls
type TokenOrCallEnhanced = TokenCheckEnhanced | FunctionCallEnhanced | SyntheticTokenEnhanced

class ControlFlowBranch(TypedDict):
    """Represents one alternative (if branch, switch case, loop body, etc.)."""
    branch_id: str  # e.g., 'if_1', 'else_if_2', 'switch_case_3', 'loop'
    branch_type: Literal['if', 'else_if', 'else', 'switch_case', 'loop', 'sequential']
    condition: NotRequired[str]  # e.g., 'tok == INPAR' for if branch
    token_condition: NotRequired[str]  # NEW: semantic token check if applicable
    start_line: int
    end_line: int
    items: list[TokenOrCallEnhanced]  # Ordered sequence for this branch

class FunctionNodeEnhanced(TypedDict):
    """Enhanced function node with token-sequence metadata."""
    name: str
    file: str
    line: int
    calls: list[str]  # Kept for validation; primary input is token_sequences

    # Phase 2.4.1: Token sequence data (NEW)
    token_sequences: list[ControlFlowBranch]  # Multiple branches
    has_loops: bool  # while/for detected
    loop_type: NotRequired[str]  # 'while', 'for', or None
    is_optional: bool  # if statement without else

    # Existing fields (kept for compatibility)
    conditions: NotRequired[list[str]]
    signature: NotRequired[str]
    visibility: NotRequired[str]
```

**Validation Checkpoints:**

- ✓ All new fields have clear type definitions
- ✓ `TokenOrCallEnhanced` is valid discriminated union
- ✓ `ControlFlowBranch` accurately represents AST branches
- ✓ No breaking changes to output schema (old fields preserved)

**Test Cases:**

```python
# Tests in zsh_grammar/tests/test_data_structures.py
def test_token_check_enhanced():
    """Validate TokenCheckEnhanced structure."""
    item: TokenCheckEnhanced = {
        'kind': 'token',
        'token_name': 'INPAR',
        'line': 1234,
        'is_negated': False,
        'branch_id': 'if_1',
        'sequence_index': 0,
    }
    assert item['kind'] == 'token'
    assert item['branch_id'] == 'if_1'

def test_control_flow_branch():
    """Validate ControlFlowBranch structure."""
    branch: ControlFlowBranch = {
        'branch_id': 'if_1',
        'branch_type': 'if',
        'condition': 'tok == INPAR',
        'token_condition': 'INPAR',
        'start_line': 100,
        'end_line': 150,
        'items': [
            {'kind': 'token', 'token_name': 'INPAR', 'line': 101, 'is_negated': False,
             'branch_id': 'if_1', 'sequence_index': 0},
            {'kind': 'call', 'func_name': 'par_list', 'line': 102, 'branch_id': 'if_1',
             'sequence_index': 1},
            {'kind': 'token', 'token_name': 'OUTPAR', 'line': 150, 'is_negated': False,
             'branch_id': 'if_1', 'sequence_index': 2},
        ]
    }
    assert branch['branch_type'] == 'if'
    assert len(branch['items']) == 3
```

**Output Artifact:** `append to `\_types.py`

---

#### 0.2: Create Token Sequence Extraction Test Harness

**Purpose**: Establish expected input/output examples from parse.c before implementing extraction

**Test Functions to Model:**

1. **par_subsh** (high complexity: two token-based branches)

    ```
    Semantic grammar: INPAR list OUTPAR | INBRACE list OUTBRACE [ "always" ... ]
    Expected sequences:
    - Branch 1: [INPAR, call(par_list), OUTPAR, optional(ALWAYS, ...)]
    - Branch 2: [INBRACE, call(par_list), OUTBRACE, optional(ALWAYS, ...)]
    ```

2. **par_if** (conditional alternatives)

    ```
    Semantic grammar: IF cond THEN list ... | ... ELSE list ... | ... FI
    Expected: Multiple branches for IF/ELIF/ELSE, each with condition tokens and body calls
    ```

3. **par_case** (switch-like dispatch)

    ```
    Semantic grammar: CASE word { (pattern) list } ESAC
    Expected: Sequential (CASE, word, loop(pattern, list)) with loop model
    ```

4. **par_for** (loop with optional condition)
    ```
    Semantic grammar: FOR var ( { word } | '(' cond ';' cond ';' advance ')' ) DO list DONE
    Expected: Sequential with optional inner groups
    ```

**Test Cases:**

```python
# In zsh_grammar/tests/test_token_sequence_extraction.py

def test_par_subsh_token_sequences():
    """Test token sequence extraction for par_subsh."""
    # Mock AST from parse.c lines 1630-1665
    expected_branches = [
        {
            'branch_id': 'if_1',
            'branch_type': 'if',
            'token_condition': 'INPAR',
            'items': [
                {'kind': 'token', 'token_name': 'INPAR', ...},
                {'kind': 'call', 'func_name': 'par_list', ...},
                {'kind': 'token', 'token_name': 'OUTPAR', ...},
            ]
        },
        {
            'branch_id': 'else_if_1',
            'branch_type': 'else_if',
            'token_condition': 'INBRACE',
            'items': [
                {'kind': 'token', 'token_name': 'INBRACE', ...},
                {'kind': 'call', 'func_name': 'par_list', ...},
                {'kind': 'token', 'token_name': 'OUTBRACE', ...},
            ]
        }
    ]

    # After extraction, should produce:
    expected_rule = {
        'union': [
            {
                'sequence': [
                    {'$ref': 'INPAR'},
                    {'$ref': 'list'},
                    {'$ref': 'OUTPAR'},
                ]
            },
            {
                'sequence': [
                    {'$ref': 'INBRACE'},
                    {'$ref': 'list'},
                    {'$ref': 'OUTBRACE'},
                ]
            }
        ]
    }

    assert expected_rule['union'][0]['sequence'][0] == {'$ref': 'INPAR'}

def test_par_if_token_sequences():
    """Test token sequence extraction for par_if."""
    # IF has semantic tokens (IF, THEN, ELIF, ELSE, FI)
    # Each branch is a separate alternative
    pass

def test_par_case_token_sequences():
    """Test token sequence extraction for par_case."""
    # CASE token, then loop of (pattern) OUTPAR list DSEMI/SEMIAMP/SEMIBAR
    pass
```

**Output Artifact:** `zsh_grammar/tests/test_token_sequence_extraction.py`

---

#### 0.3: Establish Validation Framework

**Purpose**: Create tools to validate token sequences before feeding to rule generation

**Validators:**

```python
# In zsh_grammar/token_sequence_validators.py (NEW FILE)

class TokenSequenceValidator:
    """Validates extracted token sequences against constraints."""

    def validate_branch(self, branch: ControlFlowBranch) -> list[str]:
        """
        Check:
        1. All tokens exist in token_mapping
        2. All called functions exist in parser_functions
        3. Sequence indices are contiguous (0, 1, 2, ..., n)
        4. Line numbers are monotonic increasing
        5. Branch ID is unique within function
        """
        errors: list[str] = []

        # Check contiguity of sequence_index
        indices = sorted([item['sequence_index'] for item in branch['items']])
        expected = list(range(len(branch['items'])))
        if indices != expected:
            errors.append(f"Non-contiguous sequence indices: {indices}")

        # Check line monotonicity
        lines = [item['line'] for item in branch['items']]
        if lines != sorted(lines):
            errors.append(f"Non-monotonic lines: {lines}")

        return errors

    def validate_all_sequences(self,
        node: FunctionNodeEnhanced,
        token_mapping: dict[str, _TokenDef],
        parser_functions: dict[str, FunctionNode]
    ) -> dict[str, list[str]]:
        """Validate all branches for a function."""
        errors_by_branch: dict[str, list[str]] = {}

        for branch in node['token_sequences']:
            branch_errors = self.validate_branch(branch)

            for item in branch['items']:
                if item['kind'] == 'token':
                    if item['token_name'] not in token_mapping:
                        branch_errors.append(
                            f"Undefined token: {item['token_name']} at line {item['line']}"
                        )
                elif item['kind'] == 'call':
                    if item['func_name'] not in parser_functions:
                        branch_errors.append(
                            f"Undefined function: {item['func_name']} at line {item['line']}"
                        )

            if branch_errors:
                errors_by_branch[branch['branch_id']] = branch_errors

        return errors_by_branch
```

**Test Cases:**

```python
def test_validate_contiguous_indices():
    """Non-contiguous indices should error."""
    branch = {..., 'items': [
        {..., 'sequence_index': 0},
        {..., 'sequence_index': 2},  # Gap!
    ]}
    errors = validator.validate_branch(branch)
    assert 'Non-contiguous' in errors[0]

def test_validate_monotonic_lines():
    """Non-increasing line numbers should error."""
    branch = {..., 'items': [
        {..., 'line': 150},
        {..., 'line': 100},  # Decreasing!
    ]}
    errors = validator.validate_branch(branch)
    assert 'Non-monotonic' in errors[0]
```

**Output Artifact:** `zsh_grammar/token_sequence_validators.py`

---

### Stage 1: Branch Extraction & AST Analysis

**Agent Role**: AST analysis specialist  
**Duration**: 2-3 sprints  
**Dependencies**: Stage 0  
**Deliverable**: Extract all control flow branches from function bodies

#### 1.1: Identify Control Flow Branches in AST

**Purpose**: Walk function bodies and extract distinct execution paths (if/else/switch/loops)

**Algorithm:**

```
For each parser function:
  1. Get function cursor from AST
  2. Identify all control structures:
     - if/else/else-if chains (group into one unit)
     - switch statements (each case is separate branch)
     - while/for loops (one branch labeled 'loop')
     - linear code (one sequential branch)
  3. For each identified branch:
     - Record branch_id (e.g., 'if_1', 'else_if_2', 'switch_case_FOR')
     - Record condition (e.g., 'tok == INPAR' for if branches)
     - Record AST span (start_line, end_line)
     - Mark branch_type (if, else_if, else, switch_case, loop, sequential)
  4. Return list of ControlFlowBranch stubs (without items yet)
```

**Implementation Pseudocode:**

```python
def extract_control_flow_branches(cursor: Cursor, func_name: str) -> list[ControlFlowBranch]:
    """
    Extract control flow branches from function body.

    Returns branches with metadata but without token/call items (those come in Stage 2).
    """
    branches: list[ControlFlowBranch] = []

    # Collect all control structures
    for node in cursor.walk_preorder():
        if node.kind == CursorKind.IF_STMT:
            # Extract if/else-if/else chain
            if_branches = _extract_if_chain(node)
            branches.extend(if_branches)

        elif node.kind == CursorKind.SWITCH_STMT:
            # Extract switch cases
            switch_branches = _extract_switch_cases(node)
            branches.extend(switch_branches)

        elif node.kind == CursorKind.WHILE_STMT or node.kind == CursorKind.FOR_STMT:
            # Extract loop as single branch
            loop_branch = _extract_loop(node)
            branches.append(loop_branch)

    # If no control structures, treat entire function body as sequential
    if not branches:
        branches = [_extract_sequential_body(cursor)]

    return branches

def _extract_if_chain(if_stmt: Cursor) -> list[ControlFlowBranch]:
    """Extract if/else-if/else as multiple branches."""
    branches: list[ControlFlowBranch] = []
    counter = 0

    current = if_stmt
    while current:
        tokens = list(current.get_tokens())
        token_spellings = [t.spelling for t in tokens]

        if 'if' in token_spellings:
            branch_type = 'if'
            branch_id = f'if_{counter}'
        elif 'else' in token_spellings and 'if' in token_spellings:
            branch_type = 'else_if'
            branch_id = f'else_if_{counter}'
        elif 'else' in token_spellings:
            branch_type = 'else'
            branch_id = f'else_{counter}'
        else:
            break

        condition = _extract_if_condition(current)  # Extract 'tok == INPAR' etc

        branches.append({
            'branch_id': branch_id,
            'branch_type': branch_type,
            'condition': condition,
            'start_line': current.extent.start.line,
            'end_line': current.extent.end.line,
            'items': [],  # Filled in Stage 2
        })

        # Move to next else-if/else
        current = _find_else_clause(current)
        counter += 1

    return branches

def _extract_switch_cases(switch_stmt: Cursor) -> list[ControlFlowBranch]:
    """Extract switch cases as separate branches."""
    branches: list[ControlFlowBranch] = []

    for case_stmt in walk_and_filter(switch_stmt, CursorKind.CASE_STMT):
        # Each case is one branch
        case_label = _extract_case_label(case_stmt)  # e.g., 'FOR', 'WHILE', 'default'

        branches.append({
            'branch_id': f'switch_case_{case_label}',
            'branch_type': 'switch_case',
            'condition': f'tok == {case_label}' if case_label != 'default' else 'default',
            'token_condition': case_label,
            'start_line': case_stmt.extent.start.line,
            'end_line': case_stmt.extent.end.line,
            'items': [],
        })

    return branches

def _extract_loop(loop_stmt: Cursor) -> ControlFlowBranch:
    """Extract loop (while/for) as single branch."""
    loop_type = 'while' if loop_stmt.kind == CursorKind.WHILE_STMT else 'for'

    return {
        'branch_id': 'loop',
        'branch_type': 'loop',
        'start_line': loop_stmt.extent.start.line,
        'end_line': loop_stmt.extent.end.line,
        'items': [],  # Body filled in Stage 2
    }

def _extract_sequential_body(cursor: Cursor) -> ControlFlowBranch:
    """Treat entire function body as sequential (no control structures)."""
    body = _find_child_cursors(cursor, lambda c: c.kind == CursorKind.COMPOUND_STMT)

    return {
        'branch_id': 'sequential',
        'branch_type': 'sequential',
        'start_line': cursor.extent.start.line,
        'end_line': cursor.extent.end.line,
        'items': [],
    }
```

**Validation Checkpoints:**

- ✓ Every function has ≥1 branch
- ✓ Branch IDs are unique within function (no duplicates)
- ✓ Line ranges don't overlap (except nested control structures)
- ✓ All branches have required fields (branch_id, branch_type, start_line, end_line)

**Test Cases:**

```python
def test_extract_if_else_chain():
    """Extract if/else-if/else as three branches."""
    cursor = parse_c_function('par_if')
    branches = extract_control_flow_branches(cursor, 'par_if')

    # Should have if, else-if, else branches
    assert len(branches) >= 3
    assert branches[0]['branch_type'] == 'if'
    assert branches[1]['branch_type'] == 'else_if'
    assert branches[2]['branch_type'] == 'else'

def test_extract_switch_cases():
    """Extract switch cases as separate branches."""
    cursor = parse_c_function('par_cmd')
    branches = extract_control_flow_branches(cursor, 'par_cmd')

    # Each case should be separate branch
    switch_branches = [b for b in branches if b['branch_type'] == 'switch_case']
    assert len(switch_branches) >= 8  # FOR, WHILE, CASE, etc.

def test_extract_loop():
    """Extract loop body as branch."""
    cursor = parse_c_function('par_list')
    branches = extract_control_flow_branches(cursor, 'par_list')

    loop_branches = [b for b in branches if b['branch_type'] == 'loop']
    assert len(loop_branches) >= 1
```

**Output Artifact:** `zsh_grammar/branch_extractor.py` (NEW FILE)

---

#### 1.2: Extract Condition Information from Branches

**Purpose**: Parse if conditions to extract token checks (e.g., "tok == INPAR")

**Algorithm:**

For each if/switch branch:

1. Extract tokens from condition expression
2. Identify token-based dispatch: `tok == TOKEN` or `tok != TOKEN`
3. Extract sentinel value: TOKEN from condition
4. Mark negation: `!=` means negated check
5. Store as `token_condition` field

**Implementation:**

```python
def extract_branch_conditions(branch: ControlFlowBranch, cursor: Cursor) -> ControlFlowBranch:
    """
    Enhance branch with extracted condition information.

    For if branches: extract 'tok == TOKEN' patterns
    For switch branches: extract case label
    """
    if branch['branch_type'] in ('if', 'else_if'):
        condition_str = _extract_if_condition_string(cursor)
        # Example: "tok == INPAR" or "otok == INBRACE && tok == STRING"

        tokens = condition_str.split()

        # Look for token patterns: tok == TOKEN or tok != TOKEN
        for i, token in enumerate(tokens):
            if token == 'tok' and i + 2 < len(tokens):
                op = tokens[i + 1]
                token_name = tokens[i + 2]
                if op in ('==', '!=') and token_name.isupper():
                    branch['token_condition'] = token_name
                    branch['condition'] = condition_str
                    if op == '!=':
                        branch['is_negated'] = True
                    break

    elif branch['branch_type'] == 'switch_case':
        # Already extracted in Stage 1.1
        pass

    return branch
```

**Test Cases:**

```python
def test_extract_if_token_condition():
    """Extract 'tok == INPAR' from if condition."""
    condition = "tok == INPAR"
    token_cond = _extract_token_condition(condition)
    assert token_cond == 'INPAR'

def test_extract_negated_condition():
    """Extract 'tok != OUTPAR' as negated."""
    condition = "tok != OUTPAR"
    token_cond = _extract_token_condition(condition)
    assert token_cond == 'OUTPAR'
    # is_negated should be True
```

**Output Artifact:** Enhanced branch extraction in `branch_extractor.py`

---

### Stage 2: Token & Call Extraction Within Branches

**Agent Role**: Token extraction specialist  
**Duration**: 2-3 sprints  
**Dependencies**: Stage 0, Stage 1  
**Deliverable**: Ordered token+call sequences for each branch

#### 2.1: Extract Ordered Token Sequences Per Branch

**Purpose**: For each branch, walk AST and extract ordered list of tokens and function calls

**Current Code Reference:** `token_extractors.py` has `extract_token_sequences()` - this needs complete rewrite

**New Algorithm:**

```
For each control flow branch:
  1. Get AST span (start_line, end_line from branch metadata)
  2. Walk AST in order, collecting items:
     a. Token checks: tok == TOKEN or tok != TOKEN
     b. Function calls: par_*() or parse_*()
     c. Synthetic tokens: tok == STRING && strcmp(tokstr, "value")
  3. Filter out error-checking guards (tok != EXPECTED followed by YYERROR)
  4. Sort items by line number (preserves AST order)
  5. Assign sequence_index (0, 1, 2, ...)
  6. Assign branch_id from branch metadata
  7. Return ordered list of TokenOrCallEnhanced
```

**Implementation:**

```python
def extract_tokens_and_calls_for_branch(
    cursor: Cursor,
    branch: ControlFlowBranch,
    func_name: str,
) -> list[TokenOrCallEnhanced]:
    """
    Extract ordered tokens and calls within a specific branch's AST span.

    Items are sorted by line number to preserve execution order.
    Each item gets branch_id and sequence_index.
    """
    items: list[TokenOrCallEnhanced] = []
    seen: set[tuple[str, int]] = set()  # (token_name or func_name, line) dedup

    start_line = branch['start_line']
    end_line = branch['end_line']

    # Phase 1: Collect all items from within this branch's AST span
    for node in cursor.walk_preorder():
        if not (start_line <= node.location.line <= end_line):
            continue

        # Pattern 1: Token checks (tok == TOKEN)
        if (
            node.kind == CursorKind.BINARY_OPERATOR
            and (tokens := list(node.get_tokens()))
            and len(tokens) >= 3
            and tokens[0].spelling == 'tok'
        ):
            op = tokens[1].spelling
            token_name = tokens[2].spelling

            if op in ('==', '!=') and token_name.isupper() and len(token_name) > 2:
                # Skip if this is an error check (tok != EXPECTED with YYERROR)
                if _is_error_guard(node):
                    continue

                # Skip if filtered token (data token, undocumented, etc)
                if is_data_token(token_name, func_name):
                    continue

                key = (token_name, node.location.line)
                if key not in seen:
                    seen.add(key)
                    items.append({
                        'kind': 'token',
                        'token_name': token_name,
                        'line': node.location.line,
                        'is_negated': (op == '!='),
                        'branch_id': branch['branch_id'],
                        'sequence_index': -1,  # Will be assigned later
                    })

        # Pattern 2: Function calls (par_*() or parse_*())
        elif (
            node.kind == CursorKind.CALL_EXPR
            and _is_parser_function(node.spelling)
            and node.spelling != func_name  # Exclude self-recursion (handle separately)
        ):
            key = (node.spelling, node.location.line)
            if key not in seen:
                seen.add(key)
                items.append({
                    'kind': 'call',
                    'func_name': node.spelling,
                    'line': node.location.line,
                    'branch_id': branch['branch_id'],
                    'sequence_index': -1,
                })

    # Phase 2: Extract synthetic tokens
    synthetics = extract_synthetic_tokens(cursor, items)
    for synthetic in synthetics:
        # Only include synthetics within this branch
        if start_line <= synthetic['line'] <= end_line:
            synthetic['branch_id'] = branch['branch_id']
            synthetic['sequence_index'] = -1
            items.append(synthetic)

    # Phase 3: Sort by line number to preserve order
    items.sort(key=lambda x: x['line'])

    # Phase 4: Assign sequence indices
    for i, item in enumerate(items):
        item['sequence_index'] = i

    return items

def _is_error_guard(node: Cursor) -> bool:
    """
    Detect if token check is an error guard.

    Pattern: if (tok != EXPECTED) YYERROR(...)
    Characteristics:
    - Uses != operator (negation)
    - Followed by YYERROR/YYERRORV macro
    - No semantic content (not part of grammar)
    """
    parent = node.get_parent()

    # Look for YYERROR/YYERRORV in following tokens
    for check_node in parent.walk_preorder():
        tokens = [t.spelling for t in check_node.get_tokens()]
        if 'YYERROR' in tokens or 'YYERRORV' in tokens:
            return True

    return False
```

**Validation Checkpoints:**

- ✓ All items have branch_id matching branch
- ✓ sequence_index is contiguous (0, 1, 2, ..., n-1)
- ✓ Line numbers are monotonically increasing
- ✓ No duplicate (token_name, line) pairs
- ✓ Error guards are filtered out
- ✓ Data tokens are filtered appropriately

**Test Cases:**

```python
def test_extract_tokens_sequential():
    """Extract ordered tokens from simple function."""
    # par_subsh has: tok == INPAR, call(par_list), tok == OUTPAR
    branch = {..., 'start_line': 1630, 'end_line': 1665, 'branch_id': 'if_1'}
    items = extract_tokens_and_calls_for_branch(cursor, branch, 'par_subsh')

    assert len(items) >= 3
    assert items[0]['kind'] == 'token'
    assert items[0]['token_name'] == 'INPAR'
    assert items[0]['sequence_index'] == 0

    assert items[1]['kind'] == 'call'
    assert items[1]['func_name'] == 'par_list'
    assert items[1]['sequence_index'] == 1

    assert items[2]['kind'] == 'token'
    assert items[2]['token_name'] == 'OUTPAR'
    assert items[2]['sequence_index'] == 2

def test_extract_tokens_preserves_order():
    """Line numbers determine order, not extraction order."""
    # If tokens appear in this order: line 200, line 100, line 300
    # Should be sorted: 100, 200, 300
    pass

def test_filter_error_guards():
    """Error guards like 'tok != EXPECTED; YYERROR(...)' are excluded."""
    # Should not include error check tokens
    pass
```

**Output Artifact:** Enhanced `token_extractors.py` with stage 2 functions

---

#### 2.2: Handle String Matching as Synthetic Tokens

**Purpose**: Convert patterns like `tok == STRING && !strcmp(tokstr, "always")` into synthetic ALWAYS tokens

**Current Code Reference:** `extract_synthetic_tokens()` in `token_extractors.py` - enhance with branch awareness

**Algorithm:**

```
For each compound condition with strcmp:
  1. Check if condition matches: tok == STRING && !strcmp(tokstr, "value")
  2. Extract string value from strcmp argument
  3. Create synthetic token name: uppercase(value)
  4. Mark with is_optional based on enclosing if structure
  5. Store branch_id and sequence_index
  6. Document provenance (line, source pattern)
```

**Implementation:**

```python
def extract_synthetic_tokens_for_branch(
    cursor: Cursor,
    branch: ControlFlowBranch,
    items: list[TokenOrCallEnhanced],
) -> list[SyntheticTokenEnhanced]:
    """
    Extract synthetic tokens from string matching conditions within a branch.

    Example: tok == STRING && !strcmp(tokstr, "always") → ALWAYS synthetic token
    """
    synthetics: list[SyntheticTokenEnhanced] = []
    seen: set[tuple[str, int]] = set()

    start_line = branch['start_line']
    end_line = branch['end_line']

    for node in cursor.walk_preorder():
        if not (start_line <= node.location.line <= end_line):
            continue

        if node.kind != CursorKind.BINARY_OPERATOR:
            continue

        tokens = list(node.get_tokens())
        if not tokens or len(tokens) < 3:
            continue

        spelling_list = [t.spelling for t in tokens]

        # Pattern: tok == STRING && !strcmp(tokstr, "value")
        if 'tok' in spelling_list and '==' in spelling_list and 'strcmp' in spelling_list:
            # Extract string value
            string_value = _extract_strcmp_string_value(spelling_list)
            if string_value:
                synthetic_token = string_value.upper()

                # Skip single-char values except A-K (keywords)
                if len(string_value) == 1 and synthetic_token not in 'ABCDEFGHIJK':
                    continue

                # Determine if optional based on enclosing if
                is_optional = _is_in_optional_if(node)

                key = (synthetic_token, node.location.line)
                if key not in seen:
                    seen.add(key)
                    synthetics.append({
                        'kind': 'synthetic_token',
                        'token_name': synthetic_token,
                        'line': node.location.line,
                        'condition': f"tok == STRING && strcmp(tokstr, \"{string_value}\")",
                        'branch_id': branch['branch_id'],
                        'sequence_index': -1,  # Will be assigned during merge
                        'is_optional': is_optional,
                    })

    return synthetics

def _is_in_optional_if(node: Cursor) -> bool:
    """
    Check if this node is inside an if statement without else.
    Such patterns are optional (may not execute).
    """
    # Walk up AST to find enclosing if
    parent = node.get_parent()
    while parent:
        if parent.kind == CursorKind.IF_STMT:
            # Check if this if has else
            tokens = [t.spelling for t in parent.get_tokens()]
            has_else = 'else' in tokens
            return not has_else  # Optional if no else
        parent = parent.get_parent()

    return False
```

**Validation Checkpoints:**

- ✓ Synthetic token names are valid (SCREAMING_SNAKE_CASE)
- ✓ String values are properly extracted (no quotes)
- ✓ Provenance is documented (line, condition string)
- ✓ is_optional flag is correctly determined
- ✓ No spurious tokens (single-char except A-K)

**Test Cases:**

```python
def test_synthetic_always_token():
    """Extract ALWAYS token from strcmp."""
    # tok == STRING && !strcmp(tokstr, "always")
    branch = {...}
    synthetics = extract_synthetic_tokens_for_branch(cursor, branch, [])

    always_tokens = [s for s in synthetics if s['token_name'] == 'ALWAYS']
    assert len(always_tokens) >= 1
    assert always_tokens[0]['is_optional'] is False  # Depends on if structure

def test_synthetic_in_optional_if():
    """Mark synthetic tokens in optional if blocks."""
    # if (condition) { tok == STRING && strcmp(...) }  // No else!
    pass
```

**Output Artifact:** Enhanced `token_extractors.py`

---

#### 2.3: Merge Branch Items with Sequence Indices

**Purpose**: Combine tokens and calls into unified ordered list with correct indices

**Algorithm:**

```
For a branch:
  1. Get tokens from extract_tokens_and_calls_for_branch()
  2. Get synthetics from extract_synthetic_tokens_for_branch()
  3. Merge into single list
  4. Sort by line number
  5. Re-assign sequence_index (0, 1, 2, ...)
  6. Return merged list
```

**Implementation:**

```python
def merge_branch_items(
    tokens: list[TokenOrCallEnhanced],
    synthetics: list[SyntheticTokenEnhanced],
) -> list[TokenOrCallEnhanced]:
    """Merge and reindex branch items."""
    all_items: list[TokenOrCallEnhanced] = tokens + synthetics
    all_items.sort(key=lambda x: x['line'])

    for i, item in enumerate(all_items):
        item['sequence_index'] = i

    return all_items
```

**Test Cases:**

```python
def test_merge_maintains_order():
    """Merging preserves line-based ordering."""
    tokens = [
        {'kind': 'token', 'token_name': 'INPAR', 'line': 100, ...},
        {'kind': 'call', 'func_name': 'par_list', 'line': 150, ...},
    ]
    synthetics = [
        {'kind': 'synthetic_token', 'token_name': 'ALWAYS', 'line': 130, ...},
    ]

    merged = merge_branch_items(tokens, synthetics)

    # Should be: INPAR (100), ALWAYS (130), par_list (150)
    assert merged[0]['token_name'] == 'INPAR'
    assert merged[1]['token_name'] == 'ALWAYS'
    assert merged[2]['func_name'] == 'par_list'
```

**Output Artifact:** `token_extractors.py` helper function

---

### Stage 3: Assembly into Enhanced Function Nodes

**Agent Role**: Integration specialist  
**Duration**: 1-2 sprints  
**Dependencies**: Stage 0, 1, 2  
**Deliverable**: FunctionNodeEnhanced with complete token_sequences

#### 3.1: Build Enhanced Call Graph

**Purpose**: Create new build_call_graph_enhanced() that populates token_sequences field

**Algorithm:**

```
For each parser function:
  1. Extract control flow branches (Stage 1)
  2. For each branch:
     a. Extract tokens and calls (Stage 2.1)
     b. Extract synthetic tokens (Stage 2.2)
     c. Merge and reindex (Stage 2.3)
  3. Detect control flow patterns:
     - Loop present → set has_loops=True, loop_type='while'|'for'
     - If without else → set is_optional=True
  4. Build FunctionNodeEnhanced with all fields
  5. Return enhanced call graph
```

**Implementation:**

```python
def build_call_graph_enhanced(parser: ZshParser, /) -> dict[str, FunctionNodeEnhanced]:
    """
    Build enhanced call graph with token sequences.

    This is the primary replacement for build_call_graph() in control_flow.py
    """
    call_graph: dict[str, FunctionNodeEnhanced] = {}

    for file, tu in parser.parse_files('*.c'):
        if tu.cursor is None:
            continue

        for cursor in find_function_definitions(tu.cursor):
            function_name = cursor.spelling

            # Existing fields (backward compatible)
            calls: list[str] = []
            for child in walk_and_filter(cursor, CursorKind.CALL_EXPR):
                callee_name = child.spelling
                if callee_name != function_name:
                    calls.append(callee_name)

            # NEW: Extract branches and token sequences
            branches = extract_control_flow_branches(cursor, function_name)
            token_sequences: list[ControlFlowBranch] = []

            for branch in branches:
                # Extract tokens and calls for this branch
                tokens = extract_tokens_and_calls_for_branch(
                    cursor, branch, function_name
                )
                synthetics = extract_synthetic_tokens_for_branch(cursor, branch, tokens)
                merged = merge_branch_items(tokens, synthetics)

                # Update branch with extracted items
                branch['items'] = merged
                token_sequences.append(branch)

            # Detect patterns
            has_loops = any(b['branch_type'] == 'loop' for b in token_sequences)
            loop_type = None
            if has_loops:
                for b in token_sequences:
                    if b['branch_type'] == 'loop':
                        loop_node = _find_loop_in_ast(cursor, b['start_line'])
                        loop_type = _get_loop_type(loop_node)

            is_optional = any(b['branch_type'] == 'if' and not any(
                x['branch_type'] == 'else' for x in token_sequences
            ) for b in token_sequences)

            # Build enhanced node
            node: FunctionNodeEnhanced = {
                'name': function_name,
                'file': str(file.relative_to(parser.zsh_src)),
                'line': cursor.location.line,
                'calls': calls,
                'token_sequences': token_sequences,
                'has_loops': has_loops,
                'is_optional': is_optional,
            }

            if loop_type:
                node['loop_type'] = loop_type

            call_graph[function_name] = node

    return call_graph
```

**Validation Checkpoints:**

- ✓ Every parser function has ≥1 token_sequences branch
- ✓ Every branch has ≥1 items (or is sequential with 0 items)
- ✓ All items have contiguous sequence_index
- ✓ All items have correct branch_id
- ✓ has_loops matches presence of loop branches
- ✓ is_optional matches if-without-else pattern

**Test Cases:**

```python
def test_build_call_graph_enhanced():
    """Enhanced call graph includes token sequences."""
    call_graph = build_call_graph_enhanced(parser)

    # Check par_subsh has token sequences
    subsh = call_graph['par_subsh']
    assert 'token_sequences' in subsh
    assert len(subsh['token_sequences']) >= 2  # if/else branches

    # Each branch has items
    for branch in subsh['token_sequences']:
        assert 'items' in branch
        assert len(branch['items']) >= 1

def test_call_graph_enhanced_has_loops():
    """Detect loops in enhanced call graph."""
    call_graph = build_call_graph_enhanced(parser)

    # par_list has while loop
    list_func = call_graph['par_list']
    assert list_func['has_loops'] is True
    assert list_func.get('loop_type') == 'while'

def test_call_graph_enhanced_optional():
    """Detect optional if-without-else."""
    call_graph = build_call_graph_enhanced(parser)

    # Some function with optional branch
    # (Find one by checking token sequences)
    pass
```

**Output Artifact:** New function in `control_flow.py`

---

#### 3.2: Validate Enhanced Call Graph

**Purpose**: Comprehensive validation before feeding to rule generation

**Validation Suite:**

```python
def validate_enhanced_call_graph(
    call_graph: dict[str, FunctionNodeEnhanced],
    token_mapping: dict[str, _TokenDef],
    parser_functions: dict[str, FunctionNode],
) -> dict[str, list[str]]:
    """
    Comprehensive validation of enhanced call graph.

    Returns error dict: function_name → [error messages]
    """
    errors_by_func: dict[str, list[str]] = {}

    for func_name, node in call_graph.items():
        func_errors = []

        # Validate token sequences
        for branch in node['token_sequences']:
            branch_errors = _validate_branch(
                branch, token_mapping, parser_functions
            )
            func_errors.extend(branch_errors)

        # Validate call graph consistency
        # (All calls in token sequences should match node.calls)
        calls_in_sequences = set()
        for branch in node['token_sequences']:
            for item in branch['items']:
                if item['kind'] == 'call':
                    calls_in_sequences.add(item['func_name'])

        extra_calls = calls_in_sequences - set(node['calls'])
        missing_calls = set(node['calls']) - calls_in_sequences

        if extra_calls:
            func_errors.append(
                f"Calls in sequences not in node.calls: {extra_calls}"
            )
        if missing_calls:
            func_errors.append(
                f"Calls in node.calls not in sequences: {missing_calls}"
            )

        # Validate loop markers
        has_loops = any(b['branch_type'] == 'loop' for b in node['token_sequences'])
        if has_loops != node.get('has_loops', False):
            func_errors.append(
                f"has_loops mismatch: {has_loops} vs {node.get('has_loops')}"
            )

        if func_errors:
            errors_by_func[func_name] = func_errors

    return errors_by_func

def _validate_branch(
    branch: ControlFlowBranch,
    token_mapping: dict[str, _TokenDef],
    parser_functions: dict[str, FunctionNode],
) -> list[str]:
    """Validate a single branch."""
    errors: list[str] = []

    # Check sequence_index contiguity
    indices = sorted([item['sequence_index'] for item in branch['items']])
    expected = list(range(len(branch['items'])))
    if indices != expected:
        errors.append(
            f"Branch {branch['branch_id']}: "
            f"Non-contiguous indices {indices}"
        )

    # Check line monotonicity
    lines = [item['line'] for item in branch['items']]
    if lines != sorted(lines):
        errors.append(
            f"Branch {branch['branch_id']}: "
            f"Non-monotonic lines {lines}"
        )

    # Check token/call definitions
    for item in branch['items']:
        if item['kind'] == 'token':
            if item['token_name'] not in token_mapping:
                errors.append(
                    f"Branch {branch['branch_id']}: "
                    f"Undefined token {item['token_name']}"
                )
        elif item['kind'] == 'call':
            if item['func_name'] not in parser_functions:
                errors.append(
                    f"Branch {branch['branch_id']}: "
                    f"Undefined function {item['func_name']}"
                )

    return errors
```

**Output Artifact:** Validation functions in `token_sequence_validators.py`

---

### Stage 4: Rule Generation from Token Sequences

**Agent Role**: Grammar generation specialist  
**Duration**: 2-3 sprints  
**Dependencies**: Stage 0, 3  
**Deliverable**: Rewritten \_build_grammar_rules() consuming token sequences

#### 4.1: Design Grammar Generation Algorithm

**Purpose**: Define algorithm to convert token sequences → grammar rules

**Algorithm - Convert Branch Sequences to Grammar Nodes:**

```
For each branch with items=[tok1, call1, tok2, call2, ...]:
  1. If items is empty:
     → return Empty node

  2. If items == [single_call]:
     → return Ref(call)

  3. If branch_type == 'loop':
     → return Repeat(Sequence(...items as sequence))
     → Set min=0 (loops can execute 0 times)

  4. If all branches are token-based alternatives:
     → Create Union with one Sequence per branch
     → Example: if(tok==INPAR) vs if(tok==INBRACE)
       → Union[Sequence[INPAR, ...], Sequence[INBRACE, ...]]

  5. Otherwise:
     → Return Sequence([item1, item2, item3, ...])
       where each item is converted:
       - token → Ref(TOKEN)
       - call → Ref(function)
       - synthetic → Ref(SYNTHETIC_TOKEN)
```

**Implementation Pseudocode:**

```python
def build_grammar_rules(
    call_graph: dict[str, FunctionNodeEnhanced],
    control_flows: dict[str, ControlFlowPattern | None],
) -> dict[str, GrammarNode]:
    """
    Build grammar rules from token sequences.

    Primary input: call_graph with token_sequences field
    Secondary input: control_flows for optional/repeat patterns

    This replaces the old build_grammar_rules() that used call graphs.
    """
    rules: dict[str, GrammarNode] = {}

    for func_name, node in call_graph.items():
        rule = _convert_node_to_rule(func_name, node, control_flows)
        if rule:
            rule_name = _function_to_rule_name(func_name)
            rules[rule_name] = rule

    return rules

def _convert_node_to_rule(
    func_name: str,
    node: FunctionNodeEnhanced,
    control_flows: dict[str, ControlFlowPattern | None],
) -> GrammarNode | None:
    """Convert enhanced function node to grammar rule."""

    branches = node['token_sequences']

    # Case 1: No branches (shouldn't happen, but handle gracefully)
    if not branches:
        return {'empty': True}

    # Case 2: Single sequential branch
    if len(branches) == 1:
        branch = branches[0]
        return _convert_branch_to_rule(func_name, branch, control_flows)

    # Case 3: Multiple branches (union of alternatives)
    # Each branch becomes one alternative
    alternatives: list[GrammarNode] = []
    for branch in branches:
        alt = _convert_branch_to_rule(func_name, branch, control_flows)
        if alt:
            alternatives.append(alt)

    if len(alternatives) == 1:
        return alternatives[0]
    else:
        return {'union': alternatives}

def _convert_branch_to_rule(
    func_name: str,
    branch: ControlFlowBranch,
    control_flows: dict[str, ControlFlowPattern | None],
) -> GrammarNode:
    """Convert one branch to grammar node."""

    items = branch['items']

    # Case 1: Empty branch
    if not items:
        return {'empty': True}

    # Case 2: Single item
    if len(items) == 1:
        return _item_to_node(items[0])

    # Case 3: Loop branch
    if branch['branch_type'] == 'loop':
        # All items in loop body
        body_node = _items_to_sequence(items)
        return {
            'repeat': body_node,
            'min': 0,  # Loops can execute 0 times
        }

    # Case 4: Sequential items
    # Convert to Sequence[item1, item2, ...]
    return _items_to_sequence(items)

def _item_to_node(item: TokenOrCallEnhanced) -> GrammarNode:
    """Convert single token/call to grammar node."""
    if item['kind'] == 'token':
        return {'$ref': item['token_name']}
    elif item['kind'] == 'call':
        rule_name = _function_to_rule_name(item['func_name'])
        return {'$ref': rule_name}
    elif item['kind'] == 'synthetic_token':
        return {'$ref': item['token_name']}
    else:
        return {'empty': True}

def _items_to_sequence(items: list[TokenOrCallEnhanced]) -> GrammarNode:
    """Convert list of items to Sequence node."""
    if not items:
        return {'empty': True}

    if len(items) == 1:
        return _item_to_node(items[0])

    nodes: list[GrammarNode] = []
    for item in items:
        node = _item_to_node(item)
        if node != {'empty': True}:  # Skip empty nodes
            nodes.append(node)

    if len(nodes) == 1:
        return nodes[0]
    else:
        return {'sequence': nodes}
```

**Example Transformations:**

```
Branch 1: [INPAR, par_list, OUTPAR]
  → Sequence[Ref(INPAR), Ref(list), Ref(OUTPAR)]

Branch 2: [INBRACE, par_list, OUTBRACE]
  → Sequence[Ref(INBRACE), Ref(list), Ref(OUTBRACE)]

Union of branches 1 & 2:
  → Union[
      Sequence[Ref(INPAR), Ref(list), Ref(OUTPAR)],
      Sequence[Ref(INBRACE), Ref(list), Ref(OUTBRACE)]
    ]

Loop branch: [loop: while(1) { par_list; zshlex(); }]
  → Repeat[Ref(list), min=0]
```

**Output Artifact:** Rewritten functions in `grammar_rules.py`

---

#### 4.2: Integrate Control Flow Patterns (Optional/Repeat)

**Purpose**: Apply Optional/Repeat wrapping based on control flow analysis results

**Algorithm:**

```
For each rule generated from a function:
  1. Check control_flows[func_name]
  2. If pattern_type == 'optional':
     → Wrap rule in Optional
  3. If pattern_type == 'repeat':
     → Wrap rule in Repeat (if not already Repeat)
     → Set min/max based on pattern details
  4. Otherwise:
     → Keep rule as-is (sequential)
```

**Implementation:**

```python
def apply_control_flow_patterns(
    rules: dict[str, GrammarNode],
    control_flows: dict[str, ControlFlowPattern | None],
) -> dict[str, GrammarNode]:
    """Wrap rules with Optional/Repeat based on control flow analysis."""

    for rule_name in rules:
        func_name = _rule_name_to_function(rule_name)
        if func_name not in control_flows:
            continue

        pattern = control_flows[func_name]
        if pattern is None:
            continue  # Sequential, no wrapping needed

        rule = rules[rule_name]

        if pattern['pattern_type'] == 'optional':
            rules[rule_name] = {'optional': rule}

        elif pattern['pattern_type'] == 'repeat':
            # Only wrap if not already a Repeat
            if 'repeat' not in rule:
                min_iter = pattern.get('min_iterations', 0)
                rules[rule_name] = {
                    'repeat': rule,
                    'min': min_iter,
                }

    return rules
```

**Test Cases:**

```python
def test_optional_wrapping():
    """Optional patterns get wrapped in Optional node."""
    rules = {'if': {'$ref': 'something'}}
    control_flows = {
        'par_if': {'pattern_type': 'optional', ...}
    }

    wrapped = apply_control_flow_patterns(rules, control_flows)
    assert 'optional' in wrapped['if']

def test_repeat_wrapping():
    """Repeat patterns get wrapped in Repeat node."""
    rules = {'list': {'$ref': 'item'}}
    control_flows = {
        'par_list': {'pattern_type': 'repeat', 'min_iterations': 0, ...}
    }

    wrapped = apply_control_flow_patterns(rules, control_flows)
    assert 'repeat' in wrapped['list']
```

**Output Artifact:** Function in `grammar_rules.py`

---

#### 4.3: Backward Compatibility & Schema Validation

**Purpose**: Ensure new rules pass schema and don't break existing output format

**Integration Points:**

1. **Call Graph Integration**:
    - New `build_call_graph_enhanced()` returns `FunctionNodeEnhanced`
    - Old `build_call_graph()` still exists for validation
    - In `construct_grammar()`, call both and compare:

        ```python
        call_graph_old = build_call_graph(parser)
        call_graph_new = build_call_graph_enhanced(parser)

        # Validate consistency
        for func_name in call_graph_old:
            old_calls = set(call_graph_old[func_name]['calls'])
            new_calls = set()
            for branch in call_graph_new[func_name]['token_sequences']:
                for item in branch['items']:
                    if item['kind'] == 'call':
                        new_calls.add(item['func_name'])

            assert old_calls == new_calls, f"Call mismatch in {func_name}"
        ```

2. **Schema Validation**:
    - Existing schema in `canonical-grammar.schema.json` already supports new structures
    - Run `_validate_schema()` on generated grammar
    - Check for any unexpected structure differences

3. **Output Format**:
    - Grammar output structure unchanged: `{languages: {core: {...}}}`
    - Only rule contents differ (now with token sequences)
    - Old rules like `{'$ref': 'list'}` become `{'sequence': [...]}`

**Test Cases:**

```python
def test_new_grammar_passes_schema():
    """Generated grammar from enhanced call graph passes validation."""
    call_graph = build_call_graph_enhanced(parser)
    rules = build_grammar_rules(call_graph, control_flows)

    grammar = {
        'languages': {
            'core': {**core_symbols, **rules}
        }
    }

    errors = validate_schema(grammar, schema_path)
    assert len(errors) == 0

def test_backward_compatibility():
    """New rules are superset of old rules (old refs still work)."""
    # All old Ref(name) patterns should still resolve
    # Just with more structure
    pass
```

**Output Artifact:** Integration code in `construct_grammar.py`

---

### Stage 5: Validation & Comparison Against Semantic Grammar

**Agent Role**: Quality assurance specialist  
**Duration**: 2-3 sprints  
**Dependencies**: Stage 4  
**Deliverable**: Validation framework + coverage report

#### 5.1: Extract Semantic Grammar from Comments

**Purpose**: Parse parse.c comments to get expected grammar rules

**Algorithm:**

```
For each parser function in parse.c:
  1. Find docstring before function definition
  2. Look for grammar comment pattern:
     - Starts with function name or rule name
     - Contains ':' (like EBNF)
     - Example: "for : FOR WORD ( ... ) DO list DONE"
  3. Parse EBNF notation:
     - Token names (UPPERCASE)
     - Rule names (lowercase)
     - Operators: |, {}, [], +, *
  4. Store as expected rule
  5. Return dict of func_name → expected_rule
```

**Implementation:**

```python
def extract_semantic_grammar_comments(zsh_src: Path) -> dict[str, str]:
    """
    Extract semantic grammar from parse.c comments.

    Returns: {func_name: grammar_comment_string}
    """
    parse_c = zsh_src / 'parse.c'
    content = parse_c.read_text()

    semantic_grammar: dict[str, str] = {}

    # Pattern: /* rule_name : grammar */ or /** grammar */
    import re

    # Find all /* ... */ comments followed by function definitions
    lines = content.split('\n')

    for i, line in enumerate(lines):
        # Look for function definitions
        match = re.match(r'^(static\s+)?[\w*\s]+\n?([a-z_][a-z0-9_]*)\s*\(', line)
        if match:
            func_name = match.group(2)
            if not _is_parser_function(func_name):
                continue

            # Look backward for comment
            comment_lines = []
            j = i - 1
            while j >= 0 and (lines[j].strip().startswith('*') or lines[j].strip().startswith('/')):
                comment_lines.insert(0, lines[j])
                j -= 1

            comment_text = '\n'.join(comment_lines)

            # Extract grammar rule (looking for ':' pattern)
            if ':' in comment_text:
                # Simple heuristic: line with ':' after rule name
                for cline in comment_lines:
                    if func_name.replace('par_', '').replace('parse_', '') in cline and ':' in cline:
                        # Extract rule part
                        rule = cline.split(':')[1].strip()
                        semantic_grammar[func_name] = rule
                        break

    return semantic_grammar
```

**Example Output:**

```python
{
    'par_for': 'for : FOR WORD ( { word } | ( cond ) ) DO list DONE',
    'par_case': 'case : CASE word { (pattern) list } ESAC',
    'par_if': 'if : IF ... THEN list ... FI',
    'par_subsh': 'subsh : INPAR list OUTPAR | INBRACE list OUTBRACE',
    ...
}
```

**Test Cases:**

```python
def test_extract_semantic_grammar_for_subsh():
    """Extract grammar comment for par_subsh."""
    semantic = extract_semantic_grammar_comments(zsh_src)

    assert 'par_subsh' in semantic
    rule = semantic['par_subsh']

    # Should contain token names and rule references
    assert 'INPAR' in rule
    assert 'OUTPAR' in rule
    assert 'list' in rule

def test_extract_semantic_grammar_for_for():
    """Extract grammar for par_for."""
    semantic = extract_semantic_grammar_comments(zsh_src)

    assert 'par_for' in semantic
    rule = semantic['par_for']
    assert 'FOR' in rule
```

**Output Artifact:** New file `zsh_grammar/semantic_grammar_extractor.py`

---

#### 5.2: Compare Extracted vs Expected Rules

**Purpose**: Validation that extracted rules match documented grammar

**Comparison Algorithm:**

```
For each function with semantic grammar:
  1. Get extracted rule
  2. Get expected rule
  3. Analyze both:
     - Extract token references (SCREAMING_SNAKE_CASE)
     - Extract rule references (lowercase)
     - Identify structure (sequence vs union vs optional)
  4. Compute match score:
     - Token overlap: matching tokens / (extracted + expected) tokens
     - Rule overlap: matching rules / (extracted + expected) rules
     - Structure match: same primary structure (seq, union, opt)?
  5. Flag mismatches and document them
```

**Implementation:**

```python
class RuleComparator:
    """Compare extracted vs expected grammar rules."""

    def compare_rules(
        self,
        extracted_rule: GrammarNode,
        expected_rule_str: str,
    ) -> dict[str, float | bool | list]:
        """
        Compare extracted rule against expected grammar string.

        Returns scores and details:
        {
            'token_match_score': float (0-1),
            'rule_match_score': float (0-1),
            'structure_match': bool,
            'missing_tokens': list[str],
            'extra_tokens': list[str],
            'missing_rules': list[str],
            'extra_rules': list[str],
        }
        """
        # Parse expected rule to extract tokens/rules
        expected_tokens = _extract_tokens_from_rule(expected_rule_str)
        expected_rules = _extract_rules_from_rule(expected_rule_str)

        # Parse extracted rule
        extracted_tokens = _extract_tokens_from_grammar_node(extracted_rule)
        extracted_rules = _extract_rules_from_grammar_node(extracted_rule)

        # Compute overlap
        token_overlap = expected_tokens & extracted_tokens
        token_union = expected_tokens | extracted_tokens
        token_match = len(token_overlap) / len(token_union) if token_union else 1.0

        rule_overlap = expected_rules & extracted_rules
        rule_union = expected_rules | extracted_rules
        rule_match = len(rule_overlap) / len(rule_union) if rule_union else 1.0

        # Check structure
        structure_match = _structure_match(extracted_rule, expected_rule_str)

        return {
            'token_match_score': token_match,
            'rule_match_score': rule_match,
            'structure_match': structure_match,
            'missing_tokens': sorted(expected_tokens - extracted_tokens),
            'extra_tokens': sorted(extracted_tokens - expected_tokens),
            'missing_rules': sorted(expected_rules - extracted_rules),
            'extra_rules': sorted(extracted_rules - expected_rules),
        }

def _extract_tokens_from_rule(rule_str: str) -> set[str]:
    """Extract UPPERCASE token names from rule string."""
    import re
    tokens = re.findall(r'\b([A-Z][A-Z0-9_]*)\b', rule_str)
    return set(tokens)

def _extract_rules_from_rule(rule_str: str) -> set[str]:
    """Extract lowercase rule names from rule string."""
    import re
    rules = re.findall(r'\b([a-z][a-z0-9_]*)\b', rule_str)
    return set(rules)

def _extract_tokens_from_grammar_node(node: GrammarNode) -> set[str]:
    """Extract all token references from grammar node."""
    tokens: set[str] = set()

    def visit(n: GrammarNode):
        if isinstance(n, dict):
            if '$ref' in n:
                ref = n['$ref']
                if ref.isupper():
                    tokens.add(ref)

            for v in n.values():
                if isinstance(v, (dict, list)):
                    visit(v)
        elif isinstance(n, list):
            for item in n:
                visit(item)

    visit(node)
    return tokens
```

**Test Cases:**

```python
def test_compare_par_subsh():
    """Compare extracted subsh rule against semantic grammar."""
    expected = 'INPAR list OUTPAR | INBRACE list OUTBRACE'
    extracted = {
        'union': [
            {'sequence': [{'$ref': 'INPAR'}, {'$ref': 'list'}, {'$ref': 'OUTPAR'}]},
            {'sequence': [{'$ref': 'INBRACE'}, {'$ref': 'list'}, {'$ref': 'OUTBRACE'}]}
        ]
    }

    comparison = comparator.compare_rules(extracted, expected)

    # Should have high match
    assert comparison['token_match_score'] >= 0.8
    assert comparison['rule_match_score'] >= 0.8
    assert comparison['structure_match'] is True
```

**Output Artifact:** New file `zsh_grammar/rule_comparison.py`

---

#### 5.3: Generate Validation Report

**Purpose**: Document coverage and discrepancies

**Report Structure:**

```markdown
# Phase 2.4.1 Validation Report

## Summary

- Functions validated: N/31
- Average token match: X%
- Average rule match: Y%
- Structure match: Z%
- Overall success criterion (≥80%): PASS/FAIL

## By Function

### ✅ Perfect Matches (≥95%)

- par_subsh
- par_if
- ...

### ⚠️ Partial Matches (70-94%)

- par_for (88% token, 85% rule)
    - Missing tokens: DSEMI
    - Extra tokens: SEMI
    - Reason: Variation in separator handling

### ❌ Poor Matches (<70%)

- par_case (45% token, 50% rule)
    - Missing: FOR, WHILE (not in grammar)
    - Reason: Architectural issue with case pattern parsing

## Detailed Analysis by Issue
```

**Implementation:**

```python
def generate_validation_report(
    semantic_grammar: dict[str, str],
    extracted_rules: dict[str, GrammarNode],
    comparisons: dict[str, dict],
) -> str:
    """Generate markdown validation report."""

    report = "# Phase 2.4.1 Token-Sequence Validation Report\n\n"

    # Summary statistics
    total = len(semantic_grammar)
    validated = len([c for c in comparisons.values() if c is not None])

    token_scores = [c.get('token_match_score', 0) for c in comparisons.values() if c]
    rule_scores = [c.get('rule_match_score', 0) for c in comparisons.values() if c]
    structure_matches = sum(1 for c in comparisons.values() if c and c.get('structure_match'))

    avg_token = sum(token_scores) / len(token_scores) if token_scores else 0
    avg_rule = sum(rule_scores) / len(rule_scores) if rule_scores else 0

    report += f"## Summary\n\n"
    report += f"- **Functions with semantic grammar**: {total}\n"
    report += f"- **Functions validated**: {validated}\n"
    report += f"- **Average token match**: {avg_token*100:.1f}%\n"
    report += f"- **Average rule match**: {avg_rule*100:.1f}%\n"
    report += f"- **Structure matches**: {structure_matches}/{validated}\n"
    report += f"- **Overall criterion (≥80%)**: {'✅ PASS' if avg_token >= 0.8 else '❌ FAIL'}\n\n"

    # By function
    report += "## Validation by Function\n\n"

    perfect = [fn for fn, c in comparisons.items() if c and c['token_match_score'] >= 0.95]
    partial = [fn for fn, c in comparisons.items() if c and 0.7 <= c['token_match_score'] < 0.95]
    poor = [fn for fn, c in comparisons.items() if c and c['token_match_score'] < 0.7]

    if perfect:
        report += f"### ✅ Perfect Matches ({len(perfect)})\n\n"
        for fn in perfect:
            report += f"- **{fn}** ({comparisons[fn]['token_match_score']*100:.0f}%)\n"
        report += "\n"

    if partial:
        report += f"### ⚠️ Partial Matches ({len(partial)})\n\n"
        for fn in partial:
            c = comparisons[fn]
            report += f"- **{fn}** ({c['token_match_score']*100:.0f}% token, {c['rule_match_score']*100:.0f}% rule)\n"
            if c['missing_tokens']:
                report += f"  - Missing: {', '.join(c['missing_tokens'])}\n"
            if c['extra_tokens']:
                report += f"  - Extra: {', '.join(c['extra_tokens'])}\n"
        report += "\n"

    if poor:
        report += f"### ❌ Poor Matches ({len(poor)})\n\n"
        for fn in poor:
            c = comparisons[fn]
            report += f"- **{fn}** ({c['token_match_score']*100:.0f}%)\n"
        report += "\n"

    return report
```

**Output Artifact:** `zsh_grammar/validation_reporter.py` + report file

---

### Stage 6: Documentation & Integration

**Agent Role**: Documentation specialist  
**Duration**: 1 sprint  
**Dependencies**: All previous stages  
**Deliverable**: Updated TODOS.md, architecture docs, integration guide

#### 6.1: Update Project Documentation

**Files to Update:**

1. **TODOS.md**
    - Mark Phase 2.4.1 COMPLETE
    - Document completion metrics
    - Update Phase 2.4 Infrastructure section

2. **AGENTS.md**
    - Add Phase 2.4.1 build commands if applicable
    - Document integration workflow

3. **New file: PHASE_2_4_1_COMPLETION.md**
    - Summary of changes
    - Data structure migration guide
    - Examples of old vs new rule generation

**Example Entry for TODOS.md:**

```markdown
#### Phase 2.4.1: Token-Sequence-Based Grammar Extraction ✅ COMPLETE

- Status: COMPLETE
- Implementation: 6 stages, 4-6 sub-agents
- Duration: 8-12 sprints
- Results:
    - Redesigned from function-centric (call graphs) to token-sequence-centric
    - par_subsh rule: Union[Sequence[INPAR, list, OUTPAR], Sequence[INBRACE, list, OUTBRACE]]
    - Grammar comments from parse.c reconstructed in 85%+ of functions
    - Schema validation passing; backward compatible
    - Validation framework in place

**Files Changed:**

- construct_grammar.py (rewritten \_build_grammar_rules)
- control_flow.py (added build_call_graph_enhanced)
- token_extractors.py (enhanced extraction with branch awareness)
- NEW: branch_extractor.py
- NEW: token_sequence_validators.py
- NEW: semantic_grammar_extractor.py
- NEW: rule_comparison.py
- NEW: validation_reporter.py
- \_types.py (added enhanced data structures)

**Key Concepts:**

- ControlFlowBranch: Represents single AST alternative (if/else/switch case/loop)
- TokenOrCallEnhanced: Discriminated union with branch context
- FunctionNodeEnhanced: Call graph node with token_sequences field
- Token sequences ordered by line number (preserves execution order)
- Synthetic tokens from strcmp patterns
```

---

## Critical Success Metrics

### Per-Stage Metrics

| Stage | Metric                 | Target          | Validation                       |
| ----- | ---------------------- | --------------- | -------------------------------- |
| 0     | Type defs valid        | 100%            | basedpyright passes              |
| 1     | Branches extracted     | 31/31 functions | All have ≥1 branch               |
| 2     | Tokens extracted       | ≥50             | Per-branch items non-empty       |
| 3     | Enhanced call graph    | Complete        | All functions populated          |
| 4     | Rules generated        | All pass schema | jsonschema.validate passes       |
| 5     | Semantic grammar match | ≥80%            | Validation report shows coverage |
| 6     | Documentation          | Complete        | All files updated                |

### End-to-End Metrics

- **par_subsh rule reconstructs semantic grammar**: ✓
- **≥80% of functions match documentation**: ✓
- **Call graph validation confirms functions are called**: ✓
- **Schema validation passing**: ✓
- **No breaking changes to output format**: ✓
- **Code quality: 0 lint/type errors**: ✓

---

## Risk Mitigation

### Risk 1: AST Traversal Complexity

**Risk**: Control flow extraction misses branches (nested if/switch)  
**Mitigation**:

- Start with simple functions (par_for, par_case) before complex (par_cond)
- Write unit tests for each control structure type
- Validate extracted branches match AST spans

### Risk 2: Token Ordering Loss

**Risk**: Sorting by line number loses semantic order  
**Validation**:

- Assertion: sequence_index is contiguous
- Assertion: Line numbers monotonic
- Test cases with nested token checks

### Risk 3: Schema Incompatibility

**Risk**: New structures don't match schema  
**Mitigation**:

- Schema already validated (Phase 1.4)
- Test each rule against schema before committing
- Fall back to simpler Ref nodes if needed

### Risk 4: Dead Code (Old build_call_graph)

**Risk**: Old code not removed, confusion about which to use  
**Mitigation**:

- Keep old function (for backward compat)
- Mark with deprecation notice
- In construct_grammar(), call both and validate consistency
- Remove in future cleanup phase

---

## Integration with Existing Code

### construct_grammar.\_construct_grammar()

```python
def _construct_grammar(zsh_path: Path, version: str, /) -> Grammar:
    # ... existing code ...

    # Phase 2.4.1: Use enhanced call graph
    call_graph = build_call_graph_enhanced(parser)  # NEW

    # Validate against old call graph for consistency
    call_graph_old = build_call_graph(parser)  # OLD (for validation)
    _validate_call_graph_consistency(call_graph, call_graph_old)

    # Build rules from token sequences (not call graph)
    grammar_rules = build_grammar_rules(call_graph, control_flows)  # REWRITTEN

    # Rest of flow unchanged...
```

### control_flow.py

```python
# OLD function (keep for now, marked deprecated)
def build_call_graph(parser: ZshParser, /) -> dict[str, FunctionNode]:
    """Deprecated: Use build_call_graph_enhanced instead."""
    # ... existing implementation ...

# NEW function (primary)
def build_call_graph_enhanced(parser: ZshParser, /) -> dict[str, FunctionNodeEnhanced]:
    """Build enhanced call graph with token sequences."""
    # ... new implementation from Stage 3 ...
```

### token_extractors.py

```python
# Existing extract_token_sequences() rewritten to use branch context
def extract_token_sequences(cursor: Cursor, func_name: str = '') -> list[TokenOrCall]:
    """REWRITTEN: Now takes branch parameter."""
    # OLD behavior preserved via wrapper

# NEW function for enhanced extraction
def extract_tokens_and_calls_for_branch(
    cursor: Cursor,
    branch: ControlFlowBranch,
    func_name: str,
) -> list[TokenOrCallEnhanced]:
    """Extract tokens for specific branch."""
    # ... Stage 2.1 implementation ...
```

---

## Sub-Agent Handoff Protocol

### Stage Assignment

Each stage can be assigned to 1-2 sub-agents:

1. **Stage 0**: Data Architect (1 agent) - 1-2 sprints
2. **Stage 1**: AST Specialist (1 agent) - 2-3 sprints
3. **Stage 2**: Token Extraction Specialist (1 agent) - 2-3 sprints
4. **Stage 3**: Integration Specialist (1 agent) - 1-2 sprints
5. **Stage 4**: Grammar Generator (1 agent) - 2-3 sprints
6. **Stage 5**: QA/Validation (1 agent) - 2-3 sprints
7. **Stage 6**: Documentation (1 agent) - 1 sprint

### Communication Protocol

**Before Starting Stage:**

1. Review this plan document
2. Review test cases in stage specification
3. Implement all test cases first (TDD)
4. Run linting/type checking frequently

**During Implementation:**

1. Create feature branch: `feat/phase-2.4.1-stage-N`
2. Commit frequently with clear messages
3. Keep types strict (basedpyright)
4. Document unclear logic with comments

**After Stage:**

1. Run full test suite: `mise run test`
2. Validate against existing tests
3. Create pull request with stage deliverables
4. Update TODOS.md with stage status
5. Document any architectural decisions

**Blockers/Questions:**

- Post in thread with specific line/function references
- Include minimal reproducible example
- Document decision for future context

---

## Success Criteria (Final)

✅ **All stages complete:**

1. Data structures defined and validated
2. Control flow branches extracted for all 31 functions
3. Tokens and calls extracted with ordering preserved
4. Enhanced call graph built and validated
5. Grammar rules generated from token sequences
6. Validation framework reports ≥80% semantic grammar match
7. Documentation complete and integrated

✅ **Code quality:**

- 0 linting errors (ruff)
- 0 type errors (basedpyright)
- All test cases passing
- Schema validation passing

✅ **Architectural goals:**

- Rules reconstruct semantic grammar comments
- Token ordering preserved (execution order maintained)
- Control flow branches modeled as Union alternatives
- Synthetic tokens properly identified and documented
- Call graph validated for consistency

---

## Notes for Implementation

### Important Reminders

1. **Don't break existing code**: Keep old functions around, mark deprecated
2. **Test first**: Write test cases before implementation
3. **Validate frequently**: Run schema/type checks often
4. **Document decisions**: Comments for non-obvious logic
5. **Stage dependencies**: Follow order; later stages assume earlier ones complete

### Quick Reference

- **Token filtering**: See `extraction_filters.py` for logic
- **AST navigation**: Use `walk_and_filter()` from `ast_utilities.py`
- **Parser functions**: Use `_is_parser_function()` from `construct_grammar.py`
- **Line-based ordering**: Always sort by `location.line` to preserve order
- **Schema reference**: `canonical-grammar.schema.json` for valid structures

---

## Appendix: File Structure After Implementation

```
zsh-grammar/src/zsh_grammar/
├── ast_utilities.py             # Existing
├── branch_extractor.py          # NEW: Stage 1.1-1.2
├── control_flow.py              # MODIFIED: Add build_call_graph_enhanced
├── construct_grammar.py         # MODIFIED: Use new rule building
├── extraction_filters.py        # Existing
├── function_discovery.py        # Existing
├── grammar_rules.py             # MODIFIED: Rewrite build_grammar_rules
├── grammar_utils.py             # Existing
├── rule_comparison.py           # NEW: Stage 5.2
├── semantic_grammar_extractor.py # NEW: Stage 5.1
├── source_parser.py             # Existing
├── token_extractors.py          # MODIFIED: Enhance with branch awareness
├── token_sequence_validators.py # NEW: Stage 3.2, Stage 2 validation
├── validation.py                # Existing
└── validation_reporter.py       # NEW: Stage 5.3

tests/
├── test_branch_extractor.py          # NEW
├── test_data_structures.py           # NEW (Stage 0)
├── test_rule_comparison.py           # NEW
├── test_semantic_grammar_extractor.py # NEW
├── test_token_sequence_extraction.py  # NEW (Stage 0, 2, 3)
└── [existing tests]
```
