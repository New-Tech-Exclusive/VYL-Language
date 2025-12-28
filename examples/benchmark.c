#include <stdio.h>

long fib_iter(long n) {
    if (n <= 1) return n;
    long a = 0, b = 1;
    for (long i = 2; i <= n; i++) {
        long t = a + b;
        a = b;
        b = t;
    }
    return b;
}

int main() {
    printf("%ld\n", fib_iter(1000));
    return 0;
}
