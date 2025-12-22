#define _POSIX_C_SOURCE 200809L
#include "codegen.h"
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

// Forward declarations
void gen_statement(CodeGen *cg, ASTNode *node);
void gen_expr(CodeGen *cg, ASTNode *node);
void gen_if(CodeGen *cg, IfNode *node);

// Error reporting
static void codegen_error(const char *format, ...) {
  va_list args;
  va_start(args, format);
  fprintf(stderr, "CodeGen Error: ");
  vfprintf(stderr, format, args);
  fprintf(stderr, "\n");
  va_end(args);
}

void codegen_init(CodeGen *cg, FILE *out) {
  cg->out = out;
  cg->string_count = 0;
  cg->local_count = 0;
  cg->stack_pointer = 0;
  cg->struct_count = 0;
  cg->current_loop_start = NULL;
  cg->current_loop_end = NULL;
}

// Simple String Table
typedef struct StringConst {
  char *value;
  int id;
  int length;
  struct StringConst *next;
} StringConst;

StringConst *strings_head = NULL;

typedef struct DecimalConst {
  double value;
  int id;
  struct DecimalConst *next;
} DecimalConst;

DecimalConst *decimals_head = NULL;

int get_string_id(const char *value) {
  StringConst *cur = strings_head;
  while (cur) {
    if (strcmp(cur->value, value) == 0)
      return cur->id;
    cur = cur->next;
  }
  static int global_id = 0;
  StringConst *new_str = malloc(sizeof(StringConst));
  new_str->value = strdup(value);
  new_str->id = global_id++;
  new_str->next = strings_head;
  strings_head = new_str;
  return new_str->id;
}

int get_decimal_id(double value) {
  DecimalConst *cur = decimals_head;
  while (cur) {
    if (cur->value == value)
      return cur->id;
    cur = cur->next;
  }
  static int dec_global_id = 0;
  DecimalConst *new_dec = malloc(sizeof(DecimalConst));
  new_dec->value = value;
  new_dec->id = dec_global_id++;
  new_dec->next = decimals_head;
  decimals_head = new_dec;
  return new_dec->id;
}

const char *get_local_reg(CodeGen *cg, const char *name) {
  for (int i = 0; i < cg->local_count; i++) {
    if (strcmp(cg->locals[i].name, name) == 0)
      return cg->locals[i].reg;
  }
  return NULL;
}

int get_local_offset(CodeGen *cg, const char *name) {
  for (int i = 0; i < cg->local_count; i++) {
    if (strcmp(cg->locals[i].name, name) == 0)
      return cg->locals[i].offset;
  }
  return 0;
}

VylType get_local_type(CodeGen *cg, const char *name) {
  for (int i = 0; i < cg->local_count; i++) {
    if (strcmp(cg->locals[i].name, name) == 0)
      return cg->locals[i].type;
  }
  return VYL_TYPE_INT; // Default
}

VylType get_expr_type(CodeGen *cg, ASTNode *node) {
  if (!node)
    return VYL_TYPE_INT;
  if (node->type == NODE_NUMBER)
    return VYL_TYPE_INT;
  if (node->type == NODE_STRING)
    return VYL_TYPE_STRING;
  if (node->type == NODE_DECIMAL)
    return VYL_TYPE_DEC;
  if (node->type == NODE_VAR)
    return get_local_type(cg, ((VarNode *)node)->name);
  if (node->type == NODE_CALL) {
    CallNode *call = (CallNode *)node;
    if (strcmp(call->callee, "Clock") == 0)
      return VYL_TYPE_DEC;
  }

  return VYL_TYPE_INT;
}

int get_local_array_size(CodeGen *cg, const char *name) {
  for (int i = 0; i < cg->local_count; i++) {
    if (strcmp(cg->locals[i].name, name) == 0)
      return cg->locals[i].array_size;
  }
  return 1;
}

const char *get_local_custom_type_name(CodeGen *cg, const char *name) {
  for (int i = 0; i < cg->local_count; i++) {
    if (strcmp(cg->locals[i].name, name) == 0)
      return cg->locals[i].custom_type_name;
  }
  return NULL;
}

const char *get_expr_custom_type_name(CodeGen *cg, ASTNode *node) {
  if (!node)
    return NULL;
  if (node->type == NODE_VAR)
    return get_local_custom_type_name(cg, ((VarNode *)node)->name);
  if (node->type == NODE_NEW)
    return ((NewNode *)node)->type_name;
  if (node->type == NODE_MEMBER_ACCESS) {
    MemberAccessNode *ma = (MemberAccessNode *)node;
    const char *struct_name = get_expr_custom_type_name(cg, ma->struct_expr);
    if (!struct_name)
      return NULL;
    // Find field custom type... we only support nested structs if field is
    // CUSTOM For now we assume fields are int/dec/etc, but if they are custom:
    // We need to look up struct definition.
    for (int i = 0; i < cg->struct_count; i++) {
      if (strcmp(cg->structs[i].name, struct_name) == 0) {
        // Need field type info in StructInfo!
      }
    }
  }
  return NULL;
}

StructInfo *get_struct_info(CodeGen *cg, const char *name) {
  for (int i = 0; i < cg->struct_count; i++) {
    if (strcmp(cg->structs[i].name, name) == 0)
      return &cg->structs[i];
  }
  return NULL;
}

int get_field_offset(StructInfo *si, const char *field_name) {
  for (int i = 0; i < si->field_count; i++) {
    if (strcmp(si->field_names[i], field_name) == 0)
      return i * 8; // All fields 8 bytes for now
  }
  return -1;
}

void gen_cond_jmp(CodeGen *cg, ASTNode *cond, const char *label,
                  bool jump_if_true) {
  if (!cond) return;
  // Evaluate the condition into rax and jump based on zero/non-zero.
  gen_expr(cg, cond);
  fprintf(cg->out, "    cmp rax, 0\n");
  if (jump_if_true)
    fprintf(cg->out, "    jne %s\n", label);
  else
    fprintf(cg->out, "    je %s\n", label);
}

void gen_expr(CodeGen *cg, ASTNode *node) {
  if (!node) return;

  if (node->type == NODE_NUMBER) {
    fprintf(cg->out, "    mov rax, %d\n", ((NumberNode *)node)->value);
  } else if (node->type == NODE_VAR) {
    VarNode *var = (VarNode *)node;
    VylType type = get_local_type(cg, var->name);
    const char *reg = get_local_reg(cg, var->name);
    int offset = get_local_offset(cg, var->name);

    if (offset == 0 && reg == NULL) {
      codegen_error("Undefined variable '%s'", var->name);
      fprintf(cg->out, "    # Error: Undefined variable %s\n", var->name);
      return;
    }

    if (type == VYL_TYPE_DEC) {
      fprintf(cg->out, "    movsd xmm0, [rbp - %d]\n", offset);
    } else if (reg) {
      fprintf(cg->out, "    mov rax, %s\n", reg);
    } else {
      fprintf(cg->out, "    mov rax, [rbp - %d]\n", offset);
    }

  } else if (node->type == NODE_BINARY_OP) {
    BinaryNode *bin = (BinaryNode *)node;
    VylType left_type = get_expr_type(cg, bin->left);
    VylType right_type = get_expr_type(cg, bin->right);
    VylType res_type = (left_type == VYL_TYPE_DEC || right_type == VYL_TYPE_DEC)
                           ? VYL_TYPE_DEC
                           : VYL_TYPE_INT;

    gen_expr(cg, bin->left);
    if (res_type == VYL_TYPE_DEC) {
      if (left_type == VYL_TYPE_INT)
        fprintf(cg->out, "    cvtsi2sd xmm0, rax\n");
      fprintf(cg->out, "    sub rsp, 8\n    movsd [rsp], xmm0\n");
    } else {
      fprintf(cg->out, "    push rax\n");
    }

    gen_expr(cg, bin->right);
    if (res_type == VYL_TYPE_DEC) {
      if (right_type == VYL_TYPE_INT)
        fprintf(cg->out, "    cvtsi2sd xmm0, rax\n");
      fprintf(cg->out, "    movsd xmm1, xmm0\n");
      fprintf(cg->out, "    movsd xmm0, [rsp]\n");
      fprintf(cg->out, "    add rsp, 8\n");

      if (bin->op == TOKEN_PLUS)
        fprintf(cg->out, "    addsd xmm0, xmm1\n");
      else if (bin->op == TOKEN_MINUS)
        fprintf(cg->out, "    subsd xmm0, xmm1\n");
      else if (bin->op == TOKEN_STAR)
        fprintf(cg->out, "    mulsd xmm0, xmm1\n");
      else if (bin->op == TOKEN_SLASH)
        fprintf(cg->out, "    divsd xmm0, xmm1\n");
    } else {
      fprintf(cg->out, "    mov r11, rax\n");
      fprintf(cg->out, "    pop rax\n");
      if (bin->op == TOKEN_PLUS) {
        fprintf(cg->out, "    add rax, r11\n");
      } else if (bin->op == TOKEN_MINUS) {
        fprintf(cg->out, "    sub rax, r11\n");
      } else if (bin->op == TOKEN_STAR) {
        fprintf(cg->out, "    imul rax, r11\n");
      } else if (bin->op == TOKEN_MOD) {
        fprintf(cg->out, "    cqo\n");
        fprintf(cg->out, "    idiv r11\n");
        fprintf(cg->out, "    mov rax, rdx\n");
      } else if (bin->op == TOKEN_SLASH) {
        fprintf(cg->out, "    cqo\n");
        fprintf(cg->out, "    idiv r11\n");
      } else if (bin->op == TOKEN_EQ || bin->op == TOKEN_LT ||
                 bin->op == TOKEN_GT || bin->op == TOKEN_LE ||
                 bin->op == TOKEN_GE) {
        fprintf(cg->out, "    cmp rax, r11\n");
        if (bin->op == TOKEN_EQ)
          fprintf(cg->out, "    sete al\n");
        else if (bin->op == TOKEN_LT)
          fprintf(cg->out, "    setl al\n");
        else if (bin->op == TOKEN_GT)
          fprintf(cg->out, "    setg al\n");
        else if (bin->op == TOKEN_LE)
          fprintf(cg->out, "    setle al\n");
        else if (bin->op == TOKEN_GE)
          fprintf(cg->out, "    setge al\n");
        fprintf(cg->out, "    movzx rax, al\n");
      }
    }
  } else if (node->type == NODE_CALL) {
    CallNode *call = (CallNode *)node;
    ASTNode *arg = call->args;
    int count = 0;
    while (arg) {
      gen_expr(cg, arg);
      fprintf(cg->out, "    push rax\n");
      arg = arg->next;
      count++;
    }
    static const char *regs[] = {"rdi", "rsi", "rdx", "rcx", "r8", "r9"};
    for (int i = count - 1; i >= 0; i--) {
      if (i < 6)
        fprintf(cg->out, "    pop %s\n", regs[i]);
      else
        fprintf(cg->out, "    add rsp, 8\n");
    }
    // Handle builtin functions that return values
    // Note: Arguments are already in registers from the push/pop above
    if (strcmp(call->callee, "Clock") == 0) {
      fprintf(cg->out, "    call clock@plt\n");
      // Convert to seconds: rax / 1000000.0
      fprintf(cg->out, "    cvtsi2sd xmm0, rax\n");
      int id = get_decimal_id(1000000.0);
      fprintf(cg->out, "    divsd xmm0, [rip + dec_const_%d]\n", id);
    } else if (strcmp(call->callee, "Exists") == 0) {
      // Arg already in rdi
      fprintf(cg->out, "    xor esi, esi\n");
      fprintf(cg->out, "    call access@plt\n");
      fprintf(cg->out, "    test eax, eax\n");
      fprintf(cg->out, "    sete al\n");
      fprintf(cg->out, "    movzx rax, al\n");
    } else if (strcmp(call->callee, "Len") == 0) {
      // Arg already in rdi
      fprintf(cg->out, "    call strlen@plt\n");
    } else if (strcmp(call->callee, "Concat") == 0) {
      // Args already in rdi (str1) and rsi (str2)
      fprintf(cg->out, "    push rdi\n");                 // Save str1
      fprintf(cg->out, "    push rsi\n");                 // Save str2
      fprintf(cg->out, "    call strlen@plt\n");          // len(str1)
      fprintf(cg->out, "    mov r14, rax\n");             // r14 = len1
      fprintf(cg->out, "    pop rsi\n");                  // Restore str2
      fprintf(cg->out, "    pop r15\n");                  // str1 in r15
      fprintf(cg->out, "    push r15\n");                 // Save str1 again
      fprintf(cg->out, "    mov rdi, rsi\n");             // str2 in rdi
      fprintf(cg->out, "    mov r13, rsi\n");             // Save str2 in r13
      fprintf(cg->out, "    call strlen@plt\n");          // len(str2)
      fprintf(cg->out, "    lea rdi, [r14 + rax + 1]\n"); // len1 + len2 + 1
      fprintf(cg->out, "    call malloc@plt\n");
      fprintf(cg->out, "    mov rdi, rax\n"); // result in rdi
      fprintf(cg->out, "    pop rsi\n");      // str1 in rsi
      fprintf(cg->out, "    push rax\n");     // Save result
      fprintf(cg->out, "    call strcpy@plt\n");
      fprintf(cg->out, "    pop rax\n"); // result
      fprintf(cg->out, "    mov rdi, rax\n");
      fprintf(cg->out, "    mov rsi, r13\n"); // str2
      fprintf(cg->out, "    call strcat@plt\n");
    } else if (strcmp(call->callee, "Open") == 0) {
      // Args already in rdi (filename) and rsi (mode)
      fprintf(cg->out, "    call fopen@plt\n");
    } else if (strcmp(call->callee, "System") == 0 ||
               strcmp(call->callee, "Exec") == 0) {
      // Arg already in rdi
      fprintf(cg->out, "    sub rsp, 8\n");         // Stack alignment
      fprintf(cg->out, "    call system@plt\n");
      fprintf(cg->out, "    add rsp, 8\n");         // Clean up
    } else if (strcmp(call->callee, "CreateFolder") == 0) {
      // Arg already in rdi
      fprintf(cg->out, "    mov esi, 0755\n");
      fprintf(cg->out, "    call mkdir@plt\n");
    } else if (strcmp(call->callee, "Read") == 0) {
      // Read(file) -> string (reads entire file)
      // Arg already in rdi (FILE* handle)
      // We need to read the file content
      fprintf(cg->out, "    call vyl_read_file@plt\n");
    } else if (strcmp(call->callee, "ReadLine") == 0) {
      // ReadLine(file) -> string (reads one line)
      // Arg already in rdi (FILE* handle)
      fprintf(cg->out, "    call vyl_readline_file@plt\n");
    } else if (strcmp(call->callee, "ReadSize") == 0) {
      // ReadSize(file) -> int (file size in bytes)
      // Arg already in rdi (FILE* handle)
      fprintf(cg->out, "    call vyl_filesize@plt\n");
    } else if (strcmp(call->callee, "Sqrt") == 0) {
      // Sqrt(num) -> dec
      fprintf(cg->out, "    call sqrt@plt\n");
    } else if (strcmp(call->callee, "Sin") == 0) {
      // Sin(rad) -> dec
      fprintf(cg->out, "    call sin@plt\n");
    } else if (strcmp(call->callee, "Cos") == 0) {
      // Cos(rad) -> dec
      fprintf(cg->out, "    call cos@plt\n");
    } else if (strcmp(call->callee, "Tan") == 0) {
      // Tan(rad) -> dec
      fprintf(cg->out, "    call tan@plt\n");
    } else if (strcmp(call->callee, "Abs") == 0) {
      // Abs(num) -> num (same type)
      fprintf(cg->out, "    call fabs@plt\n");
    } else if (strcmp(call->callee, "Floor") == 0) {
      // Floor(dec) -> int
      fprintf(cg->out, "    call floor@plt\n");
    } else if (strcmp(call->callee, "Ceil") == 0) {
      // Ceil(dec) -> int
      fprintf(cg->out, "    call ceil@plt\n");
    } else if (strcmp(call->callee, "Power") == 0) {
      // Power(base, exp) -> dec
      // Args already in xmm0 (base) and xmm1 (exp)
      fprintf(cg->out, "    call pow@plt\n");
    } else if (strcmp(call->callee, "StringCompare") == 0) {
      // StringCompare(str1, str2) -> int (0 if equal, <0 if str1<str2, >0 if str1>str2)
      // Args already in rdi (str1) and rsi (str2)
      fprintf(cg->out, "    call strcmp@plt\n");
    } else if (strcmp(call->callee, "StringSplit") == 0) {
      // StringSplit(str, delim) -> array of strings
      // Args already in rdi (str) and rsi (delim)
      fprintf(cg->out, "    call vyl_stringsplit@plt\n");
    } else if (strcmp(call->callee, "ToInt") == 0) {
      // ToInt(str)
      fprintf(cg->out, "    call vyl_to_int@plt\n");
    } else if (strcmp(call->callee, "ToDecimal") == 0) {
      // ToDecimal(str)
      fprintf(cg->out, "    call vyl_to_decimal@plt\n");
      // result in xmm0? vyl_to_decimal returns double in xmm? It returns double in rax normally
      // We'll move returned double from rax to xmm0 via cvtsi2sd if needed; but vyl_to_decimal implemented returns double via C calling convention in xmm0.
    } else if (strcmp(call->callee, "ToString") == 0) {
      // ToString(value) -> string; we call appropriate runtime depending on types at compile time
      fprintf(cg->out, "    call vyl_to_string_int@plt\n");
    } else if (strcmp(call->callee, "Free") == 0) {
      fprintf(cg->out, "    mov rdi, rax\n");
      fprintf(cg->out, "    call vyl_free_ptr@plt\n");
    } else if (strcmp(call->callee, "ArrayLen") == 0) {
      // If argument is a simple local variable, emit immediate length
      ASTNode *a = call->args;
      if (a && a->type == NODE_VAR) {
        const char *nm = ((VarNode *)a)->name;
        int asz = get_local_array_size(cg, nm);
        fprintf(cg->out, "    mov rax, %d\n", asz);
      } else {
        // Fallback to runtime (unknown)
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    call vyl_array_len@plt\n");
      }
    } else {
      fprintf(cg->out, "    call %s\n", call->callee);
    }
  } else if (node->type == NODE_DECIMAL) {
    double val = ((DecimalNode *)node)->value;
    int id = get_decimal_id(val);
    fprintf(cg->out, "    movsd xmm0, [rip + dec_const_%d]\n", id);
  } else if (node->type == NODE_STRING) {
    int id = get_string_id(((StringNode *)node)->value);
    fprintf(cg->out, "    lea rax, [rip + str_%d]\n", id);
  } else if (node->type == NODE_VYL_NEWLINE) {
    int id = get_string_id("\n");
    fprintf(cg->out, "    lea rax, [rip + str_%d]\n", id);
  } else if (node->type == NODE_NEW) {
    NewNode *nn = (NewNode *)node;
    StructInfo *si = get_struct_info(cg, nn->type_name);
    if (!si) {
      codegen_error("Undefined struct '%s'", nn->type_name);
      fprintf(cg->out, "    # Error: Undefined struct %s\n", nn->type_name);
      return;
    }
    fprintf(cg->out, "    mov rdi, %d\n", si->field_count * 8);
    fprintf(cg->out, "    call malloc@plt\n");
  } else if (node->type == NODE_MEMBER_ACCESS) {
    MemberAccessNode *ma = (MemberAccessNode *)node;
    gen_expr(cg, ma->struct_expr); // Base in rax
    const char *struct_name = get_expr_custom_type_name(cg, ma->struct_expr);
    if (!struct_name) {
      codegen_error("Could not resolve struct type for member access");
      fprintf(cg->out,
              "    # Error: Could not resolve struct type for member access\n");
      return;
    }
    StructInfo *si = get_struct_info(cg, struct_name);
    if (!si) {
      codegen_error("Undefined struct '%s'", struct_name);
      fprintf(cg->out, "    # Error: Undefined struct %s\n", struct_name);
      return;
    }
    int offset = get_field_offset(si, ma->member_name);
    if (offset == -1) {
      fprintf(cg->out, "    # Error: Field %s not found in struct %s\n",
              ma->member_name, struct_name);
      return;
    }
    fprintf(cg->out, "    mov rax, [rax + %d]\n", offset);
  }
}

void gen_var_decl(CodeGen *cg, VarDeclNode *node) {
  int size = node->array_size > 0 ? node->array_size : 1;
  int allocation = 8 * size;

  gen_expr(cg, node->init);

  cg->stack_pointer += allocation;
  int offset = cg->stack_pointer - (8 * (size - 1));
  cg->locals[cg->local_count].name = strdup(node->name);
  cg->locals[cg->local_count].offset = offset;
  cg->locals[cg->local_count].array_size = size;
  cg->locals[cg->local_count].type = node->type;
  cg->locals[cg->local_count].custom_type_name =
      node->custom_type_name ? strdup(node->custom_type_name) : NULL;

  // Register Promotion: Assign registers to the first few locals if they are
  // INT or BOOL (scalars only)
  static const char *reg_pool[] = {"rbx", "r12", "r13", "r14", "r15"};
  if (size == 1 && cg->local_count < 5 &&
      (node->type == VYL_TYPE_INT || node->type == VYL_TYPE_BOOL)) {
    cg->locals[cg->local_count].reg = reg_pool[cg->local_count];
  } else {
    cg->locals[cg->local_count].reg = NULL;
  }

  cg->local_count++;

  const char *reg = cg->locals[cg->local_count - 1].reg;
  if (node->type == VYL_TYPE_DEC && size == 1) {
    fprintf(cg->out, "    sub rsp, 8\n");
    fprintf(cg->out, "    movsd [rbp - %d], xmm0\n", offset);
  } else if (reg) {
    fprintf(cg->out, "    mov %s, rax\n", reg);
  } else {
    fprintf(cg->out, "    sub rsp, %d\n", allocation);
    if (size == 1) {
      fprintf(cg->out, "    mov [rbp - %d], rax\n", offset);
    }
  }
}

void gen_if(CodeGen *cg, IfNode *node) {
  static int label_idx = 0;
  int cur_idx = label_idx++;
  if (node->else_block) {
    char else_label[32], end_label[32];
    sprintf(else_label, ".Lelse%d", cur_idx);
    sprintf(end_label, ".Lend%d", cur_idx);
    gen_cond_jmp(cg, node->condition, else_label, false);
    ASTNode *cur = node->then_block;
    while (cur) {
      gen_statement(cg, cur);
      cur = cur->next;
    }
    fprintf(cg->out, "    jmp %s\n", end_label);
    fprintf(cg->out, "%s:\n", else_label);
    ASTNode *e_cur = node->else_block;
    while (e_cur) {
      gen_statement(cg, e_cur);
      e_cur = e_cur->next;
    }
    fprintf(cg->out, "%s:\n", end_label);
  } else {
    char end_label[32];
    sprintf(end_label, ".Lend%d", cur_idx);
    gen_cond_jmp(cg, node->condition, end_label, false);
    ASTNode *cur = node->then_block;
    while (cur) {
      gen_statement(cg, cur);
      cur = cur->next;
    }
    fprintf(cg->out, "%s:\n", end_label);
  }
}

void gen_while(CodeGen *cg, WhileNode *node) {
  static int label_idx = 0;
  int cur_idx = label_idx++;
  char body_label[32], test_label[32], end_label[32];
  sprintf(body_label, ".Lwhile_body%d", cur_idx);
  sprintf(test_label, ".Lwhile_test%d", cur_idx);
  sprintf(end_label, ".Lwhile_end%d", cur_idx);

  // Save previous loop context
  const char *prev_start = cg->current_loop_start;
  const char *prev_end = cg->current_loop_end;

  // Set current loop context for break/continue
  cg->current_loop_start = test_label;
  cg->current_loop_end = end_label;

  fprintf(cg->out, "    jmp %s\n", test_label);
  fprintf(cg->out, "%s:\n", body_label);
  ASTNode *cur = node->body;
  while (cur) {
    gen_statement(cg, cur);
    cur = cur->next;
  }
  fprintf(cg->out, "%s:\n", test_label);
  gen_cond_jmp(cg, node->condition, body_label, true);
  fprintf(cg->out, "%s:\n", end_label);

  // Restore previous loop context
  cg->current_loop_start = prev_start;
  cg->current_loop_end = prev_end;
}

void gen_statement(CodeGen *cg, ASTNode *node) {
  if (!node)
    return;
  // fprintf(stderr, "DEBUG: gen_statement node type %d\n", node->type);
  if (node->type == NODE_CALL) {
    CallNode *call = (CallNode *)node;
    if (strcmp(call->callee, "Print") == 0) {
      ASTNode *arg = call->args;
      while (arg) {
        if (arg->type == NODE_VYL_NEWLINE) {
          int id = get_string_id("\n");
          fprintf(cg->out, "    lea rdi, [rip + str_%d]\n", id);
          fprintf(cg->out, "    xor eax, eax\n");
          fprintf(cg->out, "    call printf@plt\n");
        } else {
          VylType type = get_expr_type(cg, arg);
          gen_expr(cg, arg);
          if (type == VYL_TYPE_STRING) {
            int fmt_id = get_string_id("%s ");
            fprintf(cg->out, "    mov rsi, rax\n");
            fprintf(cg->out, "    lea rdi, [rip + str_%d]\n", fmt_id);
            fprintf(cg->out, "    xor eax, eax\n");
            fprintf(cg->out, "    call printf@plt\n");
          } else if (type == VYL_TYPE_BOOL) {
            int fmt_id = get_string_id("%s ");
            static int bool_label_idx = 0;
            int cur_bool = bool_label_idx++;
            int true_id = get_string_id("true");
            int false_id = get_string_id("false");

            fprintf(cg->out, "    cmp rax, 0\n");
            fprintf(cg->out, "    jne .Ltrue%d\n", cur_bool);
            fprintf(cg->out, "    lea rsi, [rip + str_%d]\n", false_id);
            fprintf(cg->out, "    jmp .Lprint_bool%d\n", cur_bool);
            fprintf(cg->out, ".Ltrue%d:\n", cur_bool);
            fprintf(cg->out, "    lea rsi, [rip + str_%d]\n", true_id);
            fprintf(cg->out, ".Lprint_bool%d:\n", cur_bool);
            fprintf(cg->out, "    lea rdi, [rip + str_%d]\n", fmt_id);
            fprintf(cg->out, "    xor eax, eax\n");
            fprintf(cg->out, "    call printf@plt\n");
          } else if (type == VYL_TYPE_DEC) {
            int fmt_id = get_string_id("%.6g ");
            fprintf(cg->out, "    sub rsp, 8\n");  // Maintain 16-byte stack alignment
            fprintf(cg->out, "    lea rdi, [rip + str_%d]\n", fmt_id);
            fprintf(cg->out, "    mov eax, 1\n");  // 1 XMM register in use
            fprintf(cg->out, "    call printf@plt\n");
            fprintf(cg->out, "    add rsp, 8\n");  // Clean up
          } else { // INT
            int fmt_id = get_string_id("%d ");
            fprintf(cg->out, "    mov rsi, rax\n");
            fprintf(cg->out, "    lea rdi, [rip + str_%d]\n", fmt_id);
            fprintf(cg->out, "    xor eax, eax\n");
            fprintf(cg->out, "    call printf@plt\n");
          }
        }
        arg = arg->next;
      }
      int nl_id = get_string_id("\n");
      fprintf(cg->out, "    lea rdi, [rip + str_%d]\n", nl_id);
      fprintf(cg->out, "    xor eax, eax\n");
      fprintf(cg->out, "    call printf@plt\n");
    } else if (strcmp(call->callee, "Clock") == 0) {
      fprintf(cg->out, "    call clock@plt\n");
      // rax now has clock_t (long)
    } else if (strcmp(call->callee, "Open") == 0) {
      // Open(filename, mode) -> file handle (as int)
      // Args: filename (string), mode (string)
      ASTNode *filename = call->args;
      ASTNode *mode = filename ? filename->next : NULL;
      if (filename && mode) {
        gen_expr(cg, mode); // mode in rax
        fprintf(cg->out, "    push rax\n");
        gen_expr(cg, filename);                 // filename in rax
        fprintf(cg->out, "    pop rsi\n");      // mode in rsi
        fprintf(cg->out, "    mov rdi, rax\n"); // filename in rdi
        fprintf(cg->out, "    call fopen@plt\n");
        // rax now has FILE* (or NULL)
      }
    } else if (strcmp(call->callee, "Close") == 0) {
      // Close(file)
      ASTNode *file = call->args;
      if (file) {
        gen_expr(cg, file);
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    call fclose@plt\n");
      }
    } else if (strcmp(call->callee, "Read") == 0) {
      // Read(file) -> string (reads entire file)
      ASTNode *file = call->args;
      if (file) {
        gen_expr(cg, file);
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    call vyl_read_file@plt\n");
      }
    } else if (strcmp(call->callee, "ReadLine") == 0) {
      // ReadLine(file) -> string
      ASTNode *file = call->args;
      if (file) {
        gen_expr(cg, file);
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    call vyl_readline_file@plt\n");
      }
    } else if (strcmp(call->callee, "ReadSize") == 0) {
      // ReadSize(file) -> int
      ASTNode *file = call->args;
      if (file) {
        gen_expr(cg, file);
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    call vyl_filesize@plt\n");
      }
    } else if (strcmp(call->callee, "Write") == 0) {
      // Write(file, data) -> bytes written
      ASTNode *file = call->args;
      ASTNode *data = file ? file->next : NULL;
      if (file && data) {
        gen_expr(cg, data); // data in rax
        fprintf(cg->out, "    push rax\n");
        gen_expr(cg, file);                // file in rax
        fprintf(cg->out, "    pop rdi\n"); // data (string) in rdi - 1st arg
        fprintf(cg->out, "    mov rsi, rax\n"); // file (FILE*) in rsi - 2nd arg
        fprintf(cg->out, "    call fputs@plt\n");
        // rax has result
      }
    } else if (strcmp(call->callee, "System") == 0 ||
               strcmp(call->callee, "Exec") == 0) {
      // System(command) -> exit code
      ASTNode *cmd = call->args;
      if (cmd) {
        gen_expr(cg, cmd);
        fprintf(cg->out, "    sub rsp, 8\n");        // Stack alignment for system()
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    call system@plt\n");
        fprintf(cg->out, "    add rsp, 8\n");        // Clean up stack
        // rax has exit code
      }
    } else if (strcmp(call->callee, "Exit") == 0) {
      // Exit(code)
      ASTNode *code = call->args;
      if (code) {
        gen_expr(cg, code);
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    call exit@plt\n");
      } else {
        fprintf(cg->out, "    xor edi, edi\n");
        fprintf(cg->out, "    call exit@plt\n");
      }
    } else if (strcmp(call->callee, "Exists") == 0) {
      // Exists(path) -> bool (1 if exists, 0 if not)
      // Uses access() syscall to check file/folder existence
      ASTNode *path = call->args;
      if (path) {
        gen_expr(cg, path);
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    xor esi, esi\n"); // F_OK = 0 (check existence)
        fprintf(cg->out, "    call access@plt\n");
        // access returns 0 on success, -1 on failure
        // Convert to bool: 0 -> 1, -1 -> 0
        fprintf(cg->out, "    test eax, eax\n");
        fprintf(cg->out, "    sete al\n"); // Set AL to 1 if ZF=1 (eax==0)
        fprintf(cg->out, "    movzx rax, al\n");
      }
    } else if (strcmp(call->callee, "CreateFolder") == 0) {
      // CreateFolder(path) -> int (0 on success, -1 on error)
      ASTNode *path = call->args;
      if (path) {
        gen_expr(cg, path);
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    mov esi, 0755\n"); // Default permissions
        fprintf(cg->out, "    call mkdir@plt\n");
      }
    } else if (strcmp(call->callee, "Len") == 0) {
      // Len(string) -> int (length of string)
      ASTNode *str = call->args;
      if (str) {
        gen_expr(cg, str);
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    call strlen@plt\n");
      }
    } else if (strcmp(call->callee, "Concat") == 0) {
      // Concat(str1, str2) -> string (concatenated)
      // Note: This allocates memory, caller should eventually free
      ASTNode *str1 = call->args;
      ASTNode *str2 = str1 ? str1->next : NULL;
      if (str1 && str2) {
        // Get lengths
        gen_expr(cg, str1);
        fprintf(cg->out, "    push rax\n"); // Save str1
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    call strlen@plt\n");
        fprintf(cg->out, "    push rax\n"); // Save len1

        gen_expr(cg, str2);
        fprintf(cg->out, "    push rax\n"); // Save str2
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    call strlen@plt\n");
        fprintf(cg->out, "    mov r12, rax\n"); // len2 in r12

        // Allocate memory: len1 + len2 + 1
        fprintf(cg->out, "    pop r13\n"); // str2 in r13
        fprintf(cg->out, "    pop r14\n"); // len1 in r14
        fprintf(cg->out, "    pop r15\n"); // str1 in r15
        fprintf(cg->out, "    lea rdi, [r14 + r12 + 1]\n");
        fprintf(cg->out, "    call malloc@plt\n");
        fprintf(cg->out, "    push rax\n"); // Save result

        // strcpy(result, str1)
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    mov rsi, r15\n");
        fprintf(cg->out, "    call strcpy@plt\n");

        // strcat(result, str2)
        fprintf(cg->out, "    pop rax\n"); // result
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    mov rsi, r13\n");
        fprintf(cg->out, "    call strcat@plt\n");
      }
    } else if (strcmp(call->callee, "Substring") == 0) {
      // Substring(str, start, length) -> string
      ASTNode *str = call->args;
      ASTNode *start = str ? str->next : NULL;
      ASTNode *length = start ? start->next : NULL;
      if (str && start && length) {
        gen_expr(cg, length);
        fprintf(cg->out, "    push rax\n"); // Save length
        gen_expr(cg, start);
        fprintf(cg->out, "    push rax\n"); // Save start
        gen_expr(cg, str);
        fprintf(cg->out, "    pop r12\n"); // start in r12
        fprintf(cg->out, "    pop r13\n"); // length in r13

        // Allocate memory: length + 1
        fprintf(cg->out, "    lea rdi, [r13 + 1]\n");
        fprintf(cg->out, "    call malloc@plt\n");
        fprintf(cg->out, "    push rax\n"); // Save result

        // strncpy(result, str + start, length)
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    lea rsi, [rax + r12]\n"); // str + start
        fprintf(cg->out, "    mov rdx, r13\n");         // length
        fprintf(cg->out, "    call strncpy@plt\n");

        // Null terminate
        fprintf(cg->out, "    pop rax\n"); // result
        fprintf(cg->out, "    mov byte ptr [rax + r13], 0\n");
      }
    } else if (strcmp(call->callee, "System") == 0 ||
               strcmp(call->callee, "Exec") == 0) {
      // System/Exec(command) -> exit code
      ASTNode *cmd = call->args;
      if (cmd) {
        gen_expr(cg, cmd);
        fprintf(cg->out, "    mov rdi, rax\n");
        fprintf(cg->out, "    call system@plt\n");
        // rax has exit code
      }
    } else {
      gen_expr(cg, node);
    }
  } else if (node->type == NODE_RETURN) {
    ReturnNode *ret = (ReturnNode *)node;
    if (ret->expr)
      gen_expr(cg, ret->expr);
    fprintf(cg->out, "    leave\n    ret\n");
  } else if (node->type == NODE_IF) {
    gen_if(cg, (IfNode *)node);
  } else if (node->type == NODE_WHILE) {
    gen_while(cg, (WhileNode *)node);
  } else if (node->type == NODE_FOR) {
    // For loop: for i in start..end { body }
    ForNode *fnode = (ForNode *)node;
    static int for_label_idx = 0;
    int cur_idx = for_label_idx++;

    // Generate labels
    char start_label[32], test_label[32], end_label[32];
    sprintf(start_label, ".Lfor_start%d", cur_idx);
    sprintf(test_label, ".Lfor_test%d", cur_idx);
    sprintf(end_label, ".Lfor_end%d", cur_idx);

    // Initialize iterator variable
    gen_expr(cg, fnode->start);
    cg->stack_pointer += 8;
    int iter_offset = cg->stack_pointer;
    cg->locals[cg->local_count].name = strdup(fnode->iterator_name);
    cg->locals[cg->local_count].offset = iter_offset;
    cg->locals[cg->local_count].type = VYL_TYPE_INT;
    cg->locals[cg->local_count].reg = NULL;
    cg->locals[cg->local_count].custom_type_name = NULL;
    cg->local_count++;
    fprintf(cg->out, "    sub rsp, 8\n");
    fprintf(cg->out, "    mov [rbp - %d], rax\n", iter_offset);

    // Jump to test first (condition-at-tail optimization)
    fprintf(cg->out, "    jmp %s\n", test_label);

    // Loop body
    fprintf(cg->out, "%s:\n", start_label);
    ASTNode *cur = fnode->body;
    while (cur) {
      gen_statement(cg, cur);
      cur = cur->next;
    }

    // Increment iterator
    fprintf(cg->out, "    mov rax, [rbp - %d]\n", iter_offset);
    fprintf(cg->out, "    add rax, 1\n");
    fprintf(cg->out, "    mov [rbp - %d], rax\n", iter_offset);

    // Test condition: iterator <= end
    fprintf(cg->out, "%s:\n", test_label);
    fprintf(cg->out, "    mov rax, [rbp - %d]\n", iter_offset);
    fprintf(cg->out, "    push rax\n");
    gen_expr(cg, fnode->end);
    fprintf(cg->out, "    pop r11\n");
    fprintf(cg->out, "    cmp r11, rax\n");
    fprintf(cg->out, "    jle %s\n", start_label);

    // End label
    fprintf(cg->out, "%s:\n", end_label);
  } else if (node->type == NODE_VAR_DECL) {
    gen_var_decl(cg, (VarDeclNode *)node);
  } else if (node->type == NODE_STRUCT_DEF) {
    StructDefNode *snode = (StructDefNode *)node;
    if (cg->struct_count < 32) {
      StructInfo *si = &cg->structs[cg->struct_count++];
      si->name = strdup(snode->name);
      si->field_count = snode->field_count;
      si->field_names = malloc(sizeof(char *) * snode->field_count);
      for (int i = 0; i < snode->field_count; i++) {
        si->field_names[i] = strdup(snode->fields[i].name);
      }
    }
  } else if (node->type == NODE_ASSIGN) {
    AssignmentNode *assign = (AssignmentNode *)node;
    if (assign->target->type == NODE_VAR) {
      const char *name = ((VarNode *)assign->target)->name;
      int offset = get_local_offset(cg, name);
      const char *reg = get_local_reg(cg, name);

      // Peephole: name = name + literal
      if ((offset != 0 || reg != NULL) &&
          assign->expr->type == NODE_BINARY_OP) {
        BinaryNode *bin = (BinaryNode *)assign->expr;
        if (bin->op == TOKEN_PLUS || bin->op == TOKEN_MINUS) {
          ASTNode *left = bin->left;
          ASTNode *right = bin->right;
          if (left->type == NODE_VAR &&
              strcmp(((VarNode *)left)->name, name) == 0 &&
              right->type == NODE_NUMBER) {
            int val = ((NumberNode *)right)->value;
            const char *op_str = (bin->op == TOKEN_PLUS) ? "add" : "sub";

            if (reg) {
              fprintf(cg->out, "    %s %s, %d\n", op_str, reg, val);
            } else {
              if (val == 1) {
                fprintf(cg->out, "    %s qword ptr [rbp - %d], 1\n", op_str,
                        offset);
              } else {
                fprintf(cg->out, "    %s qword ptr [rbp - %d], %d\n", op_str,
                        offset, val);
              }
            }
            return;
          }
        }
      }

      gen_expr(cg, assign->expr);
      if (offset == 0 && reg == NULL) {
        // Inline declaration (implicit)
        cg->stack_pointer += 8;
        offset = cg->stack_pointer;
        cg->locals[cg->local_count].name = strdup(name);
        cg->locals[cg->local_count].offset = offset;
        cg->locals[cg->local_count].type = get_expr_type(cg, assign->expr);
        cg->locals[cg->local_count].array_size = 1;

        // Register Promotion for inline assignments too
        static const char *reg_pool[] = {"rbx", "r12", "r13", "r14", "r15"};
        if (cg->local_count < 5 &&
            (cg->locals[cg->local_count].type == VYL_TYPE_INT ||
             cg->locals[cg->local_count].type == VYL_TYPE_BOOL)) {
          cg->locals[cg->local_count].reg = reg_pool[cg->local_count];
          reg = cg->locals[cg->local_count].reg;
        } else {
          cg->locals[cg->local_count].reg = NULL;
        }
        cg->local_count++;
        if (!reg)
          fprintf(cg->out, "    sub rsp, 8\n");
      }

      VylType var_type = get_local_type(cg, name);
      if (reg) {
        // reg is only used for integer/bool scalars
        fprintf(cg->out, "    mov %s, rax\n", reg);
      } else {
        if (var_type == VYL_TYPE_DEC) {
          fprintf(cg->out, "    movsd [rbp - %d], xmm0\n", offset);
        } else {
          fprintf(cg->out, "    mov [rbp - %d], rax\n", offset);
        }
      }
    } else if (assign->target->type == NODE_INDEX) {
      IndexNode *in = (IndexNode *)assign->target;
      gen_expr(cg, in->index);
      fprintf(cg->out, "    push rax\n");
      gen_expr(cg, assign->expr);
      fprintf(cg->out, "    pop r10\n"); // r10 = index
      if (in->base_expr->type == NODE_VAR) {
        const char *name = ((VarNode *)in->base_expr)->name;
        int offset = get_local_offset(cg, name);
        int arr_size = get_local_array_size(cg, name);
        int msg_id = get_string_id("Index out of bounds\n");
        static int bound_idx2 = 0;
        int cur2 = bound_idx2++;
        // bounds check for write: r10 >= 0 && r10 < arr_size
        fprintf(cg->out, "    mov r11, r10\n");
        fprintf(cg->out, "    cmp r11, 0\n");
        fprintf(cg->out, "    jl .Lbound_write_fail%d\n", cur2);
        fprintf(cg->out, "    mov r12, %d\n", arr_size);
        fprintf(cg->out, "    cmp r11, r12\n");
        fprintf(cg->out, "    jae .Lbound_write_fail%d\n", cur2);
        fprintf(cg->out, "    jmp .Lbound_write_ok%d\n", cur2);
        fprintf(cg->out, ".Lbound_write_fail%d:\n", cur2);
        fprintf(cg->out, "    lea rdi, [rip + str_%d]\n", msg_id);
        fprintf(cg->out, "    call vyl_panic@plt\n");
        fprintf(cg->out, ".Lbound_write_ok%d:\n", cur2);

        fprintf(cg->out, "    lea rcx, [rbp - %d]\n", offset);
        fprintf(cg->out, "    shl r10, 3\n");
        fprintf(cg->out, "    sub rcx, r10\n");

        VylType elem_type = get_local_type(cg, name);
        if (elem_type == VYL_TYPE_DEC) {
          fprintf(cg->out, "    movsd [rcx], xmm0\n");
        } else {
          fprintf(cg->out, "    mov [rcx], rax\n");
        }
      }
    } else if (assign->target->type == NODE_MEMBER_ACCESS) {
      MemberAccessNode *ma = (MemberAccessNode *)assign->target;
      gen_expr(cg, ma->struct_expr);
      fprintf(cg->out, "    push rax\n");
      gen_expr(cg, assign->expr);
      fprintf(cg->out, "    pop r11\n");
      const char *struct_name = get_expr_custom_type_name(cg, ma->struct_expr);
      if (struct_name) {
        StructInfo *si = get_struct_info(cg, struct_name);
        if (si) {
          int foffset = get_field_offset(si, ma->member_name);
          if (foffset != -1) {
            VylType field_type = get_expr_type(cg, assign->expr);
            if (field_type == VYL_TYPE_DEC)
              fprintf(cg->out, "    movsd [r11 + %d], xmm0\n", foffset);
            else
              fprintf(cg->out, "    mov [r11 + %d], rax\n", foffset);
          }
        }
      }
    }
    if (cg->current_loop_start) {
      fprintf(cg->out, "    jmp %s\n", cg->current_loop_start);
    } else {
      fprintf(stderr, "Error: continue statement outside of loop\n");
    }
  }
}

void gen_function(CodeGen *cg, FunctionDefNode *node) {
  codegen_cleanup(cg);
  cg->stack_pointer = 0;
  fprintf(cg->out, ".global %s\n%s:\n    push rbp\n    mov rbp, rsp\n",
          node->name, node->name);
  // Push callee-saved registers that might be used
  fprintf(cg->out,
          "    push rbx\n    push r12\n    push r13\n    push r14\n    "
          "push r15\n");

  const char *param_regs[] = {"rdi", "rsi", "rdx", "rcx", "r8", "r9"};
  for (int i = 0; i < node->param_count && i < 6; i++) {
    cg->stack_pointer += 8;
    int offset = cg->stack_pointer;
    cg->locals[cg->local_count].name = strdup(node->params[i]);
    cg->locals[cg->local_count].offset = offset;
    cg->locals[cg->local_count].reg = NULL; // Parameters on stack for now
    cg->locals[cg->local_count].type = VYL_TYPE_INT; // Default
    cg->local_count++;
    fprintf(cg->out, "    sub rsp, 8\n    mov [rbp - %d], %s\n", offset,
            param_regs[i]);
  }
  ASTNode *cur = node->body;
  while (cur) {
    gen_statement(cg, cur);
    cur = cur->next;
  }
  // Pop callee-saved registers
  fprintf(cg->out,
          "    pop r15\n    pop r14\n    pop r13\n    pop r12\n    pop rbx\n");
  fprintf(cg->out, "    leave\n    ret\n\n");
}

void gen_main(CodeGen *cg, ASTNode *nodes) {
  codegen_cleanup(cg);
  cg->stack_pointer = 0;
  fprintf(cg->out, ".global main\nmain:\n    push rbp\n    mov rbp, rsp\n");
  // Push callee-saved registers that might be used
  fprintf(cg->out,
          "    push rbx\n    push r12\n    push r13\n    push r14\n    "
          "push r15\n");

  ASTNode *cur = nodes;
  while (cur) {
    if (cur->type != NODE_FUNCTION_DEF && cur->type != NODE_IMPORT)
      gen_statement(cg, cur);
    cur = cur->next;
  }

  // Pop callee-saved registers
  fprintf(cg->out,
          "    pop r15\n    pop r14\n    pop r13\n    pop r12\n    pop rbx\n");
  fprintf(cg->out, "    mov rax, 0\n    leave\n    ret\n");
}

void codegen_generate(CodeGen *cg, ASTNode *root) {
  ProgramNode *prog = (ProgramNode *)root;
  char *text_buffer = NULL;
  size_t text_size = 0;
  FILE *real_out = cg->out;
  FILE *text_stream = open_memstream(&text_buffer, &text_size);
  cg->out = text_stream;
  fprintf(cg->out, ".section .text\n");
  ASTNode *cur = prog->nodes;
  while (cur) {
    if (cur->type == NODE_FUNCTION_DEF)
      gen_function(cg, (FunctionDefNode *)cur);
    cur = cur->next;
  }
  gen_main(cg, prog->nodes);
  fclose(text_stream);
  cg->out = real_out;
  fprintf(cg->out, ".intel_syntax noprefix\n.extern printf\n.extern "
                   "clock\n.extern system\n.extern sqrt\n.extern sin\n.extern cos\n.extern tan\n"
                   ".extern fabs\n.extern floor\n.extern ceil\n.extern pow\n"
                   ".extern strcmp\n.extern fopen\n.extern fclose\n"
                   ".extern vyl_read_file\n.extern vyl_readline_file\n"
                   ".extern vyl_filesize\n.extern vyl_stringsplit\n"
                   ".extern vyl_to_int\n.extern vyl_to_decimal\n.extern vyl_to_string_int\n.extern vyl_free_ptr\n.extern vyl_array_len\n"
                   ".extern log\n.extern exp\n.extern fmin\n.extern fmax\n.extern round\n"
                   ".section .rodata\n");
  StringConst *s = strings_head;
  while (s) {
    fprintf(cg->out, "str_%d: .asciz \"", s->id);
    for (char *p = s->value; *p; p++) {
      if (*p == '\n')
        fprintf(cg->out, "\\n");
      else if (*p == '\"')
        fprintf(cg->out, "\\\"");
      else if (*p == '\\')
        fprintf(cg->out, "\\\\");
      else
        fputc(*p, cg->out);
    }
    fprintf(cg->out, "\"\n");
    s = s->next;
  }

  DecimalConst *d = decimals_head;
  while (d) {
    fprintf(cg->out, ".align 8\n");
    fprintf(cg->out, "dec_const_%d: .double %f\n", d->id, d->value);
    d = d->next;
  }

  fprintf(cg->out, "\n%s", text_buffer);
  free(text_buffer);
}

void codegen_free() {
  StringConst *s = strings_head;
  while (s) {
    StringConst *next = s->next;
    if (s->value)
      free(s->value);
    free(s);
    s = next;
  }

  DecimalConst *d = decimals_head;
  while (d) {
    DecimalConst *next = d->next;
    free(d);
    d = next;
  }

  // Also free locals names in active CodeGen if persistent?
  // Locals are re-init per function, but strings/decimals are global for the
  // module. Ideally CodeGen struct should manage this better, but for this
  // single-pass:
  strings_head = NULL;
  decimals_head = NULL;
}

void codegen_cleanup(CodeGen *cg) {
  for (int i = 0; i < cg->local_count; i++) {
    if (cg->locals[i].name) {
      free(cg->locals[i].name);
      cg->locals[i].name = NULL;
    }
    if (cg->locals[i].custom_type_name) {
      free(cg->locals[i].custom_type_name);
      cg->locals[i].custom_type_name = NULL;
    }
  }
  cg->local_count = 0;

  for (int i = 0; i < cg->struct_count; i++) {
    if (cg->structs[i].name)
      free(cg->structs[i].name);
    for (int j = 0; j < cg->structs[i].field_count; j++) {
      if (cg->structs[i].field_names[j])
        free(cg->structs[i].field_names[j]);
    }
    if (cg->structs[i].field_names)
      free(cg->structs[i].field_names);
  }
  cg->struct_count = 0;
}
