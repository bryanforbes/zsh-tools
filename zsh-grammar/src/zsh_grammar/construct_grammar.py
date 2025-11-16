from __future__ import annotations

import json
import os
import re
import subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import TYPE_CHECKING, Final, NotRequired, TypedDict, cast

import jsonschema
from clang.cindex import Cursor, CursorKind, StorageClass

from zsh_grammar.grammar_utils import (
    create_lex_state,
    create_optional,
    create_ref,
    create_repeat,
    create_source,
    create_terminal,
    create_token,
    create_union,
    create_variant,
)
from zsh_grammar.source_parser import ZshParser

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from zsh_grammar._types import Grammar, GrammarNode, Language

PROJECT_ROOT: Final = Path(__file__).resolve().parents[3]


def _is_parser_function(name: str, /) -> bool:
    """Check if a function name is a parser function (par_* or parse_*)."""
    return name.startswith(('par_', 'parse_'))


def _walk_and_filter(cursor: Cursor, kind: CursorKind, /) -> Iterator[Cursor]:
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


def _extract_token_name(expr_node: Cursor, /) -> str | None:
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


def _filter_parser_functions(names: list[str], /) -> list[str]:  # pyright: ignore[reportUnusedFunction]
    """
    Filter list of function names to keep only parser functions.

    Args:
        names: List of function names to filter

    Returns:
        Filtered list containing only par_* or parse_* functions
    """
    return [name for name in names if _is_parser_function(name)]


def _detect_state_assignment(
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


def _find_function_definitions(
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


class _FunctionNode(TypedDict):
    name: str
    file: str
    line: int
    calls: list[str]
    conditions: NotRequired[list[str]]
    signature: NotRequired[str]
    visibility: NotRequired[str]


class _ControlFlowPattern(TypedDict):
    """Control flow classification for grammar rules.

    Attributes:
        pattern_type: 'optional', 'repeat', 'conditional', or 'sequential'
        reason: Human-readable description of why this pattern was classified
        has_else: For optional patterns, whether if statement has explicit else
        loop_type: For repeat patterns, 'while' or 'for'
        min_iterations: Minimum iterations for repeat (0 for optional, 1+ for required)
        max_iterations: Maximum iterations for repeat (None for unlimited)
    """

    pattern_type: str  # 'optional', 'repeat', 'conditional', 'sequential'
    reason: str
    has_else: NotRequired[bool]
    loop_type: NotRequired[str]
    min_iterations: NotRequired[int]
    max_iterations: NotRequired[int]


def _extract_parser_functions(zsh_src: Path, /) -> dict[str, _FunctionNode]:
    """
    Extract parser functions from parse.syms file.

    Parser functions are identified by lines starting with 'L' (static) or 'E' (extern)
    that contain function declarations for par_* or parse_* functions.

    Format examples:
    - Lstatic void par_for _((int*cmplx));
    - Eextern Eprog parse_list _((void));

    Returns a dict mapping function names to _FunctionNode objects containing:
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

    functions: dict[str, _FunctionNode] = {}

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


def _build_call_graph(parser: ZshParser, /) -> dict[str, _FunctionNode]:
    call_graph: dict[str, _FunctionNode] = {}

    for file, tu in parser.parse_files('*.c'):
        if tu.cursor is None:
            continue

        for cursor in _find_function_definitions(tu.cursor):
            function_name = cursor.spelling
            calls: list[str] = []

            for child in _walk_and_filter(cursor, CursorKind.CALL_EXPR):
                callee_name = child.spelling
                if callee_name != function_name:
                    calls.append(callee_name)

            node = call_graph[function_name] = {
                'name': function_name,
                'file': str(file.relative_to(parser.zsh_src)),
                'line': cursor.location.line,
                'calls': calls,
            }

            conditions = _detect_conditions(cursor)
            if conditions:
                node['conditions'] = conditions

    return call_graph


def _extract_lexer_state_changes(
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

    for cursor in _find_function_definitions(tu.cursor, parser_func_names):
        func_name = cursor.spelling
        state_changes[func_name] = {}

        # Walk function body looking for state assignments
        for child in _walk_and_filter(cursor, CursorKind.BINARY_OPERATOR):
            # Look for assignment patterns: state_var = ...
            left_operand = None
            for token in child.get_tokens():
                left_operand = _detect_state_assignment(token.spelling, lexer_states)
                if left_operand:
                    break

            if left_operand:
                if left_operand not in state_changes[func_name]:
                    state_changes[func_name][left_operand] = []
                state_changes[func_name][left_operand].append(child.location.line)

    # Filter to only functions that have state changes
    return {func: states for func, states in state_changes.items() if states}


def _analyze_control_flow(  # noqa: C901, PLR0912
    cursor: Cursor, /, *, func_name: str = ''
) -> _ControlFlowPattern | None:
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
            return _ControlFlowPattern(
                pattern_type='repeat',
                reason=f'{func_name} contains while loop with parser function calls',
                loop_type='while',
                min_iterations=0,  # while can execute 0 times
            )

    # Check for for loops with parser function calls
    for for_stmt in for_stmts:
        has_parser_call = False
        for node in for_stmt.walk_preorder():
            if node.kind == CursorKind.CALL_EXPR and _is_parser_function(node.spelling):
                has_parser_call = True
                break

        if has_parser_call:
            return _ControlFlowPattern(
                pattern_type='repeat',
                reason=f'{func_name} contains for loop with parser function calls',
                loop_type='for',
                min_iterations=0,
            )

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
                return _ControlFlowPattern(
                    pattern_type='optional',
                    reason=reason,
                    has_else=False,
                    min_iterations=0,
                )

    # If we have extensive if-else chains (like large conditional parsing),
    # but all branches contain parser calls, it's conditional (not optional)
    if if_stmts and switch_stmts:
        # Multiple conditional paths - likely just conditional routing
        pass

    # Default: sequential pattern (control flow analysis didn't reveal optional/repeat)
    return None


def _detect_cycles(
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


def _function_to_rule_name(func_name: str, /) -> str:
    """
    Convert function name to grammar rule name.

    - par_for → for
    - parse_list → list
    - par_cond_double → cond_double
    """
    if func_name.startswith('par_'):
        return func_name[4:]  # Remove 'par_' prefix
    if func_name.startswith('parse_'):
        return func_name[6:]  # Remove 'parse_' prefix
    return func_name


def _build_func_to_rule_map(  # pyright: ignore[reportUnusedFunction]
    parser_functions: dict[str, _FunctionNode], /
) -> dict[str, str]:
    """
    Build a mapping from parser function names to rule names.

    Iterates through parser functions and converts function names to rule names
    using standard naming conventions.
    """
    func_to_rule: dict[str, str] = {}
    for func_name in parser_functions:
        if _is_parser_function(func_name):
            rule_name = _function_to_rule_name(func_name)
            func_to_rule[func_name] = rule_name
    return func_to_rule


def _analyze_all_control_flows(
    parser: ZshParser, parser_functions: dict[str, _FunctionNode], /
) -> dict[str, _ControlFlowPattern]:
    """
    Analyze control flow patterns for all parser functions.

    Phase 3.3: Walks AST of each parser function and detects:
    - While/for loops with parser calls → Repeat patterns
    - If statements without else → Optional patterns
    - Other control flow → Sequential/conditional patterns

    Args:
        parser: ZshParser instance for parsing C source
        parser_functions: Map of parser function definitions

    Returns:
        Dict mapping function names to detected control flow patterns
    """
    control_flows: dict[str, _ControlFlowPattern] = {}
    parser_func_names = set(parser_functions.keys())

    # Parse parse.c to get AST for all functions
    tu = parser.parse('parse.c')
    if tu is None or tu.cursor is None:
        return control_flows

    # Analyze each parser function
    for cursor in _find_function_definitions(tu.cursor, parser_func_names):
        func_name = cursor.spelling
        pattern = _analyze_control_flow(cursor, func_name=func_name)
        if pattern:
            control_flows[func_name] = pattern

    return control_flows


def _build_grammar_rules(  # noqa: C901, PLR0912
    call_graph: dict[str, _FunctionNode],
    parser_functions: dict[str, _FunctionNode],
    control_flows: dict[str, _ControlFlowPattern] | None = None,
    token_to_rules: dict[str, list[str]] | None = None,
    /,
) -> Language:
    """
    Infer grammar rules from the call graph using call pattern heuristics.

    Strategy:
    1. Identify core parsing functions (par_* and parse_* functions)
    2. For each function, extract unique parse function calls
    3. Classify based on:
        - No calls: leaf/terminal
        - 1 call: direct delegation (reference)
        - Multiple calls: union (alternatives/dispatch)
    4. Apply control flow analysis (Phase 3.3):
        - Wrap optional references in Optional nodes
        - Wrap repeating patterns in Repeat nodes
    5. Apply token dispatch integration (Phase 3.2):
        - For dispatcher rules, include token references in unions
    6. Handle cycles by using references (breaking circular dependencies)

    Cycles are handled by detecting them and using $ref to break cycles
    rather than inlining definitions. This allows the grammar to remain acyclic
    while accurately representing recursive parsing patterns.

    Args:
        call_graph: Function call graph from AST analysis
        parser_functions: Parser function definitions from .syms
        control_flows: Optional control flow patterns from Phase 3.3
        token_to_rules: Optional token-to-rule mappings from conditionals
            (Phase 3.2)
    """
    rules: Language = {}

    # Identify core parsing functions
    core_parse_funcs = {
        name: node for name, node in call_graph.items() if _is_parser_function(name)
    }

    # Build reverse mapping from rule names to tokens (for Phase 3.2)
    rule_to_tokens: dict[str, list[str]] = {}
    default_marker = '__default__'
    if token_to_rules:
        for token_name, rule_names in token_to_rules.items():
            if token_name != default_marker:  # Skip special marker
                for rule_name in rule_names:
                    if rule_name not in rule_to_tokens:
                        rule_to_tokens[rule_name] = []
                    rule_to_tokens[rule_name].append(token_name)

    # Build rules from parse functions
    for func_name, node in core_parse_funcs.items():
        rule_name = _function_to_rule_name(func_name)

        # Extract unique parse function calls
        called_funcs = node['calls']
        unique_parse_calls = sorted(
            {f for f in called_funcs if _is_parser_function(f) and f != func_name}
        )

        # Convert called function names to rule refs
        rule_refs = [create_ref(_function_to_rule_name(f)) for f in unique_parse_calls]

        # Build source info from parser_functions if available
        if func_name in parser_functions:
            pf = parser_functions[func_name]
            source_info = create_source(pf['file'], pf['line'], function=func_name)
        else:
            # Fallback from call_graph
            source_info = create_source(node['file'], node['line'], function=func_name)

        # Classify rule based on unique calls
        if not unique_parse_calls:
            # No parse function calls -> leaf/terminal
            # These are typically token consumers (par_getword, etc.)
            rules[rule_name] = create_terminal(f'[{rule_name}]', source=source_info)
        elif len(unique_parse_calls) == 1:
            # Single unique parse call -> direct delegation/reference
            # Don't wrap single refs in a sequence (sequences need 2+ elements)
            ref_name = _function_to_rule_name(unique_parse_calls[0])
            base_rule = create_ref(ref_name, source=source_info)

            # Phase 3.3: Apply control flow analysis
            if control_flows and func_name in control_flows:
                flow = control_flows[func_name]
                if flow['pattern_type'] == 'optional':
                    base_rule = create_optional(
                        base_rule,
                        description=flow['reason'],
                        source=source_info,
                    )
                elif flow['pattern_type'] == 'repeat':
                    min_iter = flow.get('min_iterations', 0)
                    base_rule = create_repeat(
                        base_rule,
                        min=min_iter,
                        description=flow['reason'],
                        source=source_info,
                    )

            rules[rule_name] = base_rule
        else:
            # Multiple unique calls -> union/alternatives
            # (typically via switch/if statements with mutually exclusive branches)
            # Cycles are naturally broken because we use refs, not inlining

            # Phase 3.2: Integrate token dispatch into union
            union_nodes: list[GrammarNode] = list(rule_refs)
            if rule_name in rule_to_tokens:
                # This rule is a dispatcher: include token references in the union
                tokens = sorted(rule_to_tokens[rule_name])
                for token_name in tokens:
                    union_nodes.insert(0, create_ref(token_name))

            union_rule = create_union(union_nodes, source=source_info)

            # Phase 3.3: Apply control flow analysis to union
            if control_flows and func_name in control_flows:
                flow = control_flows[func_name]
                if flow['pattern_type'] == 'optional':
                    union_rule = create_optional(
                        union_rule,
                        description=flow['reason'],
                        source=source_info,
                    )
                elif flow['pattern_type'] == 'repeat':
                    min_iter = flow.get('min_iterations', 0)
                    union_rule = create_repeat(
                        union_rule,
                        min=min_iter,
                        description=flow['reason'],
                        source=source_info,
                    )

            rules[rule_name] = union_rule

    return rules


def _embed_lexer_state_conditions(
    rules: Language,
    lexer_states: dict[str, dict[str, list[int]]],
    parser_functions: dict[str, _FunctionNode],
    /,
) -> Language:
    """
    Embed lexer state changes as Condition/Variant nodes in grammar rules.

    Phase 4.3: For each parser function that modifies lexer state, add variant
    definitions showing which lexer states are set when the rule is active.

    Args:
        rules: Grammar rules generated from call graph
        lexer_states: Maps function names to state changes
            {
                'par_cond': {'incond': [line1, line2, ...]},
                'par_for': {'infor': [line1, ...]},
                ...
            }
        parser_functions: Map of parser function definitions from .syms

    Returns:
        Enhanced language rules with lexer state documentation/variants
    """
    # Map lowercase state names to SCREAMING_SNAKE_CASE for schema compliance
    state_case_map: dict[str, str] = {
        'incmdpos': 'INCMDPOS',
        'incond': 'INCOND',
        'inredir': 'INREDIR',
        'incasepat': 'INCASEPAT',
        'infor': 'INFOR',
        'inrepeat': 'INREPEAT',
        'intypeset': 'INTYPESET',
        'isnewlin': 'ISNEWLIN',
        'in_math': 'IN_MATH',
        'aliasspaceflag': 'ALIASSPACEFLAG',
        'incomparison': 'INCOMPARISON',
        'in_array': 'IN_ARRAY',
        'in_substitution': 'IN_SUBSTITUTION',
        'in_braceexp': 'IN_BRACEEXP',
        'in_globpat': 'IN_GLOBPAT',
    }

    enhanced_rules = dict(rules)

    # For each function that modifies lexer state
    for func_name, states in lexer_states.items():
        rule_name = _function_to_rule_name(func_name)

        # Only enhance rules that exist (skip if rule wasn't generated)
        if rule_name not in enhanced_rules:
            continue

        base_rule = enhanced_rules[rule_name]

        # Convert state names to proper case
        uppercase_states: list[str] = []
        for state_name in states:
            if state_name in state_case_map:
                uppercase_states.append(state_case_map[state_name])

        # If we have state changes, add variant documentation
        if uppercase_states:
            # For each state this rule modifies, create a variant showing
            # that when this rule is active, that lexer state is set
            variant_list: list[GrammarNode] = []

            for lex_state in sorted(uppercase_states):
                # Get source location from first state change line
                state_lines = states[
                    next(s for s in states if state_case_map.get(s) == lex_state)
                ]
                source_line = state_lines[0] if state_lines else 0

                # Build source info for variant
                variant_source = create_source(
                    'parse.c',
                    source_line,
                    function=func_name,
                    context=f'sets {lex_state}',
                )

                # Create variant: this rule with condition on active lexer state
                # Note: lex_state is validated at runtime via state_case_map
                variant = create_variant(
                    base_rule,
                    create_lex_state(lex_state),  # pyright: ignore[reportArgumentType]
                    source=variant_source,
                    description=f'{rule_name} sets lexer state {lex_state}',
                )
                variant_list.append(variant)

            # Replace rule with union containing base rule and all state variants
            # This allows rule matching unconditionally OR with specific state context
            source_info = rules[rule_name].get('source')
            enhanced_rules[rule_name] = create_union(
                [base_rule, *variant_list],
                source=source_info,  # pyright: ignore[reportArgumentType]
                description=(
                    f'{rule_name} '
                    f'(modifies lexer states: {", ".join(uppercase_states)})'
                ),
            )

    return enhanced_rules


class _TokenDef(TypedDict):
    token: str
    value: int
    text: list[str]
    file: str
    line: int


def _find_cursor(
    cursor: Cursor | None, predicate: Callable[[Cursor], bool], /
) -> Cursor | None:
    if cursor is None:
        return None

    for child in cursor.get_children():
        if predicate(child):
            return child
    return None


def _find_child_cursors(
    cursor: Cursor | None, predicate: Callable[[Cursor], bool], /
) -> Iterator[Cursor]:
    if cursor is not None:
        for child in cursor.get_children():
            if predicate(child):
                yield child


def _find_all_cursors(  # pyright: ignore[reportUnusedFunction]
    cursor: Cursor | None, predicate: Callable[[Cursor], bool], /
) -> Iterator[Cursor]:
    if cursor is not None:
        for child in cursor.walk_preorder():
            if predicate(child):
                yield child


def _parse_hash_entries(parser: ZshParser, /) -> Iterator[tuple[str, str]]:
    tu = parser.parse('hashtable.c', expand_macros=True)
    if (
        tu is not None
        and (
            reswds_cursor := _find_cursor(
                tu.cursor,
                lambda c: c.kind == CursorKind.VAR_DECL and c.spelling == 'reswds',
            )
        )
        is not None
        and (
            list_cursor := _find_cursor(
                reswds_cursor,
                lambda c: c.kind == CursorKind.INIT_LIST_EXPR,
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


def _parse_token_strings(parser: ZshParser, /) -> Iterator[tuple[int, str]]:
    tu = parser.parse('lex.c', expand_macros=True)

    if tu is None or tu.cursor is None:
        return

    if (
        tokstrings_cursor := _find_cursor(
            tu.cursor,
            lambda c: c.kind == CursorKind.VAR_DECL
            and c.spelling == 'tokstrings'
            and c.storage_class != StorageClass.EXTERN,
        )
    ) is not None and (
        init_list_cursor := _find_cursor(
            tokstrings_cursor, lambda c: c.kind == CursorKind.INIT_LIST_EXPR
        )
    ) is not None:
        for index, item in enumerate(init_list_cursor.get_children()):
            if item.kind == CursorKind.UNEXPOSED_EXPR:
                tokens = list(item.get_tokens())
                if tokens:
                    text = ''.join([token.spelling for token in tokens])
                    print(text)
                    if text.startswith('"') and text.endswith('"'):
                        text = text[1:-1]

                    if text != '((void*)0)':
                        yield index, text


def _extract_case_statements(  # noqa: C901, PLR0912, PLR0915
    cursor: Cursor, /
) -> Iterator[tuple[str, str]]:
    """
    Walk the AST and extract case statements from switch statements.

    Yields tuples of (token_name, handler_call) from patterns like:
        case FOR:
            ...
            par_for(...);
            ...

    Algorithm:
    1. Find SWITCH_STMT nodes
    2. Within each switch's compound statement, build a map of:
       - Position of each case label
       - Token name for that case
    3. For each case, find the first par_* call that appears after the case label
       (but before the next case/default/end of switch)

    Returns: Iterator of (token_name, handler_function_name) tuples.
    """
    # Walk preorder to find SWITCH_STMT nodes
    for node in cursor.walk_preorder():
        if node.kind == CursorKind.SWITCH_STMT:
            # Find the compound statement inside the switch
            for stmt_body in node.get_children():
                if stmt_body.kind == CursorKind.COMPOUND_STMT:
                    # Build a list of all children with their indices
                    children = list(stmt_body.get_children())

                    # Map from case position to (token_name, start_index)
                    cases: dict[int, tuple[str, int]] = {}
                    default_idx: int | None = None
                    for idx, child in enumerate(children):
                        if child.kind == CursorKind.CASE_STMT:
                            # Extract token name from case label
                            case_children = list(child.get_children())
                            if case_children:
                                expr = case_children[0]
                                token_name = _extract_token_name(expr)
                                if token_name:
                                    cases[idx] = (token_name, idx)
                        elif child.kind == CursorKind.DEFAULT_STMT:
                            default_idx = idx

                    # For each case, find the first par_* call within the case body
                    for idx, (token_name, _start_idx) in cases.items():
                        case_node = children[idx]

                        # First, check if there's a par_* call directly in the case node
                        case_children = list(case_node.get_children())
                        found_par_call = False

                        # Skip the first child (case expression) and look at rest
                        for child_idx in range(1, len(case_children)):
                            stmt = case_children[child_idx]
                            # Walk the statement tree looking for par_* calls
                            for candidate in stmt.walk_preorder():
                                if candidate.kind == CursorKind.CALL_EXPR:
                                    callee = candidate.spelling
                                    if _is_parser_function(callee):
                                        rule_name = _function_to_rule_name(callee)
                                        yield token_name, rule_name
                                        found_par_call = True
                                        break
                            if found_par_call:
                                break

                        # If not found in case, search following siblings until next
                        if not found_par_call:
                            next_case_idx = None
                            for i in range(idx + 1, len(children)):
                                if children[i].kind in (
                                    CursorKind.CASE_STMT,
                                    CursorKind.DEFAULT_STMT,
                                ):
                                    next_case_idx = i
                                    break

                            search_end = (
                                next_case_idx if next_case_idx else len(children)
                            )
                            for search_idx in range(idx + 1, search_end):
                                node_to_search = children[search_idx]
                                # Walk the entire subtree looking for first par_* call
                                for candidate in node_to_search.walk_preorder():
                                    if candidate.kind == CursorKind.CALL_EXPR:
                                        callee = candidate.spelling
                                        if _is_parser_function(callee):
                                            rule_name = _function_to_rule_name(callee)
                                            yield token_name, rule_name
                                            found_par_call = True
                                            break
                                if found_par_call:
                                    break

                    # Handle default case if present
                    if default_idx is not None:
                        default_node = children[default_idx]
                        default_children = list(default_node.get_children())

                        # Search for par_* calls in default case body
                        for stmt in default_children:
                            # Walk the statement tree looking for par_* calls
                            for candidate in stmt.walk_preorder():
                                if candidate.kind == CursorKind.CALL_EXPR:
                                    callee = candidate.spelling
                                    if _is_parser_function(callee):
                                        rule_name = _function_to_rule_name(callee)
                                        # For default case, associate with special token
                                        # Indicates it's the fallback/catch-all rule
                                        yield '__default__', rule_name
                                        break


def _extract_tokens_from_conditionals(  # noqa: PLR0912
    cursor: Cursor, /
) -> Iterator[tuple[str, str | None]]:
    """
    Walk the AST and extract token matches from inline conditional statements.

    Phase 3.2.1: Extract token dispatch patterns from if/else blocks,
    complementing Phase 3.2's switch/case extraction.

    This extracts token patterns from:
    1. Direct equality checks: if (tok == SEPER)
    2. Negation checks: if (tok != WORD)
    3. Bitwise flag checks: if (tok & SOME_FLAG)
    4. Range checks: if (tok >= X && tok <= Y)
    5. Compound conditions: if (tok == SEPER || tok == PIPE)
    6. Ternary operators: condition ? consequence : alternative
    7. Macro-based checks: ISTOK(), ISUNSET(), etc.
    8. Logical compound: && and || operators

    Algorithm:
    1. Walks the function body for IF_STMT nodes
    2. Examines the condition expression for token comparisons
    3. Extracts token names from comparison operations
    4. For each condition with token matches, looks for parser function calls
       in the true/false branches
    5. Associates extracted tokens with handler parser functions

    Returns:
        Iterator of (token_name, handler_rule_name or None) tuples

    Example:
        if (tok == FOR) { par_for(...); } → yields (FOR, for)
        if (tok & SOME_FLAG) { par_foo(...); } → yields (SOME_FLAG, foo)
    """
    # Walk preorder to find IF_STMT nodes in function body
    for node in cursor.walk_preorder():
        if node.kind == CursorKind.IF_STMT:
            # Get the condition and then/else branches
            children = list(node.get_children())
            if len(children) < 2:
                continue

            condition = children[0]
            then_stmt = children[1]
            else_stmt = children[2] if len(children) > 2 else None

            # Extract tokens from the condition expression
            tokens_in_condition = _extract_tokens_from_expression(condition)

            # For each token found in condition, look for parser function calls
            # in the then/else branches
            for token_name in tokens_in_condition:
                # First try then branch
                then_rule = None
                for candidate in then_stmt.walk_preorder():
                    if candidate.kind == CursorKind.CALL_EXPR:
                        callee = candidate.spelling
                        if _is_parser_function(callee):
                            then_rule = _function_to_rule_name(callee)
                            break

                if then_rule:
                    yield token_name, then_rule

                # Also try else branch if present
                if else_stmt:
                    else_rule = None
                    for candidate in else_stmt.walk_preorder():
                        if candidate.kind == CursorKind.CALL_EXPR:
                            callee = candidate.spelling
                            if _is_parser_function(callee):
                                else_rule = _function_to_rule_name(callee)
                                break

                    if else_rule:
                        yield token_name, else_rule


def _extract_tokens_from_expression(expr: Cursor, /) -> set[str]:  # noqa: C901, PLR0912
    """
    Extract token names from a conditional expression.

    Phase 3.2.1 helper: Analyzes condition expressions to find token references.

    Handles:
    - Binary operators: ==, !=, &, |, >=, <=, >, <
    - Unary operators: !
    - Compound conditions: && and ||
    - Macro-like calls: ISTOK(TOKEN), ISUNSET(), etc.
    - Member access and dereference
    - Ternary conditional operators: ? :
    - Multi-part compound expressions

    Heuristics:
    - Token names are uppercase identifiers (A-Z with underscores)
    - Excludes single letters and generic names like 'TOK'
    - Context-aware: tokens near operators are more likely real tokens

    Returns:
        Set of token names (SCREAMING_SNAKE_CASE) found in the expression

    Example expressions:
        - tok == SEPER → {SEPER}
        - tok & IF_FLAGS → {IF_FLAGS}
        - ISTOK(WORD) → {WORD}
        - tok == FOO || tok == BAR → {FOO, BAR}
    """
    tokens: set[str] = set()
    ops = {'==', '!=', '&', '|', '&&', '||', '>=', '<=', '>', '<'}

    # Walk the expression AST looking for token references
    for node in expr.walk_preorder():
        # Direct token references in binary operations
        # Pattern: tok == SOME_TOKEN or SOME_TOKEN == tok
        if node.kind == CursorKind.BINARY_OPERATOR:
            node_tokens = list(node.get_tokens())
            # Look for operator symbols (==, !=, &, |, &&, ||)
            for i, tok in enumerate(node_tokens):
                if tok.spelling in ops:
                    # Adjacent tokens before/after operator may be variable/token
                    # Look for uppercase identifiers (token names)
                    if i > 0:
                        before = node_tokens[i - 1].spelling
                        if before.isupper() and before not in ('TOK',):
                            tokens.add(before)
                    if i < len(node_tokens) - 1:
                        after = node_tokens[i + 1].spelling
                        if after.isupper() and after not in ('TOK',):
                            tokens.add(after)

        # Function-like macro calls: ISTOK(TOKEN), etc.
        elif node.kind == CursorKind.CALL_EXPR:
            func_name = node.spelling
            # Macro patterns: ISTOK, ISUNSET, etc.
            if func_name.isupper() or func_name.startswith('IS'):
                # Extract arguments which may be tokens
                node_tokens = list(node.get_tokens())
                for tok in node_tokens:
                    if tok.spelling.isupper() and len(tok.spelling) > 2:
                        tokens.add(tok.spelling)

        # Ternary conditional operators: condition ? true_val : false_val
        elif node.kind == CursorKind.UNEXPOSED_EXPR:
            # Ternary operators sometimes appear as UNEXPOSED_EXPR
            node_tokens = list(node.get_tokens())
            for i, tok in enumerate(node_tokens):
                if tok.spelling == '?' and i > 0:
                    # Look at surrounding tokens
                    before = node_tokens[i - 1].spelling
                    if before.isupper():
                        tokens.add(before)

    # Additional pattern: direct token comparisons with members
    # Pattern: tok.type == SOME_TOKEN
    tok_list = list(expr.get_tokens())
    for i, tok in enumerate(tok_list):
        if tok.spelling.isupper() and len(tok.spelling) > 2:
            # Check context: if preceded by comparison operator or assignment
            if i > 0:
                prev = tok_list[i - 1].spelling
                if prev in ops:
                    tokens.add(tok.spelling)
            if i < len(tok_list) - 1:
                next_tok = tok_list[i + 1].spelling
                if next_tok in ops:
                    tokens.add(tok.spelling)

    return tokens


def _map_tokens_to_rules(
    parser: ZshParser, parser_functions: dict[str, _FunctionNode], /
) -> dict[str, list[str]]:
    """
    Extract token-to-rule mappings from both switch and inline conditional statements.

    Phase 3.2 implementation (full): Extracts token references from:
    1. Switch/case dispatcher statements (original implementation)
    2. Inline conditional statements (new in Phase 3.2.1)

    For each parser function, extracts token patterns and determines which token
    maps to which parser rule.

    This function:
    1. Scans for SWITCH_STMT nodes in all parser functions (Phase 3.2 original)
    2. Extracts case statements and their handler function calls
    3. Scans for IF_STMT nodes with token comparisons (Phase 3.2.1 new)
    4. Extracts conditional token matches and their handler calls
    5. Identifies which tokens map to which parser rules

    Returns: Dictionary mapping token names (SCREAMING_SNAKE_CASE) to lists of
    rule names (lower_snake_case) that handle them.
    """
    token_to_rules: dict[str, list[str]] = {}

    # Parse parse.c to access all functions
    tu = parser.parse('parse.c')
    if tu is None or tu.cursor is None:
        return token_to_rules

    # Find all functions in parse.c and extract their token mappings
    parser_func_names = set(parser_functions.keys())
    for cursor in _find_function_definitions(tu.cursor, parser_func_names):
        # Phase 3.2 (original): Extract case statements from switch dispatchers
        for token_name, rule_name in _extract_case_statements(cursor):
            if token_name not in token_to_rules:
                token_to_rules[token_name] = []
            if rule_name not in token_to_rules[token_name]:
                token_to_rules[token_name].append(rule_name)

        # Phase 3.2.1 (new): Extract token matches from inline conditionals
        for token_name, rule_name in _extract_tokens_from_conditionals(cursor):
            if rule_name is not None:  # Only add if we found a handler
                if token_name not in token_to_rules:
                    token_to_rules[token_name] = []
                if rule_name not in token_to_rules[token_name]:
                    token_to_rules[token_name].append(rule_name)

    return token_to_rules


def _validate_all_refs(  # noqa: C901, PLR0912
    grammar_symbols: dict[str, GrammarNode], /
) -> list[str]:
    """
    Validate that all $ref in grammar point to defined symbols.

    Phase 3.2 reference consistency validation (new):
    Ensures that:
    - All token references use SCREAMING_SNAKE_CASE
    - All rule references use lowercase
    - No missing or circular references
    - Proper naming convention consistency

    Args:
        grammar_symbols: Dictionary of all grammar symbols

    Returns:
        List of validation errors, empty if all valid
    """
    errors: list[str] = []

    def walk_node(node: GrammarNode, path: str = 'root') -> None:
        """Recursively walk grammar node and validate refs."""
        # Check if this is a $ref node (dict with $ref key)
        if not isinstance(node, dict):
            return

        if '$ref' in node:
            ref_name = cast('str', node['$ref'])
            if ref_name not in grammar_symbols:
                errors.append(
                    f'Missing symbol referenced: {ref_name} (at {path})'
                )
            # Validate naming convention
            elif ref_name.isupper():
                # Token reference - should be all uppercase
                if not ref_name.isupper():
                    errors.append(
                        f'Token reference not UPPERCASE: {ref_name} (at {path})'
                    )
            else:
                # Rule reference - should be lowercase
                if ref_name != ref_name.lower():
                    errors.append(
                        f'Rule reference not lowercase: {ref_name} (at {path})'
                    )

        # Recursively check nested structures
        for key, value in node.items():
            if key != '$ref':
                if isinstance(value, dict):
                    walk_node(
                        cast('GrammarNode', value), f'{path}.{key}'
                    )
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            walk_node(
                                cast('GrammarNode', item),
                                f'{path}.{key}[{i}]'
                            )

    # Walk all symbols
    for symbol_name, symbol_node in grammar_symbols.items():
        walk_node(symbol_node, f'symbols.{symbol_name}')

    return errors


def _validate_token_references(
    token_to_rules: dict[str, list[str]],
    core_symbols: dict[str, GrammarNode],
    /,
) -> list[str]:
    """
    Validate that all token references in token_to_rules exist in core_symbols.

    Phase 3.2 validation: Ensures that dispatcher rules reference valid tokens.

    Args:
        token_to_rules: Mapping of tokens to rules from switch statements
        core_symbols: Language symbols (tokens and rules) to validate against

    Returns:
        List of validation errors, or empty list if all tokens are valid
    """
    errors: list[str] = []
    explicit_tokens = {
        k: v for k, v in token_to_rules.items() if k != '__default__'
    }

    for token_name in explicit_tokens:
        if token_name not in core_symbols:
            errors.append(
                f'Token "{token_name}" referenced in case statements but not defined '
                f'in token mapping'
            )

    return errors


def _validate_completeness(  # noqa: C901, PLR0912
    token_to_rules: dict[str, list[str]],
    parser_functions: dict[str, _FunctionNode],
    call_graph: dict[str, _FunctionNode] | None = None,
    /,
) -> dict[str, list[str]]:
    """
    Validate that all expected parser rules are present in token mappings.

    Cross-references:
    1. All parser functions extracted from .syms should correspond to rules
    2. Rules should be referenced from at least one token case statement OR
       called from other parser functions
    3. Reports any rules that are unreferenced (orphaned)

    Returns: Completeness report with categorized unreferenced rules.
    """
    # Get all expected rule names (from parser functions)
    expected_rules: set[str] = set()
    for func_name in parser_functions:
        if func_name.startswith('par_'):
            rule_name = func_name[4:]  # Remove 'par_' prefix
            expected_rules.add(rule_name)
        elif func_name.startswith('parse_'):
            rule_name = func_name[6:]  # Remove 'parse_' prefix
            expected_rules.add(rule_name)

    # Get all referenced rules from token dispatch (case statements)
    dispatch_referenced: set[str] = set()
    for rules in token_to_rules.values():
        dispatch_referenced.update(rules)

    # Get all referenced rules from call graph (if available)
    call_graph_referenced: set[str] = set()
    if call_graph:
        # Build a map from function names to rule names
        func_to_rule: dict[str, str] = {}
        for func_name in parser_functions:
            if func_name.startswith('par_'):
                rule_name = func_name[4:]
            elif func_name.startswith('parse_'):
                rule_name = func_name[6:]
            else:
                continue
            func_to_rule[func_name] = rule_name

        # For each function call in the call graph, if it's a parser function,
        # mark its corresponding rule as referenced
        for func_node in call_graph.values():
            for called_func in func_node['calls']:
                if called_func in func_to_rule:
                    call_graph_referenced.add(func_to_rule[called_func])

    # Rules referenced through any mechanism (dispatch or call graph)
    all_referenced = dispatch_referenced | call_graph_referenced

    # Find orphaned rules (rules not referenced by any mechanism)
    orphaned_rules = expected_rules - all_referenced

    # Categorize orphaned rules
    # Top-level entry points that are typically not called from elsewhere
    entry_points = {'list', 'event', 'cond'}
    context_funcs = {'context_save', 'context_restore'}
    internal_funcs = {
        'list1',
        'sublist',
        'sublist2',
        'pline',
        'cond_1',
        'cond_2',
        'cond_double',
        'cond_triple',
        'cond_multi',
        'nl_wordlist',
    }

    report: dict[str, list[str]] = {}

    # Report dispatch-referenced rules for validation
    if dispatch_referenced:
        report['dispatch_referenced'] = sorted(dispatch_referenced)

    # Report orphaned rules, categorized
    if orphaned_rules:
        categorized: dict[str, list[str]] = {
            'entry_points': [],
            'context_functions': [],
            'internal_helpers': [],
            'other_orphaned': [],
        }

        for rule in sorted(orphaned_rules):
            if rule in entry_points:
                categorized['entry_points'].append(rule)
            elif rule in context_funcs:
                categorized['context_functions'].append(rule)
            elif rule in internal_funcs:
                categorized['internal_helpers'].append(rule)
            else:
                categorized['other_orphaned'].append(rule)

        for category, rules in categorized.items():
            if rules:
                report[category] = rules

    return report


def _build_token_mapping(parser: ZshParser, /) -> dict[str, _TokenDef]:
    """
    Build token mapping from enum definitions and text representations.

    Phase 1.4 enhanced: Extracts:
    1. Token enum values from zsh.h
    2. Hash table entries from hashtable.c (multi-value tokens like TYPESET)
    3. Token strings from lex.c (token display text)

    Returns: Dictionary mapping token names to _TokenDef with:
    - token: Token name
    - value: Numeric token ID
    - text: List of text representations (empty for semantic tokens)
    - file/line: Source location
    """
    result: dict[str, _TokenDef] = {}
    by_value: dict[int, _TokenDef] = {}
    tu = parser.parse('zsh.h')

    if (
        tu is not None
        and (
            lextok_cursor := _find_cursor(
                tu.cursor,
                lambda c: c.kind == CursorKind.ENUM_DECL and c.spelling == 'lextok',
            )
        )
        is not None
    ):
        for child in _find_child_cursors(
            lextok_cursor,
            lambda c: c.kind == CursorKind.ENUM_CONSTANT_DECL
            and c.enum_value is not None,
        ):
            value = cast('int', child.enum_value)
            result[child.spelling] = {
                'token': child.spelling,
                'value': value,
                'text': [],
                'file': 'zsh.h',
                'line': child.location.line,
            }
            by_value[value] = result[child.spelling]

    # Extract multi-value tokens from hash table
    # Phase 1.4: Handle tokens like TYPESET that map to multiple keywords
    for token_name, hash_key in _parse_hash_entries(parser):
        if token_name in result:
            # Prevent duplicates in text array
            if hash_key not in result[token_name]['text']:
                result[token_name]['text'].append(hash_key)

    # Extract token string representations
    for value, text in _parse_token_strings(parser):
        if value in by_value:
            # Prevent duplicates in text array
            if text not in by_value[value]['text']:
                by_value[value]['text'].append(text)

    return result


def _validate_schema(grammar: Grammar, schema_path: Path, /) -> list[str]:
    """
    Validate the grammar against the JSON schema.

    Returns a list of validation errors, or an empty list if valid.
    """
    if not schema_path.exists():
        return [f'Schema file not found: {schema_path}']

    try:
        schema = json.loads(schema_path.read_text())
    except json.JSONDecodeError as e:
        return [f'Failed to parse schema: {e}']

    errors: list[str] = []
    try:
        jsonschema.validate(instance=grammar, schema=schema)
    except jsonschema.ValidationError as e:
        errors.append(f'Schema validation error at {e.path}: {e.message}')
    except jsonschema.SchemaError as e:
        errors.append(f'Invalid schema: {e.message}')

    return errors


def _construct_grammar(  # noqa: C901, PLR0912, PLR0915
    zsh_path: Path, version: str, /
) -> Grammar:
    zsh_src = zsh_path / 'Src'
    parser = ZshParser(zsh_src)

    # Phase 1: Extract parser functions from .syms files
    parser_functions = _extract_parser_functions(zsh_src)

    # Phase 1.2: Map tokens to rules from switch/case statements
    token_to_rules = _map_tokens_to_rules(parser, parser_functions)

    # Phase 2: Build call graph for analyzing function composition
    call_graph = _build_call_graph(parser)

    # Merge call_graph into parser_functions to get actual C file locations
    # (call_graph has file/line from actual C files, parser_functions has metadata from .syms)
    parser_func_keys = set(parser_functions.keys())
    call_graph_keys = set(call_graph.keys())
    parser_parse_funcs = {k for k in parser_func_keys if _is_parser_function(k)}
    call_graph_parse_funcs = {k for k in call_graph_keys if _is_parser_function(k)}
    
    merge_count = 0
    for func_name in parser_parse_funcs:
        if func_name in call_graph:
            # Update with actual C file location while preserving .syms metadata
            parser_functions[func_name]['file'] = call_graph[func_name]['file']
            parser_functions[func_name]['line'] = call_graph[func_name]['line']
            merge_count += 1

    # Phase 1.2: Validate completeness of rule references
    completeness_report = _validate_completeness(
        token_to_rules, parser_functions, call_graph
    )

    token_mapping = _build_token_mapping(parser)

    core_symbols: Language = {}
    
    # Add tokens with text representations
    for token in token_mapping.values():
        if token['text']:
            core_symbols[token['token']] = create_token(
                token['token'],
                token['text'][0],
                source={'file': token['file'], 'line': token['line']},
            ) if len(token['text']) == 1 else create_token(
                token['token'],
                token['text'],
                source={'file': token['file'], 'line': token['line']},
            )
    
    # Add semantic tokens that don't have text representations
    # These are tokens that represent parsed content, not literal strings
    # They're created with placeholder patterns indicating their semantic type
    semantic_tokens: dict[str, str] = {
        'STRING': '<string>',         # Parsed string content
        'ENVSTRING': '<env_string>',  # Environment variable as string
        'ENVARRAY': '<env_array>',    # Environment variable as array
        'NULLTOK': '<null>',          # Null/empty token
        'LEXERR': '<lexer_error>',    # Lexer error token
    }
    for token_name, placeholder in semantic_tokens.items():
        if token_name in token_mapping and token_name not in core_symbols:
            token_def = token_mapping[token_name]
            # Create a semantic token with pattern indicating its semantic type
            # Note: These don't match concrete text, they represent token categories
            core_symbols[token_name] = create_token(
                token_name,
                placeholder,
                source={'file': token_def['file'], 'line': token_def['line']},
            )

    core_symbols['parameter'] = create_union(
        [
            create_ref('variable'),
            create_terminal('*'),
            create_terminal('@'),
            create_terminal('#'),
            create_terminal('?'),
            create_terminal('-'),
            create_terminal('$'),
            create_terminal('!'),
        ]
    )
    core_symbols['variable'] = create_terminal('[a-zA-Z0-9_]+')

    # Phase 3.2: Validate that all token references exist
    token_ref_errors = _validate_token_references(token_to_rules, core_symbols)
    
    # Phase 3.2 (new): Validate reference consistency across all symbols
    ref_validation_errors = _validate_all_refs(core_symbols)

    # Phase 2.3: Detect cycles in call graph
    func_to_cycles = _detect_cycles(call_graph)

    # Phase 3.3: Analyze control flow patterns for optional/repeat detection
    control_flows = _analyze_all_control_flows(parser, parser_functions)

    # Phase 4: Extract lexer state dependencies
    lexer_states = _extract_lexer_state_changes(parser, parser_functions)

    # Phase 3: Build grammar rules from call graph with control flow analysis
    # Phase 3.2: Integrate token dispatch into grammar rules
    grammar_rules = _build_grammar_rules(
        call_graph, parser_functions, control_flows, token_to_rules
    )

    # Phase 4.3: Embed lexer state conditions into grammar rules
    grammar_rules = _embed_lexer_state_conditions(
        grammar_rules, lexer_states, parser_functions
    )

    # Merge rules into core_symbols
    core_symbols.update(grammar_rules)

    # Log extracted parser functions for debugging
    if parser_functions:
        print(f'Extracted {len(parser_functions)} parser functions:')
        for name, node in sorted(parser_functions.items()):
            vis = node.get('visibility', 'unknown')
            sig = node.get('signature', '(...)')
            print(f'  {name:30} {vis:10} {sig}')

    # Log token-to-rule mappings and Phase 3.2 integration
    if token_to_rules:
        # Separate explicit tokens from default
        explicit_tokens = {
            k: v for k, v in token_to_rules.items() if k != '__default__'
        }
        default_rule = token_to_rules.get('__default__')

        print('\nPhase 3.2: Token dispatch integration')
        print(f'Phase 3.2.1 (inline conditionals): Extracted from if/else blocks')
        print(f'Total token-to-rule mappings found: {len(explicit_tokens)} explicit tokens')
        for token, rules in sorted(explicit_tokens.items()):
            print(f'  {token:30} → {", ".join(rules)}')

        if default_rule:
            print(f'  Default (catch-all) handler: {", ".join(default_rule)}')

        # Show which dispatcher rules have embedded token references
        rule_to_tokens: dict[str, list[str]] = {}
        for token_name, rule_names in explicit_tokens.items():
            for rule_name in rule_names:
                if rule_name not in rule_to_tokens:
                    rule_to_tokens[rule_name] = []
                rule_to_tokens[rule_name].append(token_name)

        if rule_to_tokens:
            print('\nDispatcher rules with embedded token references:')
            for rule_name in sorted(rule_to_tokens.keys()):
                tokens = sorted(rule_to_tokens[rule_name])
                print(f'  {rule_name:20} dispatches: {", ".join(tokens)}')

        # Log validation errors for token references
        if token_ref_errors:
            print('\nToken reference validation errors:')
            for error in token_ref_errors:
                print(f'  ERROR: {error}')
        else:
            print('Token reference validation: PASSED')
        
        # Log reference consistency validation (Phase 3.2 new)
        if ref_validation_errors:
            print('\nReference consistency validation errors:')
            for error in ref_validation_errors:
                print(f'  ERROR: {error}')
        else:
            print('Reference consistency validation: PASSED')

    # Log completeness report
    print('\nCompleteness validation report:')
    if completeness_report:
        for issue_type, items in sorted(completeness_report.items()):
            print(f'  {issue_type}:')
            for item in items:
                print(f'    - {item}')
    else:
        print('  (No issues found - all rules are referenced)')

    # Log control flow analysis (Phase 3.3)
    if control_flows:
        optional_count = sum(
            1 for cf in control_flows.values() if cf['pattern_type'] == 'optional'
        )
        repeat_count = sum(
            1 for cf in control_flows.values() if cf['pattern_type'] == 'repeat'
        )
        total = len(control_flows)
        print(f'\nControl flow analysis (Phase 3.3): {total} patterns detected')
        if optional_count:
            print(f'  Optional patterns (if without else): {optional_count}')
            for func, pattern in sorted(control_flows.items()):
                if pattern['pattern_type'] == 'optional':
                    rule_name = _function_to_rule_name(func)
                    reason = pattern['reason']
                    print(f'    - {func:30} → {rule_name:20} ({reason})')
        if repeat_count:
            print(f'  Repeat patterns (while/for loops): {repeat_count}')
            for func, pattern in sorted(control_flows.items()):
                if pattern['pattern_type'] == 'repeat':
                    rule_name = _function_to_rule_name(func)
                    loop_type = pattern.get('loop_type', 'unknown')
                    print(f'    - {func:30} → {rule_name:20} ({loop_type} loop)')
    else:
        print('\nControl flow analysis (Phase 3.3): No patterns detected')

    # Log call graph analysis
    if call_graph:
        print('\nCall graph analysis:')
        print(f'  Total functions in call graph: {len(call_graph)}')
        # Show which parser functions are called from other parser functions
        parser_func_names: set[str] = set(parser_functions.keys())
        called_parser_funcs: set[str] = set()
        for func_node in call_graph.values():
            for called_func in func_node['calls']:
                if called_func in parser_func_names:
                    called_parser_funcs.add(called_func)
        if called_parser_funcs:
            num_called = len(called_parser_funcs)
            print(f'  Parser functions called by others: {num_called}')
            for func in sorted(called_parser_funcs):
                rule_name = func[4:] if func.startswith('par_') else func[6:]
                print(f'    - {func:30} → {rule_name}')

    # Log lexer state dependencies
    if lexer_states:
        num_funcs = len(lexer_states)
        print(
            f'\nLexer state management (Phase 4): '
            f'{num_funcs} parser functions modify state'
        )
        state_case_map: dict[str, str] = {
            'incmdpos': 'INCMDPOS',
            'incond': 'INCOND',
            'inredir': 'INREDIR',
            'incasepat': 'INCASEPAT',
            'infor': 'INFOR',
            'inrepeat': 'INREPEAT',
            'intypeset': 'INTYPESET',
            'isnewlin': 'ISNEWLIN',
            'in_math': 'IN_MATH',
            'aliasspaceflag': 'ALIASSPACEFLAG',
            'incomparison': 'INCOMPARISON',
            'in_array': 'IN_ARRAY',
            'in_substitution': 'IN_SUBSTITUTION',
            'in_braceexp': 'IN_BRACEEXP',
            'in_globpat': 'IN_GLOBPAT',
        }
        for func, states in sorted(lexer_states.items()):
            uppercase_states: list[str] = []
            for state_name in states:
                if state_name in state_case_map:
                    uppercase_states.append(state_case_map[state_name])
            state_str = ', '.join(sorted(uppercase_states))
            rule_name = func[4:] if func.startswith('par_') else func[6:]
            print(f'  {rule_name:20} → {state_str}')
        print(
            f'\nPhase 4.3: Embedded lexer state variants in {num_funcs} grammar rules'
        )
    else:
        print('\nNo lexer state changes detected (may require full preprocessing)')

    # Log cycle detection results
    if func_to_cycles:
        print(f'\nCycle detection found {len(func_to_cycles)} functions in cycles:')
        # Show unique cycles (avoid duplicates)
        seen_cycles: set[tuple[str, ...]] = set()
        for _func, cycles in sorted(func_to_cycles.items()):
            for cycle in cycles:
                # Normalize cycle for display
                min_node = min(cycle)
                min_idx = cycle.index(min_node)
                normalized = tuple(cycle[min_idx:] + cycle[:min_idx])
                if normalized not in seen_cycles:
                    seen_cycles.add(normalized)

        for cycle in sorted(seen_cycles):
            print(f'  Cycle: {" → ".join(cycle)} → {cycle[0]}')

        # Explain how cycles are handled
        print('\n  Cycles are broken by using $ref instead of inlining definitions.')
        print('  This keeps the grammar acyclic while representing recursive patterns.')

    grammar: Grammar = {
        '$schema': './canonical-grammar.schema.json',
        'languages': {'core': core_symbols},
        'zsh_version': version,
    }

    # Phase 5.2: Validate grammar against schema
    schema_path = PROJECT_ROOT / 'zsh-grammar' / 'canonical-grammar.schema.json'
    validation_errors = _validate_schema(grammar, schema_path)

    if validation_errors:
        print('\nSchema validation errors:')
        for error in validation_errors:
            print(f'  ERROR: {error}')
    else:
        print('\nSchema validation: PASSED')

    return grammar


def main() -> None:
    args_parser = ArgumentParser(description='Construct the canonical grammar for Zsh')
    args_parser.add_argument(
        '--src',
        '-s',
        type=Path,
        default=PROJECT_ROOT / 'vendor' / 'zsh',
        help='Path to Zsh source',
    )
    args_parser.add_argument(
        '--output',
        '-o',
        type=Path,
        default=PROJECT_ROOT / 'zsh-grammar' / 'canonical-grammar.json',
        help='Directory to write grammar to',
    )

    args_parser.add_argument(
        '--clang-prefix',
        dest='clang_prefix',
        type=Path,
        default=os.environ.get('LIBCLANG_PREFIX'),
        help='Prefix for libclang',
    )

    args = args_parser.parse_args()

    if args.clang_prefix:
        ZshParser.set_clang_prefix(cast('Path', args.clang_prefix).absolute())

    src = cast('Path', args.src).absolute()
    output = cast('Path', args.output).absolute()

    version_mk = (src / 'Config' / 'version.mk').read_text()
    if (match := re.search(r'^VERSION=(.*)$', version_mk, re.M)) is not None:
        version = cast('str', match[1])
    else:
        raise ValueError('No VERSION found')

    grammar = _construct_grammar(src, version)

    if (src / '.git').exists():
        result = subprocess.run(  # noqa: S603
            ['git', '-C', src, 'rev-parse', 'HEAD'],  # noqa: S607
            check=True,
            capture_output=True,
            text=True,
        )

        if not result.returncode:
            grammar['zsh_revision'] = result.stdout.strip()

    output.write_text(json.dumps(grammar, indent=2))
