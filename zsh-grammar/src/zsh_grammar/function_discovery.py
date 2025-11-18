"""Function discovery and metadata extraction from parse.syms and AST.

Extracts parser function definitions and builds function metadata including
dispatcher keywords, state assignments, and call relationships.
"""

from __future__ import annotations

import re
from collections.abc import Iterator  # noqa: TC003
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING

from clang.cindex import CursorKind

from zsh_grammar.ast_utilities import find_cursor

if TYPE_CHECKING:
    from zsh_grammar._types import FunctionNode
    from zsh_grammar.source_parser import ZshParser


def _is_parser_function(name: str, /) -> bool:
    """Check if a function name is a parser function (par_* or parse_*).

    Excludes internal helper functions that are called from other parsers:
    - par_cond_double, par_cond_triple, par_cond_multi: Test helpers
      (called from par_cond_2)
    - par_list1: Shortloops helper (called from par_list)

    These helpers are implementation details of their parent functions and
    shouldn't be treated as top-level semantic grammar rules.
    """
    internal_helpers = {
        'par_cond_double',
        'par_cond_triple',
        'par_cond_multi',
        'par_list1',
    }
    return name.startswith(('par_', 'parse_')) and name not in internal_helpers


def _filter_parser_functions(names: list[str], /) -> list[str]:  # pyright: ignore[reportUnusedFunction]
    """
    Filter list of function names to keep only parser functions.

    Args:
        names: List of function names to filter

    Returns:
        Filtered list containing only par_* or parse_* functions
    """
    return [name for name in names if _is_parser_function(name)]


def extract_parser_functions(zsh_src: Path, /) -> dict[str, FunctionNode]:
    """
    Extract parser functions from parse.syms file.

    Parser functions are identified by lines starting with 'L' (static) or 'E' (extern)
    that contain function declarations for par_* or parse_* functions.

    Format examples:
    - Lstatic void par_for _((int*cmplx));
    - Eextern Eprog parse_list _((void));

    Returns a dict mapping function names to FunctionNode objects containing:
    - name: function name
    - file: source file path relative to zsh_src
    - line: line number in .syms file
    - visibility: 'static' or 'extern'
    - signature: function signature (parameters and return type)
    - calls: empty list (populated later from call graph)
    """
    parse_syms = zsh_src / 'parse.syms'
    if not parse_syms.exists():
        return {}

    functions: dict[str, FunctionNode] = {}

    # Pattern to match function declarations in .syms files
    # Format: Lstatic void par_for _((int*cmplx));
    # or:     Eextern Eprog parse_list _((void));
    # or:     Eextern mod_import_function Eprog parse_list _((void));
    # Pattern explanation:
    # - [LE] = visibility indicator (static or extern)
    # - (static|extern) = visibility keyword
    # - (?:\w+\s+)* = optional intermediate keywords (e.g., mod_import_function)
    # - (\w+) = return type
    # - ([a-z_][a-z0-9_]*) = function name
    # - _\(\(([^)]*)\) = parameters
    func_pattern = re.compile(
        r'^[LE](static|extern)\s+(?:\w+\s+)*(\w+)\s+([a-z_][a-z0-9_]*)\s+_\(\(([^)]*)\)\);$'
    )

    with parse_syms.open() as f:
        for line_no, raw_line in enumerate(f, 1):
            line = raw_line.rstrip()

            # Skip preprocessor directives and empty lines
            if line.startswith(('E#', 'L#')) or not line.strip():
                continue

            match = func_pattern.match(line)
            if not match:
                continue

            visibility, return_type, func_name, params = match.groups()

            # Filter to parser functions only
            if not _is_parser_function(func_name):
                continue

            # Extract visibility
            vis = 'static' if visibility == 'static' else 'extern'

            # Build signature string
            signature = f'({params}) → {return_type}'

            functions[func_name] = {
                'name': func_name,
                'file': 'parse.syms',
                'line': line_no,
                'calls': [],
                'visibility': vis,
                'signature': signature,
            }

    return functions


def get_dispatcher_keywords(func_name: str, /) -> list[str]:
    """
    Get dispatcher-level keywords that are consumed before a parsing function is called.

    Some keywords are consumed in par_cmd's switch statement before the parsing function
    is invoked. These keywords should be prepended to the token sequence to match the
    semantic grammar rules documented in parse.c.

    Mapping (from par_cmd switch statement around line 966):
    - FOR/FOREACH/SELECT → par_for (FOR/FOREACH/SELECT already consumed)
    - CASE → par_case (CASE already consumed)
    - IF → par_if (IF/ELIF already consumed in dispatcher loop)
    - WHILE/UNTIL → par_while (WHILE/UNTIL already consumed)
    - REPEAT → par_repeat (REPEAT already consumed)
    - FUNCTION → par_funcdef (FUNCTION already consumed in higher dispatcher)
    - DINBRACK/DOUTBRACK → par_dinbrack (structural tokens)
    - INPAR → par_subsh (INPAR already consumed)
    - TIME → par_time (TIME already consumed at line 1032)

    Args:
        func_name: Parser function name

    Returns:
        List of dispatcher keywords (in order) that should appear at sequence start
    """
    dispatcher_keywords: dict[str, list[str]] = {
        'par_for': ['FOR'],  # FOREACH/SELECT handled within
        'par_case': ['CASE'],
        'par_if': ['IF'],  # ELIF handled within
        'par_while': ['WHILE'],  # UNTIL handled within
        'par_repeat': ['REPEAT'],
        'par_funcdef': ['FUNCTION'],
        'par_dinbrack': ['DINBRACK', 'DOUTBRACK'],
        'par_subsh': [],  # INPAR handled by par_cmd dispatch
        'par_time': ['TIME'],  # TIME already consumed at line 1032
    }

    return dispatcher_keywords.get(func_name, [])


def detect_state_assignment(
    token_spelling: str, lexer_states: set[str], /
) -> str | None:
    """
    Detect if token matches a lexer state variable and return its lowercase name.

    Args:
        token_spelling: Token spelling to check
        lexer_states: Set of valid lexer state names (lowercase)

    Returns:
        Lowercase state name if token matches a lexer state, None otherwise
    """
    if token_spelling in lexer_states:
        return token_spelling.lower()
    return None


def _parse_hash_entries(parser: ZshParser, /) -> Iterator[tuple[str, str]]:  # pyright: ignore[reportUnusedFunction]
    """Parse hash table entries from hashtable.c."""
    tu = parser.parse('hashtable.c', expand_macros=True)
    if (
        tu is not None
        and (
            reswds_cursor := find_cursor(
                tu.cursor,  # pyright: ignore[reportArgumentType]
                lambda c: c.kind == CursorKind.VAR_DECL and c.spelling == 'reswds',  # pyright: ignore[reportArgumentType,reportUnknownLambdaType,reportUnknownMemberType]
            )
        )
        is not None
        and (
            list_cursor := find_cursor(
                reswds_cursor,
                lambda c: c.kind == CursorKind.INIT_LIST_EXPR,  # pyright: ignore[reportArgumentType,reportUnknownLambdaType,reportUnknownMemberType]
            )
        )
        is not None
    ):
        for entry_cursor in list_cursor.get_children():
            hash_key: str | None = None
            token_name: str | None = None

            entry_children = list(entry_cursor.get_children())

            if len(entry_children) == 2:
                if entry_children[0].kind == CursorKind.INIT_LIST_EXPR:
                    hash_children = list(entry_children[0].get_children())
                    if (
                        len(hash_children) == 3
                        and hash_children[1].kind == CursorKind.UNEXPOSED_EXPR
                    ):
                        hash_key = next(hash_children[1].get_children()).spelling[1:-1]
                if entry_children[1].kind == CursorKind.DECL_REF_EXPR:
                    token_name = entry_children[1].spelling

            if hash_key is not None and token_name is not None:
                yield token_name, hash_key
