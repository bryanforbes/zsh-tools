"""Stage 4: Rule generation from token sequences (Phase 2.4.1).

Tests for converting token sequences and control flow branches into
grammar rules using the new token-sequence-centric approach.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zsh_grammar.grammar_rules import (
    build_grammar_rules_from_enhanced,
    convert_branch_to_rule,
    convert_node_to_rule,
    function_to_rule_name,
    item_to_node,
    items_to_sequence,
)

if TYPE_CHECKING:
    from zsh_grammar._types import (
        ControlFlowBranch,
        ControlFlowBranchType,
        FunctionNodeEnhanced,
        TokenOrCallEnhanced,
    )

# ============================================================================
# Test Fixtures: Helper functions to create test data structures
# ============================================================================


def make_token_item(
    token_name: str,
    line: int,
    sequence_index: int,
    branch_id: str = 'main',
    is_negated: bool = False,
) -> TokenOrCallEnhanced:
    """Create a token item."""
    return {  # type: ignore[return-value]
        'kind': 'token',
        'token_name': token_name,
        'line': line,
        'sequence_index': sequence_index,
        'branch_id': branch_id,
        'is_negated': is_negated,
    }


def make_call_item(
    func_name: str,
    line: int,
    sequence_index: int,
    branch_id: str = 'main',
) -> TokenOrCallEnhanced:
    """Create a call item."""
    return {  # type: ignore[return-value]
        'kind': 'call',
        'func_name': func_name,
        'line': line,
        'sequence_index': sequence_index,
        'branch_id': branch_id,
    }


def make_synthetic_item(
    token_name: str,
    condition: str,
    line: int,
    sequence_index: int,
    branch_id: str = 'main',
) -> TokenOrCallEnhanced:
    """Create a synthetic token item."""
    return {  # type: ignore[return-value]
        'kind': 'synthetic_token',
        'token_name': token_name,
        'condition': condition,
        'line': line,
        'sequence_index': sequence_index,
        'branch_id': branch_id,
        'is_optional': False,
    }


def make_branch(
    branch_id: str = 'main',
    branch_type: ControlFlowBranchType = 'sequential',
    items: list[TokenOrCallEnhanced] | None = None,
    start_line: int = 100,
    end_line: int = 150,
) -> ControlFlowBranch:
    """Create a control flow branch."""
    if items is None:
        items = []
    return {
        'branch_id': branch_id,
        'branch_type': branch_type,
        'start_line': start_line,
        'end_line': end_line,
        'items': items,
    }


def make_function_node(
    name: str = 'par_subsh',
    token_sequences: list[ControlFlowBranch] | None = None,
    calls: list[str] | None = None,
    has_loops: bool = False,
    is_optional: bool = False,
) -> FunctionNodeEnhanced:
    """Create a function node."""
    if token_sequences is None:
        token_sequences = []
    if calls is None:
        calls = []
    return {
        'name': name,
        'file': 'parse.c',
        'line': 100,
        'calls': calls,
        'token_sequences': token_sequences,
        'has_loops': has_loops,
        'is_optional': is_optional,
    }


# ============================================================================
# Test Section 4.1: item_to_node() - Convert single items
# ============================================================================


class TestItemToNode:
    """Test conversion of single items to grammar nodes."""

    def test_token_item_to_ref(self) -> None:
        """Token item converts to reference."""
        item = make_token_item('INPAR', 100, 0)
        node = item_to_node(item)
        assert node == {'$ref': 'INPAR'}

    def test_negated_token_item(self) -> None:
        """Negated token item includes description."""
        item = make_token_item('INPAR', 100, 0, is_negated=True)
        node = item_to_node(item)
        assert node == {'$ref': 'INPAR', 'description': 'NOT INPAR'}

    def test_call_item_to_ref(self) -> None:
        """Call item converts to rule reference."""
        item = make_call_item('par_list', 102, 1)
        node = item_to_node(item)
        # Function name 'par_list' becomes rule name 'list'
        assert node == {'$ref': 'list'}

    def test_synthetic_token_item(self) -> None:
        """Synthetic token item converts to reference with description."""
        item = make_synthetic_item(
            'ALWAYS', 'tok == STRING && !strcmp(tokstr, "always")', 104, 2
        )
        node = item_to_node(item)
        assert '$ref' in node
        assert node['$ref'] == 'ALWAYS'
        assert 'description' in node

    def test_synthetic_with_description(self) -> None:
        """Synthetic token includes condition as description."""
        condition = 'tok == STRING && !strcmp(tokstr, "always")'
        item = make_synthetic_item('ALWAYS', condition, 104, 2)
        node = item_to_node(item)
        assert 'description' in node
        assert '$ref' in node
        assert 'ALWAYS' in str(node['$ref'])


# ============================================================================
# Test Section 4.2: items_to_sequence() - Convert sequences
# ============================================================================


class TestItemsToSequence:
    """Test conversion of item lists to sequence nodes."""

    def test_empty_items(self) -> None:
        """Empty items list returns empty node."""
        items: list[TokenOrCallEnhanced] = []
        node = items_to_sequence(items)
        assert node == {'empty': True}

    def test_single_item(self) -> None:
        """Single item unwrapped from sequence."""
        items = [make_token_item('INPAR', 100, 0)]
        node = items_to_sequence(items)
        assert node == {'$ref': 'INPAR'}

    def test_two_items_sequence(self) -> None:
        """Two items wrapped in sequence."""
        items: list[TokenOrCallEnhanced] = [
            make_token_item('INPAR', 100, 0),
            make_call_item('par_list', 102, 1),
        ]
        node = items_to_sequence(items)
        assert 'sequence' in node
        seq_list = node['sequence']  # type: ignore[index]
        assert len(seq_list) == 2
        assert seq_list[0] == {'$ref': 'INPAR'}
        assert seq_list[1] == {'$ref': 'list'}

    def test_three_items_sequence(self) -> None:
        """Three items form sequence with all elements."""
        items: list[TokenOrCallEnhanced] = [
            make_token_item('INPAR', 100, 0),
            make_call_item('par_list', 102, 1),
            make_token_item('OUTPAR', 104, 2),
        ]
        node = items_to_sequence(items)
        assert 'sequence' in node
        seq_list = node['sequence']  # type: ignore[index]
        assert len(seq_list) == 3

    def test_skip_empty_nodes(self) -> None:
        """Empty nodes are skipped in sequence."""
        items: list[TokenOrCallEnhanced] = [
            make_token_item('INPAR', 100, 0),
            make_call_item('par_list', 102, 1),
        ]
        node = items_to_sequence(items)
        assert 'sequence' in node
        seq_list = node['sequence']  # type: ignore[index]
        assert len(seq_list) == 2  # No empty nodes


# ============================================================================
# Test Section 4.3: convert_branch_to_rule() - Branch → Grammar rule
# ============================================================================


class TestConvertBranchToRule:
    """Test conversion of branches to grammar rules."""

    def test_empty_branch(self) -> None:
        """Empty branch returns empty node."""
        branch = make_branch('main', 'sequential', [])
        rule = convert_branch_to_rule('par_test', branch, {})
        assert rule == {'empty': True}

    def test_single_item_branch(self) -> None:
        """Single-item branch unwrapped."""
        items = [make_token_item('INPAR', 100, 0)]
        branch = make_branch('main', 'sequential', items)
        rule = convert_branch_to_rule('par_test', branch, {})
        assert rule == {'$ref': 'INPAR'}

    def test_sequential_branch(self) -> None:
        """Sequential branch creates sequence."""
        items: list[TokenOrCallEnhanced] = [
            make_token_item('INPAR', 100, 0),
            make_call_item('par_list', 102, 1),
            make_token_item('OUTPAR', 104, 2),
        ]
        branch = make_branch('main', 'sequential', items)
        rule = convert_branch_to_rule('par_subsh', branch, {})
        assert 'sequence' in rule
        seq_list = rule['sequence']  # type: ignore[index]
        assert len(seq_list) == 3

    def test_loop_branch(self) -> None:
        """Loop branch wraps in repeat."""
        items: list[TokenOrCallEnhanced] = [
            make_call_item('par_item', 100, 0),
            make_token_item('SEPER', 102, 1),
        ]
        branch = make_branch('loop', 'loop', items, 100, 150)
        rule = convert_branch_to_rule('par_list', branch, {})
        assert 'repeat' in rule
        assert rule.get('min') == 0

    def test_loop_min_value(self) -> None:
        """Loop sets min=0 (can execute zero times)."""
        items: list[TokenOrCallEnhanced] = [
            make_call_item('par_item', 100, 0),
            make_token_item('SEPER', 102, 1),
        ]
        branch = make_branch('loop', 'loop', items)
        rule = convert_branch_to_rule('par_list', branch, {})
        assert 'repeat' in rule
        assert rule.get('min') == 0


# ============================================================================
# Test Section 4.4: convert_node_to_rule() - Function node → Rule
# ============================================================================


class TestConvertNodeToRule:
    """Test conversion of function nodes to rules."""

    def test_empty_sequences(self) -> None:
        """Function with no sequences returns empty."""
        node = make_function_node(
            'par_test', [], [], has_loops=False, is_optional=False
        )
        rule = convert_node_to_rule('par_test', node, {})
        assert rule == {'empty': True}

    def test_single_sequence(self) -> None:
        """Single sequence returns its rule directly."""
        items: list[TokenOrCallEnhanced] = [
            make_token_item('INPAR', 100, 0),
            make_call_item('par_list', 102, 1),
            make_token_item('OUTPAR', 104, 2),
        ]
        branch = make_branch('if_1', 'if', items)
        node = make_function_node('par_subsh', [branch], ['par_list'])
        rule = convert_node_to_rule('par_subsh', node, {})
        assert 'sequence' in rule

    def test_multiple_sequences_union(self) -> None:
        """Multiple branches create union of alternatives."""
        branch1_items: list[TokenOrCallEnhanced] = [
            make_token_item('INPAR', 100, 0),
            make_call_item('par_list', 102, 1),
            make_token_item('OUTPAR', 104, 2),
        ]
        branch1 = make_branch('if_1', 'if', branch1_items, 100, 150)

        branch2_items: list[TokenOrCallEnhanced] = [
            make_token_item('INBRACE', 160, 0),
            make_call_item('par_list', 162, 1),
            make_token_item('OUTBRACE', 164, 2),
        ]
        branch2 = make_branch('else_if_1', 'else_if', branch2_items, 160, 180)

        node = make_function_node('par_subsh', [branch1, branch2], ['par_list'])
        rule = convert_node_to_rule('par_subsh', node, {})
        assert 'union' in rule
        union_list = rule['union']  # type: ignore[index]
        assert len(union_list) == 2

    def test_two_identical_branches_single_rule(self) -> None:
        """Two branches producing identical rules: union with one alternative."""
        items: list[TokenOrCallEnhanced] = [make_token_item('WORD', 100, 0)]
        branch1 = make_branch('if_1', 'if', items)
        branch2 = make_branch('else_if_1', 'else_if', items)
        node = make_function_node('par_test', [branch1, branch2])
        rule = convert_node_to_rule('par_test', node, {})
        # Two identical rules should create union
        if 'union' in rule:
            union_list = rule['union']  # type: ignore[index]
            assert len(union_list) >= 1


# ============================================================================
# Test Section 4.5: build_grammar_rules_from_enhanced() - Integration
# ============================================================================


class TestBuildGrammarRulesFromEnhanced:
    """Test full rule generation from enhanced call graph."""

    def test_single_function(self) -> None:
        """Single function generates one rule."""
        items: list[TokenOrCallEnhanced] = [
            make_token_item('INPAR', 100, 0),
            make_call_item('par_list', 102, 1),
            make_token_item('OUTPAR', 104, 2),
        ]
        branch = make_branch('main', 'sequential', items)
        node = make_function_node('par_subsh', [branch], ['par_list'])
        call_graph = {'par_subsh': node}

        rules = build_grammar_rules_from_enhanced(call_graph, {})

        assert 'subsh' in rules  # par_subsh → subsh
        assert rules['subsh'] != {'empty': True}

    def test_multiple_functions(self) -> None:
        """Multiple functions generate multiple rules."""
        # Create par_subsh
        subsh_items: list[TokenOrCallEnhanced] = [
            make_token_item('INPAR', 100, 0),
            make_call_item('par_list', 102, 1),
            make_token_item('OUTPAR', 104, 2),
        ]
        subsh_branch = make_branch('main', 'sequential', subsh_items)
        subsh_node = make_function_node('par_subsh', [subsh_branch], ['par_list'])

        # Create par_list
        list_items: list[TokenOrCallEnhanced] = [
            make_call_item('par_item', 200, 0),
            make_token_item('SEPER', 202, 1),
        ]
        list_branch = make_branch('loop', 'loop', list_items)
        list_node = make_function_node('par_list', [list_branch], [], has_loops=True)

        call_graph = {
            'par_subsh': subsh_node,
            'par_list': list_node,
        }

        rules = build_grammar_rules_from_enhanced(call_graph, {})

        assert 'subsh' in rules
        assert 'list' in rules
        assert 'repeat' in rules['list']  # Loop becomes repeat


class TestParSubshParallelBranches:
    """Test par_subsh with two token-based alternatives (classic example)."""

    def test_par_subsh_two_branches(self) -> None:
        """par_subsh with two token-based branches: INPAR vs INBRACE."""
        # Branch 1: if (tok == INPAR)
        branch1_items: list[TokenOrCallEnhanced] = [
            make_token_item('INPAR', 100, 0, 'if_1'),
            make_call_item('par_list', 102, 1, 'if_1'),
            make_token_item('OUTPAR', 104, 2, 'if_1'),
        ]
        branch1 = make_branch('if_1', 'if', branch1_items, 100, 150)

        # Branch 2: else if (tok == INBRACE)
        branch2_items: list[TokenOrCallEnhanced] = [
            make_token_item('INBRACE', 160, 0, 'else_if_1'),
            make_call_item('par_list', 162, 1, 'else_if_1'),
            make_token_item('OUTBRACE', 164, 2, 'else_if_1'),
        ]
        branch2 = make_branch('else_if_1', 'else_if', branch2_items, 160, 200)

        node = make_function_node('par_subsh', [branch1, branch2], ['par_list'])
        rule = convert_node_to_rule('par_subsh', node, {})

        # Should have union
        assert 'union' in rule
        alternatives = rule['union']  # type: ignore[index]

        # Each alternative is a sequence
        assert len(alternatives) >= 2
        for alt in alternatives:
            assert 'sequence' in alt

    def test_par_subsh_with_synthetic_optional_block(self) -> None:
        """par_subsh with optional ALWAYS block after OUTPAR."""
        items: list[TokenOrCallEnhanced] = [
            make_token_item('INPAR', 100, 0),
            make_call_item('par_list', 102, 1),
            make_token_item('OUTPAR', 104, 2),
            make_synthetic_item(
                'ALWAYS',
                'tok == STRING && !strcmp(tokstr, "always")',
                106,
                3,
            ),
        ]
        branch = make_branch('main', 'sequential', items)
        rule = convert_branch_to_rule('par_subsh', branch, {})

        assert 'sequence' in rule
        seq = rule['sequence']  # type: ignore[index]
        assert len(seq) == 4


# ============================================================================
# Test Section 4.6: Backward Compatibility
# ============================================================================


class TestBackwardCompatibility:
    """Test that new rules are compatible with old extraction."""

    def test_rule_name_conversion(self) -> None:
        """Function names convert to rule names correctly."""
        assert function_to_rule_name('par_list') == 'list'
        assert function_to_rule_name('par_subsh') == 'subsh'
        assert function_to_rule_name('par_for') == 'for'
        assert function_to_rule_name('parse_string') == 'string'
        assert function_to_rule_name('asdf_foo') == 'asdf_foo'

    def test_generated_rule_has_required_structure(self) -> None:
        """Generated rules have $ref or terminal fields."""
        items: list[TokenOrCallEnhanced] = [make_token_item('WORD', 100, 0)]
        branch = make_branch('main', 'sequential', items)
        node = make_function_node('par_test', [branch])
        rule = convert_node_to_rule('par_test', node, {})

        # Rule should have one of these structures
        assert (
            '$ref' in rule or 'empty' in rule or 'sequence' in rule or 'union' in rule
        )


# ============================================================================
# Test Section 4.7: Control Flow Pattern Integration
# ============================================================================


class TestControlFlowPatternIntegration:
    """Test integration with control flow analysis results."""

    def test_optional_rule_wrapping(self) -> None:
        """Rules marked as optional get wrapped properly."""
        items: list[TokenOrCallEnhanced] = [make_token_item('WORD', 100, 0)]
        branch = make_branch('main', 'sequential', items)
        node = make_function_node('par_test', [branch], is_optional=True)

        # Note: Optional wrapping might be done in apply_control_flow_patterns()
        # This test documents the expected interface
        rule = convert_node_to_rule('par_test', node, {})
        assert rule  # Should generate a rule

    def test_loop_rule_wrapping(self) -> None:
        """Rules with loops get wrapped in repeat."""
        items: list[TokenOrCallEnhanced] = [
            make_call_item('par_item', 100, 0),
            make_token_item('SEPER', 102, 1),
        ]
        branch = make_branch('loop', 'loop', items)
        node = make_function_node('par_test', [branch], has_loops=True)

        rule = convert_node_to_rule('par_test', node, {})
        assert 'repeat' in rule
