#include <stdio.h>
#include <time.h>
//This is the C script used in the benchmark
int main() {
    printf("Starting benchmark: counting to 1,000,000,000...\n");
    
    clock_t start = clock();
    long i = 0;
    while (i < 1000000000) {
        i++;
    }
    clock_t end = clock();
    
    double elapsed = (double)(end - start) / CLOCKS_PER_SEC;
    printf("Time taken (seconds): \n%f\n", elapsed);
    printf("Finished.\n");
    
    return 0;
}
