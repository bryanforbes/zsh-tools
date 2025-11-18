"""Low-level AST utilities for clang.cindex cursor operations.

This module provides foundational operations for walking and searching the AST,
serving as a base layer for other extraction modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from clang.cindex import Cursor, CursorKind

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


def walk_and_filter(cursor: Cursor, kind: CursorKind, /) -> Iterator[Cursor]:
    """
    Walk AST preorder and filter by cursor kind.

    Args:
        cursor: Root cursor to walk
        kind: CursorKind to filter by

    Yields:
        Cursors matching the specified kind
    """
    for node in cursor.walk_preorder():
        if node.kind == kind:
            yield node


def extract_token_name(expr_node: Cursor, /) -> str | None:
    """
    Extract token name from case expression node.

    Args:
        expr_node: Expression cursor to extract token from

    Returns:
        Token name (first token spelling) or None if not found
    """
    tokens = list(expr_node.get_tokens())
    if tokens:
        return tokens[0].spelling
    return None


def find_function_definitions(
    cursor: Cursor, names: set[str] | None = None, /
) -> Iterator[Cursor]:
    """
    Find function definitions in AST, optionally filtered by name.

    Args:
        cursor: Root cursor to walk
        names: Optional set of function names to filter by

    Yields:
        Function definition cursors matching criteria
    """
    for node in cursor.walk_preorder():
        if (
            node.kind == CursorKind.FUNCTION_DECL
            and node.is_definition()
            and (names is None or node.spelling in names)
        ):
            yield node


def find_cursor(cursor: Cursor, name: str, /) -> Cursor | None:
    """
    Find a child cursor by name.

    Args:
        cursor: Parent cursor to search
        name: Name of cursor to find

    Returns:
        Found cursor or None if not found
    """
    for child in cursor.get_children():
        if child.spelling == name:
            return child
    return None


def _find_child_cursors(cursor: Cursor, name: str, /) -> Iterator[Cursor]:  # pyright: ignore[reportUnusedFunction]
    """Find all direct child cursors with given name."""
    for child in cursor.get_children():
        if child.spelling == name:
            yield child


def _find_all_cursors(  # pyright: ignore[reportUnusedFunction]
    cursor: Cursor, predicate: Callable[[Cursor], bool], /
) -> Iterator[Cursor]:
    """Find all cursors matching predicate via preorder walk."""
    for node in cursor.walk_preorder():
        if predicate(node):
            yield node
