/**
 * @file Zsh grammar for tree-sitter
 * @author Bryan Forbes <bryan@reigndropsfall.net>
 * @license BSD-3-Clause
 */

/// <reference types="tree-sitter-cli/dsl" />
// @ts-check

const BLANK = /[ \t]+/;
const SEPER = ['\n', ';'];
const NEWLINE = '\n';
const DASH = '-';
const SEMI = ';';
const DSEMI = ';;';
const AMPER = '&';
const INPAR = '(';
const OUTPAR = ')';
const DBAR = '||';
const DAMPER = '&&';
const OUTANG = '>';
const OUTANGBANG = ['>|', '>!'];
const DOUTANG = '>>';
const DOUTANGBANG = ['>>|', '>>!'];
const INANG = '<';
const INOUTANG = '<>';
const DINANG = '<<';
const DINANGDASH = '<<-';
const INANGAMP = '<&';
const OUTANGAMP = '>&';
const AMPOUTANG = '&>';
const OUTANGAMPBANG = ['&>|', '&>!', '>&|', '>&!'];
const DOUTANGAMP = ['&>>', '>>&'];
const DOUTANGAMPBANG = ['&>>|', '&>>!', '>>&|', '>>&!'];
const TRINANG = '<<<';
const BAR = '|';
const BARAMP = '|&';
const INOUTPAR = '()';
const DINPAR = '((';
const DOUTPAR = '))';
const AMPERBANG = ['&|', '&!'];
const SEMIAMP = ';&';
const SEMIBAR = ';|';
const DO = 'do';
const DONE = 'done';
const ESAC = 'esac';
const THEN = 'then';
const ELIF = 'elif';
const ELSE = 'else';
const FI = 'fi';
const FOR = 'for';
const CASE = 'case';
const IF = 'if';
const WHILE = 'while';
const FUNCTION = 'function';
const REPEAT = 'repeat';
const TIME = 'time';
const UNTIL = 'until';
const SELECT = 'select';
const COPROC = 'coproc';
const BUILTIN = 'builtin';
const NOCORRECT = 'nocorrect';
const NOGLOB = 'noglob';
const FOREACH = 'foreach';
const END = 'end';
const BANG = '!';
const DINBRACK = '[[';
const DOUTBRACK = ']]';
const INBRACE = '{';
const OUTBRACE = '}';
const DECLARE = 'declare';
const EXPORT = 'export';
const FLOAT = 'float';
const INTEGER = 'integer';
const LOCAL = 'local';
const READONLY = 'readonly';
const TYPESET = 'typeset';
const SPECIAL_STAR = '*';
const SPECIAL_AT = '@';
const SPECIAL_HASH = '#';
const SPECIAL_QUESTION = '?';
const SPECIAL_DOLLAR = '$';

export default grammar({
  name: 'zsh',

  rules: {
    source_file: ($) => repeat(choice($._comment, $.list)),
    special_parameter: ($) =>
      choice(
        SPECIAL_STAR,
        SPECIAL_AT,
        SPECIAL_HASH,
        SPECIAL_QUESTION,
        DASH,
        SPECIAL_DOLLAR,
        BANG,
      ),
    variable: ($) => /[a-zA-Z_][a-zA-Z0-9_]*/,
    positional_parameter: ($) => /[0-9]+/,
    parameter: ($) =>
      choice($.variable, $.positional_parameter, $.special_parameter),
    parameter_assignment: ($) => /[a-zA-Z_][a-zA-Z0-9_]*(\[[^\]]*\])*(\+)?=.*/,
    simple_command: ($) =>
      seq(
        repeat(
          seq(
            choice(
              $.parameter_assignment,
              $.precommand_modifier,
              $.redirection,
            ),
            BLANK,
          ),
        ),
        $.word,
        repeat(
          seq(BLANK, choice($.word, $.redirection, $.parameter_assignment)),
        ),
      ),
    pipeline: ($) =>
      seq(
        optional(seq(choice(BANG, COPROC), BLANK)),
        $.simple_command,
        repeat1(
          seq(
            optional(BLANK),
            choice(BAR, BARAMP),
            optional(BLANK),
            $.simple_command,
          ),
        ),
      ),
    _sublist: ($) =>
      seq(
        $.pipeline,
        repeat(
          seq(
            optional(BLANK),
            choice(DAMPER, DBAR),
            optional(BLANK),
            $.pipeline,
          ),
        ),
      ),
    sublist_terminator_no_semi: ($) => choice(AMPER, ...AMPERBANG, NEWLINE),
    sublist_terminator: ($) => choice(SEMI, $.sublist_terminator_no_semi),
    list: ($) =>
      choice(
        repeat(
          seq(
            $._sublist,
            optional(BLANK),
            $.sublist_terminator,
            optional(BLANK),
          ),
        ),
        seq(
          repeat(
            seq(
              $._sublist,
              optional(BLANK),
              $.sublist_terminator,
              optional(BLANK),
            ),
          ),
          optional(
            seq(
              $._sublist,
              optional(BLANK),
              $.sublist_terminator_no_semi,
              optional(BLANK),
            ),
          ),
        ),
      ),
    reserved_word: ($) =>
      choice(
        DO,
        DONE,
        ESAC,
        THEN,
        ELIF,
        ELSE,
        FI,
        FOR,
        CASE,
        IF,
        WHILE,
        FUNCTION,
        REPEAT,
        TIME,
        UNTIL,
        SELECT,
        COPROC,
        NOCORRECT,
        FOREACH,
        END,
        BANG,
        DINBRACK,
        INBRACE,
        OUTBRACE,
        DECLARE,
        EXPORT,
        FLOAT,
        INTEGER,
        LOCAL,
        READONLY,
        TYPESET,
      ),
    plain_string: ($) => /(?:\\.|[^\s'"$`|&;<>()\[\]{}])+/,
    glob_pattern: ($) =>
      /(?:\\.|[^\s'"$`|&;<>()\[\]{}])*[*?\[](?:\\.|[^\s'"$`|&;<>()\[\]{}])*/,
    single_quoted_string: ($) => choice(/'[^']*'/, /'(?:[^']|'{2})+'/),
    double_quoted_string: ($) => /"(?:[^"\\]|\\.)*"/,
    ansi_c_quoted_string: ($) => /\$'(?:[^'\\]|\\.)*'/,
    quoted_string: ($) =>
      choice(
        $.single_quoted_string,
        $.double_quoted_string,
        $.ansi_c_quoted_string,
      ),
    simple_parameter: ($) => /\$[a-zA-Z_][a-zA-Z0-9_]*/,
    braced_parameter: ($) => /\$\{[^}]*\}/,
    indexed_parameter: ($) => /\$[0-9]+/,
    special_parameter_ref: ($) => /\$[*@#?\-$!]/,
    parameter_reference: ($) =>
      choice(
        $.simple_parameter,
        $.braced_parameter,
        $.indexed_parameter,
        $.special_parameter_ref,
      ),
    command_substitution: ($) =>
      choice(/\$\([^)]*\)/, /`[^`]*`/, /\$\[[^\]]*\]/),
    word: ($) =>
      choice(
        repeat1(
          choice(
            $.glob_pattern,
            $.plain_string,
            $.quoted_string,
            $.parameter_reference,
            $.command_substitution,
          ),
        ),
        $.reserved_word,
        choice(
          $.command_separator,
          $.redirection_operator,
          choice(INPAR, OUTPAR),
        ),
      ),
    redirection_operator: ($) =>
      choice(
        OUTANG,
        ...OUTANGBANG,
        DOUTANG,
        ...DOUTANGBANG,
        INANG,
        INOUTANG,
        DINANG,
        DINANGDASH,
        INANGAMP,
        OUTANGAMP,
        AMPOUTANG,
        ...OUTANGAMPBANG,
        ...DOUTANGAMP,
        ...DOUTANGAMPBANG,
        TRINANG,
      ),
    command_separator: ($) =>
      choice($.sublist_terminator, BAR, DBAR, DAMPER, BARAMP, SEMIAMP, SEMIBAR),
    redirection: ($) =>
      seq(
        optional(choice(/[0-9]/, seq(/\{/, $.variable, /\}/))),
        $.redirection_operator,
        optional(BLANK),
        $.word,
      ),
    command_pcm: ($) => seq(/command/, repeat(seq(BLANK, /-[pvV]+/))),
    exec_pcm: ($) =>
      seq(
        /exec/,
        repeat(seq(BLANK, choice(/-[cl]+/, seq(/-a/, BLANK, $.word)))),
      ),
    precommand_modifier: ($) =>
      choice(DASH, BUILTIN, $.command_pcm, $.exec_pcm, NOCORRECT, NOGLOB),
    complex_command: ($) =>
      choice(
        $.if_statement,
        $.for_loop,
        $.while_loop,
        $.until_loop,
        $.repeat_loop,
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
          IF,
          BLANK,
          $.list,
          BLANK,
          THEN,
          BLANK,
          $.list,
          repeat(seq(BLANK, ELIF, BLANK, $.list, BLANK, THEN, BLANK, $.list)),
          optional(seq(BLANK, ELSE, BLANK, $.list)),
          BLANK,
          FI,
        ),
        seq(
          IF,
          BLANK,
          $.list,
          BLANK,
          INBRACE,
          BLANK,
          $.list,
          BLANK,
          OUTBRACE,
          repeat(
            seq(
              BLANK,
              ELIF,
              BLANK,
              $.list,
              BLANK,
              INBRACE,
              BLANK,
              $.list,
              BLANK,
              OUTBRACE,
            ),
          ),
          optional(
            seq(BLANK, ELSE, BLANK, INBRACE, BLANK, $.list, BLANK, OUTBRACE),
          ),
        ),
        seq(IF, BLANK, $.list, BLANK, $._sublist),
      ),
    term: ($) => choice(repeat1(NEWLINE), SEMI),
    wordlist: ($) => repeat($.word),
    nl_wordlist: ($) => repeat1(choice(BLANK, ...SEPER, $.word)),
    in_wordlist: ($) => seq(/in/, BLANK, $.wordlist),
    optional_word: ($) =>
      choice(optional(BLANK), optional(seq($.word, optional(BLANK)))),
    arith_for_expression: ($) =>
      seq(
        $.optional_word,
        ...SEPER,
        $.optional_word,
        ...SEPER,
        $.optional_word,
      ),
    for_loop: ($) =>
      choice(
        seq(
          FOR,
          BLANK,
          repeat1($.variable),
          BLANK,
          optional($.in_wordlist),
          BLANK,
          $.term,
          BLANK,
          DO,
          BLANK,
          $.list,
          BLANK,
          DONE,
        ),
        seq(
          FOR,
          BLANK,
          DINPAR,
          $.arith_for_expression,
          DOUTPAR,
          BLANK,
          DO,
          BLANK,
          $.list,
          BLANK,
          DONE,
        ),
        seq(
          FOR,
          BLANK,
          repeat1($.variable),
          BLANK,
          INPAR,
          optional(BLANK),
          $.nl_wordlist,
          optional(BLANK),
          OUTPAR,
          BLANK,
          choice(seq(INBRACE, BLANK, $.list, BLANK, OUTBRACE), $._sublist),
        ),
        seq(
          FOR,
          BLANK,
          repeat1($.variable),
          optional(seq(BLANK, $.in_wordlist)),
          BLANK,
          $.term,
          BLANK,
          choice(seq(INBRACE, BLANK, $.list, BLANK, OUTBRACE), $._sublist),
        ),
        seq(
          FOR,
          BLANK,
          DINPAR,
          optional(BLANK),
          $.arith_for_expression,
          optional(BLANK),
          DOUTPAR,
          BLANK,
          choice(seq(INBRACE, BLANK, $.list, BLANK, OUTBRACE), $._sublist),
        ),
        seq(
          FOREACH,
          BLANK,
          repeat1($.variable),
          BLANK,
          INPAR,
          optional(BLANK),
          $.nl_wordlist,
          optional(BLANK),
          OUTPAR,
          BLANK,
          $.list,
          END,
        ),
      ),
    while_loop: ($) =>
      choice(
        seq(WHILE, BLANK, $.list, BLANK, DO, BLANK, $.list, BLANK, DONE),
        seq(
          WHILE,
          BLANK,
          $.list,
          BLANK,
          INBRACE,
          BLANK,
          $.list,
          BLANK,
          OUTBRACE,
        ),
      ),
    until_loop: ($) =>
      choice(
        seq(UNTIL, BLANK, $.list, BLANK, DO, BLANK, $.list, BLANK, DONE),
        seq(
          UNTIL,
          BLANK,
          $.list,
          BLANK,
          INBRACE,
          BLANK,
          $.list,
          BLANK,
          OUTBRACE,
        ),
      ),
    repeat_loop: ($) =>
      choice(
        seq(REPEAT, BLANK, $.word, BLANK, DO, BLANK, $.list, BLANK, DONE),
        seq(REPEAT, BLANK, $.word, BLANK, $._sublist),
      ),
    case_pattern: ($) => choice(/[a-zA-Z0-9_*?\[\]]+/, $.quoted_string),
    case_pattern_item: ($) =>
      choice(
        seq($.case_pattern, repeat(seq(BAR, $.case_pattern))),
        seq(INPAR, $.case_pattern, repeat(seq(BAR, $.case_pattern)), OUTPAR),
      ),
    case_statement: ($) =>
      choice(
        seq(
          CASE,
          BLANK,
          $.word,
          BLANK,
          /in/,
          repeat(
            seq($.case_pattern_item, $.list, choice(DSEMI, SEMIAMP, SEMIBAR)),
          ),
          ESAC,
        ),
        seq(
          CASE,
          BLANK,
          $.word,
          BLANK,
          INBRACE,
          repeat(
            seq($.case_pattern_item, $.list, choice(DSEMI, SEMIAMP, SEMIBAR)),
          ),
          OUTBRACE,
        ),
      ),
    select_statement: ($) =>
      choice(
        seq(
          SELECT,
          BLANK,
          $.variable,
          optional(seq(BLANK, /in/, BLANK, $.nl_wordlist, BLANK, $.term)),
          BLANK,
          DO,
          BLANK,
          $.list,
          BLANK,
          DONE,
        ),
        seq(
          SELECT,
          BLANK,
          $.variable,
          optional(seq(BLANK, /in/, BLANK, $.nl_wordlist, BLANK, $.term)),
          BLANK,
          INBRACE,
          BLANK,
          $.list,
          BLANK,
          OUTBRACE,
        ),
        seq(
          SELECT,
          BLANK,
          $.variable,
          optional(seq(BLANK, /in/, BLANK, $.nl_wordlist, BLANK, $.term)),
          BLANK,
          $._sublist,
        ),
      ),
    subshell: ($) => seq(INPAR, BLANK, $.list, BLANK, OUTPAR),
    exec_list: ($) => seq(INBRACE, BLANK, $.list, BLANK, OUTBRACE),
    try_always: ($) =>
      seq(
        INBRACE,
        BLANK,
        $.list,
        BLANK,
        OUTBRACE,
        BLANK,
        /always/,
        BLANK,
        INBRACE,
        BLANK,
        $.list,
        BLANK,
        OUTBRACE,
      ),
    function_def: ($) =>
      choice(
        seq(
          FUNCTION,
          optional(seq(BLANK, /-T/)),
          BLANK,
          repeat1($.word),
          optional(seq(BLANK, INOUTPAR)),
          optional(seq(BLANK, $.term)),
          BLANK,
          INBRACE,
          BLANK,
          $.list,
          BLANK,
          OUTBRACE,
          optional(seq(BLANK, $.redirection)),
        ),
        seq(
          repeat1($.word),
          BLANK,
          INPAR,
          OUTPAR,
          optional(seq(BLANK, $.term)),
          BLANK,
          INBRACE,
          BLANK,
          $.list,
          BLANK,
          OUTBRACE,
          optional(seq(BLANK, $.redirection)),
        ),
        seq(
          FUNCTION,
          BLANK,
          repeat1($.word),
          optional(seq(BLANK, INPAR, OUTPAR)),
          optional(seq(BLANK, $.term)),
          BLANK,
          $._sublist,
          optional(seq(BLANK, $.redirection)),
        ),
      ),
    time_command: ($) => choice(seq(TIME, BLANK, $.pipeline), TIME),
    conditional_command: ($) => seq(DINBRACK, DOUTBRACK),
    arithmetic_command: ($) => seq(DINPAR, /[^)]+/, DOUTPAR),
    _comment: ($) => seq(/#/, /[^\n]*/),
    alias_command: ($) =>
      seq(
        /alias/,
        repeat(seq(BLANK, /[+\-]([gmrsL]+)?/)),
        repeat(seq(BLANK, $.variable, optional(seq(/=/, $.word)))),
      ),
  },
});
