from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final, cast

import typer

from zsh_grammar.source_parser import ZshParser

if TYPE_CHECKING:
    from zsh_grammar._types import GrammarDict

PROJECT_ROOT: Final = Path(__file__).resolve().parents[3]


def _construct_grammar(
    *,
    clang_prefix: Annotated[
        Path,
        typer.Option(
            envvar='LIBCLANG_PREFIX',
            file_okay=False,
            dir_okay=True,
            exists=True,
            resolve_path=True,
            help='Path to Clang installation prefix (for libclang).',
        ),
    ],
    src: Annotated[
        Path,
        typer.Option(
            file_okay=False,
            dir_okay=True,
            readable=True,
            exists=True,
            resolve_path=True,
            help='Path to Zsh source',
        ),
    ] = PROJECT_ROOT / 'vendor' / 'zsh',
    output: Annotated[
        Path,
        typer.Option(
            file_okay=True,
            dir_okay=False,
            writable=True,
            resolve_path=True,
            help='File to write the output grammar to.',
        ),
    ] = PROJECT_ROOT / 'zsh-grammar' / 'canonical-grammar.json',
) -> None:
    if clang_prefix:
        ZshParser.set_clang_prefix(clang_prefix)

    version_mk = (src / 'Config' / 'version.mk').read_text()
    if (match := re.search(r'^VERSION=(.*)$', version_mk, re.M)) is not None:
        version = cast('str', match[1])  # noqa: F841
    else:
        raise ValueError('No VERSION found')

    grammar: GrammarDict = {
        '$schema': './canonical-grammar.schema.json',
        'languages': {'core': {'rules': {}, 'tokens': {}}},
    }

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


def main() -> None:
    typer.run(_construct_grammar)
