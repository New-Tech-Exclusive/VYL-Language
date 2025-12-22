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

// Conversions
int vyl_to_int(const char *s);
char *vyl_to_string_int(long v);
char *vyl_to_string_dec(double v);
double vyl_to_decimal(const char *s);

// Free
void vyl_free_ptr(void *p);

// Fallback array len (may return -1 if unknown)
long vyl_array_len(void *arr);

#endif
