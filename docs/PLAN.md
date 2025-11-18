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

### Prerequisites

**Objective**: Ensure `.syms` files are available for parsing.

**Implementation**:

If `.syms` files don't exist in `vendor/zsh/Src/`, generate them by running:

```bash
mise //vendor:prepare
```

This task will generate the necessary `.syms` files from the Zsh source code, enabling Phase 1 extraction.

### 1.1 Extract Parser Functions

**Objective**: Identify all parser entry points and core parsing functions.

**Implementation**:

1. Parse `.syms` files (primarily `vendor/zsh/Src/parse.syms`) to extract function declarations
2. Lines prefixed with `L` (static) and `E` (extern) contain function declarations
3. Extract function name, signature, and visibility from each declaration:
    - Example line: `Lstatic void par_for _((int*cmplx));` → name: `par_for`, signature: `(int*cmplx) → void`, visibility: static
4. For each parser function, record: name, parameters, return type, visibility
5. No libclang preprocessing needed for this step—simple text parsing suffices
6. Functions extracted from `parse.syms` (lines 33-60):
    - Entry points: `parse_list()`, `parse_event()`, `parse_cond()`
    - Top-level: `par_event()`, `par_list()`, `par_list1()`, `par_sublist()`, `par_sublist2()`, `par_pline()`
    - Control structures: `par_cmd()`, `par_for()`, `par_case()`, `par_if()`, `par_while()`, `par_repeat()`
    - Compound commands: `par_subsh()`, `par_funcdef()`, `par_time()`, `par_dinbrack()`
    - Simple commands: `par_simple()`, `par_redir()`, `par_wordlist()`, `par_nl_wordlist()`
    - Conditionals: `par_cond()`, `par_cond_1()`, `par_cond_2()`, `par_cond_double()`, `par_cond_triple()`, `par_cond_multi()`

**Output**: List of `FunctionNode` objects with name, file, line, signature, and visibility.

### 1.2 Identify Grammar Symbols from Switch/Case Statements

**Objective**: Map parser functions to the grammar symbols they recognize.

**Note**: Function extraction (1.1) is now independent of this step via `.syms` files. This section focuses on mapping tokens to functions and extracting dispatcher logic via AST analysis.

**Implementation**:

1. Use libclang to analyze switch statements in `par_cmd()` and other dispatcher functions
2. Extract token types matched in case statements (e.g., `case FOR:`, `case CASE:`, `case IF:`)
3. For grammar symbol names:
    - **Tokens**: Keep as SCREAMING_SNAKE_CASE (e.g., `FOR`, `DINBRACK`, `WORD`)
    - **Rules** (from `par_*` functions): Remove `par_` prefix and convert to lower_snake_case
        - `par_for` → `for`
        - `par_case` → `case`
        - `par_cond_double` → `cond_double`
        - `par_cmd` → `cmd`
4. Record which parser function handles each symbol (mapping token → handler rule)
5. **Prove completeness**:
    - Cross-reference all extracted symbols against `vendor/zsh/Src/parse.syms`
    - Grep source for pattern `case [A-Z_]*:` to catch all case statements
    - Verify no symbols are silently omitted
    - Document any functions referenced via function pointers (not direct calls)
6. **Context-sensitive token examples**:
    - `[[ ]]` uses different token matchers than `[ ]` (double bracket vs. single)
    - Parameter expansion `${}` syntax differs inside vs. outside quotes
    - Math context `(( ))` tokenizes operators differently than command position
    - Brace expansion `{}` vs. subshell `()` disambiguation

**Output**: Token-to-rule mapping table showing which tokens (SCREAMING_SNAKE_CASE) map to which grammar rules (lower_snake_case, with completeness validation report).

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

**Output**: Dictionary mapping token names (SCREAMING_SNAKE_CASE) to their terminal string representations. Tokens become first-class grammar symbols that rules will reference via `$ref`.

### 1.4 Preprocess Token Analysis

**Objective**: Extract hash table-based tokens and pattern-based matches beyond simple enums.

**Implementation**:

1. Extract `reswds` hash table from `hashtable.c`:
    - Hash entries map keywords to token values
    - Some keywords map to same token (e.g., TYPESET from `declare`, `export`, `float`, `integer`, `local`, `readonly`, `typeset`)
    - Parse the `builtintab` structure to identify keyword → token mappings
2. **Document runtime token registration scope**:
    - Zsh conditionally adds keywords via `addhashnode()` based on loaded builtins
    - This plan assumes static tokens from compiled-in keywords
    - **Limitation**: Runtime-configured tokens (from dynamically loaded modules) are out of scope
    - Document which tokens are optional based on build configuration
3. Extract pattern-based tokens from lexer:
    - Tokens matched by regex patterns (FIRST, SECOND, etc.) not literal strings
    - Parse tokenization logic in `lex.c` to identify pattern matchers
4. Handle multi-value tokens:
    - Create mapping: `{ TYPESET: ["declare", "export", "float", "integer", "local", "readonly", "typeset"] }`
    - These will be represented with `matches` array in final grammar (not union nodes)

**Output**: Enhanced token mapping with multi-value support, pattern-based tokens, and documented limitations.

### 1.5 Extract Lexer State Dependencies

**Objective**: Document which parser functions require which lexer states and how states transition.

**Implementation**:

1. From `lex.c`, identify lexer state flags:
    - `INCMDPOS` (in command position): affects which tokens are keywords
    - `INCOND` (inside `[[ ... ]]`): changes token matching rules
    - `INREDIR` (after redirection operator): prevents keyword recognition
    - `INCASEPAT` (in case pattern): affects glob pattern parsing
    - `INFOR`, `INREPEAT`, `INTYPESET`: modify keyword context
    - `IN_MATH`, `IN_ARRAY`, `IN_SUBSTITUTION`, `IN_BRACEEXP`, `IN_GLOBPAT`: expansion contexts
2. Analyze `parse.c` for state management:
    - Which `par_*` functions set/reset states at entry/exit
    - Example: `par_subsh()` sets `incmdpos = 1` for subshell body
    - Example: `par_cond()` sets `incond = 1` inside `[[ ... ]]`
3. Build state dependency map:
    - For each `par_*` function, list which states must be active
    - For each token matcher, list which states enable/disable it
4. Document state-dependent parsing:
    - Same token may parse differently depending on active state
    - This is core to correctness but not captured by call graph alone

**Output**: State dependency map showing which functions require which lexer states.

### 1.6 Preprocessor Strategy

**Objective**: Document how to handle C preprocessing and feature-conditional code.

**Implementation**:

1. **Scope of preprocessing**:
    - Preprocessing needed only for Phase 2 (call graph) and Phase 4 (complex cases)
    - Phase 1 (function extraction) uses `.syms` files—no preprocessing needed
    - Decision: Include all compiled-in features for call graph accuracy
2. **Zsh source availability**:
    - Function extraction requires only `.syms` text files (portable, version-independent)
    - Full AST analysis (call graphs, control flow) requires preprocessed/fully-featured Zsh source
3. **Preprocessor invocation** (for call graph extraction only):
    - Use libclang with full preprocessing for Phase 2
    - Use `CXIndex_SkipFunctionBodies=False` to preserve full AST
    - Pass all `-D` flags from Zsh's `config.h` during parsing
    - Handle `#ifdef` blocks by extracting all conditional paths
4. **Document assumptions**:
    - `.syms` parsing requires no special preprocessing
    - AST-based call graph analysis assumes fully featured build
    - Feature-minimal builds may have different grammar
    - Version-specific parsing happens via Conditions, not code exclusion

**Output**: Preprocessor configuration and build assumptions documented.

## Phase 2: Construct Parser Call Graph

### 2.1 Build Complete Call Graph

**Objective**: Extract all function calls within parser functions to understand composition.

**Why libclang here**: Unlike function extraction (which uses `.syms` files), call graphs require full AST analysis to identify call expressions within function bodies. Text-based parsing cannot capture this control flow information.

**Implementation**:

1. Parser functions already identified from Phase 1 (via `.syms`)
2. Walk the AST of each `par_*` function using libclang
3. For each `CALL_EXPR`, extract:
    - Caller function name
    - Callee function name
    - Call location (line number)
4. Filter to keep only internal `par_*` and `parse_*` calls
5. Detect conditional context (calls inside `if`, `switch`, `while` blocks)

**Output**: Call graph as `dict[str, FunctionNode]` with `calls` list.

### 2.2 Analyze Call Patterns

**Objective**: Classify parser functions by their calling patterns with concrete examples.

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
3. **Concrete code examples from `parse.c`**:
    - **Leaf example**: `par_getword()` - directly matches tokens, no `par_*` calls
    - **Sequential example**: `par_list()` calls `par_sublist()` unconditionally
    - **Conditional/Union example**: `par_cmd()` has `switch(tok)` with multiple `case` statements, each calling different `par_*` function
    - **Iterative example**: `par_list1()` contains `while (tok == SEPER) par_pline()` - recursive repetition

**Output**: Classification of each function with inferred rule type and source code references.

### 2.3 Detect and Handle Recursion Cycles

**Objective**: Identify and safely handle recursive/cyclic parser function calls.

**Implementation**:

1. Detect cycles in call graph:
    - Use depth-first search (DFS) from each function to find back edges
    - Common cycles in Zsh: `par_list()` → `par_sublist()` → `par_pline()` → `par_cmd()` → `par_list()`
2. Classify cycle types:
    - **Direct recursion**: `par_something()` calls itself
    - **Mutual recursion**: Function A calls B, B calls A
    - **Indirect cycles**: Chains longer than 2 functions
3. Handling strategy:
    - Mark cyclic calls with `{$ref}` to create acyclic DAG (directed acyclic grammar)
    - For direct recursion, model as `Repeat` with base case detection
    - For mutual recursion, break at the least important link (determined by frequency analysis)
4. Document cycle structure:
    - Create a cycle report mapping back-edges to grammar choices

**Output**: Call graph with cycles identified and break-points selected.

### 2.4 Extract Direct Token Consumption Patterns

**Objective**: Identify and capture tokens that are consumed directly within parser functions (not delegated to other functions), and reconstruct token-sequence-based grammar from AST control flow.

**Critical Insight**: The semantic grammar comments in `parse.c` (lines 1604-1611, etc.) describe **token sequences**, not function call graphs. Example: `par_subsh()` has semantic grammar:

```
subsh : INPAR list OUTPAR | INBRACE list OUTBRACE [ "always" INBRACE list OUTBRACE ]
```

This documents three critical elements:

1. Token sequences wrapping function calls: `INPAR` + `list` + `OUTPAR`
2. Token-based alternatives: `INPAR...OUTPAR` **vs** `INBRACE...OUTBRACE` (not function alternatives)
3. Token-based conditionals: `[ "always" ... ]` (the optional "always" block depends on matching STRING token "always")

**Why current approach fails**: Function call graphs cannot reconstruct these patterns because:

- `par_list` is called unconditionally, but its wrapper tokens (`INPAR`/`INBRACE`) are token-dependent alternatives
- The "always" keyword is a STRING token match, not a function call—control flow analysis sees `if (tok == STRING && !strcmp(...))` but doesn't extract the semantic relationship
- Token consumption order relative to function calls is invisible to call graph alone

**Implementation**:

1. **Token-to-Call Sequencing** (Phase 2.4.1):
    - For each parser function, walk AST preorder and record all `tok == TOKEN` checks and `par_*()` calls in execution order
    - Build timeline: `[tok==INPAR, par_list(), tok==OUTPAR] | [tok==INBRACE, par_list(), tok==OUTBRACE]`
    - Group tokens by control flow branch (if/else, switch cases)

2. **Reconstruct Semantic Grammar Comments**:
    - Extract leading C comment from each `par_*` function definition
    - Parse grammar notation: `rule : alternative1 | alternative2 [ optional ]`
    - Match extracted token sequences against documented grammar to validate extraction
    - For functions without comments, synthesize grammar from extracted sequences

3. **Token-Based Dispatch**:
    - Identify where token values (not function calls) determine control flow: `if (tok == INPAR) ... else if (tok == INBRACE) ...`
    - Model as Union where alternatives are selected by token value, not function name
    - Create Union nodes with token conditions, not function references

4. **Handle String Matching**:
    - Keywords like "always" are matched via `tok == STRING && !strcmp(tokstr, "always")`
    - These are control flow conditionals, not parsed tokens
    - Model as Optional wrapped with condition matching STRING token with specific content

5. **Tail-Call vs Function Call Distinction**:
    - Some token consumption happens after calling a function: `par_list(); if (tok == OUTPAR) ...`
    - These are suffix tokens (wrap rule with `Sequence[ref(called_rule), ref(suffix_token)]`)
    - Distinguish from prefix tokens (come before function call)

**Example for `par_subsh` (lines 1615-1659)**:

Extract from AST:

```
Function par_subsh:
  Line 1617: enum lextok otok = tok;  # Save initial token
  Line 1623: zshlex();                # Consume token

  Branch 1 (if otok == INPAR):
    Sequence: tok==INPAR, par_list(), tok==OUTPAR

  Branch 2 (else - otok == INBRACE):
    Sequence: tok==INBRACE, par_list(), tok==OUTBRACE
    Optional: tok==STRING("always"), tok==INBRACE, par_save_list(), tok==OUTBRACE
```

Reconstruct as:

```
subsh: Union[
  Sequence[INPAR, list, OUTPAR],
  Sequence[INBRACE, list, OUTBRACE, Optional[Sequence[ALWAYS, INBRACE, list, OUTBRACE]]]
]
```

Where `ALWAYS` is a synthetic token derived from STRING matching "always".

**Output**: Function nodes extended with `token_sequences` field containing ordered list of (token_name or function_call) elements per control flow branch.

**Critical Gap**: The grammar extraction currently produces only parser function call references, missing the token sequences documented in grammar comments. This means:

- Semantic grammar: `INPAR list OUTPAR | INBRACE list OUTBRACE [ "always" ... ]` (from line 1605 comment)
- Extracted grammar: `$ref: list` only (missing token envelope)

**Implementation**:

1. For each parser function, analyze token consumption patterns:
    - Identify `tok == TOKEN_NAME` conditionals and assignments
    - Identify `zshlex()` calls to advance the token stream
    - Track sequence: token check → function call(s) → token check
    - Detect guards: tokens checked conditionally for control flow
2. Build token-aware parse sequences:
    - Pattern: `tok == INPAR; par_list(); tok == OUTPAR` → Sequence `[INPAR, list, OUTPAR]`
    - Pattern: `(tok == INPAR || tok == INBRACE); par_list()` → Union with token-dependent wrapping
    - Pattern: `if (tok == ALWAYS) { ... par_list() ... }` → Optional sequence
    - Pattern: `while (tok == SEPER) { ... }` → Repeated sequence of tokens
3. Enhance call graph representation:
    - Extend `FunctionNode` with new fields:
        - `token_prefix`: List of tokens consumed before nested call
        - `token_suffix`: List of tokens consumed after nested call
        - `token_checks`: List of conditional token checks affecting control flow
    - Create `TokenEdge` type to represent direct token consumption (separate from function calls)
4. Integrate tokens into grammar rules:
    - When building rules from call graph, prepend/append token sequences
    - Convert token sequences to Sequence or Repeat nodes in grammar
    - Apply control flow analysis to sequences (optional wrapping, repetition)

**Output**: Extended call graph with token consumption metadata; token-aware parse tree patterns for each function; ability to reconstruct full grammar from tokens + function calls.

### 2.3.5 Distinguish Tail Recursion from Mutual Recursion

**Objective**: Detect and properly model tail-recursive patterns separately from mutual recursion.

**Implementation**:

1. **Identify tail recursion patterns**:
    - Function calls itself as the last operation in a control path
    - Pattern: `if (condition) { ... par_self(); return; }`
    - Should be modeled as `Repeat`, not `Ref`, because repetition is semantically clear
2. **Algorithm for tail call detection**:
    - For each recursive call edge, check if it's the last statement in its code block
    - Verify no code executes after the recursive call (except return)
    - Example: `par_list1()` calling itself at end of loop → tail recursion
3. **Distinguish from mutual recursion**:
    - Tail recursion: A calls A at end
    - Mutual recursion: A calls B, B calls A, neither at tail position
    - Mutual recursion requires `$ref` to break cycle without losing meaning
4. **Grammar implications**:
    - Tail recursion → use `Repeat` with detected base case
    - Mutual recursion → use `Ref` and document break-point
    - Document which cycle type each back-edge represents

**Output**: Recursive call classification with tail vs. mutual distinction for accurate grammar inference.

### 2.4 Detect Contextual Options

**Objective**: Identify which parser behavior depends on shell options.

**Implementation**:

1. In `_detect_conditions()`, extract references to:
    - `isset(OPTION)` macro calls
    - Direct option constant names (e.g., `EXTENDED_GLOB`)
2. Build a mapping of `par_*` functions → list of option conditions
3. Examples from `parse.c`:
    - Functions that change behavior with `EXTENDED_GLOB`, `KSH_ARRAYS`, etc.

**Output**: Dictionary mapping functions to their conditional behavior flags.

## Phase 3: Build Grammar Rules from Token-Sequence Patterns

**FUNDAMENTAL RESTRUCTURING**: Rules are derived from token-sequence patterns extracted in Phase 2.4, not from function call graphs alone.

### 3.1 Generate Rule Definitions from Token Sequences

**Objective**: Transform token-sequence patterns into grammar rule definitions.

**Why token sequences matter**: A function may call the same function unconditionally (single call in call graph) but use different wrapping tokens depending on control flow. Example:

- Call graph view: `par_subsh() calls par_list()`
- Semantic grammar: `INPAR list OUTPAR | INBRACE list OUTBRACE`

The token sequences capture what the call graph cannot.

**Implementation**:

1. For each `par_*` function, retrieve `token_sequences` from Phase 2.4
2. For each branch in `token_sequences`, build a sequence or union:
    - **Leaf functions** (only token checks, no calls): Build Terminal or Token sequence
        - Example: `par_getword()` with tokens STRING, ENVSTRING → `Union[STRING, ENVSTRING]`
    - **Single-sequence functions**: Build Sequence wrapping token + call + token
        - Example: `par_for()` with sequence `[FOR, ... par_simple() ...]` → `Sequence[FOR, simple, ...]`
    - **Multi-branch functions**: Build Union of alternatives per branch
        - Example: `par_subsh()` with branches:
            - Branch 1: `[INPAR, par_list(), OUTPAR]` → `Sequence[INPAR, list, OUTPAR]`
            - Branch 2: `[INBRACE, par_list(), OUTBRACE, optional(ALWAYS, ...)]` → `Sequence[INBRACE, list, OUTBRACE, Optional[...]]`
            - Result: `Union[Sequence[...], Sequence[...]]`
    - **Recursive functions**: Model based on token sequence in loop
        - If recursion is at end of sequence → `Repeat`
        - If recursion is conditional → `Optional(Repeat(...))`

3. **Strict ordering requirement**:
    - Preserve exact token order from AST extraction
    - If extraction shows `tok==A, par_foo(), zshlex(), tok==B`, model as `Sequence[A, foo, B]`
    - Do NOT reorder; AST order determines semantic meaning

4. **Synthetic tokens for string matching**:
    - If code contains `tok == STRING && !strcmp(tokstr, "always")`, create synthetic token `ALWAYS`
    - Use it in token sequence: `Optional[Sequence[ALWAYS, ...]]`
    - Document synthetic tokens in grammar metadata

5. Handle special cases:
    - `par_redir()` → Optional in many contexts; token sequence determines placement
    - `par_simple()` → Complex dispatcher; may need multiple union alternatives per token pattern
    - Conditional variants → Use `create_variant()` with option conditions
    - Tail recursion → Wrap in `Repeat` with base case

**Output**: Complete `Language` dictionary with rule definitions derived from token sequences, validated against call graph for completeness.

### 3.2 Integrate Token Dispatch into Grammar Rules

**Objective**: Embed token-to-rule mappings into grammar rules to show which tokens trigger which alternatives.

**Status**: COMPLETE ✅

- ✅ Dispatcher switch/case tokens extracted and embedded
- ✅ Inline conditional token matching extracted via Phase 3.2.1
- Result: 30 explicit tokens, 23 dispatcher rules with embedded token references

**Context**: Parser functions use two patterns to match tokens:

1. **Switch/case dispatchers**: Functions like `par_cmd()` with explicit `case FOR:`, `case CASE:` statements
2. **Inline conditionals**: Functions like `par_list()` with `if (tok == SEPER)`, `if (tok != WORD)`, bitwise checks, ternary operators, macros, etc.

**Why this matters**: Zsh parser comments document grammar as `event : ENDINPUT | SEPER | sublist`, showing that tokens are first-class grammar elements, not just metadata. All parser functions should have token entry points documented in grammar.

**Implementation** (Phase 3.2.1 - complete):

1. ✅ Extract tokens from switch/case dispatcher statements:
    - Walk `SWITCH_STMT` nodes in parser functions
    - Extract case labels and their handler function calls
    - Build token-to-rule mappings from dispatcher logic
2. ✅ Extract tokens from inline conditional statements (Phase 3.2.1):
    - Direct equality: `if (tok == SEPER)` → token SEPER
    - Negation: `if (tok != WORD)` → exclude token WORD
    - Bitwise flags: `if (tok & SOME_FLAG)` → extract flag token
    - Range checks: `if (tok >= X && tok <= Y)` → extract boundaries
    - Compound conditions: `if (tok == SEPER || tok == PIPE)` → multiple tokens
    - Ternary operators: `tok == FOO ? ... : ...` → extract FOO
    - Macro-based checks: `ISTOK()`, `ISUNSET()` → extract arguments
    - Walk `IF_STMT` nodes in parser function bodies
3. ✅ Integrate both sources into `_map_tokens_to_rules()` function:
    - Combine tokens from switch/case and inline conditionals
    - Build unified token-to-rule mapping
    - Aggregate across all parser functions
4. ✅ Pass `token_to_rules` to `_build_grammar_rules()` and embed in unions:
    - Include token references in rule union nodes
    - Example: `cmd: { union: [{'$ref': 'FOR'}, {'$ref': 'CASE'}, ..., {'$ref': 'for'}, {'$ref': 'case'}, ...] }`
5. ✅ Validate that all token references exist in `core_symbols`
6. ✅ Maintain distinction: tokens in SCREAMING_SNAKE_CASE, rules in lowercase

**Benefits** (realized with completion):

- ✅ Grammar rules show complete dispatcher logic (what tokens trigger what)
- ✅ Tokens become discoverable through rules that use them
- ✅ Dispatcher rules have documented token entry points (23 rules with 30 tokens)
- ✅ Aligns extracted grammar with Zsh parser source comments
- ✅ Improves canonical grammar completeness and fidelity to source

**Output**: Grammar rules with complete token dispatch information integrated into rule definitions (both switch and inline conditional patterns). 30 explicit tokens extracted, 23 dispatcher rules with embedded token references.

### 3.3 Construct Symbol References

**Objective**: Create proper inter-symbol references using the `$ref` mechanism.

**Implementation**:

1. When a function calls another parser function, generate a reference:
    - `par_list()` calls `par_sublist()` → `{'$ref': 'sublist'}`
2. When a rule uses a token, reference the token symbol:
    - Token `FOR` in `for` rule → `{'$ref': 'FOR'}`
    - Do not inline token definitions; always use references
3. Handle scoped references if needed for future multi-language support:
    - `{'$ref': '/modulename/symbol_name'}` (for rules)
    - `{'$ref': '/modulename/TOKEN_NAME'}` (for tokens)
4. Maintain a symbol table during generation to ensure all references exist

**Output**: Grammar with properly resolved symbol references (tokens and rules both as `$ref`).

### 3.4 Infer Optional and Repetition Patterns

**Objective**: Add structural annotations for optional and repeated elements.

**Implementation**:

1. Analyze return types and conditional logic:
    - Functions returning success/failure → Likely optional
    - Functions inside loops → Likely repeated
2. Use control flow hints:
    - Code patterns like `while (par_something()) { ... }` → `{'repeat': {'$ref': 'something'}, 'min': 1}`
    - Code patterns like `if (par_something()) { ... }` → `{'optional': {'$ref': 'something'}}`
3. Enhance `_build_grammar_rules()` to:
    - Detect and wrap called functions with `create_optional()`
    - Detect and wrap called functions with `create_repeat()` or `create_repeat(..., one=True)`

**Output**: Grammar with proper optional and repetition annotations.

### 3.5 Define Token/Symbol Merge Rules

**Objective**: Establish precedence rules for combining token and symbol information with concrete heuristics.

**Implementation**:

1. Token handling strategy:
    - **All tokens are named symbols**: Tokens exist in grammar as standalone symbols (e.g., `FOR`, `WORD`, `SEMI`)
    - **Rules reference tokens**: When a rule uses a token, use `{'$ref': 'TOKEN_NAME'}`
    - **Multi-keyword tokens**: If multiple keywords map to same token, use `matches` array
        - Token `TYPESET` definition: `{'token': 'TYPESET', 'matches': ['declare', 'export', 'float', 'integer', 'local', 'readonly', 'typeset']}`
    - **No inlining**: Rules never inline token definitions; always reference via `$ref`

2. Implement conflict resolution with concrete decision algorithm:
    - **Question**: When both token and `par_*` function exist for same concept
    - **Example**: `WORD` token vs. parameter expansion parsing in `par_simple()`
    - **Decision algorithm**:
        1. Check if `par_*` function directly references the token in its body
        2. If yes: Use Sequence `{'sequence': [{'$ref': 'TOKEN_NAME'}, {'$ref': 'rule_name'}]}`
        3. If no (separate code paths): Use Union of alternatives
        4. If function's first operation is token matching: Sequential reference
        5. If function is called regardless of token: Parameter is optional reference
    - **Documentation**: Explicitly note which heuristic was applied

3. Tokens as first-class symbols:
    - Each token gets its own grammar symbol definition
    - Multi-value tokens use `matches` array (not union)
    - Rules reference tokens via `$ref`, never inline them
    - Example token definition:
        ```
        "TYPESET": {
          "token": "TYPESET",
          "matches": ["typeset", "declare", "export", "float", "integer", "local", "readonly"],
          "source": {"file": "zsh.h", "line": 142}
        }
        ```
    - Example rule referencing token:
        ```
        "typeset_cmd": {
          "sequence": [
            {"$ref": "TYPESET"},
            {"$ref": "name"},
            {"optional": {"$ref": "value"}}
          ]
        }
        ```

**Output**: Grammar with tokens as first-class symbols and rules referencing them, with clear merge decisions and no duplication.

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

1. Convert `par_*` function names to lower_snake_case rule names:
    - Remove `par_` prefix from function name
    - Convert remaining part to lower_snake_case (handle underscores and multi-word patterns)
    - Examples:
        - `par_for` → `for`
        - `par_case` → `case`
        - `par_cond_double` → `cond_double`
        - `par_nl_wordlist` → `nl_wordlist`
        - `par_simple` → `simple`
2. Tokens remain SCREAMING_SNAKE_CASE (FOR, CASE, WORD, etc.)
3. Ensure uniqueness within rule namespace and within token namespace
4. No conflicts possible: rules and tokens occupy different case namespaces

**Output**: Consistent naming scheme with tokens in SCREAMING_SNAKE_CASE and rules in lower_snake_case derived from function names.

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

### 4.4 Model Context-Dependent Token Behavior

**Objective**: Capture how tokens behave differently based on lexer state and parser flags.

**Implementation**:

1. Extract lexer state dependencies from `lex.c`:
    - Map which lexer state variables affect tokenization
    - Example: `INCMDPOS` affects whether `case` is keyword (token) or word
    - State variables from schema: `IN_MATH`, `ALIASSPACEFLAG`, `INCOMPARISON`, `IN_ARRAY`, `IN_SUBSTITUTION`, `IN_BRACEEXP`, `IN_GLOBPAT`

2. Create state-dependent token definitions:
    - Base rule: `{token: "WORD", matches: "[a-zA-Z_][a-zA-Z0-9_]*"}`
    - Variant for `INCMDPOS`:
        ```json
        {
            "variant": { "token": "TYPESET", "matches": "typeset" },
            "condition": { "lexstate": "INCMDPOS" }
        }
        ```

3. Trace state changes through parser:
    - When `par_cmd()` sets `incmdpos = 1`, track this
    - Map which functions enable/disable which states
    - Example: `par_subsh()` sets `incmdpos = 1` at entry, resets at exit

4. Embed conditions in grammar:
    - Use `Condition` nodes with `lexstate` for context-dependent rules
    - Use `Variant` nodes to express alternatives

**Output**: Grammar rules annotated with state conditions for accurate parsing in different contexts.

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

### 5.3 Validate Against Real Zsh Code

**Objective**: Test extracted grammar against actual Zsh scripts to verify correctness.

**Implementation**:

1. **Feed real Zsh code through grammar validator**:
    - Run Zsh test suite (`vendor/zsh/Tests/`) through grammar
    - Use realistic examples from zsh-users/zsh-completions
    - Test edge cases and complex nested constructs
2. **Compare with actual parser**:
    - Instrument Zsh parser to capture parse tree
    - Compare extracted grammar's inference with actual parser output
    - Flag any discrepancies as grammar errors
3. **Test coverage**:
    - All control structures (for, if, case, while, repeat, function defs)
    - Redirections and pipes
    - Parameter expansion in different contexts
    - Arithmetic and conditional expressions
    - Complex nested combinations
4. **Document discrepancies**:
    - Create report of grammar violations found
    - Flag over-permissive rules (accepts invalid syntax)
    - Flag under-permissive rules (rejects valid syntax)

**Output**: Validation report with test coverage and discrepancy analysis.

### 5.4 Manual Review and Integration

**Objective**: Refine automatically-generated grammar with manual improvements and merge with existing content.

**Implementation**:

1. **Merge with existing manual definitions**:
    - Compare generated grammar with any hand-curated `canonical-grammar.json` sections
    - For each symbol: prefer manually-curated version if significantly better
    - Document merge strategy and conflict resolution
2. **Conflict resolution process**:
    - If both auto and manual versions exist: evaluate quality
    - Keep auto if accurate and complete, manual if it has superior documentation
    - Otherwise merge: use auto structure with manual descriptions/annotations
3. **Mark provenance**:
    - Add `source.auto_generated: bool` field to track origin
    - Document which parts are auto-extracted vs. manually refined
    - Enable future regeneration with preservation of manual edits
4. **Quality gates**:
    - Ensure merged grammar passes full validation (Phase 5.2)
    - Re-run test suite (Phase 5.3) on merged output
    - Verify no regressions from manual integration

**Output**: Final, validated grammar ready for use with clear provenance tracking.

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

4. **`_extract_parser_symbols()` -> dict[str, ParserFunction]`** (NEW)
    - Parse `vendor/zsh/Src/parse.syms` text file
    - Extract function declarations (lines starting with `L` or `E`)
    - Parse signature: name, parameters, return type, visibility
    - Filter to `par_*` and `parse_*` functions only

5. **`_map_tokens_to_symbols()` -> dict[str, str]` (NEW)**
    - Link token constants to parser functions
    - Handle multi-token cases

6. **`validate_grammar(grammar: Grammar) -> list[str]`** (NEW)
    - Check schema compliance
    - Verify all references exist
    - Return list of errors or empty

### Data Flow

```
vendor/zsh/Src/
    ├── parse.syms (text file)
    │   ↓ [parse text file]
    │   → Parser Functions (fast, no preprocessing)
    │
    └── parse.c (C source)
        ↓ [parse with libclang]
        ↓
    Parse Tree
        ├→ [build call graph] → Call Graph
        └→ [extract tokens] → Token Mapping
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

### Phase-by-Phase Success Metrics

**Phase 1: Parser Symbol Extraction**

- Completeness: ≥95% of all `par_*` functions identified and named as rules (validated against `parse.syms`)
- Rule naming: All rules derived from `par_*` functions by removing prefix (e.g., `par_for` → `for`)
- Token naming: All tokens use SCREAMING_SNAKE_CASE convention
- Lexer state dependencies mapped for each function
- Token mapping includes all multi-value tokens with proper matches array representation
- Namespace separation: Rules (lowercase) and tokens (uppercase) occupy distinct namespaces, no conflicts

**Phase 2: Call Graph Analysis**

- Call graph accuracy: All direct `par_*` → `par_*` calls captured
- Cycle detection: Identify all back-edges in call graph
- Classification: Every function assigned correct pattern (leaf/sequential/conditional/iterative)
- Tail recursion: Correctly distinguished from mutual recursion

**Phase 3: Grammar Rule Generation**

- Rule generation: Every `par_*` function becomes exactly one grammar rule ✅
- Token definitions: Every token is a first-class symbol with proper definition ✅
- Reference consistency: All `$ref` use correct naming (SCREAMING_SNAKE_CASE for tokens, lowercase for rules) ✅
- No inlining: Tokens never inlined in rules; always referenced via `$ref` ✅
- **Phase 3.2 Token Dispatch - PARTIAL** ⚠️:
    - ✅ Dispatcher switch/case tokens extracted (9 dispatcher rules: for, while, case, if, etc.)
    - ❌ Inline conditional token matching NOT YET extracted (blocking full completion)
    - Success (when complete): All 31 parser functions have documented token entry points
    - Missing patterns: Equality checks, bitwise flags, ranges, compounds, ternary, macros, indirect calls

**Phase 4: Complex Cases**

- Lexer state conditions: Grammar rules include state-dependent variants
- Option conditions: All `isset()` and option-dependent code captured
- Context accuracy: Grammar models correct parsing context for each symbol

**Phase 5: Validation and Integration**

1. Schema Compliance: Generated grammar passes JSON schema validation (Phase 5.2)
2. Real-world testing: Grammar validates against ≥80% of Zsh test suite scripts (Phase 5.3)
3. Discrepancy resolution: All major grammar errors documented and resolved
4. Provenance tracking: Clear documentation of auto-generated vs. manual sections

### Overall Success Criteria

1. **Completeness**: Extract all major parsing functions (20+ symbols minimum)
2. **Accuracy**: Call graph correctly identifies function relationships; validated against real code
3. **Schema Compliance**: Generated grammar passes JSON schema validation
4. **Correctness**: Grammar validates ≥80% of real Zsh code without false positives
5. **Maintainability**: Extraction is reproducible when Zsh source updates
6. **Documentation**: Process is documented with clear rationale for each decision
7. **Cycle Safety**: All recursive patterns modeled correctly (tail recursion as Repeat, mutual as Ref)
8. **Multi-value Tokens**: Correctly disambiguates keywords mapping to same token using matches array
9. **Traceability**: Every grammar rule can be traced to source code location and extraction phase
10. **Provenance**: Clear marking of auto-generated vs. manually-curated content
11. **Naming Convention**: Tokens in SCREAMING_SNAKE_CASE, rules in lower_snake_case
12. **Token References**: All token usage via `$ref`, no inlined token definitions

## Risks and Mitigations

| Risk                              | Impact                          | Mitigation                                                                |
| --------------------------------- | ------------------------------- | ------------------------------------------------------------------------- |
| .syms file parsing errors         | Incomplete function list        | Validate parsed functions against libclang AST in Phase 2                 |
| libclang preprocessing fails      | Cannot extract call graph       | Handle gracefully, document requirements; function extraction still works |
| Complex control flow not analyzed | Incorrect rule inference        | Manual review and annotation of complex functions                         |
| Token name conflicts              | Grammar ambiguity               | Implement conflict detection and resolution                               |
| Performance on large call graph   | Slow extraction                 | Cache intermediate results, optimize traversal; Phase 1 is now very fast  |
| Schema changes                    | Regeneration breaks             | Version schema, maintain backward compatibility                           |
| Macro expansion failures          | Silent extraction of wrong code | Use libclang with preprocessing enabled, validate against known patterns  |
| Function pointer dispatch         | Missed parser functions         | Implement jump table pattern matching, manually augment call graph        |
| Inline parsing                    | Incomplete grammar              | Scan function bodies for direct token matching, create synthetic rules    |
| Cyclic references                 | Infinite grammar loops          | Implement cycle detection, break cycles at identified break-points        |
| Context-dependent tokens          | Grammar ambiguity               | Track lexer state changes, use Variant nodes with conditions              |

## Testing and Validation

1. **Unit Tests**: Test each extraction function independently
2. **Integration Tests**: Run full pipeline and validate output
3. **Comparison Tests**: Compare with manually-created grammar sections
4. **Performance Tests**: Ensure extraction completes in reasonable time
5. **Regression Tests**: Verify grammar remains valid across Zsh versions

## Appendix: Implementation Concerns

### Naming Convention

**Problem**: Grammar should use consistent naming for tokens vs. rules.

**Solution**:

1. **Tokens** (terminals from lexer): SCREAMING_SNAKE_CASE
    - Examples: `FOR`, `CASE`, `WORD`, `TYPESET`, `DINBRACK`, `SEMI`
    - Source: Token enum in `zsh.h`
    - Each token is a first-class grammar symbol with its own definition
    - Multi-keyword tokens (e.g., TYPESET matching declare/export/float/etc.) use `matches` array, not union
2. **Rules** (non-terminals from parser functions): lower_snake_case
    - Derived from `par_*` function names by removing `par_` prefix
    - Examples:
        - `par_for` → `for`
        - `par_case` → `case`
        - `par_cond_double` → `cond_double`
        - `par_simple` → `simple`
        - `par_cmd` → `cmd`
    - Source: Parser function names from `parse.c`
3. **References between symbols**: Always use `{'$ref': 'SYMBOL_NAME'}`
    - Rules reference tokens: `{'$ref': 'FOR'}`
    - Rules reference other rules: `{'$ref': 'wordlist'}`
    - Never inline token or rule definitions
4. **Rationale**:
    - Easy visual distinction (UPPERCASE = terminal, lowercase = non-terminal)
    - Follows standard grammar notation conventions
    - Simple derivation: remove `par_` prefix from function name
    - No namespace collisions: tokens and rules use different case conventions

### Line Number Semantics

**Problem**: `source.line` field in grammar needs clear definition for reproducibility.

**Solution**:

1. **Standardize line number meaning**:
    - For function-based symbols: Start of function definition (line of `name(...)`)
    - For inline rules: Start of relevant code block (case statement, loop, etc.)
    - For token definitions: Line of token enum entry
2. **Document in grammar**:
    - Add comment in output JSON explaining line number convention
    - Include example: `"line": 456  // Start of par_redir() function definition`
3. **Reproducibility**:
    - Store Zsh source commit hash alongside grammar
    - Enable verification that extracted rules match specific source revision

### Scope Boundaries and Limitations

**Problem**: Plan doesn't clearly define what is in/out of scope.

**Solution**:

1. **In scope** (will be extracted):
    - Core parser in `parse.c`
    - Token definitions in `zsh.h`, `lex.c`, `hashtable.c`
    - Main language grammar (command parsing)
    - Documented parser functions and call relationships
2. **Out of scope** (not extracted, may need manual addition):
    - Math language parsing (separate grammar)
    - Condition syntax grammar (separate grammar)
    - Expansion patterns (parameter, glob, brace)
    - Builtin command argument parsing
    - Interactive features (completion, history)
3. **Documented limitations**:
    - Runtime-loaded builtins not included
    - Feature-conditional code marked but requires build configuration
    - Macro-defined grammar rules require manual inspection

### Terminal Pattern Specification

**Problem**: Schema allows Terminal nodes with regex patterns but doesn't specify regex dialect.

**Solution**:

1. **Standardize regex dialect**:
    - Use ECMAScript regex (JSON-compatible)
    - Avoid Perl/PCRE features like lookahead
    - Document with examples
2. **Extraction strategy**:
    - From `lex.c` character class checking: `itype()` macros → convert to regex
    - Example: `while (itype(c, IWORD))` → pattern `[a-zA-Z0-9_]+`
    - From quoted strings in lexer: Extract literal character classes
3. **Documentation in output**:
    - Add comment explaining pattern origin
    - Link to source function that implements matching

### Traceability and Debugging

**Problem**: If generated grammar is incorrect, hard to debug origin of error.

**Solution**:

1. **Maintain detailed extraction log**:
    - Log every function processed, call found, rule generated
    - Record all decisions made (merge strategy, cycle break point, etc.)
    - Include source code snippets for verification
2. **Traceability in output**:
    - Every symbol includes `source` field with file, line, function, context
    - Optional `_debug` field with extraction notes
    - Example:
        ```json
        "for": {
          "description": "For loop parsing: parses 'for var in words; do ... done'",
          "source": {
            "file": "parse.c",
            "line": 1234,
            "function": "par_for",
            "context": "case FOR in par_cmd()"
          },
          "_debug": "Extracted from case statement; references FOR token and calls wordlist and list rules"
        }
        ```
3. **Verification tools**:
    - Script to map grammar rule back to source code
    - Script to verify all extracted calls appear in grammar
    - Script to list all symbols with conflicting definitions

## Appendix A: Advanced C Analysis Patterns

### Macro Handling Strategy

**Problem**: Zsh uses macros extensively (`isset()`, `OPTION_VALUE()`, etc.)

- These expand to code not visible in AST without preprocessing
- libclang supports preprocessing, but strategy must be specified

**Solution**:

1. Enable preprocessing in libclang:
    ```python
    index = clang.Index.create()
    # Pass preprocessing directives to keep expanded code
    ```
2. For known macros, maintain lookup table:
    - `isset(OPTION)` → Track as option condition
    - `OPTION_VALUE(...)` → Extract option check
    - Token macros → Keep original symbolic names
3. Document assumption: Full C preprocessing applied before parsing

### Function Pointer and Jump Table Handling

**Problem**: Zsh uses function pointers and jump tables for parsing dispatch

- Not visible as direct function calls in call graph
- Example: Builtin function dispatch table

**Solution**:

1. Identify jump table patterns:
    ```c
    static const struct binfunc binfuncs[] = {
        {"KEYWORD", par_keyword_handler},
        ...
    };
    ```
2. For each table entry, add edge to call graph manually
3. Mark table-driven calls with `[jump_table]` annotation in call graph
4. Limit scope: Focus on parser-related dispatch tables in `parse.c` and `zsh.h`

### Inline Parsing Without Delegation

**Problem**: Some parsing happens inline without separate `par_*` function

- Direct token matching and pattern parsing
- Token-level rules that don't delegate to another parser function

**Solution**:

1. Identify inline parsing patterns:
    - Look for `while (itype(...))` or `if (ITYPE(...))` blocks
    - Direct token matching within function body
2. Extract these as grammar rules:
    - Create synthetic symbol for inline pattern
    - Document as "inline" in `source.context`
3. Example:
    ```json
    "redir": {
      "description": "Inline parsing of redirections",
      "source": {
        "file": "parse.c",
        "line": 456,
        "context": "par_redir inline loop"
      }
    }
    ```

### Comment Extraction for Descriptions

**Problem**: Schema allows `description` field but plan doesn't extract these

**Solution**:

1. Use libclang to extract comments preceding function definitions
2. For each `par_*` function, extract leading doc comments
3. Strip formatting, keep first sentence as description
4. Fallback: Generate description from function name + handler behavior
5. Example:
    ```json
    "for": {
      "description": "For loop parsing: parses 'for var in words; do ... done'",
      "source": {"function": "par_for"}
    }
    ```

### Handling of Shadowed/Overloaded Symbols

**Problem**: Some token names shadow other identifiers

- Multiple definitions of same symbol in different contexts
- Version-specific alternatives

**Solution**:

1. Track symbol provenance:
    - Record all sources (files, versions) where symbol appears
    - Use `sinceVersion`/`untilVersion` conditions
2. Disambiguate by:
    - File where extracted
    - Zsh version from configure/Makefile
    - Git commit hash if applicable
3. For ambiguous cases, create variants with conditions:
    ```json
    "some_symbol": {
      "union": [
        {"variant": {...}, "condition": {"sinceVersion": "5.8"}},
        {"variant": {...}, "condition": {"untilVersion": "5.7"}}
      ]
    }
    ```

## Future Enhancements

1. **Multiple Languages**: Extend to extract math grammar, condition grammar, etc.
2. **Interactive Mode**: Allow manual symbol addition/annotation during extraction
3. **Visualization**: Generate call graph diagrams and grammar tree visualizations
4. **Incremental Updates**: Only re-extract changed functions on source updates
5. **Grammar Optimization**: Simplify generated grammar by extracting common patterns
