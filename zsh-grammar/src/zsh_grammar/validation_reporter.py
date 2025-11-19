"""Generate validation reports from rule comparisons.

Stage 5.3: Document coverage and discrepancies in extracted grammar.

This module generates markdown reports summarizing the validation results,
showing which functions match their semantic grammar, which have partial
matches, and which need investigation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from zsh_grammar.rule_comparison import ComparisonResult


def generate_validation_report(
    semantic_grammar: Mapping[str, str],
    comparisons: Mapping[str, ComparisonResult | None],
) -> str:
    """Generate markdown validation report.

    Args:
        semantic_grammar: Dict of function -> documented grammar
        comparisons: Results from comparing extracted vs semantic

    Returns:
        Markdown formatted report.
    """
    report = '# Phase 2.4.1 Token-Sequence Validation Report\n\n'

    # Summary statistics
    total = len(semantic_grammar)
    validated = len([c for c in comparisons.values() if c is not None])

    if validated == 0:
        report += 'No comparisons available.\n'
        return report

    token_scores = [c['token_match_score'] for c in comparisons.values() if c]
    rule_scores = [c['rule_match_score'] for c in comparisons.values() if c]
    structure_matches = sum(
        1 for c in comparisons.values() if c and c['structure_match']
    )

    avg_token = sum(token_scores) / len(token_scores) if token_scores else 0
    avg_rule = sum(rule_scores) / len(rule_scores) if rule_scores else 0

    report += '## Summary\n\n'
    report += f'- **Functions with semantic grammar**: {total}\n'
    report += f'- **Functions validated**: {validated}\n'
    report += f'- **Average token match**: {avg_token * 100:.1f}%\n'
    report += f'- **Average rule match**: {avg_rule * 100:.1f}%\n'
    report += f'- **Structure matches**: {structure_matches}/{validated}\n'
    status = '✅ PASS' if avg_token >= 0.8 else '❌ FAIL'
    report += f'- **Overall criterion (≥80%)**: {status}\n\n'

    # By function
    report += _add_comparison_sections(comparisons)

    return report


def _add_comparison_sections(  # noqa: C901, PLR0912
    comparisons: Mapping[str, ComparisonResult | None],
) -> str:
    """Add comparison sections to report.

    Extracted to avoid PLR0915 (too many statements) error.
    """
    report = ''

    perfect = [
        fn for fn, c in comparisons.items() if c and c['token_match_score'] >= 0.95
    ]
    partial = [
        fn
        for fn, c in comparisons.items()
        if c and 0.7 <= c['token_match_score'] < 0.95
    ]
    poor = [fn for fn, c in comparisons.items() if c and c['token_match_score'] < 0.7]

    if perfect:
        report += f'### ✅ Perfect Matches ({len(perfect)})\n\n'
        for fn in sorted(perfect):
            c = comparisons[fn]
            if c is not None:
                report += f'- **{fn}** ({c["token_match_score"] * 100:.0f}%)\n'
        report += '\n'

    if partial:
        report += f'### ⚠️ Partial Matches ({len(partial)})\n\n'
        for fn in sorted(partial):
            c = comparisons[fn]
            if c is not None:
                report += (
                    f'- **{fn}** '
                    f'({c["token_match_score"] * 100:.0f}% token, '
                    f'{c["rule_match_score"] * 100:.0f}% rule)\n'
                )
                if c['missing_tokens']:
                    missing = ', '.join(c['missing_tokens'][:3])
                    if len(c['missing_tokens']) > 3:
                        missing += f', ... ({len(c["missing_tokens"])} total)'
                    report += f'  - Missing tokens: {missing}\n'
                if c['extra_tokens']:
                    extra = ', '.join(c['extra_tokens'][:3])
                    if len(c['extra_tokens']) > 3:
                        extra += f', ... ({len(c["extra_tokens"])} total)'
                    report += f'  - Extra tokens: {extra}\n'
        report += '\n'

    if poor:
        report += f'### ❌ Poor Matches ({len(poor)})\n\n'
        for fn in sorted(poor):
            c = comparisons[fn]
            if c is not None:
                report += f'- **{fn}** ({c["token_match_score"] * 100:.0f}%)\n'
        report += '\n'

    # No semantic grammar section
    no_grammar = [fn for fn, c in comparisons.items() if c is None]
    if no_grammar:
        report += f'### ⊘ No Semantic Grammar ({len(no_grammar)})\n\n'
        report += 'These functions have no documented semantic grammar:\n\n'
        for fn in sorted(no_grammar):
            report += f'- {fn}\n'
        report += '\n'

    return report


def generate_detailed_comparison_report(
    semantic_grammar: dict[str, str],
    comparisons: dict[str, ComparisonResult | None],
) -> str:
    """Generate detailed per-function comparison report.

    Args:
        semantic_grammar: Dict of function -> documented grammar
        comparisons: Results from comparing extracted vs semantic

    Returns:
        Markdown formatted detailed report.
    """
    report = '# Phase 2.4.1 Detailed Comparison Report\n\n'

    for func_name in sorted(semantic_grammar.keys()):
        comparison = comparisons.get(func_name)

        report += f'## {func_name}\n\n'
        report += f'**Semantic Grammar:**\n```\n{semantic_grammar[func_name]}\n```\n\n'

        if comparison is None:
            report += '❌ No extracted rule available\n\n'
            continue

        report += f'**Token Match:** {comparison["token_match_score"] * 100:.1f}%\n'
        report += f'**Rule Match:** {comparison["rule_match_score"] * 100:.1f}%\n'
        report += (
            f'**Structure Match:** '
            f'{"✅ Yes" if comparison["structure_match"] else "❌ No"}\n\n'
        )

        if comparison['missing_tokens']:
            report += (
                f'**Missing Tokens:** {", ".join(comparison["missing_tokens"])}\n\n'
            )

        if comparison['extra_tokens']:
            report += f'**Extra Tokens:** {", ".join(comparison["extra_tokens"])}\n\n'

        if comparison['notes']:
            report += f'**Notes:** {comparison["notes"]}\n\n'

        report += '---\n\n'

    return report


def print_summary_table(
    comparisons: dict[str, ComparisonResult | None],
) -> str:
    """Print summary table of all comparisons.

    Args:
        comparisons: Results from comparing extracted vs semantic

    Returns:
        Markdown table.
    """
    lines = [
        '| Function | Token Match | Rule Match | Structure | Missing Tokens |',
        '|----------|-------------|-----------|-----------|---|',
    ]

    for func_name in sorted(comparisons.keys()):
        c = comparisons[func_name]

        if c is None:
            lines.append(f'| {func_name} | N/A | N/A | N/A | N/A |')
        else:
            token_pct = f'{c["token_match_score"] * 100:.0f}%'
            rule_pct = f'{c["rule_match_score"] * 100:.0f}%'
            struct = '✅' if c['structure_match'] else '❌'

            missing = ', '.join(c['missing_tokens'][:2]) if c['missing_tokens'] else '-'
            if len(c['missing_tokens']) > 2:
                missing += f', +{len(c["missing_tokens"]) - 2}'

            lines.append(
                f'| {func_name} | {token_pct} | {rule_pct} | {struct} | {missing} |'
            )

    return '\n'.join(lines)
