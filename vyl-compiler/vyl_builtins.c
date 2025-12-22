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

// Simple panic helper used by generated code for bounds checks
void vyl_panic(const char *msg) {
  if (msg)
    fprintf(stderr, "Runtime Error: %s\n", msg);
  else
    fprintf(stderr, "Runtime Error\n");
  exit(1);
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
