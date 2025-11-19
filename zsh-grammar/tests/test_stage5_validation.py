"""Tests for Stage 5: Semantic Grammar Validation & Comparison.

This test suite validates:
1. Semantic grammar extraction from parse.c
2. Rule comparison logic
3. Validation report generation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zsh_grammar.rule_comparison import (
    ComparisonResult,
    RuleComparator,
    compare_extracted_against_semantic,
)
from zsh_grammar.semantic_grammar_extractor import (
    SemanticGrammarExtractor,
    extract_semantic_grammar_from_parse_c,
)
from zsh_grammar.validation_reporter import (
    generate_detailed_comparison_report,
    generate_validation_report,
    print_summary_table,
)

if TYPE_CHECKING:
    from pathlib import Path

    from zsh_grammar._types import GrammarNode


class TestSemanticGrammarExtraction:
    """Test semantic grammar extraction from parse.c."""

    def test_extractor_initialization(self, parse_c_path: Path) -> None:
        """Test extractor can be initialized with parse.c."""
        extractor = SemanticGrammarExtractor(parse_c_path)
        assert extractor.parse_c_path == parse_c_path
        assert len(extractor.lines) > 0

    def test_extract_all_rules(self, parse_c_path: Path) -> None:
        """Test extracting all semantic grammar rules."""
        extractor = SemanticGrammarExtractor(parse_c_path)
        rules = extractor.extract_all_rules()

        # Should extract at least some rules
        assert len(rules) > 0

        # Each rule should have required fields
        for func_name, rule in rules.items():
            assert 'function' in rule
            assert 'rule' in rule
            assert 'source_line' in rule
            assert 'source_file' in rule
            assert rule['function'] == func_name
            assert rule['source_line'] > 0

    def test_extract_par_subsh_grammar(self, parse_c_path: Path) -> None:
        """Test extracting par_subsh semantic grammar."""
        extractor = SemanticGrammarExtractor(parse_c_path)
        rules = extractor.extract_all_rules()

        assert 'par_subsh' in rules
        rule = rules['par_subsh']

        # Should contain expected tokens
        assert 'INPAR' in rule['rule']
        assert 'OUTPAR' in rule['rule']
        assert 'INBRACE' in rule['rule']
        assert 'OUTBRACE' in rule['rule']

        # Should have pipe separator (alternatives)
        assert '|' in rule['rule']

    def test_extract_par_if_grammar(self, parse_c_path: Path) -> None:
        """Test extracting par_if semantic grammar."""
        extractor = SemanticGrammarExtractor(parse_c_path)
        rules = extractor.extract_all_rules()

        if 'par_if' in rules:
            rule = rules['par_if']
            # Should mention if/then/else tokens or rules
            rule_lower = rule['rule'].lower()
            assert any(x in rule_lower for x in ['then', 'else', 'fi'])

    def test_extract_par_for_grammar(self, parse_c_path: Path) -> None:
        """Test extracting par_for semantic grammar."""
        extractor = SemanticGrammarExtractor(parse_c_path)
        rules = extractor.extract_all_rules()

        if 'par_for' in rules:
            rule = rules['par_for']
            # Should mention for/do/done or similar
            rule_lower = rule['rule'].lower()
            assert any(x in rule_lower for x in ['for', 'do', 'done', 'word'])


class TestRuleComparison:
    """Test rule comparison logic."""

    def test_comparator_initialization(self) -> None:
        """Test comparator can be initialized."""
        comparator = RuleComparator()
        assert comparator is not None

    def test_extract_tokens_from_string(self) -> None:
        """Test token extraction from semantic grammar string."""
        comparator = RuleComparator()

        grammar = 'INPAR list OUTPAR | INBRACE list OUTBRACE'
        tokens = comparator._extract_tokens_from_string(grammar)

        expected = {'INPAR', 'OUTPAR', 'INBRACE', 'OUTBRACE'}
        assert tokens == expected

    def test_extract_rule_refs_from_string(self) -> None:
        """Test rule reference extraction from string."""
        comparator = RuleComparator()

        grammar = 'INPAR list OUTPAR | INBRACE list OUTBRACE'
        rules = comparator._extract_rule_refs_from_string(grammar)

        assert 'list' in rules

    def test_extract_tokens_from_grammar_node(self) -> None:
        """Test token extraction from grammar node."""
        comparator = RuleComparator()

        node: GrammarNode = {
            'union': [
                {
                    'sequence': [
                        {'$ref': 'INPAR'},
                        {'$ref': 'list'},
                        {'$ref': 'OUTPAR'},
                    ]
                },
            ]
        }

        tokens = comparator._extract_tokens_from_grammar_node(node)

        expected = {'INPAR', 'OUTPAR'}
        assert tokens == expected

    def test_extract_rule_refs_from_grammar_node(self) -> None:
        """Test rule reference extraction from grammar node."""
        comparator = RuleComparator()

        node: GrammarNode = {
            'union': [
                {
                    'sequence': [
                        {'$ref': 'INPAR'},
                        {'$ref': 'list'},
                        {'$ref': 'OUTPAR'},
                    ]
                },
            ]
        }

        rules = comparator._extract_rule_refs_from_grammar_node(node)

        assert 'list' in rules

    def test_compare_perfect_match(self) -> None:
        """Test comparison of perfect matching rules."""
        comparator = RuleComparator()

        extracted: GrammarNode = {
            'union': [
                {
                    'sequence': [
                        {'$ref': 'INPAR'},
                        {'$ref': 'list'},
                        {'$ref': 'OUTPAR'},
                    ]
                },
            ]
        }

        semantic = 'INPAR list OUTPAR'

        result = comparator.compare_rules(extracted, semantic)

        assert result['token_match_score'] == 1.0
        assert result['missing_tokens'] == []
        assert result['extra_tokens'] == []

    def test_compare_partial_match(self) -> None:
        """Test comparison of partially matching rules."""
        comparator = RuleComparator()

        extracted: GrammarNode = {
            'union': [
                {
                    'sequence': [
                        {'$ref': 'INPAR'},
                        {'$ref': 'list'},
                        {'$ref': 'OUTPAR'},
                    ]
                },
            ]
        }

        semantic = 'INPAR list OUTPAR | INBRACE list OUTBRACE'

        result = comparator.compare_rules(extracted, semantic)

        # Missing the second alternative
        assert result['token_match_score'] < 1.0
        assert 'INBRACE' in result['missing_tokens']
        assert 'OUTBRACE' in result['missing_tokens']

    def test_compare_with_extra_tokens(self) -> None:
        """Test comparison when extracted has extra tokens."""
        comparator = RuleComparator()

        extracted: GrammarNode = {
            'union': [
                {
                    'sequence': [
                        {'$ref': 'INPAR'},
                        {'$ref': 'list'},
                        {'$ref': 'OUTPAR'},
                        {'$ref': 'EXTRA'},
                    ]
                },
            ]
        }

        semantic = 'INPAR list OUTPAR'

        result = comparator.compare_rules(extracted, semantic)

        assert 'EXTRA' in result['extra_tokens']
        assert result['token_match_score'] < 1.0


class TestValidationReporter:
    """Test validation report generation."""

    def test_generate_empty_report(self) -> None:
        """Test generating report with no comparisons."""
        semantic: dict[str, str] = {}
        comparisons: dict[str, ComparisonResult | None] = {}

        report = generate_validation_report(semantic, comparisons)

        assert 'Validation Report' in report
        assert 'No comparisons available' in report

    def test_generate_summary_report(self) -> None:
        """Test generating summary report."""
        semantic = {
            'par_subsh': 'INPAR list OUTPAR | INBRACE list OUTBRACE',
        }

        comparison: ComparisonResult = {
            'token_match_score': 1.0,
            'rule_match_score': 1.0,
            'structure_match': True,
            'missing_tokens': [],
            'extra_tokens': [],
            'missing_rules': [],
            'extra_rules': [],
            'notes': 'Perfect match.',
        }

        comparisons: dict[str, ComparisonResult | None] = {
            'par_subsh': comparison,
        }

        report = generate_validation_report(semantic, comparisons)

        assert 'Summary' in report
        assert 'Average token match' in report
        assert 'Average rule match' in report
        assert '✅ Perfect Matches' in report
        assert 'par_subsh' in report

    def test_generate_detailed_report(self) -> None:
        """Test generating detailed per-function report."""
        semantic = {
            'par_subsh': 'INPAR list OUTPAR | INBRACE list OUTBRACE',
        }

        comparison: ComparisonResult = {
            'token_match_score': 0.75,
            'rule_match_score': 0.8,
            'structure_match': True,
            'missing_tokens': ['INBRACE'],
            'extra_tokens': [],
            'missing_rules': [],
            'extra_rules': [],
            'notes': 'Missing INBRACE token.',
        }

        comparisons: dict[str, ComparisonResult | None] = {
            'par_subsh': comparison,
        }

        report = generate_detailed_comparison_report(semantic, comparisons)

        assert 'par_subsh' in report
        assert 'Semantic Grammar' in report
        assert 'Token Match' in report
        assert 'Missing Tokens' in report
        assert 'INBRACE' in report

    def test_generate_summary_table(self) -> None:
        """Test generating summary table."""
        comparison: ComparisonResult = {
            'token_match_score': 0.9,
            'rule_match_score': 0.85,
            'structure_match': True,
            'missing_tokens': ['EXTRA'],
            'extra_tokens': [],
            'missing_rules': [],
            'extra_rules': [],
            'notes': 'Mostly good.',
        }

        comparisons: dict[str, ComparisonResult | None] = {
            'par_subsh': comparison,
        }

        table = print_summary_table(comparisons)

        assert '|' in table  # Markdown table
        assert 'par_subsh' in table
        assert '90%' in table or '0.9' in table


class TestIntegration:
    """Integration tests for Stage 5."""

    def test_extract_and_compare_workflow(self, parse_c_path: Path) -> None:
        """Test full workflow: extract semantic grammar and compare."""
        # Extract semantic grammar
        semantic_rules = extract_semantic_grammar_from_parse_c(parse_c_path)

        # Create mock extracted rules
        extracted_rules: dict[str, GrammarNode] = {
            'par_subsh': {
                'union': [
                    {
                        'sequence': [
                            {'$ref': 'INPAR'},
                            {'$ref': 'list'},
                            {'$ref': 'OUTPAR'},
                        ]
                    },
                ]
            }
        }

        # Filter semantic rules to only those with extractions
        semantic_for_comparison = {
            k: v['rule'] for k, v in semantic_rules.items() if k in extracted_rules
        }

        # Compare
        comparisons = compare_extracted_against_semantic(
            extracted_rules, semantic_for_comparison
        )

        assert len(comparisons) > 0

        # Generate report
        report = generate_validation_report(semantic_for_comparison, comparisons)
        assert 'Summary' in report

    def test_full_validation_pipeline(self, parse_c_path: Path) -> None:
        """Test complete Stage 5 pipeline."""
        # Stage 5.1: Extract semantic grammar
        semantic_rules = extract_semantic_grammar_from_parse_c(parse_c_path)
        assert len(semantic_rules) > 0

        # Create sample extracted rules for testing
        extracted: dict[str, GrammarNode] = {k: {'$ref': k} for k in semantic_rules}

        semantic_for_comparison = {k: v['rule'] for k, v in semantic_rules.items()}

        # Stage 5.2: Compare
        comparisons = compare_extracted_against_semantic(
            extracted, semantic_for_comparison
        )
        assert len(comparisons) == len(semantic_rules)

        # Stage 5.3: Generate reports
        summary_report = generate_validation_report(
            semantic_for_comparison, comparisons
        )
        assert 'Summary' in summary_report

        detailed_report = generate_detailed_comparison_report(
            semantic_for_comparison, comparisons
        )
        assert len(detailed_report) > 0

        table = print_summary_table(comparisons)
        assert '|' in table
