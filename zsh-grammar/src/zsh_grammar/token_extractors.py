"""Token extraction from AST for semantic grammar construction.

Provides pattern-based extraction of tokens and function calls from parser
function implementations. Handles synthetic tokens from string matching,
error guards, and branch analysis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from clang.cindex import CursorKind, Token

from zsh_grammar.ast_utilities import walk_and_filter
from zsh_grammar.extraction_filters import (
    is_data_token,
    is_undocumented_token,
    normalize_internal_token,
)

if TYPE_CHECKING:
    from clang.cindex import Cursor

    from zsh_grammar.construct_grammar import TokenOrCall, _SyntheticToken, _TokenCheck


def extract_token_sequences(cursor: Cursor, func_name: str = '') -> list[TokenOrCall]:  # noqa: C901, PLR0912
    """
    Phase 2.4.1: Extract ordered token+call sequences from function implementation.

    Walks AST and identifies all semantic tokens and function calls in execution order.

    Returns a list of TokenOrCall items (discriminated union of _TokenCheck,
    _FunctionCall, _SyntheticToken) ordered by source line number.

    This is the main extraction entry point that combines multiple patterns:
    - Pattern 1: Binary operators (tok == TOKEN checks)
    - Pattern 2: Function calls (par_* and parse_*)
    - Pattern 3: Direct token references (from declaration/assignment)

    Args:
        cursor: Parser function definition cursor
        func_name: Function name for context-sensitive filtering

    Returns:
        Ordered list of tokens and function calls (single consolidated sequence)
    """
    # Token name set (SCREAMING_SNAKE_CASE)
    # Note: LEXERR is intentionally excluded - it only appears in error paths
    common_tokens = {
        'INPAR',
        'OUTPAR',
        'INBRACE',
        'OUTBRACE',
        'SEPER',
        'SEMI',
        'DSEMI',
        'STRING',
        'FOR',
        'FOREACH',
        'SELECT',
        'CASE',
        'ESAC',
        'IF',
        'THEN',
        'ELSE',
        'ELIF',
        'FI',
        'WHILE',
        'UNTIL',
        'REPEAT',
        'DO',
        'DONE',
        'DINPAR',
        'DOUTPAR',
        'BAR',
        'OUTANG',
        'INANG',
        'ALWAYS',
        'ENVSTRING',
        'ENVARRAY',
        'NULLTOK',
        'WORD',
    }

    items: list[TokenOrCall] = []
    seen: set[tuple[str, int]] = set()  # Avoid duplicate items (token_name, line)
    error_check_lines: set[int] = set()  # Track lines with error-checking conditions

    # Pre-pass: identify error-checking if statements
    # These use patterns like: if (tok != EXPECTED) YYERRORV(...)
    # We'll exclude items from these patterns later
    if_stmts = list(walk_and_filter(cursor, CursorKind.IF_STMT))
    for if_stmt in if_stmts:
        tokens = list(if_stmt.get_tokens())
        condition_tokens = [t.spelling for t in tokens[:15]]

        # If this is an error-checking condition, mark all lines in this if block
        if _is_error_check_condition(condition_tokens):
            if_start = if_stmt.extent.start.line
            if_end = if_stmt.extent.end.line
            for line_num in range(if_start, if_end + 1):
                error_check_lines.add(line_num)

    # First pass: collect all items with their line numbers
    # Note: Filter out error tokens (LEXERR) and error-checking conditions
    for node in cursor.walk_preorder():
        # Skip nodes in error-checking branches
        if node.location.line in error_check_lines:
            continue

        # Pattern 1: tok == TOKEN_NAME in binary operators
        if (
            node.kind == CursorKind.BINARY_OPERATOR
            and (tokens := list(node.get_tokens()))
            and len(tokens) >= 3
            and tokens[0].spelling == 'tok'
        ):
            op = tokens[1].spelling
            token_name = tokens[2].spelling

            # Skip error tokens (LEXERR) - they only appear in error paths
            # Also skip pure inequality checks (tok != EXPECTED) as guards
            if (
                op in ('==', '!=')
                and token_name.isupper()
                and len(token_name) > 2
                and token_name != 'LEXERR'  # noqa: S105
            ):
                # Skip pure inequality checks (no semantic content)
                if op == '!=' and not _has_semantic_context(tokens):
                    continue

                # Skip data tokens (STRING, WORD, NULLTOK, etc.)
                if is_data_token(token_name, func_name):
                    continue

                key = (token_name, node.location.line)
                if key not in seen:
                    seen.add(key)
                    items.append(
                        {
                            'kind': 'token',
                            'token_name': token_name,
                            'line': node.location.line,
                            'is_negated': (op == '!='),
                        }
                    )

        # Pattern 2: Direct parser function calls (non-recursive)
        elif (
            node.kind == CursorKind.CALL_EXPR
            and _is_parser_function(node.spelling)
            and node.spelling != func_name  # Don't include self-recursion here yet
        ):
            key = (node.spelling, node.location.line)
            if key not in seen:
                seen.add(key)
                items.append(
                    {
                        'kind': 'call',
                        'func_name': node.spelling,
                        'line': node.location.line,
                    }
                )

        # Pattern 3: Direct token reference (e.g., in enum comparisons)
        # Skip LEXERR token references as they only appear in error paths
        elif (
            node.kind == CursorKind.DECL_REF_EXPR
            and node.spelling in common_tokens
            and node.spelling != 'LEXERR'
        ):
            # Skip data tokens unless semantic in context
            if is_data_token(node.spelling, func_name):
                continue

            key = (node.spelling, node.location.line)
            if key not in seen:
                seen.add(key)
                items.append(
                    {
                        'kind': 'token',
                        'token_name': node.spelling,
                        'line': node.location.line,
                        'is_negated': False,
                    }
                )

    # Extract error guard tokens (required terminators in YYERROR guards)
    error_guards = extract_error_guard_tokens(cursor, func_name)
    items.extend(error_guards)

    # Sort items by line number to preserve execution order
    items.sort(key=lambda x: x['line'])

    # Return all items as a single consolidated sequence
    # (Branch analysis would create multiple sequences, but we consolidate here)
    return items if items else []


def extract_synthetic_tokens(  # noqa: PLR0912
    cursor: Cursor, items: list[TokenOrCall], /
) -> list[_SyntheticToken]:
    """
    Phase 2.4.1e: Extract synthetic tokens from compound string matching conditions.

    Identifies patterns like:
    - `tok == STRING && !strcmp(tokstr, "always")` → ALWAYS token
    - `tok == STRING && !strcmp(tokstr, "in")` → IN token
    - `otok == INBRACE && tok == STRING && !strcmp(tokstr, "always")` → ALWAYS token

    Generates synthetic token entries to represent the semantic intent of these
    compound conditions in the grammar.

    These are created when:
    1. A condition checks `tok == STRING`
    2. AND uses strcmp to match tokstr against a specific string value
    3. The string value becomes the synthetic token name (uppercased)
    4. IMPORTANT: Only extract if NOT preceded by negation (!=)

    Example from par_subsh (line 1632):
        if (otok == INBRACE && tok == STRING && !strcmp(tokstr, "always"))
        → Generates ALWAYS synthetic token

    Args:
        cursor: Function definition cursor
        items: Current list of collected items (for deduplication)

    Returns:
        List of _SyntheticToken items to add to the token sequence.
    """
    synthetics: list[_SyntheticToken] = []
    seen_synthetics: set[tuple[str, int]] = set()

    # Pattern: Binary logical AND with strcmp for POSITIVE matching
    # Common in Zsh: tok == STRING && !strcmp(tokstr, "string_value")
    # DO NOT extract from error checks: tok != EXPECTED
    for node in cursor.walk_preorder():
        if node.kind != CursorKind.BINARY_OPERATOR:
            continue

        tokens = list(node.get_tokens())
        if not tokens:
            continue

        spelling_list = [t.spelling for t in tokens]

        # Must contain: tok, ==, STRING, &&, strcmp
        # Check for presence, but ensure tok == (not tok !=)
        if not (
            'tok' in spelling_list
            and '==' in spelling_list
            and 'STRING' in spelling_list
            and '&&' in spelling_list
            and 'strcmp' in spelling_list
        ):
            continue

        # Find the first tok == part - it should not be tok !=
        try:
            tok_idx = spelling_list.index('tok')
            if tok_idx + 1 >= len(spelling_list) or spelling_list[tok_idx + 1] != '==':
                continue  # Skip if not tok ==
        except (ValueError, IndexError):
            continue

        # Now extract the string value from strcmp
        # Pattern: !strcmp(tokstr, "value") or strcmp(tokstr, "value")
        try:
            strcmp_idx = spelling_list.index('strcmp')
        except ValueError:
            continue

        # After strcmp, expect: ( tokstr , "string" ) or similar
        # Look ahead from strcmp position
        rest = spelling_list[strcmp_idx:]

        if len(rest) < 5 or rest[0] != 'strcmp' or rest[1] != '(':
            continue

        # Extract string literal - it should be between comma and closing paren
        # Format: strcmp ( tokstr , "string" )
        string_value = _extract_strcmp_string_value(rest)

        if not string_value:
            continue

        # Skip single-character strings that likely aren't semantic tokens
        # (avoid extracting things like "P" from spurious patterns)
        valid_single_chars = {'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'}
        if len(string_value) == 1 and string_value.upper() not in valid_single_chars:
            continue

        # Generate synthetic token name (SCREAMING_SNAKE_CASE)
        synth_token_name = string_value.upper()

        # Skip "IN" synthetic token - it represents "in" keyword which is an
        # alternative to INPAR, not a distinct semantic token. The INPAR
        # alternative is already represented.
        if synth_token_name == 'IN':  # noqa: S105
            continue

        # Avoid duplicates
        key = (synth_token_name, node.location.line)
        if key in seen_synthetics:
            continue

        seen_synthetics.add(key)

        # Build condition description
        # Check if this was a negated strcmp (!strcmp vs strcmp)
        is_negated_strcmp = (
            'strcmp' in spelling_list
            and spelling_list.index('strcmp') > 0
            and spelling_list[spelling_list.index('strcmp') - 1] == '!'
        )

        if is_negated_strcmp:
            condition_desc = f'tok == STRING && !strcmp(tokstr, "{string_value}")'
        else:
            condition_desc = f'tok == STRING && strcmp(tokstr, "{string_value}")'

        synth: _SyntheticToken = {
            'kind': 'synthetic_token',
            'token_name': synth_token_name,
            'line': node.location.line,
            'condition': condition_desc,
        }
        synthetics.append(synth)

    return synthetics


def extract_error_guard_tokens(
    cursor: Cursor, func_name: str = '', /
) -> list[_TokenCheck]:
    """
    Extract semantically important tokens from error-checking guards.

    Error guards have the pattern: `if (tok != EXPECTED) YYERRORV(...)`
    Although these are error checks, the EXPECTED token is semantically important:
    - Loop/block terminators: DONE, FI, ESAC, OUTBRACE
    - After-parse markers: OUTPAR, OUTANG, SEMI, DSEMI

    These tokens represent required endpoints in the grammar and should be extracted.

    Strategy:
    1. Find all if statements with `tok != TOKEN` patterns
    2. Check if the then-clause contains YYERROR/YYERRORV
    3. Extract the TOKEN as a semantically important terminator
    4. Map internal tokens to semantic tokens (DOLOOP → DO)
    5. Skip undocumented tokens that shouldn't appear in the semantic grammar

    Args:
        cursor: Function definition cursor
        func_name: Function name for context (to check for undocumented tokens)

    Returns:
        List of _TokenCheck items for error-guard tokens
    """
    terminator_tokens = {
        'DONE',
        'DO',
        'FI',
        'ESAC',
        'OUTBRACE',
        'OUTPAR',
        'SEMI',
        'DSEMI',
        'SEPER',
        'OUTANG',
        'INANG',
        'DOUTPAR',  # C-style for loop terminator (for (;;))
    }

    extracted: list[_TokenCheck] = []
    seen: set[tuple[str, int]] = set()

    if_stmts = list(walk_and_filter(cursor, CursorKind.IF_STMT))

    for if_stmt in if_stmts:
        tokens = list(if_stmt.get_tokens())
        if not tokens:
            continue

        # Check if this is an error guard: look for tok != TOKEN pattern
        # followed by YYERROR or YYERRORV in the then-clause
        found_inequality = False
        token_name: str | None = None
        token_idx = -1

        for i, token in enumerate(tokens):
            if (
                token.spelling == 'tok'
                and i + 2 < len(tokens)
                and tokens[i + 1].spelling == '!='
            ):
                candidate = tokens[i + 2].spelling
                if candidate.isupper() and len(candidate) > 2:
                    token_name = candidate
                    token_idx = i + 2
                    found_inequality = True
                    break

        if not (found_inequality and token_name):
            continue

        # Check if the then-clause contains YYERROR or YYERRORV
        then_clause_tokens = tokens[token_idx + 1 :]
        has_error_macro = any(
            t.spelling in ('YYERROR', 'YYERRORV') for t in then_clause_tokens[:20]
        )

        if has_error_macro:
            # Skip undocumented tokens (not part of semantic grammar)
            if is_undocumented_token(token_name, func_name):
                continue

            # Normalize internal tokens to semantic tokens
            semantic_token = normalize_internal_token(token_name)

            # Special case: STRING in par_repeat is semantically required per
            # grammar: repeat : REPEAT STRING { SEPER } ( DO list DONE | list1 )
            # OUTPAR in par_simple at line 1900 is part of ENVARRAY handling, not
            # semantic
            should_extract = semantic_token in terminator_tokens or (
                semantic_token == 'STRING' and func_name == 'par_repeat'  # noqa: S105
            )

            # Skip OUTPAR in par_simple - it's from ENVARRAY error check, not
            # semantic
            if semantic_token == 'OUTPAR' and func_name == 'par_simple':  # noqa: S105
                should_extract = False

            if should_extract:
                key = (semantic_token, if_stmt.extent.start.line)
                if key not in seen:
                    seen.add(key)
                    extracted.append(
                        {
                            'kind': 'token',
                            'token_name': semantic_token,
                            'line': if_stmt.extent.start.line,
                            'is_negated': True,  # Mark as from a negative guard
                        }
                    )

    return extracted


def _extract_branch_items(  # pyright: ignore[reportUnusedFunction]
    items: list[TokenOrCall], start_line: int, end_line: int, /
) -> list[TokenOrCall]:
    """Extract items that fall within a line range (branch)."""
    return [item for item in items if start_line <= item['line'] <= end_line]


def _extract_if_branches(  # pyright: ignore[reportUnusedFunction]
    cursor: Cursor, items: list[TokenOrCall], /
) -> list[tuple[int, int, str, list[TokenOrCall]]]:
    """
    Extract IF statement branches, distinguishing semantic from error-checking.

    Strategy:
    1. Identify error-checking if statements (tok != expected, YYERROR)
    2. Skip extracting those as separate branches (they're guards)
    3. Extract only if statements with semantic alternatives (else blocks with calls)
    4. For nested if statements, keep only top-level semantic branches
    5. Skip extracting nested if/else-if chains - these are implementation details,
       not semantic alternatives

    Returns branches only for true semantic alternatives.
    """
    branches: list[tuple[int, int, str, list[TokenOrCall]]] = []

    if_stmts = list(walk_and_filter(cursor, CursorKind.IF_STMT))

    # Group if statements into top-level chains
    # An if/else-if/else-if/else chain should be treated as ONE unit, not extracted
    if_chains: list[list[Cursor]] = []
    processed: set[int] = set()

    for if_stmt in if_stmts:
        if_line = if_stmt.extent.start.line
        if if_line in processed:
            continue

        # Start a chain with this if statement
        chain = [if_stmt]
        processed.add(if_line)

        # Find any else-if statements that follow
        # (This would require deeper AST analysis, so for now, skip chains entirely)
        if_chains.append(chain)

    # For now, don't extract nested if/else-if chains
    # They fragment the semantic structure and create spurious branches
    # TODO: Implement smarter branch extraction that groups semantic alternatives
    # This is a known limitation - par_for, par_while, etc. have complex if/else-if
    # logic that doesn't map cleanly to semantic grammar alternatives

    return branches


def _extract_switch_branches(  # pyright: ignore[reportUnusedFunction]
    cursor: Cursor, items: list[TokenOrCall], /
) -> list[tuple[int, int, str, list[TokenOrCall]]]:
    """Extract SWITCH statement cases and their items.

    Note: Disabled switch extraction for now due to fragmentation issues.
    Switch statements in parse.c (like in par_case) are typically used for
    simple token dispatching inside loops, not true semantic alternatives.
    Extracting them as separate branches fragments the main sequence incorrectly.

    This was causing par_case to produce 8 sequences (one per case) when it
    should be 1 unified sequence.
    """
    # Don't extract switch cases as separate branches
    # They fragment the extraction incorrectly
    # TODO: Implement smarter switch extraction that preserves loop structure
    return []


def _is_error_check_condition(condition_tokens: list[str], /) -> bool:
    """
    Detect if an if condition is primarily for error checking.

    Error-checking conditions typically:
    - Use != (inequality) operators
    - Check tok against expected token values without positive && conditions
    - Are guards with no semantic alternatives (no matching positive condition)

    Conversely, semantic conditions often:
    - Use == with && chains: (tok == STRING && !strcmp(...))
    - Have positive checks for alternatives: (otok == INBRACE && tok == STRING)

    Args:
        condition_tokens: List of token spellings from condition

    Returns:
        True if this appears to be an error check, False if semantic alternative
    """
    # Check for semantic condition patterns first (higher priority)
    # If we have positive equality checks with &&, it's likely semantic
    # e.g., (otok == INBRACE && tok == STRING && !strcmp(...))
    if '==' in condition_tokens and '&&' in condition_tokens:
        # This could be semantic - check if it's mostly positive checks
        return False

    # Only check tok-related conditions for error patterns
    # Other conditions (like function call return checks) are not error guards
    if 'tok' not in condition_tokens:
        return False

    # Pure inequality checks without semantic alternatives are error checks
    # e.g., if (tok != OUTPAR) YYERRORV(...)
    if '!=' in condition_tokens and '&&' not in condition_tokens:
        return True

    # Single != operator is almost always error checking
    return condition_tokens.count('!=') > 0 and condition_tokens.count('==') == 0


def _has_semantic_context(tokens: list[Token], /) -> bool:
    """
    Check if a token check has semantic context (part of a compound condition).

    A pure error check like `tok != OUTPAR` without semantic context is a guard.
    A semantic check like `tok == STRING && !strcmp(...)` has context.

    Args:
        tokens: Token list from binary operator

    Returns:
        True if this appears to be part of a semantic alternative, False for guards
    """
    token_spellings = [t.spelling for t in tokens]
    # If there's && or ||, it's part of a compound condition (semantic)
    return '&&' in token_spellings or '||' in token_spellings


def _is_parser_function(name: str, /) -> bool:
    """Check if a function name is a parser function (par_* or parse_*)."""
    return name.startswith(('par_', 'parse_'))


def _extract_strcmp_string_value(tokens: list[str], /) -> str | None:
    """
    Extract string value from strcmp(...) token sequence.

    Args:
        tokens: Tokens starting with 'strcmp', e.g.,
            ['strcmp', '(', 'tokstr', ',', '"value"', ')']

    Returns:
        The string value (without quotes), or None if not found.
    """
    # Skip punctuation and identifier names
    for i in range(2, len(tokens)):
        token = tokens[i]
        if token in ('(', ')', ',', 'tokstr'):
            continue
        # String literals appear as quoted text
        if token.startswith('"') and token.endswith('"'):
            return token[1:-1]  # Remove quotes
        # Also handle unquoted string constants (rare)
        if token and not token.startswith('(') and not token.startswith(')'):
            return token
    return None
