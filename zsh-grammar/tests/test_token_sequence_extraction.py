"""Test harness for Phase 2.4.1 token sequence extraction.

These tests establish expected input/output examples for token sequence extraction
before the extraction logic is implemented. They serve as specification for Stages 1-2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zsh_grammar._types import ControlFlowBranch


class TestParSubshTokenSequences:
    """Test token sequence extraction for par_subsh.

    Semantic grammar: INPAR list OUTPAR | INBRACE list OUTBRACE [ "always" ... ]
    Expected: Two branches for ( ) vs { } alternatives, each with tokens and calls.
    """

    def test_par_subsh_branch_if_inpar(self) -> None:
        """INPAR branch: ( list )"""
        expected_branch: ControlFlowBranch = {
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

        assert expected_branch['branch_type'] == 'if'
        assert expected_branch['token_condition'] == 'INPAR'  # noqa: S105
        assert len(expected_branch['items']) == 3
        assert expected_branch['items'][1]['kind'] == 'call'

    def test_par_subsh_branch_else_if_inbrace(self) -> None:
        """INBRACE branch: { list }"""
        expected_branch: ControlFlowBranch = {
            'branch_id': 'else_if_1',
            'branch_type': 'else_if',
            'condition': 'tok == INBRACE',
            'token_condition': 'INBRACE',
            'start_line': 1651,
            'end_line': 1665,
            'items': [
                {
                    'kind': 'token',
                    'token_name': 'INBRACE',
                    'line': 1652,
                    'is_negated': False,
                    'branch_id': 'else_if_1',
                    'sequence_index': 0,
                },
                {
                    'kind': 'call',
                    'func_name': 'par_list',
                    'line': 1655,
                    'branch_id': 'else_if_1',
                    'sequence_index': 1,
                },
                {
                    'kind': 'token',
                    'token_name': 'OUTBRACE',
                    'line': 1661,
                    'is_negated': False,
                    'branch_id': 'else_if_1',
                    'sequence_index': 2,
                },
            ],
        }

        assert expected_branch['branch_type'] == 'else_if'
        assert expected_branch['token_condition'] == 'INBRACE'  # noqa: S105
        assert len(expected_branch['items']) == 3

    def test_par_subsh_union_rule_structure(self) -> None:
        """After extraction, par_subsh should produce Union[Sequence, Sequence]."""
        expected_rule = {
            'union': [
                {
                    'sequence': [
                        {'$ref': 'INPAR'},
                        {'$ref': 'list'},
                        {'$ref': 'OUTPAR'},
                    ]
                },
                {
                    'sequence': [
                        {'$ref': 'INBRACE'},
                        {'$ref': 'list'},
                        {'$ref': 'OUTBRACE'},
                    ]
                },
            ]
        }

        assert expected_rule['union'][0]['sequence'][0] == {'$ref': 'INPAR'}
        assert expected_rule['union'][0]['sequence'][1] == {'$ref': 'list'}
        assert expected_rule['union'][1]['sequence'][2] == {'$ref': 'OUTBRACE'}


class TestParIfTokenSequences:
    """Test token sequence extraction for par_if.

    Semantic grammar: IF cond THEN list ... | ... ELSE list ... | ... FI
    Expected: Multiple branches for IF/ELIF/ELSE, each with condition and body.
    """

    def test_par_if_has_multiple_branches(self) -> None:
        """par_if should have IF, ELIF, ELSE branches."""
        # Placeholder: full test once extraction is implemented

    def test_par_if_branch_structure(self) -> None:
        """Each if/elif/else branch should have token-call-token pattern."""
        # Placeholder: full test once extraction is implemented


class TestParCaseTokenSequences:
    """Test token sequence extraction for par_case.

    Semantic grammar: CASE word { (pattern) list } ESAC
    Expected: Sequential (CASE, word, loop(pattern, list)) with loop model.
    """

    def test_par_case_has_loop_branch(self) -> None:
        """par_case should have loop branch for case alternatives."""
        # Placeholder: full test once extraction is implemented

    def test_par_case_loop_items(self) -> None:
        """Loop branch should have pattern and list calls in sequence."""
        # Placeholder: full test once extraction is implemented


class TestParForTokenSequences:
    """Test token sequence extraction for par_for.

    Semantic: FOR var ( { word } | '(' cond ';' advance ')' ) DO list DONE
    Expected: Sequential with optional inner groups.
    """

    def test_par_for_has_for_token(self) -> None:
        """par_for should start with FOR token."""
        # Placeholder: full test once extraction is implemented

    def test_par_for_optional_structure(self) -> None:
        """par_for should have optional branches for different loop syntax."""
        # Placeholder: full test once extraction is implemented
