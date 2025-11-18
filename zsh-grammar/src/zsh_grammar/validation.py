"""Semantic grammar validation and confidence scoring.

Compares extracted tokens against documented semantic grammar rules from
parse.c comments. Calculates confidence scores based on match rates and
penalty for false positives.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict

from zsh_grammar.grammar_rules import get_semantic_grammar_rules

if TYPE_CHECKING:
    from zsh_grammar.construct_grammar import _FunctionNode


class ValidationResult(TypedDict):
    """Validation result for a parser function.

    Attributes:
        func_name: Parser function name
        status: 'match', 'partial', 'mismatch', or 'no_rule'
        expected_tokens: Tokens mentioned in semantic grammar
        extracted_tokens: Tokens extracted from implementation
        missing_tokens: Tokens in rule but not extracted
        extra_tokens: Tokens extracted but not in rule
        num_sequences: Number of execution sequences extracted
        confidence: Confidence score (0.0 - 1.0)
        notes: Human-readable notes on validation
    """

    func_name: str
    status: Literal['match', 'partial', 'mismatch', 'no_rule']
    expected_tokens: set[str]
    extracted_tokens: set[str]
    missing_tokens: set[str]
    extra_tokens: set[str]
    num_sequences: int
    confidence: float
    notes: str


def validate_semantic_grammar(  # noqa: PLR0912
    call_graph: dict[str, _FunctionNode],
    parser_functions: dict[str, _FunctionNode],
    /,
) -> tuple[dict[str, ValidationResult], float]:
    """
    Phase 2.4.1f: Validate extracted token sequences against semantic grammar rules.

    Compares the tokens extracted from the AST for each parser function against
    the documented semantic grammar in parse.c comments.

    Returns:
        Tuple of (validation_results_dict, overall_confidence_score)
        Overall confidence is 0.0-1.0 based on match rates.
    """
    semantic_rules = get_semantic_grammar_rules()
    results: dict[str, ValidationResult] = {}

    for func_name, expected_rule in semantic_rules.items():
        if func_name not in call_graph:
            results[func_name] = {
                'func_name': func_name,
                'status': 'no_rule',
                'expected_tokens': expected_rule['tokens_in_rule'],
                'extracted_tokens': set(),
                'missing_tokens': expected_rule['tokens_in_rule'],
                'extra_tokens': set(),
                'num_sequences': 0,
                'confidence': 0.0,
                'notes': 'Function not found in call graph',
            }
            continue

        func_node = call_graph[func_name]
        token_sequences = func_node.get('token_sequences', [])

        # Extract all tokens from sequences
        extracted_tokens: set[str] = set()
        for sequence in token_sequences:
            for item in sequence:
                if item['kind'] == 'token' or item['kind'] == 'synthetic_token':
                    extracted_tokens.add(item['token_name'])

        expected_tokens = expected_rule['tokens_in_rule']
        missing_tokens = expected_tokens - extracted_tokens
        extra_tokens = extracted_tokens - expected_tokens

        # Calculate confidence score
        # Match: all expected tokens found, no extras
        # Partial: most expected tokens found, few extras
        # Mismatch: significant divergence
        if not expected_tokens:
            confidence = 1.0
            status = 'match'
        else:
            matches = len(expected_tokens & extracted_tokens)
            match_ratio = matches / len(expected_tokens)

            # Penalize for extra tokens (false positives)
            extra_penalty = len(extra_tokens) / max(1, len(expected_tokens))

            confidence = max(0.0, match_ratio - extra_penalty * 0.1)

            if confidence >= 0.9:
                status = 'match'
            elif confidence >= 0.7:
                status = 'partial'
            else:
                status = 'mismatch'

        # Build notes
        notes_parts: list[str] = []
        if confidence >= 0.9:
            notes_parts.append('Excellent match with semantic rule')
        elif confidence >= 0.7:
            notes_parts.append('Good match with minor discrepancies')
        else:
            notes_parts.append('Significant divergence from documented rule')

        if missing_tokens:
            notes_parts.append(f'Missing: {", ".join(sorted(missing_tokens))}')
        if extra_tokens:
            notes_parts.append(f'Extra: {", ".join(sorted(extra_tokens))}')

        results[func_name] = {
            'func_name': func_name,
            'status': status,
            'expected_tokens': expected_tokens,
            'extracted_tokens': extracted_tokens,
            'missing_tokens': missing_tokens,
            'extra_tokens': extra_tokens,
            'num_sequences': len(token_sequences),
            'confidence': confidence,
            'notes': ' | '.join(notes_parts),
        }

    # Calculate overall confidence
    if results:
        total_confidence = sum(r['confidence'] for r in results.values())
        overall_confidence = total_confidence / len(results)
    else:
        overall_confidence = 0.0

    return results, overall_confidence
