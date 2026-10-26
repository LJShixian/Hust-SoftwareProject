int square(int n) { return n * n; }
int main(void) {
    int i;
    int sum = 0;
    for (i = 0; i < 6; i++) sum += square(i);
    printint(sum);
    putchar('\n');
    return 0;
}
