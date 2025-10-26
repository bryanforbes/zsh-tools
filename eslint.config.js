import eslint from '@eslint/js';
import treesitter from 'eslint-config-treesitter';
import prettier from 'eslint-config-prettier';
import { defineConfig, globalIgnores } from 'eslint/config';

export default defineConfig(
  globalIgnores(['vendor/']),
  {
    ignores: ['tree-sitter-zsh/**'],
    extends: [eslint.configs.recommended],
  },
  {
    files: ['tree-sitter-zsh/grammar.js'],
    extends: [treesitter],
  },
  prettier,
);
