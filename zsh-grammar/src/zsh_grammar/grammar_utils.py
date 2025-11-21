from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

if TYPE_CHECKING:
    from collections.abc import Iterable

    from zsh_grammar._types import (
        AndCondition,
        Condition,
        Empty,
        LexState,
        LexStateCondition,
        NotCondition,
        Optional,
        OptionCondition,
        OrCondition,
        ParseFlag,
        ParseFlagCondition,
        Repeat,
        Rule,
        RuleRef,
        Sequence,
        Source,
        Terminal,
        Token,
        TokenRef,
        Union,
        Variant,
        VersionCondition,
        _WithMetadata,
    )


def _annotate_node[N: _WithMetadata](node: N, /, **kwargs: Unpack[_WithMetadata]) -> N:
    if 'description' in kwargs:
        node['description'] = kwargs['description']
    if 'source' in kwargs:
        node['source'] = kwargs['source']

    return node


def create_source(
    file: str, line: int, /, *, function: str | None = None, context: str | None = None
) -> Source:
    source: Source = {'file': file, 'line': line}

    if function is not None:
        source['function'] = function
    if context is not None:
        source['context'] = context

    return source


def create_empty(**kwargs: Unpack[_WithMetadata]) -> Empty:
    return _annotate_node({'empty': True}, **kwargs)


def create_token(
    token: str, matches: str | Iterable[str], /, **kwargs: Unpack[_WithMetadata]
) -> Token:
    return _annotate_node(
        {
            'token': token,
            'matches': matches if isinstance(matches, str) else list(matches),
        },
        **kwargs,
    )


def create_optional(rule: Rule, /, **kwargs: Unpack[_WithMetadata]) -> Optional:
    return _annotate_node({'optional': rule}, **kwargs)


def create_option(option: str, /) -> OptionCondition:
    return {'option': option}


def create_parse_flag(parse_flag: ParseFlag, /) -> ParseFlagCondition:
    return {'parseflag': parse_flag}


def create_lex_state(lex_state: LexState, /) -> LexStateCondition:
    return {'lexstate': lex_state}


def create_version(
    *, since: str | None = None, until: str | None = None
) -> VersionCondition:
    if since is None and until is None:
        raise ValueError('Either since or until must be specified')

    version: VersionCondition = {}

    if since is not None:
        version['sinceVersion'] = since

    if until is not None:
        version['untilVersion'] = until

    return version


def create_not(condition: Condition, /) -> NotCondition:
    return {'not': condition}


def create_and(conditions: Iterable[Condition], /) -> AndCondition:
    return {'and': list(conditions)}


def create_or(conditions: Iterable[Condition], /) -> OrCondition:
    return {'or': list(conditions)}


def create_variant(
    rule: Rule, condition: Condition, /, **kwargs: Unpack[_WithMetadata]
) -> Variant:
    return _annotate_node({'variant': rule, 'condition': condition}, **kwargs)


def create_terminal(pattern: str, /, **kwargs: Unpack[_WithMetadata]) -> Terminal:
    return _annotate_node({'pattern': pattern}, **kwargs)


def create_union(union: Iterable[Rule], /, **kwargs: Unpack[_WithMetadata]) -> Union:
    return _annotate_node({'union': list(union)}, **kwargs)


def create_sequence(
    sequence: Iterable[Rule], /, **kwargs: Unpack[_WithMetadata]
) -> Sequence:
    return _annotate_node({'sequence': list(sequence)}, **kwargs)


def create_repeat(
    rule: Rule,
    /,
    *,
    min: int | None = None,
    max: int | None = None,
    **kwargs: Unpack[_WithMetadata],
) -> Repeat:
    if min is not None and max is not None and min > max:
        raise ValueError(f'min ({min}) cannot be greater than max ({max})')

    repeat: Repeat = {'repeat': rule}

    if min is not None:
        repeat['min'] = min

    if max is not None:
        repeat['max'] = max

    return _annotate_node(repeat, **kwargs)


def create_rule_ref(ref: str, /, **kwargs: Unpack[_WithMetadata]) -> RuleRef:
    return _annotate_node({'$rule': ref}, **kwargs)


def create_token_ref(ref: str, /, **kwargs: Unpack[_WithMetadata]) -> TokenRef:
    return _annotate_node({'$token': ref}, **kwargs)
