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
    create_terminal_pattern,
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


def _build_grammar_rules(call_graph: dict[str, _FunctionNode], /) -> Language:
    """
    Infer grammar rules from the call graph using call pattern heuristics.

    Strategy:
    1. Identify core parsing functions (par_* functions)
    2. For each function, extract unique parse function calls
    3. Classify based on:
       - No calls: token (terminal/leaf)
       - 1 call: sequence (direct composition)
       - Multiple calls: union (alternatives/dispatch)

    Note: The call pattern inference is approximate. A function that calls
    multiple parse functions typically does so via switch/if statements,
    making them mutually exclusive unions rather than sequential.
    """
    rules: Language = {}

    # Identify core parsing functions (exclude conditional parsing)
    core_parse_funcs = {
        name: node
        for name, node in call_graph.items()
        if name.startswith(('par_', 'parse_')) and not name.startswith('par_cond')
    }

    # Build rules from parse functions
    for func_name, node in core_parse_funcs.items():
        # Extract unique parse function calls
        called_funcs = node['calls']
        unique_parse_calls = sorted(
            {f for f in called_funcs if f.startswith('par_') and f != func_name}
        )

        # Classify rule based on unique calls
        if not unique_parse_calls:
            # No parse function calls -> token/terminal
            rules[func_name] = create_terminal_pattern(f'[{func_name}]')
        elif len(unique_parse_calls) == 1:
            # Single unique parse call -> direct composition
            rules[func_name] = create_sequence(unique_parse_calls)
        else:
            # Multiple unique calls -> dispatch/union
            # (typically via switch/if statements with mutually exclusive branches)
            rules[func_name] = create_union(unique_parse_calls)

    return rules


class _TokenDef(TypedDict):
    token: str
    value: int
    text: list[str]


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


def _find_all_cursors(
    cursor: Cursor | None, predicate: Callable[[Cursor], bool], /
) -> Iterator[Cursor]:
    if cursor is not None:
        for child in cursor.walk_preorder():
            if predicate(child):
                yield child


def _parse_hash_entries(parser: ZshParser, /) -> Iterator[tuple[str, str]]:
    tu = parser.parse('hashtable.c')
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
    tu = parser.parse('lex.c')

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
            }
            by_value[value] = result[child.spelling]

    for token_name, hash_key in _parse_hash_entries(parser):
        if token_name in result:
            result[token_name]['text'].append(hash_key)

    for value, text in _parse_token_strings(parser):
        if value in by_value:
            by_value[value]['text'].append(text)

    return result


def _construct_grammar(zsh_path: Path, version: str, /) -> Grammar:
    parser = ZshParser(zsh_path / 'Src')

    token_mapping = _build_token_mapping(parser)

    core_symbols: Language = {
        token['token']: token['text'][0]
        if len(token['text']) == 1
        else create_union(token['text'])
        for token in token_mapping.values()
        if token['text']
    }

    core_symbols['Parameter'] = create_union(
        [create_ref('Variable'), '*', '@', '#', '?', '-', '$', '!']
    )
    core_symbols['Variable'] = create_terminal_pattern('[a-zA-Z0-9_]+')

    # call_graph = _build_call_graph(parser)

    # Parse call graph to build grammar
    # grammar_rules = _build_grammar_rules(call_graph)

    grammar: Grammar = {
        '$schema': './canonical-grammar.schema.json',
        'languages': {'core': core_symbols},
        'zsh_version': version,
    }

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
