"""Grammar rule construction and semantic grammar database.

Converts extracted token sequences to BNF grammar rules and provides
access to documented semantic grammar rules from parse.c comments.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from zsh_grammar.function_discovery import _is_parser_function
from zsh_grammar.grammar_utils import create_ref, create_sequence, create_terminal

if TYPE_CHECKING:
    from zsh_grammar._types import GrammarNode, Source
    from zsh_grammar.construct_grammar import (
        TokenOrCall,
        _FunctionNode,
        _SemanticGrammarRule,
    )


def sequence_to_rule(
    sequence: list[TokenOrCall],
    func_name: str = '',
    source_info: Source | None = None,
) -> GrammarNode:
    """
    Phase 2.4.1c: Convert a token sequence to a grammar rule.

    Converts a list of TokenOrCall items (extracted from function body) into
    a GrammarNode representing the rule structure.

    Strategy:
    1. Convert each item to a ref (token, call, or synthetic token)
    2. Group items into a sequence
    3. Detect patterns:
       - Single item: return ref directly
       - Multiple items: wrap in sequence
       - Negated tokens: currently pass through (future: use negative lookahead)

    Args:
        sequence: List of _TokenCheck, _FunctionCall, _SyntheticToken items
        func_name: Function name for context
        source_info: Source location info to attach to rule (Source TypedDict)

    Returns:
        GrammarNode representing the sequence (Terminal, Ref, Sequence, etc.)
    """
    if not sequence:
        # Empty sequence: return placeholder terminal
        if source_info is not None:
            return create_terminal(f'[{func_name}]', source=source_info)
        return create_terminal(f'[{func_name}]')

    # Collect references for this sequence, preserving order and structure
    refs: list[GrammarNode] = []

    for item in sequence:
        if item['kind'] == 'token':
            # Token reference (may be negated for negative checks)
            token_check = item  # Already typed as _TokenCheck by discriminated union
            token_name = token_check['token_name']
            is_negated = token_check.get('is_negated', False)

            # Create reference with description for negated checks
            if is_negated:
                ref = create_ref(
                    token_name,
                    description=f'NOT {token_name}',
                )
            else:
                ref = create_ref(token_name)
            refs.append(ref)

        elif item['kind'] == 'call':
            # Function call - reference to called rule
            call = item  # Already typed as _FunctionCall by discriminated union
            rule_name = _function_to_rule_name(call['func_name'])
            ref = create_ref(rule_name)
            refs.append(ref)

        elif item['kind'] == 'synthetic_token':
            # Synthetic token from string matching
            synth = item  # Already typed as _SyntheticToken by discriminated union
            token_name = synth['token_name']
            condition = synth.get('condition', '')

            if condition:
                ref = create_ref(
                    token_name,
                    description=f'Synthetic: {condition}',
                )
            else:
                ref = create_ref(token_name)
            refs.append(ref)

    # Convert refs to rule structure
    if len(refs) == 1:
        # Single item: return unwrapped
        return refs[0]

    # Multiple items: wrap in sequence with source info
    if source_info is not None:
        return create_sequence(refs, source=source_info)
    return create_sequence(refs)


def get_semantic_grammar_rules() -> dict[str, _SemanticGrammarRule]:
    """
    Phase 2.4.1f: Extract semantic grammar rules from parse.c comments.

    These rules document the expected token sequences for each parser function,
    directly from the source code comments.

    Returns:
        Dict mapping function names to semantic rules with expected tokens.
    """

    rules: dict[str, _SemanticGrammarRule] = {
        'par_list': {
            'func_name': 'par_list',
            'line_no': 762,
            'rule': (
                'list : { SEPER } [ sublist [ { SEPER | AMPER | AMPERBANG } list ] ]'
            ),
            'alternatives': ['{ SEPER }', 'sublist', '{ SEPER | AMPER | AMPERBANG }'],
            'tokens_in_rule': {'SEPER', 'AMPER', 'AMPERBANG'},
            'description': 'Sequence with optional separators and sublists',
        },
        'par_sublist': {
            'func_name': 'par_sublist',
            'line_no': 815,
            'rule': 'sublist : sublist2 [ ( DBAR | DAMPER ) { SEPER } sublist ]',
            'alternatives': ['sublist2', 'DBAR', 'DAMPER'],
            'tokens_in_rule': {'DBAR', 'DAMPER', 'SEPER'},
            'description': 'Sublist with logical operators',
        },
        'par_cond': {
            'func_name': 'par_cond',
            'line_no': 2390,
            'rule': 'cond : cond_1 { SEPER } [ DBAR { SEPER } cond ]',
            'alternatives': ['cond_1', 'DBAR'],
            'tokens_in_rule': {'DBAR', 'SEPER'},
            'description': 'Conditional expression disjunction (OR)',
        },
        'par_cond_1': {
            'func_name': 'par_cond_1',
            'line_no': 2417,
            'rule': 'cond_1 : cond_2 { SEPER } [ DAMPER { SEPER } cond_1 ]',
            'alternatives': ['cond_2', 'DAMPER'],
            'tokens_in_rule': {'DAMPER', 'SEPER'},
            'description': 'Conditional expression conjunction (AND)',
        },
        'par_cond_2': {
            'func_name': 'par_cond_2',
            'line_no': 2455,
            'rule': (
                'cond_2 : BANG cond_2 '
                '| INPAR { SEPER } cond_2 { SEPER } OUTPAR '
                '| STRING STRING STRING '
                '| STRING STRING '
                '| STRING ( INANG | OUTANG ) STRING'
            ),
            'alternatives': [
                'BANG cond_2',
                'INPAR { SEPER } cond_2 { SEPER } OUTPAR',
                'STRING STRING STRING',
                'STRING STRING',
                'STRING ( INANG | OUTANG ) STRING',
            ],
            'tokens_in_rule': {
                'BANG',
                'INPAR',
                'OUTPAR',
                'INANG',
                'OUTANG',
                'STRING',
                'SEPER',
            },
            'description': 'Conditional base cases and unary operators',
        },
    }

    return rules


def build_grammar_rules(
    parser_functions: dict[str, _FunctionNode],
    call_graph: dict[str, _FunctionNode],
    extracted_tokens: dict[str, list[TokenOrCall]],
    validation_results: dict[str, dict[str, Any]] | None = None,
) -> dict[str, GrammarNode]:
    """
    Build grammar rules from extracted token sequences.

    Takes extracted token sequences and validation results, then constructs
    proper grammar rules for each parser function discovered via AST analysis.

    Strategy (AST-centric):
    1. Iterate over ALL parser functions in call_graph (discovered from C code)
    2. Get source info from parser_functions (.syms metadata) if available
    3. For each parser function:
       - If has token_sequences: convert via sequence_to_rule()
       - Otherwise: create placeholder rule referencing the function

    Generates rules for:
    1. Parser functions with extracted token sequences (primary)
    2. Parser functions without sequences (placeholder rules)

    This approach ensures all parser functions found in the actual C code are
    included in the grammar, not just those declared in parse.syms. Functions
    like parse_string (exec.c), parse_subscript (lex.c), etc. are discovered
    from AST analysis and get rules via this mechanism.

    Args:
        parser_functions: Map of parser function definitions from .syms files
                         (used for metadata like visibility and signature)
        call_graph: Map of ALL functions discovered from C file AST analysis
                   (primary source for building rules)
        extracted_tokens: Map of function names to token sequences
        validation_results: Optional validation results for confidence scoring

    Returns:
        Dict mapping rule names to GrammarNode definitions
    """
    rules: dict[str, GrammarNode] = {}

    # Generate rules for ALL parser functions found in call_graph (from AST)
    # This includes functions from parse.c, lex.c, exec.c, etc.
    for func_name in call_graph:
        if not _is_parser_function(func_name):
            continue

        rule_name = _function_to_rule_name(func_name)

        # Check if this function has extracted sequences
        if sequences := extracted_tokens.get(func_name):
            # Convert sequences to rules
            # For now, combine into a single rule if multiple sequences exist
            # (Future: distinguish alternatives via union nodes)
            rule = sequence_to_rule(sequences, func_name=func_name)
            rules[rule_name] = rule
        else:
            # No extracted sequences - create placeholder rule
            # This handles functions where token extraction failed or was not applicable
            rules[rule_name] = create_ref(
                rule_name,
                description=f'Parser function {func_name} (no sequences extracted)',
            )

    return rules


def embed_lexer_state_conditions(
    grammar: dict[str, GrammarNode],
    lexer_state_info: dict[str, dict[str, list[int]]] | None,
) -> dict[str, GrammarNode]:
    """
    Embed lexer state conditions into grammar rules.

    Some parser functions switch lexer states before/after parsing.
    This embeds those conditions into the grammar for documentation.

    Args:
        grammar: Base grammar structure
        lexer_state_info: Map of function names to state changes

    Returns:
        Grammar with embedded state information
    """
    if not lexer_state_info:
        return grammar

    # TODO: Implement lexer state embedding
    # This would add LexState nodes to rules that change state
    return grammar


def _function_to_rule_name(func_name: str, /) -> str:
    """
    Convert function name to grammar rule name.

    - par_for → for
    - parse_list → list
    - par_cond_double → cond_double
    """
    if func_name.startswith('par_'):
        return func_name[4:]  # Remove 'par_' prefix
    if func_name.startswith('parse_'):
        return func_name[6:]  # Remove 'parse_' prefix
    return func_name


def _build_func_to_rule_map(  # pyright: ignore[reportUnusedFunction]
    parser_functions: dict[str, _FunctionNode], /
) -> dict[str, str]:
    """
    Build a mapping from parser function names to rule names.

    Iterates through parser functions and converts function names to rule names
    using standard naming conventions.
    """
    func_to_rule: dict[str, str] = {}
    for func_name in parser_functions:
        if _is_parser_function(func_name):
            rule_name = _function_to_rule_name(func_name)
            func_to_rule[func_name] = rule_name
    return func_to_rule
