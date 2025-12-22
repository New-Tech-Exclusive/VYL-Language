#define _POSIX_C_SOURCE 200809L
#include "lexer.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

const char *keywords[] = {"Main",     "Function", "import", "include", "if",
                          "else",     "while",    "return", "Print",   "var",
                          "int",      "string",   "dec",    "bool",    "struct",
                          "new",      "for",      "in",     "match",   "break",
                          "continue", NULL};

int is_keyword(const char *str) {
  for (int i = 0; keywords[i] != NULL; i++) {
    if (strcmp(str, keywords[i]) == 0)
      return 1;
  }
  return 0;
}

void lexer_init(Lexer *lexer, const char *source) {
  lexer->source = source;
  lexer->pos = 0;
  lexer->line = 1;
  lexer->length = strlen(source);
}

char peek(Lexer *lexer) {
  if (lexer->pos < lexer->length)
    return lexer->source[lexer->pos];
  return 0;
}

void advance(Lexer *lexer) {
  if (lexer->pos < lexer->length) {
    if (lexer->source[lexer->pos] == '\n')
      lexer->line++;
    lexer->pos++;
  }
}

Token create_token(TokenType type, const char *value, int line) {
  Token token;
  token.type = type;
  token.value = value ? strdup(value) : NULL;
  token.line = line;
  return token;
}

Token *lexer_tokenize(Lexer *lexer, int *count) {
  int capacity = 10;
  *count = 0;
  Token *tokens = malloc(sizeof(Token) * capacity);

  while (lexer->pos < lexer->length) {
    char c = peek(lexer);

    if (isspace(c)) {
      advance(lexer);
      continue;
    }

    if (c == '/' && lexer->pos + 1 < lexer->length &&
        lexer->source[lexer->pos + 1] == '/') {
      while (lexer->pos < lexer->length && peek(lexer) != '\n') {
        advance(lexer);
      }
      continue;
    }

    if (*count >= capacity) {
      capacity *= 2;
      tokens = realloc(tokens, sizeof(Token) * capacity);
    }

    if (c == '"') {
      // Start of string literal
      advance(lexer);
      // Allocate a temporary buffer for the processed string
      size_t buf_cap = 64;
      size_t buf_len = 0;
      char *buf = malloc(buf_cap);
      if (!buf) {
        fprintf(stderr, "Memory allocation failed in lexer\n");
        exit(1);
      }
      while (lexer->pos < lexer->length && peek(lexer) != '"') {
        char ch = peek(lexer);
        if (ch == '\\') {
          // Escape sequence
          advance(lexer);
          if (lexer->pos >= lexer->length)
            break;
          char esc = peek(lexer);
          char out;
          switch (esc) {
          case 'n':
            out = '\n';
            break;
          case 't':
            out = '\t';
            break;
          case '\\':
            out = '\\';
            break;
          case '"':
            out = '"';
            break;
          default:
            out = esc;
            break; // Unknown escape, keep as is
          }
          if (buf_len + 1 >= buf_cap) {
            buf_cap *= 2;
            buf = realloc(buf, buf_cap);
          }
          buf[buf_len++] = out;
        } else {
          if (buf_len + 1 >= buf_cap) {
            buf_cap *= 2;
            buf = realloc(buf, buf_cap);
          }
          buf[buf_len++] = ch;
        }
        advance(lexer);
      }
      // Null‑terminate the string
      if (buf_len + 1 >= buf_cap) {
        buf = realloc(buf, buf_len + 1);
      }
      buf[buf_len] = '\0';
      tokens[(*count)++] = create_token(TOKEN_STRING, buf, lexer->line);
      free(buf);
      // Skip closing quote
      advance(lexer);
      continue;
    }

    if (isdigit(c)) {
      int start = lexer->pos;
      int is_decimal = 0;
      while (lexer->pos < lexer->length &&
             (isdigit(peek(lexer)) || peek(lexer) == '.')) {
        if (peek(lexer) == '.') {
          if (lexer->pos + 1 < lexer->length &&
              lexer->source[lexer->pos + 1] == '.') {
            break; // Found '..', stop parsing number
          }
          if (is_decimal)
            break; // Only one dot
          is_decimal = 1;
        }
        advance(lexer);
      }
      char *val = strndup(lexer->source + start, lexer->pos - start);
      tokens[(*count)++] = create_token(
          is_decimal ? TOKEN_DECIMAL : TOKEN_NUMBER, val, lexer->line);
      free(val);
      continue;
    }

    if (isalpha(c) || c == '_') {
      int start = lexer->pos;
      while (lexer->pos < lexer->length &&
             (isalnum(peek(lexer)) || peek(lexer) == '_')) {
        advance(lexer);
      }
      char *val = strndup(lexer->source + start, lexer->pos - start);
      if (strcmp(val, "true") == 0) {
        tokens[(*count)++] = create_token(TOKEN_NUMBER, "1", lexer->line);
      } else if (strcmp(val, "false") == 0) {
        tokens[(*count)++] = create_token(TOKEN_NUMBER, "0", lexer->line);
      } else if (is_keyword(val)) {
        TokenType type = TOKEN_KEYWORD;
        if (strcmp(val, "var") == 0)
          type = TOKEN_KEYWORD_VAR;
        else if (strcmp(val, "int") == 0)
          type = TOKEN_KEYWORD_INT;
        else if (strcmp(val, "string") == 0)
          type = TOKEN_KEYWORD_STRING;
        else if (strcmp(val, "dec") == 0)
          type = TOKEN_KEYWORD_DEC;
        else if (strcmp(val, "while") == 0)
          type = TOKEN_KEYWORD_WHILE;
        else if (strcmp(val, "bool") == 0)
          type = TOKEN_KEYWORD_BOOL;
        else if (strcmp(val, "struct") == 0)
          type = TOKEN_KEYWORD_STRUCT;
        else if (strcmp(val, "new") == 0)
          type = TOKEN_KEYWORD_NEW;
        else if (strcmp(val, "for") == 0)
          type = TOKEN_KEYWORD_FOR;
        else if (strcmp(val, "in") == 0)
          type = TOKEN_KEYWORD_IN;
        else if (strcmp(val, "match") == 0)
          type = TOKEN_KEYWORD_MATCH;
        else if (strcmp(val, "break") == 0)
          type = TOKEN_KEYWORD_BREAK;
        else if (strcmp(val, "continue") == 0)
          type = TOKEN_KEYWORD_CONTINUE;
        tokens[(*count)++] = create_token(type, val, lexer->line);
      } else {
        tokens[(*count)++] = create_token(TOKEN_ID, val, lexer->line);
      }
      free(val);
      continue;
    }

    switch (c) {
    case '.':
      if (lexer->pos + 1 < lexer->length &&
          lexer->source[lexer->pos + 1] == '.') {
        tokens[(*count)++] = create_token(TOKEN_DOTDOT, "..", lexer->line);
        advance(lexer);
        advance(lexer);
        continue;
      }
      tokens[(*count)++] = create_token(TOKEN_DOT, ".", lexer->line);
      break;
    case '(':
      tokens[(*count)++] = create_token(TOKEN_LPAREN, "(", lexer->line);
      break;
    case ')':
      tokens[(*count)++] = create_token(TOKEN_RPAREN, ")", lexer->line);
      break;
    case '{':
      tokens[(*count)++] = create_token(TOKEN_LBRACE, "{", lexer->line);
      break;
    case '}':
      tokens[(*count)++] = create_token(TOKEN_RBRACE, "}", lexer->line);
      break;
    case '[':
      tokens[(*count)++] = create_token(TOKEN_LBRACKET, "[", lexer->line);
      break;
    case ']':
      tokens[(*count)++] = create_token(TOKEN_RBRACKET, "]", lexer->line);
      break;
    case ',':
      tokens[(*count)++] = create_token(TOKEN_COMMA, ",", lexer->line);
      break;
    case ';':
      tokens[(*count)++] = create_token(TOKEN_SEMICOLON, ";", lexer->line);
      break;
    case '+':
      tokens[(*count)++] = create_token(TOKEN_PLUS, "+", lexer->line);
      break;
    case '-':
      tokens[(*count)++] = create_token(TOKEN_MINUS, "-", lexer->line);
      break;
    case '*':
      tokens[(*count)++] = create_token(TOKEN_STAR, "*", lexer->line);
      break;
    case '<':
      if (lexer->pos + 1 < lexer->length && lexer->source[lexer->pos + 1] == '=') {
        tokens[(*count)++] = create_token(TOKEN_LE, "<=", lexer->line);
        advance(lexer);
      } else {
        tokens[(*count)++] = create_token(TOKEN_LT, "<", lexer->line);
      }
      break;
    case '>':
      if (lexer->pos + 1 < lexer->length && lexer->source[lexer->pos + 1] == '=') {
        tokens[(*count)++] = create_token(TOKEN_GE, ">=", lexer->line);
        advance(lexer);
      } else {
        tokens[(*count)++] = create_token(TOKEN_GT, ">", lexer->line);
      }
      break;
    case '=':
      if (lexer->pos + 1 < lexer->length &&
          lexer->source[lexer->pos + 1] == '=') {
        tokens[(*count)++] = create_token(TOKEN_EQ, "==", lexer->line);
        advance(lexer);
        advance(lexer);
        continue;
      } else if (lexer->pos + 1 < lexer->length &&
                 lexer->source[lexer->pos + 1] == '>') {
        tokens[(*count)++] = create_token(TOKEN_ARROW, "=>", lexer->line);
        advance(lexer);
        advance(lexer);
        continue;
      }
      tokens[(*count)++] = create_token(TOKEN_ASSIGN, "=", lexer->line);
      break;
    case '_':
      tokens[(*count)++] = create_token(TOKEN_UNDERSCORE, "_", lexer->line);
      break;
    case '/':
      if (lexer->pos + 1 < lexer->length &&
          lexer->source[lexer->pos + 1] == 'n') {
        tokens[(*count)++] = create_token(TOKEN_VYL_NEWLINE, "/n", lexer->line);
        advance(lexer); // Skip /
        advance(lexer); // Skip n
        continue;       // Skip the default advance at bottom
      } else if (lexer->pos + 1 < lexer->length &&
                 lexer->source[lexer->pos + 1] == '/') {
        // Comment handled above, but just in case
        while (lexer->pos < lexer->length && peek(lexer) != '\n') {
          advance(lexer);
        }
        continue;
      } else {
        // Division operator
        tokens[(*count)++] = create_token(TOKEN_SLASH, "/", lexer->line);
      }
      break;
    case '%':
      tokens[(*count)++] = create_token(TOKEN_MOD, "%", lexer->line);
      break;
    case '&':
      if (lexer->pos + 1 < lexer->length && lexer->source[lexer->pos + 1] == '&') {
        tokens[(*count)++] = create_token(TOKEN_AND, "&&", lexer->line);
        advance(lexer);
      } else {
        fprintf(stderr, "Unexpected '&' at line %d\n", lexer->line);
        exit(1);
      }
      break;
    case '|':
      if (lexer->pos + 1 < lexer->length && lexer->source[lexer->pos + 1] == '|') {
        tokens[(*count)++] = create_token(TOKEN_OR, "||", lexer->line);
        advance(lexer);
      } else {
        fprintf(stderr, "Unexpected '|' at line %d\n", lexer->line);
        exit(1);
      }
      break;
    case '!':
      if (lexer->pos + 1 < lexer->length &&
          lexer->source[lexer->pos + 1] == '=') {
        tokens[(*count)++] = create_token(TOKEN_NEQ, "!=", lexer->line);
        advance(lexer);
        advance(lexer);
        continue;
      }
      tokens[(*count)++] = create_token(TOKEN_NOT, "!", lexer->line);
      break;
    default:
      fprintf(stderr, "Unexpected character type '%c' at line %d\n", c,
              lexer->line);
      exit(1);
    }
    advance(lexer);
  }

  // Add EOF
  if (*count >= capacity) {
    tokens = realloc(tokens, sizeof(Token) * (capacity + 1));
  }
  tokens[(*count)++] = create_token(TOKEN_EOF, NULL, lexer->line);

  return tokens;
}

void free_tokens(Token *tokens, int count) {
  for (int i = 0; i < count; i++) {
    if (tokens[i].value)
      free(tokens[i].value);
  }
  free(tokens);
}

const char *token_type_to_string(TokenType type) {
  switch (type) {
  case TOKEN_EOF:
    return "EOF";
  case TOKEN_KEYWORD:
    return "KEYWORD";
  case TOKEN_ID:
    return "ID";
  case TOKEN_STRING:
    return "STRING";
  case TOKEN_NUMBER:
    return "NUMBER";
  case TOKEN_LPAREN:
    return "LPAREN";
  case TOKEN_RPAREN:
    return "RPAREN";
  case TOKEN_LBRACE:
    return "LBRACE";
  case TOKEN_RBRACE:
    return "RBRACE";
  case TOKEN_COMMA:
    return "COMMA";
  case TOKEN_SEMICOLON:
    return "SEMICOLON";
  case TOKEN_PLUS:
    return "PLUS";
  case TOKEN_MINUS:
    return "MINUS";
  case TOKEN_STAR:
    return "STAR";
  case TOKEN_SLASH:
    return "SLASH";
  case TOKEN_MOD:
    return "MOD";
  case TOKEN_LE:
    return "LE";
  case TOKEN_GE:
    return "GE";
  case TOKEN_AND:
    return "AND";
  case TOKEN_OR:
    return "OR";
  case TOKEN_EQ:
    return "EQ";
  case TOKEN_LT:
    return "LT";
  case TOKEN_GT:
    return "GT";
  case TOKEN_ASSIGN:
    return "ASSIGN";
  case TOKEN_DECIMAL:
    return "DECIMAL";
  case TOKEN_KEYWORD_VAR:
    return "VAR";
  case TOKEN_KEYWORD_INT:
    return "INT";
  case TOKEN_KEYWORD_STRING:
    return "STRING";
  case TOKEN_KEYWORD_DEC:
    return "DEC";
  case TOKEN_KEYWORD_WHILE:
    return "WHILE";
  case TOKEN_KEYWORD_BOOL:
    return "BOOL";
  case TOKEN_VYL_NEWLINE:
    return "VYL_NEWLINE";
  default:
    return "UNKNOWN";
  }
}
