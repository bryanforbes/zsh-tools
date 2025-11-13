# Plan: Automatic Extraction of Modular Zsh Grammar

## Overview

This document outlines a concrete plan for automatically extracting a modular Zsh grammar that conforms to the `canonical-grammar.schema.json` specification. The grammar extraction will leverage static analysis of the Zsh source code (`vendor/zsh/Src`) to identify parsing symbols, construct call graphs, and build a comprehensive grammar model.

## Current State

- **Schema**: `zsh-grammar/canonical-grammar.schema.json` defines the grammar structure with:
  - Language definitions (symbol names must start with uppercase)
  - Grammar node types: Optional, Terminal, Union, Sequence, Repeat, Ref, Variant, Condition
- **Existing Implementation**: `zsh-grammar/src/zsh_grammar/construct_grammar.py` has:
  - `ZshParser`: Uses libclang to parse C source files with preprocessing
  - `_build_token_mapping()`: Extracts token definitions from enums and arrays
  - Token mapping from `lex.c` and `zsh.h` (already functional)
  - Placeholder code for `_build_call_graph()` and `_build_grammar_rules()` (commented out)

## Phase 1: Identify Core Parsing Symbols

### 1.1 Extract Parser Functions
**Objective**: Identify all parser entry points and core parsing functions.

**Implementation**:
1. Parse `parse.c` using libclang to identify all functions matching the pattern `par_*` and `parse_*`
2. Extract function signatures, return types, and parameters
3. Current known functions (from `vendor/zsh/Src/parse.syms`):
   - Entry points: `parse_list()`, `parse_event()`, `parse_cond()`
   - Top-level: `par_event()`, `par_list()`, `par_list1()`, `par_sublist()`, `par_sublist2()`, `par_pline()`
   - Control structures: `par_cmd()`, `par_for()`, `par_case()`, `par_if()`, `par_while()`, `par_repeat()`
   - Compound commands: `par_subsh()`, `par_funcdef()`, `par_time()`, `par_dinbrack()`
   - Simple commands: `par_simple()`, `par_redir()`, `par_wordlist()`, `par_nl_wordlist()`
   - Conditionals: `par_cond()`, `par_cond_1()`, `par_cond_2()`, `par_cond_double()`, `par_cond_triple()`, `par_cond_multi()`

**Output**: List of `_FunctionNode` objects with name, file, line, and signature.

### 1.2 Identify Grammar Symbols from Switch/Case Statements
**Objective**: Map parser functions to the grammar symbols they recognize.

**Implementation**:
1. Use libclang to analyze switch statements in `par_cmd()` and other dispatcher functions
2. Extract token types matched in case statements (e.g., `case FOR:`, `case CASE:`, `case IF:`)
3. For each token type matched, create a grammar symbol name based on naming convention:
   - `FOR` → `For` (capitalize first letter)
   - `DINBRACK` → `DinBrack` (camelCase from SCREAMING_SNAKE_CASE)
4. Record which parser function handles each symbol

**Output**: Symbol-to-handler mapping table.

### 1.3 Extract Token-to-String Mapping
**Objective**: Map internal token types to their literal syntax strings.

**Implementation**:
1. The token mapping is already extracted in `_build_token_mapping()` from:
   - Token enum in `zsh.h` → token names and values
   - Hash table entries in `hashtable.c` (`reswds`) → token keywords
   - Token strings in `lex.c` (`tokstrings`) → token literal text
2. Enhance to handle:
   - Multi-value tokens (e.g., `TYPESET` matches multiple keywords)
   - Pattern-based tokens vs. literal string tokens

**Output**: Dictionary mapping token names to their terminal representations.

## Phase 2: Construct Parser Call Graph

### 2.1 Build Complete Call Graph
**Objective**: Extract all function calls within parser functions to understand composition.

**Implementation**:
1. The `_build_call_graph()` function already exists but is commented out
2. Walk the AST of each `par_*` function using libclang
3. For each `CALL_EXPR`, extract:
   - Caller function name
   - Callee function name
   - Call location (line number)
4. Filter to keep only internal `par_*` and `parse_*` calls
5. Detect conditional context (calls inside `if`, `switch`, `while` blocks)

**Output**: Call graph as `dict[str, _FunctionNode]` with `calls` list.

### 2.2 Analyze Call Patterns
**Objective**: Classify parser functions by their calling patterns.

**Implementation**:
1. For each parser function, categorize by call pattern:
   - **Leaf/Terminal**: No internal `par_*` calls → base token or terminal pattern
   - **Sequential**: Single unique `par_*` call → direct composition
   - **Conditional/Union**: Multiple unique `par_*` calls → alternatives based on context
   - **Iterative**: Recursive call to itself or looping calls → repetition
2. Use control flow analysis to distinguish:
   - Mutually exclusive calls (inside switch/if) → union
   - Sequential calls (one after another) → sequence
   - Conditional calls (inside if with no else) → optional
   - Loop calls (inside while/for) → repeat

**Output**: Classification of each function with inferred rule type.

### 2.3 Detect Contextual Options
**Objective**: Identify which parser behavior depends on shell options.

**Implementation**:
1. In `_detect_conditions()`, extract references to:
   - `isset(OPTION)` macro calls
   - Direct option constant names (e.g., `EXTENDED_GLOB`)
2. Build a mapping of `par_*` functions → list of option conditions
3. Examples from `parse.c`:
   - Functions that change behavior with `EXTENDED_GLOB`, `KSH_ARRAYS`, etc.

**Output**: Dictionary mapping functions to their conditional behavior flags.

## Phase 3: Build Grammar Rules from Call Graph

### 3.1 Generate Rule Definitions
**Objective**: Transform call graph patterns into grammar rule definitions.

**Implementation**:
1. For each `par_*` function, generate a `GrammarNode`:
   ```
   Name = {Inferred Node Type}
   ```
2. Rule generation logic:
   - **Leaf functions** → Create terminal pattern or reference to token
   - **Single-call functions** → `create_sequence()` wrapping the called function
   - **Multi-call functions** → `create_union()` of called functions
   - **Recursive functions** → `create_repeat()` wrapping base call
3. Handle special cases:
   - `par_redir()` → Handles redirections, should be optional in many contexts
   - `par_simple()` → Complex dispatcher, may need multiple union alternatives
   - Conditional variants → Use `create_variant()` with option conditions

**Output**: Complete `Language` dictionary with symbol definitions.

### 3.2 Construct Symbol References
**Objective**: Create proper inter-symbol references using the `$ref` mechanism.

**Implementation**:
1. When a function calls another parser function, generate a reference:
   - `par_list()` calls `par_sublist()` → `{'$ref': 'ParSublist'}`
2. Handle scoped references if needed for future multi-language support:
   - `{'$ref': '/modulename/SymbolName'}`
3. Maintain a symbol table during generation to ensure all references exist

**Output**: Grammar with properly resolved symbol references.

### 3.3 Infer Optional and Repetition Patterns
**Objective**: Add structural annotations for optional and repeated elements.

**Implementation**:
1. Analyze return types and conditional logic:
   - Functions returning success/failure → Likely optional
   - Functions inside loops → Likely repeated
2. Use control flow hints:
   - Code patterns like `while (par_something()) { ... }` → `repeat1`
   - Code patterns like `if (par_something()) { ... }` → optional
3. Enhance `_build_grammar_rules()` to:
   - Detect and wrap called functions with `create_optional()`
   - Detect and wrap called functions with `create_repeat()` or `create_repeat(..., one=True)`

**Output**: Grammar with proper optional and repetition annotations.

## Phase 4: Handle Complex Cases

### 4.1 Manage Token vs. Symbol Distinction
**Objective**: Properly categorize whether a grammar element is a terminal token or a non-terminal symbol.

**Implementation**:
1. Create two symbol categories:
   - **Tokens** (from token mapping): Single letter, keywords, operators → Direct strings
   - **Symbols** (from call graph): Parser functions → References to other symbols
2. Mix them appropriately:
   - When token appears in token mapping → Use terminal
   - When only parser function exists → Use `$ref`
   - When both exist → Determine precedence (prefer token for literals)

**Output**: Proper categorization in final grammar.

### 4.2 Handle Ambiguous Function Names
**Objective**: Resolve naming conflicts and create readable symbol names.

**Implementation**:
1. Convert function names to grammar symbol names:
   - `par_for` → `For`
   - `par_case` → `Case`
   - `par_cond_double` → `CondDouble`
2. For multi-word conditions:
   - `par_cond_1` → `Cond1` (or `CondOne` with number expansion)
3. Ensure uniqueness and avoid conflicts with token names
4. Create an alias table if migration needed

**Output**: Consistent symbol naming scheme.

### 4.3 Incorporate Lexer State
**Objective**: Account for parser context flags that affect parsing.

**Implementation**:
1. From `parse.c`, extract parser context flags:
   - `incmdpos` (in command position)
   - `incond` (inside `[[ ... ]]`)
   - `inredir` (after redirection)
   - `incasepat` (in case pattern)
   - `infor`, `inrepeat_`, `intypeset`
2. These flags affect parser behavior and should be modeled as conditions
3. Add `Condition` nodes to grammar rules where flags affect parsing:
   - Use `create_variant()` for option-dependent rules

**Output**: Grammar rules with conditional variants.

## Phase 5: Build and Validate Complete Grammar

### 5.1 Assemble Grammar Structure
**Objective**: Combine all extracted elements into final grammar object.

**Implementation**:
1. Merge:
   - Token mapping (terminals) from Phase 1
   - Parser symbols from Phase 3
   - Special constructs (Parameter, Variable, etc.)
2. Create root `Grammar` object:
   ```python
   grammar: Grammar = {
       'languages': {
           'core': {
               # All extracted symbols and tokens
           }
       },
       'zsh_version': version_from_makefile,
       'zsh_revision': git_commit_hash,
   }
   ```
3. Maintain the existing manual definitions if still needed

**Output**: Complete `Grammar` object ready for serialization.

### 5.2 Validate Against Schema
**Objective**: Ensure generated grammar conforms to the schema.

**Implementation**:
1. Load `canonical-grammar.schema.json`
2. Use `jsonschema` library to validate:
   - Property names follow naming rules (uppercase starting)
   - All referenced symbols exist
   - No circular dependencies
3. Report validation errors with file/line references
4. Provide suggestions for fixing schema violations

**Output**: Validated grammar object or detailed error report.

### 5.3 Manual Review and Enhancement
**Objective**: Refine automatically-generated grammar with manual improvements.

**Implementation**:
1. Compare generated grammar with manually-created sections
2. Preserve high-quality manual definitions where they exist
3. Merge auto-generated content with manually-curated content
4. Document which parts are auto-generated vs. manual

**Output**: Final grammar ready for use.

## Implementation Details

### File Structure
```
zsh-grammar/
├── src/zsh_grammar/
│   ├── construct_grammar.py      (main entry point, enhanced)
│   ├── source_parser.py          (libclang parsing - done)
│   ├── grammar_utils.py          (helper functions - done)
│   ├── _types.py                 (TypedDicts - done)
│   └── call_graph.py             (NEW: call graph analysis)
├── canonical-grammar.schema.json
├── canonical-grammar.json        (output)
└── pyproject.toml
```

### Key Functions to Implement/Enhance

1. **`_build_call_graph()` (uncomment and fix)**
   - Parse all `.c` files
   - Build call graph with proper filtering

2. **`_analyze_control_flow(cursor: Cursor) -> dict`** (NEW)
   - Detect if calls are conditional, sequential, or looped
   - Return classification for each call

3. **`_build_grammar_rules()` (complete implementation)**
   - Transform call patterns into grammar nodes
   - Handle special cases and complex patterns

4. **`_extract_parser_symbols()` -> dict[str, ParserFunction]` (NEW)
   - Identify all `par_*` functions
   - Extract signatures and documentation

5. **`_map_tokens_to_symbols()` -> dict[str, str]` (NEW)**
   - Link token constants to parser functions
   - Handle multi-token cases

6. **`validate_grammar(grammar: Grammar) -> list[str]`** (NEW)
   - Check schema compliance
   - Verify all references exist
   - Return list of errors or empty

### Data Flow

```
vendor/zsh/Src/ (C source)
    ↓ [parse with libclang]
    ↓
Parse Tree
    ├→ [extract functions] → Parser Functions
    ├→ [extract tokens] → Token Mapping
    └→ [build call graph] → Call Graph
         ↓
    [analyze patterns] → Classifications
         ↓
    [generate rules] → Grammar Nodes
         ↓
    [validate] → Validated Grammar
         ↓
canonical-grammar.json
```

## Success Criteria

1. **Completeness**: Extract all major parsing functions (20+ symbols minimum)
2. **Accuracy**: Call graph correctly identifies function relationships
3. **Schema Compliance**: Generated grammar passes JSON schema validation
4. **Maintainability**: Extraction is reproducible when Zsh source updates
5. **Documentation**: Process is documented and understood by other developers

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| libclang preprocessing fails | Cannot extract C structure | Handle gracefully, document requirements |
| Complex control flow not analyzed | Incorrect rule inference | Manual review and annotation of complex functions |
| Token name conflicts | Grammar ambiguity | Implement conflict detection and resolution |
| Performance on large call graph | Slow extraction | Cache intermediate results, optimize traversal |
| Schema changes | Regeneration breaks | Version schema, maintain backward compatibility |

## Testing and Validation

1. **Unit Tests**: Test each extraction function independently
2. **Integration Tests**: Run full pipeline and validate output
3. **Comparison Tests**: Compare with manually-created grammar sections
4. **Performance Tests**: Ensure extraction completes in reasonable time
5. **Regression Tests**: Verify grammar remains valid across Zsh versions

## Future Enhancements

1. **Multiple Languages**: Extend to extract math grammar, condition grammar, etc.
2. **Interactive Mode**: Allow manual symbol addition/annotation during extraction
3. **Visualization**: Generate call graph diagrams and grammar tree visualizations
4. **Incremental Updates**: Only re-extract changed functions on source updates
5. **Grammar Optimization**: Simplify generated grammar by extracting common patterns
