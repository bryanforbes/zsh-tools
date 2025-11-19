"""Branch extraction and AST analysis for Phase 2.4.1.

This module implements Stage 1 of Phase 2.4.1: extracting control flow branches
from parser function bodies. Each branch represents a distinct execution path
(if/else/switch case/loop), with metadata for reconstruction into grammar rules.

The algorithm:
1. Walk function body AST
2. Identify control structures (if/else, switch, while/for loops)
3. Extract metadata for each branch (condition, lines, type)
4. Return list of ControlFlowBranch stubs (items filled in Stage 2)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from clang.cindex import Cursor, CursorKind

from zsh_grammar.ast_utilities import walk_and_filter

if TYPE_CHECKING:
    from zsh_grammar._types import ControlFlowBranch


def extract_control_flow_branches(
    cursor: Cursor, func_name: str = ''
) -> list[ControlFlowBranch]:
    """Extract control flow branches from function body.

    Identifies all distinct execution paths in a parser function:
    - if/else/else-if chains as multiple branches
    - switch statements with each case as separate branch
    - while/for loops as single 'loop' branch
    - linear code as single 'sequential' branch

    Returns branches with metadata but without token/call items
    (items are populated in Stage 2).

    Args:
        cursor: Function definition cursor
        func_name: Function name for context-sensitive logic

    Returns:
        List of ControlFlowBranch with branch_id, branch_type, condition,
        start_line, end_line, and empty items list
    """
    branches: list[ControlFlowBranch] = []

    # Collect control structures
    if_stmts = list(walk_and_filter(cursor, CursorKind.IF_STMT))
    switch_stmts = list(walk_and_filter(cursor, CursorKind.SWITCH_STMT))
    while_stmts = list(walk_and_filter(cursor, CursorKind.WHILE_STMT))
    for_stmts = list(walk_and_filter(cursor, CursorKind.FOR_STMT))

    # Extract if/else chains (group into one unit with multiple branches)
    if if_stmts:
        if_branches = _extract_if_chain(if_stmts[0])
        branches.extend(if_branches)

    # Extract switch cases (each case is separate branch)
    if switch_stmts:
        switch_branches = _extract_switch_cases(switch_stmts[0])
        branches.extend(switch_branches)

    # Extract loops (one branch labeled 'loop')
    if while_stmts:
        loop_branch = _extract_loop(while_stmts[0], 'while')
        branches.append(loop_branch)
    elif for_stmts:
        loop_branch = _extract_loop(for_stmts[0], 'for')
        branches.append(loop_branch)

    # If no control structures, treat entire function body as sequential
    if not branches:
        branches = [_extract_sequential_body(cursor)]

    return branches


def _extract_if_chain(if_stmt: Cursor) -> list[ControlFlowBranch]:
    """Extract if/else-if/else as multiple branches.

    Walks the if statement and all else clauses to build a chain of branches,
    extracting the condition from each branch.

    Args:
        if_stmt: Initial if statement cursor

    Returns:
        List of ControlFlowBranch for if, else-if, else nodes
    """
    branches: list[ControlFlowBranch] = []
    counter = 0

    current: Cursor | None = if_stmt
    while current is not None:
        tokens = list(current.get_tokens())
        token_spellings = [t.spelling for t in tokens]

        # Determine branch type
        branch_type: str
        if 'if' in token_spellings:
            branch_type = 'if'
            branch_id = f'if_{counter}'
        elif 'else' in token_spellings and 'if' in token_spellings:
            branch_type = 'else_if'
            branch_id = f'else_if_{counter}'
        elif 'else' in token_spellings:
            branch_type = 'else'
            branch_id = f'else_{counter}'
        else:
            break

        # Extract condition for if/else-if
        condition: str | None = None
        token_condition: str | None = None
        if branch_type in ('if', 'else_if'):
            condition, token_condition = _extract_if_condition(current)

        # Build branch
        branch: ControlFlowBranch = {
            'branch_id': branch_id,
            'branch_type': branch_type,  # type: ignore[typeddict-unknown-key]
            'start_line': current.extent.start.line,
            'end_line': current.extent.end.line,
            'items': [],
        }

        if condition:
            branch['condition'] = condition
        if token_condition:
            branch['token_condition'] = token_condition

        branches.append(branch)

        # Move to next else clause
        current = _find_else_clause(current)
        counter += 1

    return branches


def _extract_if_condition(if_stmt: Cursor) -> tuple[str | None, str | None]:
    """Extract condition string and semantic token from if statement.

    Extracts the raw condition (e.g., 'tok == INPAR') and the semantic token
    name if applicable (e.g., 'INPAR').

    Args:
        if_stmt: If statement cursor

    Returns:
        Tuple of (condition_str, token_name) or (None, None) if not found
    """
    # Find the condition node (usually first child after 'if' keyword)
    for child in if_stmt.get_children():
        # Skip until we find the condition (not statement body)
        if child.kind in (
            CursorKind.COMPOUND_STMT,
            CursorKind.IF_STMT,
        ):
            continue

        tokens = list(child.get_tokens())
        if not tokens:
            continue

        # Reconstruct condition string from tokens
        condition_str = ' '.join(t.spelling for t in tokens)

        # Extract semantic token if present (e.g., INPAR from 'tok == INPAR')
        token_name: str | None = None
        for token in tokens:
            spelling = token.spelling
            if (
                spelling.isupper()
                and len(spelling) > 2
                and spelling
                not in (
                    'IF',
                    'ELSE',
                    'ELIF',
                )
            ):
                token_name = spelling
                break

        return condition_str, token_name

    return None, None


def _find_else_clause(if_stmt: Cursor) -> Cursor | None:
    """Find the else clause of an if statement.

    Args:
        if_stmt: If statement cursor

    Returns:
        Else statement cursor or None if not found
    """
    # The else clause is typically the last child of an if statement
    children = list(if_stmt.get_children())
    if len(children) >= 2:
        last_child = children[-1]
        # Check if it's a statement (could be another if for else-if)
        if last_child.kind in (
            CursorKind.COMPOUND_STMT,
            CursorKind.IF_STMT,
        ):
            return last_child if last_child.kind == CursorKind.IF_STMT else None

    return None


def _extract_switch_cases(switch_stmt: Cursor) -> list[ControlFlowBranch]:
    """Extract switch cases as separate branches.

    Each case statement becomes a separate branch with its own branch_id
    (e.g., 'switch_case_FOR', 'switch_case_default').

    Args:
        switch_stmt: Switch statement cursor

    Returns:
        List of ControlFlowBranch for each case
    """
    branches: list[ControlFlowBranch] = []

    for case_stmt in walk_and_filter(switch_stmt, CursorKind.CASE_STMT):
        # Extract case label (token name or 'default')
        case_label = _extract_case_label(case_stmt)

        case_branch: ControlFlowBranch = {
            'branch_id': f'switch_case_{case_label}',
            'branch_type': 'switch_case',  # type: ignore[typeddict-unknown-key]
            'start_line': case_stmt.extent.start.line,
            'end_line': case_stmt.extent.end.line,
            'items': [],
        }

        # Add condition
        if case_label != 'default':
            case_branch['condition'] = f'tok == {case_label}'
            case_branch['token_condition'] = case_label

        branches.append(case_branch)

    # Handle default case if present
    for default_stmt in walk_and_filter(switch_stmt, CursorKind.DEFAULT_STMT):
        default_branch: ControlFlowBranch = {
            'branch_id': 'switch_case_default',
            'branch_type': 'switch_case',  # type: ignore[typeddict-unknown-key]
            'condition': 'default',
            'start_line': default_stmt.extent.start.line,
            'end_line': default_stmt.extent.end.line,
            'items': [],
        }
        branches.append(default_branch)

    return branches


def _extract_case_label(case_stmt: Cursor) -> str:
    """Extract the label from a case statement.

    Args:
        case_stmt: Case statement cursor

    Returns:
        Token name (e.g., 'FOR') or 'default'
    """
    # Get the expression associated with the case
    for child in case_stmt.get_children():
        tokens = list(child.get_tokens())
        if tokens:
            # Return first uppercase token (the case label)
            for token in tokens:
                spelling = token.spelling
                if spelling.isupper() and len(spelling) > 1:
                    return spelling
    return 'default'


def _extract_loop(loop_stmt: Cursor, loop_type: str) -> ControlFlowBranch:
    """Extract while or for loop as single 'loop' branch.

    Args:
        loop_stmt: While or for statement cursor
        loop_type: 'while' or 'for'

    Returns:
        ControlFlowBranch with branch_type='loop'
    """
    return {
        'branch_id': 'loop',
        'branch_type': 'loop',  # type: ignore[typeddict-unknown-key]
        'start_line': loop_stmt.extent.start.line,
        'end_line': loop_stmt.extent.end.line,
        'items': [],
    }


def _extract_sequential_body(cursor: Cursor) -> ControlFlowBranch:
    """Extract entire function body as single sequential branch.

    Used when no control structures are detected.

    Args:
        cursor: Function definition cursor

    Returns:
        ControlFlowBranch with branch_type='sequential'
    """
    return {
        'branch_id': 'sequential',
        'branch_type': 'sequential',  # type: ignore[typeddict-unknown-key]
        'start_line': cursor.extent.start.line,
        'end_line': cursor.extent.end.line,
        'items': [],
    }
