from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Self, TypedDict, cast, override

from jsonschema import validate

from zsh_grammar.common import GRAMMAR_SCHEMA_PATH

if TYPE_CHECKING:
    from _typeshed import StrPath

    from zsh_grammar._types import (
        Condition,
        EmptyDict,
        GrammarDict,
        LanguageDict,
        LanguagesDict,
        OptionalDict,
        RepeatDict,
        RuleDict,
        RuleRefDict,
        SequenceDict,
        SourceDict,
        TerminalDict,
        TokenDict,
        TokenMatchDict,
        TokenRefDict,
        UnionDict,
        VariantDict,
        _WithMetadataDict,
    )


@dataclass(slots=True)
class Source:
    file: str
    line: int | tuple[int, int]
    function: str | None = None
    context: str | None = None

    def to_json(self) -> SourceDict:
        source: SourceDict = {
            'file': self.file,
            'line': self.line,
        }

        if self.function is not None:
            source['function'] = self.function

        if self.context is not None:
            source['context'] = self.context

        return source

    @classmethod
    def from_json(cls, data: SourceDict) -> Self:
        return cls(
            file=data['file'],
            line=data['line']
            if isinstance(data['line'], int)
            else cast('tuple[int, int]', tuple(data['line'][0:2])),
            function=data.get('function'),
            context=data.get('context'),
        )


class _FromJsonWithMetadataDict(TypedDict):
    description: str | None
    source: Source | None


@dataclass(slots=True, kw_only=True)
class _WithMetadata:
    description: str | None = None
    source: Source | None = None

    def to_json(self) -> _WithMetadataDict:
        data: _WithMetadataDict = {}

        if self.description is not None:
            data['description'] = self.description

        if self.source is not None:
            data['source'] = self.source.to_json()

        return data

    @staticmethod
    def _from_json(
        data: _WithMetadataDict,
    ) -> _FromJsonWithMetadataDict:
        return {
            'description': data.get('description'),
            'source': Source.from_json(data['source']) if 'source' in data else None,
        }


@dataclass(slots=True)
class Empty(_WithMetadata):
    @override
    def to_json(self) -> EmptyDict:
        return {'empty': True, **super().to_json()}

    @classmethod
    def from_json(cls, data: EmptyDict) -> Self:
        return cls(**cls._from_json(data))


@dataclass(slots=True)
class Optional(_WithMetadata):
    rule: Rule

    @override
    def to_json(self) -> OptionalDict:
        return {'optional': self.rule.to_json(), **super().to_json()}

    @classmethod
    def from_json(cls, data: OptionalDict) -> Self:
        return cls(_from_rule(data['optional']), **cls._from_json(data))


@dataclass(slots=True)
class Variant(_WithMetadata):
    rule: Rule
    condition: Condition

    @override
    def to_json(self) -> VariantDict:
        return {
            'variant': self.rule.to_json(),
            'condition': self.condition,
            **super().to_json(),
        }

    @classmethod
    def from_json(cls, data: VariantDict) -> Self:
        return cls(
            _from_rule(data['variant']), data['condition'], **cls._from_json(data)
        )


@dataclass(slots=True)
class Terminal(_WithMetadata):
    pattern: str

    @override
    def to_json(self) -> TerminalDict:
        return {'pattern': self.pattern, **super().to_json()}

    @classmethod
    def from_json(cls, data: TerminalDict) -> Self:
        return cls(data['pattern'], **cls._from_json(data))


@dataclass(slots=True)
class Union(_WithMetadata):
    rules: list[Rule]

    @override
    def to_json(self) -> UnionDict:
        return {
            'union': [rule.to_json() for rule in self.rules],
            **super().to_json(),
        }

    @classmethod
    def from_json(cls, data: UnionDict) -> Self:
        return cls([_from_rule(rule) for rule in data['union']], **cls._from_json(data))


@dataclass(slots=True)
class Sequence(_WithMetadata):
    rules: list[Rule]

    @override
    def to_json(self) -> SequenceDict:
        return {
            'sequence': [rule.to_json() for rule in self.rules],
            **super().to_json(),
        }

    @classmethod
    def from_json(cls, data: SequenceDict) -> Self:
        return cls(
            [_from_rule(rule) for rule in data['sequence']], **cls._from_json(data)
        )


@dataclass(slots=True)
class Repeat(_WithMetadata):
    rule: Rule
    min: int = 1
    max: int | None = None

    @override
    def to_json(self) -> RepeatDict:
        repeat: RepeatDict = {
            'repeat': self.rule.to_json(),
            'min': self.min,
            **super().to_json(),
        }

        if self.max is not None:
            repeat['max'] = self.max

        return repeat

    @classmethod
    def from_json(cls, data: RepeatDict) -> Self:
        return cls(
            _from_rule(data['repeat']),
            min=data.get('min') or 0,
            max=data.get('max'),
            **cls._from_json(data),
        )


@dataclass(slots=True)
class RuleReference(_WithMetadata):
    rule: str
    lang: str | None = None

    @override
    def to_json(self) -> RuleRefDict:
        ref: RuleRefDict = {'$rule': self.rule, **super().to_json()}

        if self.lang is not None:
            ref['$lang'] = self.lang

        return ref

    @classmethod
    def from_json(cls, data: RuleRefDict) -> Self:
        return cls(
            data['$rule'],
            lang=data.get('$lang'),
            **cls._from_json(data),
        )


@dataclass(slots=True)
class TokenReference(_WithMetadata):
    token: str

    @override
    def to_json(self) -> TokenRefDict:
        return {'$token': self.token, **super().to_json()}

    @classmethod
    def from_json(cls, data: TokenRefDict) -> Self:
        return cls(
            data['$token'],
            **cls._from_json(data),
        )


type Reference = RuleReference | TokenReference


type Rule = (
    Empty | Optional | Reference | Repeat | Sequence | Terminal | Union | Variant
)


def _from_rule(data: RuleDict, /) -> Rule:
    rule: Rule

    match data:
        case {'empty': True}:
            rule = Empty.from_json(data)
        case {'optional': _}:
            rule = Optional.from_json(data)
        case {'$rule': _}:
            rule = RuleReference.from_json(data)
        case {'$token': _}:
            rule = TokenReference.from_json(data)
        case {'repeat': _}:
            rule = Repeat.from_json(data)
        case {'sequence': _}:
            rule = Sequence.from_json(data)
        case {'pattern': _}:
            rule = Terminal.from_json(data)
        case {'union': _}:
            rule = Union.from_json(data)
        case {'variant': _}:
            rule = Variant.from_json(data)
        case _:
            raise ValueError(f'Invalid rule data: {data}')

    return rule


@dataclass(slots=True)
class TokenMatch(_WithMetadata):
    matches: str | list[str]

    @override
    def to_json(self) -> TokenMatchDict:
        return {'matches': self.matches, **super().to_json()}

    @classmethod
    def from_json(cls, data: TokenMatchDict) -> Self:
        return cls(
            data['matches'],
            **cls._from_json(data),
        )


type Token = Terminal | TokenMatch


def _from_token(data: TokenDict, /) -> Token:
    match data:
        case {'matches': _}:
            return TokenMatch.from_json(data)
        case {'pattern': _}:
            return Terminal.from_json(data)
        case _:
            raise ValueError(f'Invalid token data: {data}')


@dataclass(slots=True)
class Language:
    tokens: dict[str, Token]
    rules: dict[str, Rule]

    def to_json(self) -> LanguageDict:
        return {
            'tokens': {key: token.to_json() for key, token in self.tokens.items()},
            'rules': {key: rule.to_json() for key, rule in self.rules.items()},
        }

    @classmethod
    def from_json(cls, data: LanguageDict) -> Self:
        return cls(
            tokens={key: _from_token(token) for key, token in data['tokens'].items()},
            rules={key: _from_rule(rule) for key, rule in data['rules'].items()},
        )


@dataclass(slots=True)
class Grammar:
    languages: dict[str, Language]
    version: str | None = None
    zsh_version: str | None = None
    zsh_revision: str | None = None
    generated_at: datetime | None = None

    def to_json(self) -> GrammarDict:
        grammar: GrammarDict = {
            'languages': cast(
                'LanguagesDict',
                {key: lang.to_json() for key, lang in self.languages.items()},
            ),
        }

        if self.version is not None:
            grammar['version'] = self.version

        if self.zsh_version is not None:
            grammar['zsh_version'] = self.zsh_version

        if self.zsh_revision is not None:
            grammar['zsh_revision'] = self.zsh_revision

        if self.generated_at is not None:
            grammar['generated_at'] = self.generated_at.isoformat()

        return grammar

    @classmethod
    def from_json(cls, data: GrammarDict) -> Self:
        generated_at = data.get('generated_at')
        return cls(
            languages={
                key: Language.from_json(lang) for key, lang in data['languages'].items()
            },
            version=data.get('version'),
            zsh_version=data.get('zsh_version'),
            zsh_revision=data.get('zsh_revision'),
            generated_at=datetime.fromisoformat(generated_at) if generated_at else None,
        )

    @classmethod
    def load(cls, path: StrPath, /) -> Self:
        path = Path(path)
        grammar_data = json.loads(path.read_text())
        schema = json.loads(GRAMMAR_SCHEMA_PATH.read_text(encoding='utf-8'))

        validate(grammar_data, schema)

        return cls.from_json(grammar_data)
