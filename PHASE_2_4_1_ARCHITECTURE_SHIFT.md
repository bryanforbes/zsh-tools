# Phase 2.4.1: Architecture Shift - Function-Centric to Token-Sequence-Centric

## The Problem: What's Broken?

### Current Architecture (Phase 1-3)

The grammar extraction currently operates as a **call graph traversal**:

```
┌─────────────────────┐
│   Parse.c source    │
│   (semantic grammar │
│   comments)         │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────────────┐
│  AST Analysis               │
│  Find function definitions  │
└──────────┬──────────────────┘
           │
           ↓
┌─────────────────────────────────────────┐
│  Call Graph Construction                │
│  {func_name: {calls: [func1, func2]}}   │
└──────────┬──────────────────────────────┘
           │
           ↓
┌──────────────────────────────────────────────┐
│  Rule Generation                             │
│  FOR EACH function:                          │
│    rule = {$ref: name_of_called_function}    │
│  RESULT: {'list': {'$ref': 'sublist'}}       │
└──────────────────────────────────────────────┘
```

### What Gets Lost

The **token sequences** that surround function calls are never used:

```c
// parse.c par_subsh (line 1630)
/*
 * subsh : INPAR list OUTPAR | INBRACE list OUTBRACE ...
 */

static void par_subsh(int *cmplx) {
    // ... setup ...

    if (tok == INPAR) {                    // ← TOKEN 1 (lost!)
        zshlex();
        par_list(&c);                      // Function call (extracted)
        if (tok != OUTPAR)                 // ← TOKEN 2 (lost!)
            YYERRORV(oecused);
        zshlex();
    } else if (tok == INBRACE) {           // ← DIFFERENT BRANCH (lost!)
        zshlex();
        par_list(&c);                      // Same function (ambiguous!)
        if (tok != OUTBRACE)               // ← TOKEN 3 (lost!)
            YYERRORV(oecused);
        zshlex();
    }

    // ... cleanup ...
}
```

**Current Extraction Result:**

```json
{
    "subsh": {
        "$ref": "list"
    }
}
```

**Problem**: Lost information:

- ✗ INPAR/OUTPAR tokens never appear in rule
- ✗ INBRACE/OUTBRACE tokens never appear in rule
- ✗ Two distinct alternatives (INPAR vs INBRACE) merged into single reference
- ✗ Rule cannot be parsed by anyone unfamiliar with Zsh internals
- ✗ Semantic grammar comment "INPAR list OUTPAR | INBRACE list OUTBRACE" unrecoverable

**Example Failures:**

| Function    | Expected                                                        | Actual             | Gap  |
| ----------- | --------------------------------------------------------------- | ------------------ | ---- |
| `par_subsh` | `Union[Seq[INPAR, list, OUTPAR], Seq[INBRACE, list, OUTBRACE]]` | `{'$ref': 'list'}` | 100% |
| `par_if`    | `Seq[IF, list, THEN, list, FI]`                                 | `{'$ref': 'list'}` | 100% |
| `par_for`   | `Seq[FOR, word, DO, list, DONE]`                                | `{'$ref': 'list'}` | 100% |

---

## The Solution: Token-Sequence-Centric Architecture

### New Architecture (Phase 2.4.1)

```
┌─────────────────────┐
│   Parse.c source    │
└──────────┬──────────┘
           │
           ↓
┌──────────────────────────────────────────────┐
│  AST Analysis                                │
│  1. Extract control flow branches (if/else)  │
│  2. For each branch:                         │
│     - Walk AST within branch bounds          │
│     - Collect tokens in order                │
│     - Collect function calls in order        │
│     - Store with line numbers                │
│  3. Sort by line number (preserve order)     │
└──────────┬───────────────────────────────────┘
           │
           ↓
┌─────────────────────────────────────────────────────────┐
│  Token Sequence Extraction                              │
│  {func_name: [                                          │
│    {branch_id: 'if_1', items: [                         │
│      {kind: 'token', name: 'INPAR', seq_idx: 0},        │
│      {kind: 'call', name: 'par_list', seq_idx: 1},      │
│      {kind: 'token', name: 'OUTPAR', seq_idx: 2}        │
│    ]},                                                  │
│    {branch_id: 'else_if_1', items: [                    │
│      {kind: 'token', name: 'INBRACE', seq_idx: 0},      │
│      {kind: 'call', name: 'par_list', seq_idx: 1},      │
│      {kind: 'token', name: 'OUTBRACE', seq_idx: 2}      │
│    ]}                                                   │
│  ]}                                                     │
└──────────┬──────────────────────────────────────────────┘
           │
           ↓
┌─────────────────────────────────────────────────────────┐
│  Grammar Rule Generation                                │
│  FOR EACH branch:                                       │
│    1. Convert items to grammar nodes                    │
│    2. Token → Ref(TOKEN)                                │
│    3. Call → Ref(rule_name)                             │
│    4. Create Sequence or Union of alternatives          │
│                                                         │
│  RESULT: {                                              │
│    'subsh': {                                           │
│      'union': [                                         │
│        {'sequence': [                                   │
│          {'$ref': 'INPAR'},                             │
│          {'$ref': 'list'},                              │
│          {'$ref': 'OUTPAR'}                             │
│        ]},                                              │
│        {'sequence': [                                   │
│          {'$ref': 'INBRACE'},                           │
│          {'$ref': 'list'},                              │
│          {'$ref': 'OUTBRACE'}                           │
│        ]}                                               │
│      ]                                                  │
│    }                                                    │
│  }                                                      │
└─────────────────────────────────────────────────────────┘
```

### What Changes

**Information Preserved:**

- ✓ All tokens extracted in order
- ✓ Each branch as separate alternative
- ✓ Token-based dispatch visible (INPAR vs INBRACE)
- ✓ Semantic grammar comments reconstructable
- ✓ Rules are self-documenting

---

## Side-by-Side Comparison

### Example 1: par_subsh (Token-Based Dispatch)

#### Current (Broken)

```json
{
    "subsh": {
        "$ref": "list"
    }
}
```

**Problem**: Just calls list; no structure.

#### Target (Fixed)

```json
{
    "subsh": {
        "union": [
            {
                "sequence": [
                    { "$ref": "INPAR" },
                    { "$ref": "list" },
                    { "$ref": "OUTPAR" }
                ]
            },
            {
                "sequence": [
                    { "$ref": "INBRACE" },
                    { "$ref": "list" },
                    { "$ref": "OUTBRACE" }
                ]
            }
        ]
    }
}
```

**Benefit**: Clear: either `(list)` or `{list}`

---

### Example 2: par_if (Multiple Alternatives)

#### Current (Broken)

```json
{
    "if": {
        "$ref": "list"
    }
}
```

**Problem**: Calls list multiple times; structure hidden.

#### Target (Fixed)

```json
{
  "if": {
    "sequence": [
      {"$ref": "IF"},
      {"$ref": "cond"},
      {
        "union": [
          {"sequence": [{"$ref": "THEN"}, {"$ref": "list"}]},
          {"sequence": [{"$ref": "INBRACE"}, {"$ref": "list"}, {"$ref": "OUTBRACE"}]}
        ]
      },
      {"optional": {
        "union": [
          {"sequence": [{"$ref": "ELIF"}, {"$ref": "cond"}, ...]},
          {"sequence": [{"$ref": "ELSE"}, {"$ref": "list"}]}
        ]
      }},
      {"$ref": "FI"}
    ]
  }
}
```

**Benefit**: Full structure with IF/THEN/ELIF/ELSE/FI tokens visible.

---

### Example 3: par_for (Loop with Token Prefix)

#### Current (Broken)

```json
{
    "for": {
        "union": [{ "$ref": "list" }, { "$ref": "list" }]
    }
}
```

**Problem**: Two identical list calls; no FOR/WHILE/DO/DONE tokens.

#### Target (Fixed)

```json
{
    "for": {
        "sequence": [
            { "$ref": "FOR" },
            { "$ref": "word" },
            {
                "union": [
                    {
                        "sequence": [
                            { "$ref": "INPAR" },
                            { "repeat": { "$ref": "word" } },
                            { "$ref": "OUTPAR" }
                        ]
                    },
                    {
                        "sequence": [
                            { "$ref": "INPAR" },
                            { "$ref": "cond" },
                            { "repeat": { "$ref": "word" } }
                        ]
                    }
                ]
            },
            { "$ref": "DO" },
            { "repeat": { "$ref": "list" } },
            { "$ref": "DONE" }
        ]
    }
}
```

**Benefit**: Complete structure with all control tokens.

---

## Data Structure Evolution

### Current (Phase 1-3)

```python
class FunctionNode(TypedDict):
    name: str
    file: str
    line: int
    calls: list[str]  # ['par_list', 'par_cond']
    conditions: NotRequired[list[str]]

    # DEAD CODE (never used):
    token_edges: NotRequired[list[TokenEdge]]

# What we get:
# par_subsh = {
#   'calls': ['par_list'],
#   'token_edges': [{'token_name': 'INPAR', 'position': 'before', ...}]  # UNUSED
# }
```

### New (Phase 2.4.1)

```python
class ControlFlowBranch(TypedDict):
    branch_id: str  # 'if_1', 'else_if_1', 'loop'
    branch_type: Literal['if', 'else_if', 'else', 'switch_case', 'loop', 'sequential']
    condition: NotRequired[str]  # 'tok == INPAR' for if branches
    start_line: int
    end_line: int
    items: list[TokenOrCallEnhanced]  # ORDERED!

class FunctionNodeEnhanced(TypedDict):
    name: str
    file: str
    line: int
    calls: list[str]  # For validation

    # PRIMARY INPUT (NEW):
    token_sequences: list[ControlFlowBranch]
    has_loops: bool
    is_optional: bool

# What we get:
# par_subsh = {
#   'calls': ['par_list'],
#   'token_sequences': [
#     {
#       'branch_id': 'if_1',
#       'branch_type': 'if',
#       'condition': 'tok == INPAR',
#       'items': [
#         {'kind': 'token', 'token_name': 'INPAR', 'sequence_index': 0},
#         {'kind': 'call', 'func_name': 'par_list', 'sequence_index': 1},
#         {'kind': 'token', 'token_name': 'OUTPAR', 'sequence_index': 2}
#       ]
#     },
#     {
#       'branch_id': 'else_if_1',
#       'branch_type': 'else_if',
#       'condition': 'tok == INBRACE',
#       'items': [
#         {'kind': 'token', 'token_name': 'INBRACE', 'sequence_index': 0},
#         {'kind': 'call', 'func_name': 'par_list', 'sequence_index': 1},
#         {'kind': 'token', 'token_name': 'OUTBRACE', 'sequence_index': 2}
#       ]
#     }
#   ]
# }
```

**Key Differences:**

- ✓ `token_sequences` field: ordered, branched token/call sequences
- ✓ Each branch has distinct execution path
- ✓ Items ordered by line number (preserves execution order)
- ✓ Each item tagged with branch_id and sequence_index
- ✓ Condition extracted from if/switch statements

---

## Processing Flow Changes

### Current Rule Generation

```python
def _build_grammar_rules(parser_functions, call_graph):
    """Old: Iterate functions, look at calls"""
    for func_name, node in parser_functions.items():
        calls = node['calls']

        if len(calls) == 0:
            rule = {'empty': True}
        elif len(calls) == 1:
            rule = {'$ref': _function_to_rule_name(calls[0])}
        else:
            # Multiple calls: create union
            rule = {'union': [
                {'$ref': _function_to_rule_name(c)} for c in calls
            ]}

        rules[func_name] = rule

    return rules
```

**Problems:**

- Only looks at function names, ignores tokens
- Merges all calls into flat union (loses structure)
- Can't distinguish between different token-based dispatch

### New Rule Generation

```python
def build_grammar_rules(call_graph_enhanced, control_flows):
    """New: Iterate branches, convert sequences to rules"""
    for func_name, node in call_graph_enhanced.items():
        branches = node['token_sequences']

        # Convert each branch to a rule
        alternatives = []
        for branch in branches:
            alt = _convert_branch_to_rule(branch)
            alternatives.append(alt)

        # Union alternatives or return single
        if len(alternatives) == 1:
            rule = alternatives[0]
        else:
            rule = {'union': alternatives}

        rules[func_name] = rule

    return rules

def _convert_branch_to_rule(branch):
    """Convert token sequence to grammar rule"""
    items = branch['items']  # [tok1, call1, tok2, ...]

    nodes = []
    for item in items:
        if item['kind'] == 'token':
            nodes.append({'$ref': item['token_name']})
        elif item['kind'] == 'call':
            nodes.append({'$ref': _function_to_rule_name(item['func_name'])})

    if len(nodes) == 1:
        return nodes[0]
    else:
        return {'sequence': nodes}
```

**Benefits:**

- Respects token sequence ordering
- Each branch becomes distinct alternative
- Tokens appear in rule explicitly
- Self-documenting structure

---

## Execution Path Examples

### Example: par_subsh with Two Branches

**Source Code (parse.c, lines 1630-1665):**

```c
static void par_subsh(int *cmplx) {
    int oecused = ecused;

    if (tok == INPAR) {                    // Line 1634: Branch 1 condition
        zshlex();
        par_list(&c);                      // Line 1637: Call within branch 1
        if (tok != OUTPAR)
            YYERRORV(oecused);
        zshlex();
    } else if (tok == INBRACE) {           // Line 1641: Branch 2 condition
        zshlex();
        par_list(&c);                      // Line 1644: Call within branch 2
        if (tok != OUTBRACE)
            YYERRORV(oecused);
        zshlex();
    }
    // ... optional "always" block ...
}
```

**Phase 2.4.1 Extraction Process:**

**Stage 1: Extract Branches**

```
Function: par_subsh
├─ Branch 1:
│  ├─ branch_id: 'if_1'
│  ├─ branch_type: 'if'
│  ├─ condition: 'tok == INPAR'
│  └─ AST span: lines 1634-1639
└─ Branch 2:
   ├─ branch_id: 'else_if_1'
   ├─ branch_type: 'else_if'
   ├─ condition: 'tok == INBRACE'
   └─ AST span: lines 1641-1646
```

**Stage 2: Extract Tokens & Calls (Per Branch)**

For Branch 1 (INPAR case):

```
Walk AST between lines 1634-1639:
  Line 1634: Binary operator 'tok == INPAR' → TokenCheck
  Line 1637: Function call 'par_list' → FunctionCall
  Line 1638: Binary operator 'tok != OUTPAR' → ERROR GUARD (skip)

Items: [
  {kind: 'token', token_name: 'INPAR', line: 1634, seq_idx: 0, branch_id: 'if_1'},
  {kind: 'call', func_name: 'par_list', line: 1637, seq_idx: 1, branch_id: 'if_1'},
  {kind: 'token', token_name: 'OUTPAR', line: 1638, seq_idx: 2, branch_id: 'if_1'}
]
```

For Branch 2 (INBRACE case):

```
Walk AST between lines 1641-1646:
  Line 1641: Binary operator 'tok == INBRACE' → TokenCheck
  Line 1644: Function call 'par_list' → FunctionCall
  Line 1645: Binary operator 'tok != OUTBRACE' → ERROR GUARD (skip)

Items: [
  {kind: 'token', token_name: 'INBRACE', line: 1641, seq_idx: 0, branch_id: 'else_if_1'},
  {kind: 'call', func_name: 'par_list', line: 1644, seq_idx: 1, branch_id: 'else_if_1'},
  {kind: 'token', token_name: 'OUTBRACE', line: 1645, seq_idx: 2, branch_id: 'else_if_1'}
]
```

**Stage 3: Build Enhanced Call Graph**

```json
{
  "par_subsh": {
    "name": "par_subsh",
    "file": "parse.c",
    "line": 1630,
    "calls": ["par_list"],
    "token_sequences": [
      {
        "branch_id": "if_1",
        "branch_type": "if",
        "condition": "tok == INPAR",
        "items": [...from branch 1...]
      },
      {
        "branch_id": "else_if_1",
        "branch_type": "else_if",
        "condition": "tok == INBRACE",
        "items": [...from branch 2...]
      }
    ]
  }
}
```

**Stage 4: Generate Grammar Rules**

```python
# Process par_subsh
branches = call_graph_enhanced['par_subsh']['token_sequences']

# Convert branch 1 to rule
branch1_rule = _convert_branch_to_rule(branches[0])
# {
#   'sequence': [
#     {'$ref': 'INPAR'},
#     {'$ref': 'list'},
#     {'$ref': 'OUTPAR'}
#   ]
# }

# Convert branch 2 to rule
branch2_rule = _convert_branch_to_rule(branches[1])
# {
#   'sequence': [
#     {'$ref': 'INBRACE'},
#     {'$ref': 'list'},
#     {'$ref': 'OUTBRACE'}
#   ]
# }

# Union them
final_rule = {
  'union': [branch1_rule, branch2_rule]
}
```

**Final Grammar Output:**

```json
{
    "subsh": {
        "union": [
            {
                "sequence": [
                    { "$ref": "INPAR" },
                    { "$ref": "list" },
                    { "$ref": "OUTPAR" }
                ]
            },
            {
                "sequence": [
                    { "$ref": "INBRACE" },
                    { "$ref": "list" },
                    { "$ref": "OUTBRACE" }
                ]
            }
        ]
    }
}
```

---

## Error Handling Differences

### Current: Token vs Error Guard Confusion

```c
// In par_simple
if (tok != STRING)  // Error check
    YYERRORV(oecused);
// vs
if (tok == STRING)  // Semantic token
    // handle...
```

**Current extraction**: Might include error check token, contaminating grammar

### New: Explicit Error Guard Filtering

```python
def _is_error_guard(node: Cursor) -> bool:
    """Detect if token check is an error guard."""
    # Pattern: if (tok != EXPECTED) YYERROR(...)
    # Characteristics:
    # - Uses != operator
    # - Followed by YYERROR/YYERRORV
    # - No semantic content

    if '!=' not in token_spellings:
        return False

    # Check for YYERROR in then-clause
    has_error = any(
        t.spelling in ('YYERROR', 'YYERRORV')
        for t in then_clause_tokens
    )

    return has_error
```

**Result**: Error guards always filtered out; only semantic tokens extracted.

---

## Validation & Verification

### Current: No Validation

- ✗ Call graph never validated
- ✗ No check that extracted functions are actually called
- ✗ No verification against semantic grammar comments

### New: Multi-Layer Validation

**Layer 1: Branch Validation**

```python
def validate_branch(branch):
    """Check sequence indices are contiguous, lines monotonic"""
    indices = [item['sequence_index'] for item in branch['items']]
    assert indices == list(range(len(branch['items'])))

    lines = [item['line'] for item in branch['items']]
    assert lines == sorted(lines)
```

**Layer 2: Call Graph Consistency**

```python
def validate_call_graph_consistency(new, old):
    """Verify new extraction matches old calls field"""
    for func_name in old:
        old_calls = set(old[func_name]['calls'])
        new_calls = {
            item['func_name']
            for branch in new[func_name]['token_sequences']
            for item in branch['items']
            if item['kind'] == 'call'
        }
        assert old_calls == new_calls
```

**Layer 3: Schema Validation**

```python
jsonschema.validate(grammar, schema)
```

**Layer 4: Semantic Grammar Comparison**

```python
extracted_tokens = _extract_tokens_from_rule(rule)
expected_tokens = _extract_tokens_from_comment(comment)
match_score = len(overlap) / len(union)
```

---

## Summary of Shift

| Aspect                        | Current (Function-Centric)       | New (Token-Sequence-Centric)                                    |
| ----------------------------- | -------------------------------- | --------------------------------------------------------------- |
| **Primary Input**             | Call graph (what calls what)     | Token sequences (tokens surrounding calls)                      |
| **Data Granularity**          | Function-level                   | Branch-level (per if/else/case/loop)                            |
| **Token Information**         | Extracted but unused (dead code) | Central; drives rule structure                                  |
| **Ordering**                  | Not preserved                    | Preserved (line-number based)                                   |
| **Rule Generation**           | Flatten all calls to union       | Sequence within branch, union across branches                   |
| **Token-Based Dispatch**      | Not visible                      | Explicit (Union alternatives per token)                         |
| **Example: par_subsh**        | `{'$ref': 'list'}`               | `Union[Seq[INPAR, list, OUTPAR], Seq[INBRACE, list, OUTBRACE]]` |
| **Example: par_if**           | `{'$ref': 'list'}`               | `Seq[IF, cond, Union[...], THEN, list, FI]`                     |
| **Semantic Grammar Recovery** | 0% (impossible)                  | 80%+ (reconstructable)                                          |
| **Validation**                | None                             | 4-layer (branch, consistency, schema, semantic)                 |
