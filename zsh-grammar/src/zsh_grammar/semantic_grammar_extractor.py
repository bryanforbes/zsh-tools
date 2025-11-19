"""Extract semantic grammar comments from parse.c.

Stage 5.1: Extract documented grammar rules from source comments.

This module parses the semantic grammar comments that appear above and
around parser functions in parse.c, capturing the documented BNF-style
grammar that the parser implements.

Example:
    From parse.c:
    /*
     * subsh	: INPAR list OUTPAR
     *		| INBRACE list OUTBRACE [ "always" ... ]
     */

    Extracted:
    {
        'function': 'par_subsh',
        'rule': 'INPAR list OUTPAR | INBRACE list OUTBRACE [ "always" ... ]'
    }
"""

from __future__ import annotations

import re
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from _typeshed import StrPath


class SemanticGrammarRule(TypedDict):
    """Extracted semantic grammar rule."""

    function: str  # e.g., 'par_subsh'
    rule: str  # e.g., 'INPAR list OUTPAR | INBRACE list OUTBRACE'
    source_line: int  # Line number in parse.c
    source_file: str  # File path


@dataclass(slots=True)
class SemanticGrammarExtractor:
    """Extract semantic grammar comments from parse.c."""

    parse_c: InitVar[StrPath]
    parse_c_path: Path = field(init=False)
    content: str = field(init=False)
    lines: list[str] = field(init=False)

    def __post_init__(self, parse_c: StrPath) -> None:
        self.parse_c_path = Path(parse_c)
        self.content = self.parse_c_path.read_text(encoding='utf-8')
        self.lines = self.content.split('\n')

    def extract_all_rules(self) -> dict[str, SemanticGrammarRule]:
        """Extract all semantic grammar rules from parse.c.

        Returns:
            Dictionary mapping function names to their semantic grammar rules.
        """
        rules: dict[str, SemanticGrammarRule] = {}

        # Find all parser functions
        # Match function definitions like:
        # - par_subsh(...)
        # - static void par_subsh(...)
        parser_func_pattern = r'\b(par_\w+|parse_\w+)\s*\('
        for i, line in enumerate(self.lines):
            match = re.search(parser_func_pattern, line)
            if not match:
                continue

            func_name = match.group(1)
            grammar = self._extract_grammar_for_function(i)

            if grammar:
                rules[func_name] = {
                    'function': func_name,
                    'rule': grammar,
                    'source_line': i + 1,
                    'source_file': str(self.parse_c_path),
                }

        return rules

    def _extract_grammar_for_function(self, func_line_idx: int) -> str | None:
        """Extract grammar comment above function.

        Search upward from function definition for semantic grammar comments.
        Grammar comments are typically in C-style block comments with patterns:
        - Simple: single line rule
        - Multi-line: rule split across multiple comment lines
        - Alternatives: pipe-separated alternatives (|)
        - Options: bracketed [...] for optional parts

        Args:
            func_line_idx: Index of function definition line (0-based)

        Returns:
            Grammar string if found, None otherwise.
        """
        # Look backward for comment block
        for i in range(func_line_idx - 1, -1, -1):
            line = self.lines[i].strip()

            # Skip empty lines and code markers (/**/,  /*-*/,  /*+*/, etc.)
            if not line or line in ('/**/', '/*-*/', '/*+*/', '/*[[*/'):
                continue

            # Found comment block start
            if '/*' in line:
                return self._extract_from_comment_block(i, func_line_idx)

            # Stop if we hit a closing brace (end of previous function)
            if line.startswith('}'):
                break

        return None

    def _extract_from_comment_block(self, start_idx: int, end_idx: int) -> str | None:
        """Extract grammar rule from comment block.

        Args:
            start_idx: Index of line with '/*'
            end_idx: Index of function definition (for bounds check)

        Returns:
            Grammar rule string if found, None otherwise.
        """
        comment_lines: list[str] = []

        # Collect comment lines
        for i in range(start_idx, end_idx):
            line = self.lines[i]

            # Skip comment markers and leading whitespace
            # Remove /* */ and * prefixes from comment lines
            line = re.sub(r'^\s*/\*+', '', line)  # Remove leading /*
            line = re.sub(r'\*+/\s*$', '', line)  # Remove trailing */
            line = re.sub(r'^\s*\*\s?', '', line)  # Remove * prefix

            comment_lines.append(line.strip())

            if '*/' in self.lines[i]:
                break

        # Join lines and extract grammar pattern
        comment_text = ' '.join(comment_lines)

        # Look for pattern like "pattern: rule" or just "rule"
        # Patterns:
        # 1. "funcname    : RULE"
        # 2. "            | ALT1"
        # 3. "            | ALT2 [ optional ]"

        # Extract everything after colon (if present)
        if ':' in comment_text:
            # Format: "pattern_name : rule"
            parts = comment_text.split(':', 1)
            rule = parts[1].strip()
        else:
            # Might be continuation lines starting with |
            rule = comment_text.strip()

        # Clean up rule: remove extra whitespace, collapse multiple spaces
        rule = re.sub(r'\s+', ' ', rule).strip()

        # Rule should contain typical grammar elements
        # UPPERCASE tokens, lowercase rules, |, [], ()
        has_grammar_chars = any(
            c in rule for c in ['|', '[', '(', 'list', 'word', 'cond']
        ) or re.search(r'[A-Z]{2,}', rule)

        return rule if has_grammar_chars else None


def extract_semantic_grammar_from_parse_c(
    parse_c_path: str | Path,
) -> dict[str, SemanticGrammarRule]:
    """Extract semantic grammar rules from parse.c.

    Args:
        parse_c_path: Path to parse.c file

    Returns:
        Dictionary mapping function names to semantic grammar rules.
    """
    extractor = SemanticGrammarExtractor(parse_c_path)
    return extractor.extract_all_rules()
