"""Token filtering and classification logic for semantic grammar extraction.

Determines which tokens are semantic (part of grammar structure) vs. data tokens
(representing values/content). Filters handle context-sensitive rules and
function-specific exceptions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clang.cindex import Token


def is_data_token(token_name: str, func_name: str) -> bool:  # noqa: PLR0911
    """
    Detect if a token is a data token (not part of grammar structure).

    Data tokens represent values/content rather than grammar structure:
    - STRING: identifier/name/value in most contexts (except when it's a synthetic
      token)
    - WORD: similar to STRING in many contexts
    - IN: keyword spelling "in" as STRING token (not a structural INPAR alternative)
    - ENDINPUT: error-guard token in conditional checks, not semantic
    - ESAC: in par_case, the "esac" keyword is represented by synthetic token from
      strcmp, not by the ESAC token enum value

    Args:
        token_name: Token name to check
        func_name: Current parser function name (for context)

    Returns:
        True if token should be filtered as non-semantic data, False if it's structural
    """
    # IN is always filtered - represents "in" keyword matched via strcmp
    if token_name == 'IN':  # noqa: S105
        return True

    # ENDINPUT is semantic in par_event, data elsewhere
    if token_name == 'ENDINPUT' and func_name != 'par_event':  # noqa: S105
        return True

    # Function-specific filters
    if token_name == 'ESAC' and func_name == 'par_case':  # noqa: S105
        # ESAC matched via strcmp, not token enum
        return True

    if token_name == 'INPAR' and func_name == 'par_case':  # noqa: S105
        # INPAR checking optional construction detail not in semantic grammar
        return True

    if token_name in ('AMPER', 'AMPERBANG') and func_name == 'par_sublist':
        # AMPER/AMPERBANG check complexity flag, not semantic
        return True

    if token_name == 'SEPER' and func_name == 'par_subsh':  # noqa: S105
        # SEPER from loop control, not semantic
        return True

    # par_simple: error check tokens
    if token_name in ('AMPER', 'AMPERBANG') and func_name == 'par_simple':
        # Error check at line 1915: if (tok == AMPER || tok == AMPERBANG) YYERROR
        return True

    if token_name == 'OUTPAR' and func_name == 'par_simple':  # noqa: S105
        # Error check at line 1900: if (tok != OUTPAR) YYERROR
        return True

    if token_name == 'OUTANG' and func_name == 'par_simple':  # noqa: S105
        # OUTANG is from IS_REDIROP macro (redir function calls, not tokens)
        return True

    # par_cond_2: NULLTOK is error guard for test builtin only
    # Phase 3c: Context-sensitive filtering for dual-mode conditional parser
    if token_name == 'NULLTOK' and func_name == 'par_cond_2':  # noqa: S105
        # Line 2472: if (n_testargs) { if (tok == NULLTOK) ...
        # par_cond_2 implements both [[...]] (semantic mode) and [ ... ]
        # (POSIX test builtin). NULLTOK appears only in test builtin code,
        # not in [[...]] parsing. Therefore filtered as non-semantic.
        # Semantic grammar documents [[...]] behavior, no NULLTOK.
        return True

    # INPUT token appears to be synthetic/corrupted extraction artifact
    # Not a real semantic token in the grammar
    if token_name == 'INPUT':  # noqa: S105
        return True

    # STRING is semantic in several functions where it represents actual grammar tokens
    # Phase 3c: par_cond_2 is a dual-mode conditional parser
    # - Semantic grammar documents [[...]] behavior (semantic-test mode)
    # - Implementation also supports [ ... ] (POSIX test builtin)
    # - In both modes, STRING is semantic and required by grammar:
    #   - three-arg test: STRING STRING STRING (e.g., [ a -lt b ])
    #   - two-arg test: STRING STRING (e.g., [ -f file ])
    #   - comparison: STRING ( INANG | OUTANG ) STRING (e.g., [[ a < b ]])
    # Therefore STRING is kept semantic in par_cond_2
    return token_name == 'STRING' and func_name not in (  # noqa: S105
        'par_repeat',
        'par_case',
        'par_simple',
        'par_cond_2',
        'par_wordlist',
    )


def is_undocumented_token(token_name: str, func_name: str) -> bool:
    """
    Detect if a token appears in code but NOT in the semantic grammar.

    Some parser functions have alternative code paths for undocumented features.
    We filter these out to match the semantic grammar documented in parse.c comments.

    Args:
        token_name: Token name to check
        func_name: Current parser function name (for context)

    Returns:
        True if token is undocumented (not in semantic grammar), False otherwise
    """
    # par_repeat: INBRACE/OUTBRACE are undocumented in semantic grammar
    # Grammar says: repeat : REPEAT STRING { SEPER } ( DO list DONE | list1 )
    # But code implements: DO list DONE | INBRACE list OUTBRACE | list1 (SHORTLOOPS)
    return func_name == 'par_repeat' and token_name in ('INBRACE', 'OUTBRACE')


def is_error_branch(branch_items: list[object], /) -> bool:
    """
    Detect if a branch is an error-handling path.

    Since LEXERR tokens are filtered at extraction time, this function
    now checks for other error indicators:
    - Empty branches (no tokens or calls)
    - Branches with only non-semantic references

    Args:
        branch_items: Items in a potential error branch (list of TokenOrCall)

    Returns:
        True if branch appears to be error-only, False if it has semantic content
    """
    # Empty branches are not useful
    if not branch_items:
        return True

    # If branch has parser calls, it's semantic (not error-only)
    for item in branch_items:
        if isinstance(item, dict) and item.get('kind') == 'call':  # pyright: ignore[reportUnknownMemberType]
            return False

    # Branches with only tokens (no calls) are often control flow checks
    # Keep them unless they're truly trivial
    return len(branch_items) == 0


def is_error_check_condition(condition_tokens: list[str], /) -> bool:
    """
    Classify if an if condition is purely error-checking (no semantic alternatives).

    Error checks are patterns like:
    - `tok != EXPECTED` (token guard)
    - `!tok` (negated token check)
    - `tok == ENDINPUT` (end-of-input guard)

    These are guards, not semantic alternatives, so shouldn't create branches.

    Args:
        condition_tokens: Token spellings from the condition

    Returns:
        True if this appears to be an error check, False if semantic
    """
    if not condition_tokens:
        return False

    # Pattern: tok != SOMETHING (error guard)
    if 'tok' in condition_tokens and '!=' in condition_tokens:
        return True

    # Pattern: !tok (negated token, usually error check)
    if '!' in condition_tokens and 'tok' in condition_tokens:
        return True

    # ENDINPUT without semantic context is usually error guard
    return 'ENDINPUT' in condition_tokens and len(condition_tokens) <= 3


def normalize_internal_token(token_name: str, /) -> str:
    """
    Normalize internal zsh tokens to semantic token names.

    Some tokens are referenced by internal names that differ from their
    semantic token enum names.

    Example: DOLOOP internal token → DO semantic token

    Args:
        token_name: Original token name from code

    Returns:
        Normalized token name for grammar rules
    """
    # DOLOOP is internal, DO is semantic
    if token_name == 'DOLOOP':  # noqa: S105
        return 'DO'
    return token_name


def _has_semantic_context(tokens: list[Token], /) -> bool:  # pyright: ignore[reportUnusedFunction]
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
