"""Enhanced call graph construction for Phase 2.4.1 Stage 3.

Builds an enhanced call graph that includes token sequences and branch
information for each parser function. Provides:
- build_call_graph_enhanced(): Main entry point, replaces build_call_graph()
- validate_enhanced_call_graph(): Comprehensive validation suite
- compare_call_graphs(): Comparison between old and enhanced graphs
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from clang.cindex import CursorKind

from zsh_grammar.ast_utilities import find_function_definitions, walk_and_filter
from zsh_grammar.branch_extractor import extract_control_flow_branches
from zsh_grammar.function_discovery import _is_parser_function
from zsh_grammar.token_extractors import (
    extract_synthetic_tokens_for_branch,
    extract_tokens_and_calls_for_branch,
    merge_branch_items,
)

if TYPE_CHECKING:
    from clang.cindex import Cursor

    from zsh_grammar._types import (
        ControlFlowBranch,
        FunctionNode,
        FunctionNodeEnhanced,
        TokenOrCallEnhanced,
    )
    from zsh_grammar.source_parser import ZshParser


def build_call_graph_enhanced(parser: ZshParser, /) -> dict[str, FunctionNodeEnhanced]:
    """
    Build enhanced call graph with token sequences.

    Primary replacement for build_call_graph() in control_flow.py.
    Populates token_sequences field for each parser function.

    Args:
        parser: ZshParser instance for file parsing

    Returns:
        Dict mapping function names to FunctionNodeEnhanced with complete
        token_sequences and control flow patterns
    """
    call_graph: dict[str, FunctionNodeEnhanced] = {}

    for file, tu in parser.parse_files('*.c'):
        if tu.cursor is None:
            continue

        for cursor in find_function_definitions(tu.cursor):
            function_name = cursor.spelling

            # Skip non-parser functions
            if not _is_parser_function(function_name):
                continue

            # Existing fields (backward compatible)
            calls: list[str] = []
            for child in walk_and_filter(cursor, CursorKind.CALL_EXPR):
                callee_name = child.spelling
                if callee_name != function_name:
                    calls.append(callee_name)

            # NEW: Extract branches and populate token sequences
            branches = extract_control_flow_branches(cursor, function_name)
            token_sequences: list[ControlFlowBranch] = []

            for branch in branches:
                # Stage 2.1: Extract tokens and calls for this branch
                tokens = extract_tokens_and_calls_for_branch(
                    cursor, branch, function_name
                )
                # Stage 2.2: Extract synthetic tokens
                synthetics = extract_synthetic_tokens_for_branch(cursor, branch)
                # Stage 2.3: Merge and reindex
                merged = merge_branch_items(tokens, synthetics)

                # Update branch with extracted items
                branch['items'] = merged  # type: ignore[typeddict-unknown-key]
                token_sequences.append(branch)

            # Detect control flow patterns
            has_loops = any(b['branch_type'] == 'loop' for b in token_sequences)
            loop_type: str | None = None
            if has_loops:
                for b in token_sequences:
                    if b['branch_type'] == 'loop':
                        loop_type = _get_loop_type(cursor, b['start_line'])
                        break

            is_optional = _detect_optional_pattern(token_sequences)

            # Build enhanced node
            node: FunctionNodeEnhanced = {
                'name': function_name,
                'file': str(file.relative_to(parser.zsh_src)),
                'line': cursor.location.line,
                'calls': calls,
                'token_sequences': token_sequences,
                'has_loops': has_loops,
                'is_optional': is_optional,
            }

            if loop_type:
                node['loop_type'] = loop_type

            call_graph[function_name] = node

    return call_graph


def _get_loop_type(cursor: Cursor, start_line: int) -> str:
    """
    Detect loop type (while or for) from AST.

    Args:
        cursor: Function definition cursor
        start_line: Line number where loop starts

    Returns:
        'while' or 'for'
    """
    for node in cursor.walk_preorder():
        if node.location.line == start_line:
            if node.kind == CursorKind.WHILE_STMT:
                return 'while'
            if node.kind == CursorKind.FOR_STMT:
                return 'for'

    return 'while'  # Default to while if detection fails


def _detect_optional_pattern(token_sequences: list[ControlFlowBranch]) -> bool:
    """
    Detect if function has optional if-without-else pattern.

    Args:
        token_sequences: List of branches from function

    Returns:
        True if function has if statement without else
    """
    # Look for if branches without corresponding else
    has_if = any(b['branch_type'] == 'if' for b in token_sequences)
    has_else = any(b['branch_type'] == 'else' for b in token_sequences)

    # Optional if we have if but no else
    return has_if and not has_else


def validate_enhanced_call_graph(
    call_graph: dict[str, FunctionNodeEnhanced],
    /,
) -> dict[str, list[str]]:
    """
    Comprehensive validation of enhanced call graph.

    Validates:
    - Branch structure (branch_id, branch_type, line ranges)
    - Item structure (kind, line, branch_id, sequence_index)
    - Contiguity of sequence indices
    - Monotonicity of line numbers
    - Consistency between calls and token_sequences

    Args:
        call_graph: Enhanced call graph to validate

    Returns:
        Dict mapping function names to error messages
        (empty if validation passes)
    """
    errors_by_func: dict[str, list[str]] = {}

    for func_name, node in call_graph.items():
        func_errors: list[str] = []

        # Validate token_sequences exists
        if 'token_sequences' not in node:
            func_errors.append('Missing token_sequences field')
            errors_by_func[func_name] = func_errors
            continue

        # Validate each branch
        for i, branch in enumerate(node['token_sequences']):
            branch_errors = _validate_branch(func_name, i, branch)
            func_errors.extend(branch_errors)

        # Validate call consistency
        calls_in_sequences: set[str] = set()
        for branch in node['token_sequences']:
            for item in branch['items']:
                if item['kind'] == 'call':
                    func_name_from_item = item.get('func_name', '')
                    calls_in_sequences.add(func_name_from_item)

        extra_calls: set[str] = calls_in_sequences - set(node['calls'])
        missing_calls: set[str] = set(node['calls']) - calls_in_sequences

        if extra_calls:
            func_errors.append(
                f'Calls in sequences not in node.calls: {sorted(extra_calls)}'
            )
        if missing_calls:
            func_errors.append(
                f'Calls in node.calls not in sequences: {sorted(missing_calls)}'
            )

        # Validate loop markers
        has_loops = any(b['branch_type'] == 'loop' for b in node['token_sequences'])
        if has_loops != node.get('has_loops', False):
            func_errors.append(
                f'has_loops mismatch: {has_loops} vs {node.get("has_loops")}'
            )

        if func_errors:
            errors_by_func[func_name] = func_errors

    return errors_by_func


def _validate_branch(
    func_name: str, branch_idx: int, branch: ControlFlowBranch
) -> list[str]:
    """
    Validate a single branch.

    Args:
        func_name: Parent function name (for error messages)
        branch_idx: Branch index within function
        branch: Branch to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []
    branch_id = branch['branch_id']

    # Check required fields
    required_fields = ['branch_id', 'branch_type', 'start_line', 'end_line', 'items']
    for field in required_fields:
        if field not in branch:
            errors.append(f'{func_name}[{branch_idx}]: Missing {field}')

    if not branch.get('items'):
        return errors

    errors.extend(_validate_branch_items(func_name, branch_id, branch['items']))
    return errors


def _validate_branch_items(
    func_name: str, branch_id: str, items: list[TokenOrCallEnhanced]
) -> list[str]:
    """
    Validate items within a branch.

    Args:
        func_name: Parent function name (for error messages)
        branch_id: Branch identifier
        items: Items to validate

    Returns:
        List of error messages
    """
    errors: list[str] = []

    # Check sequence_index contiguity
    indices = sorted([item['sequence_index'] for item in items])
    expected = list(range(len(items)))
    if indices != expected:
        errors.append(
            f'{func_name}[{branch_id}]: Non-contiguous indices {indices}, '
            f'expected {expected}'
        )

    # Check line monotonicity
    lines = [item['line'] for item in items]
    if lines != sorted(lines):
        errors.append(f'{func_name}[{branch_id}]: Non-monotonic lines {lines}')

    # Check branch_id consistency and item structure
    for item in items:
        if item.get('branch_id') != branch_id:
            errors.append(
                f'{func_name}[{branch_id}]: Item has mismatched branch_id '
                f'{item.get("branch_id")}'
            )

        kind = item.get('kind')
        if kind is None:  # pyright: ignore[reportUnnecessaryComparison]
            errors.append(f'{func_name}[{branch_id}]: Item missing kind field')
        elif kind == 'token':
            if 'token_name' not in item or 'is_negated' not in item:
                errors.append(
                    f'{func_name}[{branch_id}]: Token item missing required fields'
                )
        elif kind == 'call':
            if 'func_name' not in item:
                errors.append(f'{func_name}[{branch_id}]: Call item missing func_name')
        elif kind == 'synthetic_token':  # noqa: SIM102
            if 'token_name' not in item or 'condition' not in item:
                errors.append(
                    f'{func_name}[{branch_id}]: Synthetic item missing required fields'
                )

    return errors


def compare_call_graphs(
    old_graph: dict[str, FunctionNode],
    enhanced_graph: dict[str, FunctionNodeEnhanced],
    /,
) -> dict[str, dict[str, object]]:
    """
    Compare old call graph with enhanced call graph.

    Analyzes differences:
    - Functions added/removed
    - Call list changes
    - New token_sequences field
    - Backward compatibility

    Args:
        old_graph: Original call graph
        enhanced_graph: Enhanced call graph

    Returns:
        Dict with comparison results and analysis
    """
    results: dict[str, dict[str, object]] = {
        'summary': {},
        'detailed': {},
    }

    old_names = set(old_graph.keys())
    enhanced_names = set(enhanced_graph.keys())

    # Check function coverage
    added = enhanced_names - old_names
    removed = old_names - enhanced_names
    common = old_names & enhanced_names

    results['summary'] = {
        'total_old': len(old_names),
        'total_enhanced': len(enhanced_names),
        'added_count': len(added),
        'removed_count': len(removed),
        'common_count': len(common),
    }

    if added:
        results['summary']['added_functions'] = sorted(added)
    if removed:
        results['summary']['removed_functions'] = sorted(removed)

    # Detailed comparison for common functions
    for func_name in sorted(common):
        old_node = old_graph[func_name]
        enhanced_node = enhanced_graph[func_name]

        comparison: dict[str, object] = {
            'name': func_name,
            'basic_fields_match': True,
            'calls_match': False,
            'has_token_sequences': False,
        }

        # Check basic fields
        if old_node['name'] != enhanced_node['name']:
            comparison['basic_fields_match'] = False
        if old_node['file'] != enhanced_node['file']:
            comparison['basic_fields_match'] = False
        if old_node['line'] != enhanced_node['line']:
            comparison['basic_fields_match'] = False

        # Check calls
        old_calls = set(old_node.get('calls', []))
        enhanced_calls = set(enhanced_node.get('calls', []))
        comparison['calls_match'] = old_calls == enhanced_calls
        if not comparison['calls_match']:
            comparison['added_calls'] = sorted(enhanced_calls - old_calls)
            comparison['removed_calls'] = sorted(old_calls - enhanced_calls)

        # Check token_sequences
        if 'token_sequences' in enhanced_node:
            comparison['has_token_sequences'] = True
            comparison['num_branches'] = len(enhanced_node['token_sequences'])
            comparison['has_loops'] = enhanced_node.get('has_loops', False)
            comparison['is_optional'] = enhanced_node.get('is_optional', False)

        results['detailed'][func_name] = comparison

    return results


def extract_call_graph_stats(
    call_graph: dict[str, FunctionNodeEnhanced], /
) -> dict[str, object]:
    """
    Extract statistics from enhanced call graph.

    Args:
        call_graph: Enhanced call graph

    Returns:
        Dict with various statistics
    """
    total_functions = len(call_graph)
    total_branches = 0
    total_items = 0
    functions_with_loops = 0
    functions_optional = 0
    branch_type_dist: dict[str, int] = {}
    item_kind_dist: dict[str, int] = {}

    for node in call_graph.values():
        if node.get('has_loops', False):
            functions_with_loops += 1
        if node.get('is_optional', False):
            functions_optional += 1

        for branch in node.get('token_sequences', []):
            total_branches += 1
            branch_type = branch['branch_type']
            branch_type_dist[branch_type] = branch_type_dist.get(branch_type, 0) + 1

            for item in branch.get('items', []):
                total_items += 1
                item_kind = item['kind']
                item_kind_dist[item_kind] = item_kind_dist.get(item_kind, 0) + 1

    return {
        'total_functions': total_functions,
        'total_branches': total_branches,
        'total_items': total_items,
        'functions_with_loops': functions_with_loops,
        'functions_optional': functions_optional,
        'branch_type_distribution': branch_type_dist,
        'item_kind_distribution': item_kind_dist,
    }
