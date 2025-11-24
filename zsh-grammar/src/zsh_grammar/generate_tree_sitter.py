from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import Annotated, Final

import typer

from zsh_grammar.common import GRAMMAR_JSON_PATH, TREE_SITTER_GRAMMAR_PATH
from zsh_grammar.grammar import (
    Grammar,
    Language,
    Optional,
    Repeat,
    Rule,
    RuleReference,
    Sequence,
    Terminal,
    TokenMatch,
    TokenReference,
    Union,
    Variant,
)

TEMPLATE: Final = """/**
 * @file Zsh grammar for tree-sitter
 * @author Bryan Forbes <bryan@reigndropsfall.net>
 * @license BSD-3-Clause
 */

/// <reference types="tree-sitter-cli/dsl" />
// @ts-check

{{TOKENS}}

export default grammar({
  name: 'zsh',

  rules: {
    source_file: ($) => $.list,
    {{RULES}}
  },
});
"""


def _transform_rule(grammar: Grammar, lang: Language, rule: Rule, /) -> str | None:  # noqa: PLR0912
    func_call: str | None = None

    match rule:
        case Optional(rule=inner_rule):
            func_call = f'optional({_transform_rule(grammar, lang, inner_rule)})'
        case Variant(rule=inner_rule):
            func_call = _transform_rule(grammar, lang, inner_rule)
        case Terminal(pattern=pattern):
            func_call = f'/{pattern}/'
        case Union(rules=rules):
            func_call = f'choice({
                ", ".join(
                    trule
                    for trule in [_transform_rule(grammar, lang, r) for r in rules]
                    if trule is not None
                )
            })'
        case Sequence(rules=rules):
            func_call = f'seq({
                ", ".join(
                    trule
                    for trule in [_transform_rule(grammar, lang, r) for r in rules]
                    if trule is not None
                )
            })'
        case Repeat(rule=inner_rule, min=min_):
            if min_ >= 1:
                func_call = f'repeat1({_transform_rule(grammar, lang, inner_rule)})'
            else:
                func_call = f'repeat({_transform_rule(grammar, lang, inner_rule)})'
        case RuleReference(rule=rule_name, lang=rule_lang):
            if rule_lang is None:
                rule_key = (
                    f'_{rule_name}'
                    if rule_name in ('sublist', 'comment')
                    else rule_name
                )
                func_call = f'$.{rule_key}'
        case TokenReference(token=token_name):
            token = lang.tokens[token_name]
            if isinstance(token, TokenMatch) and isinstance(token.matches, list):
                func_call = f'...{token_name}'
            else:
                func_call = token_name
        case _:
            pass

    return func_call


def _generate_tree_sitter(
    grammar_js: Annotated[Path, typer.Argument()] = TREE_SITTER_GRAMMAR_PATH,
) -> None:
    grammar = Grammar.load(GRAMMAR_JSON_PATH)
    core = grammar.languages['core']

    token_vars = [
        rf'const {key} = /{value.pattern}/;'
        if isinstance(value, Terminal)
        else rf"const {key} = '{value.matches}';"
        if isinstance(value.matches, str)
        else rf"const {key} = ['{"', '".join(value.matches)}'];"
        for key, value in core.tokens.items()
    ]

    rules = [
        f'{("_" + name) if name in ("sublist", "comment") else name}: ($) => {_transform_rule(grammar, core, rule)}'
        for name, rule in core.rules.items()
    ]

    grammar_js.write_text(
        TEMPLATE.replace('{{TOKENS}}', '\n'.join(token_vars)).replace(
            '{{RULES}}', ',\n'.join(rules)
        )
    )


def main() -> None:
    typer.run(_generate_tree_sitter)
