#ifndef CODEGEN_H
#define CODEGEN_H

#include "parser.h"
#include <stdio.h>

typedef struct {
  char *name;
  int offset;
  VylType type;
  int array_size; // 0 for scalars, >0 for arrays
  const char *reg; // Assigned register, or NULL if on stack
  char *custom_type_name;
} LocalVar;

typedef struct {
  char *name;
  int field_count;
  char **field_names;
} StructInfo;

typedef struct {
  FILE *out;
  int string_count;
  LocalVar locals[64];
  int local_count;
  int stack_pointer;
  StructInfo structs[32];
  int struct_count;
  // Loop context for break/continue
  const char *current_loop_start;
  const char *current_loop_end;
} CodeGen;

void codegen_init(CodeGen *cg, FILE *out);
void codegen_generate(CodeGen *cg, ASTNode *node);
void codegen_free();
void codegen_cleanup(CodeGen *cg);

#endif
