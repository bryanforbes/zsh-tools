"""Comprehensive unit tests for zsh_grammar.grammar module.

Tests all classes and functions: Source, _WithMetadata, Rule types, Token types,
Language, and Grammar with JSON serialization/deserialization, validation, and
edge cases.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from zsh_grammar.grammar import (
    Empty,
    Grammar,
    Language,
    Optional,
    Repeat,
    RuleReference,
    Sequence,
    Source,
    Terminal,
    TokenMatch,
    TokenReference,
    Union,
    Variant,
    _from_rule,
    _from_token,
)

if TYPE_CHECKING:
    from zsh_grammar._types import (
        Condition,
        EmptyDict,
        GrammarDict,
        LanguageDict,
        OptionalDict,
        RepeatDict,
        RuleRefDict,
        SequenceDict,
        SourceDict,
        TerminalDict,
        TokenMatchDict,
        TokenRefDict,
        UnionDict,
        VariantDict,
    )


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_source() -> Source:
    """Create a sample Source object."""
    return Source(
        file='Src/parse.c',
        line=42,
        function='tokenize',
        context='in token extraction',
    )


@pytest.fixture
def sample_source_dict() -> SourceDict:
    """Create a sample source dictionary."""
    return {
        'file': 'Src/parse.c',
        'line': 42,
        'function': 'tokenize',
        'context': 'in token extraction',
    }


@pytest.fixture
def sample_source_line_range() -> Source:
    """Create a Source with line range."""
    return Source(
        file='Doc/Zsh/grammar.yo',
        line=(10, 20),
    )


@pytest.fixture
def sample_terminal() -> Terminal:
    """Create a sample Terminal rule."""
    return Terminal(
        pattern=r'\w+',
        description='A word character sequence',
        source=Source(file='parse.c', line=1),
    )


@pytest.fixture
def sample_empty() -> Empty:
    """Create a sample Empty rule."""
    return Empty(
        description='No rule',
        source=Source(file='parse.c', line=2),
    )


@pytest.fixture
def sample_optional() -> Optional:
    """Create a sample Optional rule."""
    return Optional(
        rule=Terminal(pattern=r'\w+'),
        description='Optional word',
    )


@pytest.fixture
def sample_repeat() -> Repeat:
    """Create a sample Repeat rule."""
    return Repeat(
        rule=Terminal(pattern=r'\w+'),
        min=1,
        max=5,
        description='One to five words',
    )


@pytest.fixture
def sample_sequence() -> Sequence:
    """Create a sample Sequence rule."""
    return Sequence(
        rules=[
            Terminal(pattern=r'for'),
            Terminal(pattern=r'\w+'),
        ],
        description='For loop start',
    )


@pytest.fixture
def sample_union() -> Union:
    """Create a sample Union rule."""
    return Union(
        rules=[
            Terminal(pattern=r'if'),
            Terminal(pattern=r'case'),
        ],
        description='Conditional statement',
    )


@pytest.fixture
def sample_rule_reference() -> RuleReference:
    """Create a sample RuleReference."""
    return RuleReference(
        rule='for_loop',
        lang='zsh',
        description='Reference to for_loop rule',
    )


@pytest.fixture
def sample_token_reference() -> TokenReference:
    """Create a sample TokenReference."""
    return TokenReference(
        token='FOR',  # noqa: S106
        description='Reference to FOR token',
    )


@pytest.fixture
def sample_variant() -> Variant:
    """Create a sample Variant rule."""
    return Variant(
        rule=Terminal(pattern=r'\w+'),
        condition={'option': 'zsh'},
        description='Zsh variant',
    )


@pytest.fixture
def sample_token_match() -> TokenMatch:
    """Create a sample TokenMatch."""
    return TokenMatch(
        matches='for',
        description='Reserved word "for"',
    )


@pytest.fixture
def sample_token_match_multiple() -> TokenMatch:
    """Create a TokenMatch with multiple matches."""
    return TokenMatch(
        matches=['if', 'then', 'else'],
        description='Conditional keywords',
    )


@pytest.fixture
def sample_language() -> Language:
    """Create a sample Language."""
    return Language(
        tokens={
            'FOR': TokenMatch(matches='for'),
            'DO': TokenMatch(matches='do'),
            'WORD': Terminal(pattern=r'\w+'),
        },
        rules={
            'for_loop': RuleReference(rule='simple_command'),
            'word': Terminal(pattern=r'\w+'),
        },
    )


@pytest.fixture
def sample_grammar() -> Grammar:
    """Create a sample Grammar."""
    return Grammar(
        languages={
            'core': Language(
                tokens={
                    'FOR': TokenMatch(matches='for'),
                    'IF': TokenMatch(matches='if'),
                },
                rules={
                    'for_loop': RuleReference(rule='simple_command'),
                    'if_statement': RuleReference(rule='simple_command'),
                },
            ),
        },
        version='0.1.0',
        zsh_version='5.9',
        zsh_revision='abc123',
        generated_at=datetime(2025, 11, 22, 12, 0, 0),
    )


# ============================================================================
# Tests for Source
# ============================================================================


class TestSource:
    """Tests for Source dataclass."""

    def test_source_creation(self, sample_source: Source) -> None:
        """Test Source object creation."""
        assert sample_source.file == 'Src/parse.c'
        assert sample_source.line == 42
        assert sample_source.function == 'tokenize'
        assert sample_source.context == 'in token extraction'

    def test_source_to_json_full(self, sample_source: Source) -> None:
        """Test Source serialization with all fields."""
        result = sample_source.to_json()
        assert result['file'] == 'Src/parse.c'
        assert result['line'] == 42
        assert result.get('function') == 'tokenize'
        assert result.get('context') == 'in token extraction'

    def test_source_to_json_minimal(self) -> None:
        """Test Source serialization with minimal fields."""
        source = Source(file='test.c', line=1)
        result = source.to_json()
        assert result == {'file': 'test.c', 'line': 1}
        assert 'function' not in result
        assert 'context' not in result

    def test_source_to_json_with_line_range(
        self, sample_source_line_range: Source
    ) -> None:
        """Test Source serialization with line range."""
        result = sample_source_line_range.to_json()
        assert result['line'] == (10, 20)

    def test_source_from_json_full(self, sample_source_dict: SourceDict) -> None:
        """Test Source deserialization with all fields."""
        source = Source.from_json(sample_source_dict)
        assert source.file == 'Src/parse.c'
        assert source.line == 42
        assert source.function == 'tokenize'
        assert source.context == 'in token extraction'

    def test_source_from_json_minimal(self) -> None:
        """Test Source deserialization with minimal fields."""
        data: SourceDict = {'file': 'test.c', 'line': 5}
        source = Source.from_json(data)
        assert source.file == 'test.c'
        assert source.line == 5
        assert source.function is None
        assert source.context is None

    def test_source_from_json_with_line_range(self) -> None:
        """Test Source deserialization with line range."""
        data: SourceDict = {'file': 'test.c', 'line': (10, 20)}
        source = Source.from_json(data)
        assert source.line == (10, 20)
        assert isinstance(source.line, tuple)

    def test_source_roundtrip(self, sample_source: Source) -> None:
        """Test Source serialization/deserialization roundtrip."""
        json_data = sample_source.to_json()
        restored = Source.from_json(json_data)
        assert restored == sample_source

    def test_source_with_none_fields(self) -> None:
        """Test Source with None optional fields."""
        source = Source(
            file='test.c',
            line=1,
            function=None,
            context=None,
        )
        json_data = source.to_json()
        assert 'function' not in json_data
        assert 'context' not in json_data


# ============================================================================
# Tests for Terminal
# ============================================================================


class TestTerminal:
    """Tests for Terminal rule."""

    def test_terminal_creation(self, sample_terminal: Terminal) -> None:
        """Test Terminal creation."""
        assert sample_terminal.pattern == r'\w+'
        assert sample_terminal.description == 'A word character sequence'

    def test_terminal_to_json(self, sample_terminal: Terminal) -> None:
        """Test Terminal serialization."""
        result = sample_terminal.to_json()
        assert result['pattern'] == r'\w+'
        assert result.get('description') == 'A word character sequence'
        assert 'source' in result

    def test_terminal_from_json(self) -> None:
        """Test Terminal deserialization."""
        data: TerminalDict = {'pattern': r'\d+'}
        terminal = Terminal.from_json(data)
        assert terminal.pattern == r'\d+'
        assert terminal.description is None
        assert terminal.source is None

    def test_terminal_roundtrip(self, sample_terminal: Terminal) -> None:
        """Test Terminal serialization/deserialization roundtrip."""
        json_data = sample_terminal.to_json()
        restored = Terminal.from_json(json_data)
        assert restored.pattern == sample_terminal.pattern
        assert restored.description == sample_terminal.description


# ============================================================================
# Tests for Empty
# ============================================================================


class TestEmpty:
    """Tests for Empty rule."""

    def test_empty_creation(self, sample_empty: Empty) -> None:
        """Test Empty creation."""
        assert sample_empty.description == 'No rule'

    def test_empty_to_json(self, sample_empty: Empty) -> None:
        """Test Empty serialization."""
        result = sample_empty.to_json()
        assert result['empty'] is True
        assert result.get('description') == 'No rule'

    def test_empty_from_json(self) -> None:
        """Test Empty deserialization."""
        data: EmptyDict = {'empty': True}
        empty = Empty.from_json(data)
        assert empty.description is None
        assert empty.source is None

    def test_empty_roundtrip(self, sample_empty: Empty) -> None:
        """Test Empty serialization/deserialization roundtrip."""
        json_data = sample_empty.to_json()
        restored = Empty.from_json(json_data)
        assert restored.description == sample_empty.description


# ============================================================================
# Tests for Optional
# ============================================================================


class TestOptional:
    """Tests for Optional rule."""

    def test_optional_creation(self, sample_optional: Optional) -> None:
        """Test Optional creation."""
        assert isinstance(sample_optional.rule, Terminal)
        assert sample_optional.rule.pattern == r'\w+'

    def test_optional_to_json(self, sample_optional: Optional) -> None:
        """Test Optional serialization."""
        result = sample_optional.to_json()
        assert 'optional' in result
        assert 'pattern' in result['optional']
        assert result['optional']['pattern'] == r'\w+'
        assert result.get('description') == 'Optional word'

    def test_optional_from_json(self) -> None:
        """Test Optional deserialization."""
        data: OptionalDict = {
            'optional': {'pattern': r'\d+'},
        }
        optional = Optional.from_json(data)
        assert isinstance(optional.rule, Terminal)
        assert optional.rule.pattern == r'\d+'

    def test_optional_roundtrip(self, sample_optional: Optional) -> None:
        """Test Optional serialization/deserialization roundtrip."""
        json_data = sample_optional.to_json()
        restored = Optional.from_json(json_data)
        assert isinstance(sample_optional.rule, Terminal)
        assert isinstance(restored.rule, Terminal)
        assert restored.rule.pattern == sample_optional.rule.pattern


# ============================================================================
# Tests for Repeat
# ============================================================================


class TestRepeat:
    """Tests for Repeat rule."""

    def test_repeat_creation(self, sample_repeat: Repeat) -> None:
        """Test Repeat creation."""
        assert isinstance(sample_repeat.rule, Terminal)
        assert sample_repeat.min == 1
        assert sample_repeat.max == 5

    def test_repeat_to_json(self, sample_repeat: Repeat) -> None:
        """Test Repeat serialization."""
        result = sample_repeat.to_json()
        assert 'repeat' in result
        assert 'pattern' in result['repeat']
        assert result['repeat']['pattern'] == r'\w+'
        assert result.get('min') == 1
        assert result.get('max') == 5

    def test_repeat_to_json_no_bounds(self) -> None:
        """Test Repeat serialization without bounds."""
        repeat = Repeat(rule=Terminal(pattern=r'\w+'))
        result = repeat.to_json()
        assert 'repeat' in result
        assert 'min' in result
        assert 'max' not in result

    def test_repeat_from_json(self) -> None:
        """Test Repeat deserialization."""
        data: RepeatDict = {
            'repeat': {'pattern': r'\d+'},
            'min': 0,
            'max': 10,
        }
        repeat = Repeat.from_json(data)
        assert isinstance(repeat.rule, Terminal)
        assert repeat.min == 0
        assert repeat.max == 10

    def test_repeat_roundtrip(self, sample_repeat: Repeat) -> None:
        """Test Repeat serialization/deserialization roundtrip."""
        json_data = sample_repeat.to_json()
        restored = Repeat.from_json(json_data)
        assert isinstance(restored.rule, Terminal)
        assert restored.min == sample_repeat.min
        assert restored.max == sample_repeat.max


# ============================================================================
# Tests for Sequence
# ============================================================================


class TestSequence:
    """Tests for Sequence rule."""

    def test_sequence_creation(self, sample_sequence: Sequence) -> None:
        """Test Sequence creation."""
        assert len(sample_sequence.rules) == 2
        assert all(isinstance(r, Terminal) for r in sample_sequence.rules)

    def test_sequence_to_json(self, sample_sequence: Sequence) -> None:
        """Test Sequence serialization."""
        result = sample_sequence.to_json()
        assert 'sequence' in result
        assert len(result['sequence']) == 2
        item_1 = result['sequence'][0]
        item_2 = result['sequence'][1]
        assert 'pattern' in item_1
        assert 'pattern' in item_2
        assert item_1['pattern'] == r'for'
        assert item_2['pattern'] == r'\w+'

    def test_sequence_from_json(self) -> None:
        """Test Sequence deserialization."""
        data: SequenceDict = {
            'sequence': [
                {'pattern': r'if'},
                {'pattern': r'then'},
            ],
        }
        sequence = Sequence.from_json(data)
        assert len(sequence.rules) == 2

    def test_sequence_roundtrip(self, sample_sequence: Sequence) -> None:
        """Test Sequence serialization/deserialization roundtrip."""
        json_data = sample_sequence.to_json()
        restored = Sequence.from_json(json_data)
        assert len(restored.rules) == len(sample_sequence.rules)


# ============================================================================
# Tests for Union
# ============================================================================


class TestUnion:
    """Tests for Union rule."""

    def test_union_creation(self, sample_union: Union) -> None:
        """Test Union creation."""
        assert len(sample_union.rules) == 2
        assert all(isinstance(r, Terminal) for r in sample_union.rules)

    def test_union_to_json(self, sample_union: Union) -> None:
        """Test Union serialization."""
        result = sample_union.to_json()
        assert 'union' in result
        assert len(result['union']) == 2

    def test_union_from_json(self) -> None:
        """Test Union deserialization."""
        data: UnionDict = {
            'union': [
                {'pattern': r'for'},
                {'pattern': r'while'},
            ],
        }
        union = Union.from_json(data)
        assert len(union.rules) == 2

    def test_union_roundtrip(self, sample_union: Union) -> None:
        """Test Union serialization/deserialization roundtrip."""
        json_data = sample_union.to_json()
        restored = Union.from_json(json_data)
        assert len(restored.rules) == len(sample_union.rules)


# ============================================================================
# Tests for RuleReference
# ============================================================================


class TestRuleReference:
    """Tests for RuleReference."""

    def test_rule_reference_creation(
        self, sample_rule_reference: RuleReference
    ) -> None:
        """Test RuleReference creation."""
        assert sample_rule_reference.rule == 'for_loop'
        assert sample_rule_reference.lang == 'zsh'

    def test_rule_reference_to_json(self, sample_rule_reference: RuleReference) -> None:
        """Test RuleReference serialization."""
        result = sample_rule_reference.to_json()
        assert result['$rule'] == 'for_loop'
        assert result.get('$lang') == 'zsh'

    def test_rule_reference_to_json_no_lang(self) -> None:
        """Test RuleReference serialization without lang."""
        ref = RuleReference(rule='simple_command')
        result = ref.to_json()
        assert result['$rule'] == 'simple_command'
        assert '$lang' not in result

    def test_rule_reference_from_json(self) -> None:
        """Test RuleReference deserialization."""
        data: RuleRefDict = {'$rule': 'for_loop', '$lang': 'zsh'}
        ref = RuleReference.from_json(data)
        assert ref.rule == 'for_loop'
        assert ref.lang == 'zsh'

    def test_rule_reference_roundtrip(
        self, sample_rule_reference: RuleReference
    ) -> None:
        """Test RuleReference serialization/deserialization roundtrip."""
        json_data = sample_rule_reference.to_json()
        restored = RuleReference.from_json(json_data)
        assert restored.rule == sample_rule_reference.rule
        assert restored.lang == sample_rule_reference.lang


# ============================================================================
# Tests for TokenReference
# ============================================================================


class TestTokenReference:
    """Tests for TokenReference."""

    def test_token_reference_creation(
        self, sample_token_reference: TokenReference
    ) -> None:
        """Test TokenReference creation."""
        assert sample_token_reference.token == 'FOR'  # noqa: S105

    def test_token_reference_to_json(
        self, sample_token_reference: TokenReference
    ) -> None:
        """Test TokenReference serialization."""
        result = sample_token_reference.to_json()
        assert result['$token'] == 'FOR'

    def test_token_reference_from_json(self) -> None:
        """Test TokenReference deserialization."""
        data: TokenRefDict = {'$token': 'IF'}
        ref = TokenReference.from_json(data)
        assert ref.token == 'IF'  # noqa: S105

    def test_token_reference_roundtrip(
        self, sample_token_reference: TokenReference
    ) -> None:
        """Test TokenReference serialization/deserialization roundtrip."""
        json_data = sample_token_reference.to_json()
        restored = TokenReference.from_json(json_data)
        assert restored.token == sample_token_reference.token


# ============================================================================
# Tests for Variant
# ============================================================================


class TestVariant:
    """Tests for Variant rule."""

    def test_variant_creation(self, sample_variant: Variant) -> None:
        """Test Variant creation."""
        assert isinstance(sample_variant.rule, Terminal)
        assert sample_variant.condition == {'option': 'zsh'}

    def test_variant_to_json(self, sample_variant: Variant) -> None:
        """Test Variant serialization."""
        result = sample_variant.to_json()
        assert 'variant' in result
        assert result['condition'] == {'option': 'zsh'}

    def test_variant_from_json(self) -> None:
        """Test Variant deserialization."""
        data: VariantDict = {
            'variant': {'pattern': r'\w+'},
            'condition': {'option': 'zsh'},
        }
        variant = Variant.from_json(data)
        assert isinstance(variant.rule, Terminal)
        assert variant.condition == {'option': 'zsh'}

    def test_variant_roundtrip(self, sample_variant: Variant) -> None:
        """Test Variant serialization/deserialization roundtrip."""
        json_data = sample_variant.to_json()
        restored = Variant.from_json(json_data)
        assert restored.condition == sample_variant.condition


# ============================================================================
# Tests for TokenMatch
# ============================================================================


class TestTokenMatch:
    """Tests for TokenMatch."""

    def test_token_match_creation(self, sample_token_match: TokenMatch) -> None:
        """Test TokenMatch creation."""
        assert sample_token_match.matches == 'for'

    def test_token_match_creation_multiple(
        self, sample_token_match_multiple: TokenMatch
    ) -> None:
        """Test TokenMatch with multiple matches."""
        assert sample_token_match_multiple.matches == ['if', 'then', 'else']

    def test_token_match_to_json(self, sample_token_match: TokenMatch) -> None:
        """Test TokenMatch serialization."""
        result = sample_token_match.to_json()
        assert result['matches'] == 'for'
        assert result.get('description') == 'Reserved word "for"'

    def test_token_match_to_json_multiple(
        self, sample_token_match_multiple: TokenMatch
    ) -> None:
        """Test TokenMatch serialization with multiple matches."""
        result = sample_token_match_multiple.to_json()
        assert result['matches'] == ['if', 'then', 'else']

    def test_token_match_from_json(self) -> None:
        """Test TokenMatch deserialization."""
        data: TokenMatchDict = {'matches': 'while'}
        match = TokenMatch.from_json(data)
        assert match.matches == 'while'

    def test_token_match_from_json_multiple(self) -> None:
        """Test TokenMatch deserialization with multiple matches."""
        data: TokenMatchDict = {'matches': ['a', 'b', 'c']}
        match = TokenMatch.from_json(data)
        assert match.matches == ['a', 'b', 'c']

    def test_token_match_roundtrip(self, sample_token_match: TokenMatch) -> None:
        """Test TokenMatch serialization/deserialization roundtrip."""
        json_data = sample_token_match.to_json()
        restored = TokenMatch.from_json(json_data)
        assert restored.matches == sample_token_match.matches


# ============================================================================
# Tests for _from_rule helper function
# ============================================================================


class TestFromRuleHelper:
    """Tests for _from_rule factory function."""

    def test_from_rule_empty(self) -> None:
        """Test _from_rule creates Empty."""
        data: EmptyDict = {'empty': True}
        rule = _from_rule(data)
        assert isinstance(rule, Empty)

    def test_from_rule_optional(self) -> None:
        """Test _from_rule creates Optional."""
        data: OptionalDict = {'optional': {'pattern': r'\w+'}}
        rule = _from_rule(data)
        assert isinstance(rule, Optional)

    def test_from_rule_terminal(self) -> None:
        """Test _from_rule creates Terminal."""
        data: TerminalDict = {'pattern': r'\d+'}
        rule = _from_rule(data)
        assert isinstance(rule, Terminal)

    def test_from_rule_rule_reference(self) -> None:
        """Test _from_rule creates RuleReference."""
        data: RuleRefDict = {'$rule': 'for_loop'}
        rule = _from_rule(data)
        assert isinstance(rule, RuleReference)

    def test_from_rule_token_reference(self) -> None:
        """Test _from_rule creates TokenReference."""
        data: TokenRefDict = {'$token': 'FOR'}
        rule = _from_rule(data)
        assert isinstance(rule, TokenReference)

    def test_from_rule_repeat(self) -> None:
        """Test _from_rule creates Repeat."""
        data: RepeatDict = {'repeat': {'pattern': r'\w+'}}
        rule = _from_rule(data)
        assert isinstance(rule, Repeat)

    def test_from_rule_sequence(self) -> None:
        """Test _from_rule creates Sequence."""
        data: SequenceDict = {'sequence': [{'pattern': r'if'}, {'pattern': r'then'}]}
        rule = _from_rule(data)
        assert isinstance(rule, Sequence)

    def test_from_rule_union(self) -> None:
        """Test _from_rule creates Union."""
        data: UnionDict = {'union': [{'pattern': r'if'}, {'pattern': r'case'}]}
        rule = _from_rule(data)
        assert isinstance(rule, Union)

    def test_from_rule_variant(self) -> None:
        """Test _from_rule creates Variant."""
        data: VariantDict = {
            'variant': {'pattern': r'\w+'},
            'condition': {'option': 'zsh'},
        }
        rule = _from_rule(data)
        assert isinstance(rule, Variant)

    def test_from_rule_invalid(self) -> None:
        """Test _from_rule raises ValueError for invalid data."""
        with pytest.raises(ValueError, match='Invalid rule data'):
            _from_rule({'invalid': True})  # pyright: ignore[reportArgumentType]


# ============================================================================
# Tests for _from_token helper function
# ============================================================================


class TestFromTokenHelper:
    """Tests for _from_token factory function."""

    def test_from_token_terminal(self) -> None:
        """Test _from_token creates Terminal."""
        token = _from_token({'pattern': r'\d+'})
        assert isinstance(token, Terminal)

    def test_from_token_match(self) -> None:
        """Test _from_token creates TokenMatch."""
        token = _from_token({'matches': 'for'})
        assert isinstance(token, TokenMatch)

    def test_from_token_match_multiple(self) -> None:
        """Test _from_token creates TokenMatch with multiple matches."""
        token = _from_token({'matches': ['a', 'b']})
        assert isinstance(token, TokenMatch)

    def test_from_token_invalid(self) -> None:
        """Test _from_token raises ValueError for invalid data."""
        with pytest.raises(ValueError, match='Invalid token data'):
            _from_token({'invalid': True})  # pyright: ignore[reportArgumentType]


# ============================================================================
# Tests for Language
# ============================================================================


class TestLanguage:
    """Tests for Language class."""

    def test_language_creation(self, sample_language: Language) -> None:
        """Test Language creation."""
        assert len(sample_language.tokens) == 3
        assert len(sample_language.rules) == 2

    def test_language_to_json(self, sample_language: Language) -> None:
        """Test Language serialization."""
        result = sample_language.to_json()
        assert 'tokens' in result
        assert 'rules' in result
        assert 'FOR' in result['tokens']
        assert 'for_loop' in result['rules']

    def test_language_from_json(self) -> None:
        """Test Language deserialization."""
        data: LanguageDict = {
            'tokens': {
                'FOR': {'matches': 'for'},
                'WORD': {'pattern': r'\w+'},
            },
            'rules': {
                'for_loop': {'$rule': 'simple_command'},
            },
        }
        lang = Language.from_json(data)
        assert len(lang.tokens) == 2
        assert len(lang.rules) == 1

    def test_language_roundtrip(self, sample_language: Language) -> None:
        """Test Language serialization/deserialization roundtrip."""
        json_data = sample_language.to_json()
        restored = Language.from_json(json_data)
        assert len(restored.tokens) == len(sample_language.tokens)
        assert len(restored.rules) == len(sample_language.rules)


# ============================================================================
# Tests for Grammar
# ============================================================================


class TestGrammar:
    """Tests for Grammar class."""

    def test_grammar_creation(self, sample_grammar: Grammar) -> None:
        """Test Grammar creation."""
        assert len(sample_grammar.languages) == 1
        assert 'core' in sample_grammar.languages
        assert sample_grammar.version == '0.1.0'
        assert sample_grammar.zsh_version == '5.9'

    def test_grammar_to_json(self, sample_grammar: Grammar) -> None:
        """Test Grammar serialization."""
        result = sample_grammar.to_json()
        assert 'languages' in result
        assert result.get('version') == '0.1.0'
        assert result.get('zsh_version') == '5.9'
        assert result.get('zsh_revision') == 'abc123'
        assert 'generated_at' in result

    def test_grammar_to_json_minimal(self) -> None:
        """Test Grammar serialization with minimal fields."""
        grammar = Grammar(
            languages={
                'core': Language(tokens={}, rules={}),
            },
        )
        result = grammar.to_json()
        assert 'languages' in result
        assert 'version' not in result
        assert 'zsh_version' not in result
        assert 'generated_at' not in result

    def test_grammar_from_json(self) -> None:
        """Test Grammar deserialization."""
        grammar = Grammar.from_json(
            {
                'languages': {
                    'core': {
                        'tokens': {'FOR': {'matches': 'for'}},
                        'rules': {'for_loop': {'$rule': 'simple_command'}},
                    },
                },
                'version': '1.0.0',
                'zsh_version': '5.8',
                'generated_at': '2025-11-22T12:00:00',
            }
        )
        assert len(grammar.languages) == 1
        assert grammar.version == '1.0.0'
        assert isinstance(grammar.generated_at, datetime)

    def test_grammar_roundtrip(self, sample_grammar: Grammar) -> None:
        """Test Grammar serialization/deserialization roundtrip."""
        json_data = sample_grammar.to_json()
        restored = Grammar.from_json(json_data)
        assert len(restored.languages) == len(sample_grammar.languages)
        assert restored.version == sample_grammar.version
        assert restored.zsh_version == sample_grammar.zsh_version

    def test_grammar_load_from_file(self, sample_grammar: Grammar) -> None:
        """Test Grammar loading from file with validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'test_grammar.json'
            json_data = sample_grammar.to_json()
            filepath.write_text(json.dumps(json_data))

            # Load and verify
            loaded = Grammar.load(filepath)
            assert loaded.version == sample_grammar.version
            assert loaded.zsh_version == sample_grammar.zsh_version

    def test_grammar_load_minimal_grammar(self) -> None:
        """Test loading a minimal valid grammar."""
        minimal_data: GrammarDict = {
            'languages': {
                'core': {
                    'tokens': {'WORD': {'pattern': r'\w+'}},
                    'rules': {'word': {'pattern': r'\w+'}},
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'minimal.json'
            filepath.write_text(json.dumps(minimal_data))

            grammar = Grammar.load(filepath)
            assert len(grammar.languages) == 1
            assert 'core' in grammar.languages
            assert grammar.version is None
            assert len(grammar.languages['core'].tokens) == 1
            assert len(grammar.languages['core'].rules) == 1

    def test_grammar_load_with_all_fields(self) -> None:
        """Test loading grammar with all optional fields."""
        full_data = {
            'languages': {
                'core': {
                    'tokens': {'FOR': {'matches': 'for'}},
                    'rules': {'for_loop': {'$rule': 'simple_command'}},
                },
            },
            'version': '1.0.0',
            'zsh_version': '5.9',
            'zsh_revision': 'abcd1234',
            'generated_at': '2025-11-22T12:00:00',
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'full.json'
            filepath.write_text(json.dumps(full_data))

            grammar = Grammar.load(filepath)
            assert grammar.version == '1.0.0'
            assert grammar.zsh_version == '5.9'
            assert grammar.zsh_revision == 'abcd1234'
            assert grammar.generated_at == datetime(2025, 11, 22, 12, 0, 0)

    def test_grammar_load_invalid_json(self) -> None:
        """Test loading invalid JSON raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'invalid.json'
            filepath.write_text('{ invalid json }')

            with pytest.raises(json.JSONDecodeError):
                Grammar.load(filepath)

    def test_grammar_load_nonexistent_file(self) -> None:
        """Test loading from nonexistent file raises error."""
        filepath = Path('/nonexistent/path/grammar.json')
        with pytest.raises(FileNotFoundError):
            Grammar.load(filepath)

    def test_grammar_load_with_multiple_languages(self) -> None:
        """Test loading grammar with multiple language variants."""
        multi_lang_data = {
            'languages': {
                'core': {
                    'tokens': {'FOR': {'matches': 'for'}},
                    'rules': {'for_loop': {'$rule': 'simple_command'}},
                },
                'bash': {
                    'tokens': {'FOR': {'matches': 'for'}},
                    'rules': {'for_loop': {'$rule': 'simple_command'}},
                },
            },
            'version': '2.0.0',
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'multilang.json'
            filepath.write_text(json.dumps(multi_lang_data))

            grammar = Grammar.load(filepath)
            assert len(grammar.languages) == 2
            assert 'core' in grammar.languages
            assert 'bash' in grammar.languages

    def test_grammar_load_large_grammar(self) -> None:
        """Test loading a large grammar file."""
        # Create a grammar with many rules
        large_rules = {f'rule_{i}': {'$rule': 'simple_command'} for i in range(100)}
        large_tokens = {f'TOKEN_{i}': {'matches': f'word{i}'} for i in range(50)}

        large_data = {
            'languages': {
                'core': {
                    'tokens': large_tokens,
                    'rules': large_rules,
                },
            },
            'version': '1.0.0',
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'large.json'
            filepath.write_text(json.dumps(large_data))

            grammar = Grammar.load(filepath)
            assert len(grammar.languages['core'].rules) == 100
            assert len(grammar.languages['core'].tokens) == 50

    def test_grammar_load_preserves_metadata(self) -> None:
        """Test that load preserves descriptions and source info."""
        data_with_metadata = {
            'languages': {
                'core': {
                    'tokens': {
                        'FOR': {
                            'matches': 'for',
                            'description': 'For loop keyword',
                            'source': {
                                'file': 'Src/parse.c',
                                'line': 100,
                            },
                        },
                    },
                    'rules': {
                        'for_loop': {
                            '$rule': 'simple_command',
                            'description': 'For loop rule',
                            'source': {
                                'file': 'Doc/Zsh/grammar.yo',
                                'line': 50,
                            },
                        },
                    },
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'metadata.json'
            filepath.write_text(json.dumps(data_with_metadata))

            grammar = Grammar.load(filepath)
            # Tokens preserve metadata
            assert grammar.languages['core'].tokens['FOR'].description == (
                'For loop keyword'
            )
            assert grammar.languages['core'].tokens['FOR'].source is not None
            assert grammar.languages['core'].tokens['FOR'].source.file == 'Src/parse.c'
            assert grammar.languages['core'].tokens['FOR'].source.line == 100
            # Rules preserve metadata
            assert grammar.languages['core'].rules['for_loop'].description == (
                'For loop rule'
            )
            assert grammar.languages['core'].rules['for_loop'].source is not None
            assert grammar.languages['core'].rules['for_loop'].source.file == (
                'Doc/Zsh/grammar.yo'
            )
            assert grammar.languages['core'].rules['for_loop'].source.line == 50

    def test_grammar_datetime_iso_format(self) -> None:
        """Test Grammar datetime serialization in ISO format."""
        dt = datetime(2025, 11, 22, 15, 30, 45)
        grammar = Grammar(
            languages={'core': Language(tokens={}, rules={})},
            generated_at=dt,
        )
        result = grammar.to_json()
        assert result.get('generated_at') == '2025-11-22T15:30:45'

    def test_grammar_datetime_iso_parse(self) -> None:
        """Test Grammar datetime deserialization from ISO format."""
        grammar = Grammar.from_json(
            {
                'languages': {
                    'core': {'tokens': {}, 'rules': {}},
                },
                'generated_at': '2025-11-22T15:30:45',
            }
        )
        assert grammar.generated_at == datetime(2025, 11, 22, 15, 30, 45)


# ============================================================================
# Integration Tests
# ============================================================================


class TestComplexGrammarStructure:
    """Tests for complex nested grammar structures."""

    def test_nested_rules(self) -> None:
        """Test grammar with deeply nested rule structures."""
        grammar = Grammar(
            languages={
                'core': Language(
                    tokens={'FOR': TokenMatch(matches='for')},
                    rules={
                        'for_loop': Union(
                            rules=[
                                Sequence(
                                    rules=[
                                        RuleReference(rule='simple_command'),
                                        TokenReference(token='FOR'),  # noqa: S106
                                    ],
                                ),
                                Optional(rule=Repeat(rule=Terminal(pattern=r'\w+'))),
                            ],
                        ),
                    },
                ),
            },
        )

        json_data = grammar.to_json()
        restored = Grammar.from_json(json_data)
        assert restored.languages['core'].rules['for_loop'] is not None

    def test_multiple_languages(self) -> None:
        """Test grammar with multiple languages."""
        grammar = Grammar(
            languages={
                'core': Language(
                    tokens={'FOR': TokenMatch(matches='for')},
                    rules={'for_loop': RuleReference(rule='simple_command')},
                ),
                'bash': Language(
                    tokens={'FOR': TokenMatch(matches='for')},
                    rules={'for_loop': RuleReference(rule='simple_command')},
                ),
            },
        )

        json_data = grammar.to_json()
        restored = Grammar.from_json(json_data)
        assert len(restored.languages) == 2
        assert 'bash' in restored.languages

    def test_mixed_rule_types(self) -> None:
        """Test grammar with mixed rule types in sequence."""
        grammar = Grammar(
            languages={
                'core': Language(
                    tokens={'FOR': TokenMatch(matches='for')},
                    rules={
                        'mixed': Sequence(
                            rules=[
                                Empty(),
                                Terminal(pattern=r'test'),
                                RuleReference(rule='nested'),
                                TokenReference(token='FOR'),  # noqa: S106
                                Variant(
                                    rule=Optional(rule=Terminal(pattern=r'\w+')),
                                    condition={'option': 'zsh'},
                                ),
                            ],
                        ),
                    },
                ),
            },
        )

        json_data = grammar.to_json()
        restored = Grammar.from_json(json_data)
        mixed_rule = restored.languages['core'].rules['mixed']
        assert isinstance(mixed_rule, Sequence)
        assert len(mixed_rule.rules) == 5


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_grammar(self) -> None:
        """Test grammar with no languages."""
        grammar = Grammar(languages={})
        result = grammar.to_json()
        assert result['languages'] == {}

    def test_empty_language(self) -> None:
        """Test language with no tokens or rules."""
        lang = Language(tokens={}, rules={})
        result = lang.to_json()
        assert result['tokens'] == {}
        assert result['rules'] == {}

    def test_special_characters_in_pattern(self) -> None:
        """Test patterns with special regex characters."""
        terminal = Terminal(pattern=r'[\w\-\.]+')
        json_data = terminal.to_json()
        restored = Terminal.from_json(json_data)
        assert restored.pattern == r'[\w\-\.]+'

    def test_empty_description(self) -> None:
        """Test handling empty string descriptions."""
        terminal = Terminal(pattern=r'\w+', description='')
        json_data = terminal.to_json()
        assert json_data.get('description') == ''

    def test_long_description(self) -> None:
        """Test handling long descriptions."""
        long_desc = 'x' * 1000
        terminal = Terminal(pattern=r'\w+', description=long_desc)
        json_data = terminal.to_json()
        restored = Terminal.from_json(json_data)
        assert restored.description == long_desc

    def test_repeat_with_only_min(self) -> None:
        """Test Repeat with only min bound."""
        repeat = Repeat(rule=Terminal(pattern=r'\w+'), min=1)
        json_data = repeat.to_json()
        assert 'min' in json_data
        assert 'max' not in json_data

    def test_repeat_with_only_max(self) -> None:
        """Test Repeat with only max bound."""
        repeat = Repeat(rule=Terminal(pattern=r'\w+'), max=10)
        json_data = repeat.to_json()
        assert 'max' in json_data
        assert 'min' in json_data

    def test_large_grammar(self) -> None:
        """Test handling large grammar with many rules."""
        lang = Language(
            tokens={},
            rules={
                f'rule_{i}': RuleReference(rule=f'rule_{i + 1}') for i in range(100)
            },
        )
        json_data = lang.to_json()
        restored = Language.from_json(json_data)
        assert len(restored.rules) == 100

    def test_unicode_in_description(self) -> None:
        """Test handling unicode in descriptions and source context."""
        source = Source(
            file='test.c',
            line=1,
            context='Testing unicode: 你好世界 🚀',
        )
        json_data = source.to_json()
        restored = Source.from_json(json_data)
        assert restored.context == 'Testing unicode: 你好世界 🚀'

    def test_variant_with_all_conditions(self) -> None:
        """Test variants with different condition values."""
        conditions: list[Condition] = [
            {'option': 'zsh'},
            {'option': 'bash'},
            {'option': 'sh'},
            {'option': 'ksh'},
            {'option': 'interactive'},
        ]
        for cond in conditions:
            variant = Variant(
                rule=Terminal(pattern=r'\w+'),
                condition=cond,
            )
            json_data = variant.to_json()
            restored = Variant.from_json(json_data)
            assert restored.condition == cond


# ============================================================================
# Validation Tests
# ============================================================================


class TestValidation:
    """Tests for data validation during loading."""

    def test_datetime_parsing_with_z_suffix(self) -> None:
        """Test datetime parsing with Z suffix."""
        grammar = Grammar.from_json(
            {
                'languages': {'core': {'tokens': {}, 'rules': {}}},
                'generated_at': '2025-11-22T15:30:45Z',
            }
        )
        assert grammar.generated_at is not None
        assert grammar.generated_at.year == 2025

    def test_datetime_parsing_without_suffix(self) -> None:
        """Test datetime parsing without timezone suffix."""
        grammar = Grammar.from_json(
            {
                'languages': {'core': {'tokens': {}, 'rules': {}}},
                'generated_at': '2025-11-22T15:30:45',
            }
        )
        assert grammar.generated_at is not None

    def test_source_line_range_truncation(self) -> None:
        """Test source line range with extra values (only first 2 used)."""
        source = Source.from_json({'file': 'test.c', 'line': (10, 20, 30)})  # pyright: ignore[reportArgumentType]
        assert isinstance(source.line, tuple)
        assert len(source.line) == 2
        assert source.line == (10, 20)
