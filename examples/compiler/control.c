int calls;
int tick(void) { calls++; return 1; }
int main(void) {
    int i; int sum = 0;
    0 && tick();
    1 || tick();
    for (i = 0; i < 10; i++) {
        if (i == 2) continue;
        if (i == 7) break;
        sum += i;
    }
    printint(calls); putchar(' '); printint(sum); putchar('\n');
    return 0;
}
