from __future__ import annotations

from typing import Literal, NotRequired
from typing_extensions import TypedDict


class Source(TypedDict):
    file: str
    line: int
    function: NotRequired[str]
    context: NotRequired[str]


class _BaseNode(TypedDict):
    description: NotRequired[str]
    source: NotRequired[Source]


class Empty(_BaseNode):
    empty: Literal[True]


class Token(_BaseNode):
    token: str
    matches: str | list[str]


class Optional(_BaseNode):
    optional: GrammarNode


class OptionCondition(TypedDict):
    option: str


type ParseFlag = Literal[
    'incmdpos',
    'incond',
    'inredir',
    'incasepat',
    'infor',
    'inrepeat',
    'intypeset',
    'isnewlin',
]


class ParseFlagCondition(TypedDict):
    parseflag: ParseFlag


type LexState = Literal[
    'INCMDPOS',
    'INCOND',
    'INREDIR',
    'INCASEPAT',
    'INFOR',
    'INREPEAT',
    'INTYPESET',
    'ISNEWLIN',
    'IN_MATH',
    'ALIASSPACEFLAG',
    'INCOMPARISON',
    'IN_ARRAY',
    'IN_SUBSTITUTION',
    'IN_BRACEEXP',
    'IN_GLOBPAT',
]


class LexStateCondition(TypedDict):
    lexstate: LexState


class VersionCondition(TypedDict):
    sinceVersion: NotRequired[str]
    untilVersion: NotRequired[str]


NotCondition = TypedDict('NotCondition', {'not': 'Condition'})
AndCondition = TypedDict('AndCondition', {'and': 'list[Condition]'})
OrCondition = TypedDict('OrCondition', {'or': 'list[Condition]'})

type Condition = (
    OptionCondition
    | ParseFlagCondition
    | LexStateCondition
    | VersionCondition
    | NotCondition
    | AndCondition
    | OrCondition
)


class Variant(_BaseNode):
    variant: GrammarNode
    condition: Condition


class Terminal(_BaseNode):
    pattern: str


class Union(_BaseNode):
    union: list[GrammarNode]


class Sequence(_BaseNode):
    sequence: list[GrammarNode]


class Repeat(_BaseNode):
    repeat: GrammarNode
    min: NotRequired[int]
    max: NotRequired[int]


_RefBase = TypedDict('_RefBase', {'$ref': str})


class Ref(_BaseNode, _RefBase): ...


type GrammarNode = (
    Empty | Optional | Ref | Repeat | Sequence | Terminal | Token | Union | Variant
)
type Language = dict[str, GrammarNode]


class Languages(TypedDict, extra_items=Language):
    core: Language


class Grammar(TypedDict, extra_items=str):
    languages: Languages
    version: NotRequired[str]
    zsh_version: NotRequired[str]
    zsh_revision: NotRequired[str]
    generated_at: NotRequired[str]


class TokenEdge(TypedDict):
    """Represents a direct token consumption edge in a parser function.

    Attributes:
        token_name: Name of the token (e.g., 'INPAR', 'OUTPAR')
        position: 'before' (prefix), 'after' (suffix), or 'inline' (no function call)
        line: Line number in source where token check occurs
        context: Optional context description (e.g., 'guard condition', 'required')

    DEPRECATED: Use TokenCheck instead (Phase 2.4.1 redesign)
    """

    token_name: str
    position: Literal['before', 'after', 'inline']
    line: int
    context: NotRequired[str]


class TokenCheck(TypedDict):
    """Phase 2.4.1: Token check in control flow sequence.

    Attributes:
        kind: Discriminator - always 'token'
        token_name: Token name (SCREAMING_SNAKE_CASE)
        line: Line number in source
        is_negated: Whether this is a `tok != TOKEN` check
    """

    kind: Literal['token']
    token_name: str
    line: int
    is_negated: bool


class FunctionCall(TypedDict):
    """Phase 2.4.1: Function call in control flow sequence.

    Attributes:
        kind: Discriminator - always 'call'
        func_name: Function name (par_* or parse_*)
        line: Line number in source
    """

    kind: Literal['call']
    func_name: str
    line: int


class SyntheticToken(TypedDict):
    """Phase 2.4.1: Synthetic token from string matching condition.

    Example: `tok == STRING && !strcmp(tokstr, "always")` → ALWAYS token

    Attributes:
        kind: Discriminator - always 'synthetic_token'
        token_name: Generated token name (SCREAMING_SNAKE_CASE)
        line: Line number in source
        condition: Description of matching condition
    """

    kind: Literal['synthetic_token']
    token_name: str
    line: int
    condition: str


# Phase 2.4.1: Token sequence items (discriminated union)
type TokenOrCall = TokenCheck | FunctionCall | SyntheticToken


class FunctionNode(TypedDict):
    name: str
    file: str
    line: int
    calls: list[str]
    conditions: NotRequired[list[str]]
    signature: NotRequired[str]
    visibility: NotRequired[str]
    token_edges: NotRequired[list[TokenEdge]]  # DEPRECATED - use token_sequences
    token_sequences: NotRequired[
        list[list[TokenOrCall]]
    ]  # Phase 2.4.1: Ordered token+call sequences per branch


class SemanticGrammarRule(TypedDict):
    """Semantic grammar rule extracted from parse.c comments.

    Attributes:
        func_name: Parser function name (e.g., 'par_for', 'par_case')
        line_no: Line number in parse.c where rule is documented
        rule: Raw grammar rule text from comment (e.g., 'for : FOR ... { SEPER } ...')
        alternatives: List of alternative productions identified in rule
        tokens_in_rule: Set of token names mentioned in the rule
        description: Human-readable description of the production
    """

    func_name: str
    line_no: int
    rule: str
    alternatives: list[str]
    tokens_in_rule: set[str]
    description: str
