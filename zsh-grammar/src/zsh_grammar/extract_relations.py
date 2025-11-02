from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

from clang.cindex import Config, Cursor, CursorKind, Index, TranslationUnit

if TYPE_CHECKING:
    from collections.abc import Mapping

# Adjust to your LLVM install
Config.set_library_file('/opt/homebrew/opt/llvm/lib/libclang.dylib')

PROJECT_ROOT: Final = Path(__file__).resolve().parents[3]
DEFAULT_SRC: Final = PROJECT_ROOT / 'vendor' / 'zsh' / 'Src'
DEFAULT_OUT: Final = PROJECT_ROOT / 'zsh-grammar' / 'relations.json'
DEFAULT_CC: Final = PROJECT_ROOT / 'vendor' / 'zsh_compile_commands.json'

# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------


class _CompileCommand(TypedDict):
    arguments: list[str]
    directory: str
    file: str
    output: str


class _RuleRelations(TypedDict):
    follows: list[str]
    calls: list[str]
    tokens_used: list[str]
    options_used: list[str]
    confidence: float
    location: str
    line: int


class _RelationsOutput(TypedDict):
    rules: dict[str, _RuleRelations]
    metadata: dict[str, str | None]


# ---------------------------------------------------------------------------
# Heuristic patterns
# ---------------------------------------------------------------------------

# matches token names like TOK_IF, INOUTREDIR, etc.
_TOKEN_REGEX: Final = re.compile(r'\b[A-Z_]{3,}\b')
# matches isset(OPTION_NAME)
_OPTION_REGEX: Final = re.compile(r'isset\s*\(\s*([A-Z_]+)\s*\)')
# matches function-like tokens such as wordcode calls
_CALL_REGEX: Final = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(')


# ---------------------------------------------------------------------------
# Core AST traversal
# ---------------------------------------------------------------------------


def _extract_text(tu: TranslationUnit, cursor: Cursor) -> str:
    """Get raw source text of a cursor node."""
    extent = cursor.extent
    tokens = [tok.spelling for tok in tu.get_tokens(extent=extent)]
    return ' '.join(tokens)


def _collect_function_calls(tu: TranslationUnit, cursor: Cursor) -> list[str]:
    """Return list of function calls inside this function."""
    calls: list[str] = []
    for child in cursor.walk_preorder():
        if child.kind == CursorKind.CALL_EXPR and child.spelling:
            calls.append(child.spelling)
    return sorted(set(calls))


def _collect_tokens_and_options(
    tu: TranslationUnit, cursor: Cursor
) -> tuple[list[str], list[str]]:
    """Detect token identifiers and isset() references inside a function."""
    text = _extract_text(tu, cursor)
    tokens = sorted(set(_TOKEN_REGEX.findall(text)))
    options = sorted(set(_OPTION_REGEX.findall(text)))
    return tokens, options


def _estimate_follows(cursor: Cursor, calls: list[str], tokens: list[str]) -> list[str]:
    """
    Heuristic: guess which rules may follow based on control flow and token usage.
    This is intentionally approximate — the normalizer will refine it later.
    """
    follows: list[str] = []
    src = ' '.join(tok.spelling for tok in cursor.get_tokens())

    # If statements referencing next_token / peek_token
    if 'next_token' in src or 'peek_token' in src:
        follows += tokens
    # Chained calls to parse_* functions often indicate rule follow
    follows += [
        call for call in calls if call.startswith('parse_') and call != cursor.spelling
    ]
    return sorted(set(follows))


# ---------------------------------------------------------------------------
# High-level extraction
# ---------------------------------------------------------------------------


def _extract_relations_from_file(
    index: Index, c_file: Path, compile_args: list[str], /
) -> dict[str, _RuleRelations]:
    print(f'Analyzing {c_file} …')
    results: dict[str, _RuleRelations] = {}

    tu = index.parse(c_file, args=compile_args)

    if tu is not None and tu.cursor is not None:
        for child in tu.cursor.get_children():
            if (
                child.kind == CursorKind.FUNCTION_DECL
                and child.is_definition()
                and child.spelling
            ):
                calls = _collect_function_calls(tu, child)
                tokens, options = _collect_tokens_and_options(tu, child)
                follows = _estimate_follows(child, calls, tokens)
                results[child.spelling] = {
                    'follows': follows,
                    'calls': calls,
                    'tokens_used': tokens,
                    'options_used': options,
                    'confidence': 0.9 if tokens or calls else 0.5,
                    'location': str(c_file.relative_to(PROJECT_ROOT, walk_up=True)),
                    'line': child.location.line,
                }
    return results


# ---------------------------------------------------------------------------
# Preprocessor scan
# ---------------------------------------------------------------------------


def _scan_preprocessor_guards(source: str) -> dict[str, list[str]]:
    """
    Detect #ifdef / #if / #ifndef blocks and associate nearby function names.
    This uses regex rather than AST, since Clang's preprocessor info is minimal.
    """
    pattern = re.compile(r'#\s*(ifn?def)\s+([A-Z_]+)')
    guards: dict[str, list[str]] = {}
    lines = source.splitlines()
    for i, line in enumerate(lines):
        if m := pattern.search(line):
            _, symbol = m.groups()
            # look ahead a few lines for a function definition
            for j in range(i + 1, min(i + 10, len(lines))):
                if func := re.match(r'\w[\w\d_]+\s*\(', lines[j]):
                    func_name = func.group(0).split('(')[0]
                    guards.setdefault(func_name, []).append(symbol)
                    break
    return guards


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def extract_zsh_relations(
    source_dir: Path, compile_commands: Mapping[str, _CompileCommand], /
) -> _RelationsOutput:
    index = Index.create()
    compile_args = ['-I.', f'-I{source_dir}', '-DZSH_VERSION="5.9"', '-std=c99']
    c_files = [
        'parse.c',
        'cond.c',
        'glob.c',
        'params.c',
        'string.c',
        'text.c',
    ]

    rules: dict[str, _RuleRelations] = {}
    for name in c_files:
        path = source_dir / name
        if not path.exists():
            continue
        file_compile_command = compile_commands.get(name)
        file_compile_args = (
            compile_args
            if file_compile_command is None
            else file_compile_command['arguments'][2:-3]
        )
        partial = _extract_relations_from_file(
            index,
            path,
            file_compile_args,
        )
        source = path.read_text(encoding='utf-8')
        guards = _scan_preprocessor_guards(source)

        # merge guard info into relations
        for func, rel in partial.items():
            if func in guards:
                rel['options_used'] = sorted(set(rel['options_used'] + guards[func]))
        rules.update(partial)

    return {
        'rules': rules,
        'metadata': {
            'source': str(source_dir),
            'analyzer': 'extract_zsh_relations.py',
            'clang_version': str(Config.library_file),
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description='Extract raw zsh source metadata')
    parser.add_argument(
        '--src', type=Path, default=DEFAULT_SRC, help='Path to zsh Source dir'
    )
    parser.add_argument(
        '--out', type=Path, default=DEFAULT_OUT, help='Output JSON file'
    )
    parser.add_argument(
        '--compile-commands',
        type=Path,
        default=DEFAULT_CC,
        help='Compile commands JSON file',
    )
    parser.add_argument(
        '--clang',
        type=Path,
        default=os.environ.get('LIBCLANG_PATH'),
        help='Path to libclang',
    )
    parser.add_argument('--zsh-version', type=str, default='5.9', dest='zsh_version')
    parser.add_argument('--verbose', action='store_true')

    args = parser.parse_args()

    compile_commands: list[_CompileCommand] = json.loads(
        args.compile_commands.read_text()
    )
    compile_commands_map = {
        str(Path(command['file']).relative_to(args.src)): command
        for command in compile_commands
    }

    args = parser.parse_args()
    src_dir = args.src
    output = extract_zsh_relations(src_dir, compile_commands_map)
    args.out.write_text(json.dumps(output, indent=2))
    print(f'✅ Wrote {args.out}')


if __name__ == '__main__':
    main()
