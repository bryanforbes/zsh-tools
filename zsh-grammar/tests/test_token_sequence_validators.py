"""Tests for TokenSequenceValidator from Phase 2.4.1.

Validates that the validator framework correctly detects structural issues
in token sequences before rule generation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from zsh_grammar.token_sequence_validators import TokenSequenceValidator

if TYPE_CHECKING:
    from zsh_grammar._types import (
        ControlFlowBranch,
        ControlFlowBranchType,
        FunctionNodeEnhanced,
    )


class TestValidateContiguousIndices:
    """Tests for sequence index contiguity validation."""

    def test_valid_contiguous_indices(self) -> None:
        """Contiguous indices 0, 1, 2, 3 should pass."""
        validator = TokenSequenceValidator()
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',
            'condition': 'tok == INPAR',
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

        errors = validator.validate_branch(branch)
        assert len(errors) == 0

    def test_non_contiguous_indices_with_gap(self) -> None:
        """Non-contiguous indices (0, 2) should error."""
        validator = TokenSequenceValidator()
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',
            'condition': 'tok == INPAR',
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
                    'sequence_index': 2,  # Gap!
                },
            ],
        }

        errors = validator.validate_branch(branch)
        assert any('Non-contiguous' in e for e in errors)

    def test_non_contiguous_indices_out_of_order(self) -> None:
        """Out-of-order indices should error."""
        validator = TokenSequenceValidator()
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',
            'condition': 'tok == INPAR',
            'start_line': 100,
            'end_line': 150,
            'items': [
                {
                    'kind': 'token',
                    'token_name': 'INPAR',
                    'line': 101,
                    'is_negated': False,
                    'branch_id': 'if_1',
                    'sequence_index': 1,
                },
                {
                    'kind': 'call',
                    'func_name': 'par_list',
                    'line': 102,
                    'branch_id': 'if_1',
                    'sequence_index': 0,  # Out of order
                },
            ],
        }

        errors = validator.validate_branch(branch)
        assert any('Out-of-order' in e for e in errors)


class TestValidateLineMonotonicity:
    """Tests for line number monotonicity validation."""

    def test_valid_monotonic_lines(self) -> None:
        """Increasing line numbers should pass."""
        validator = TokenSequenceValidator()
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',
            'condition': 'tok == INPAR',
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
                    'line': 125,
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

        errors = validator.validate_branch(branch)
        assert not any('Non-monotonic' in e for e in errors)

    def test_non_monotonic_lines_decreasing(self) -> None:
        """Decreasing line numbers should error."""
        validator = TokenSequenceValidator()
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',
            'condition': 'tok == INPAR',
            'start_line': 100,
            'end_line': 150,
            'items': [
                {
                    'kind': 'token',
                    'token_name': 'INPAR',
                    'line': 150,
                    'is_negated': False,
                    'branch_id': 'if_1',
                    'sequence_index': 0,
                },
                {
                    'kind': 'call',
                    'func_name': 'par_list',
                    'line': 100,  # Decreasing!
                    'branch_id': 'if_1',
                    'sequence_index': 1,
                },
            ],
        }

        errors = validator.validate_branch(branch)
        assert any('Non-monotonic' in e for e in errors)


class TestValidateBranchIdConsistency:
    """Tests for branch_id consistency within items."""

    def test_consistent_branch_ids(self) -> None:
        """All items should match branch branch_id."""
        validator = TokenSequenceValidator()
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',
            'condition': 'tok == INPAR',
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
                    'line': 125,
                    'branch_id': 'if_1',
                    'sequence_index': 1,
                },
            ],
        }

        errors = validator.validate_branch(branch)
        assert not any('branch_id mismatch' in e for e in errors)

    def test_inconsistent_branch_ids(self) -> None:
        """Items with mismatched branch_ids should error."""
        validator = TokenSequenceValidator()
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',
            'condition': 'tok == INPAR',
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
                    'line': 125,
                    'branch_id': 'else_if_1',  # Mismatch!
                    'sequence_index': 1,
                },
            ],
        }

        errors = validator.validate_branch(branch)
        assert any('branch_id mismatch' in e for e in errors)


class TestValidateBranchType:
    """Tests for branch_type validation."""

    def test_valid_branch_types(self) -> None:
        """All valid branch types should pass."""
        validator = TokenSequenceValidator()
        valid_types: list[ControlFlowBranchType] = [
            'if',
            'else_if',
            'else',
            'switch_case',
            'loop',
            'sequential',
        ]

        for branch_type in valid_types:
            # Conditional types require condition
            if branch_type in {'if', 'else_if', 'switch_case'}:
                branch: ControlFlowBranch = {
                    'branch_id': f'test_{branch_type}',
                    'branch_type': branch_type,
                    'condition': 'test',
                    'start_line': 100,
                    'end_line': 150,
                    'items': [],
                }
            else:
                branch = {
                    'branch_id': f'test_{branch_type}',
                    'branch_type': branch_type,
                    'start_line': 100,
                    'end_line': 150,
                    'items': [],
                }

            errors = validator.validate_branch(branch)
            assert not any('Invalid branch_type' in e for e in errors)

    def test_invalid_branch_type(self) -> None:
        """Invalid branch_type should error."""
        validator = TokenSequenceValidator()
        branch = cast(
            'ControlFlowBranch',
            {
                'branch_id': 'test_bad',
                'branch_type': 'bad_type',
                'start_line': 100,
                'end_line': 150,
                'items': [],
            },
        )

        errors = validator.validate_branch(branch)
        assert any('Invalid branch_type' in e for e in errors)


class TestValidateConditionalRequirements:
    """Tests for conditional branch type requirements."""

    def test_if_branch_requires_condition(self) -> None:
        """if branch without condition should error."""
        validator = TokenSequenceValidator()
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',
            'start_line': 100,
            'end_line': 150,
            'items': [],
        }

        errors = validator.validate_branch(branch)
        assert any('requires' in e.lower() and 'condition' in e.lower() for e in errors)

    def test_else_if_branch_requires_condition(self) -> None:
        """else_if branch without condition should error."""
        validator = TokenSequenceValidator()
        branch: ControlFlowBranch = {
            'branch_id': 'else_if_1',
            'branch_type': 'else_if',
            'start_line': 100,
            'end_line': 150,
            'items': [],
        }

        errors = validator.validate_branch(branch)
        assert any('requires' in e.lower() and 'condition' in e.lower() for e in errors)

    def test_loop_branch_does_not_require_condition(self) -> None:
        """loop branch without condition should not error."""
        validator = TokenSequenceValidator()
        branch: ControlFlowBranch = {
            'branch_id': 'loop',
            'branch_type': 'loop',
            'start_line': 100,
            'end_line': 150,
            'items': [],
        }

        errors = validator.validate_branch(branch)
        assert not any(
            'requires' in e.lower() and 'condition' in e.lower() for e in errors
        )


class TestValidateAllSequences:
    """Tests for validate_all_sequences method."""

    def test_validate_all_sequences_valid_node(self) -> None:
        """Valid node should have no errors."""
        validator = TokenSequenceValidator()
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
                        }
                    ],
                }
            ],
            'has_loops': False,
            'is_optional': False,
        }

        errors = validator.validate_all_sequences(node)
        assert len(errors) == 0

    def test_validate_all_sequences_empty_token_sequences(self) -> None:
        """Node with empty token_sequences should error."""
        validator = TokenSequenceValidator()
        node: FunctionNodeEnhanced = {
            'name': 'par_subsh',
            'file': 'parse.c',
            'line': 1630,
            'calls': ['par_list'],
            'token_sequences': [],
            'has_loops': False,
            'is_optional': False,
        }

        errors = validator.validate_all_sequences(node)
        assert '_global' in errors
        assert any('No token_sequences' in e for e in errors['_global'])

    def test_validate_all_sequences_duplicate_branch_ids(self) -> None:
        """Duplicate branch IDs should error."""
        validator = TokenSequenceValidator()
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
                    'start_line': 100,
                    'end_line': 150,
                    'items': [],
                },
                {
                    'branch_id': 'if_1',  # Duplicate!
                    'branch_type': 'else_if',
                    'condition': 'tok == INBRACE',
                    'start_line': 151,
                    'end_line': 200,
                    'items': [],
                },
            ],
            'has_loops': False,
            'is_optional': False,
        }

        errors = validator.validate_all_sequences(node)
        assert any(
            'Duplicate' in str(e)
            for e in errors.values()
            for e in (e if isinstance(e, list) else [e])
        )


class TestValidateSequenceIndexConsistency:
    """Tests for validate_sequence_index_consistency helper."""

    def test_sequence_index_consistency_valid(self) -> None:
        """Contiguous indices from 0 should return True."""
        validator = TokenSequenceValidator()
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',
            'condition': 'test',
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
                    'line': 125,
                    'branch_id': 'if_1',
                    'sequence_index': 1,
                },
            ],
        }

        assert validator.validate_sequence_index_consistency(branch) is True

    def test_sequence_index_consistency_invalid(self) -> None:
        """Non-contiguous indices should return False."""
        validator = TokenSequenceValidator()
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',
            'condition': 'test',
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
                    'line': 125,
                    'branch_id': 'if_1',
                    'sequence_index': 2,
                },
            ],
        }

        assert validator.validate_sequence_index_consistency(branch) is False


class TestValidateLineMonotonicityHelper:
    """Tests for validate_line_monotonicity helper."""

    def test_line_monotonicity_valid(self) -> None:
        """Increasing line numbers should return True."""
        validator = TokenSequenceValidator()
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',
            'condition': 'test',
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
                    'line': 125,
                    'branch_id': 'if_1',
                    'sequence_index': 1,
                },
            ],
        }

        assert validator.validate_line_monotonicity(branch) is True

    def test_line_monotonicity_invalid(self) -> None:
        """Non-increasing line numbers should return False."""
        validator = TokenSequenceValidator()
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',
            'condition': 'test',
            'start_line': 100,
            'end_line': 150,
            'items': [
                {
                    'kind': 'token',
                    'token_name': 'INPAR',
                    'line': 125,
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
            ],
        }

        assert validator.validate_line_monotonicity(branch) is False
