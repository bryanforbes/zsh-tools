/**
 * @file Zsh grammar for tree-sitter
 * Core AST skeleton: source_file, list, sublist, pipeline, command, redirect, _word
 *
 * Precedence/associativity (see docs/tokens.md):
 * - Pipelines `|`/`|&`: highest among these; left-associative (par_pline)
 * - And/Or `&&`/`||`: same precedence; left-associative; lower than pipelines (par_sublist)
 * - List terminators `;`/`&` (newline handled later): lowest (par_list)
 */

/// <reference types="tree-sitter-cli/dsl" />
// @ts-check

export default grammar({
  name: 'zsh',

  rules: {
    // TODO: add the actual grammar rules
    source_file: ($) => 'hello',
  },
});
