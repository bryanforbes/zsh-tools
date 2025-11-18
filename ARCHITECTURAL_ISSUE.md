# Architectural Issue: Function-Centric vs Token-Sequence-Centric Grammar

## The Problem

The grammar extraction system is fundamentally misaligned with how the Zsh parser actually works.

### What We Extract

**Function-centric call graph:**

```
par_subsh → calls → par_list
```

**Generated rule:**

```json
{
    "subsh": { "$ref": "list" }
}
```

### What We Should Extract

**Token-sequence-centric grammar from parse.c lines 1604-1611:**

```
subsh : INPAR list OUTPAR |
        INBRACE list OUTBRACE [ "always" INBRACE list OUTBRACE ]
```

**Should generate rule:**

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
                    { "$ref": "OUTBRACE" },
                    {
                        "optional": {
                            "sequence": [
                                { "$ref": "ALWAYS" },
                                { "$ref": "INBRACE" },
                                { "$ref": "list" },
                                { "$ref": "OUTBRACE" }
                            ]
                        }
                    }
                ]
            }
        ]
    }
}
```

## Why This Matters

1. **Parse.c documents the grammar**, not the call graph
    - Every parser function has a leading comment describing its grammar
    - Example: `par_subsh()` has 7-line comment with explicit grammar syntax

2. **Semantic meaning is in token sequences, not function calls**
    - Function `par_list()` is called unconditionally
    - But it's wrapped by different tokens depending on context: `INPAR...OUTPAR` vs `INBRACE...OUTBRACE`
    - These are **semantic alternatives**, not function alternatives

3. **Token-based control flow is invisible to call graphs**
    - Code: `if (otok == INPAR) ... par_list() ... else if (otok == INBRACE) ... par_list() ...`
    - Call graph sees: `par_subsh → par_list` (single call)
    - Grammar should see: Union of two alternatives selected by token value

4. **String matching creates semantic control flow**
    - Code: `tok == STRING && !strcmp(tokstr, "always")`
    - This is a token-based condition controlling an optional block
    - Not a function call; not visible to call graph analysis
    - But it must appear in the grammar as `Optional[ALWAYS, ...]`

## Why Current Extraction Fails

### Token Infrastructure Exists But Is Dead Code

1. **Phase 2.4 infrastructure created:**
    - `TokenEdge` TypedDict for token metadata
    - `_extract_token_consumption_patterns()` walks AST
    - Tokens stored in `call_graph[func_name]['token_edges']`

2. **But it's never used:**
    - `_build_grammar_rules()` ignores `token_edges` field entirely
    - Rules are built from call graph alone
    - Token extraction is dead code

### What's Missing from Token Infrastructure

Even if we tried to use the extracted tokens, they lack critical information:

1. **No ordering** - tokens collected as set, not sequence
2. **No control flow branches** - all tokens mixed together, not grouped by if/else/switch arm
3. **No sequencing** - no way to know which tokens come before/after function calls
4. **No conditionals** - string matching like `!strcmp(tokstr, "always")` not captured

## The Solution: Complete Redesign of Phase 2.4.1

Not an incremental enhancement, but architectural redesign:

### 1. Extract Ordered Timelines

Walk AST and record execution order:

```
par_subsh():
  Line 1617: enum lextok otok = tok;

  Branch 1 (if otok == INPAR):
    tok == INPAR (line 1626 implicit)
    par_list() [line 1624]
    tok == OUTPAR [line 1626]

  Branch 2 (else - otok == INBRACE):
    tok == INBRACE (line 1626 implicit)
    par_list() [line 1624]
    tok == OUTBRACE [line 1626]
    Optional:
      tok == STRING("always") [line 1632]
      tok == INBRACE [line 1639]
      par_save_list() [line 1645]
      tok == OUTBRACE [line 1651]
```

### 2. Group by Control Flow Branch

Each if/else/case arm becomes a separate sequence:

```
Sequence 1: [INPAR, list, OUTPAR]
Sequence 2: [INBRACE, list, OUTBRACE, Optional[ALWAYS, INBRACE, list, OUTBRACE]]
Result: Union[Sequence1, Sequence2]
```

### 3. Create Synthetic Tokens for String Matching

`tok == STRING && !strcmp(tokstr, "always")` → synthetic token `ALWAYS`

### 4. Rewrite Rule Generation

`_build_grammar_rules()` must:

- Read `token_sequences` as primary input (not call graph)
- Build rules directly from token sequences
- Use call graph only for validation

## Current Status

- **Infrastructure**: 40% complete (token extraction exists but unused)
- **Architecture**: 0% correct (function-centric instead of token-sequence-centric)
- **Output quality**: 0% of multi-token functions match semantic grammar comments
- **Estimated rework**: 40-60% of extraction logic needs rewrite

## Impact on Other Phases

This architectural issue cascades through the entire system:

1. **Phase 3 (Rule Generation)**: Cannot work correctly if rules are built from wrong representation
2. **Phase 3.2 (Token Dispatch)**: Works at dispatcher level but misses token sequencing
3. **Phase 3.3 (Control Flow)**: Can detect optional patterns in calls, not token-based conditions
4. **Phase 5.3 (Testing)**: Grammar validation will fail because grammar doesn't match actual Zsh parsing

## Next Steps

1. Implement Phase 2.4.1 complete redesign
2. Extract ordered timelines with branch context
3. Reconstruct token-sequence-based rules
4. Validate against semantic grammar comments
5. Re-run testing to verify output quality

This is not a bug fix; it's an architectural correction.
