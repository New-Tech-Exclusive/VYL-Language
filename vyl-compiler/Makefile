CC = gcc
CFLAGS = -Wall -Wextra -std=c99 -D_POSIX_C_SOURCE=200809L -g -fsanitize=address,leak,undefined -lm
TARGET = vyl
SRCS = main.c lexer.c parser.c codegen.c vyl_builtins.c
OBJS = $(SRCS:.c=.o)

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $(TARGET) $(OBJS) -lm
%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET)

release: CFLAGS = -Wall -Wextra -std=c99 -D_POSIX_C_SOURCE=200809L -O3 -flto -march=native -DNDEBUG -lm
release: TARGET = vyl-release
release: $(OBJS)
	$(CC) $(CFLAGS) -o $(TARGET) $(OBJS) -lm

.PHONY: release

.PHONY: all clean
