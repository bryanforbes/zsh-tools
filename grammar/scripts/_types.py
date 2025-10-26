from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

# Type for associativity
_Associativity = Literal['left', 'right']

# Type for rule type
_RuleType = Literal[
    'sequence',
    'choice',
    'repeat',
    'repeat1',
    'optional',
    'token',
    'binary_expr',
]


class SubGrammarRule(TypedDict):
    type: Literal['subgrammar']
    name: str
    entry_rule: str


class RuleDef(TypedDict):
    type: _RuleType
    elements: NotRequired[list[str]]  # Names of rules or tokens
    operators: NotRequired[list[str]]  # For binary_expr
    precedence: NotRequired[list[tuple[list[str], int]]]  # [[ops, level]]
    associativity: NotRequired[_Associativity | None]  # left, right, or None
    meta: NotRequired[dict[str, object]]  # Additional metadata


type Rules = RuleDef | SubGrammarRule


class TokenDef(TypedDict):
    pattern: str  # Regex or string
    meta: NotRequired[dict[str, object]]  # e.g., needs_scanner, category


class LanguageDef(TypedDict):
    rules: dict[str, Rules]
    tokens: NotRequired[dict[str, TokenDef]]
    includes: NotRequired[list[str]]  # Other sub-languages included


class ExtensionPoint(TypedDict):
    module: str  # Path to module
    hook_type: str  # Type of syntax extension
    description: NotRequired[str]


class CanonicalGrammar(TypedDict):
    languages: dict[str, LanguageDef]  # e.g., 'zsh', 'parameter', 'arith', etc.
    metadata: NotRequired[dict[str, object]]  # Version, source, etc.
    lexer_modes: NotRequired[
        list[str]
    ]  # e.g., 'normal', 'arith', 'cond', 'double_quotes'
    extension_points: NotRequired[list[ExtensionPoint]]
