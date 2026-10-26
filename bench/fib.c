int fib(int n) {
    if (n < 2) return n;
    return fib(n - 1) + fib(n - 2);
}
int main(void) { printint(fib(10)); putchar('\n'); return 0; }
