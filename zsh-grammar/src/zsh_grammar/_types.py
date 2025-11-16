from __future__ import annotations

from typing import Literal, NotRequired
from typing_extensions import TypedDict


class Source(TypedDict):
    file: str
    line: int
    function: NotRequired[str]
    context: NotRequired[str]


class _BaseNode(TypedDict):
    description: NotRequired[str]
    source: NotRequired[Source]


class Empty(_BaseNode):
    empty: Literal[True]


class Token(_BaseNode):
    token: str
    matches: str | list[str]


class Optional(_BaseNode):
    optional: GrammarNode


class OptionCondition(TypedDict):
    option: str


type ParseFlag = Literal[
    'incmdpos',
    'incond',
    'inredir',
    'incasepat',
    'infor',
    'inrepeat',
    'intypeset',
    'isnewlin',
]


class ParseFlagCondition(TypedDict):
    parseflag: ParseFlag


type LexState = Literal[
    'INCMDPOS',
    'INCOND',
    'INREDIR',
    'INCASEPAT',
    'INFOR',
    'INREPEAT',
    'INTYPESET',
    'ISNEWLIN',
    'IN_MATH',
    'ALIASSPACEFLAG',
    'INCOMPARISON',
    'IN_ARRAY',
    'IN_SUBSTITUTION',
    'IN_BRACEEXP',
    'IN_GLOBPAT',
]


class LexStateCondition(TypedDict):
    lexstate: LexState


class VersionCondition(TypedDict):
    sinceVersion: NotRequired[str]
    untilVersion: NotRequired[str]


NotCondition = TypedDict('NotCondition', {'not': 'Condition'})
AndCondition = TypedDict('AndCondition', {'and': 'list[Condition]'})
OrCondition = TypedDict('OrCondition', {'or': 'list[Condition]'})

type Condition = (
    OptionCondition
    | ParseFlagCondition
    | LexStateCondition
    | VersionCondition
    | NotCondition
    | AndCondition
    | OrCondition
)


class Variant(_BaseNode):
    variant: GrammarNode
    condition: Condition


class Terminal(_BaseNode):
    pattern: str


class Union(_BaseNode):
    union: list[GrammarNode]


class Sequence(_BaseNode):
    sequence: list[GrammarNode]


class Repeat(_BaseNode):
    repeat: GrammarNode
    min: NotRequired[int]
    max: NotRequired[int]


_RefBase = TypedDict('_RefBase', {'$ref': str})


class Ref(_BaseNode, _RefBase): ...


type GrammarNode = (
    Empty | Optional | Ref | Repeat | Sequence | Terminal | Token | Union | Variant
)
type Language = dict[str, GrammarNode]


class Languages(TypedDict, extra_items=Language):
    core: Language


class Grammar(TypedDict, extra_items=str):
    languages: Languages
    version: NotRequired[str]
    zsh_version: NotRequired[str]
    zsh_revision: NotRequired[str]
    generated_at: NotRequired[str]
