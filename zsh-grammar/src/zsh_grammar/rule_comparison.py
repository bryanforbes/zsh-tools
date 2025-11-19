"""Compare extracted grammar rules against semantic grammar.

Stage 5.2: Validate extracted rules match documented grammar.

This module implements comparison logic between:
1. Semantic grammar: documented grammar from parse.c comments
2. Extracted grammar: grammar rules generated from AST

Metrics:
- Token match: % of documented tokens that appear in extracted rule
- Rule match: % of documented rule references in extracted rule
- Structure match: qualitative assessment of structural similarity
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

    from zsh_grammar._types import GrammarNode


class ComparisonResult(TypedDict):
    """Result of comparing extracted rule against semantic grammar."""

    token_match_score: float  # 0.0-1.0
    rule_match_score: float  # 0.0-1.0
    structure_match: bool
    missing_tokens: list[str]  # Documented but not extracted
    extra_tokens: list[str]  # Extracted but not documented
    missing_rules: list[str]  # Documented but not extracted
    extra_rules: list[str]  # Extracted but not documented
    notes: str  # Explanation of discrepancies


class RuleComparator:
    """Compare extracted rules against semantic grammar."""

    def compare_rules(
        self, extracted_rule: GrammarNode, semantic_grammar_str: str
    ) -> ComparisonResult:
        """Compare extracted rule against semantic grammar.

        Args:
            extracted_rule: Grammar node from rule generation
            semantic_grammar_str: Documented grammar from parse.c

        Returns:
            Comparison metrics and discrepancies.
        """
        expected_tokens = self._extract_tokens_from_string(semantic_grammar_str)
        extracted_tokens = self._extract_tokens_from_grammar_node(extracted_rule)

        expected_rules = self._extract_rule_refs_from_string(semantic_grammar_str)
        extracted_rules = self._extract_rule_refs_from_grammar_node(extracted_rule)

        # Compute overlap
        token_overlap = expected_tokens & extracted_tokens
        token_union = expected_tokens | extracted_tokens
        token_match = len(token_overlap) / len(token_union) if token_union else 1.0

        rule_overlap = expected_rules & extracted_rules
        rule_union = expected_rules | extracted_rules
        rule_match = len(rule_overlap) / len(rule_union) if rule_union else 1.0

        # Check structure
        structure_match = self._structure_match(extracted_rule, semantic_grammar_str)

        # Generate explanation
        notes = self._generate_notes(
            semantic_grammar_str,
            extracted_rule,
            expected_tokens,
            extracted_tokens,
        )

        return {
            'token_match_score': token_match,
            'rule_match_score': rule_match,
            'structure_match': structure_match,
            'missing_tokens': sorted(expected_tokens - extracted_tokens),
            'extra_tokens': sorted(extracted_tokens - expected_tokens),
            'missing_rules': sorted(expected_rules - extracted_rules),
            'extra_rules': sorted(extracted_rules - expected_rules),
            'notes': notes,
        }

    def _extract_tokens_from_string(self, rule_str: str) -> set[str]:
        """Extract UPPERCASE token names from semantic grammar string.

        Tokens are uppercase identifiers: INPAR, OUTPAR, INBRACE, etc.
        """
        tokens = re.findall(r'\b([A-Z][A-Z0-9_]*)\b', rule_str)
        # Filter out common non-tokens
        exclude = {'IF', 'THEN', 'ELSE', 'ELIF', 'DO', 'DONE', 'FI', 'ESAC'}
        return {t for t in tokens if t not in exclude}

    def _extract_rule_refs_from_string(self, rule_str: str) -> set[str]:
        """Extract lowercase rule references from semantic grammar string.

        Rule references are lowercase identifiers: list, word, cond, etc.
        """
        # Extract lowercase words that look like rules
        rules = re.findall(r'\b([a-z][a-z0-9_]*)\b', rule_str)
        # Filter out common keywords
        exclude = {'in', 'and', 'or', 'not', 'for', 'while', 'do', 'if', 'else'}
        return {r for r in rules if r not in exclude}

    def _extract_tokens_from_grammar_node(self, node: GrammarNode) -> set[str]:
        """Extract all token references from extracted grammar node."""
        tokens: set[str] = set()

        def visit(n: GrammarNode | list[GrammarNode]) -> None:
            if isinstance(n, dict):
                if '$ref' in n:
                    ref = n['$ref']
                    if ref.isupper() or ('_' in ref and ref.isupper()):
                        tokens.add(ref)

                for v in n.values():
                    if isinstance(v, (dict, list)):
                        visit(cast('GrammarNode | list[GrammarNode]', v))
            else:
                for item in n:
                    visit(item)

        visit(node)
        return tokens

    def _extract_rule_refs_from_grammar_node(self, node: GrammarNode) -> set[str]:
        """Extract all rule references from extracted grammar node."""
        rules: set[str] = set()

        def visit(n: GrammarNode | list[GrammarNode]) -> None:
            if isinstance(n, dict):
                if '$ref' in n:
                    ref = n['$ref']
                    # Rule refs are lowercase
                    if ref.islower() and not ref.isupper():
                        rules.add(ref)

                for v in n.values():
                    if isinstance(v, (dict, list)):
                        visit(cast('GrammarNode | list[GrammarNode]', v))
            else:
                for item in n:
                    visit(item)

        visit(node)
        return rules

    def _structure_match(self, extracted: GrammarNode, expected_str: str) -> bool:
        """Check if extracted structure matches expected structure.

        Returns True if:
        - Extracted is Union and expected has alternatives (|)
        - Extracted is Sequence and expected has sequential tokens
        - Extracted is Optional and expected has [...]
        """
        # Simple heuristics
        is_union_extracted = 'union' in extracted
        has_alternatives = '|' in expected_str

        if is_union_extracted and has_alternatives:
            return True

        is_sequence_extracted = 'sequence' in extracted
        has_sequence = any(c in expected_str for c in '(){}')

        if is_sequence_extracted and has_sequence:
            return True

        # Rough check: if both are simple refs, structure matches
        return '$ref' in extracted

    def _generate_notes(
        self,
        semantic_str: str,
        extracted: GrammarNode | list[GrammarNode],
        expected_tokens: set[str],
        extracted_tokens: set[str],
    ) -> str:
        """Generate explanation of comparison result."""
        notes_list: list[str] = []

        missing = expected_tokens - extracted_tokens
        extra = extracted_tokens - expected_tokens

        if not missing and not extra:
            notes_list.append('Perfect token match.')
        else:
            if missing:
                notes_list.append(f'Missing tokens: {", ".join(sorted(missing))}')
            if extra:
                notes_list.append(f'Extra tokens: {", ".join(sorted(extra))}')

        return ' '.join(notes_list) if notes_list else 'No notes.'


def compare_extracted_against_semantic(
    extracted_rules: Mapping[str, GrammarNode],
    semantic_rules: Mapping[str, str],
) -> dict[str, ComparisonResult | None]:
    """Compare all extracted rules against semantic grammar.

    Args:
        extracted_rules: Dict mapping function names to extracted grammar nodes
        semantic_rules: Dict mapping function names to semantic grammar strings

    Returns:
        Dict mapping function names to comparison results.
        Returns None for functions with no semantic grammar.
    """
    comparator = RuleComparator()
    comparisons: dict[str, ComparisonResult | None] = {}

    for func_name, semantic_rule in semantic_rules.items():
        if func_name not in extracted_rules:
            comparisons[func_name] = None
            continue

        comparisons[func_name] = comparator.compare_rules(
            extracted_rules[func_name], semantic_rule
        )

    return comparisons
