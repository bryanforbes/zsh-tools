from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Self

from clang.cindex import (
    Config,
    Cursor,
    CursorKind,
    Index,
    Token as ClangToken,
    TranslationUnit,
    TranslationUnitLoadError,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

# Defaults
PROJECT_ROOT: Final = Path(__file__).resolve().parents[3]
DEFAULT_SRC: Final = PROJECT_ROOT / 'vendor' / 'zsh' / 'Src'
DEFAULT_OUT: Final = PROJECT_ROOT / 'zsh-grammar' / 'zsh_raw_extraction.json'

# The option names in Zsh source code do not have underscores
TRACKED_OPTIONS: Final = {
    'EXTENDEDGLOB',
    'RCEXPANDPARAM',
    'KSHARRAYS',
    'SHWORDSPLIT',
}


def relpath(p: Path, base: Path) -> str:
    try:
        return str(p.relative_to(base, walk_up=True))
    except Exception:  # noqa: BLE001
        return str(p)


def parse_one(
    index: Index, path: Path, args: list[str], base: Path
) -> tuple[Any | None, str | None]:
    try:
        tu = index.parse(
            str(path),
            args=args,
            options=TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD,
        )
    except TranslationUnitLoadError as e:
        return None, str(e)
    except Exception as e:  # noqa: BLE001
        return None, f'{type(e).__name__}: {e}'
    else:
        return tu, None


@dataclass(frozen=True, slots=True)
class Location:
    file: str
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class BaseDef:
    name: str
    location: Location


@dataclass(frozen=True, slots=True)
class FunctionDef(BaseDef):
    return_type: str
    params: list[dict[str, str]]
    usr: str | None

    @classmethod
    def from_cursor(cls, cursor: Cursor, location: Location, /) -> Self:
        params = [
            {'name': argument.spelling, 'type': argument.type.spelling}
            for argument in cursor.get_arguments()
            if argument is not None
        ]

        return cls(
            name=cursor.spelling,
            return_type=cursor.result_type.spelling,
            params=params,
            location=location,
            usr=cursor.get_usr() if hasattr(cursor, 'get_usr') else None,
        )


@dataclass(frozen=True, slots=True)
class EnumConst:
    name: str
    value: int | None


@dataclass(frozen=True, slots=True)
class EnumDef(BaseDef):
    constants: list[EnumConst]
    is_token_enum: bool

    @classmethod
    def from_cursor(cls, cursor: Cursor, location: Location, /) -> Self:
        consts: list[EnumConst] = []
        for child in cursor.get_children():
            if child.kind == CursorKind.ENUM_CONSTANT_DECL and child.spelling:
                value = getattr(child, 'enum_value', None)
                consts.append(EnumConst(name=child.spelling, value=value))
        name = cursor.spelling
        return cls(
            name=name,
            location=location,
            constants=consts,
            # Heuristic: token enums live in lex/parse or contain 'tok'
            is_token_enum='tok' in name or location.file in ('lex.c', 'parse.c'),
        )


@dataclass(slots=True)
class StatsDef:
    functions: int = field(default=0)
    enums: int = field(default=0)
    macros: int = field(default=0)
    typedefs: int = field(default=0)
    structs: int = field(default=0)
    unions: int = field(default=0)


@dataclass(frozen=True, slots=True)
class FileDef:
    path: str
    parsed: bool
    error: str | None
    stats: StatsDef


@dataclass(frozen=True, slots=True)
class MacroDef(BaseDef):
    value: str | None
    function_like: bool

    @classmethod
    def from_cursor(cls, cursor: Cursor, location: Location, /) -> Self:
        # Best-effort: join tokens inside macro extent; may be empty if libclang omits
        # preprocessing tokens
        try:
            tokens: Iterable[ClangToken] = cursor.get_tokens()
            parts = [token.spelling for token in tokens]
            # Skip leading '#', 'define', and macro name
            if parts[:2] == ['#', 'define'] and len(parts) >= 3:
                parts = parts[3:]
            value = ' '.join(parts).strip() or None
        except Exception:  # noqa: BLE001
            value = None
        func_like = '(' in (value or '')
        return cls(
            name=cursor.spelling,
            value=value,
            function_like=func_like,
            location=location,
        )


# --- New dataclasses for types/structs/unions --- #
@dataclass(frozen=True, slots=True)
class TypedefDef(BaseDef):
    underlying_type: str | None
    usr: str | None

    @classmethod
    def from_cursor(cls, cursor: Cursor, location: Location, /) -> Self:
        # Record typedefs (best-effort)
        try:
            underlying = None
            # clang.cindex may provide underlying_typedef_type
            if hasattr(cursor, 'underlying_typedef_type'):
                try:
                    underlying = cursor.underlying_typedef_type.spelling
                except Exception:  # noqa: BLE001
                    underlying = None
            if not underlying:
                try:
                    underlying = cursor.type.get_canonical().spelling
                except Exception:  # noqa: BLE001
                    underlying = cursor.type.spelling
        except Exception:  # noqa: BLE001
            underlying = None
        return cls(
            name=cursor.spelling,
            underlying_type=underlying,
            usr=cursor.get_usr() if hasattr(cursor, 'get_usr') else None,
            location=location,
        )


@dataclass(frozen=True, slots=True)
class FieldDef:
    name: str | None
    type: str | None


@dataclass(frozen=True, slots=True)
class StructDef(BaseDef):
    fields: list[FieldDef]
    usr: str | None

    @classmethod
    def from_cursor(cls, cursor: Cursor, location: Location, /) -> Self:
        return cls(
            name=cursor.spelling,
            fields=[
                FieldDef(
                    name=child.spelling or None,
                    type=getattr(child.type, 'spelling', None),
                )
                for child in cursor.get_children()
                if child.kind == CursorKind.FIELD_DECL
            ],
            usr=cursor.get_usr() if hasattr(cursor, 'get_usr') else None,
            location=location,
        )


@dataclass(frozen=True, slots=True)
class UnionDef(StructDef): ...


def paths_match(tu: TranslationUnit, child: Cursor, /) -> bool:
    # Robustly match AST child to this translation unit.
    # Prefer comparing resolved absolute paths; fall back to basename
    # or suffix checks when resolution fails or when TU spelling is a
    # basename rather than a full path.
    if child.location.file is None:
        return False

    tu_path = Path(tu.spelling)
    child_path = Path(str(child.location.file))

    try:
        # If both can be resolved, compare canonical paths first.
        if child_path.resolve() == tu_path.resolve():
            pass  # matched by resolved path
        # Fall back to basename match or TU ending with filename
        elif child_path.name != tu_path.name and not tu.spelling.endswith(
            child_path.name
        ):
            return False
    except Exception:  # noqa: BLE001
        # If resolve() fails (e.g., file missing, permission), use name/suffix checks.
        if child_path.name != tu_path.name and not tu.spelling.endswith(
            child_path.name
        ):
            return False

    return True


@dataclass(frozen=True, slots=True)
class ZshParser:
    src_dir: Path
    clang_args: list[str]
    version: str
    verbose: bool

    index: Index = field(init=False, default_factory=lambda: Index.create())
    files: list[FileDef] = field(init=False, default_factory=list)
    functions: list[FunctionDef] = field(init=False, default_factory=list)
    enums: list[EnumDef] = field(init=False, default_factory=list)
    macros: list[MacroDef] = field(init=False, default_factory=list)
    typedefs: list[TypedefDef] = field(init=False, default_factory=list)
    structs: list[StructDef] = field(init=False, default_factory=list)
    unions: list[UnionDef] = field(init=False, default_factory=list)
    option_occurrences: dict[str, list[dict[str, Any]]] = field(
        init=False,
        default_factory=lambda: {option: [] for option in sorted(TRACKED_OPTIONS)},
    )
    errors: list[str] = field(init=False, default_factory=list)

    def __gather(self, tu: TranslationUnit, stats: StatsDef, /) -> None:  # noqa: C901, PLR0912
        func_ranges: list[tuple[tuple[int, int, int, int], str]] = []

        cursor = tu.cursor
        if cursor is not None:
            for child in cursor.get_children():
                if not paths_match(tu, child):
                    continue

                loc = child.location
                file = Path(str(loc.file)) if loc.file else Path('<unknown>')
                location = Location(
                    file=relpath(file, self.src_dir),
                    line=loc.line or 0,
                    column=loc.column or 0,
                )

                if child.kind == CursorKind.FUNCTION_DECL and child.is_definition():
                    if child.spelling:
                        self.functions.append(FunctionDef.from_cursor(child, location))
                        stats.functions += 1

                    func_ranges.append(
                        (
                            (
                                child.extent.start.line,
                                child.extent.start.column,
                                child.extent.end.line,
                                child.extent.end.column,
                            ),
                            child.spelling,
                        )
                    )

                elif child.kind == CursorKind.ENUM_DECL:
                    self.enums.append(EnumDef.from_cursor(child, location))
                    stats.enums += 1

                elif child.kind == CursorKind.MACRO_DEFINITION and child.spelling:
                    self.macros.append(MacroDef.from_cursor(child, location))
                    stats.macros += 1

                elif child.kind == CursorKind.TYPEDEF_DECL and child.spelling:
                    self.typedefs.append(TypedefDef.from_cursor(child, location))
                    stats.typedefs += 1

                elif child.kind == CursorKind.STRUCT_DECL:
                    struct = StructDef.from_cursor(child, location)
                    if struct.fields or struct.name:
                        self.structs.append(struct)
                        stats.structs += 1

                elif child.kind == CursorKind.UNION_DECL:
                    union = UnionDef.from_cursor(child, location)
                    if union.fields or union.name:
                        self.unions.append(union)
                        stats.unions += 1

            try:

                def enclosing_func(line: int, col: int) -> str | None:
                    for (sl, sc, el, ec), nm in func_ranges:
                        if (line > sl or (line == sl and col >= sc)) and (
                            line < el or (line == el and col <= ec)
                        ):
                            return nm
                    return None

                for token in tu.get_tokens(extent=cursor.extent):
                    if token.spelling in TRACKED_OPTIONS:
                        loc = Location(
                            file=relpath(Path(str(token.location.file)), self.src_dir),
                            line=token.location.line,
                            column=token.location.column,
                        )
                        self.option_occurrences.setdefault(token.spelling, []).append(
                            {
                                'file': loc.file,
                                'line': loc.line,
                                'column': loc.column,
                                'in_function': enclosing_func(
                                    token.location.line, token.location.column
                                ),
                            }
                        )
            except Exception:  # noqa: BLE001, S110
                pass

    def parse(self, file: str) -> None:
        path = self.src_dir / file
        tu, error = parse_one(self.index, path, self.clang_args, self.src_dir)

        stats = StatsDef()
        self.files.append(
            FileDef(
                path=relpath(path, self.src_dir),
                parsed=tu is not None,
                error=error,
                stats=stats,
            )
        )

        if error or tu is None:
            if self.verbose:
                print(f'! Failed to parse {path}: {error}')
            self.errors.append(f'{path.name}: {error}')
            return

        self.__gather(tu, stats)

        if self.verbose:
            print(f'\u2713 {path.name}: {stats}')

    def save_extraction(self, out_path: Path, /) -> None:
        doc: dict[str, object] = {
            'meta': {
                'zsh_version': self.version,
                'source_dir': str(relpath(self.src_dir, out_path.parent)),
                'clang_args': self.clang_args,
                'generated_at': datetime.now(UTC).isoformat(),
            },
            'files': [asdict(file) for file in self.files],
            'functions': [
                asdict(func) for func in sorted(self.functions, key=lambda x: x.name)
            ],
            'enums': [
                asdict(enum) for enum in sorted(self.enums, key=lambda x: x.name)
            ],
            'macros': [
                asdict(macro) for macro in sorted(self.macros, key=lambda x: x.name)
            ],
            'typedefs': [
                asdict(td)
                for td in sorted(
                    self.typedefs,
                    key=lambda x: x.name or f'{x.location.file}:{x.location.line}',
                )
            ],
            'structs': [
                asdict(st)
                for st in sorted(
                    self.structs,
                    key=lambda x: x.name or f'{x.location.file}:{x.location.line}',
                )
            ],
            'unions': [
                asdict(un)
                for un in sorted(
                    self.unions,
                    key=lambda x: x.name or f'{x.location.file}:{x.location.line}',
                )
            ],
            'tokens': {
                'from_enums': sorted(
                    {
                        constant.name
                        for enum in self.enums
                        for constant in enum.constants
                        if constant.name.isupper()
                    }
                ),
                'from_macros': sorted(
                    {macro.name for macro in self.macros if macro.name.isupper()}
                ),
            },
            'option_occurrences': self.option_occurrences,
            'errors': self.errors,
        }

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))

    @classmethod
    def create(cls, args: argparse.Namespace) -> Self:
        if args.clang:
            Config.set_library_file(args.clang)

        src_dir: Path = args.src.resolve()

        return cls(
            src_dir,
            [
                '-I.',
                f'-I{src_dir}',
                f'-I{src_dir.parent}',
                '-std=c99',
                '-DZSH_VERSION="5.9"',
            ],
            args.zsh_version,
            args.verbose,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description='Extract raw zsh source metadata')
    parser.add_argument(
        '--src', type=Path, default=DEFAULT_SRC, help='Path to zsh Source dir'
    )
    parser.add_argument(
        '--out', type=Path, default=DEFAULT_OUT, help='Output JSON file'
    )
    parser.add_argument(
        '--clang',
        type=str,
        default=os.environ.get('LIBCLANG_PATH'),
        help='Path to libclang',
    )
    parser.add_argument('--zsh-version', type=str, default='5.9', dest='zsh_version')
    parser.add_argument('--verbose', action='store_true')

    args = parser.parse_args()

    # Prioritize core files first
    c_files = [
        'lex.c',
        'parse.c',
        'subst.c',
        'params.c',
        'cond.c',
        'string.c',
        'text.c',
        'glob.c',
        'prompt.c',
        'hist.c',
        'math.c',
        'options.c',
        'pattern.c',
        'zsh.h',
    ]

    extractor = ZshParser.create(args)

    for file in c_files:
        extractor.parse(file)

    # Save JSON
    extractor.save_extraction(args.out.resolve())

    if extractor.verbose:
        print('Wrote', args.out)
