# Phase 2.4.1 Redesign: Token-Sequence-Based Grammar Extraction

## Objective

Replace the function-centric call graph approach with token-sequence-centric grammar extraction that accurately models how the Zsh parser actually works.

## Key Changes

### 1. New Data Structures

#### TokenOrCall (discriminated union)

```python
class _TokenCheck(TypedDict):
    kind: Literal['token']
    token_name: str
    line: int
    is_negated: bool  # for tok != checks

class _FunctionCall(TypedDict):
    kind: Literal['call']
    func_name: str
    line: int

class _ControlFlowSequence(TypedDict):
    kind: Literal['sequence']
    items: list[TokenOrCall]

class _ControlFlowBranch(TypedDict):
    kind: Literal['branch']
    condition: str  # Description of branch condition (e.g., "if (otok == INPAR)")
    items: list[TokenOrCall]

class _ControlFlowUnion(TypedDict):
    kind: Literal['union']
    branches: list[_ControlFlowBranch]

TokenOrCall = _TokenCheck | _FunctionCall | _ControlFlowSequence | _ControlFlowBranch | _ControlFlowUnion
```

#### Enhanced \_FunctionNode

```python
class _FunctionNode(TypedDict):
    name: str
    file: str
    line: int
    calls: list[str]
    token_sequences: NotRequired[list[list[TokenOrCall]]]  # Phase 2.4.1 NEW
    # ... existing fields ...
```

### 2. New Extraction Function

Replace `_extract_token_consumption_patterns()` with a complete rewrite:

**`_extract_token_sequences(cursor, func_name) -> list[list[TokenOrCall]]`**

Tasks:

1. Walk function body
2. Track all tok == checks and par\_\*() calls in order
3. Group by control flow branch (if/else/switch arms)
4. Return ordered timelines per branch

### 3. Control Flow Branch Analysis

For if/else/switch statements:

- Each branch becomes a separate sequence
- Condition captured as description
- Items within branch preserved in execution order

Example from par_subsh():

```c
// Line 1623: enum lextok otok = tok;
// Line 1626: if (otok == INPAR) {
//   par_list();  // line 1624
//   tok == OUTPAR check
// } else {
//   tok == INBRACE check
//   par_list();
//   tok == OUTBRACE check
// }
```

Extracted structure:

```python
[
  [
    _TokenCheck(token_name='INPAR', ...),
    _FunctionCall(func_name='par_list', ...),
    _TokenCheck(token_name='OUTPAR', ...),
  ],
  [
    _TokenCheck(token_name='INBRACE', ...),
    _FunctionCall(func_name='par_list', ...),
    _TokenCheck(token_name='OUTBRACE', ...),
  ]
]
```

### 4. Modified Rule Generation

Rewrite `_build_grammar_rules()` to consume token_sequences as primary input:

```python
def _build_grammar_rules(
    token_sequences_map: dict[str, list[list[TokenOrCall]]],
    parser_functions: dict[str, _FunctionNode],
    ...
) -> Language:
    for func_name, sequences in token_sequences_map.items():
        if not sequences:
            # No token sequences: leaf function (terminal)
            rule = create_terminal(f'[{rule_name}]', ...)
        elif len(sequences) == 1:
            # Single sequence: directly model as Sequence + Optional/Repeat
            rule = _sequence_to_rule(sequences[0], ...)
        else:
            # Multiple sequences: Union of alternatives
            rule = create_union(
                [_sequence_to_rule(seq, ...) for seq in sequences],
                ...
            )
```

### 5. Synthetic Tokens

For string matching like `tok == STRING && !strcmp(tokstr, "always")`:

- Create synthetic token ALWAYS
- Document in metadata
- Include in grammar

## Implementation Steps

1. **Phase 2.4.1a**: Define new data structures (\_TokenCheck, \_FunctionCall, \_ControlFlowBranch, etc.)
2. **Phase 2.4.1b**: Implement `_extract_token_sequences()` with full AST walking and branch grouping
3. **Phase 2.4.1c**: Implement `_sequence_to_rule()` to convert token sequence to GrammarNode
4. **Phase 2.4.1d**: Rewrite `_build_grammar_rules()` to consume token_sequences
5. **Phase 2.4.1e**: Handle synthetic tokens and string matching conditions
6. **Phase 2.4.1f**: Validate against semantic grammar comments in parse.c

## Success Criteria

- [ ] par_subsh rule generates Union[Sequence[INPAR, list, OUTPAR], Sequence[INBRACE, list, OUTBRACE, Optional[...]]]
- [ ] Token sequences extracted for all 31 parser functions
- [ ] ≥80% of multi-token functions reconstruct documented semantic grammar
- [ ] String matching conditions modeled as synthetic tokens
- [ ] All token-sequence-based rules pass schema validation
- [ ] Call graph validation confirms all extracted sequences match actual function calls

## Files to Modify

- **construct_grammar.py**:
    - Add new data structures (lines ~140-170)
    - Replace `_extract_token_consumption_patterns()` completely
    - Rewrite `_build_grammar_rules()` to use token_sequences
    - Add `_sequence_to_rule()` helper
    - Update `_build_call_graph()` to populate token_sequences

## Expected Impact

- Extracted grammar will accurately represent documented semantic grammar
- Rules will be self-documenting (token sequences visible in generated rules)
- Grammar will match actual Zsh parsing behavior (testable against real code)
- Token-based dispatch will be explicitly modeled (not hidden in call graph)

## Timeline

- Phase 2.4.1a: Data structures - 1 session
- Phase 2.4.1b: Token sequence extraction - 2-3 sessions
- Phase 2.4.1c-f: Rule generation and validation - 2-3 sessions
- Total: 40-60% rework of extraction logic as estimated
