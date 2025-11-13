from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from zsh_grammar._types import (
        AndCondition,
        Condition,
        GrammarNode,
        NotCondition,
        Optional,
        OrCondition,
        Ref,
        RepeatNone,
        RepeatOne,
        Sequence,
        TerminalPattern,
        Union,
        Variant,
    )


def create_optional(node: GrammarNode, /) -> Optional:
    return {'optional': node}


def create_not(condition: Condition, /) -> NotCondition:
    return {'not': condition}


def create_and(conditions: Iterable[Condition], /) -> AndCondition:
    return {'and': list(conditions)}


def create_or(conditions: Iterable[Condition], /) -> OrCondition:
    return {'or': list(conditions)}


def create_variant(node: GrammarNode, condition: Condition, /) -> Variant:
    return {'variant': node, 'condition': condition}


def create_terminal_pattern(pattern: str, /) -> TerminalPattern:
    return {'pattern': pattern}


def create_union(union: Iterable[GrammarNode], /) -> Union:
    return {'union': list(union)}


def create_sequence(sequence: Iterable[GrammarNode], /) -> Sequence:
    return {'sequence': list(sequence)}


def create_repeat(node: GrammarNode, /, *, one: bool = False) -> RepeatNone | RepeatOne:
    if one:
        return {'repeat1': node}
    return {'repeat': node}


def create_ref(ref: str, /) -> Ref:
    return {'$ref': ref}
