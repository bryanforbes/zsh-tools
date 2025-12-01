/**
 * @file Zsh grammar for tree-sitter
 * @author Bryan Forbes <bryan@reigndropsfall.net>
 * @license BSD-3-Clause
 */

/// <reference types="tree-sitter-cli/dsl" />
// @ts-check

export default grammar({
  name: 'zsh',

  // conflicts: ($) => [
  //   [$.pipeline],
  // ],

  // reserved: {
  //   global: ($) => [
  //
  //   ],
  // },

  // inline: ($) => [
  //   $.reserved_word
  // ],

  extras: ($) => [
    $.comment,
    /\s+/, // whitespace
  ],

  word: ($) => $.plain_string,

  rules: {
    program: ($) => $.list,
    variable: ($) => /[a-zA-Z_][a-zA-Z0-9_]*/,
    parameter_assignment: ($) => seq($.variable, choice('+=', '='), $.zsh_word),
    simple_command: ($) =>
      seq(
        repeat(
          choice($.parameter_assignment, $.precommand_modifier, $.redirection),
        ),
        $.zsh_word,
        repeat(choice($.redirection, $.parameter_assignment, $.zsh_word)),
      ),
    pipeline: ($) =>
      prec.right(
        seq(
          optional(choice('!', 'coproc')),
          $.simple_command,
          repeat(seq(choice('|', '|&'), $.simple_command)),
        ),
      ),
    sublist: ($) =>
      seq($.pipeline, repeat(seq(choice('&&', '||'), $.pipeline))),
    sublist_terminator: ($) => token(choice(';', '&', '&|', '&!', '\n')),
    list: ($) => repeat1(seq($.sublist, $.sublist_terminator)),
    plain_string: ($) =>
      token(
        seq(
          choice(/[^#:\s'"$`|&;<>()\[\]{}\\]/, seq('\\', /[ \n]/)),
          repeat(
            choice(/[^\s'"$`|&;<>()\[\]{}\\]/, seq('\\', /[ \n]/), /#[^\s]/),
          ),
        ),
      ),
    single_quoted_string: ($) => /'[^']*'/,
    double_quoted_string: ($) => /"(?:[^"\\]|\\.)*"/,
    ansi_c_quoted_string: ($) => /\$'(?:[^'\\]|\\.)*'/,
    quoted_string: ($) =>
      choice(
        $.single_quoted_string,
        $.double_quoted_string,
        $.ansi_c_quoted_string,
      ),
    zsh_word: ($) =>
      prec.left(repeat1(choice($.quoted_string, $.plain_string))),
    redirection_operator: ($) =>
      choice(
        '>',
        '>|',
        '>!',
        '>>',
        '>>|',
        '>>!',
        '<',
        '<>',
        '<<',
        '<<-',
        '<&',
        '>&',
        '&>',
        '&>|',
        '&>!',
        '>&|',
        '>&!',
        '&>>',
        '>>&',
        '&>>|',
        '&>>!',
        '>>&|',
        '>>&!',
        '<<<',
      ),
    command_separator: ($) =>
      choice($.sublist_terminator, '|', '||', '&&', '|&', ';&', ';|'),
    redirection: ($) =>
      seq(
        optional(choice(/[0-9]/, seq(/\{/, $.variable, /\}/))),
        $.redirection_operator,
        $.zsh_word,
      ),
    command_pcm: ($) => seq('command', repeat(/-[pvV]+/)),
    exec_pcm: ($) =>
      seq(/exec/, repeat(choice(/-[cl]+/, seq(/-a/, $.zsh_word)))),
    precommand_modifier: ($) =>
      choice('-', 'builtin', $.command_pcm, $.exec_pcm, 'nocorrect', 'noglob'),
    complex_command: ($) =>
      choice(
        $.if_statement,
        $.for_loop,
        $.while_loop,
        $.until_loop,
        $.case_statement,
        $.select_statement,
        $.subshell,
        $.exec_list,
        $.try_always,
        $.function_def,
        $.time_command,
        $.conditional_command,
      ),
    if_statement: ($) =>
      choice(
        seq(
          'if',
          $.list,
          'then',
          $.list,
          repeat(seq('elif', $.list, 'then', $.list)),
          optional(seq('else', $.list)),
          'fi',
        ),
        seq(
          'if',
          $.list,
          '{',
          $.list,
          '}',
          repeat(seq('elif', $.list, '{', $.list, '}')),
          optional(seq('else', '{', $.list, '}')),
        ),
      ),
    term: ($) => choice(repeat1('\n'), ';'),
    wordlist: ($) => repeat($.zsh_word),
    nl_wordlist: ($) => repeat1(choice('\n', ';', $.zsh_word)),
    in_wordlist: ($) => seq(/in/, $.wordlist),
    optional_word: ($) => optional($.zsh_word),
    arith_for_expression: ($) =>
      seq(
        $.optional_word,
        choice('\n', ';'),
        $.optional_word,
        choice('\n', ';'),
        $.optional_word,
      ),
    for_loop: ($) =>
      choice(
        seq(
          'for',
          repeat1($.variable),
          optional($.in_wordlist),
          $.term,
          'do',
          $.list,
          'done',
        ),
        seq('for', '((', $.arith_for_expression, '))', 'do', $.list, 'done'),
        seq(
          'for',
          repeat1($.variable),
          '(',
          $.nl_wordlist,
          ')',
          seq('{', $.list, '}'),
        ),
        seq(
          'for',
          repeat1($.variable),
          optional($.in_wordlist),
          $.term,
          seq('{', $.list, '}'),
        ),
        seq('for', '((', $.arith_for_expression, '))', seq('{', $.list, '}')),
        seq(
          'foreach',
          repeat1($.variable),
          '(',
          $.nl_wordlist,
          ')',
          $.list,
          'end',
        ),
      ),
    while_loop: ($) =>
      choice(
        seq('while', $.list, 'do', $.list, 'done'),
        seq('while', $.list, '{', $.list, '}'),
      ),
    until_loop: ($) =>
      choice(
        seq('until', $.list, 'do', $.list, 'done'),
        seq('until', $.list, '{', $.list, '}'),
      ),
    case_pattern: ($) => choice(/[a-zA-Z0-9_*?\[\]]+/, $.quoted_string),
    case_pattern_item: ($) =>
      choice(
        seq($.case_pattern, repeat(seq('|', $.case_pattern))),
        seq('(', $.case_pattern, repeat(seq('|', $.case_pattern)), ')'),
      ),
    case_statement: ($) =>
      choice(
        seq(
          'case',
          $.zsh_word,
          /in/,
          repeat(seq($.case_pattern_item, $.list, choice(';;', ';&', ';|'))),
          'esac',
        ),
        seq(
          'case',
          $.zsh_word,
          '{',
          repeat(seq($.case_pattern_item, $.list, choice(';;', ';&', ';|'))),
          '}',
        ),
      ),
    select_statement: ($) =>
      choice(
        seq(
          'select',
          $.variable,
          optional(seq(/in/, $.nl_wordlist, $.term)),
          'do',
          $.list,
          'done',
        ),
        seq(
          'select',
          $.variable,
          optional(seq(/in/, $.nl_wordlist, $.term)),
          '{',
          $.list,
          '}',
        ),
      ),
    subshell: ($) => seq('(', $.list, ')'),
    exec_list: ($) => seq('{', $.list, '}'),
    try_always: ($) => seq('{', $.list, '}', /always/, '{', $.list, '}'),
    function_def: ($) =>
      choice(
        seq(
          'function',
          optional(/-T/),
          repeat1($.zsh_word),
          optional('()'),
          optional($.term),
          '{',
          $.list,
          '}',
          optional($.redirection),
        ),
        seq(
          repeat1($.zsh_word),
          '(',
          ')',
          optional($.term),
          '{',
          $.list,
          '}',
          optional($.redirection),
        ),
      ),
    time_command: ($) => choice(seq('time', $.pipeline), 'time'),
    conditional_command: ($) => seq('[[', ']]'),
    arithmetic_command: ($) => seq('((', /[^)]+/, '))'),
    comment: ($) => token(prec(-20, seq(/[ \t]+/, '#', /.*/))),
    alias_command: ($) =>
      seq(
        /alias/,
        repeat(/[+\-]([gmrsL]+)?/),
        repeat(seq($.variable, optional(seq(/=/, $.zsh_word)))),
      ),
  },
});
