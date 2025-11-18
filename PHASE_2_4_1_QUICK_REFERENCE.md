# Phase 2.4.1 Quick Reference for Sub-Agents

## One-Page Overview

**Goal**: Replace function-centric grammar extraction with token-sequence-centric extraction.

**Current Problem**:

- Grammar extraction models "what calls what" (call graphs)
- Should model "tokens surrounding function calls" (token sequences)
- Example: `par_subsh()` currently extracts as `{'$ref': 'list'}`; should be `Union[Sequence[INPAR, list, OUTPAR], Sequence[INBRACE, list, OUTBRACE]]`

**Solution**: 6 stages, each ~2 sprints, can be parallelized.

---

## Stage Selection Guide

### I want to work on...

**Data structures & types?** → **Stage 0** (Data Architect)

- Define TypedDicts for enhanced data structures
- Create test harness with examples
- Duration: 1-2 sprints

**AST & control flow analysis?** → **Stage 1** (AST Specialist)

- Extract if/else/switch/loop branches from AST
- Identify token-based dispatch conditions
- Duration: 2-3 sprints

**Token extraction?** → **Stage 2** (Token Extractor)

- Walk AST within branch bounds
- Extract ordered token+call sequences
- Handle synthetic tokens from string matching
- Duration: 2-3 sprints

**Gluing components together?** → **Stage 3** (Integrator)

- Combine branches + tokens into enhanced call graph
- Validate completeness
- Duration: 1-2 sprints

**Grammar rule generation?** → **Stage 4** (Grammar Generator)

- Convert token sequences to grammar nodes (Sequence, Union, Repeat, Optional)
- Apply control flow patterns
- Duration: 2-3 sprints

**Testing & validation?** → **Stage 5** (QA Specialist)

- Extract semantic grammar from parse.c comments
- Compare extracted vs expected rules
- Generate validation report
- Duration: 2-3 sprints

**Documentation?** → **Stage 6** (Technical Writer)

- Update TODOS.md, AGENTS.md, architecture docs
- Create integration guide
- Duration: 1 sprint

---

## Key Concepts (Minimal Viable Understanding)

### Token Sequence

Ordered list of tokens and function calls that parser function executes.

Example: `par_subsh()` with `INPAR list OUTPAR` branch has sequence:

```python
[
    {'kind': 'token', 'token_name': 'INPAR', 'sequence_index': 0},
    {'kind': 'call', 'func_name': 'par_list', 'sequence_index': 1},
    {'kind': 'token', 'token_name': 'OUTPAR', 'sequence_index': 2},
]
```

### Control Flow Branch

One execution path through a function (if branch, else branch, switch case, loop body).

Example: `if (tok == INPAR) { ... }` is one branch; `else if (tok == INBRACE) { ... }` is another.

### TokenOrCallEnhanced (Discriminated Union)

```python
type TokenOrCallEnhanced = TokenCheckEnhanced | FunctionCallEnhanced | SyntheticTokenEnhanced
```

Each item has:

- `kind`: 'token' | 'call' | 'synthetic_token'
- `branch_id`: which branch it belongs to
- `sequence_index`: position in ordered sequence (0, 1, 2, ...)

### Synthetic Token

Token created from `tok == STRING && !strcmp(tokstr, "value")` patterns.

Example: `tok == STRING && !strcmp(tokstr, "always")` → Synthetic token `ALWAYS`

### Grammar Node

Abstract syntax tree representing grammar rule.

Examples:

```python
{'empty': True}                                    # Empty
{'$ref': 'list'}                                  # Reference
{'token': 'INPAR', 'matches': '('}                # Token
{'sequence': [{'$ref': 'A'}, {'$ref': 'B'}]}     # Sequence: A then B
{'union': [seq1, seq2]}                           # Union: A | B
{'optional': node}                                # Optional: A?
{'repeat': node, 'min': 0}                        # Repeat: A*
```

---

## Development Workflow (Recommended)

### 1. Before You Start

```bash
# Create feature branch
git checkout -b feat/phase-2.4.1-stage-N

# Review plan section for your stage
cat PHASE_2_4_1_REDESIGN_PLAN.md | grep -A 100 "### Stage N:"

# Set up testing
cd /Users/bryan/Projects/zsh-tools
mise run dev
```

### 2. TDD: Test First, Code Second

```bash
# Write test cases based on stage spec
# Put in: zsh-grammar/tests/test_YOUR_FEATURE.py

# Run tests (will fail initially)
mise //<project>:test test/test_YOUR_FEATURE.py

# Implement code to make tests pass
# ...

# Verify everything still works
mise run test
mise //:lint
mise //:format
```

### 3. During Implementation

```bash
# Format code after editing
mise //:prettier [file.py]  # JS/TS
mise //:ruff-format [file.py]  # Python

# Type check frequently
mise //:basedpyright [file.py]

# Lint and fix
mise //:ruff --fix [file.py]
```

### 4. Before Committing

```bash
# Run full validation
mise //:format                 # Format all
mise //:lint                   # Lint all
mise run test                  # All tests

# Verify schema (if modifying grammar)
python3 -m pytest tests/ -k "schema" -v

# Commit with conventional message
git add .
git commit -m "feat(phase-2.4.1-stage-N): Brief description

Longer explanation if needed.

Stage: N
Test cases: X/Y passing
Type checks: PASS
Lint: PASS
"
```

### 5. Hand Off

```bash
# Push branch
git push origin feat/phase-2.4.1-stage-N

# Create PR with:
# - Link to this plan
# - Stage number
# - Deliverables completed
# - Test coverage
# - Any blockers/questions
```

---

## Code Patterns (Copy-Paste Friendly)

### Pattern 1: Walk AST for Specific Node Type

```python
from clang.cindex import CursorKind
from zsh_grammar.ast_utilities import walk_and_filter

# Find all IF statements
for if_stmt in walk_and_filter(cursor, CursorKind.IF_STMT):
    start_line = if_stmt.extent.start.line
    end_line = if_stmt.extent.end.line
    # Process if_stmt
```

### Pattern 2: Extract Tokens from Condition

```python
tokens = list(node.get_tokens())
token_spellings = [t.spelling for t in tokens]

# Check for tok == TOKEN pattern
if 'tok' in token_spellings and '==' in token_spellings:
    tok_idx = token_spellings.index('tok')
    eq_idx = token_spellings.index('==')
    if eq_idx == tok_idx + 1:
        token_name = token_spellings[eq_idx + 1]
```

### Pattern 3: Build TypedDict with Required + Optional Fields

```python
from typing import TypedDict, NotRequired

class MyItem(TypedDict):
    required_field: str
    number: int
    optional_field: NotRequired[str]  # Optional!

item: MyItem = {
    'required_field': 'value',
    'number': 42,
    # optional_field can be omitted
}
```

### Pattern 4: Validate Sequence Indices

```python
def validate_sequence(items: list[dict]) -> list[str]:
    errors: list[str] = []

    # Check contiguity
    indices = sorted([item['sequence_index'] for item in items])
    expected = list(range(len(items)))
    if indices != expected:
        errors.append(f"Non-contiguous: {indices}")

    # Check monotonic lines
    lines = [item['line'] for item in items]
    if lines != sorted(lines):
        errors.append(f"Non-monotonic lines: {lines}")

    return errors
```

### Pattern 5: Filter Tokens (Context-Sensitive)

```python
from zsh_grammar.extraction_filters import is_data_token

# Skip data tokens in certain contexts
if is_data_token(token_name, func_name):
    continue  # Skip

# But allow some tokens in specific functions
if token_name == 'STRING' and func_name == 'par_repeat':
    # Keep it - STRING is semantic here
    pass
```

### Pattern 6: Test with parse.c Functions

```python
# In test file
from zsh_grammar.source_parser import ZshParser

def test_extract_subsh():
    parser = ZshParser(zsh_src / 'Src')
    tu = parser.parse('parse.c')

    for cursor in find_function_definitions(tu.cursor):
        if cursor.spelling == 'par_subsh':
            # Test with this function
            branches = extract_control_flow_branches(cursor, 'par_subsh')
            assert len(branches) >= 2  # if and else
```

---

## Common Mistakes to Avoid

### ❌ Don't: Reorder tokens by semantic intent

```python
# WRONG: Sorting by name instead of line
items.sort(key=lambda x: x['token_name'])
```

**Why**: Execution order is determined by line number; reordering loses semantics.  
**Fix**: Always sort by `line` number.

### ❌ Don't: Include error guard tokens

```python
# WRONG: Including tok != EXPECTED checks
if op == '!=':
    items.append(token)  # ERROR!
```

**Why**: Error guards are not semantic grammar.  
**Fix**: Check `_is_error_guard()` and skip them.

### ❌ Don't: Forget branch context

```python
# WRONG: Creating items without branch_id
item = {'kind': 'token', 'token_name': 'INPAR', ...}  # Missing branch_id!
```

**Why**: Later stages need to know which branch each item belongs to.  
**Fix**: Always include `branch_id` and `sequence_index`.

### ❌ Don't: Mix old and new extraction

```python
# WRONG: Using old extract_token_sequences() in new code
items = extract_token_sequences(cursor)  # Old!
```

**Why**: Old function doesn't have branch context.  
**Fix**: Use new `extract_tokens_and_calls_for_branch()`.

### ❌ Don't: Validate before implementing

```python
# WRONG: Writing validation code before extraction works
def validate_everything(): ...  # Too early!
```

**Why**: You don't know what to validate yet.  
**Fix**: Code first, add validation after extraction works.

---

## Testing Strategy

### Unit Tests (Test One Function)

```python
def test_extract_inpar_token():
    """Extract INPAR token from simple if."""
    cursor = mock_cursor_with_code("if (tok == INPAR) { ... }")
    branch = {'start_line': 100, 'end_line': 150, 'branch_id': 'if_1'}

    items = extract_tokens_and_calls_for_branch(cursor, branch, 'par_subsh')

    assert len(items) >= 1
    assert items[0]['token_name'] == 'INPAR'
    assert items[0]['sequence_index'] == 0
```

### Integration Tests (Test Stage Outputs)

```python
def test_stage_2_produces_valid_branches():
    """After stage 2, all branches should have valid items."""
    call_graph = build_call_graph_enhanced(parser)

    for func_name, node in call_graph.items():
        for branch in node['token_sequences']:
            # Validate
            assert branch['branch_id']
            assert branch['items']  # At least one item

            # Check sequence validity
            errors = validate_sequence(branch['items'])
            assert not errors, f"{func_name}/{branch['branch_id']}: {errors}"
```

### Regression Tests (Ensure Old Code Still Works)

```python
def test_call_graph_backward_compatible():
    """New call_graph should match old call_graph.calls field."""
    call_graph_old = build_call_graph(parser)
    call_graph_new = build_call_graph_enhanced(parser)

    for func_name in call_graph_old:
        old_calls = set(call_graph_old[func_name]['calls'])

        new_calls = set()
        for branch in call_graph_new[func_name]['token_sequences']:
            for item in branch['items']:
                if item['kind'] == 'call':
                    new_calls.add(item['func_name'])

        assert old_calls == new_calls, f"Call mismatch in {func_name}"
```

---

## Debugging Tips

### Print Branch Structure

```python
import json
from zsh_grammar._types import ControlFlowBranch

branch: ControlFlowBranch = {...}
print(json.dumps(branch, indent=2, default=str))
# Shows structure clearly
```

### Trace Extraction Step-by-Step

```python
def debug_extract_tokens(cursor, branch, func_name):
    print(f"\n=== Extracting tokens for {func_name}/{branch['branch_id']} ===")
    print(f"AST span: {branch['start_line']} - {branch['end_line']}")

    items = []
    for node in cursor.walk_preorder():
        if not (branch['start_line'] <= node.location.line <= branch['end_line']):
            continue

        if node.kind == CursorKind.BINARY_OPERATOR:
            tokens = [t.spelling for t in node.get_tokens()]
            print(f"Line {node.location.line}: BIN_OP {tokens}")
            # ... process

    return items
```

### Validate Against Schema

```python
import jsonschema
from pathlib import Path

schema = json.loads(Path('canonical-grammar.schema.json').read_text())

try:
    jsonschema.validate(instance=grammar, schema=schema)
    print("✓ Schema valid!")
except jsonschema.ValidationError as e:
    print(f"✗ Schema error: {e.message}")
    print(f"  Path: {list(e.path)}")
```

### Compare Before/After Rules

```python
from zsh_grammar.rule_comparison import RuleComparator

comparator = RuleComparator()
result = comparator.compare_rules(extracted_rule, expected_rule_str)

print(f"Token match: {result['token_match_score']*100:.0f}%")
print(f"Rule match: {result['rule_match_score']*100:.0f}%")
print(f"Missing tokens: {result['missing_tokens']}")
print(f"Extra tokens: {result['extra_tokens']}")
```

---

## Key Files Reference

| File                            | Purpose                   | Key Functions                                             |
| ------------------------------- | ------------------------- | --------------------------------------------------------- |
| `construct_grammar.py`          | Main grammar construction | `_construct_grammar()`, `_build_grammar_rules()`          |
| `control_flow.py`               | Call graph + patterns     | `build_call_graph()`, `analyze_control_flow()`            |
| `token_extractors.py`           | Token extraction          | `extract_token_sequences()`, `extract_synthetic_tokens()` |
| `ast_utilities.py`              | AST helpers               | `walk_and_filter()`, `find_function_definitions()`        |
| `extraction_filters.py`         | Token filtering           | `is_data_token()`, `is_undocumented_token()`              |
| `_types.py`                     | Type definitions          | TypedDict definitions                                     |
| `canonical-grammar.schema.json` | Grammar schema            | JSON schema for validation                                |

---

## Blockers / Questions

### How do I find the parse.c function I'm working with?

```python
from zsh_grammar.source_parser import ZshParser
from zsh_grammar.ast_utilities import find_function_definitions

parser = ZshParser(zsh_src / 'Src')
tu = parser.parse('parse.c')

for cursor in find_function_definitions(tu.cursor):
    if cursor.spelling == 'par_subsh':
        print(f"Found at line {cursor.location.line}")
        print(f"Extent: {cursor.extent.start.line} - {cursor.extent.end.line}")
```

### How do I check if a token should be included?

```python
from zsh_grammar.extraction_filters import is_data_token, is_undocumented_token

# Is this token semantic (not data)?
if not is_data_token(token_name, func_name):
    # Include it
    items.append(token)

# Is this token documented in grammar?
if not is_undocumented_token(token_name, func_name):
    # Include it
    items.append(token)
```

### How do I test without running full parser?

```python
# Use mock cursors for small test cases
from unittest.mock import Mock

cursor = Mock()
cursor.walk_preorder.return_value = [...]
cursor.get_tokens.return_value = [...]

# Call your function with mock
result = my_function(cursor)
```

---

## Success Checklist Per Stage

- [ ] Read plan section for your stage
- [ ] Review test cases provided in plan
- [ ] Create test file with all test cases
- [ ] Run tests (fail initially)
- [ ] Implement code to pass tests
- [ ] Type check: `mise //:basedpyright file.py`
- [ ] Lint: `mise //:lint`
- [ ] Format: `mise //:format`
- [ ] Run full test suite: `mise run test`
- [ ] Create PR with clear description
- [ ] Link to PHASE_2_4_1_REDESIGN_PLAN.md
- [ ] Note stage number and any blockers

---

## Questions?

Post in thread with:

1. **Specific stage** (Stage 0, Stage 1, etc.)
2. **Specific function/file** you're working on
3. **Error message or unexpected output** (if applicable)
4. **What you've tried so far**

Example:

> **Stage 2.1** - Extracting tokens from `par_if`
>
> Getting duplicate items with same line number. Expected sequence_index 0, 1, 2 but got 0, 0, 2.
>
> Code: [paste snippet]
>
> What I tried: Added dedup set, but still duplicates.
