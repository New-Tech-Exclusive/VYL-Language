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
char* vyl_string_concat(const char *a, const char *b);

// Runtime panic and error helpers
void vyl_panic(const char *msg);
void vyl_error(const char *msg, int code);

// Conversions
int vyl_to_int(const char *s);
char *vyl_to_string_int(long v);
char *vyl_to_string_dec(double v);
double vyl_to_decimal(const char *s);

// Free
void vyl_free_ptr(void *p);

// Fallback array len (may return -1 if unknown)
long vyl_array_len(void *arr);

// Dynamic List (Array) API
void* vyl_list_new(void);
void vyl_list_append(void *list, void *item);
long vyl_list_len(void *list);
void* vyl_list_get(void *list, long index);
void vyl_list_set(void *list, long index, void *item);
void vyl_list_free(void *list);

// Hash Map (Dictionary) API
// Type tags for values stored in dictionaries
typedef enum {
  VYL_VALUE_INT = 0,
  VYL_VALUE_STRING = 1,
  VYL_VALUE_DEC = 2,
  VYL_VALUE_BOOL = 3,
  VYL_VALUE_PTR = 4
} VylValueType;

void* vyl_dict_new(void);
void vyl_dict_set(void *dict, const char *key, void *value);
void vyl_dict_set_string(void *dict, const char *key, const char *value);
void vyl_dict_set_int(void *dict, const char *key, long value);
void vyl_dict_set_typed(void *dict, const char *key, void *value, VylValueType type);
void* vyl_dict_get(void *dict, const char *key);
VylValueType vyl_dict_get_type(void *dict, const char *key);
void vyl_dict_free(void *dict);

#endif

