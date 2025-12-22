#ifndef VYL_BUILTINS_H
#define VYL_BUILTINS_H

#include <stdio.h>

// File I/O builtins
char* vyl_read_file(FILE *f);
char* vyl_readline_file(FILE *f);
long vyl_filesize(FILE *f);

// String operations
char** vyl_stringsplit(const char *str, const char *delim);
void vyl_free_string_array(char **arr);

// Runtime panic helper
void vyl_panic(const char *msg);

#endif
