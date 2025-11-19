"""Pytest configuration and fixtures for Phase 2.4.1 tests.

Provides fixtures for loading parse.c and extracting parser functions.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from zsh_grammar.ast_utilities import find_function_definitions
from zsh_grammar.source_parser import ZshParser

if TYPE_CHECKING:
    from clang.cindex import Cursor, TranslationUnit


@pytest.fixture(scope='session')
def zsh_parser() -> ZshParser:
    """Initialize ZshParser with zsh source directory."""
    # Set clang library path if environment variable is set
    libclang_prefix = os.environ.get('LIBCLANG_PREFIX')
    if libclang_prefix:
        ZshParser.set_clang_prefix(libclang_prefix)

    zsh_src = Path(__file__).parent.parent.parent / 'vendor' / 'zsh' / 'Src'
    return ZshParser(zsh_src)


@pytest.fixture(scope='session')
def parse_c_ast(zsh_parser: ZshParser) -> TranslationUnit:
    """Load and parse parse.c AST."""
    tu = zsh_parser.parse('parse.c')
    if tu is None:
        pytest.skip('Failed to parse parse.c')
    return tu


@pytest.fixture(scope='session')
def parser_functions_ast(
    parse_c_ast: TranslationUnit,
) -> dict[str, Cursor]:
    """Extract all parser function definitions from parse.c AST."""
    functions: dict[str, Cursor] = {}

    # List of known parser functions to extract
    parser_func_names = {
        'par_event',
        'par_list',
        'par_sublist',
        'par_pline',
        'par_cmd',
        'par_for',
        'par_case',
        'par_if',
        'par_while',
        'par_repeat',
        'par_subsh',
        'par_funcdef',
        'par_time',
        'par_dinbrack',
        'par_simple',
        'par_redir',
        'par_wordlist',
        'par_nl_wordlist',
        'par_cond',
        'par_cond_double',
    }

    if parse_c_ast.cursor is not None:
        for func in find_function_definitions(parse_c_ast.cursor, parser_func_names):
            functions[func.spelling] = func

    return functions


@pytest.fixture
def par_subsh(parser_functions_ast: dict[str, Cursor]) -> Cursor:
    """Get par_subsh function cursor."""
    if 'par_subsh' not in parser_functions_ast:
        pytest.skip('par_subsh not found in parse.c')
    return parser_functions_ast['par_subsh']


@pytest.fixture
def par_if(parser_functions_ast: dict[str, Cursor]) -> Cursor:
    """Get par_if function cursor."""
    if 'par_if' not in parser_functions_ast:
        pytest.skip('par_if not found in parse.c')
    return parser_functions_ast['par_if']


@pytest.fixture
def par_case(parser_functions_ast: dict[str, Cursor]) -> Cursor:
    """Get par_case function cursor."""
    if 'par_case' not in parser_functions_ast:
        pytest.skip('par_case not found in parse.c')
    return parser_functions_ast['par_case']


@pytest.fixture
def par_while(parser_functions_ast: dict[str, Cursor]) -> Cursor:
    """Get par_while function cursor."""
    if 'par_while' not in parser_functions_ast:
        pytest.skip('par_while not found in parse.c')
    return parser_functions_ast['par_while']


@pytest.fixture
def par_for(parser_functions_ast: dict[str, Cursor]) -> Cursor:
    """Get par_for function cursor."""
    if 'par_for' not in parser_functions_ast:
        pytest.skip('par_for not found in parse.c')
    return parser_functions_ast['par_for']


@pytest.fixture
def par_simple(parser_functions_ast: dict[str, Cursor]) -> Cursor:
    """Get par_simple function cursor."""
    if 'par_simple' not in parser_functions_ast:
        pytest.skip('par_simple not found in parse.c')
    return parser_functions_ast['par_simple']


@pytest.fixture
def par_cond(parser_functions_ast: dict[str, Cursor]) -> Cursor:
    """Get par_cond function cursor."""
    if 'par_cond' not in parser_functions_ast:
        pytest.skip('par_cond not found in parse.c')
    return parser_functions_ast['par_cond']
