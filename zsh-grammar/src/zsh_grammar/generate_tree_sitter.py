from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Annotated, Final

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
    TokenMatch,
    TokenPattern,
    TokenReference,
    Union,
    Variant,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

TEMPLATE: Final = r"""/**
 * @file Zsh grammar for tree-sitter
 * @author Bryan Forbes <bryan@reigndropsfall.net>
 * @license BSD-3-Clause
 */

/// <reference types="tree-sitter-cli/dsl" />
// @ts-check

export default grammar({
  name: 'zsh',

  // conflicts: ($) => [
  //   [$.pipeline],
  // ],

  // reserved: {
  //   global: ($) => [
  //     {{RESERVED_WORDS}}
  //   ],
  // },

  // inline: ($) => [
  //   {{INLINE_RULES}}
  // ],

  extras: ($) => [
    $.comment,
    /\s+/, // whitespace
  ],

  word: ($) => $.plain_string,

  rules: {
    program: ($) => $.list,
    {{RULES}}
  },
});
"""


@dataclass
class Transformer:
    grammar: Grammar
    lang: Language
    rule_aliases: dict[str, str]
    token_rules: set[str]
    external_rules: set[str]
    skip_rules: set[str] = field(default_factory=set)
    func_stack: list[str] = field(default_factory=list)

    @property
    def current_func(self) -> str | None:
        return self.func_stack[-1] if self.func_stack else None

    def get_token(self, token_name: str, /) -> TokenMatch | TokenPattern | None:
        return self.lang.tokens.get(token_name)

    def get_rule_name(self, rule_name: str, /) -> str:
        if rule_name in self.external_rules:
            return f'_{rule_name}'
        return self.rule_aliases.get(rule_name, rule_name)

    @contextmanager
    def __enter_func(self, func_name: str, /) -> Iterator[str | None]:
        previous_func = self.current_func
        self.func_stack.append(func_name)
        try:
            yield previous_func
        finally:
            self.func_stack.pop()

    def transform_token_match(self, rule: TokenMatch, /) -> str:
        if isinstance(rule.matches, str):
            return f"'{rule.matches}'"

        return ''.join(
            [
                "'" if self.current_func == 'choice' else "choice('",
                "', '".join(rule.matches),
                "'" if self.current_func == 'choice' else "')",
            ]
        )

    def transform_function_call(
        self, func_name: str, arguments: Rule | Iterable[Rule], /
    ) -> str | None:
        with self.__enter_func(func_name) as previous_func:
            if isinstance(arguments, Iterable):
                transformed_rules = [self.transform_rule(arg) for arg in arguments]
            else:
                transformed_rules = [self.transform_rule(arguments)]

            transformed_args = [rule for rule in transformed_rules if rule is not None]

            if not transformed_args:
                return None

            if func_name.startswith('repeat') or (
                func_name != previous_func
                and (func_name == 'optional' or len(transformed_args) > 1)
            ):
                return f'{func_name}({", ".join(transformed_args)})'

            return ', '.join(transformed_args)

    def __transform_rule(self, rule: Rule, /, *, name: str | None = None) -> str | None:  # noqa: PLR0912
        transformed: str | None = None

        match rule:
            case Optional(rule=inner_rule):
                transformed = self.transform_function_call('optional', inner_rule)
            case Variant(rule=inner_rule):
                if name == 'comment':
                    transformed = self.transform_rule(inner_rule)
            case TokenMatch():
                transformed = self.transform_token_match(rule)
            case TokenPattern(pattern=pattern):
                transformed = f'/{pattern}/'
            case Union(rules=rules):
                transformed = self.transform_function_call('choice', rules)
            case Sequence(rules=rules):
                transformed = self.transform_function_call('seq', rules)
            case Repeat(rule=inner_rule, min=min_):
                transformed = self.transform_function_call(
                    'repeat1' if min_ >= 1 else 'repeat', inner_rule
                )
            case RuleReference(rule=rule_name, lang=rule_lang):
                if rule_lang is None and rule_name not in self.skip_rules:
                    transformed = f'$.{self.get_rule_name(rule_name)}'
            case TokenReference(token=token_name):
                if (
                    token_name != 'BLANK'  # noqa: S105
                    and (token := self.get_token(token_name)) is not None
                ):
                    transformed = self.transform_rule(token)
            case _:
                pass

        return transformed

    def __transform_precedence(
        self, rule: Rule, /, *, name: str | None = None
    ) -> str | None:
        precedence_func: str | None = None

        if rule.associativity == 'left':
            precedence_func = 'prec.left'
        elif rule.associativity == 'right':
            precedence_func = 'prec.right'
        elif rule.precedence is not None:
            precedence_func = 'prec'

        if precedence_func is not None:
            with self.__enter_func(precedence_func):
                transformed_rule = self.__transform_rule(rule, name=name)
                if transformed_rule is not None:
                    precedence = (
                        '' if rule.precedence is None else f'{rule.precedence}, '
                    )
                    return f'{precedence_func}({precedence}{transformed_rule})'
                return None

        return self.__transform_rule(rule, name=name)

    def __is_token_only_rule(self, rule: Rule, /, *, seen: set[str]) -> bool:
        match rule:
            case Union(rules=rules) | Sequence(rules=rules):
                return all(self.__is_token_only_rule(r, seen=seen) for r in rules)
            case TokenMatch() | TokenPattern() | TokenReference():
                return True
            case RuleReference(rule=rule_name, lang=lang_name) if (
                lang_name is None and rule_name not in seen
            ):
                seen.add(rule_name)
                return self.__is_token_only_rule(self.lang.rules[rule_name], seen=seen)
            case _:
                return False

    def __collapse_token_only_rule(self, rule: Rule, /) -> Rule:
        match rule:
            case Union(rules=rules) | Sequence(rules=rules):
                return replace(
                    rule, rules=[self.__collapse_token_only_rule(r) for r in rules]
                )
            case RuleReference(rule=rule_name, lang=lang_name) if lang_name is None:
                return self.__collapse_token_only_rule(self.lang.rules[rule_name])
            case _:
                return rule

    def transform_rule(self, rule: Rule, /, *, name: str | None = None) -> str | None:
        if (
            name is not None
            and name in self.token_rules
            and self.__is_token_only_rule(rule, seen={name})
        ):
            rule = self.__collapse_token_only_rule(rule)

        transformed_rule = self.__transform_precedence(rule, name=name)

        if transformed_rule is not None and name in self.token_rules:
            transformed_rule = f'token({transformed_rule})'

        return transformed_rule

    @staticmethod
    def transform(grammar: Grammar) -> str:
        transformer = Transformer(
            grammar,
            grammar.languages['core'],
            {'word': 'zsh_word'},
            {
                'comment',
                'plain_string',
                'sublist_terminator',
                'sublist_terminator_no_semi',
            },
            {'quoted_whitespace'},
            {
                'glob_pattern',
                'parameter_reference',
                'command_substitution',
                'array_subscript',
                'parameter',
                'simple_parameter',
                'braced_parameter',
                'indexed_parameter',
                'special_parameter',
                'special_parameter_ref',
                'positional_parameter',
                'bitwise_arithmetic_operators',
                'shift_arithmetic_operators',
                'c_arithmetic_expression',
                'arithmetic_expression',
                'reserved_word',
                'sublist_terminator_no_semi',
            },
        )

        reserved_words = transformer.transform_rule(
            grammar.languages['core'].rules['reserved_word']
        )

        if reserved_words is not None:
            reserved_words = reserved_words.removeprefix('choice(').removesuffix(')')

        inline_rules = ['reserved_word']

        rules = [
            f'{transformer.get_rule_name(name)}: ($) => {tree_sitter_rule}'
            for name, rule in grammar.languages['core'].rules.items()
            if name not in transformer.external_rules
            and name not in transformer.skip_rules
            and (tree_sitter_rule := transformer.transform_rule(rule, name=name))
            is not None
        ]

        return (
            TEMPLATE.replace('{{RULES}}', ',\n'.join(rules))
            .replace('{{RESERVED_WORDS}}', '')
            .replace(
                '{{INLINE_RULES}}', (', '.join(f'$.{rule}' for rule in inline_rules))
            )
            .replace(
                '{{EXTERNAL_RULES}}',
                ', '.join(f'$._{rule}' for rule in transformer.external_rules),
            )
        )


def _generate_tree_sitter(
    grammar_js: Annotated[Path, typer.Argument()] = TREE_SITTER_GRAMMAR_PATH,
) -> None:
    grammar = Grammar.load(GRAMMAR_JSON_PATH)

    grammar_js.write_text(Transformer.transform(grammar))


def main() -> None:
    typer.run(_generate_tree_sitter)
