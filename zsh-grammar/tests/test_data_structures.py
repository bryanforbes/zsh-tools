"""Tests for Phase 2.4.1 enhanced data structures.

Validates that TypedDict structures are correctly defined and support
discriminated unions and branch context information.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zsh_grammar._types import (
        ControlFlowBranch,
        ControlFlowBranchType,
        FunctionCallEnhanced,
        FunctionNodeEnhanced,
        SyntheticTokenEnhanced,
        TokenCheckEnhanced,
        TokenOrCallEnhanced,
    )


class TestTokenCheckEnhanced:
    """Tests for TokenCheckEnhanced structure."""

    def test_token_check_enhanced_required_fields(self) -> None:
        """All required fields must be present."""
        item: TokenCheckEnhanced = {
            'kind': 'token',
            'token_name': 'INPAR',
            'line': 1234,
            'is_negated': False,
            'branch_id': 'if_1',
            'sequence_index': 0,
        }

        assert item['kind'] == 'token'
        assert item['token_name'] == 'INPAR'  # noqa: S105
        assert item['line'] == 1234
        assert item['is_negated'] is False
        assert item['branch_id'] == 'if_1'
        assert item['sequence_index'] == 0

    def test_token_check_enhanced_is_negated_true(self) -> None:
        """is_negated should support True."""
        item: TokenCheckEnhanced = {
            'kind': 'token',
            'token_name': 'EOF',
            'line': 500,
            'is_negated': True,
            'branch_id': 'if_2',
            'sequence_index': 3,
        }

        assert item['is_negated'] is True

    def test_token_check_enhanced_branch_id_formats(self) -> None:
        """branch_id should support various formats."""
        for branch_id in ['if_1', 'else_if_2', 'switch_case_FOR', 'loop', 'sequential']:
            item: TokenCheckEnhanced = {
                'kind': 'token',
                'token_name': 'INPAR',
                'line': 100,
                'is_negated': False,
                'branch_id': branch_id,
                'sequence_index': 0,
            }
            assert item['branch_id'] == branch_id


class TestFunctionCallEnhanced:
    """Tests for FunctionCallEnhanced structure."""

    def test_function_call_enhanced_required_fields(self) -> None:
        """All required fields must be present."""
        item: FunctionCallEnhanced = {
            'kind': 'call',
            'func_name': 'par_list',
            'line': 1235,
            'branch_id': 'if_1',
            'sequence_index': 1,
        }

        assert item['kind'] == 'call'
        assert item['func_name'] == 'par_list'
        assert item['line'] == 1235
        assert item['branch_id'] == 'if_1'
        assert item['sequence_index'] == 1

    def test_function_call_enhanced_parser_function_names(self) -> None:
        """func_name should support various parser function names."""
        func_names = [
            'par_list',
            'par_if',
            'par_case',
            'par_for',
            'par_while',
            'par_term',
            'par_cmd',
        ]

        for func_name in func_names:
            item: FunctionCallEnhanced = {
                'kind': 'call',
                'func_name': func_name,
                'line': 100,
                'branch_id': 'if_1',
                'sequence_index': 0,
            }
            assert item['func_name'] == func_name


class TestSyntheticTokenEnhanced:
    """Tests for SyntheticTokenEnhanced structure."""

    def test_synthetic_token_enhanced_required_fields(self) -> None:
        """All required fields must be present."""
        item: SyntheticTokenEnhanced = {
            'kind': 'synthetic_token',
            'token_name': 'ALWAYS',
            'line': 1660,
            'condition': 'tok == STRING && !strcmp(tokstr, "always")',
            'branch_id': 'if_1',
            'sequence_index': 3,
            'is_optional': True,
        }

        assert item['kind'] == 'synthetic_token'
        assert item['token_name'] == 'ALWAYS'  # noqa: S105
        assert item['line'] == 1660
        assert item['condition'] == 'tok == STRING && !strcmp(tokstr, "always")'
        assert item['branch_id'] == 'if_1'
        assert item['sequence_index'] == 3
        assert item['is_optional'] is True

    def test_synthetic_token_enhanced_is_optional_false(self) -> None:
        """is_optional should support False."""
        item: SyntheticTokenEnhanced = {
            'kind': 'synthetic_token',
            'token_name': 'ALWAYS',
            'line': 1660,
            'condition': 'tok == STRING && !strcmp(tokstr, "always")',
            'branch_id': 'if_1',
            'sequence_index': 3,
            'is_optional': False,
        }

        assert item['is_optional'] is False


class TestTokenOrCallEnhancedDiscriminatedUnion:
    """Tests for TokenOrCallEnhanced discriminated union."""

    def test_token_or_call_enhanced_token(self) -> None:
        """TokenOrCallEnhanced should accept TokenCheckEnhanced."""
        item: TokenOrCallEnhanced = {
            'kind': 'token',
            'token_name': 'INPAR',
            'line': 1234,
            'is_negated': False,
            'branch_id': 'if_1',
            'sequence_index': 0,
        }
        assert item['kind'] == 'token'

    def test_token_or_call_enhanced_call(self) -> None:
        """TokenOrCallEnhanced should accept FunctionCallEnhanced."""
        item: TokenOrCallEnhanced = {
            'kind': 'call',
            'func_name': 'par_list',
            'line': 1235,
            'branch_id': 'if_1',
            'sequence_index': 1,
        }
        assert item['kind'] == 'call'

    def test_token_or_call_enhanced_synthetic(self) -> None:
        """TokenOrCallEnhanced should accept SyntheticTokenEnhanced."""
        item: TokenOrCallEnhanced = {
            'kind': 'synthetic_token',
            'token_name': 'ALWAYS',
            'line': 1660,
            'condition': 'tok == STRING && !strcmp(tokstr, "always")',
            'branch_id': 'if_1',
            'sequence_index': 3,
            'is_optional': True,
        }
        assert item['kind'] == 'synthetic_token'

    def test_token_or_call_enhanced_discriminator_required(self) -> None:
        """All items must have 'kind' field for discrimination."""
        # Valid items all have 'kind'
        items: list[TokenOrCallEnhanced] = [
            {
                'kind': 'token',
                'token_name': 'INPAR',
                'line': 100,
                'is_negated': False,
                'branch_id': 'if_1',
                'sequence_index': 0,
            },
            {
                'kind': 'call',
                'func_name': 'par_list',
                'line': 101,
                'branch_id': 'if_1',
                'sequence_index': 1,
            },
            {
                'kind': 'synthetic_token',
                'token_name': 'ALWAYS',
                'line': 102,
                'condition': 'cond',
                'branch_id': 'if_1',
                'sequence_index': 2,
                'is_optional': False,
            },
        ]

        for item in items:
            assert 'kind' in item


class TestControlFlowBranch:
    """Tests for ControlFlowBranch structure."""

    def test_control_flow_branch_if_with_condition(self) -> None:
        """if branch should have condition."""
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',
            'condition': 'tok == INPAR',
            'token_condition': 'INPAR',
            'start_line': 100,
            'end_line': 150,
            'items': [
                {
                    'kind': 'token',
                    'token_name': 'INPAR',
                    'line': 101,
                    'is_negated': False,
                    'branch_id': 'if_1',
                    'sequence_index': 0,
                },
                {
                    'kind': 'call',
                    'func_name': 'par_list',
                    'line': 102,
                    'branch_id': 'if_1',
                    'sequence_index': 1,
                },
                {
                    'kind': 'token',
                    'token_name': 'OUTPAR',
                    'line': 150,
                    'is_negated': False,
                    'branch_id': 'if_1',
                    'sequence_index': 2,
                },
            ],
        }

        assert branch['branch_type'] == 'if'
        assert branch['condition'] == 'tok == INPAR'
        assert branch['token_condition'] == 'INPAR'  # noqa: S105
        assert len(branch['items']) == 3

    def test_control_flow_branch_loop(self) -> None:
        """loop branch should not require condition."""
        branch: ControlFlowBranch = {
            'branch_id': 'loop',
            'branch_type': 'loop',
            'start_line': 200,
            'end_line': 250,
            'items': [
                {
                    'kind': 'call',
                    'func_name': 'par_list',
                    'line': 210,
                    'branch_id': 'loop',
                    'sequence_index': 0,
                }
            ],
        }

        assert branch['branch_type'] == 'loop'
        assert 'condition' not in branch
        assert len(branch['items']) == 1

    def test_control_flow_branch_sequential(self) -> None:
        """sequential branch should not require condition."""
        branch: ControlFlowBranch = {
            'branch_id': 'sequential',
            'branch_type': 'sequential',
            'start_line': 100,
            'end_line': 200,
            'items': [],
        }

        assert branch['branch_type'] == 'sequential'
        assert 'condition' not in branch

    def test_control_flow_branch_all_types(self) -> None:
        """All branch_type variants should be supported."""
        branch_types: list[ControlFlowBranchType] = [
            'if',
            'else_if',
            'else',
            'switch_case',
            'loop',
            'sequential',
        ]

        for branch_type in branch_types:
            # Conditional branches require condition
            if branch_type in {'if', 'else_if', 'switch_case'}:
                branch: ControlFlowBranch = {
                    'branch_id': f'test_{branch_type}',
                    'branch_type': branch_type,
                    'condition': 'test_condition',
                    'start_line': 100,
                    'end_line': 200,
                    'items': [],
                }
            else:
                branch = {
                    'branch_id': f'test_{branch_type}',
                    'branch_type': branch_type,
                    'start_line': 100,
                    'end_line': 200,
                    'items': [],
                }

            assert branch['branch_type'] == branch_type


class TestFunctionNodeEnhanced:
    """Tests for FunctionNodeEnhanced structure."""

    def test_function_node_enhanced_basic(self) -> None:
        """FunctionNodeEnhanced with single branch."""
        node: FunctionNodeEnhanced = {
            'name': 'par_subsh',
            'file': 'parse.c',
            'line': 1630,
            'calls': ['par_list'],
            'token_sequences': [
                {
                    'branch_id': 'if_1',
                    'branch_type': 'if',
                    'condition': 'tok == INPAR',
                    'token_condition': 'INPAR',
                    'start_line': 1630,
                    'end_line': 1650,
                    'items': [
                        {
                            'kind': 'token',
                            'token_name': 'INPAR',
                            'line': 1631,
                            'is_negated': False,
                            'branch_id': 'if_1',
                            'sequence_index': 0,
                        },
                        {
                            'kind': 'call',
                            'func_name': 'par_list',
                            'line': 1635,
                            'branch_id': 'if_1',
                            'sequence_index': 1,
                        },
                        {
                            'kind': 'token',
                            'token_name': 'OUTPAR',
                            'line': 1645,
                            'is_negated': False,
                            'branch_id': 'if_1',
                            'sequence_index': 2,
                        },
                    ],
                }
            ],
            'has_loops': False,
            'is_optional': False,
        }

        assert node['name'] == 'par_subsh'
        assert node['file'] == 'parse.c'
        assert len(node['token_sequences']) == 1
        assert node['has_loops'] is False
        assert node['is_optional'] is False

    def test_function_node_enhanced_multiple_branches(self) -> None:
        """FunctionNodeEnhanced with multiple branches."""
        node: FunctionNodeEnhanced = {
            'name': 'par_subsh',
            'file': 'parse.c',
            'line': 1630,
            'calls': ['par_list'],
            'token_sequences': [
                {
                    'branch_id': 'if_1',
                    'branch_type': 'if',
                    'condition': 'tok == INPAR',
                    'start_line': 1630,
                    'end_line': 1650,
                    'items': [],
                },
                {
                    'branch_id': 'else_if_1',
                    'branch_type': 'else_if',
                    'condition': 'tok == INBRACE',
                    'start_line': 1651,
                    'end_line': 1665,
                    'items': [],
                },
            ],
            'has_loops': False,
            'is_optional': False,
        }

        assert len(node['token_sequences']) == 2
        assert node['token_sequences'][0]['branch_id'] == 'if_1'
        assert node['token_sequences'][1]['branch_id'] == 'else_if_1'

    def test_function_node_enhanced_with_optional_fields(self) -> None:
        """FunctionNodeEnhanced should support optional fields."""
        node: FunctionNodeEnhanced = {
            'name': 'par_for',
            'file': 'parse.c',
            'line': 1400,
            'calls': ['par_list'],
            'token_sequences': [],
            'has_loops': True,
            'loop_type': 'for',
            'is_optional': True,
            'conditions': ['tok == FOR'],
            'signature': 'static int par_for(void)',
            'visibility': 'static',
        }

        assert node['loop_type'] == 'for'
        assert node['conditions'] == ['tok == FOR']
        assert node['signature'] == 'static int par_for(void)'
        assert node['visibility'] == 'static'
