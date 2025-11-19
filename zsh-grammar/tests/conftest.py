"""Pytest configuration and fixtures for Phase 2.4.1 tests.

Provides fixtures for loading parse.c and extracting parser functions.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from clang.cindex import TranslationUnit

from zsh_grammar.ast_utilities import find_function_definitions
from zsh_grammar.source_parser import ZshParser

if TYPE_CHECKING:
    from _typeshed import StrPath
    from collections.abc import Iterator

    from clang.cindex import Cursor


def pytest_addoption(
    parser: pytest.Parser, pluginmanager: pytest.PytestPluginManager
) -> None:
    parser.addoption(
        '--clear-ast-cache',
        action='store_true',
        default=False,
        help='Clear cached AST files before running tests.',
    )


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption('--clear-ast-cache'):
        cache_dir = config.cache._cachedir / 'ast'
        if cache_dir.exists():
            shutil.rmtree(cache_dir)


@dataclass(slots=True)
class CachedZshParser:
    """ZshParser wrapper that caches parsed ASTs to .ast files."""

    zsh_src: Path
    cache_dir: Path
    zsh_parser: ZshParser = field(init=False)

    def __post_init__(self) -> None:
        self.zsh_parser = ZshParser(self.zsh_src)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def parse(
        self, path: StrPath, /, *, expand_macros: bool = False
    ) -> TranslationUnit | None:
        """Parse with automatic AST caching.

        Args:
            path: Path to source file, relative to zsh_src or absolute
            expand_macros: If True, expands macros via clang preprocessing

        Returns:
            TranslationUnit or None if parsing fails
        """
        source_file = self.zsh_src / path if isinstance(path, str) else Path(path)
        cache_file = self.cache_dir / f'{source_file.stem}.ast'

        # Check cache validity (cache must be newer than source)
        cache_newer = (
            cache_file.exists()
            and cache_file.stat().st_mtime > source_file.stat().st_mtime
        )
        if cache_newer:
            try:
                return TranslationUnit.from_ast_file(cache_file)
            except OSError as e:
                # Cache corrupted or incompatible, fall through to re-parse
                print(
                    f'Warning: failed to load cached AST {cache_file}: {e}',
                    file=sys.stderr,
                )

        # Parse fresh and cache
        tu = self.zsh_parser.parse(source_file, expand_macros=expand_macros)
        if tu is not None:
            try:
                tu.save(cache_file)
            except OSError as e:
                print(
                    f'Warning: failed to cache AST {cache_file}: {e}',
                    file=sys.stderr,
                )

        return tu

    def parse_files(
        self, glob_pattern: str, /
    ) -> Iterator[tuple[Path, TranslationUnit]]:
        """
        Parse multiple Zsh source files matching a glob pattern.

        Args:
            glob_pattern (str): Glob pattern to match source files.

        Yields:
            tuple[Path, TranslationUnit]: Each file path and its parsed translation
            unit. Files that fail preprocessing are skipped.
        """
        for file in self.zsh_src.glob(glob_pattern):
            tu = self.parse(file)
            if tu is not None:
                yield file, tu


@pytest.fixture(scope='session')
def zsh_parser(request: pytest.FixtureRequest) -> CachedZshParser:
    """Initialize CachedZshParser with zsh source directory."""
    # Set clang library path if environment variable is set
    libclang_prefix = os.environ.get('LIBCLANG_PREFIX')
    if libclang_prefix:
        ZshParser.set_clang_prefix(libclang_prefix)

    zsh_src = Path(__file__).parent.parent.parent / 'vendor' / 'zsh' / 'Src'
    cache_dir = request.config.cache._cachedir / 'ast'

    return CachedZshParser(zsh_src, cache_dir)


@pytest.fixture(scope='session')
def parse_c_path(zsh_parser: CachedZshParser) -> Path:
    """Get path to parse.c file."""
    return zsh_parser.zsh_src / 'parse.c'


@pytest.fixture(scope='session')
def parse_c_ast(zsh_parser: CachedZshParser) -> TranslationUnit:
    """Load and parse parse.c AST, using cached .ast file if available."""
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
