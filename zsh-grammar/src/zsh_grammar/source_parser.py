from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from clang.cindex import Config, TranslationUnit

if TYPE_CHECKING:
    from _typeshed import StrPath
    from collections.abc import Iterator


@dataclass
class ZshParser:
    """
    Parser for Zsh source files using libclang.

    Attributes:
        zsh_src (Path): Path to the root of the Zsh source directory.
    """

    zsh_src: Path

    def parse(self, path: StrPath, /) -> TranslationUnit | None:
        """
        Preprocess and parse a Zsh C source file, returning its Clang AST.

        Args:
            path (StrPath): Relative or absolute path to the source file.

        Returns:
            TranslationUnit | None: The parsed Clang translation unit, or None if
            preprocessing fails.

        Side Effects:
            Prints a warning to stderr if clang preprocessing fails.
        """
        path = self.zsh_src / path if isinstance(path, str) else Path(path)

        clang_args: list[str] = [
            '-x',
            'c',
            '-std=c99',
            '-I.',
            '-I../Src',
            '-I../Src/Zle',
            '-DHAVE_CONFIG_H',
        ]

        with subprocess.Popen(  # noqa: S603
            [
                (
                    Path(cast('str', Config.library_path)) / '..' / 'bin' / 'clang'
                ).resolve(),
                '-E',
                *clang_args,
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as proc:
            source, _ = proc.communicate()
            if proc.returncode != 0:
                print('Warning: clang preprocessing failed', file=sys.stderr)
                return None

        return TranslationUnit.from_source(
            path,
            args=clang_args,
            options=TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD,
            unsaved_files=[(path, source)],
        )

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

    @staticmethod
    def set_clang_prefix(prefix: StrPath, /) -> None:
        """
        Set the prefix path for the Clang library used by libclang.

        Args:
            prefix (StrPath): Path to the root of the Clang installation. The 'lib'
            subdirectory containing the Clang shared library will be appended
            automatically.

        Side Effects:
            Updates the library path for clang.cindex.Config, affecting subsequent Clang
            operations.
        """
        Config.set_library_path(Path(prefix).absolute() / 'lib')
