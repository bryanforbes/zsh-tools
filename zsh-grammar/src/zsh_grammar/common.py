from __future__ import annotations

from pathlib import Path
from typing import Final

ZSH_GRAMMAR_ROOT: Final = Path(__file__).resolve().parents[2]
GRAMMAR_JSON_PATH: Final = ZSH_GRAMMAR_ROOT / 'canonical-grammar.json'
GRAMMAR_SCHEMA_PATH: Final = ZSH_GRAMMAR_ROOT / 'canonical-grammar.schema.json'

PROJECT_ROOT: Final = ZSH_GRAMMAR_ROOT.parent
TREE_SITTER_GRAMMAR_PATH: Final = PROJECT_ROOT / 'tree-sitter-zsh' / 'grammar.js'
