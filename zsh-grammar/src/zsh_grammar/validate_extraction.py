#!/usr/bin/env python3
"""
Validation script for token extraction confidence scoring.

Compares extracted token sequences against documented semantic grammar rules
and reports confidence metrics per function.

Usage:
    python -m zsh_grammar.validate_extraction
"""

from __future__ import annotations

import os
from pathlib import Path

from clang.cindex import Config

from zsh_grammar.control_flow import build_call_graph
from zsh_grammar.source_parser import ZshParser
from zsh_grammar.validation import ValidationResult, validate_semantic_grammar


def main() -> None:  # noqa: PLR0915
    """Run validation and print results."""
    # Set up libclang
    if libclang_prefix := os.environ.get('LIBCLANG_PREFIX'):
        Config.set_library_path(Path(libclang_prefix) / 'lib')
    else:
        # Try standard locations
        Config.set_library_path(Path('/opt/homebrew/opt/llvm/lib'))

    zsh_root = Path(__file__).resolve().parents[3] / 'vendor' / 'zsh'
    zsh_src = zsh_root / 'Src'

    print(f'Validating grammar extraction from {zsh_src}')
    print()

    parser = ZshParser(zsh_src)

    # Build call graph
    call_graph = build_call_graph(parser)

    # Extract just what we need for validation
    parser_functions = {
        name: node
        for name, node in call_graph.items()
        if name.startswith(('par_', 'parse_'))
    }

    # Validate
    validation_results, overall_confidence = validate_semantic_grammar(
        call_graph, parser_functions
    )

    print(f'Overall Confidence: {overall_confidence:.2%}\n')

    # Sort by confidence
    sorted_results = sorted(
        validation_results.items(), key=lambda x: x[1]['confidence'], reverse=True
    )

    # Group by confidence level
    excellent: list[tuple[str, ValidationResult]] = []
    good: list[tuple[str, ValidationResult]] = []
    partial: list[tuple[str, ValidationResult]] = []
    poor: list[tuple[str, ValidationResult]] = []

    for func_name, result in sorted_results:
        conf = result['confidence']
        if conf >= 0.9:
            excellent.append((func_name, result))
        elif conf >= 0.7:
            good.append((func_name, result))
        elif conf > 0:
            partial.append((func_name, result))
        else:
            poor.append((func_name, result))

    def print_results(title: str, results: list[tuple[str, ValidationResult]]) -> None:
        if not results:
            return
        print(f'\n{title}')
        print('=' * 70)
        for func_name, result in results:
            conf = result['confidence']
            num_seq = result['num_sequences']
            missing = result['missing_tokens']
            extra = result['extra_tokens']

            missing_str = ', '.join(sorted(missing)) if missing else 'None'
            extra_str = ', '.join(sorted(extra)) if extra else 'None'

            print(f'{func_name:20} {conf:6.1%} ({num_seq} seq)')
            if missing:
                print(f'  Missing: {missing_str}')
            if extra:
                print(f'  Extra: {extra_str}')

    print_results('✅ Excellent (≥90%)', excellent)
    print_results('⚠️  Good (70-89%)', good)
    print_results('⚠️  Partial (1-69%)', partial)
    print_results('❌ Poor (0%)', poor)

    print()
    print('=' * 70)
    print(
        f'Summary: {len(excellent)} excellent, {len(good)} good, '
        f'{len(partial)} partial, {len(poor)} poor'
    )
    print(f'Average confidence: {overall_confidence:.2%}')


if __name__ == '__main__':
    main()
