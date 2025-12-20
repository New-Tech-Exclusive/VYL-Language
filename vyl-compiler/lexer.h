#ifndef LEXER_H
#define LEXER_H

typedef enum {
  TOKEN_EOF,
  TOKEN_KEYWORD,
  TOKEN_ID,
  TOKEN_STRING,
  TOKEN_NUMBER,
  TOKEN_LPAREN,
  TOKEN_RPAREN,
  TOKEN_LBRACE,
  TOKEN_RBRACE,
  TOKEN_COMMA,
  TOKEN_SEMICOLON,
  TOKEN_PLUS,
  TOKEN_MINUS,
  TOKEN_STAR,
  TOKEN_SLASH,
  TOKEN_EQ,      // ==
  TOKEN_LT,      // <
  TOKEN_GT,      // >
  TOKEN_ASSIGN,  // =
  TOKEN_DECIMAL, // 3.14
  TOKEN_KEYWORD_VAR,
  TOKEN_KEYWORD_INT,
  TOKEN_KEYWORD_STRING,
  TOKEN_KEYWORD_DEC,
  TOKEN_KEYWORD_WHILE,
  TOKEN_KEYWORD_BOOL,
  TOKEN_LBRACKET,
  TOKEN_RBRACKET,
  TOKEN_KEYWORD_STRUCT,
  TOKEN_KEYWORD_NEW,
  TOKEN_DOT,
  TOKEN_KEYWORD_FOR,
  TOKEN_KEYWORD_IN,
  TOKEN_DOTDOT,
  TOKEN_KEYWORD_MATCH,
  TOKEN_ARROW,
  TOKEN_UNDERSCORE,
  TOKEN_VYL_NEWLINE
} TokenType;

typedef struct {
  TokenType type;
  char *value;
  int line;
} Token;

typedef struct {
  const char *source;
  int pos;
  int line;
  int length;
} Lexer;

void lexer_init(Lexer *lexer, const char *source);
Token *lexer_tokenize(Lexer *lexer, int *count);
void free_tokens(Token *tokens, int count);
const char *token_type_to_string(TokenType type);

#endif
