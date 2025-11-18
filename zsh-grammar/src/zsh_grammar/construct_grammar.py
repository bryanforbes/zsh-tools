from __future__ import annotations

import json
import os
import re
import subprocess
from argparse import ArgumentParser
from collections.abc import Callable, Iterator  # noqa: TC003
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict, cast

import jsonschema
from clang.cindex import Cursor, CursorKind, StorageClass

from zsh_grammar.ast_utilities import (
    extract_token_name,
    find_function_definitions,
    walk_and_filter,
)
from zsh_grammar.control_flow import (
    analyze_all_control_flows,
    build_call_graph,
    detect_cycles,
    extract_lexer_state_changes,
)
from zsh_grammar.function_discovery import extract_parser_functions
from zsh_grammar.grammar_rules import build_grammar_rules, embed_lexer_state_conditions
from zsh_grammar.grammar_utils import (
    create_ref,
    create_terminal,
    create_token,
    create_union,
)
from zsh_grammar.source_parser import ZshParser
from zsh_grammar.validation import validate_semantic_grammar

if TYPE_CHECKING:
    from zsh_grammar._types import (
        FunctionNode,
        Grammar,
        GrammarNode,
        Language,
        Source,
        TokenOrCall,
    )

PROJECT_ROOT: Final = Path(__file__).resolve().parents[3]


# Import helper for internal use
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


# ============================================================================
# Helper Functions
# ============================================================================


class _TokenDef(TypedDict):
    token: str
    value: int
    text: list[str]
    file: str
    line: int


def _find_cursor(
    cursor: Cursor | None, predicate: Callable[[Cursor], bool], /
) -> Cursor | None:
    """Find a cursor matching predicate in direct children."""
    if cursor is None:
        return None

    for child in cursor.get_children():
        if predicate(child):
            return child
    return None


def _find_child_cursors(
    cursor: Cursor | None, predicate: Callable[[Cursor], bool], /
) -> Iterator[Cursor]:
    """Find all direct child cursors matching predicate."""
    if cursor is not None:
        for child in cursor.get_children():
            if predicate(child):
                yield child


def _find_function_definitions(cursor: Cursor, names: set[str], /) -> Iterator[Cursor]:
    """Find function definitions by name set."""
    return find_function_definitions(cursor, names)


def _function_to_rule_name(func_name: str, /) -> str:
    """Convert function name to rule name."""
    if func_name.startswith('par_'):
        return func_name[4:]
    if func_name.startswith('parse_'):
        return func_name[6:]
    return func_name


def _parse_hash_entries(parser: ZshParser, /) -> Iterator[tuple[str, str]]:
    """Parse hash table entries from hashtable.c."""
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
    """Parse token string definitions from lex.c."""
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
                    if text.startswith('"') and text.endswith('"'):
                        text = text[1:-1]

                    if text != '((void*)0)':
                        yield index, text


def _extract_case_statements(cursor: Cursor, /) -> Iterator[tuple[str, str]]:
    """Extract case statements from switch dispatchers."""
    for switch_stmt in walk_and_filter(cursor, CursorKind.SWITCH_STMT):
        for case_stmt in walk_and_filter(switch_stmt, CursorKind.CASE_STMT):
            case_expr = None
            for child in case_stmt.get_children():
                if child.kind != CursorKind.CASE_STMT:
                    case_expr = child
                    break

            if case_expr is None:
                continue

            token_name = extract_token_name(case_expr)
            if token_name is None or not token_name.isupper():
                continue

            for call_node in walk_and_filter(case_stmt, CursorKind.CALL_EXPR):
                func_name = call_node.spelling
                if _is_parser_function(func_name):
                    rule_name = _function_to_rule_name(func_name)
                    yield token_name, rule_name
                    break


def _extract_tokens_from_conditionals(cursor: Cursor, /) -> Iterator[tuple[str, str]]:
    """Extract tokens from conditional expressions."""
    for if_stmt in walk_and_filter(cursor, CursorKind.IF_STMT):
        if_children = list(if_stmt.get_children())
        if len(if_children) < 2:
            continue

        condition = if_children[0]
        then_stmt = if_children[1]
        else_stmt = if_children[2] if len(if_children) > 2 else None

        tokens_in_condition = _extract_tokens_from_expression(condition)

        for token_name in tokens_in_condition:
            then_rule = None
            for candidate in then_stmt.walk_preorder():
                if candidate.kind == CursorKind.CALL_EXPR:
                    callee = candidate.spelling
                    if _is_parser_function(callee):
                        then_rule = _function_to_rule_name(callee)
                        break

            if then_rule:
                yield token_name, then_rule

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


def _extract_tokens_from_expression(expr: Cursor, /) -> set[str]:
    """Extract token names from conditional expression."""
    tokens: set[str] = set()

    for node in expr.walk_preorder():
        if node.kind == CursorKind.DECL_REF_EXPR:
            name = node.spelling
            if name.isupper() and len(name) > 2 and '_' not in name[:2]:
                tokens.add(name)

    return tokens


def _map_tokens_to_rules(
    parser: ZshParser, parser_functions: dict[str, FunctionNode], /
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
            if token_name not in token_to_rules:
                token_to_rules[token_name] = []
            if rule_name not in token_to_rules[token_name]:
                token_to_rules[token_name].append(rule_name)

    return token_to_rules


def _validate_all_refs(grammar_symbols: dict[str, GrammarNode], /) -> list[str]:
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
        # Check if this is a $ref node
        if '$ref' in node:
            ref_name = node.get('$ref', '')
            if ref_name not in grammar_symbols:
                errors.append(f'Missing symbol referenced: {ref_name} (at {path})')
            # Validate naming convention
            elif ref_name.isupper():
                # Token reference - should be all uppercase
                if not ref_name.isupper():
                    errors.append(
                        f'Token reference not UPPERCASE: {ref_name} (at {path})'
                    )
            elif ref_name != ref_name.lower():
                # Rule reference - should be lowercase
                errors.append(f'Rule reference not lowercase: {ref_name} (at {path})')

        # Recursively check nested structures
        for key, value in node.items():
            if key != '$ref':
                if isinstance(value, dict):
                    walk_node(cast('GrammarNode', value), f'{path}.{key}')
                elif isinstance(value, list):
                    for i, item in enumerate(value):  # pyright: ignore[reportUnknownVariableType,reportUnknownArgumentType]
                        if isinstance(item, dict):
                            walk_node(cast('GrammarNode', item), f'{path}.{key}[{i}]')

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
    explicit_tokens = {k: v for k, v in token_to_rules.items() if k != '__default__'}

    for token_name in explicit_tokens:
        if token_name not in core_symbols:
            errors.append(
                f'Token "{token_name}" referenced in case statements but not defined '
                f'in token mapping'
            )

    return errors


def _validate_completeness(  # noqa: C901, PLR0912
    token_to_rules: dict[str, list[str]],
    parser_functions: dict[str, FunctionNode],
    call_graph: dict[str, FunctionNode] | None = None,
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
        if token_name in result and hash_key not in result[token_name]['text']:
            # Prevent duplicates in text array
            result[token_name]['text'].append(hash_key)

    # Extract token string representations
    for value, text in _parse_token_strings(parser):
        if value in by_value and text not in by_value[value]['text']:
            # Prevent duplicates in text array
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
    parser_functions = extract_parser_functions(zsh_src)

    # Phase 1.2: Map tokens to rules from switch/case statements
    token_to_rules = _map_tokens_to_rules(parser, parser_functions)

    # Phase 2: Build call graph for analyzing function composition
    call_graph = build_call_graph(parser)

    # Merge call_graph into parser_functions to get actual C file locations
    # (call_graph has file/line from actual C files, parser_functions has .syms
    # metadata)
    parser_func_keys = set(parser_functions.keys())
    parser_parse_funcs = {k for k in parser_func_keys if _is_parser_function(k)}

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

    # Add all tokens from token_mapping
    # Phase 1.4: Process all tokens, whether they have text representations or not
    for token in token_mapping.values():
        token_name = token['token']
        source: Source = {'file': token['file'], 'line': token['line']}

        # Use text representations if available, otherwise create semantic token
        if token['text']:
            # Token has explicit text representations (e.g., ";" for SEPER)
            core_symbols[token_name] = (
                create_token(
                    token_name,
                    token['text'][0],
                    source=source,
                )
                if len(token['text']) == 1
                else create_token(
                    token_name,
                    token['text'],
                    source=source,
                )
            )

    # Add semantic tokens that don't have text representations
    # These are tokens that represent parsed content, not literal strings
    # They're created with placeholder patterns indicating their semantic type
    semantic_tokens: dict[str, str] = {
        'STRING': '<string>',  # Parsed string content
        'ENVSTRING': '<env_string>',  # Environment variable as string
        'ENVARRAY': '<env_array>',  # Environment variable as array
        'NULLTOK': '<null>',  # Null/empty token
        'LEXERR': '<lexer_error>',  # Lexer error token
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
    func_to_cycles = detect_cycles(call_graph)

    # Phase 3.3: Analyze control flow patterns for optional/repeat detection
    # Note: analyze_all_control_flows takes extracted_tokens as
    # dict[str, list[TokenOrCall]]. We construct this from call_graph
    # token_sequences
    extracted_tokens_dict: dict[str, list[TokenOrCall]] = {}
    for func_name, node in call_graph.items():
        if 'token_sequences' in node:
            # token_sequences is list[list[TokenOrCall]], use first sequence
            seqs = node['token_sequences']
            if seqs:
                extracted_tokens_dict[func_name] = seqs[0]
    control_flows = analyze_all_control_flows(parser, extracted_tokens_dict)

    # Phase 4: Extract lexer state dependencies
    lexer_states = extract_lexer_state_changes(parser, parser_functions)

    # Phase 3: Build grammar rules from call graph with control flow analysis
    # Phase 3.2: Integrate token dispatch into grammar rules
    grammar_rules = build_grammar_rules(
        parser_functions, call_graph, extracted_tokens_dict
    )

    # Phase 4.3: Embed lexer state conditions into grammar rules
    grammar_rules = embed_lexer_state_conditions(grammar_rules, lexer_states)

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
        print('Phase 3.2.1 (inline conditionals): Extracted from if/else blocks')
        print(
            f'Total token-to-rule mappings found: {len(explicit_tokens)} '
            'explicit tokens'
        )
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
            1
            for cf in control_flows.values()
            if cf is not None and cf['pattern_type'] == 'optional'
        )
        repeat_count = sum(
            1
            for cf in control_flows.values()
            if cf is not None and cf['pattern_type'] == 'repeat'
        )
        total = len(control_flows)
        print(f'\nControl flow analysis (Phase 3.3): {total} patterns detected')
        if optional_count:
            print(f'  Optional patterns (if without else): {optional_count}')
            for func, pattern in sorted(control_flows.items()):
                if pattern is not None and pattern['pattern_type'] == 'optional':
                    rule_name = _function_to_rule_name(func)
                    reason = pattern['reason']
                    print(f'    - {func:30} → {rule_name:20} ({reason})')
        if repeat_count:
            print(f'  Repeat patterns (while/for loops): {repeat_count}')
            for func, pattern in sorted(control_flows.items()):
                if pattern is not None and pattern['pattern_type'] == 'repeat':
                    rule_name = _function_to_rule_name(func)
                    loop_type = pattern.get('loop_type', 'unknown')
                    print(f'    - {func:30} → {rule_name:20} ({loop_type} loop)')
    else:
        print('\nControl flow analysis (Phase 3.3): No patterns detected')

    # Log Phase 2.4.1 token sequences
    print('\nToken sequences (Phase 2.4.1):')
    funcs_with_sequences = 0
    total_items = 0
    sequences_by_func: dict[str, int] = {}

    for func_name, func_node in call_graph.items():
        if _is_parser_function(func_name):
            token_sequences = func_node.get('token_sequences')
            if token_sequences:
                funcs_with_sequences += 1
                # Count total items across all sequences
                total_sequence_items = sum(len(seq) for seq in token_sequences)
                total_items += total_sequence_items
                sequences_by_func[func_name] = len(token_sequences)

    if sequences_by_func:
        # Count total sequences across all functions
        total_sequences = sum(
            len(call_graph[f].get('token_sequences', [])) for f in sequences_by_func
        )
        print(
            f'  {funcs_with_sequences} parser functions extracted with '
            f'{total_sequences} sequences'
        )
        for func_name in sorted(sequences_by_func.keys()):
            num_sequences = sequences_by_func[func_name]
            sequences = call_graph[func_name].get('token_sequences', [])
            total_seq_items = sum(len(seq) for seq in sequences)
            rule_name = _function_to_rule_name(func_name)
            seq_plural = 'sequence' if num_sequences == 1 else 'sequences'
            print(
                f'    {func_name:30} → {rule_name:20} '
                f'{num_sequences} {seq_plural} ({total_seq_items} items)'
            )
        print(
            '\n  Phase 2.4.1: Token sequences extracted and ready for rule generation.'
        )
    else:
        print('  No token sequences detected')
        print(
            '  (May indicate functions with no direct token checks or call sequences)'
        )

    # Phase 2.4.1f: Validate against semantic grammar from parse.c comments
    print('\nSemantic grammar validation (Phase 2.4.1f):')
    validation_results, overall_confidence = validate_semantic_grammar(
        call_graph, parser_functions
    )

    # Categorize results by status
    match_count = sum(1 for r in validation_results.values() if r['status'] == 'match')
    partial_count = sum(
        1 for r in validation_results.values() if r['status'] == 'partial'
    )
    mismatch_count = sum(
        1 for r in validation_results.values() if r['status'] == 'mismatch'
    )

    total_validated = len(validation_results)

    print(f'  Validated {total_validated} parser functions against documented rules')
    print(
        f'  Match rate: {match_count} excellent, {partial_count} good, '
        f'{mismatch_count} divergent'
    )
    print(f'  Overall confidence score: {overall_confidence:.2%}')

    # Show individual results sorted by confidence (best first)
    sorted_results = sorted(
        validation_results.values(), key=lambda r: r['confidence'], reverse=True
    )

    if sorted_results:
        print('\n  Detailed results:')
        for result in sorted_results:
            status_symbol = (
                '✓'
                if result['status'] == 'match'
                else '~'
                if result['status'] == 'partial'
                else '✗'
                if result['status'] == 'mismatch'
                else '?'
            )
            print(
                f'    {status_symbol} {result["func_name"]:30} '
                f'{result["confidence"]:.0%} ({result["num_sequences"]} sequences)'
            )
            if result['notes']:
                # Wrap notes for readability
                notes = result['notes']
                if len(notes) > 70:
                    # Split on " | " for better wrapping
                    parts = notes.split(' | ')
                    for part in parts:
                        print(f'      {part}')
                else:
                    print(f'      {notes}')

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
