from __future__ import annotations

import json
import os
import re
import subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import TYPE_CHECKING, Final, NotRequired, TypedDict, cast

from clang.cindex import Cursor, CursorKind, StorageClass

from zsh_grammar.grammar_utils import (
    create_ref,
    create_sequence,
    create_terminal,
    create_token,
    create_union,
)
from zsh_grammar.source_parser import ZshParser

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from zsh_grammar._types import Grammar, Language

PROJECT_ROOT: Final = Path(__file__).resolve().parents[3]


class _FunctionNode(TypedDict):
    name: str
    file: str
    line: int
    calls: list[str]
    conditions: NotRequired[list[str]]
    signature: NotRequired[str]
    visibility: NotRequired[str]


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
            if not func_name.startswith(('par_', 'parse_')):
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

        for cursor in tu.cursor.walk_preorder():
            if cursor.kind == CursorKind.FUNCTION_DECL and cursor.is_definition():
                function_name = cursor.spelling
                calls: list[str] = []

                for child in cursor.walk_preorder():
                    if child.kind == CursorKind.CALL_EXPR:
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


def _build_grammar_rules(
    call_graph: dict[str, _FunctionNode], parser_functions: dict[str, _FunctionNode], /
) -> Language:
    """
    Infer grammar rules from the call graph using call pattern heuristics.

    Strategy:
    1. Identify core parsing functions (par_* and parse_* functions)
    2. For each function, extract unique parse function calls
    3. Classify based on:
       - No calls: leaf/terminal
       - 1 call: sequential composition
       - Multiple calls: union (alternatives/dispatch)

    Note: The call pattern inference is approximate. A function that calls
    multiple parse functions typically does so via switch/if statements,
    making them mutually exclusive unions rather than sequential.
    """
    rules: Language = {}

    # Identify core parsing functions
    core_parse_funcs = {
        name: node
        for name, node in call_graph.items()
        if name.startswith(('par_', 'parse_'))
    }

    # Build rules from parse functions
    for func_name, node in core_parse_funcs.items():
        rule_name = _function_to_rule_name(func_name)

        # Extract unique parse function calls
        called_funcs = node['calls']
        unique_parse_calls = sorted(
            {f for f in called_funcs if f.startswith(('par_', 'parse_')) and f != func_name}
        )

        # Convert called function names to rule refs
        rule_refs = [create_ref(_function_to_rule_name(f)) for f in unique_parse_calls]

        # Build source info from parser_functions if available
        source_info = None
        if func_name in parser_functions:
            pf = parser_functions[func_name]
            source_info = {
                'file': pf['file'],
                'line': pf['line'],
                'function': func_name,
            }
        else:
            # Fallback from call_graph
            source_info = {
                'file': node['file'],
                'line': node['line'],
                'function': func_name,
            }

        # Classify rule based on unique calls
        if not unique_parse_calls:
            # No parse function calls -> leaf/terminal
            # These are typically token consumers (par_getword, etc.)
            rules[rule_name] = create_terminal(
                f'[{rule_name}]', source=source_info
            )
        elif len(unique_parse_calls) == 1:
            # Single unique parse call -> direct delegation/reference
            # Don't wrap single refs in a sequence (sequences need 2+ elements)
            ref_name = _function_to_rule_name(unique_parse_calls[0])
            rules[rule_name] = create_ref(ref_name, source=source_info)
        else:
            # Multiple unique calls -> union/alternatives
            # (typically via switch/if statements with mutually exclusive branches)
            rules[rule_name] = create_union(
                rule_refs, source=source_info
            )

    return rules


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
                                tokens = list(expr.get_tokens())
                                if tokens:
                                    token_name = tokens[0].spelling
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
                                    if callee.startswith(('par_', 'parse_')):
                                        # Convert function name to rule name
                                        if callee.startswith('par_'):
                                            rule_name = callee[
                                                4:
                                            ]  # Remove 'par_' prefix
                                        else:
                                            rule_name = callee[
                                                6:
                                            ]  # Remove 'parse_' prefix

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
                                        if callee.startswith(('par_', 'parse_')):
                                            # Convert function name to rule name
                                            if callee.startswith('par_'):
                                                rule_name = callee[
                                                    4:
                                                ]  # Remove 'par_' prefix
                                            else:
                                                rule_name = callee[
                                                    6:
                                                ]  # Remove 'parse_' prefix

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
                                    if callee.startswith(('par_', 'parse_')):
                                        # Convert function name to rule name
                                        if callee.startswith('par_'):
                                            rule_name = callee[
                                                4:
                                            ]  # Remove 'par_' prefix
                                        else:
                                            rule_name = callee[
                                                6:
                                            ]  # Remove 'parse_' prefix

                                        # For default case, associate with special token
                                        # Indicates it's the fallback/catch-all rule
                                        yield '__default__', rule_name
                                        break


def _map_tokens_to_rules(
    parser: ZshParser, parser_functions: dict[str, _FunctionNode], /
) -> dict[str, list[str]]:
    """
    Extract token-to-rule mappings from switch statements in dispatcher functions.

    For each dispatcher function (like par_cmd), extracts case statements and
    determines which token maps to which parser rule.

    This function:
    1. Scans for SWITCH_STMT nodes in all parser functions
    2. Extracts case statements and their handler function calls
    3. Identifies which tokens (case labels) map to which parser rules

    Returns: Dictionary mapping token names (SCREAMING_SNAKE_CASE) to lists of
    rule names (lower_snake_case) that handle them.
    """
    token_to_rules: dict[str, list[str]] = {}

    # Parse parse.c to access all functions
    tu = parser.parse('parse.c')
    if tu is None or tu.cursor is None:
        return token_to_rules

    # Find all functions in parse.c and extract their case statements
    parser_func_names = set(parser_functions.keys())
    for cursor in tu.cursor.walk_preorder():
        if (
            cursor.kind == CursorKind.FUNCTION_DECL
            and cursor.is_definition()
            and cursor.spelling in parser_func_names
        ):
            # Extract case statements from this function
            # This will find dispatchers like par_cmd, and any other function
            # that has switch statements
            for token_name, rule_name in _extract_case_statements(cursor):
                if token_name not in token_to_rules:
                    token_to_rules[token_name] = []
                if rule_name not in token_to_rules[token_name]:
                    token_to_rules[token_name].append(rule_name)

    return token_to_rules


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

    for token_name, hash_key in _parse_hash_entries(parser):
        if token_name in result:
            result[token_name]['text'].append(hash_key)

    for value, text in _parse_token_strings(parser):
        if value in by_value:
            by_value[value]['text'].append(text)

    return result


def _validate_schema(grammar: Grammar, schema_path: Path, /) -> list[str]:
    """
    Validate the grammar against the JSON schema.
    
    Returns a list of validation errors, or an empty list if valid.
    """
    try:
        import jsonschema
    except ImportError:
        return ['jsonschema library not available for validation']
    
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


def _construct_grammar(zsh_path: Path, version: str, /) -> Grammar:  # noqa: PLR0912
    zsh_src = zsh_path / 'Src'
    parser = ZshParser(zsh_src)

    # Phase 1: Extract parser functions from .syms files
    parser_functions = _extract_parser_functions(zsh_src)

    # Phase 1.2: Map tokens to rules from switch/case statements
    token_to_rules = _map_tokens_to_rules(parser, parser_functions)

    # Phase 2: Build call graph for analyzing function composition
    call_graph = _build_call_graph(parser)

    # Phase 1.2: Validate completeness of rule references
    completeness_report = _validate_completeness(
        token_to_rules, parser_functions, call_graph
    )

    token_mapping = _build_token_mapping(parser)

    core_symbols: Language = {
        token['token']: create_token(
            token['token'],
            token['text'][0],
            source={'file': token['file'], 'line': token['line']},
        )
        if len(token['text']) == 1
        else create_token(
            token['token'],
            token['text'],
            source={'file': token['file'], 'line': token['line']},
        )
        for token in token_mapping.values()
        if token['text']
    }

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

    # Phase 3: Build grammar rules from call graph
    grammar_rules = _build_grammar_rules(call_graph, parser_functions)
    
    # Merge rules into core_symbols
    core_symbols.update(grammar_rules)

    # Log extracted parser functions for debugging
    if parser_functions:
        print(f'Extracted {len(parser_functions)} parser functions:')
        for name, node in sorted(parser_functions.items()):
            vis = node.get('visibility', 'unknown')
            sig = node.get('signature', '(...)')
            print(f'  {name:30} {vis:10} {sig}')

    # Log token-to-rule mappings
    if token_to_rules:
        # Separate explicit tokens from default
        explicit_tokens = {
            k: v for k, v in token_to_rules.items() if k != '__default__'
        }
        default_rule = token_to_rules.get('__default__')

        print(f'\nToken-to-rule mappings found: {len(explicit_tokens)} explicit tokens')
        for token, rules in sorted(explicit_tokens.items()):
            print(f'  {token:30} → {", ".join(rules)}')

        if default_rule:
            print(f'\n  Default (catch-all) handler: {", ".join(default_rule)}')

    # Log completeness report
    print('\nCompleteness validation report:')
    if completeness_report:
        for issue_type, items in sorted(completeness_report.items()):
            print(f'  {issue_type}:')
            for item in items:
                print(f'    - {item}')
    else:
        print('  (No issues found - all rules are referenced)')

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
