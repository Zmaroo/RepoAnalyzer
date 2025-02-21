#include <stdio.h>
#include <stdlib.h>

// Function declaration
void print_hello(void);

// Basic function
int add(int a, int b) {
    return a + b;
}

// Function with pointer parameters
void swap(int* a, int* b) {
    int temp = *a;
    *a = *b;
    *b = temp;
}

// Function returning pointer
int* create_array(int size) {
    return (int*)malloc(size * sizeof(int));
}

// Variadic function
void print_numbers(int count, ...) {
    va_list args;
    va_start(args, count);
    for(int i = 0; i < count; i++) {
        printf("%d ", va_arg(args, int));
    }
    va_end(args);
}

// Function with struct parameter
struct Point {
    int x;
    int y;
};

void print_point(struct Point p) {
    printf("(%d, %d)\n", p.x, p.y);
}

// Function implementation
void print_hello(void) {
    printf("Hello, World!\n");
}

// Main function
int main(int argc, char *argv[]) {
    print_hello();
    return 0;
} 