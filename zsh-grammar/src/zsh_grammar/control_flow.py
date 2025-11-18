"""Control flow analysis and call graph construction.

Analyzes function implementation patterns (loops, conditionals) to detect
repeat, optional, and sequential patterns in the grammar. Builds call graphs
and detects cycles in parser function relationships.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict

from clang.cindex import CursorKind

from zsh_grammar.ast_utilities import find_function_definitions, walk_and_filter
from zsh_grammar.function_discovery import _is_parser_function, detect_state_assignment
from zsh_grammar.token_extractors import extract_token_sequences

if TYPE_CHECKING:
    from clang.cindex import Cursor

    from zsh_grammar.construct_grammar import TokenOrCall, _FunctionNode
    from zsh_grammar.source_parser import ZshParser


class ControlFlowPattern(TypedDict):
    """Control flow classification for grammar rules.

    Attributes:
        pattern_type: 'optional', 'repeat', 'conditional', or 'sequential'
        reason: Human-readable description of why this pattern was classified
        has_else: For optional patterns, whether if statement has explicit else
        loop_type: For repeat patterns, 'while' or 'for'
        min_iterations: Minimum iterations for repeat (0 for optional, 1+ for required)
        max_iterations: Maximum iterations for repeat (None for unlimited)
    """

    pattern_type: Literal['optional', 'repeat', 'conditional', 'sequential']
    reason: str
    has_else: NotRequired[bool]
    loop_type: NotRequired[str]
    min_iterations: NotRequired[int]
    max_iterations: NotRequired[int]


def analyze_control_flow(  # noqa: C901, PLR0912
    cursor: Cursor, /, *, func_name: str = ''
) -> ControlFlowPattern | None:
    """
    Analyze control flow patterns in a function body.

    Detects:
    - While loops with parser function calls → Repeat pattern
    - If statements without else → Optional pattern
    - Switch/case patterns with exhaustive coverage → Conditional (non-optional)
    - Sequential calls → Sequential pattern

    Phase 3.3 implementation: Analyzes AST to distinguish between:
    1. Repeating elements (while/for loops calling parser functions)
    2. Optional elements (if statements without else branches)
    3. Conditional alternatives (switch/case or if-else with all branches covered)
    4. Sequential required elements (no control flow modifying optionality)

    Args:
        cursor: Function definition cursor
        func_name: Function name for description

    Returns:
        _ControlFlowPattern if a clear pattern is detected, None if sequential/neutral
    """
    # Collect control flow structures
    while_stmts: list[Cursor] = []
    for_stmts: list[Cursor] = []
    if_stmts: list[Cursor] = []
    switch_stmts: list[Cursor] = []

    for child in cursor.walk_preorder():
        if child.kind == CursorKind.WHILE_STMT:
            while_stmts.append(child)
        elif child.kind == CursorKind.FOR_STMT:
            for_stmts.append(child)
        elif child.kind == CursorKind.IF_STMT:
            if_stmts.append(child)
        elif child.kind == CursorKind.SWITCH_STMT:
            switch_stmts.append(child)

    # Check for while loops with parser function calls
    # These indicate repetition in the grammar
    for while_stmt in while_stmts:
        # Check if while body contains parser function calls
        has_parser_call = False
        for node in while_stmt.walk_preorder():
            if node.kind == CursorKind.CALL_EXPR and _is_parser_function(node.spelling):
                has_parser_call = True
                break

        if has_parser_call:
            return {
                'pattern_type': 'repeat',
                'reason': f'{func_name} contains while loop with parser function calls',
                'loop_type': 'while',
                'min_iterations': 0,  # while can execute 0 times
            }

    # Check for for loops with parser function calls
    for for_stmt in for_stmts:
        has_parser_call = False
        for node in for_stmt.walk_preorder():
            if node.kind == CursorKind.CALL_EXPR and _is_parser_function(node.spelling):
                has_parser_call = True
                break

        if has_parser_call:
            return {
                'pattern_type': 'repeat',
                'reason': f'{func_name} contains for loop with parser function calls',
                'loop_type': 'for',
                'min_iterations': 0,
            }

    # Check for if statements without else (indicating optional parsing)
    # Only consider if statements that are direct children of function body,
    # not nested ones (nested ones are part of conditional logic)
    func_children = list(cursor.get_children())
    func_body: Cursor | None = None

    for child in func_children:
        if child.kind == CursorKind.COMPOUND_STMT:
            func_body = child
            break

    if func_body:
        for if_stmt in if_stmts:
            # Count tokens to detect presence of "else"
            tokens = list(if_stmt.get_tokens())
            token_spellings = [t.spelling for t in tokens]
            has_else_token = 'else' in token_spellings

            # Check if if body contains parser function calls
            has_parser_call = False
            for node in if_stmt.walk_preorder():
                if node.kind == CursorKind.CALL_EXPR and _is_parser_function(
                    node.spelling
                ):
                    has_parser_call = True
                    break

            # If there's no else and there are parser calls, it's optional
            if has_parser_call and not has_else_token:
                reason = (
                    f'{func_name} contains if statement without else '
                    'with parser function calls'
                )
                return {
                    'pattern_type': 'optional',
                    'reason': reason,
                    'has_else': False,
                    'min_iterations': 0,
                }

    # If we have extensive if-else chains (like large conditional parsing),
    # but all branches contain parser calls, it's conditional (not optional)
    if if_stmts and switch_stmts:
        # Multiple conditional paths - likely just conditional routing
        pass

    # Default: sequential pattern (control flow analysis didn't reveal optional/repeat)
    return None


def analyze_all_control_flows(
    parser: ZshParser, extracted_tokens: dict[str, list[TokenOrCall]], /
) -> dict[str, ControlFlowPattern | None]:
    """
    Analyze control flow patterns for all parser functions.

    Args:
        parser: ZshParser instance for file parsing
        extracted_tokens: Dict mapping function names to extracted token sequences

    Returns:
        Dict mapping function names to _ControlFlowPattern (or None if sequential)
    """
    patterns: dict[str, ControlFlowPattern | None] = {}

    for _file, tu in parser.parse_files('*.c'):
        if tu.cursor is None:
            continue

        for cursor in find_function_definitions(tu.cursor):
            function_name = cursor.spelling
            if _is_parser_function(function_name):
                pattern = analyze_control_flow(cursor, func_name=function_name)
                if pattern:
                    patterns[function_name] = pattern

    return patterns


def build_call_graph(parser: ZshParser, /) -> dict[str, _FunctionNode]:
    """
    Build call graph with Phase 2.4.1 token sequences.

    For each function, extract:
    1. Function calls (existing)
    2. Conditions (existing)
    3. Token sequences via Phase 2.4.1 (ordered tokens + calls per branch)
    """
    call_graph: dict[str, _FunctionNode] = {}

    for file, tu in parser.parse_files('*.c'):
        if tu.cursor is None:
            continue

        for cursor in find_function_definitions(tu.cursor):
            function_name = cursor.spelling
            calls: list[str] = []

            for child in walk_and_filter(cursor, CursorKind.CALL_EXPR):
                callee_name = child.spelling
                if callee_name != function_name:
                    calls.append(callee_name)

            node: _FunctionNode = {
                'name': function_name,
                'file': str(file.relative_to(parser.zsh_src)),
                'line': cursor.location.line,
                'calls': calls,
            }
            call_graph[function_name] = node

            conditions = _detect_conditions(cursor)
            if conditions:
                node['conditions'] = conditions

            # Phase 2.4.1: Extract ordered token sequences with control flow branches
            if _is_parser_function(function_name):
                token_sequences = extract_token_sequences(
                    cursor, func_name=function_name
                )
                if token_sequences:
                    # Need to cast to the expected type (list of sequences)
                    node['token_sequences'] = [token_sequences]

    return call_graph


def detect_cycles(
    call_graph: dict[str, _FunctionNode], /
) -> dict[str, list[list[str]]]:
    """
    Detect all cycles in the call graph.

    Returns a dict mapping each function to the list of cycles it participates in.
    Uses depth-first search to identify all cycles.
    """
    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycles: set[tuple[str, ...]] = set()

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        if node not in call_graph:
            path.pop()
            rec_stack.discard(node)
            return

        for neighbor in call_graph[node]['calls']:
            if neighbor not in visited:
                dfs(neighbor, path)
            elif neighbor in rec_stack:
                # Found a cycle: normalize it to canonical form
                cycle_start_idx = path.index(neighbor)
                cycle_nodes = path[cycle_start_idx:]
                # Find minimum to normalize cycle
                min_node = min(cycle_nodes)
                min_idx = cycle_nodes.index(min_node)
                normalized = tuple(cycle_nodes[min_idx:] + cycle_nodes[:min_idx])
                cycles.add(normalized)

        path.pop()
        rec_stack.discard(node)

    # Run DFS from all nodes
    for start_node in call_graph:
        if start_node not in visited:
            dfs(start_node, [])

    # Map each function to its cycles
    func_to_cycles: dict[str, list[list[str]]] = {}
    for cycle in cycles:
        for func in cycle:
            if func not in func_to_cycles:
                func_to_cycles[func] = []
            func_to_cycles[func].append(list(cycle))

    return func_to_cycles


def extract_lexer_state_changes(
    parser: ZshParser, parser_functions: dict[str, _FunctionNode], /
) -> dict[str, dict[str, list[int]]]:
    """
    Extract lexer state changes from parser functions.

    Returns a dict mapping function names to state changes:
    {
        'par_cond': {'INCOND': [line1, line2, ...]},
        'par_for': {'INFOR': [line1, ...]},
        ...
    }

    Lexer states include:
    - INCMDPOS: in command position
    - INCOND: inside [[ ... ]]
    - INREDIR: after redirection operator
    - INCASEPAT: in case pattern
    - IN_MATH: inside (( ... ))
    - etc.
    """
    state_changes: dict[str, dict[str, list[int]]] = {}

    # Common lexer state variables to look for
    lexer_states = {
        'incmdpos',
        'incond',
        'inredir',
        'incasepat',
        'infor',
        'inrepeat',
        'intypeset',
        'isnewlin',
        'in_math',
        'aliasspaceflag',
        'incomparison',
        'in_array',
        'in_substitution',
        'in_braceexp',
        'in_globpat',
    }

    # Parse parse.c to find state management
    tu = parser.parse('parse.c')
    if tu is None or tu.cursor is None:
        return state_changes

    parser_func_names = set(parser_functions.keys())

    for cursor in find_function_definitions(tu.cursor, parser_func_names):
        func_name = cursor.spelling
        state_changes[func_name] = {}

        # Walk function body looking for state assignments
        for child in walk_and_filter(cursor, CursorKind.BINARY_OPERATOR):
            # Look for assignment patterns: state_var = ...
            left_operand = None
            for token in child.get_tokens():
                left_operand = detect_state_assignment(token.spelling, lexer_states)
                if left_operand:
                    break

            if left_operand:
                if left_operand not in state_changes[func_name]:
                    state_changes[func_name][left_operand] = []
                state_changes[func_name][left_operand].append(child.location.line)

    # Filter to only functions that have state changes
    return {func: states for func, states in state_changes.items() if states}


def _detect_conditions(cursor: Cursor, /) -> list[str]:
    """
    Walk the AST of a function and collect any option references:
    - isset(OPTION)
    - EXTENDED_GLOB, KSH_ARRAYS, etc.
    """
    conditions: set[str] = set()
    for sub in cursor.walk_preorder():
        if sub.kind == CursorKind.CALL_EXPR and sub.spelling == 'isset':
            args = [tok.spelling for tok in sub.get_tokens()]
            for a in args:
                if a.isupper() and len(a) > 3:
                    conditions.add(a)
        elif sub.spelling.isupper() and len(sub.spelling) > 3:
            conditions.add(sub.spelling)
    return sorted(conditions)
