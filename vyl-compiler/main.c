#define _POSIX_C_SOURCE 200809L
#include "codegen.h"
#include "lexer.h"
#include "parser.h"
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char *read_file(const char *path) {
  FILE *f = fopen(path, "r");
  if (!f)
    return NULL;
  fseek(f, 0, SEEK_END);
  long length = ftell(f);
  fseek(f, 0, SEEK_SET);
  char *buf = malloc(length + 1);
  fread(buf, 1, length, f);
  buf[length] = '\0';
  fclose(f);
  return buf;
}

int main(int argc, char **argv) {
  if (argc < 2) {
    printf("VYL Language Driver v0.1.5\n");
    printf("Usage: %s [flags] <source.vyl>\n", argv[0]);
    printf("Flags:\n");
    printf("  -c, --compile    Compile only (do not run)\n");
    return 1;
  }

  bool compile_only = false;
  const char *source_path = NULL;

  for (int i = 1; i < argc; i++) {
    if (strcmp(argv[i], "-c") == 0 || strcmp(argv[i], "--compile") == 0) {
      compile_only = true;
    } else {
      source_path = argv[i];
    }
  }

  if (!source_path) {
    fprintf(stderr, "Error: No source file specified.\n");
    return 1;
  }

  char *source = read_file(source_path);
  if (!source) {
    fprintf(stderr, "Error: Could not read file %s\n", source_path);
    return 1;
  }

  Lexer lexer;
  lexer_init(&lexer, source);
  int count;
  Token *tokens = lexer_tokenize(&lexer, &count);

  // Determine base name
  char base_name[256];
  const char *last_slash = strrchr(source_path, '/');
  const char *filename = last_slash ? last_slash + 1 : source_path;
  char *dot = strrchr(filename, '.');
  int len = dot ? (int)(dot - filename) : (int)strlen(filename);
  if (len > 250)
    len = 250;
  strncpy(base_name, filename, len);
  base_name[len] = '\0';

  Parser parser;
  parser_init(&parser, tokens, count);
  ASTNode *ast = parser_parse(&parser);

  char asm_path[256];
  snprintf(asm_path, 255, "%s.s", base_name);

  FILE *out = fopen(asm_path, "w");
  if (!out) {
    fprintf(stderr, "Error: Could not create output file %s\n", asm_path);
    free_ast(ast);
    free_tokens(tokens, count);
    free(source);
    return 1;
  }

  CodeGen cg;
  codegen_init(&cg, out);
  codegen_generate(&cg, ast);
  fclose(out);

  // Build
  char cmd[1024];
  char exe_path[256];
  snprintf(exe_path, 255, "%s.vylo", base_name);
  snprintf(cmd, 1024, "gcc %s /media/bentley/2TB/repos/vyl-lang/vyl-compiler/vyl_builtins_release.o -o %s -lm", asm_path, exe_path);

  if (system(cmd) != 0) {
    fprintf(stderr, "Error: Build failed (gcc error).\n");
    remove(asm_path);
    codegen_cleanup(&cg);
    codegen_free();
    free_ast(ast);
    free_tokens(tokens, count);
    free(source);
    return 1;
  }

  if (compile_only) {
    printf("Compiled: %s -> %s\n", source_path, exe_path);
  } else {
    // Run the resulting binary
    char run_cmd[512];
    snprintf(run_cmd, 512, "./%s", exe_path);
    system(run_cmd);
  }

  // Cleanup intermediate .s file
  remove(asm_path);

  codegen_cleanup(&cg);
  codegen_free();
  free_ast(ast);
  free_tokens(tokens, count);
  free(source);

  return 0;
}
