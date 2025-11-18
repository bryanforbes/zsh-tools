# Phase 3 Analysis: Conditional Expression Hierarchy

## par_cond, par_cond_1, par_cond_2 - Semantic Grammar Validation

**Analysis Date**: November 17, 2025  
**Status**: Analysis Complete - Findings Documented  
**Functions Analyzed**: 3 (par_cond, par_cond_1, par_cond_2)  
**Lines Analyzed**: 2397-2608 in vendor/zsh/Src/parse.c

---

## Executive Summary

The conditional expression hierarchy implements the [[...]] construct and POSIX test [ ... ] builtin using a classic recursive descent parser with operator precedence:

- **par_cond**: OR level (||) - DBAR token
- **par_cond_1**: AND level (&&) - DAMPER token
- **par_cond_2**: Base level (!, (), <, >, unary ops, string comparisons)

**Current Extraction Results**:

- par_cond: 100% confidence ✓ (perfect match)
- par_cond_1: 100% confidence ✓ (perfect match)
- par_cond_2: 65-75% confidence ⚠️ (extraction issues identified)

**Expected After Fixes**: 92-95% overall for hierarchy

---

## 1. Semantic Grammar Rules

Extracted from parse.c comment blocks (lines 2390-2460):

### Rule 1: par_cond (Line 2397)

```
Grammar:  cond : cond_1 { SEPER } [ DBAR { SEPER } cond ]

Interpretation:
  - Call par_cond_1() first (recursive descent entry)
  - Optionally consume DBAR (||) token
  - SEPER allows newlines/semicolons at alternation point
  - Recursive on right: right-associative disjunction
```

**Implementation** (lines 2401-2411):

```c
r = par_cond_1();              // Parse first alternative
while (COND_SEP())             // Skip separators
    condlex();
if (tok == DBAR) {             // Check for ||
    condlex();                 // Consume ||
    while (COND_SEP())         // Skip separators
        condlex();
    ecispace(p, 1);            // Insert instruction space
    par_cond();                // Recursively parse right side
    ecbuf[p] = WCB_COND(...);  // Encode disjunction
    return 1;
}
return r;                      // No ||, return left side
```

### Rule 2: par_cond_1 (Line 2422)

```
Grammar:  cond_1 : cond_2 { SEPER } [ DAMPER { SEPER } cond_1 ]

Interpretation:
  - Call par_cond_2() first
  - Optionally consume DAMPER (&&) token
  - SEPER allows newlines/semicolons
  - Recursive on right: right-associative conjunction
```

**Implementation** (lines 2426-2437):

```c
r = par_cond_2();              // Parse first alternative
while (COND_SEP())             // Skip separators
    condlex();
if (tok == DAMPER) {           // Check for &&
    condlex();                 // Consume &&
    while (COND_SEP())         // Skip separators
        condlex();
    ecispace(p, 1);            // Insert instruction space
    par_cond_1();              // Recursively parse right side
    ecbuf[p] = WCB_COND(...);  // Encode conjunction
    return 1;
}
return r;                      // No &&, return left side
```

### Rule 3: par_cond_2 (Line 2464)

```
Grammar:  cond_2 : BANG cond_2
                | INPAR { SEPER } cond_2 { SEPER } OUTPAR
                | STRING STRING STRING
                | STRING STRING
                | STRING ( INANG | OUTANG ) STRING

Interpretation:
  Alternative 1: ! (logical negation)
    - Prefix operator
    - Recursively parses another cond_2
    - Can combine: ! ! x (double negation)

  Alternative 2: (expr) (grouping)
    - Parenthesized subexpression
    - Allows separators inside
    - Recursively calls par_cond() to parse subexpression

  Alternative 3: a = b = c (three-arg test)
    - Two operators: equality, comparison
    - Examples: [ a = b ], [ a -lt b ], [ -f a ]

  Alternative 4: a = b (two-arg test)
    - Unary operator with argument
    - Examples: [ -f file ], [ -n string ]

  Alternative 5: a < b (relational)
    - String less-than or greater-than
    - INANG: < (less than)
    - OUTANG: > (greater than)
```

**Implementation** (lines 2507-2608):
Complex with multiple branches for different test modes and argument counts.

---

## 2. Current Extraction vs. Grammar

### par_cond: Extraction Validation

**Expected from Grammar**:

- Semantic tokens: `SEPER`, `DBAR`
- Semantic functions: Call to `par_cond_1`

**Actually Extracted**:

```python
tokens: ['par_cond_1', 'SEPER', 'DBAR']
functions: par_cond_1
```

**Validation**: ✓ PERFECT MATCH (100%)

- par_cond_1 called ✓
- SEPER token detected ✓
- DBAR token detected ✓
- No extra tokens ✓
- No missing tokens ✓

---

### par_cond_1: Extraction Validation

**Expected from Grammar**:

- Semantic tokens: `SEPER`, `DAMPER`
- Semantic functions: Call to `par_cond_2`

**Actually Extracted**:

```python
tokens: ['par_cond_2', 'SEPER', 'DAMPER']
functions: par_cond_2
```

**Validation**: ✓ PERFECT MATCH (100%)

- par_cond_2 called ✓
- SEPER token detected ✓
- DAMPER token detected ✓
- No extra tokens ✓
- No missing tokens ✓

---

### par_cond_2: Extraction Validation

**Expected from Grammar**:

- Semantic tokens: `BANG`, `INPAR`, `OUTPAR`, `STRING`, `INANG`, `OUTANG`, `SEPER`
- Semantic functions: `par_cond_2` (recursive), `par_cond` (from INPAR alternative)

**Actually Extracted** (current):

```python
tokens: [
  'NULLTOK',                      # ← ERROR: Error guard, not semantic
  'par_cond_double',              # ← ERROR: Helper function, not parser function
  'par_cond_double',              # ← ERROR: Helper function
  'par_cond_double',              # ← ERROR: Helper function
  'par_cond_triple',              # ← ERROR: Helper function, not parser function
  'SEPER',                        # ✓ Semantic
  'BANG',                         # ✓ Semantic
  'INPAR',                        # ✓ Semantic
  'OUTPAR',                       # ✓ Semantic
  'par_cond',                     # ✓ Semantic function
  'INPUT', 'INPUT',               # ← ERROR: Synthetic/corrupted
  'INANG',                        # ✓ Semantic
  'OUTANG',                       # ✓ Semantic
  'INPUT', 'INPUT', 'INPUT',      # ← ERROR: Synthetic/corrupted
  'INPUT',                        # ← ERROR: Synthetic/corrupted
  'par_cond_multi',               # ← ERROR: Helper function
  'par_cond_triple',              # ← ERROR: Helper function
  'par_cond_double'               # ← ERROR: Helper function
]
```

**Issues Identified**:

| Issue           | Type           | Count | Impact         | Cause                                  |
| --------------- | -------------- | ----- | -------------- | -------------------------------------- |
| NULLTOK         | Error guard    | 1     | Extra token    | Line 2472 error check for test builtin |
| INPUT tokens    | Corrupted      | 5     | False positive | Unknown - needs investigation          |
| par_cond_double | Wrong function | 3     | Extra item     | Extraction too broad                   |
| par_cond_triple | Wrong function | 2     | Extra item     | Extraction too broad                   |
| par_cond_multi  | Wrong function | 1     | Extra item     | Extraction too broad                   |
| STRING          | Missing        | N/A   | Missing token  | Likely filtered by \_is_data_token()   |

**Validation**: ⚠️ PARTIAL (65-75%)

**Score Calculation**:

```
Semantic tokens in grammar: {BANG, INPAR, OUTPAR, STRING, INANG, OUTANG, SEPER} = 7
Semantic tokens extracted: {BANG, INPAR, OUTPAR, INANG, OUTANG, SEPER} = 6
Missing: STRING = 1

Confidence = (matched / expected) - (extra_count * penalty)
           = (6 / 7) - (11 extra items * 0.05)
           = 0.857 - 0.55
           = 0.307...

More realistic model:
Matched: 6/7 = 85.7%
Missing penalty: -1 token = -14.3%
Extra items penalty: -11 items * 0.05 = -55%
Result: 85.7% - 14.3% - 55% = 16.4% ???

Better model (matches earlier scoring):
Confidence = (matched / expected) - (extra_categories * 0.1)
           = (6 / 7) - (3 extra categories: NULLTOK, INPUT, helpers * 0.1)
           = 0.857 - 0.30
           = 0.557 ≈ 55-60%

Adjusted (accounting for par_cond call which IS semantic):
Actual semantic items: 7 tokens + 1 function = 8
Extracted correctly: 6 tokens + 1 function = 7
Missing: 1 token (STRING)
Extra: 11 wrong items

Confidence = 7/8 - (11 * 0.05) = 0.875 - 0.55 = 0.325 ≈ 33%

OR simple model (matches extraction_status.py):
matched = 6, expected = 7, extra = 11
confidence = (matched - extra*0.1) / expected
           = (6 - 1.1) / 7
           = 4.9 / 7
           = 0.70 = 70%
```

**Current confidence**: ~65-75% (likely around 70%)

---

## 3. Detailed Analysis of Issues

### Issue A: NULLTOK Error Guard (Line 2472)

**Code Context**:

```c
int n_testargs = (condlex == testlex) ? arrlen(testargs) + 1 : 0;

if (n_testargs) {
    /* See the description of test in POSIX 1003.2 */
    if (tok == NULLTOK)
        /* no arguments: false */
        return par_cond_double(dupstring("-n"), dupstring(""));
```

**What it means**:

- `n_testargs`: Non-zero when in test builtin mode ([ ... ])
- When NULLTOK: Means "no arguments", which is an error case
- Called with early return to `par_cond_double`

**Why it's extracted**:

- Token comparison: `if (tok == NULLTOK)` is detected
- Not tagged as error check

**Why it's wrong**:

- NULLTOK is only checked in test builtin mode (n_testargs > 0)
- Not part of [[...]] grammar
- Is an error guard, not semantic alternative

**What semantic grammar says**:

- cond_2 grammar doesn't mention NULLTOK
- cond_2 grammar is for [[...]], not [ ... ]

**Fix needed**: Filter NULLTOK via \_is_data_token() when func_name == 'par_cond_2'

---

### Issue B: Helper Functions in Sequence

**Functions appearing in extraction**:

- `par_cond_double` (lines 2612-2625)
- `par_cond_triple` (lines 2645-2692)
- `par_cond_multi` (lines 2696+)

**What they are**:

- Internal helper functions
- NOT parser functions (don't match par\_\* pattern for input parsing)
- Used to ENCODE parse results into bytecode
- Take string arguments and generate WCB_COND instructions

**Why they're extracted**:

- Current extraction walks all function calls
- No distinction between parser functions and helper functions

**Why they're wrong**:

- They represent OUTPUT encoding, not INPUT parsing
- Not part of semantic grammar
- Including them suggests extraction found a parse path through these helpers

**Example**:

```c
if (n_testargs > 2) {
    if (!strcmp(*testargs, "=") || ...) {
        s1 = tokstr;
        condlex();
        s2 = tokstr;
        condlex();
        s3 = tokstr;
        condlex();
        return par_cond_triple(s1, s2, s3);  // ← Helper called
    }
}
```

The extraction sees `par_cond_triple(...)` call but doesn't understand it's not a parser function.

**Fix needed**: Refine extraction logic to only include par*\* and parse*\* functions

---

### Issue C: INPUT Tokens (5 instances)

**What's appearing**:

```
'INPUT', 'INPUT', 'INANG', 'OUTANG', 'INPUT', 'INPUT', 'INPUT', 'INPUT', 'INPUT'
```

**What it should be**:
Likely:

- Several STRING tokens (for multi-arg tests)
- INANG/OUTANG for relational operators

**Why it's wrong**:

- INPUT is not a token in parse.c
- 5 consecutive INPUT tokens suggest corrupted extraction
- May be placeholder or synthetic token gone wrong

**Possible causes**:

1. Token name extraction failing, defaults to "INPUT"
2. Synthetic token generation creating placeholders
3. AST node name being used instead of actual token
4. Tokenizer bug introducing placeholder

**Investigation needed**: Debug extraction to find origin

---

### Issue D: Missing STRING Tokens

**What's missing**:
STRING tokens from grammar alternatives:

- Alt 3: `STRING STRING STRING` (3-arg tests)
- Alt 4: `STRING STRING` (2-arg tests, operand)
- Alt 5: `STRING ... STRING` (comparison operands)

**Grammar expects**: STRING in 3 of 5 alternatives

**Extraction shows**: No STRING tokens explicitly

**Why it matters**:

- STRING is semantic (represents operands/operators)
- Grammar clearly requires them
- Missing indicates filtering issue

**Likely cause**:

- \_is_data_token() filter is removing STRING
- Generic rule: "STRING is data in par_cond_2"
- But STRING IS semantic here (it's the test values)

**Difference from other functions**:

- In par_simple: STRING is data (arguments)
- In par_repeat: STRING is semantic (repeat count)
- In par_cond_2: STRING is semantic (test operands)

**Fix needed**: Exception to keep STRING semantic in par_cond_2

---

## 4. Architectural Insights

### Insight 1: Operator Precedence Hierarchy

Classic recursive descent for operator precedence:

```
Precedence Level 1 (lowest): OR (||) - par_cond
Precedence Level 2: AND (&&) - par_cond_1
Precedence Level 3 (highest): Unary ops - par_cond_2
```

**Code pattern**:

```c
parse_level_N() {
    result = parse_level_N+1();  // Parse higher precedence
    while (SEPARATOR) skip();
    if (tok == OPERATOR) {
        consume();
        result = parse_level_N();  // RIGHT ASSOCIATIVE
    }
    return result;
}
```

**Key**: Right-associative allows chaining: `a || b || c` = `a || (b || c)`

---

### Insight 2: Dual-Mode Parser

par_cond_2 serves two masters:

```c
int n_testargs = (condlex == testlex) ? arrlen(testargs) + 1 : 0;

if (n_testargs) {
    // POSIX test builtin [ ... ] mode
    // Different grammar, early exits, special cases
} else {
    // [[ ... ]] mode
    // Full grammar as documented
}
```

**Implications**:

1. Same function, two different grammars
2. Semantic grammar documentation only covers [[...]]
3. Extraction mixes both modes
4. Error guards like NULLTOK are test-specific only

**Pattern observation**:
Functions supporting multiple input modes (test vs [[]]) are harder to extract cleanly.

---

### Insight 3: COND_SEP() Macro for Separator Handling

```c
#define COND_SEP() (tok == SEPER && condlex != testlex && *zshlextext != ';')
```

- SEPER allowed between operators and operands
- But NOT when in test builtin mode
- But NOT when token is semicolon (despite SEPER classification)

**Extraction sees**: SEPER token checks

**Grammar documents**: `{ SEPER }` in rules

**Complexity**: Macro hides conditional logic from simple extraction

---

## 5. Comparison with Earlier Functions

### Similar to par_if / par_while

**Pattern**: Missing optional INPAR/OUTPAR
**Cause**: Delegation to par_cmd which recognizes (list) as subshell
**Status**: Architectural limitation, not extraction bug
**par_cond_2 similarity**: Different cause (dual-mode) but similar result (some paths not extracted)

### Different from par_simple

**Pattern**: par_simple also has helper analysis
**How par_simple solved it**: Carefully filtered non-semantic items
**What we can learn**: Systematic filtering approach works
**par_cond_2 opportunity**: Apply similar systematic filtering

### Key difference

- par_if/par_while: Architectural difference (delegation)
- par_cond_2: Extraction issues (helpers, guards, missing STRING)
- Both: Some aspects are unfixable, some are fixable

---

## 6. Recommended Fixes and Expected Outcomes

### Fix 1: Filter NULLTOK (HIGH PRIORITY)

**Location**: construct_grammar.py, `_is_data_token()`

**Change**:

```python
def _is_data_token(token_name: str, func_name: str) -> bool:
    # ... existing code ...

    # NULLTOK in par_cond_2 is error guard for test builtin
    if token_name == 'NULLTOK' and func_name == 'par_cond_2':
        return True  # Filter it

    # ... rest of code ...
```

**Impact**: Removes 1 error item from extraction

**Expected change**: 70% → 72-73%

---

### Fix 2: Exclude Helper Functions (HIGH PRIORITY)

**Location**: construct_grammar.py, token extraction phase

**Issue**: par_cond_double, par_cond_triple, par_cond_multi should not be in token_sequences

**Current code**: Likely walks all function calls

**Fix approach**:

```python
# Don't include non-parser functions in semantic extraction
if func_name.startswith(('par_', 'parse_')):
    # Include in sequence
else:
    # Skip non-parser function calls
```

**Impact**: Removes 6 helper function calls from extraction

**Expected change**: 72-73% → 78-80%

---

### Fix 3: Investigate INPUT Tokens (HIGH PRIORITY)

**Action**: Debug extraction code

**Questions**:

- Where do INPUT tokens come from?
- Are they synthetic tokens or corrupted names?
- Should they be STRING tokens?

**Process**:

1. Add debug logging to token extraction
2. Trace which AST nodes produce INPUT
3. Determine if it's a tokenizer issue or extraction bug
4. Fix at source

**Impact**: Removes 5 synthetic/corrupted items

**Expected change**: 78-80% → 82-85%

---

### Fix 4: Verify STRING Token Handling (MEDIUM PRIORITY)

**Issue**: STRING tokens missing from extraction but expected in grammar

**Investigation**:

1. Check if STRING being filtered by \_is_data_token()
2. Verify STRING is semantic in par_cond_2 (it should be)
3. Create exception for context

**Potential fix**:

```python
if token_name == 'STRING' and func_name == 'par_cond_2':
    return False  # Keep STRING as semantic
```

**Impact**: Adds 1 expected token

**Expected change**: 82-85% → 85-88%

---

### Fix 5: Handle Test Builtin Paths (LOW PRIORITY)

**Context**: par_cond_2 has separate [[...]] and [ ... ] code paths

**Options**:

1. Accept reduced confidence for dual-mode functions
2. Document the distinction
3. Create separate validation rules for each mode
4. Extract only [[...]] path (more complex)

**Recommendation**: Document and accept (not a fix, an explanation)

---

## 7. Expected Final Results

### Without any fixes:

```
par_cond:   100% ✓
par_cond_1: 100% ✓
par_cond_2: 65-70% ⚠️
Hierarchy avg: 88-90%
```

### With all fixes applied:

```
par_cond:   100% ✓
par_cond_1: 100% ✓
par_cond_2: 85-90% ✓
Hierarchy avg: 95-97%
```

### Project-wide impact:

```
Current: 17 functions, 96.34% overall
After Phase 3: 20 functions, 96.5-96.8% overall (marginal due to already-high baseline)
Better metric: 20/31 parser functions validated = 65% coverage
```

---

## 8. Strategic Value

### Why Phase 3 Matters

1. **Foundation construct**: [[...]] is central to Zsh
2. **Complexity level**: par_cond_2 shows we handle alternation well
3. **Architecture insight**: Dual-mode functions reveal real-world complexity
4. **Pattern recognition**: Operator precedence pattern likely repeats in arithmetic expressions

### Learning from Phase 3

This phase teaches:

- ✓ Recursive descent hierarchy extraction works reliably
- ⚠️ Helper functions need explicit filtering
- ⚠️ Dual-mode functions create extraction ambiguity
- ⚠️ Error guards in one mode are noise in another mode
- ⚠️ String/data token filtering requires deep context

### Future phases will benefit from:

1. Better function classification (parser vs helper vs internal)
2. Context-sensitive token filtering system
3. Multi-mode function handling strategy
4. Operator precedence patterns documentation

---

## 9. Implementation Checklist

- [ ] Analyze helper function inclusion issue
- [ ] Filter NULLTOK in par_cond_2
- [ ] Debug INPUT token origin
- [ ] Fix helper function extraction
- [ ] Verify STRING token extraction
- [ ] Run validation suite on par_cond, par_cond_1, par_cond_2
- [ ] Update EXTRACTION_STATUS.md with results
- [ ] Add Phase 3 notes to PARSER_FUNCTION_AUDIT.md
- [ ] Document dual-mode parser pattern
- [ ] Create comprehensive test cases

---

## 10. Code References

### Grammar Documentation

- Lines 2390-2391: par_cond grammar
- Lines 2417-2418: par_cond_1 grammar
- Lines 2455-2460: par_cond_2 grammar (with alternatives)

### Implementation Code

- Lines 2397-2414: par_cond() function
- Lines 2422-2439: par_cond_1() function
- Lines 2464-2608: par_cond_2() function

### Helper Functions (not for semantic extraction)

- Lines 2612-2625: par_cond_double()
- Lines 2645-2692: par_cond_triple()
- Lines 2696+: par_cond_multi()

### Key Infrastructure

- Line 2387: `condlex` function pointer
- Line 2393: `COND_SEP()` macro
- Lines 2447-2452: `check_cond()` helper
- Lines 2629-2641: `get_cond_num()` helper

---

## 11. Conclusion

The conditional expression hierarchy shows that:

1. **Top levels (par_cond, par_cond_1)** are clean, simple, perfectly extracted
2. **Base level (par_cond_2)** is complex, with 5 alternatives and some extraction issues
3. **Issues are fixable**: Helper function filtering, error guard removal, STRING token verification
4. **Expected improvement**: 65-70% → 85-90% with systematic fixes
5. **Strategic value**: Operator precedence patterns and dual-mode function handling

This group of functions demonstrates the extraction system's strength (recursive descent works well) and identifies areas for improvement (helper function filtering, context-sensitive token filtering).

Ready for implementation phase.
