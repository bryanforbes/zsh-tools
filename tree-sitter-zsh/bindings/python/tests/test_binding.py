from __future__ import annotations

from unittest import TestCase

import tree_sitter_zsh

from tree_sitter import Language, Parser


class TestLanguage(TestCase):
    def test_can_load_grammar(self) -> None:
        try:
            Parser(Language(tree_sitter_zsh.language()))
        except Exception:  # noqa: BLE001
            self.fail('Error loading Zsh grammar')
