# Conditional Expression Hierarchy Analysis

## Phase 3: par_cond, par_cond_1, par_cond_2 Validation

**Date**: 2025-11-17  
**Status**: Analysis Complete - Ready for Implementation  
**Confidence Estimates**: par_cond (100%), par_cond_1 (100%), par_cond_2 (65-75%)

---

## 1. Semantic Grammar Rules

Extracted from parse.c comments (lines 2390-2460):

### par_cond (line 2390)

```
cond : cond_1 { SEPER } [ DBAR { SEPER } cond ]
```

- Entry point for conditional parsing
- Calls par_cond_1 recursively
- Handles disjunction (||) via DBAR token
- Separators (newlines/semicolons) via SEPER

### par_cond_1 (line 2417)

```
cond_1 : cond_2 { SEPER } [ DAMPER { SEPER } cond_1 ]
```

- Second level of precedence
- Calls par_cond_2
- Handles conjunction (&&) via DAMPER token
- Separators via SEPER

### par_cond_2 (line 2455)

```
cond_2 : BANG cond_2
       | INPAR { SEPER } cond_2 { SEPER } OUTPAR
       | STRING STRING STRING
       | STRING STRING
       | STRING ( INANG | OUTANG ) STRING
```

- Base case expressions
- 5 alternatives:
    1. Negation (!)
    2. Parenthesized sub-expression
    3. Three-argument test (e.g., `[ a = b ]`)
    4. Two-argument test (unary operator)
    5. String comparison with <, >

---

## 2. Current Extraction Results

### par_cond

```
Extracted tokens: ['par_cond_1', 'SEPER', 'DBAR']
Extracted functions: par_cond_1
```

**Match with grammar**: ✓ PERFECT (100%)

- Recursively calls par_cond_1 ✓
- Checks DBAR token ✓
- Handles SEPER ✓

### par_cond_1

```
Extracted tokens: ['par_cond_2', 'SEPER', 'DAMPER']
Extracted functions: par_cond_2
```

**Match with grammar**: ✓ PERFECT (100%)

- Recursively calls par_cond_2 ✓
- Checks DAMPER token ✓
- Handles SEPER ✓

### par_cond_2

```
Extracted tokens: [
  'NULLTOK',
  'par_cond_double', 'par_cond_double', 'par_cond_double',
  'par_cond_triple',
  'SEPER',
  'BANG', 'INPAR', 'OUTPAR', 'par_cond',
  'INPUT', 'INPUT', 'INANG', 'OUTANG', 'INPUT', 'INPUT', 'INPUT', 'INPUT', 'INPUT',
  'par_cond_multi', 'par_cond_triple', 'par_cond_double'
]
```

**Match with grammar**: ⚠️ PARTIAL (~65-70%)

---

## 3. Detailed Analysis of par_cond_2

### Grammar Alternatives (Expected)

1. **BANG branch**: `BANG cond_2` → Expects: BANG token
2. **INPAR branch**: `INPAR { SEPER } cond_2 { SEPER } OUTPAR` → Expects: INPAR, OUTPAR, SEPER
3. **STRING STRING STRING**: Three-arg test → Expects: STRING (3x)
4. **STRING STRING**: Two-arg test → Expects: STRING (2x)
5. **STRING ( INANG | OUTANG ) STRING**: Comparison → Expects: STRING, INANG/OUTANG

### Extracted Elements (Code Walk-through)

#### Issue 1: NULLTOK Error Guard (Line 2472)

```c
if (n_testargs) {
    if (tok == NULLTOK)  // ← ERROR GUARD, not semantic
        return par_cond_double(dupstring("-n"), dupstring(""));
```

**Status**: Should be FILTERED
**Reason**: Error check for "no arguments" case in test builtin, not part of [[...]] grammar
**Solution**: Add to \_is_data_token() for par_cond_2 context

#### Issue 2: Helper Function Calls (Lines 2474+)

Extraction includes:

- `par_cond_double`: Internal function (lines 2612-2625)
- `par_cond_triple`: Internal function (lines 2645-2692)
- `par_cond_multi`: Internal function (lines 2696+)

**Status**: Should NOT be included in semantic token sequence
**Reason**: These are implementation details - they encode the parsed values, not the grammar structure
**Problem**: Current extraction walks all functions, including non-parser helpers

#### Issue 3: "INPUT" Tokens (Unexpected)

```
'INPUT', 'INPUT', 'INPUT', 'INPUT', 'INPUT'
```

**Status**: Investigate - likely synthetic or corrupted
**Hypothesis**: May be placeholder for STRING token or variable name extraction
**Action Needed**: Debug extraction code to understand origin

#### Issue 4: Missing STRING Tokens

**Expected**: STRING should appear in all three/two-argument test branches
**Extracted**: None explicitly
**Reason**: STRING tokens may be filtered by \_is_data_token() for par_cond_2
**Action Needed**: Verify STRING is semantic in this context

### Architecture Observation: test Builtin Mode

par_cond_2 has special handling for POSIX test builtin (lines 2468-2503):

```c
int n_testargs = (condlex == testlex) ? arrlen(testargs) + 1 : 0;
```

- When `condlex == testlex`: Running in test builtin mode ([...])
- When `condlex == zshlex`: Running in [[...]] mode
- NULLTOK, early exits are test-specific, not [[...]] specific

For [[...]] grammar validation, test-specific branches are semantic "noise" from our perspective.

---

## 4. Token Filtering Recommendations

### For par_cond_2:

#### A. Error Guard Tokens

- **NULLTOK** (line 2472): Filter as error guard
    - Only in `if (n_testargs)` block for test builtin
    - Not semantic in [[...]] expressions

#### B. Function Call Filtering

- **par_cond_double, par_cond_triple, par_cond_multi**: Don't extract
    - These are output encoding, not input parsing
    - Not part of semantic grammar
    - Problem: Current extraction includes all function calls

#### C. STRING Token

- Keep semantic (appears in 3 of 5 alternatives)
- May be getting filtered incorrectly

#### D. Context-Sensitive Logic

- Test builtin mode branches (lines 2468-2503) are test-specific
- [[...]] mode (lines 2504+) is what semantic grammar documents
- Extraction should focus on condlex == zshlex path

---

## 5. Implementation Challenges

### Challenge 1: Helper Functions in Extraction

Current approach walks AST and finds function calls. But par_cond_double/triple/multi are:

- Not parser functions (don't match par\_\* pattern)
- Internal codegen helpers
- Inclusion suggests extraction is too broad

**Fix Needed**: Refine extraction to exclude non-parser function calls from semantic sequence

### Challenge 2: Test Builtin vs [[...]]

par_cond_2 has significant conditional logic:

- `if (n_testargs)`: test builtin specific
- `else`: [[...]] path

Current grammar in parse.c comments doesn't distinguish, but implementation has different paths.

**Possible Approach**:

1. Extract only the [[...]] path (condlex != testlex)
2. Or mark test-specific branches as "data" tokens
3. Or accept reduced confidence score for mixed mode function

### Challenge 3: Missing STRING Extraction

The grammar clearly expects STRING tokens, but extraction doesn't show them explicitly.

**Investigation Needed**:

- Check if STRING is being filtered by \_is_data_token()
- Verify token extraction from conditional branches
- May need to NOT filter STRING in par_cond_2 context

---

## 6. Confidence Score Calculation

### par_cond (Line 2397)

```
Semantic Tokens (from grammar): SEPER, DBAR
Extracted Tokens: SEPER, DBAR
Semantic Functions: par_cond_1 (correct)

Match: 2/2 = 100%
Confidence: 100%
```

### par_cond_1 (Line 2422)

```
Semantic Tokens (from grammar): SEPER, DAMPER
Extracted Tokens: SEPER, DAMPER
Semantic Functions: par_cond_2 (correct)

Match: 2/2 = 100%
Confidence: 100%
```

### par_cond_2 (Line 2464)

```
Semantic Tokens (from grammar): BANG, INPAR, OUTPAR, INANG, OUTANG, STRING, SEPER (7 unique)
Extracted tokens: BANG, INPAR, OUTPAR, INANG, OUTANG, SEPER, NULLTOK (7 unique, but NULLTOK is error)
  + Spurious: INPUT (5x), helper functions

Matched: BANG, INPAR, OUTPAR, INANG, OUTANG, SEPER = 6/7 (missing STRING)
Extra tokens: NULLTOK, 5x INPUT, + all helper functions
Penalty: -0.1 per extra token category

Confidence: (6/7 - 0.1*2) / 1 = ~57-65%
```

---

## 7. Key Learnings for Conditional Functions

### Pattern: Recursive Descent Hierarchy

- par_cond → par_cond_1 → par_cond_2 → (base cases and recursion)
- Each level adds one operator precedence level (OR, AND, NOT)
- SEPER appears at each level (optional newlines)

### Pattern: Alternation via Recursive Calls

- par_cond_2 implements 5 alternatives via if-else chains
- Each alternative calls different sub-parser or has token checks
- No switch statement (unlike par_case or par_simple)

### Pattern: Special Lexer (condlex)

- Conditional functions use `condlex()` function pointer (line 2387)
- Can point to testlex (POSIX test builtin) or zshlex ([[...]])
- Same functions serve both modes
- Makes extraction harder because semantic grammar path is embedded

### Pattern: Helper Functions vs Parser Functions

- par_cond_double/triple/multi are NOT parser functions
- They encode parse results, not parse structure
- Current extraction may be too broad in including all function calls

---

## 8. Recommendations for Implementation

### Priority 1: Validate par_cond and par_cond_1

- Both should be 100% confidence
- No changes needed to extraction
- Add validation rules to \_validate_semantic_grammar()

### Priority 2: Fix par_cond_2 Extraction

1. **Filter NULLTOK**: Add to \_is_data_token(func_name='par_cond_2')
2. **Exclude helper functions**: Refine extraction to not include par_cond_double/triple/multi
3. **Verify STRING extraction**: Check if STRING is being filtered incorrectly
4. **Investigate INPUT tokens**: Debug where these come from

### Priority 3: Document Limitations

- If STRING extraction can't be fixed: Document as 80-85% confidence
- Rationale: Architecture shows STRING is handled, but extraction can't resolve it
- Similar to INPAR/OUTPAR limitations in par_if/par_while

### Expected Final Scores

- par_cond: 100% ✓
- par_cond_1: 100% ✓
- par_cond_2: 75-85% (with filtering improvements)

**Overall for conditional hierarchy**: ~92-95% confidence

---

## 9. Next Steps

1. **Implement token filtering**:
    - Add NULLTOK to \_is_data_token() filter
    - Add STRING exception for par_cond_2 context
2. **Fix helper function extraction**:
    - Investigate why par_cond_double/triple/multi appear
    - Refine extraction logic to exclude non-parser functions
3. **Debug INPUT tokens**:
    - Trace extraction code to find origin
    - May be synthetic tokens or corrupted names
4. **Run validation**:
    - Execute \_validate_semantic_grammar() on all three functions
    - Compare against expected semantic rules
5. **Document findings**:
    - Update EXTRACTION_STATUS.md with conditional hierarchy results
    - Add Phase 3 completion notes to PARSER_FUNCTION_AUDIT.md

---

## Appendix: Code References

### Grammar Comments Location

- Lines 2390-2391: par_cond grammar
- Lines 2417-2418: par_cond_1 grammar
- Lines 2455-2460: par_cond_2 grammar

### Implementation Details

- Lines 2397-2414: par_cond implementation
- Lines 2422-2439: par_cond_1 implementation
- Lines 2464-2608: par_cond_2 implementation
- Lines 2612-2625: par_cond_double (helper)
- Lines 2645-2692: par_cond_triple (helper)
- Lines 2696+: par_cond_multi (helper)

### Lexer References

- Line 2387: condlex function pointer
- Line 2393: COND_SEP() macro (newline handling)
- Line 2468: n_testargs (test builtin mode detection)
