#include "tree_sitter/alloc.h"
#include "tree_sitter/array.h"
#include "tree_sitter/parser.h"

enum TokenType { UNQUOTED_WHITESPACE };

void *tree_sitter_zsh_external_scanner_create() { return NULL; }

void tree_sitter_zsh_external_scanner_destroy(void *p) {}

unsigned tree_sitter_zsh_external_scanner_serialize(void *payload,
                                                    char *buffer) {
    return 0;
}

void tree_sitter_zsh_external_scanner_deserialize(void *p, const char *b,
                                                  unsigned n) {}

bool tree_sitter_zsh_external_scanner_scan(void *payload, TSLexer *lexer,
                                           const bool *valid_symbols) {
    if (valid_symbols[UNQUOTED_WHITESPACE]) {
        if (lexer->lookahead == '\\') {
            lexer->advance(lexer, false);
        }
        if (lexer->lookahead == ' ' || lexer->lookahead == '\t' ||
            lexer->lookahead == '\n') {
            while (lexer->lookahead == ' ' || lexer->lookahead == '\t' ||
                   lexer->lookahead == '\n') {
                lexer->advance(lexer, false);
            }
            lexer->result_symbol = UNQUOTED_WHITESPACE;
            return true;
        }
    }
    return false;
}
