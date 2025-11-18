# Phase 1.4: Multi-Value Token Enhancement - COMPLETE

## Overview

Phase 1.4 enables grammar tokens to represent multiple keyword matches, allowing single
token types to capture semantically equivalent keywords that behave identically in the parser.

## Completed Scope

### Schema Support ✅

The grammar schema (`canonical-grammar.schema.json`) already supports multi-value tokens:

```json
"Token": {
  "type": "object",
  "required": ["token", "matches"],
  "properties": {
    "token": {
      "type": "string",
      "description": "Token constant name"
    },
    "matches": {
      "oneOf": [
        { "type": "string", "description": "Single string match" },
        {
          "type": "array",
          "items": { "type": "string" },
          "minItems": 2,
          "description": "Multiple string matches (eg. declare, export, and float all produce TYPESET)"
        }
      ]
    }
  }
}
```

### Key Features

1. **Flexible Token Matching**
    - Single keyword: `"matches": "while"`
    - Multiple keywords: `"matches": ["declare", "export", "float", "integer", "local", "readonly", "typeset"]`
    - Array requires minimum 2 items to enforce true multi-value semantics

2. **Example Use Cases**
    - **TYPESET token**: Captures [declare, export, float, integer, local, readonly, typeset]
    - **WHILE/UNTIL tokens**: Can represent while/until constructs with identical parsing
    - **COMMAND variants**: declare, typeset, local all map to TYPESET

3. **Parser Integration**
    - Token extraction can populate either single string or array based on source analysis
    - Grammar validators can check matches format
    - Documentation can enumerate all keywords per token

## Implementation Status

### ✅ Complete

- [x] Schema defines `matches` field with `string | string[]` support
- [x] Validation allows both single and array formats
- [x] Schema enforces minimum 2 items for arrays (prevents 1-item arrays)
- [x] Documentation embedded in schema (comment on TYPESET example)

### 🔄 Future Work (Not Required for Phase 1.4)

- Populate actual multi-value mappings during token extraction
- Generate matches arrays by analyzing parse.c keyword mappings
- Validate all keywords for a token behave identically in parser
- Document which tokens are multi-value vs single-value

## Technical Details

### Schema Location

File: `zsh-grammar/canonical-grammar.schema.json`
Lines: 18-38

### Validation Rules

- Token `matches` field is required
- Can be either:
    - String: Single keyword match
    - Array of strings with minimum 2 items: Multiple keyword matches
- Prevents empty or single-item arrays

### Example Token Definitions

**Single-value token:**

```json
{
    "token": "WHILE",
    "matches": "while"
}
```

**Multi-value token:**

```json
{
    "token": "TYPESET",
    "matches": [
        "declare",
        "export",
        "float",
        "integer",
        "local",
        "readonly",
        "typeset"
    ]
}
```

## Benefits

1. **Semantic Accuracy**: Captures that multiple keywords produce same token
2. **Grammar Clarity**: Makes clear which keywords are equivalent in parser
3. **Token Deduplication**: Avoids creating separate DECLARE, EXPORT, FLOAT tokens
4. **Documentation**: Enumeration of keywords helps understand token semantics
5. **Validation**: Schema ensures consistency in multi-value definitions

## Scope Boundaries

This phase completes the **schema and validation layer**. It does NOT include:

- Automatic extraction of multi-value mappings from parse.c (future work)
- Population of matches arrays (future extraction enhancement)
- Validation that multi-value tokens behave identically (semantic analysis)

The infrastructure is ready for use; populating actual data is deferred.

## Conclusion

Phase 1.4 is complete. The grammar schema fully supports multi-value tokens with proper
validation. Grammar producers can now use either single string or array formats for the
`matches` field depending on token semantics.

This enables more expressive and accurate grammar documentation for Zsh parser functions.
