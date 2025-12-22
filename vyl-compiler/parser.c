#define _POSIX_C_SOURCE 200809L
#include "parser.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void parser_init(Parser *parser, Token *tokens, int count) {
  parser->tokens = tokens;
  parser->count = count;
  parser->pos = 0;
}

Token peek_token(Parser *parser) {
  if (parser->pos < parser->count)
    return parser->tokens[parser->pos];
  Token eof;
  eof.type = TOKEN_EOF;
  eof.value = NULL;
  return eof;
}

Token peek_token_ahead(Parser *parser, int offset) {
  if (parser->pos + offset < parser->count)
    return parser->tokens[parser->pos + offset];
  Token eof;
  eof.type = TOKEN_EOF;
  eof.value = NULL;
  return eof;
}

Token consume_token(Parser *parser, TokenType type, const char *value) {
  Token token = peek_token(parser);
  if (type != TOKEN_EOF && token.type != type) {
    fprintf(stderr, "\n");
    fprintf(stderr, "┌─ Parser Error at line %d\n", token.line);
    fprintf(stderr, "├─ Expected: %s\n", token_type_to_string(type));
    fprintf(stderr, "├─ Found:    %s", token_type_to_string(token.type));
    if (token.value) fprintf(stderr, " ('%s')", token.value);
    fprintf(stderr, "\n");
    fprintf(stderr, "└─ Check your syntax and try again\n\n");
    exit(1);
  }
  if (value != NULL && strcmp(token.value, value) != 0) {
    fprintf(stderr, "\n");
    fprintf(stderr, "┌─ Parser Error at line %d\n", token.line);
    fprintf(stderr, "├─ Expected keyword or symbol: '%s'\n", value);
    fprintf(stderr, "├─ Found: '%s'\n", token.value);
    fprintf(stderr, "└─ Check spelling and syntax\n\n");
    exit(1);
  }
  parser->pos++;
  return token;
}

// Forward declarations
ASTNode *parse_statement(Parser *parser);
ASTNode *parse_expression(Parser *parser);
ASTNode *parse_block(Parser *parser);

ASTNode *parse_struct(Parser *parser) {
  consume_token(parser, TOKEN_KEYWORD_STRUCT, NULL);
  Token name = consume_token(parser, TOKEN_ID, NULL);
  consume_token(parser, TOKEN_LBRACE, NULL);

  int capacity = 8;
  int count = 0;
  StructField *fields = malloc(sizeof(StructField) * capacity);

  while (peek_token(parser).type != TOKEN_RBRACE &&
         peek_token(parser).type != TOKEN_EOF) {
    if (peek_token(parser).type == TOKEN_VYL_NEWLINE) {
      consume_token(parser, TOKEN_VYL_NEWLINE, NULL);
      continue;
    }

    consume_token(parser, TOKEN_KEYWORD_VAR, NULL);
    Token type_tok = peek_token(parser);
    VylType field_type = VYL_TYPE_INT;
    char *custom_name = NULL;

    if (type_tok.type == TOKEN_KEYWORD_INT) {
      field_type = VYL_TYPE_INT;
      consume_token(parser, TOKEN_KEYWORD_INT, NULL);
    } else if (type_tok.type == TOKEN_KEYWORD_STRING) {
      field_type = VYL_TYPE_STRING;
      consume_token(parser, TOKEN_KEYWORD_STRING, NULL);
    } else if (type_tok.type == TOKEN_KEYWORD_DEC) {
      field_type = VYL_TYPE_DEC;
      consume_token(parser, TOKEN_KEYWORD_DEC, NULL);
    } else if (type_tok.type == TOKEN_KEYWORD_BOOL) {
      field_type = VYL_TYPE_BOOL;
      consume_token(parser, TOKEN_KEYWORD_BOOL, NULL);
    } else if (type_tok.type == TOKEN_ID) {
      field_type = VYL_TYPE_CUSTOM;
      custom_name = strdup(consume_token(parser, TOKEN_ID, NULL).value);
    }

    Token field_name = consume_token(parser, TOKEN_ID, NULL);
    if (peek_token(parser).type == TOKEN_VYL_NEWLINE) {
      consume_token(parser, TOKEN_VYL_NEWLINE, NULL);
    }

    if (count >= capacity) {
      capacity *= 2;
      fields = realloc(fields, sizeof(StructField) * capacity);
    }
    fields[count].type = field_type;
    fields[count].name = strdup(field_name.value);
    fields[count].custom_type_name = custom_name;
    count++;
  }

  consume_token(parser, TOKEN_RBRACE, NULL);

  StructDefNode *node = malloc(sizeof(StructDefNode));
  node->base.type = NODE_STRUCT_DEF;
  node->base.next = NULL;
  node->name = strdup(name.value);
  node->field_count = count;
  node->fields = fields;
  return (ASTNode *)node;
}

// Helper to read file
static char *parser_read_file(const char *path) {
  FILE *f = fopen(path, "r");
  if (!f)
    return NULL;
  fseek(f, 0, SEEK_END);
  long length = ftell(f);
  fseek(f, 0, SEEK_SET);
  char *buf = malloc(length + 1);
  if (fread(buf, 1, length, f) != (size_t)length) {
    free(buf);
    fclose(f);
    return NULL;
  }
  buf[length] = '\0';
  fclose(f);
  return buf;
}

ASTNode *parse_include(Parser *parser) {
  consume_token(parser, TOKEN_KEYWORD, "include");
  Token path_tok = consume_token(parser, TOKEN_STRING, NULL);
  char *path = path_tok.value;

  char *source = parser_read_file(path);
  if (!source) {
    fprintf(stderr, "Error: Could not include file '%s'\n", path);
    exit(1);
  }

  Lexer lexer;
  lexer_init(&lexer, source);
  int count;
  Token *tokens = lexer_tokenize(&lexer, &count);
  free(source);

  Parser sub_parser;
  parser_init(&sub_parser, tokens, count);
  ASTNode *sub_ast = parser_parse(&sub_parser);

  // sub_ast is a ProgramNode. We want its nodes.
  ASTNode *results = ((ProgramNode *)sub_ast)->nodes;

  // Clean up sub-parser shell
  free(sub_ast);

  // FIX: Free tokens from the included file
  free_tokens(tokens, count);

  return results;
}

ASTNode *parse_import(Parser *parser) {
  consume_token(parser, TOKEN_KEYWORD, "import");
  Token mod = consume_token(parser, TOKEN_ID, NULL);
  // Optional semicolon
  if (peek_token(parser).type == TOKEN_SEMICOLON) {
    consume_token(parser, TOKEN_SEMICOLON, NULL);
  }

  ImportNode *node = malloc(sizeof(ImportNode));
  node->base.type = NODE_IMPORT;
  node->base.next = NULL;
  node->module = strdup(mod.value);
  return (ASTNode *)node;
}

ASTNode *parse_function(Parser *parser) {
  consume_token(parser, TOKEN_KEYWORD, "Function");
  Token name = consume_token(parser, TOKEN_ID, NULL);
  consume_token(parser, TOKEN_LPAREN, NULL);

  // Params
  char *params[16]; // Max 16 params for now
  int p_count = 0;
  if (peek_token(parser).type != TOKEN_RPAREN) {
    while (1) {
      Token p = consume_token(parser, TOKEN_ID, NULL);
      params[p_count++] = strdup(p.value);
      if (peek_token(parser).type == TOKEN_COMMA) {
        consume_token(parser, TOKEN_COMMA, NULL);
      } else {
        break;
      }
    }
  }
  consume_token(parser, TOKEN_RPAREN, NULL);

  ASTNode *body = parse_block(parser);

  FunctionDefNode *node = malloc(sizeof(FunctionDefNode));
  node->base.type = NODE_FUNCTION_DEF;
  node->base.next = NULL;
  node->name = strdup(name.value);
  node->param_count = p_count;
  node->params = malloc(sizeof(char *) * p_count);
  for (int i = 0; i < p_count; i++)
    node->params[i] = params[i];
  node->body = body;
  return (ASTNode *)node;
}

ASTNode *parse_block(Parser *parser) {
  consume_token(parser, TOKEN_LBRACE, NULL);
  ASTNode *head = NULL;
  ASTNode *tail = NULL;
  while (peek_token(parser).type != TOKEN_RBRACE &&
         peek_token(parser).type != TOKEN_EOF) {
    ASTNode *stmt = parse_statement(parser);
    if (head == NULL) {
      head = stmt;
      tail = stmt;
    } else {
      tail->next = stmt;
      tail = stmt;
    }
  }
  consume_token(parser, TOKEN_RBRACE, NULL);
  return head; // Should wrap in BlockNode if needed, but returning list is fine
               // for now
}

ASTNode *parse_return(Parser *parser) {
  consume_token(parser, TOKEN_KEYWORD, "return");
  ASTNode *expr = parse_expression(parser);
  if (peek_token(parser).type == TOKEN_SEMICOLON) {
    consume_token(parser, TOKEN_SEMICOLON, NULL);
  }
  ReturnNode *node = malloc(sizeof(ReturnNode));
  node->base.type = NODE_RETURN;
  node->base.next = NULL;
  node->expr = expr;
  return (ASTNode *)node;
}

// Simple primary expression parser
ASTNode *parse_primary(Parser *parser) {
  Token t = peek_token(parser);
  ASTNode *node = NULL;

  if (t.type == TOKEN_KEYWORD_NEW) {
    consume_token(parser, TOKEN_KEYWORD_NEW, NULL);
    Token type_name = consume_token(parser, TOKEN_ID, NULL);
    NewNode *nn = malloc(sizeof(NewNode));
    nn->base.type = NODE_NEW;
    nn->base.next = NULL;
    nn->type_name = strdup(type_name.value);
    node = (ASTNode *)nn;
  } else if (t.type == TOKEN_NUMBER) {
    consume_token(parser, TOKEN_NUMBER, NULL);
    NumberNode *nnode = malloc(sizeof(NumberNode));
    nnode->base.type = NODE_NUMBER;
    nnode->base.next = NULL;
    nnode->value = atoi(t.value);
    node = (ASTNode *)nnode;
  } else if (t.type == TOKEN_DECIMAL) {
    consume_token(parser, TOKEN_DECIMAL, NULL);
    DecimalNode *dnode = malloc(sizeof(DecimalNode));
    dnode->base.type = NODE_DECIMAL;
    dnode->base.next = NULL;
    dnode->value = atof(t.value);
    node = (ASTNode *)dnode;
  } else if (t.type == TOKEN_STRING) {
    consume_token(parser, TOKEN_STRING, NULL);
    StringNode *snode = malloc(sizeof(StringNode));
    snode->base.type = NODE_STRING;
    snode->base.next = NULL;
    snode->value = strdup(t.value);
    node = (ASTNode *)snode;
  } else if (t.type == TOKEN_ID) {
    // Variable or Function Call
    Token id = consume_token(parser, TOKEN_ID, NULL);
    if (peek_token(parser).type == TOKEN_LPAREN) {
      // Function Call
      consume_token(parser, TOKEN_LPAREN, NULL);
      ASTNode *args_head = NULL;
      ASTNode *args_tail = NULL;
      if (peek_token(parser).type != TOKEN_RPAREN) {
        while (1) {
          ASTNode *arg = parse_expression(parser);
          if (!args_head) {
            args_head = arg;
            args_tail = arg;
          } else {
            args_tail->next = arg;
            args_tail = arg;
          }

          if (peek_token(parser).type == TOKEN_COMMA) {
            consume_token(parser, TOKEN_COMMA, NULL);
          } else {
            break;
          }
        }
      }
      consume_token(parser, TOKEN_RPAREN, NULL);
      CallNode *cnode = malloc(sizeof(CallNode));
      cnode->base.type = NODE_CALL;
      cnode->base.next = NULL;
      cnode->callee = strdup(id.value);
      cnode->args = args_head;
      node = (ASTNode *)cnode;
    } else {
      // Variable reference
      VarNode *vnode = malloc(sizeof(VarNode));
      vnode->base.type = NODE_VAR;
      vnode->base.next = NULL;
      vnode->name = strdup(id.value);
      if (peek_token(parser).type == TOKEN_LBRACKET) {
        consume_token(parser, TOKEN_LBRACKET, NULL);
        ASTNode *idx = parse_expression(parser);
        consume_token(parser, TOKEN_RBRACKET, NULL);
        IndexNode *inode = malloc(sizeof(IndexNode));
        inode->base.type = NODE_INDEX;
        inode->base.next = NULL;
        inode->base_expr = (ASTNode *)vnode;
        inode->index = idx;
        node = (ASTNode *)inode;
      } else {
        node = (ASTNode *)vnode;
      }
    }
  } else if (t.type == TOKEN_VYL_NEWLINE) {
    consume_token(parser, TOKEN_VYL_NEWLINE, NULL);
    ASTNode *nnode = malloc(sizeof(ASTNode));
    nnode->type = NODE_VYL_NEWLINE;
    nnode->next = NULL;
    node = nnode;
  } else if (t.type == TOKEN_LPAREN) {
    consume_token(parser, TOKEN_LPAREN, NULL);
    ASTNode *expr = parse_expression(parser);
    consume_token(parser, TOKEN_RPAREN, NULL);
    node = expr;
  } else {
    fprintf(stderr, "Unexpected token in expression: %s line %d\n",
            t.value ? t.value : token_type_to_string(t.type), t.line);
    exit(1);
  }

  // Postfix loop for member access
  while (peek_token(parser).type == TOKEN_DOT) {
    consume_token(parser, TOKEN_DOT, NULL);
    Token member = consume_token(parser, TOKEN_ID, NULL);
    MemberAccessNode *ma = malloc(sizeof(MemberAccessNode));
    ma->base.type = NODE_MEMBER_ACCESS;
    ma->base.next = NULL;
    ma->struct_expr = node;
    ma->member_name = strdup(member.value);
    node = (ASTNode *)ma;
  }

  return node;
}

// Precedence:
// primary -> math (+, -) -> mult (*, /) -> comparison (<, >, ==)
// Actually let's do:
// primary -> factor (*, /) -> sum (+, -) -> comparison (==, <, >)

ASTNode *parse_factor(Parser *parser) {
  ASTNode *left = parse_primary(parser);
  while (1) {
    Token t = peek_token(parser);
    if (t.type == TOKEN_STAR || t.type == TOKEN_SLASH || t.type == TOKEN_MOD) {
      consume_token(parser, t.type, NULL);
      ASTNode *right = parse_primary(parser);

      // Constant Folding
      if (left->type == NODE_NUMBER && right->type == NODE_NUMBER) {
        int a = ((NumberNode *)left)->value;
        int b = ((NumberNode *)right)->value;
        int res = (t.type == TOKEN_STAR) ? (a * b) : (a / b);
        ((NumberNode *)left)->value = res;
        free_ast(right);
        continue;
      } else if (left->type == NODE_DECIMAL && right->type == NODE_DECIMAL) {
        double a = ((DecimalNode *)left)->value;
        double b = ((DecimalNode *)right)->value;
        double res = (t.type == TOKEN_STAR) ? (a * b) : (a / b);
        ((DecimalNode *)left)->value = res;
        free_ast(right);
        continue;
      }

      BinaryNode *node = malloc(sizeof(BinaryNode));
      node->base.type = NODE_BINARY_OP;
      node->base.next = NULL;
      node->op = t.type;
      node->left = left;
      node->right = right;
      left = (ASTNode *)node;
    } else
      break;
  }
  return left;
}

ASTNode *parse_sum(Parser *parser) {
  ASTNode *left = parse_factor(parser);
  while (1) {
    Token t = peek_token(parser);
    if (t.type == TOKEN_PLUS || t.type == TOKEN_MINUS) {
      consume_token(parser, t.type, NULL);
      ASTNode *right = parse_factor(parser);

      // Constant Folding for numbers
      if (left->type == NODE_NUMBER && right->type == NODE_NUMBER) {
        int a = ((NumberNode *)left)->value;
        int b = ((NumberNode *)right)->value;
        int res = (t.type == TOKEN_PLUS) ? (a + b) : (a - b);
        ((NumberNode *)left)->value = res;
        free_ast(right);
        continue;
      } else if (left->type == NODE_DECIMAL && right->type == NODE_DECIMAL) {
        double a = ((DecimalNode *)left)->value;
        double b = ((DecimalNode *)right)->value;
        double res = (t.type == TOKEN_PLUS) ? (a + b) : (a - b);
        ((DecimalNode *)left)->value = res;
        free_ast(right);
        continue;
      }
      
      // String concatenation with + operator
      if (t.type == TOKEN_PLUS && left->type == NODE_STRING && right->type == NODE_STRING) {
        char *a = ((StringNode *)left)->value;
        char *b = ((StringNode *)right)->value;
        size_t len = strlen(a) + strlen(b) + 1;
        char *result = malloc(len);
        strcpy(result, a);
        strcat(result, b);
        ((StringNode *)left)->value = result;
        free_ast(right);
        continue;
      }

      BinaryNode *node = malloc(sizeof(BinaryNode));
      node->base.type = NODE_BINARY_OP;
      node->base.next = NULL;
      node->op = t.type;
      node->left = left;
      node->right = right;
      left = (ASTNode *)node;
    } else
      break;
  }
  return left;
}

ASTNode *parse_comparison(Parser *parser) {
  ASTNode *left = parse_sum(parser);
  while (1) {
    Token t = peek_token(parser);
    if (t.type == TOKEN_EQ || t.type == TOKEN_NEQ || t.type == TOKEN_LT ||
        t.type == TOKEN_GT || t.type == TOKEN_LE || t.type == TOKEN_GE) {
      consume_token(parser, t.type, NULL);
      ASTNode *right = parse_sum(parser);

      // Constant Folding
      if (left->type == NODE_NUMBER && right->type == NODE_NUMBER) {
        int a = ((NumberNode *)left)->value;
        int b = ((NumberNode *)right)->value;
        int res = 0;
        if (t.type == TOKEN_LT)
          res = (a < b);
        else if (t.type == TOKEN_GT)
          res = (a > b);
        else if (t.type == TOKEN_EQ)
          res = (a == b);
        ((NumberNode *)left)->value = res;
        free_ast(right);
        continue;
      }

      BinaryNode *node = malloc(sizeof(BinaryNode));
      node->base.type = NODE_BINARY_OP;
      node->base.next = NULL;
      node->op = t.type;
      node->left = left;
      node->right = right;
      left = (ASTNode *)node;
    } else
      break;
  }
  return left;
}

ASTNode *parse_logic(Parser *parser) {
  ASTNode *left = parse_comparison(parser);
  while (1) {
    Token t = peek_token(parser);
    if (t.type == TOKEN_AND || t.type == TOKEN_OR) {
      consume_token(parser, t.type, NULL);
      ASTNode *right = parse_comparison(parser);
      BinaryNode *node = malloc(sizeof(BinaryNode));
      node->base.type = NODE_BINARY_OP;
      node->base.next = NULL;
      node->op = t.type;
      node->left = left;
      node->right = right;
      left = (ASTNode *)node;
    } else
      break;
  }
  return left;
}

ASTNode *parse_expression(Parser *parser) { return parse_logic(parser); }

ASTNode *parse_if(Parser *parser) {
  consume_token(parser, TOKEN_KEYWORD, "if");
  consume_token(parser, TOKEN_LPAREN, NULL);
  ASTNode *cond = parse_expression(parser);
  consume_token(parser, TOKEN_RPAREN, NULL);

  ASTNode *then_block = parse_block(parser);
  ASTNode *else_block = NULL;

  if (peek_token(parser).type == TOKEN_KEYWORD &&
      strcmp(peek_token(parser).value, "else") == 0) {
    consume_token(parser, TOKEN_KEYWORD, "else");
    if (peek_token(parser).type == TOKEN_LBRACE) {
      else_block = parse_block(parser);
    } else if (peek_token(parser).type == TOKEN_KEYWORD &&
               strcmp(peek_token(parser).value, "if") == 0) {
      else_block = parse_if(parser);
    }
  }

  IfNode *node = malloc(sizeof(IfNode));
  node->base.type = NODE_IF;
  node->base.next = NULL;
  node->condition = cond;
  node->then_block = then_block;
  node->else_block = else_block;
  return (ASTNode *)node;
}

ASTNode *parse_var_decl(Parser *parser) {
  consume_token(parser, TOKEN_KEYWORD_VAR, NULL);
  Token type_tok = peek_token(parser);
  VylType type = VYL_TYPE_INT; // Default
  char *custom_type_name = NULL;

  if (type_tok.type == TOKEN_KEYWORD_INT) {
    type = VYL_TYPE_INT;
    consume_token(parser, TOKEN_KEYWORD_INT, NULL);
  } else if (type_tok.type == TOKEN_KEYWORD_STRING) {
    type = VYL_TYPE_STRING;
    consume_token(parser, TOKEN_KEYWORD_STRING, NULL);
  } else if (type_tok.type == TOKEN_KEYWORD_DEC) {
    type = VYL_TYPE_DEC;
    consume_token(parser, TOKEN_KEYWORD_DEC, NULL);
  } else if (type_tok.type == TOKEN_KEYWORD_BOOL) {
    type = VYL_TYPE_BOOL;
    consume_token(parser, TOKEN_KEYWORD_BOOL, NULL);
  } else if (type_tok.type == TOKEN_ID) {
    // Check if it's a type name... for now assume ID after 'var' before name is
    // a type Wait, VYL syntax so far: 'var name = expr' or 'var type name =
    // expr' If it's TOKEN_ID and the NEXT token is also TOKEN_ID, then it's a
    // custom type.
    if (peek_token_ahead(parser, 1).type == TOKEN_ID ||
        peek_token_ahead(parser, 1).type == TOKEN_LBRACKET) {
      type = VYL_TYPE_CUSTOM;
      custom_type_name = strdup(type_tok.value);
      consume_token(parser, TOKEN_ID, NULL);
    }
  } else {
    fprintf(stderr,
            "Parser Error: Expected type or variable name after 'var'\n");
    exit(1);
  }

  int array_size = 0;
  if (peek_token(parser).type == TOKEN_LBRACKET) {
    consume_token(parser, TOKEN_LBRACKET, NULL);
    Token size_tok = consume_token(parser, TOKEN_NUMBER, NULL);
    array_size = atoi(size_tok.value);
    consume_token(parser, TOKEN_RBRACKET, NULL);
  }

  Token name = consume_token(parser, TOKEN_ID, NULL);
  ASTNode *init = NULL;
  if (peek_token(parser).type == TOKEN_ASSIGN) {
    consume_token(parser, TOKEN_ASSIGN, NULL);
    init = parse_expression(parser);
  }

  if (peek_token(parser).type == TOKEN_SEMICOLON) {
    consume_token(parser, TOKEN_SEMICOLON, NULL);
  }

  VarDeclNode *node = malloc(sizeof(VarDeclNode));
  node->base.type = NODE_VAR_DECL;
  node->base.next = NULL;
  node->type = type;
  node->name = strdup(name.value);
  node->custom_type_name = custom_type_name;
  node->init = init;
  node->array_size = array_size;
  return (ASTNode *)node;
}

ASTNode *parse_while(Parser *parser) {
  consume_token(parser, TOKEN_KEYWORD_WHILE, NULL);
  consume_token(parser, TOKEN_LPAREN, NULL);
  ASTNode *cond = parse_expression(parser);
  consume_token(parser, TOKEN_RPAREN, NULL);
  ASTNode *body = parse_block(parser);

  WhileNode *node = malloc(sizeof(WhileNode));
  node->base.type = NODE_WHILE;
  node->base.next = NULL;
  node->condition = cond;
  node->body = body;
  return (ASTNode *)node;
}

ASTNode *parse_for(Parser *parser) {
  consume_token(parser, TOKEN_KEYWORD_FOR, NULL);
  Token id = consume_token(parser, TOKEN_ID, NULL);
  consume_token(parser, TOKEN_KEYWORD_IN, NULL);
  ASTNode *start = parse_expression(parser);
  consume_token(parser, TOKEN_DOTDOT, NULL);
  ASTNode *end = parse_expression(parser);
  ASTNode *body = parse_block(parser);

  ForNode *node = malloc(sizeof(ForNode));
  node->base.type = NODE_FOR;
  node->base.next = NULL;
  node->iterator_name = strdup(id.value);
  node->start = start;
  node->end = end;
  node->body = body;
  return (ASTNode *)node;
}

ASTNode *parse_match(Parser *parser) {
  consume_token(parser, TOKEN_KEYWORD_MATCH, NULL);
  ASTNode *target = parse_expression(parser);
  consume_token(parser, TOKEN_LBRACE, NULL);

  MatchCase *cases = NULL;
  int count = 0;
  int capacity = 0;

  while (peek_token(parser).type != TOKEN_RBRACE &&
         peek_token(parser).type != TOKEN_EOF) {
    ASTNode *val = NULL;
    if (peek_token(parser).type == TOKEN_UNDERSCORE) {
      consume_token(parser, TOKEN_UNDERSCORE, NULL);
    } else {
      val = parse_expression(parser);
    }

    consume_token(parser, TOKEN_ARROW, NULL);
    ASTNode *body =
        parse_block(parser); // parse_block expects { ... } or just a statement?
    // VYL blocks are usually { ... }. But match cases might be single
    // statements. parse_block in VYL parser logic handles { } check internally
    // usually? Let's check parse_block. If it requires {, then we are good. If
    // not, we might need to enforce braces or allow single stmt. For now
    // assuming braces are required as per design.

    if (count >= capacity) {
      capacity = capacity == 0 ? 4 : capacity * 2;
      cases = realloc(cases, sizeof(MatchCase) * capacity);
    }
    cases[count].value = val;
    cases[count].body = body;
    count++;
  }
  consume_token(parser, TOKEN_RBRACE, NULL);

  MatchNode *node = malloc(sizeof(MatchNode));
  node->base.type = NODE_MATCH;
  node->base.next = NULL;
  node->target = target;
  node->case_count = count;
  node->cases = cases;
  return (ASTNode *)node;
}

ASTNode *parse_statement(Parser *parser) {
  Token t = peek_token(parser);
  if (t.type == TOKEN_KEYWORD_VAR) {
    return parse_var_decl(parser);
  }
  if (t.type == TOKEN_KEYWORD_WHILE) {
    return parse_while(parser);
  }
  if (t.type == TOKEN_KEYWORD_FOR) {
    return parse_for(parser);
  }
  if (t.type == TOKEN_KEYWORD_MATCH) {
    return parse_match(parser);
  }
  if (t.type == TOKEN_KEYWORD_BREAK) {
    consume_token(parser, TOKEN_KEYWORD_BREAK, NULL);
    if (peek_token(parser).type == TOKEN_SEMICOLON) {
      consume_token(parser, TOKEN_SEMICOLON, NULL);
    }
    ASTNode *node = malloc(sizeof(ASTNode));
    node->type = NODE_BREAK;
    node->next = NULL;
    return node;
  }
  if (t.type == TOKEN_KEYWORD_CONTINUE) {
    consume_token(parser, TOKEN_KEYWORD_CONTINUE, NULL);
    if (peek_token(parser).type == TOKEN_SEMICOLON) {
      consume_token(parser, TOKEN_SEMICOLON, NULL);
    }
    ASTNode *node = malloc(sizeof(ASTNode));
    node->type = NODE_CONTINUE;
    node->next = NULL;
    return node;
  }
  if (t.type == TOKEN_KEYWORD) {
    if (strcmp(t.value, "return") == 0)
      return parse_return(parser);
    if (strcmp(t.value, "if") == 0)
      return parse_if(parser);
    if (strcmp(t.value, "Print") == 0) {
      consume_token(parser, TOKEN_KEYWORD, "Print");
      consume_token(parser, TOKEN_LPAREN, NULL);

      ASTNode *head = NULL;
      ASTNode *tail = NULL;

      while (peek_token(parser).type != TOKEN_RPAREN &&
             peek_token(parser).type != TOKEN_EOF) {
        ASTNode *arg = parse_expression(parser);
        if (!head) {
          head = arg;
          tail = arg;
        } else {
          tail->next = arg;
          tail = arg;
        }

        if (peek_token(parser).type == TOKEN_COMMA) {
          consume_token(parser, TOKEN_COMMA, NULL);
        }
      }

      consume_token(parser, TOKEN_RPAREN, NULL);
      if (peek_token(parser).type == TOKEN_SEMICOLON) {
        consume_token(parser, TOKEN_SEMICOLON, NULL);
      }
      CallNode *node = malloc(sizeof(CallNode));
      node->base.type = NODE_CALL;
      node->base.next = NULL;
      node->callee = strdup("Print");
      node->args = head;
      return (ASTNode *)node;
    }
  }

  ASTNode *expr = parse_expression(parser);
  if (peek_token(parser).type == TOKEN_ASSIGN) {
    consume_token(parser, TOKEN_ASSIGN, NULL);
    ASTNode *val = parse_expression(parser);
    if (peek_token(parser).type == TOKEN_SEMICOLON) {
      consume_token(parser, TOKEN_SEMICOLON, NULL);
    }

    // Check if expr is a valid lvalue
    if (expr->type != NODE_VAR && expr->type != NODE_INDEX &&
        expr->type != NODE_MEMBER_ACCESS) {
      fprintf(stderr, "Parser Error: Invalid assignment target type %d\n",
              expr->type);
      exit(1);
    }

    AssignmentNode *node = malloc(sizeof(AssignmentNode));
    node->base.type = NODE_ASSIGN;
    node->base.next = NULL;
    node->target = expr;
    node->expr = val;
    return (ASTNode *)node;
  }

  if (peek_token(parser).type == TOKEN_SEMICOLON) {
    consume_token(parser, TOKEN_SEMICOLON, NULL);
  }
  return expr;
}

ASTNode *parse_main(Parser *parser) {
  // Support Main() or Main(argc, argv)
  consume_token(parser, TOKEN_KEYWORD, "Main");
  consume_token(parser, TOKEN_LPAREN, NULL);
  
  // Parse parameters if any
  int param_count = 0;
  char **params = malloc(sizeof(char *) * 6);  // Pre-allocate to simplify cleanup
  
  Token t = peek_token(parser);
  if (t.type != TOKEN_RPAREN) {
    while (t.type != TOKEN_RPAREN && param_count < 6) {
      Token param = consume_token(parser, TOKEN_ID, NULL);
      params[param_count] = strdup(param.value);
      param_count++;
      
      t = peek_token(parser);
      if (t.type == TOKEN_COMMA) {
        consume_token(parser, TOKEN_COMMA, NULL);
        t = peek_token(parser);
      }
    }
  }
  
  consume_token(parser, TOKEN_RPAREN, NULL);
  
  ASTNode *body = parse_block(parser);
  
  // Wrap in a FunctionDefNode to represent Main with parameters
  if (param_count > 0) {
    FunctionDefNode *fn = malloc(sizeof(FunctionDefNode));
    fn->base.type = NODE_MAIN;
    fn->base.next = NULL;
    fn->name = malloc(5);
    strcpy(fn->name, "main");
    fn->param_count = param_count;
    fn->params = params;
    fn->body = body;
    return (ASTNode *)fn;
  }
  
  // Free unused params array when no parameters
  free(params);
  return body; // Return list of statements
}

ASTNode *parser_parse(Parser *parser) {
  ASTNode *head = NULL;
  ASTNode *tail = NULL;

  while (peek_token(parser).type != TOKEN_EOF) {
    ASTNode *node = NULL;
    Token t = peek_token(parser);

    if (t.type == TOKEN_KEYWORD && strcmp(t.value, "import") == 0) {
      node = parse_import(parser);
    } else if (t.type == TOKEN_KEYWORD && strcmp(t.value, "include") == 0) {
      ASTNode *included = parse_include(parser);
      if (included) {
        if (head == NULL) {
          head = included;
          tail = included;
        } else {
          tail->next = included;
        }
        while (tail && tail->next)
          tail = tail->next;
      }
      continue;
    } else if (t.type == TOKEN_KEYWORD_STRUCT) {
      node = parse_struct(parser);
    } else if (t.type == TOKEN_KEYWORD && strcmp(t.value, "Function") == 0) {
      node = parse_function(parser);
    } else if (t.type == TOKEN_KEYWORD && strcmp(t.value, "Main") == 0) {
      ASTNode *body = parse_main(parser);
      if (head == NULL) {
        head = body;
        tail = body;
      } else {
        tail->next = body;
        tail = body;
      }
      // Move tail to the end of the block
      while (tail && tail->next)
        tail = tail->next;
      continue; // Skip the default head/tail logic at bottom
    } else {
      // Top-level statement
      node = parse_statement(parser);
    }

    if (node) {
      if (head == NULL) {
        head = node;
        tail = node;
      } else {
        tail->next = node;
        tail = node;
      }
    }
  }

  ProgramNode *prog = malloc(sizeof(ProgramNode));
  prog->base.type = NODE_PROGRAM;
  prog->base.next = NULL;
  prog->nodes = head;
  return (ASTNode *)prog;
}

void free_ast(ASTNode *node) {
  while (node) {
    ASTNode *next = node->next;

    if (node->type == NODE_PROGRAM) {
      free_ast(((ProgramNode *)node)->nodes);
    } else if (node->type == NODE_FUNCTION_DEF || node->type == NODE_MAIN) {
      FunctionDefNode *fn = (FunctionDefNode *)node;
      if (fn->name)
        free(fn->name);
      for (int i = 0; i < fn->param_count; i++)
        free(fn->params[i]);
      if (fn->params)
        free(fn->params);
      free_ast(fn->body);
    } else if (node->type == NODE_BLOCK) {
      // Block usually just returns a list, but if wrapper exists in future:
      // free_ast(((BlockNode*)node)->statements);
    } else if (node->type == NODE_CALL) {
      CallNode *call = (CallNode *)node;
      if (call->callee)
        free(call->callee);
      free_ast(call->args);
    } else if (node->type == NODE_IMPORT) {
      ImportNode *imp = (ImportNode *)node;
      if (imp->module)
        free(imp->module);
    } else if (node->type == NODE_STRING) {
      StringNode *s = (StringNode *)node;
      if (s->value)
        free(s->value);
    } else if (node->type == NODE_NUMBER) {
      // Nothing extra
    } else if (node->type == NODE_DECIMAL) {
      // Nothing extra
    } else if (node->type == NODE_VAR) {
      VarNode *v = (VarNode *)node;
      if (v->name)
        free(v->name);
    } else if (node->type == NODE_RETURN) {
      ReturnNode *ret = (ReturnNode *)node;
      free_ast(ret->expr);
    } else if (node->type == NODE_BINARY_OP) {
      BinaryNode *bin = (BinaryNode *)node;
      free_ast(bin->left);
      free_ast(bin->right);
    } else if (node->type == NODE_IF) {
      IfNode *ifn = (IfNode *)node;
      free_ast(ifn->condition);
      free_ast(ifn->then_block);
      free_ast(ifn->else_block);
    } else if (node->type == NODE_ASSIGN) {
      AssignmentNode *assign = (AssignmentNode *)node;
      free_ast(assign->target);
      free_ast(assign->expr);
    } else if (node->type == NODE_INDEX) {
      IndexNode *in = (IndexNode *)node;
      free_ast(in->base_expr);
      free_ast(in->index);
    } else if (node->type == NODE_VAR_DECL) {
      VarDeclNode *decl = (VarDeclNode *)node;
      if (decl->name)
        free(decl->name);
      if (decl->custom_type_name)
        free(decl->custom_type_name);
      free_ast(decl->init);
    } else if (node->type == NODE_STRUCT_DEF) {
      StructDefNode *s = (StructDefNode *)node;
      if (s->name)
        free(s->name);
      for (int i = 0; i < s->field_count; i++) {
        if (s->fields[i].name)
          free(s->fields[i].name);
        if (s->fields[i].custom_type_name)
          free(s->fields[i].custom_type_name);
      }
      if (s->fields)
        free(s->fields);
    } else if (node->type == NODE_NEW) {
      NewNode *n = (NewNode *)node;
      if (n->type_name)
        free(n->type_name);
    } else if (node->type == NODE_FOR) {
      ForNode *f = (ForNode *)node;
      if (f->iterator_name)
        free(f->iterator_name);
      free_ast(f->start);
      free_ast(f->end);
      free_ast(f->body);
    } else if (node->type == NODE_MATCH) {
      MatchNode *m = (MatchNode *)node;
      free_ast(m->target);
      for (int i = 0; i < m->case_count; i++) {
        free_ast(m->cases[i].value);
        free_ast(m->cases[i].body);
      }
      if (m->cases)
        free(m->cases);
    } else if (node->type == NODE_MEMBER_ACCESS) {
      MemberAccessNode *ma = (MemberAccessNode *)node;
      free_ast(ma->struct_expr);
      if (ma->member_name)
        free(ma->member_name);
    } else if (node->type == NODE_WHILE) {
      WhileNode *wn = (WhileNode *)node;
      free_ast(wn->condition);
      free_ast(wn->body);
    } else if (node->type == NODE_VYL_NEWLINE) {
      // Just the node
    } else if (node->type == NODE_BREAK) {
      // Just the node
    } else if (node->type == NODE_CONTINUE) {
      // Just the node
    }

    free(node);
    node = next;
  }
}
