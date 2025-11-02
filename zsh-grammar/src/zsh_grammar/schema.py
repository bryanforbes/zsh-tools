from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


# ---------------------------------------------------------------------------
# Core Types
# ---------------------------------------------------------------------------
class _ParamDef(TypedDict):
    name: str
    type: str


class _FunctionLocation(TypedDict):
    file: str
    line: int
    name: str
    return_type: str
    params: list[_ParamDef]


class _TokenDef(TypedDict):
    pattern: str
    description: NotRequired[str]
    enter_mode: NotRequired[str]
    leave_mode: NotRequired[str]
    meta: NotRequired[dict[str, str | bool | None]]
    origin_file: NotRequired[str]
    line: NotRequired[int]


class _RuleDef(TypedDict):
    type: Literal[
        'token',
        'sequence',
        'choice',
        'prec',
        'repeat',
        'repeat1',
        'field',
        'alias',
        'external',
    ]
    elements: NotRequired[list[str]]
    operators: NotRequired[list[str]]
    precedence: NotRequired[list[list[object]]]
    follows: NotRequired[list[str]]  # what may follow this rule
    calls: NotRequired[list[str]]  # functions or subrules called
    contexts: NotRequired[list[str]]  # lexer modes or parsing contexts
    node_type: NotRequired[str]
    entry_rule: NotRequired[str]
    formatting: NotRequired[dict[str, str | int | None]]
    lint: NotRequired[dict[str, str | bool | None]]
    meta: NotRequired[dict[str, str | bool | None]]
    location: NotRequired[_FunctionLocation]
    description: NotRequired[str]
    confidence: NotRequired[float]


class _LanguageDef(TypedDict):
    rules: dict[str, _RuleDef]
    tokens: NotRequired[dict[str, _TokenDef]]
    includes: NotRequired[list[str]]
    contexts: NotRequired[list[str]]
    precedence: NotRequired[list[list[str]]]
    description: NotRequired[str]


class _OptionEffect(TypedDict):
    enables: NotRequired[list[str]]
    disables: NotRequired[list[str]]
    modifies: NotRequired[list[str]]
    description: NotRequired[str]


class _LexerMode(TypedDict):
    name: str
    inherits: NotRequired[str]
    tokens_active: list[str]
    enter_rules: NotRequired[list[str]]
    leave_rules: NotRequired[list[str]]
    description: NotRequired[str]


class _ExtensionPoint(TypedDict):
    module: str
    hook_type: str
    description: NotRequired[str]


class _Feature(TypedDict):
    name: str
    since: NotRequired[str]
    until: NotRequired[str]
    description: NotRequired[str]
    options: NotRequired[list[str]]


class _Metadata(TypedDict):
    version: str
    source: str
    source_commit: NotRequired[str]
    generated_by: NotRequired[str]
    generated_at: NotRequired[str]
    generator_version: NotRequired[str]
    notes: NotRequired[str]


class CanonicalGrammar(TypedDict):
    languages: dict[str, _LanguageDef]
    contexts: NotRequired[dict[str, list[str]]]
    lexer_modes: NotRequired[list[_LexerMode]]
    option_effects: NotRequired[dict[str, _OptionEffect]]
    features: NotRequired[list[_Feature]]
    extension_points: NotRequired[list[_ExtensionPoint]]
    metadata: NotRequired[_Metadata]
