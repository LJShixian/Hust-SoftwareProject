int square(int n) { return n * n; }
int main(void) {
    int i;
    int j=1;
    int sum = 0;
    j=j<<10;
    for (i = 0; i < 6; i++) sum += square(i);
    printint(sum);
    putchar('\n');
    return 0;
}
