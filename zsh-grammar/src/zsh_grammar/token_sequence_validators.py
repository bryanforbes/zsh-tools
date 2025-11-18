"""Validation framework for Phase 2.4.1 token sequences.

This module provides validators to ensure extracted token sequences are well-formed
before feeding them to rule generation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zsh_grammar._types import ControlFlowBranch, FunctionNode, FunctionNodeEnhanced


class TokenSequenceValidator:
    """Validates extracted token sequences against constraints."""

    def validate_branch(self, branch: ControlFlowBranch) -> list[str]:
        """Validate single branch for structural correctness.

        Checks:
        1. All items are TokenOrCallEnhanced discriminated union members
        2. Sequence indices are contiguous (0, 1, 2, ..., n)
        3. Line numbers are monotonic increasing
        4. Branch ID is unique within function
        5. Branch type is valid

        Args:
            branch: ControlFlowBranch to validate

        Returns:
            List of error messages (empty if valid)
        """
        errors: list[str] = []

        # Validate branch_type
        valid_types = {'if', 'else_if', 'else', 'switch_case', 'loop', 'sequential'}
        if branch['branch_type'] not in valid_types:
            errors.append(f'Invalid branch_type: {branch["branch_type"]}')

        # Check contiguity of sequence_index (must be in order, not just contain 0..n)
        indices = [item['sequence_index'] for item in branch['items']]
        expected = list(range(len(branch['items'])))
        if indices != expected:
            sorted_indices = sorted(indices)
            if sorted_indices != expected:
                errors.append(
                    f'Non-contiguous sequence indices: {indices} (expected {expected})'
                )
            else:
                errors.append(
                    f'Out-of-order sequence indices: {indices} (expected {expected})'
                )

        # Check line monotonicity
        lines = [item['line'] for item in branch['items']]
        if lines != sorted(lines):
            errors.append(f'Non-monotonic lines: {lines}')

        # Check branch_id is consistent within items
        for item in branch['items']:
            if item['branch_id'] != branch['branch_id']:
                errors.append(
                    f'Item branch_id mismatch: '
                    f'item has {item["branch_id"]}, branch has {branch["branch_id"]}'
                )

        # Validate conditional requirements
        if branch['branch_type'] in {'if', 'else_if', 'switch_case'} and (
            'condition' not in branch or not branch['condition']
        ):
            errors.append(
                f"Branch type {branch['branch_type']} requires 'condition' field"
            )

        return errors

    def validate_all_sequences(
        self,
        node: FunctionNodeEnhanced,
        token_mapping: dict[str, object] | None = None,
        parser_functions: dict[str, FunctionNode] | None = None,
    ) -> dict[str, list[str]]:
        """Validate all branches for a function.

        Args:
            node: FunctionNodeEnhanced to validate
            token_mapping: Optional mapping of token names to definitions
            parser_functions: Optional mapping of function names to FunctionNode

        Returns:
            Dictionary mapping branch_id to error lists (empty if valid)
        """
        errors_by_branch: dict[str, list[str]] = {}

        # Validate branches exist
        if not node['token_sequences']:
            errors_by_branch['_global'] = ['No token_sequences found']
            return errors_by_branch

        # Track branch IDs for uniqueness
        seen_branch_ids: set[str] = set()

        for branch in node['token_sequences']:
            branch_errors = self.validate_branch(branch)

            # Check branch ID uniqueness
            if branch['branch_id'] in seen_branch_ids:
                branch_errors.append(f'Duplicate branch_id: {branch["branch_id"]}')
            seen_branch_ids.add(branch['branch_id'])

            # Validate token and function references if mappings provided
            if token_mapping is not None or parser_functions is not None:
                for item in branch['items']:
                    if item['kind'] == 'token' and token_mapping:
                        if item['token_name'] not in token_mapping:
                            msg = (
                                f'Undefined token: {item["token_name"]} '
                                f'at line {item["line"]}'
                            )
                            branch_errors.append(msg)
                    elif (
                        item['kind'] == 'call'
                        and parser_functions
                        and item['func_name'] not in parser_functions
                    ):
                        msg = (
                            f'Undefined function: {item["func_name"]} '
                            f'at line {item["line"]}'
                        )
                        branch_errors.append(msg)

            if branch_errors:
                errors_by_branch[branch['branch_id']] = branch_errors

        return errors_by_branch

    def validate_sequence_index_consistency(self, branch: ControlFlowBranch) -> bool:
        """Check that sequence indices are contiguous starting from 0.

        Args:
            branch: ControlFlowBranch to check

        Returns:
            True if indices are contiguous, False otherwise
        """
        if not branch['items']:
            return True

        indices = [item['sequence_index'] for item in branch['items']]
        return indices == list(range(len(branch['items'])))

    def validate_line_monotonicity(self, branch: ControlFlowBranch) -> bool:
        """Check that line numbers are monotonically increasing.

        Args:
            branch: ControlFlowBranch to check

        Returns:
            True if lines are increasing, False otherwise
        """
        if not branch['items']:
            return True

        lines = [item['line'] for item in branch['items']]
        return lines == sorted(lines)

    def validate_branch_id_consistency(self, branch: ControlFlowBranch) -> bool:
        """Check that all items have matching branch_id.

        Args:
            branch: ControlFlowBranch to check

        Returns:
            True if all items match branch ID, False otherwise
        """
        return all(item['branch_id'] == branch['branch_id'] for item in branch['items'])
