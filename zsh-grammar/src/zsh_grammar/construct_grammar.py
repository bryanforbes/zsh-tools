from __future__ import annotations

import json
import os
import re
import subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

from zsh_grammar.source_parser import ZshParser

if TYPE_CHECKING:
    from zsh_grammar._types import Grammar

PROJECT_ROOT: Final = Path(__file__).resolve().parents[3]


def _construct_grammar(zsh_path: Path, version: str, /) -> Grammar:
    return {
        '$schema': './canonical-grammar.schema.json',
        'languages': {'core': {'rules': {}, 'tokens': {}}},
    }


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
