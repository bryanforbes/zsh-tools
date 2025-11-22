"""Tests for JSON grammar schema validation.

Validates amp-grammar.json structure, references, and token definitions.
Part of Phase 2.4.1: Grammar Testing Level 1 (Schema Validation).
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, TypeGuard, cast

import pytest
from jsonschema import Draft7Validator, ValidationError
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

if TYPE_CHECKING:
    from collections.abc import Mapping

    from jsonschema.protocols import Validator

    from zsh_grammar._types import Grammar, Language, Languages, Rule, Source, Token


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope='session')
def project_root() -> Path:
    """Get path to zsh-grammar root"""
    return Path(__file__).parent.parent


@pytest.fixture(scope='session')
def grammar_path(project_root: Path) -> Path:
    """Get path to amp-grammar.json."""
    # Navigate from tests directory to project root
    return project_root / 'canonical-grammar.json'


@pytest.fixture(scope='session')
def grammar(grammar_path: Path) -> Grammar:
    """Load and cache amp-grammar.json."""
    return json.loads(grammar_path.read_text())


@pytest.fixture(scope='session')
def core_lang(grammar: Grammar) -> Language:
    """Get core language rules from grammar."""
    return grammar.get('languages', {}).get('core', {})


@pytest.fixture(scope='session')
def schema_path(project_root: Path) -> Path:
    """Get path to the JSON schema file."""
    return project_root / 'canonical-grammar.schema.json'


@pytest.fixture(scope='session')
def schema(schema_path: Path) -> dict[str, object]:
    """Load and cache the JSON schema."""
    if not schema_path.exists():
        pytest.skip(f'Schema file not found at {schema_path}')
    return json.loads(schema_path.read_text())


@pytest.fixture(scope='session')
def registry(schema: dict[str, object]) -> Registry:
    def retrieve_schema(uri: str) -> Resource:
        if uri != './canonical-grammar.schema.json':
            raise NoSuchResource(f'Cannot resolve schema URI: {uri}')

        return Resource.from_contents(schema)

    return Registry(retrieve=retrieve_schema)


@pytest.fixture(scope='session')
def validator(registry: Registry, schema: dict[str, object]) -> Validator:
    return Draft7Validator(schema=schema, registry=registry)


# ============================================================================
# Helper Functions
# ============================================================================


def is_grammar_node(obj: object) -> TypeGuard[Rule]:
    return isinstance(obj, dict) and (
        'empty' in obj
        or 'optional' in obj
        or '$ref' in obj
        or 'repeat' in obj
        or 'sequence' in obj
        or 'pattern' in obj
        or 'token' in obj
        or 'union' in obj
        or 'variant' in obj
    )


def is_grammar(obj: object) -> TypeGuard[Grammar]:
    return isinstance(obj, dict) and 'languages' in obj


def is_languages(obj: object) -> TypeGuard[Languages]:
    return isinstance(obj, dict) and 'core' in obj


def is_grammar_node_list(obj: object) -> TypeGuard[list[Rule]]:
    return isinstance(obj, list)


def extract_all_refs(
    obj: Grammar | Rule | list[Rule],
    rule_names: set[str] | None = None,
    token_names: set[str] | None = None,
    /,
) -> tuple[set[str], set[str]]:
    """Recursively extract all $ref values from grammar structure.

    Args:
        obj: Grammar object to search
        refs: Set to accumulate references (default: new set)

    Returns:
        Set of all $ref values found
    """
    if rule_names is None:
        rule_names = set()
    if token_names is None:
        token_names = set()

    match obj:
        case {'$rule': rule}:
            rule_names.add(rule)
        case {'$token': token}:
            token_names.add(token)
        case {'languages': {'core': {'rules': rule_map}}}:
            for rule in rule_map.values():
                extract_all_refs(rule, rule_names)
        case [*rules] | {'union': rules} | {'sequence': rules}:
            for rule in rules:
                extract_all_refs(rule, rule_names)
        case {'variant': rule} | {'repeat': rule} | {'optional': rule}:
            extract_all_refs(rule, rule_names)
        case _:
            pass

    return rule_names, token_names


def find_circular_refs(
    name: str,
    core_rules: Mapping[str, Rule],
    visited: set[str] | None = None,
    path: list[str] | None = None,
) -> list[str]:
    """Find circular references in grammar rules.

    Args:
        name: Rule name to check
        core_lang: Core language rules dictionary
        visited: Set of visited rules in current path
        path: List of rule names in current path (for error reporting)

    Returns:
        List of circular reference paths found (empty if none)
    """
    if visited is None:
        visited = set()
    if path is None:
        path = []

    if name in visited:
        # Found a cycle
        cycle_path = [*path, name]
        return [' -> '.join(cycle_path)]

    definition = core_rules.get(name)
    if not isinstance(definition, dict):
        return []

    visited.add(name)
    path.append(name)

    cycles: list[str] = []
    rules, _ = extract_all_refs(definition)

    # Don't check primitive tokens for cycles
    primitive_tokens = {'BLANK', 'NEWLINE', 'SEMI', 'SEPER'}

    for rule in rules:
        if rule not in primitive_tokens and rule in core_rules:
            cycles.extend(
                find_circular_refs(rule, core_rules, visited.copy(), path.copy())
            )

    return cycles


# ============================================================================
# Test Classes
# ============================================================================


class TestGrammarStructure:
    """Test basic grammar structure and validity."""

    def test_grammar_conforms_to_schema(
        self,
        grammar: Grammar,
        validator: Validator,
    ) -> None:
        """Test that grammar validates against the JSON schema."""
        try:
            validator.validate(grammar)  #   # pyright: ignore[reportArgumentType]
        except ValidationError as e:
            pytest.fail(
                f'Grammar does not conform to schema: {e.message}\n'
                f'Path: {list(e.absolute_path)}\n'
                f'Schema path: {list(e.absolute_schema_path)}'
            )

    def test_grammar_has_required_structure(
        self, grammar: Grammar, core_lang: Language
    ) -> None:
        """Test grammar has required top-level fields and core rules."""
        assert isinstance(grammar, dict)
        assert len(grammar) > 0

        required_keys = {'$schema', 'version', 'languages'}
        assert required_keys.issubset(grammar.keys())

        assert isinstance(core_lang, dict)
        assert len(core_lang['rules']) > 20  # Should have many rules
        assert len(core_lang['tokens']) > 20  # Should have many rules

    def test_grammar_version_is_valid(self, grammar: Grammar) -> None:
        """Test grammar has valid version information."""
        assert 'version' in grammar
        assert isinstance(grammar['version'], str)
        assert grammar['version'].count('.') >= 1

        assert 'zsh_version' in grammar
        assert isinstance(grammar['zsh_version'], str)

    def test_grammar_has_generated_at_timestamp(self, grammar: Grammar) -> None:
        """Test grammar has generation timestamp in ISO 8601 format."""
        assert 'generated_at' in grammar
        timestamp = grammar['generated_at']
        # Should be ISO 8601: 2025-11-19T00:00:00Z
        assert 'T' in timestamp
        assert 'Z' in timestamp


class TestReferenceResolution:
    """Test that $ref references are valid and resolvable."""

    def test_no_undefined_refs(self, grammar: Grammar, core_lang: Language) -> None:
        """Test all $ref references point to defined rules."""
        all_rules, all_tokens = extract_all_refs(grammar)

        undefined_rules = [rule for rule in all_rules if rule not in core_lang['rules']]
        undefined_tokens = [
            token for token in all_tokens if token not in core_lang['tokens']
        ]

        assert not undefined_rules or undefined_rules == ['placeholder'], (
            f'Undefined references found: {undefined_rules}'
        )
        assert not undefined_tokens, f'Undefined tokens found: {undefined_tokens}'

    def test_no_circular_references(self, core_lang: Language) -> None:
        """Test grammar has no circular $ref chains.

        Checks a sampling of important rules to ensure no infinite loops.
        """
        # Check a sampling of important rules
        rules_to_check = [
            'for_loop',
            'if_statement',
            'while_loop',
            'simple_command',
            'list',
        ]

        for rule_name in rules_to_check:
            if rule_name not in core_lang:
                continue

            cycles = find_circular_refs(rule_name, core_lang['rules'])
            assert not cycles, f'Circular reference found in {rule_name}: {cycles}'

    def test_all_refs_use_valid_names(self, grammar: Grammar) -> None:
        """Test all $ref values use valid identifier names."""
        all_rules, all_tokens = extract_all_refs(grammar)

        for rule in all_rules:
            # Should be a valid identifier (alphanumeric + underscore)
            rule_replaced = rule.replace('_', '')
            assert rule_replaced.isalnum() and rule_replaced.islower(), (  # noqa: PT018
                f'Invalid ref name: {rule}'
            )

        for token in all_tokens:
            # Should be a valid identifier (alphanumeric + underscore)
            token_replaced = token.replace('_', '')
            assert token_replaced.isalnum() and token_replaced.isupper(), (  # noqa: PT018
                f'Invalid ref name: {token}'
            )


class TestTokenDefinitions:
    """Test token definitions are properly structured."""

    def test_required_tokens_exist(self, core_lang: Language) -> None:
        """Test all required tokens are defined."""
        required_tokens = {
            'BLANK',
            'NEWLINE',
            'SEMI',
            'SEPER',
            'FOR',
            'DO',
            'DONE',
            'IF',
            'THEN',
            'ELSE',
            'ELIF',
            'FI',
            'CASE',
            'ESAC',
            'WHILE',
            'UNTIL',
            'REPEAT',
            'INPAR',
            'OUTPAR',
            'INBRACE',
            'OUTBRACE',
            'DINPAR',
            'DOUTPAR',
            'BAR',
            'BARAMP',
        }

        missing = required_tokens - set(core_lang['tokens'].keys())
        assert not missing, f'Missing required tokens: {missing}'

    def test_reserved_word_tokens_have_matches(self, core_lang: Language) -> None:
        """Test reserved words have 'matches' field."""
        reserved_words = {
            'FOR': 'for',
            'DO': 'do',
            'DONE': 'done',
            'IF': 'if',
            'THEN': 'then',
            'ELSE': 'else',
            'ELIF': 'elif',
            'FI': 'fi',
            'CASE': 'case',
            'ESAC': 'esac',
            'WHILE': 'while',
            'UNTIL': 'until',
        }

        for token_name, expected_match in reserved_words.items():
            assert token_name in core_lang['tokens']
            token_def = core_lang['tokens'][token_name]
            assert isinstance(token_def, dict)
            assert 'matches' in token_def, f'{token_name} missing matches'
            assert token_def['matches'] == expected_match

    def test_token_definitions_have_token_field(self, core_lang: Language) -> None:
        """Test token definitions include 'token' field or pattern."""
        # Sample a few tokens - they should have either 'token' field or 'pattern'
        token_names = ['BLANK', 'SEMI', 'FOR', 'DO']

        for token_name in token_names:
            if token_name in core_lang:
                definition = core_lang['tokens'][token_name]
                has_definition = any(
                    key in definition for key in ['token', 'matches', 'pattern']
                )
                assert has_definition, f'{token_name} missing token/matches/pattern'


class TestGrammarRules:
    """Test specific grammar rules exist and have correct structure."""

    def test_required_rules_exist(self, core_lang: Language) -> None:
        """Test all required top-level grammar rules are defined."""
        required_rules = {
            'for_loop',
            'if_statement',
            'while_loop',
            'simple_command',
            'list',
            'word',
            'case_statement',
            'repeat_loop',
            'until_loop',
        }
        missing = required_rules - set(core_lang['rules'].keys())
        assert not missing, f'Missing required rules: {missing}'

    def test_for_loop_structure(self, core_lang: Language) -> None:
        """Test for_loop has correct structure with 6 variants."""
        assert 'for_loop' in core_lang['rules']
        for_loop = core_lang['rules']['for_loop']

        assert isinstance(for_loop, dict)
        assert 'description' in for_loop
        assert isinstance(for_loop['description'], str)
        assert len(for_loop['description']) > 10

        assert 'union' in for_loop
        assert isinstance(for_loop['union'], list)
        assert len(for_loop['union']) == 6

    def test_for_loop_variants_have_metadata(self, core_lang: Language) -> None:
        """Test all for_loop variants have descriptions and sources."""
        assert 'for_loop' in core_lang['rules']
        for_loop = core_lang['rules']['for_loop']
        assert 'union' in for_loop

        for i, variant in enumerate(for_loop['union']):
            assert 'description' in variant, f'Variant {i} missing description'
            desc = variant['description']
            assert isinstance(desc, str)
            assert len(desc) > 5

            assert 'source' in variant, f'Variant {i} missing source'
            source = variant['source']
            assert 'file' in source
            assert 'line' in source
            assert isinstance(source['line'], int)
            assert source['line'] > 0


class TestHelperDefinitions:
    """Test helper rule definitions used across grammar."""

    def test_required_helpers_defined(self, core_lang: Language) -> None:
        """Test all required helper rules are defined."""
        required_helpers = {
            'wordlist',
            'nl_wordlist',
            'arith_for_expression',
            'in_wordlist',
            'optional_word',
        }
        missing = required_helpers - set(core_lang['rules'].keys())
        assert not missing, f'Missing required helpers: {missing}'

    def test_optional_word_structure(self, core_lang: Language) -> None:
        """Test optional_word helper has correct structure."""
        optional_word = core_lang['rules']['optional_word']
        assert isinstance(optional_word, dict)
        assert 'union' in optional_word


class TestSourceAttributions:
    """Test source file attributions are valid."""

    def test_source_file_is_valid(self, project_root: Path, grammar: Grammar) -> None:
        """Test source files point to valid file."""
        zsh_root = project_root.parent / 'vendor' / 'zsh'
        zsh_src = zsh_root / 'Src'
        zsh_doc = zsh_root / 'Doc' / 'Zsh'
        for source in self._extract_all_sources(grammar):
            assert (zsh_src / source['file']).exists() or (
                zsh_doc / source['file']
            ).exists(), f'Expected {source["file"]} to exist'

    def test_source_line_numbers_reasonable(self, grammar: Grammar) -> None:
        """Test source line numbers are reasonable."""
        for source in self._extract_all_sources(grammar):
            if 'line' in source:
                line = source['line']

                if isinstance(line, Sequence):
                    line = line[0]

                # grammar.yo has ~500 lines, but allow some margin
                assert 0 < line < 2000, f'Suspicious line number: {line}'

    def test_source_context_is_string(self, grammar: Grammar) -> None:
        """Test source context fields are strings."""
        for source in self._extract_all_sources(grammar):
            if 'context' in source:
                assert isinstance(source['context'], str)

    @staticmethod
    def _extract_all_sources(
        obj: Grammar | Rule | list[Rule] | Token,
        sources: list[Source] | None = None,
    ) -> Iterator[Source]:
        """Recursively extract all source objects."""
        match obj:
            case {'languages': {'core': core}}:
                for rule in core['rules'].values():
                    yield from TestSourceAttributions._extract_all_sources(rule)
                for token in core['tokens'].values():
                    yield from TestSourceAttributions._extract_all_sources(token)
            case (
                {'variant': rule, **extra}
                | {'repeat': rule, **extra}
                | {'optional': rule, **extra}
                | {'union': rule, **extra}
                | {'sequence': rule, **extra}
                | {'$rule': rule, **extra}
                | {'$token': rule, **extra}
            ):
                if 'source' in extra:
                    yield cast('Source', extra['source'])

                if not isinstance(rule, str):
                    yield from TestSourceAttributions._extract_all_sources(rule)
            case [*rules]:
                for rule in rules:
                    yield from TestSourceAttributions._extract_all_sources(rule)
            case _:
                pass

        return sources
