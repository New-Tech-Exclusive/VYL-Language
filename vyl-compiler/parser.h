#ifndef PARSER_H
#define PARSER_H

#include "lexer.h"

typedef enum {
  NODE_PROGRAM,
  NODE_FUNCTION_DEF,
  NODE_MAIN, // Keep for backward compat, though treat like Function
  NODE_BLOCK,
  NODE_CALL,
  NODE_IMPORT,
  NODE_STRING,
  NODE_NUMBER,
  NODE_VAR, // Variable reference
  NODE_RETURN,
  NODE_BINARY_OP, // a + b
  NODE_VYL_NEWLINE,
  NODE_IF,
  NODE_ASSIGN,
  NODE_WHILE,
  NODE_VAR_DECL,
  NODE_DECIMAL,
  NODE_INDEX,
  NODE_STRUCT_DEF,
  NODE_MEMBER_ACCESS,
  NODE_NEW,
  NODE_FOR,
  NODE_MATCH
} NodeType;

typedef struct ASTNode {
  NodeType type;
  struct ASTNode *next; // Linked list for sequences
} ASTNode;

typedef struct {
  ASTNode base;
  ASTNode *nodes; // Mix of Functions and Top-level statements
} ProgramNode;

typedef struct {
  ASTNode base;
  char *name;
  // Parameters could be a list of strings
  int param_count;
  char **params;
  ASTNode *body;
} FunctionDefNode;

typedef struct {
  ASTNode base;
  ASTNode *body;
} MainNode;

typedef struct {
  ASTNode base;
  char *callee;  // Function name being called
  ASTNode *args; // Linked list of expression nodes
} CallNode;

typedef struct {
  ASTNode base;
  char *module;
} ImportNode;

typedef struct {
  ASTNode base;
  char *value;
} StringNode;

typedef struct {
  ASTNode base;
  double value;
} DecimalNode;

typedef struct {
  ASTNode base;
  int value;
} NumberNode;

typedef struct {
  ASTNode base;
  char *name;
} VarNode;

typedef struct {
  ASTNode base;
  ASTNode *target; // NODE_VAR or NODE_INDEX
  ASTNode *expr;
} AssignmentNode;

typedef enum {
  VYL_TYPE_INT,
  VYL_TYPE_STRING,
  VYL_TYPE_DEC,
  VYL_TYPE_BOOL,
  VYL_TYPE_CUSTOM
} VylType;

typedef struct {
  VylType type;
  char *name;
  char *custom_type_name; // if VYL_TYPE_CUSTOM
} StructField;

typedef struct {
  ASTNode base;
  char *name;
  int field_count;
  StructField *fields;
} StructDefNode;

typedef struct {
  ASTNode base;
  ASTNode *struct_expr;
  char *member_name;
} MemberAccessNode;

typedef struct {
  ASTNode base;
  char *type_name;
} NewNode;

typedef struct {
  ASTNode base;
  VylType type;
  char *name;
  char *custom_type_name; // if VYL_TYPE_CUSTOM
  ASTNode *init;
  int array_size; // 0 if scalar
} VarDeclNode;

typedef struct {
  ASTNode base;
  ASTNode *base_expr;
  ASTNode *index;
} IndexNode;

typedef struct {
  ASTNode base;
  ASTNode *expr;
} ReturnNode;

typedef struct {
  ASTNode base;
  TokenType op; // TOKEN_PLUS etc
  ASTNode *left;
  ASTNode *right;
} BinaryNode;

typedef struct {
  ASTNode base;
  ASTNode *condition;
  ASTNode *body;
} WhileNode;

typedef struct {
  ASTNode base;
  ASTNode *condition;
  ASTNode *then_block;
  ASTNode *else_block;
} IfNode;

typedef struct {
  ASTNode base;
  char *iterator_name;
  ASTNode *start;
  ASTNode *end;
  ASTNode *body;
} ForNode;

typedef struct {
  ASTNode *value; // NULL for default case (_)
  ASTNode *body;
} MatchCase;

typedef struct {
  ASTNode base;
  ASTNode *target;
  int case_count;
  MatchCase *cases;
} MatchNode;

typedef struct {
  ASTNode base;
  Token *tokens;
  int count;
  int pos;
} Parser;

void parser_init(Parser *parser, Token *tokens, int count);
ASTNode *parser_parse(Parser *parser);
void free_ast(ASTNode *node);

#endif
