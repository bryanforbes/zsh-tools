from __future__ import annotations

from typing import Literal, NotRequired
from typing_extensions import TypedDict


class SourceDict(TypedDict):
    file: str
    line: int | tuple[int, int]
    function: NotRequired[str]
    context: NotRequired[str]


class _WithMetadataDict(TypedDict):
    description: NotRequired[str]
    source: NotRequired[SourceDict]


class EmptyDict(_WithMetadataDict):
    empty: Literal[True]


class OptionalDict(_WithMetadataDict):
    optional: RuleDict


class OptionConditionDict(TypedDict):
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


class ParseFlagConditionDict(TypedDict):
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


class LexStateConditionDict(TypedDict):
    lexstate: LexState


class VersionConditionDict(TypedDict):
    sinceVersion: NotRequired[str]
    untilVersion: NotRequired[str]


NotConditionDict = TypedDict('NotConditionDict', {'not': 'Condition'})
AndConditionDict = TypedDict('AndConditionDict', {'and': 'list[Condition]'})
OrConditionDict = TypedDict('OrConditionDict', {'or': 'list[Condition]'})

type Condition = (
    OptionConditionDict
    | ParseFlagConditionDict
    | LexStateConditionDict
    | VersionConditionDict
    | NotConditionDict
    | AndConditionDict
    | OrConditionDict
)


class VariantDict(_WithMetadataDict):
    variant: RuleDict
    condition: Condition


class TerminalDict(_WithMetadataDict):
    pattern: str


class UnionDict(_WithMetadataDict):
    union: list[RuleDict]


class SequenceDict(_WithMetadataDict):
    sequence: list[RuleDict]


class RepeatDict(_WithMetadataDict):
    repeat: RuleDict
    min: NotRequired[int]
    max: NotRequired[int]


_RuleRefBase = TypedDict('_RuleRefBase', {'$rule': str, '$lang': NotRequired[str]})
_TokenRefBase = TypedDict('_TokenRefBase', {'$token': str})


class RuleRefDict(_WithMetadataDict, _RuleRefBase): ...


class TokenRefDict(_WithMetadataDict, _TokenRefBase): ...


type Reference = RuleRefDict | TokenRefDict


type RuleDict = (
    EmptyDict
    | OptionalDict
    | Reference
    | RepeatDict
    | SequenceDict
    | TerminalDict
    | UnionDict
    | VariantDict
)


class TokenMatchDict(_WithMetadataDict):
    matches: str | list[str]


type TokenDict = TerminalDict | TokenMatchDict


class LanguageDict(TypedDict):
    tokens: dict[str, TokenDict]
    rules: dict[str, RuleDict]


class LanguagesDict(TypedDict, extra_items=LanguageDict):
    core: LanguageDict


class GrammarDict(TypedDict, extra_items=str):
    languages: LanguagesDict
    version: NotRequired[str]
    zsh_version: NotRequired[str]
    zsh_revision: NotRequired[str]
    generated_at: NotRequired[str]
