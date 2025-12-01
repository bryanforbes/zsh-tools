from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

if TYPE_CHECKING:
    from collections.abc import Iterable

    from zsh_grammar._types import (
        AndConditionDict,
        Condition,
        EmptyDict,
        LexState,
        LexStateConditionDict,
        NotConditionDict,
        OptionalDict,
        OptionConditionDict,
        OrConditionDict,
        ParseFlag,
        ParseFlagConditionDict,
        RepeatDict,
        RuleDict,
        RuleRefDict,
        SequenceDict,
        SourceDict,
        TokenMatchDict,
        TokenPatternDict,
        TokenRefDict,
        UnionDict,
        VariantDict,
        VersionConditionDict,
        _WithMetadataDict,
    )


def _annotate_node[N: _WithMetadataDict](
    node: N, /, **kwargs: Unpack[_WithMetadataDict]
) -> N:
    if 'description' in kwargs:
        node['description'] = kwargs['description']
    if 'source' in kwargs:
        node['source'] = kwargs['source']

    return node


def create_source(
    file: str, line: int, /, *, function: str | None = None, context: str | None = None
) -> SourceDict:
    source: SourceDict = {'file': file, 'line': line}

    if function is not None:
        source['function'] = function
    if context is not None:
        source['context'] = context

    return source


def create_empty(**kwargs: Unpack[_WithMetadataDict]) -> EmptyDict:
    return _annotate_node({'empty': True}, **kwargs)


def create_token(
    matches: str | Iterable[str], /, **kwargs: Unpack[_WithMetadataDict]
) -> TokenMatchDict:
    return _annotate_node(
        {
            'matches': matches if isinstance(matches, str) else list(matches),
        },
        **kwargs,
    )


def create_optional(
    rule: RuleDict, /, **kwargs: Unpack[_WithMetadataDict]
) -> OptionalDict:
    return _annotate_node({'optional': rule}, **kwargs)


def create_option(option: str, /) -> OptionConditionDict:
    return {'option': option}


def create_parse_flag(parse_flag: ParseFlag, /) -> ParseFlagConditionDict:
    return {'parseflag': parse_flag}


def create_lex_state(lex_state: LexState, /) -> LexStateConditionDict:
    return {'lexstate': lex_state}


def create_version(
    *, since: str | None = None, until: str | None = None
) -> VersionConditionDict:
    if since is None and until is None:
        raise ValueError('Either since or until must be specified')

    version: VersionConditionDict = {}

    if since is not None:
        version['sinceVersion'] = since

    if until is not None:
        version['untilVersion'] = until

    return version


def create_not(condition: Condition, /) -> NotConditionDict:
    return {'not': condition}


def create_and(conditions: Iterable[Condition], /) -> AndConditionDict:
    return {'and': list(conditions)}


def create_or(conditions: Iterable[Condition], /) -> OrConditionDict:
    return {'or': list(conditions)}


def create_variant(
    rule: RuleDict, condition: Condition, /, **kwargs: Unpack[_WithMetadataDict]
) -> VariantDict:
    return _annotate_node({'variant': rule, 'condition': condition}, **kwargs)


def create_terminal(
    pattern: str, /, **kwargs: Unpack[_WithMetadataDict]
) -> TokenPatternDict:
    return _annotate_node({'pattern': pattern}, **kwargs)


def create_union(
    union: Iterable[RuleDict], /, **kwargs: Unpack[_WithMetadataDict]
) -> UnionDict:
    return _annotate_node({'union': list(union)}, **kwargs)


def create_sequence(
    sequence: Iterable[RuleDict], /, **kwargs: Unpack[_WithMetadataDict]
) -> SequenceDict:
    return _annotate_node({'sequence': list(sequence)}, **kwargs)


def create_repeat(
    rule: RuleDict,
    /,
    *,
    min: int | None = None,
    max: int | None = None,
    **kwargs: Unpack[_WithMetadataDict],
) -> RepeatDict:
    if min is not None and max is not None and min > max:
        raise ValueError(f'min ({min}) cannot be greater than max ({max})')

    repeat: RepeatDict = {'repeat': rule}

    if min is not None:
        repeat['min'] = min

    if max is not None:
        repeat['max'] = max

    return _annotate_node(repeat, **kwargs)


def create_rule_ref(ref: str, /, **kwargs: Unpack[_WithMetadataDict]) -> RuleRefDict:
    return _annotate_node({'$rule': ref}, **kwargs)


def create_token_ref(ref: str, /, **kwargs: Unpack[_WithMetadataDict]) -> TokenRefDict:
    return _annotate_node({'$token': ref}, **kwargs)
