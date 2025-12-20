#define _POSIX_C_SOURCE 200809L
#include "codegen.h"
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

// Forward declarations
void gen_statement(CodeGen *cg, ASTNode *node);
void gen_expr(CodeGen *cg, ASTNode *node);
void gen_if(CodeGen *cg, IfNode *node);

void codegen_init(CodeGen *cg, FILE *out) {
  cg->out = out;
  cg->string_count = 0;
  cg->local_count = 0;
  cg->stack_pointer = 0;
  cg->struct_count = 0;
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
  if (node->type == NODE_BINARY_OP) {
    // Simple heuristic: if either side is dec, result is dec
    BinaryNode *bin = (BinaryNode *)node;
    if (get_expr_type(cg, bin->left) == VYL_TYPE_DEC ||
        get_expr_type(cg, bin->right) == VYL_TYPE_DEC)
      return VYL_TYPE_DEC;
    return VYL_TYPE_INT;
  }
  return VYL_TYPE_INT;
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
  if (cond->type == NODE_BINARY_OP) {
    BinaryNode *bin = (BinaryNode *)cond;
    if (bin->op == TOKEN_LT || bin->op == TOKEN_GT || bin->op == TOKEN_EQ) {
      const char *l_reg = (bin->left->type == NODE_VAR)
                              ? get_local_reg(cg, ((VarNode *)bin->left)->name)
                              : NULL;
      const char *r_reg = (bin->right->type == NODE_VAR)
                              ? get_local_reg(cg, ((VarNode *)bin->right)->name)
                              : NULL;
      const char *l = "rax";
      const char *r = "r11";

      if (l_reg && r_reg) {
        l = l_reg;
        r = r_reg;
        fprintf(cg->out, "    cmp %s, %s\n", l, r);
      } else if (l_reg && bin->right->type == NODE_NUMBER) {
        fprintf(cg->out, "    cmp %s, %d\n", l_reg,
                ((NumberNode *)bin->right)->value);
      } else if (l_reg) {
        l = l_reg;
        gen_expr(cg, bin->right);
        r = "rax";
        fprintf(cg->out, "    cmp %s, %s\n", l, r);
      } else if (r_reg) {
        r = r_reg;
        gen_expr(cg, bin->left);
        l = "rax";
        fprintf(cg->out, "    cmp %s, %s\n", l, r);
      } else {
        gen_expr(cg, bin->left);
        fprintf(cg->out, "    push rax\n");
        gen_expr(cg, bin->right);
        fprintf(cg->out, "    mov r11, rax\n    pop rax\n");
        fprintf(cg->out, "    cmp %s, %s\n", l, r);
      }
      const char *jmp = "";
      if (bin->op == TOKEN_LT)
        jmp = jump_if_true ? "jl" : "jge";
      else if (bin->op == TOKEN_GT)
        jmp = jump_if_true ? "jg" : "jle";
      else if (bin->op == TOKEN_EQ)
        jmp = jump_if_true ? "je" : "jne";
      fprintf(cg->out, "    %s %s\n", jmp, label);
      return;
    }
  }
  // Fallback for non-binary-comparison conditions
  gen_expr(cg, cond);
  fprintf(cg->out, "    cmp rax, 0\n");
  if (jump_if_true)
    fprintf(cg->out, "    jne %s\n", label);
  else
    fprintf(cg->out, "    je %s\n", label);
}

void gen_expr(CodeGen *cg, ASTNode *node) {
  if (!node)
    return;
  if (node->type == NODE_NUMBER) {
    fprintf(cg->out, "    mov rax, %d\n", ((NumberNode *)node)->value);
  } else if (node->type == NODE_VAR) {
    VarNode *var = (VarNode *)node;
    VylType type = get_local_type(cg, var->name);
    const char *reg = get_local_reg(cg, var->name);
    int offset = get_local_offset(cg, var->name);

    if (offset == 0 && reg == NULL) {
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
  } else if (node->type == NODE_INDEX) {
    IndexNode *in = (IndexNode *)node;
    gen_expr(cg, in->index); // Result in rax
    if (in->base_expr->type == NODE_VAR) {
      const char *name = ((VarNode *)in->base_expr)->name;
      int offset = get_local_offset(cg, name);
      // address = rbp - (offset + rax*8)
      fprintf(cg->out, "    lea rcx, [rbp - %d]\n", offset);
      fprintf(cg->out, "    shl rax, 3\n");
      // Actually, stack grows down. arr[0] is at rbp-offset.
      // arr[1] is at rbp-(offset+8).
      // So rcx = rbp - offset - rax*8
      fprintf(cg->out, "    sub rcx, rax\n");
      fprintf(cg->out, "    mov rax, [rcx]\n");
    }
  } else if (node->type == NODE_BINARY_OP) {
    BinaryNode *bin = (BinaryNode *)node;
    VylType left_type = get_expr_type(cg, bin->left);
    VylType right_type = get_expr_type(cg, bin->right);
    VylType res_type = (left_type == VYL_TYPE_DEC || right_type == VYL_TYPE_DEC)
                           ? VYL_TYPE_DEC
                           : VYL_TYPE_INT;

    // Fast path for integer literal optimized ops
    if (res_type == VYL_TYPE_INT && bin->right->type == NODE_NUMBER) {
      gen_expr(cg, bin->left);
      int val = ((NumberNode *)bin->right)->value;
      if (bin->op == TOKEN_PLUS)
        fprintf(cg->out, "    add rax, %d\n", val);
      else if (bin->op == TOKEN_MINUS)
        fprintf(cg->out, "    sub rax, %d\n", val);
      else if (bin->op == TOKEN_STAR)
        fprintf(cg->out, "    imul rax, rax, %d\n", val);
      else if (bin->op == TOKEN_EQ || bin->op == TOKEN_LT ||
               bin->op == TOKEN_GT) {
        fprintf(cg->out, "    cmp rax, %d\n", val);
        if (bin->op == TOKEN_EQ)
          fprintf(cg->out, "    sete al\n");
        else if (bin->op == TOKEN_LT)
          fprintf(cg->out, "    setl al\n");
        else if (bin->op == TOKEN_GT)
          fprintf(cg->out, "    setg al\n");
        fprintf(cg->out, "    movzx rax, al\n");
      } else {
        // Fallback for division or other ops not easily optimized with
        // immediate
        fprintf(cg->out, "    push rax\n");
        gen_expr(cg, bin->right);
        fprintf(cg->out, "    mov r11, rax\n");
        fprintf(cg->out, "    pop rax\n");
        fprintf(cg->out, "    cqo\n    idiv r11\n");
      }
      return;
    }

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
      } else if (bin->op == TOKEN_SLASH) {
        fprintf(cg->out, "    cqo\n");
        fprintf(cg->out, "    idiv r11\n");
      } else if (bin->op == TOKEN_EQ || bin->op == TOKEN_LT ||
                 bin->op == TOKEN_GT) {
        fprintf(cg->out, "    cmp rax, r11\n");
        if (bin->op == TOKEN_EQ)
          fprintf(cg->out, "    sete al\n");
        else if (bin->op == TOKEN_LT)
          fprintf(cg->out, "    setl al\n");
        else if (bin->op == TOKEN_GT)
          fprintf(cg->out, "    setg al\n");
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
    if (strcmp(call->callee, "Clock") == 0) {
      fprintf(cg->out, "    call clock@plt\n");
      // Convert to seconds: rax / 1000000.0
      fprintf(cg->out, "    cvtsi2sd xmm0, rax\n");
      int id = get_decimal_id(1000000.0);
      fprintf(cg->out, "    divsd xmm0, [rip + dec_const_%d]\n", id);
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
      fprintf(cg->out,
              "    # Error: Could not resolve struct type for member access\n");
      return;
    }
    StructInfo *si = get_struct_info(cg, struct_name);
    if (!si) {
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
  char body_label[32], test_label[32];
  sprintf(body_label, ".Lwhile_body%d", cur_idx);
  sprintf(test_label, ".Lwhile_test%d", cur_idx);

  fprintf(cg->out, "    jmp %s\n", test_label);
  fprintf(cg->out, "%s:\n", body_label);
  ASTNode *cur = node->body;
  while (cur) {
    gen_statement(cg, cur);
    cur = cur->next;
  }
  fprintf(cg->out, "%s:\n", test_label);
  gen_cond_jmp(cg, node->condition, body_label, true);
  fprintf(cg->out, ".Lwhile_end%d:\n",
          cur_idx); // Keep label for potential break in future
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
            int fmt_id = get_string_id("%f ");
            fprintf(cg->out, "    lea rdi, [rip + str_%d]\n", fmt_id);
            fprintf(cg->out, "    mov eax, 1\n");
            fprintf(cg->out, "    call printf@plt\n");
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

      if (reg) {
        fprintf(cg->out, "    mov %s, rax\n", reg);
      } else {
        fprintf(cg->out, "    mov [rbp - %d], rax\n", offset);
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
        fprintf(cg->out, "    lea rcx, [rbp - %d]\n", offset);
        fprintf(cg->out, "    shl r10, 3\n");
        fprintf(cg->out, "    sub rcx, r10\n");
        fprintf(cg->out, "    mov [rcx], rax\n");
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
          int offset = get_field_offset(si, ma->member_name);
          if (offset != -1) {
            fprintf(cg->out, "    mov [r11 + %d], rax\n", offset);
          }
        }
      }
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
                   "clock\n.section .data\n");
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
