#define _POSIX_C_SOURCE 200809L
#include "vyl_builtins.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#include <errno.h>

// Read entire file contents into a string
char* vyl_read_file(FILE *f) {
  if (!f) return NULL;
  
  // Save current position
  long pos = ftell(f);
  
  // Seek to end to get size
  fseek(f, 0, SEEK_END);
  long size = ftell(f);
  fseek(f, pos, SEEK_SET);
  
  // Allocate buffer
  char *buf = (char *)malloc(size + 1);
  if (!buf) return NULL;
  
  // Read content
  size_t read = fread(buf, 1, size, f);
  buf[read] = '\0';
  
  return buf;
}

// Read one line from file
char* vyl_readline_file(FILE *f) {
  if (!f) return NULL;
  
  size_t capacity = 128;
  size_t length = 0;
  char *line = (char *)malloc(capacity);
  if (!line) return NULL;
  
  int c;
  while ((c = fgetc(f)) != EOF && c != '\n') {
    if (length >= capacity - 1) {
      capacity *= 2;
      char *new_line = (char *)realloc(line, capacity);
      if (!new_line) {
        free(line);
        return NULL;
      }
      line = new_line;
    }
    line[length++] = c;
  }
  
  line[length] = '\0';
  return line;
}

// Get file size in bytes
long vyl_filesize(FILE *f) {
  if (!f) return -1;
  
  long pos = ftell(f);
  fseek(f, 0, SEEK_END);
  long size = ftell(f);
  fseek(f, pos, SEEK_SET);
  
  return size;
}

// Split string by delimiter
char** vyl_stringsplit(const char *str, const char *delim) {
  if (!str || !delim) return NULL;
  
  // Count occurrences
  int count = 1;
  const char *p = str;
  size_t delim_len = strlen(delim);
  
  while ((p = strstr(p, delim)) != NULL) {
    count++;
    p += delim_len;
  }
  
  // Allocate array (count + 1 for NULL terminator)
  char **result = (char **)malloc((count + 1) * sizeof(char *));
  if (!result) return NULL;
  
  // Split
  char *copy = strdup(str);
  char *token = strtok(copy, delim);
  int i = 0;
  
  while (token && i < count) {
    result[i++] = strdup(token);
    token = strtok(NULL, delim);
  }
  
  result[i] = NULL;  // NULL terminate array
  free(copy);
  
  return result;
}

// Free string array
void vyl_free_string_array(char **arr) {
  if (!arr) return;
  
  for (int i = 0; arr[i] != NULL; i++) {
    free(arr[i]);
  }
  free(arr);
}

// String concatenation
char* vyl_string_concat(const char *a, const char *b) {
  if (!a) a = "";
  if (!b) b = "";
  
  size_t len = strlen(a) + strlen(b) + 1;
  char *result = (char *)malloc(len);
  if (!result) return NULL;
  
  strcpy(result, a);
  strcat(result, b);
  return result;
}

// Simple panic helper used by generated code for bounds checks
void vyl_panic(const char *msg) {
  if (msg)
    fprintf(stderr, "Runtime Error: %s\n", msg);
  else
    fprintf(stderr, "Runtime Error\n");
  exit(1);
}

// Error reporting with code
void vyl_error(const char *msg, int code) {
  if (msg)
    fprintf(stderr, "Error [%d]: %s\n", code, msg);
  else
    fprintf(stderr, "Error [%d]\n", code);
  exit(code);
}


int vyl_to_int(const char *s) {
  if (!s) return 0;
  char *end;
  errno = 0;
  long v = strtol(s, &end, 10);
  if (errno != 0) return 0;
  return (int)v;
}

double vyl_to_decimal(const char *s) {
  if (!s) return 0.0;
  char *end;
  errno = 0;
  double v = strtod(s, &end);
  if (errno != 0) return 0.0;
  return v;
}

char *vyl_to_string_int(long v) {
  char buf[64];
  int n = snprintf(buf, sizeof(buf), "%ld", v);
  char *r = malloc(n + 1);
  if (!r) return NULL;
  memcpy(r, buf, n + 1);
  return r;
}

char *vyl_to_string_dec(double v) {
  char buf[128];
  int n = snprintf(buf, sizeof(buf), "%.6g", v);
  char *r = malloc(n + 1);
  if (!r) return NULL;
  memcpy(r, buf, n + 1);
  return r;
}

void vyl_free_ptr(void *p) {
  if (p) free(p);
}

long vyl_array_len(void *arr) {
  // Unknown for generic pointers; compiler can optimize ArrayLen at compile time
  return -1;
}

// ============================================================================
// Dynamic List (Array) Implementation
// ============================================================================

typedef struct {
  void **items;
  long count;
  long capacity;
} VylList;

void* vyl_list_new(void) {
  VylList *list = (VylList *)malloc(sizeof(VylList));
  if (!list) return NULL;
  
  list->capacity = 16;
  list->count = 0;
  list->items = (void **)malloc(sizeof(void *) * list->capacity);
  
  if (!list->items) {
    free(list);
    return NULL;
  }
  
  return (void *)list;
}

void vyl_list_append(void *list, void *item) {
  if (!list) return;
  
  VylList *vlist = (VylList *)list;
  
  // Grow capacity if needed
  if (vlist->count >= vlist->capacity) {
    vlist->capacity *= 2;
    void **new_items = (void **)realloc(vlist->items, sizeof(void *) * vlist->capacity);
    if (!new_items) return;
    vlist->items = new_items;
  }
  
  vlist->items[vlist->count++] = item;
}

long vyl_list_len(void *list) {
  if (!list) return 0;
  return ((VylList *)list)->count;
}

void* vyl_list_get(void *list, long index) {
  if (!list) return NULL;
  
  VylList *vlist = (VylList *)list;
  if (index < 0 || index >= vlist->count) return NULL;
  
  return vlist->items[index];
}

void vyl_list_set(void *list, long index, void *item) {
  if (!list) return;
  
  VylList *vlist = (VylList *)list;
  if (index < 0 || index >= vlist->count) return;
  
  vlist->items[index] = item;
}

void vyl_list_free(void *list) {
  if (!list) return;
  
  VylList *vlist = (VylList *)list;
  if (vlist->items) {
    free(vlist->items);
  }
  free(vlist);
}

// ============================================================================
// Hash Map (Dictionary) Implementation
// ============================================================================

typedef struct DictEntry {
  char *key;
  void *value;
  VylValueType type;
  struct DictEntry *next;
} DictEntry;

typedef struct {
  DictEntry **buckets;
  int bucket_count;
  long entry_count;
} VylDict;

#define DICT_INITIAL_BUCKETS 16

static unsigned long hash_string(const char *str) {
  unsigned long hash = 5381;
  int c;
  while ((c = *str++)) {
    hash = ((hash << 5) + hash) + c;
  }
  return hash;
}

void* vyl_dict_new(void) {
  VylDict *dict = (VylDict *)malloc(sizeof(VylDict));
  if (!dict) return NULL;
  
  dict->bucket_count = DICT_INITIAL_BUCKETS;
  dict->entry_count = 0;
  dict->buckets = (DictEntry **)calloc(dict->bucket_count, sizeof(DictEntry *));
  
  if (!dict->buckets) {
    free(dict);
    return NULL;
  }
  
  return (void *)dict;
}

void vyl_dict_set(void *dict, const char *key, void *value) {
  // Default: treat as pointer (backwards compat)
  vyl_dict_set_typed(dict, key, value, VYL_VALUE_PTR);
}

// New functions for typed storage
void vyl_dict_set_string(void *dict, const char *key, const char *value) {
  vyl_dict_set_typed(dict, key, (void *)value, VYL_VALUE_STRING);
}

void vyl_dict_set_int(void *dict, const char *key, long value) {
  // Store int as pointer (using casting trick)
  vyl_dict_set_typed(dict, key, (void *)value, VYL_VALUE_INT);
}

void vyl_dict_set_typed(void *dict, const char *key, void *value, VylValueType type) {
  if (!dict || !key) return;
  
  VylDict *vdict = (VylDict *)dict;
  unsigned long hash = hash_string(key);
  int bucket = hash % vdict->bucket_count;
  
  // Check if key exists and update
  DictEntry *entry = vdict->buckets[bucket];
  while (entry) {
    if (strcmp(entry->key, key) == 0) {
      entry->value = value;
      entry->type = type;
      return;
    }
    entry = entry->next;
  }
  
  // Create new entry
  entry = (DictEntry *)malloc(sizeof(DictEntry));
  if (!entry) return;
  
  entry->key = strdup(key);
  entry->value = value;
  entry->type = type;
  entry->next = vdict->buckets[bucket];
  vdict->buckets[bucket] = entry;
  vdict->entry_count++;
}

void* vyl_dict_get(void *dict, const char *key) {
  if (!dict || !key) return NULL;
  
  VylDict *vdict = (VylDict *)dict;
  unsigned long hash = hash_string(key);
  int bucket = hash % vdict->bucket_count;
  
  DictEntry *entry = vdict->buckets[bucket];
  while (entry) {
    if (strcmp(entry->key, key) == 0) {
      return entry->value;
    }
    entry = entry->next;
  }
  
  return NULL;
}

VylValueType vyl_dict_get_type(void *dict, const char *key) {
  if (!dict || !key) return VYL_VALUE_PTR;
  
  VylDict *vdict = (VylDict *)dict;
  unsigned long hash = hash_string(key);
  int bucket = hash % vdict->bucket_count;
  
  DictEntry *entry = vdict->buckets[bucket];
  while (entry) {
    if (strcmp(entry->key, key) == 0) {
      return entry->type;
    }
    entry = entry->next;
  }
  
  return VYL_VALUE_PTR;
}

void vyl_dict_free(void *dict) {
  if (!dict) return;
  
  VylDict *vdict = (VylDict *)dict;
  
  for (int i = 0; i < vdict->bucket_count; i++) {
    DictEntry *entry = vdict->buckets[i];
    while (entry) {
      DictEntry *next = entry->next;
      if (entry->key) free(entry->key);
      free(entry);
      entry = next;
    }
  }
  
  if (vdict->buckets) free(vdict->buckets);
  free(vdict);
}

