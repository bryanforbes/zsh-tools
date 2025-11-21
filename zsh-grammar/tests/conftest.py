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

from zsh_grammar.source_parser import ZshParser

if TYPE_CHECKING:
    from _typeshed import StrPath
    from collections.abc import Iterator


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
