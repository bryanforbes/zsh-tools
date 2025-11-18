# construct_grammar.py Refactoring - Visual Architecture

## Module Organization

```
zsh_grammar/
├── construct_grammar.py          [~300 lines]  ← Types + Orchestration
│   ├── TypedDict: TokenEdge
│   ├── TypedDict: TokenCheck
│   ├── TypedDict: FunctionCall
│   ├── TypedDict: SyntheticToken
│   ├── TypedDict: FunctionNode
│   ├── TypedDict: ControlFlowPattern
│   ├── TypedDict: SemanticGrammarRule
│   ├── TypedDict: ValidationResult
│   ├── Union: TokenOrCall
│   ├── Const: PROJECT_ROOT
│   ├── main()                    ← Entry point
│   └── _construct_grammar()      ← Orchestration
│
├── ast_utilities.py              [95 lines]    ← Foundation Layer
│   ├── walk_and_filter()         PUBLIC
│   ├── extract_token_name()      PUBLIC
│   ├── find_function_definitions() PUBLIC
│   ├── find_cursor()             PUBLIC
│   ├── _find_child_cursors()     private
│   └── _find_all_cursors()       private
│
├── extraction_filters.py          [215 lines]   ← Classification
│   ├── is_data_token()           PUBLIC
│   ├── is_undocumented_token()   PUBLIC
│   ├── is_error_branch()         PUBLIC
│   ├── is_error_check_condition() PUBLIC
│   ├── normalize_internal_token() PUBLIC
│   └── _has_semantic_context()   private
│
├── function_discovery.py          [209 lines]   ← Discovery
│   ├── extract_parser_functions() PUBLIC
│   ├── get_dispatcher_keywords()  PUBLIC
│   ├── detect_state_assignment()  PUBLIC
│   ├── _is_parser_function()      private
│   ├── _filter_parser_functions() private
│   └── _parse_hash_entries()      private
│
├── token_extractors.py            [410 lines]   ← Extraction Patterns
│   ├── extract_token_sequences()  PUBLIC
│   ├── extract_synthetic_tokens() PUBLIC
│   ├── extract_error_guard_tokens() PUBLIC
│   ├── _extract_branch_items()    private
│   ├── _extract_if_branches()     private
│   ├── _extract_switch_branches() private
│   └── _extract_strcmp_string_value() private
│
├── control_flow.py                [330 lines]   ← Analysis
│   ├── analyze_control_flow()     PUBLIC
│   ├── analyze_all_control_flows() PUBLIC
│   ├── build_call_graph()         PUBLIC
│   ├── detect_cycles()            PUBLIC
│   ├── extract_lexer_state_changes() PUBLIC
│   └── _detect_conditions()       private
│
├── grammar_rules.py               [246 lines]   ← Building
│   ├── sequence_to_rule()         PUBLIC
│   ├── get_semantic_grammar_rules() PUBLIC
│   ├── build_grammar_rules()      PUBLIC
│   ├── embed_lexer_state_conditions() PUBLIC
│   ├── _function_to_rule_name()   private
│   └── _build_func_to_rule_map()  private
│
└── validation.py                  [110 lines]   ← Validation
    └── validate_semantic_grammar() PUBLIC
```

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│                  construct_grammar.py                       │
│              (Types + Main Orchestration)                   │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ function_discovery│  │ token_extractors │  │  control_flow    │
│  (extract funcs)  │  │ (pattern match)  │  │  (analysis)      │
└──────────────────┘  └──────────────────┘  └──────────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
            ┌──────────────────┐  ┌──────────────────┐
            │ ast_utilities    │  │ extraction_filters│
            │  (AST primitives)│  │  (classification) │
            └──────────────────┘  └──────────────────┘
                    │
                    ▼
            ┌──────────────────┐
            │  clang.cindex    │
            │   (C binding)    │
            └──────────────────┘


            ┌──────────────────┐      ┌──────────────────┐
            │  grammar_rules   │◄─────┤   validation     │
            │  (rule building) │      │  (confidence)    │
            └──────────────────┘      └──────────────────┘
                    │
                    ▼
            ┌──────────────────┐
            │ grammar_utils    │
            │  (grammar DSL)   │
            └──────────────────┘
```

## Data Flow Pipeline

```
Input: Zsh source code (parse.c, parse.syms)
   │
   ▼
┌──────────────────────────────────────────────────┐
│ function_discovery.extract_parser_functions()    │
│ → Dict[func_name, FunctionNode]                  │
└──────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────┐
│ token_extractors.extract_token_sequences()       │
│ + extract_synthetic_tokens()                     │
│ + extract_error_guard_tokens()                   │
│ → List[TokenOrCall] per function                 │
└──────────────────────────────────────────────────┘
   │
   ├──► extraction_filters.is_data_token()
   │    (filter semantic vs data tokens)
   │
   └──► token_extractors._extract_branch_items()
        (organize by execution branch)
   │
   ▼
┌──────────────────────────────────────────────────┐
│ control_flow.analyze_control_flow()              │
│ + build_call_graph()                             │
│ → Dict[func_name, ControlFlowPattern]            │
│ → Dict[func_name, List[calls]]                   │
└──────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────┐
│ grammar_rules.get_semantic_grammar_rules()       │
│ → Dict[func_name, SemanticGrammarRule]           │
└──────────────────────────────────────────────────┘
   │
   ├──► grammar_rules.sequence_to_rule()
   │    (convert token sequences to grammar)
   │
   └──► validation.validate_semantic_grammar()
        (compare against documented rules)
   │
   ▼
┌──────────────────────────────────────────────────┐
│ Output: GrammarNode dict + confidence scores     │
│ → Dict[rule_name, GrammarNode]                   │
│ → Dict[func_name, ValidationResult]              │
│ → overall_confidence: float                      │
└──────────────────────────────────────────────────┘
```

## Module Responsibilities at a Glance

| Module                 | Responsibility        | Key Operations                         | Audience             |
| ---------------------- | --------------------- | -------------------------------------- | -------------------- |
| **ast_utilities**      | Low-level AST walking | Cursor filtering, tree traversal       | Internal, foundation |
| **extraction_filters** | Token classification  | Data/structural distinction, filtering | Internal, extraction |
| **function_discovery** | Function metadata     | Discovery, signature parsing           | Internal, discovery  |
| **token_extractors**   | Pattern matching      | Token & call extraction                | External, core       |
| **control_flow**       | Structure analysis    | Loop/conditional detection             | External, analysis   |
| **grammar_rules**      | Rule construction     | Token sequence → grammar               | External, building   |
| **validation**         | Confidence scoring    | Rule comparison, metrics               | External, validation |

## Code Metrics

### Line Count Distribution

```
ast_utilities.py      |████ 95       (5%)
extraction_filters.py |███████████ 215     (11%)
function_discovery.py |███████████ 209     (11%)
token_extractors.py   |███████████████████ 410     (21%)
control_flow.py       |████████████████ 330       (17%)
grammar_rules.py      |████████████ 246         (13%)
validation.py         |██ 110                (6%)
construct_grammar.py  |███████████████ ~300      (16%)
                      └────────────────────────────
                      Total: ~1915 lines (refactored)
```

### Function Count Distribution

```
ast_utilities.py      |██ 4 public        (15%)
extraction_filters.py |██ 5 public        (19%)
function_discovery.py |██ 3 public        (12%)
token_extractors.py   |██ 3 public        (12%)
control_flow.py       |███ 5 public       (19%)
grammar_rules.py      |██ 4 public        (15%)
validation.py         |█ 1 public         (4%)
                      └────────────────────────────
                      Total: 26 public functions
```

## Import Statements (Before Refactoring)

```python
# Monolithic construct_grammar.py had to import everything:
import json, os, re, subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import ...
import jsonschema
from clang.cindex import Cursor, CursorKind, StorageClass, Token
from zsh_grammar.grammar_utils import (...)
from zsh_grammar.source_parser import ZshParser
```

## Import Statements (After Refactoring)

```python
# ast_utilities.py
from clang.cindex import Cursor, CursorKind

# extraction_filters.py
from clang.cindex import Token

# function_discovery.py
import re
from pathlib import Path

# token_extractors.py
from clang.cindex import CursorKind, Cursor, Token
from zsh_grammar.ast_utilities import walk_and_filter
from zsh_grammar.extraction_filters import (is_data_token, is_undocumented_token, ...)

# control_flow.py
from clang.cindex import CursorKind
from zsh_grammar.ast_utilities import find_function_definitions, walk_and_filter
from zsh_grammar.function_discovery import _is_parser_function, detect_state_assignment

# grammar_rules.py
from zsh_grammar.function_discovery import _is_parser_function
from zsh_grammar.grammar_utils import (create_ref, create_sequence, ...)

# validation.py
from zsh_grammar.grammar_rules import get_semantic_grammar_rules

# construct_grammar.py
from argparse import ArgumentParser
import json, os, re, subprocess
from pathlib import Path
from zsh_grammar import (
    ast_utilities, extraction_filters, function_discovery,
    token_extractors, control_flow, grammar_rules, validation
)
```

## Benefits of Refactoring

### ✓ Easier Testing

```python
# Before: Had to import and test 3920-line monolith
import construct_grammar  # Loads everything

# After: Test individual modules
import extraction_filters
# Test only token classification logic (215 lines)

import control_flow
# Test only control flow analysis (330 lines)
```

### ✓ Improved Reusability

```python
# After: Can use ast_utilities in other projects
from zsh_grammar.ast_utilities import walk_and_filter

# Extract tokens for a different language parser
def extract_my_tokens(cursor):
    for binary_op in walk_and_filter(cursor, CursorKind.BINARY_OPERATOR):
        # Custom extraction logic
```

### ✓ Clearer Responsibilities

```
# Before: 90+ functions in one file
# Which ones are for filtering? Which for extraction? Unclear.

# After: Purpose is immediately clear from module name
from token_extractors import extract_token_sequences  # "I extract"
from extraction_filters import is_data_token          # "I filter"
from control_flow import analyze_control_flow         # "I analyze"
```

### ✓ Reduced Cognitive Load

```
# Instead of understanding 3920 lines:
ast_utilities         (95 lines)   ← Foundation
  ↓
extraction_filters    (215 lines)  ← Classification
  ↓
token_extractors      (410 lines)  ← Extraction
  ↓
control_flow          (330 lines)  ← Analysis
  ↓
grammar_rules         (246 lines)  ← Building
  ↓
validation            (110 lines)  ← Validation
```

---

**Status**: Refactoring complete. All modules verified and importable. Ready for integration testing.
