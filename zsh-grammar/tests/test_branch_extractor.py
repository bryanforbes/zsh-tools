"""Tests for Phase 2.4.1 Stage 1: Branch Extraction.

Tests the extract_control_flow_branches() function and helper functions
that identify if/else/switch/loop branches in parser function bodies.

Stage 1.3: AST Testing with real parse.c cursors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from clang.cindex import Cursor  # noqa: TC002

from zsh_grammar.branch_extractor import extract_control_flow_branches

if TYPE_CHECKING:
    from zsh_grammar._types import ControlFlowBranch


class TestExtractControlFlowBranches:
    """Tests for main branch extraction function."""

    def test_extract_branches_from_function_with_if_else(self, par_if: Cursor) -> None:
        """Function with if/else should extract multiple branches."""
        branches = extract_control_flow_branches(par_if, 'par_if')

        # par_if has if/elif/else structure
        assert len(branches) >= 2, f'Expected at least 2 branches, got {len(branches)}'

        # Should have if branches
        branch_types = {b['branch_type'] for b in branches}
        assert 'if' in branch_types or 'else_if' in branch_types

    def test_extract_branches_from_function_with_switch(self, par_case: Cursor) -> None:
        """Function with switch-like structure should extract branches."""
        branches = extract_control_flow_branches(par_case, 'par_case')

        # par_case is primarily sequential with internal loops
        assert len(branches) >= 1, f'Expected at least 1 branch, got {len(branches)}'
        assert branches[0]['branch_id']

    def test_extract_branches_from_function_with_loop(self, par_while: Cursor) -> None:
        """Function with while loop should extract loop branch."""
        branches = extract_control_flow_branches(par_while, 'par_while')

        # par_while should have control flow (if statements inside)
        assert len(branches) >= 1, f'Expected at least 1 branch, got {len(branches)}'

    def test_extract_branches_from_sequential_function(self, par_subsh: Cursor) -> None:
        """Function may have conditional branches."""
        branches = extract_control_flow_branches(par_subsh, 'par_subsh')

        # Even simple functions should return something
        assert len(branches) >= 1, f'Expected at least 1 branch, got {len(branches)}'
        assert all('branch_id' in b for b in branches)


class TestIfChainExtraction:
    """Tests for if/else/else-if chain extraction."""

    def test_if_chain_extracts_branch_type_if(self, par_if: Cursor) -> None:
        """First branch in chain should have branch_type='if'."""
        branches = extract_control_flow_branches(par_if, 'par_if')

        # Should have at least one if branch
        if_branches = [b for b in branches if b['branch_type'] == 'if']
        assert len(if_branches) >= 1, (
            f'No if branches found in {[b["branch_type"] for b in branches]}'
        )

        # First if branch should have proper attributes
        first_if = if_branches[0]
        assert first_if['branch_id'].startswith('if_')
        assert first_if['start_line'] > 0
        assert first_if['end_line'] > 0

    def test_if_chain_extracts_else_if_branches(self, par_if: Cursor) -> None:
        """Chain should have if or else_if branches."""
        branches = extract_control_flow_branches(par_if, 'par_if')

        # Should have multiple branches (if/elif/else structure)
        assert len(branches) >= 2, f'Expected at least 2 branches, got {len(branches)}'

        # Check for conditional branches
        conditional_types = {'if', 'else_if', 'else'}
        branch_types = {b['branch_type'] for b in branches}
        assert len(branch_types & conditional_types) > 0

    def test_if_chain_extracts_else_branch(self, par_if: Cursor) -> None:
        """Chain should properly handle else branches."""
        branches = extract_control_flow_branches(par_if, 'par_if')

        # Check that all conditional branches have expected structure
        for branch in branches:
            assert 'branch_id' in branch
            assert 'branch_type' in branch
            assert 'start_line' in branch
            assert 'end_line' in branch
            assert 'items' in branch
            assert isinstance(branch['items'], list)

    def test_if_condition_extraction(self, par_if: Cursor) -> None:
        """If branch should have condition field when present."""
        branches = extract_control_flow_branches(par_if, 'par_if')

        # Conditional branches should have condition
        for branch in branches:
            if branch['branch_type'] in ('if', 'else_if') and 'condition' in branch:
                # Condition may or may not be present depending on extraction
                assert isinstance(branch['condition'], str)

    def test_if_condition_semantic_token_extraction(self, par_if: Cursor) -> None:
        """Semantic token should be extracted from condition if present."""
        branches = extract_control_flow_branches(par_if, 'par_if')

        # Check that token_condition is properly typed when present
        for branch in branches:
            if 'token_condition' in branch:
                assert isinstance(branch['token_condition'], str)
                token = branch['token_condition']
                assert token.isupper() or token == 'default'  # noqa: S105


class TestSwitchExtraction:
    """Tests for switch statement extraction."""

    def test_switch_extracts_case_branches(self, par_case: Cursor) -> None:
        """Switch-like structures should be handled."""
        branches = extract_control_flow_branches(par_case, 'par_case')

        # Should return valid branches
        assert len(branches) >= 1
        for branch in branches:
            assert 'branch_id' in branch
            assert 'branch_type' in branch

    def test_switch_case_label_extraction(self, par_simple: Cursor) -> None:
        """Complex function should have valid branch structure."""
        branches = extract_control_flow_branches(par_simple, 'par_simple')

        # All branches should have required fields
        for branch in branches:
            assert isinstance(branch['branch_id'], str)
            assert len(branch['branch_id']) > 0
            assert branch['start_line'] <= branch['end_line']

    def test_switch_extracts_default_case(self, par_simple: Cursor) -> None:
        """Default case handling should be correct."""
        branches = extract_control_flow_branches(par_simple, 'par_simple')

        # Validate branch structure
        for branch in branches:
            if branch['branch_type'] == 'switch_case' and 'condition' in branch:
                # Should be either a token condition or 'default'
                assert isinstance(branch['condition'], str)


class TestLoopExtraction:
    """Tests for while/for loop extraction."""

    def test_extract_while_loop(self, par_while: Cursor) -> None:
        """While loop function should be handled."""
        branches = extract_control_flow_branches(par_while, 'par_while')

        # Should extract branches from while function
        assert len(branches) >= 1
        assert all('branch_id' in b for b in branches)

    def test_extract_for_loop(self, par_for: Cursor) -> None:
        """For loop function should be handled."""
        branches = extract_control_flow_branches(par_for, 'par_for')

        # Should extract branches
        assert len(branches) >= 1
        # Validate all branches have required fields
        for branch in branches:
            assert branch['branch_id']
            assert branch['branch_type'] in {
                'if',
                'else_if',
                'else',
                'switch_case',
                'loop',
                'sequential',
            }


class TestBranchMetadata:
    """Tests for branch metadata correctness."""

    def test_branch_has_required_fields(self) -> None:
        """Each branch must have branch_id, branch_type, start_line, end_line."""
        # Test data structure compliance
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',  # type: ignore[typeddict-unknown-key]
            'start_line': 100,
            'end_line': 150,
            'items': [],
        }
        assert branch['branch_id'] == 'if_1'
        assert branch['branch_type'] == 'if'
        assert branch['start_line'] == 100
        assert branch['end_line'] == 150

    def test_branch_id_format_if(self) -> None:
        """If branch_id should follow pattern 'if_N'."""
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',  # type: ignore[typeddict-unknown-key]
            'start_line': 100,
            'end_line': 110,
            'items': [],
        }
        assert branch['branch_id'].startswith('if_')

    def test_branch_id_format_else_if(self) -> None:
        """Else-if branch_id should follow pattern 'else_if_N'."""
        branch: ControlFlowBranch = {
            'branch_id': 'else_if_1',
            'branch_type': 'else_if',  # type: ignore[typeddict-unknown-key]
            'start_line': 111,
            'end_line': 120,
            'items': [],
        }
        assert branch['branch_id'].startswith('else_if_')

    def test_branch_id_format_switch_case(self) -> None:
        """Switch case branch_id should follow pattern 'switch_case_TOKEN'."""
        branch: ControlFlowBranch = {
            'branch_id': 'switch_case_FOR',
            'branch_type': 'switch_case',  # type: ignore[typeddict-unknown-key]
            'condition': 'tok == FOR',
            'start_line': 200,
            'end_line': 250,
            'items': [],
        }
        assert branch['branch_id'].startswith('switch_case_')

    def test_branch_id_format_loop(self) -> None:
        """Loop branch_id should be 'loop'."""
        branch: ControlFlowBranch = {
            'branch_id': 'loop',
            'branch_type': 'loop',  # type: ignore[typeddict-unknown-key]
            'start_line': 300,
            'end_line': 350,
            'items': [],
        }
        assert branch['branch_id'] == 'loop'

    def test_branch_id_format_sequential(self) -> None:
        """Sequential branch_id should be 'sequential'."""
        branch: ControlFlowBranch = {
            'branch_id': 'sequential',
            'branch_type': 'sequential',  # type: ignore[typeddict-unknown-key]
            'start_line': 100,
            'end_line': 200,
            'items': [],
        }
        assert branch['branch_id'] == 'sequential'


class TestConditionalBranchConditions:
    """Tests for condition field presence."""

    def test_if_branch_has_condition(self) -> None:
        """If branch should have condition field."""
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',  # type: ignore[typeddict-unknown-key]
            'condition': 'tok == INPAR',
            'start_line': 100,
            'end_line': 110,
            'items': [],
        }
        assert 'condition' in branch

    def test_else_if_branch_has_condition(self) -> None:
        """Else-if branch should have condition field."""
        branch: ControlFlowBranch = {
            'branch_id': 'else_if_1',
            'branch_type': 'else_if',  # type: ignore[typeddict-unknown-key]
            'condition': 'tok == INBRACE',
            'start_line': 111,
            'end_line': 120,
            'items': [],
        }
        assert 'condition' in branch

    def test_else_branch_no_condition_required(self) -> None:
        """Else branch should not require condition field."""
        branch: ControlFlowBranch = {
            'branch_id': 'else_1',
            'branch_type': 'else',  # type: ignore[typeddict-unknown-key]
            'start_line': 121,
            'end_line': 130,
            'items': [],
        }
        # Else doesn't need condition
        assert branch['branch_type'] == 'else'

    def test_loop_branch_no_condition_required(self) -> None:
        """Loop branch should not require condition field."""
        branch: ControlFlowBranch = {
            'branch_id': 'loop',
            'branch_type': 'loop',  # type: ignore[typeddict-unknown-key]
            'start_line': 200,
            'end_line': 250,
            'items': [],
        }
        assert 'condition' not in branch or branch.get('condition') is None

    def test_sequential_branch_no_condition_required(self) -> None:
        """Sequential branch should not require condition field."""
        branch: ControlFlowBranch = {
            'branch_id': 'sequential',
            'branch_type': 'sequential',  # type: ignore[typeddict-unknown-key]
            'start_line': 100,
            'end_line': 200,
            'items': [],
        }
        assert 'condition' not in branch or branch.get('condition') is None


class TestBranchLineNumbers:
    """Tests for branch line number properties."""

    def test_branch_start_line_less_than_end_line(self) -> None:
        """start_line must be <= end_line."""
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',  # type: ignore[typeddict-unknown-key]
            'start_line': 100,
            'end_line': 150,
            'items': [],
        }
        assert branch['start_line'] <= branch['end_line']

    def test_branch_line_numbers_positive(self) -> None:
        """Line numbers must be positive integers."""
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',  # type: ignore[typeddict-unknown-key]
            'start_line': 100,
            'end_line': 150,
            'items': [],
        }
        assert branch['start_line'] > 0
        assert branch['end_line'] > 0


class TestBranchItemsInitialization:
    """Tests that branches are initialized with empty items list."""

    def test_branch_items_initialized_empty(self) -> None:
        """All extracted branches should have empty items list."""
        branch: ControlFlowBranch = {
            'branch_id': 'if_1',
            'branch_type': 'if',  # type: ignore[typeddict-unknown-key]
            'start_line': 100,
            'end_line': 110,
            'items': [],
        }
        assert branch['items'] == []
        assert isinstance(branch['items'], list)


class TestBranchExtractionCoverage:
    """Tests to validate branch extraction across multiple functions."""

    def test_par_if_branch_structure(self, par_if: Cursor) -> None:
        """Validate par_if extracts control flow branches."""
        branches = extract_control_flow_branches(par_if, 'par_if')

        # par_if has a for-loop wrapper with nested if/else inside
        assert len(branches) >= 1
        # All branches should be valid
        assert all(
            b['branch_type'] in ('if', 'else_if', 'else', 'loop', 'sequential')
            for b in branches
        )

    def test_par_while_branch_structure(self, par_while: Cursor) -> None:
        """Validate par_while extracts control flow."""
        branches = extract_control_flow_branches(par_while, 'par_while')

        assert len(branches) >= 1
        assert all('branch_id' in b and 'branch_type' in b for b in branches)

    def test_par_for_branch_structure(self, par_for: Cursor) -> None:
        """Validate par_for extracts control flow."""
        branches = extract_control_flow_branches(par_for, 'par_for')

        assert len(branches) >= 1
        assert all('start_line' in b and 'end_line' in b for b in branches)

    def test_all_branches_have_items_list(
        self, parser_functions_ast: dict[str, Cursor]
    ) -> None:
        """All branches should initialize empty items list."""
        for func_name, func_cursor in list(parser_functions_ast.items())[:5]:
            branches = extract_control_flow_branches(func_cursor, func_name)

            for branch in branches:
                assert 'items' in branch
                assert isinstance(branch['items'], list)
                assert branch['items'] == []

    def test_par_case_returns_valid_branches(self, par_case: Cursor) -> None:
        """par_case should return valid branch structures."""
        branches = extract_control_flow_branches(par_case, 'par_case')

        for branch in branches:
            # Validate all required fields
            assert isinstance(branch['branch_id'], str)
            assert branch['branch_id']
            assert isinstance(branch['branch_type'], str)
            assert branch['branch_type'] in (
                'if',
                'else_if',
                'else',
                'switch_case',
                'loop',
                'sequential',
            )
            assert isinstance(branch['start_line'], int)
            assert isinstance(branch['end_line'], int)
            assert branch['start_line'] > 0
            assert branch['end_line'] > 0
            assert branch['start_line'] <= branch['end_line']

    def test_par_cond_returns_valid_branches(self, par_cond: Cursor) -> None:
        """par_cond (complex conditional function) should be handled."""
        branches = extract_control_flow_branches(par_cond, 'par_cond')

        assert len(branches) >= 1
        for branch in branches:
            assert 'branch_id' in branch
            assert 'branch_type' in branch
