from __future__ import annotations

from typing import NotRequired, TypedDict


class Optional(TypedDict):
    optional: GrammarNode


NotCondition = TypedDict('NotCondition', {'not': 'Condition'})
AndCondition = TypedDict('AndCondition', {'and': 'list[Condition]'})
OrCondition = TypedDict('OrCondition', {'or': 'list[Condition]'})

type Condition = str | NotCondition | AndCondition | OrCondition


class Variant(TypedDict):
    variant: GrammarNode
    condition: Condition


class TerminalPattern(TypedDict):
    pattern: str


type Terminal = str | TerminalPattern


class Union(TypedDict):
    union: list[GrammarNode]


class Sequence(TypedDict):
    sequence: list[GrammarNode]


class RepeatNone(TypedDict):
    repeat: GrammarNode


class RepeatOne(TypedDict):
    repeat1: GrammarNode


type Repeat = RepeatNone | RepeatOne


Ref = TypedDict('Ref', {'$ref': str})


type GrammarNode = Optional | Ref | Repeat | Sequence | Terminal | Union | Variant
type Language = dict[str, GrammarNode]


class Languages(TypedDict, extra_items=Language):
    core: Language


class Grammar(TypedDict, extra_items=str):
    languages: Languages
    version: NotRequired[str]
    zsh_version: NotRequired[str]
    zsh_revision: NotRequired[str]
