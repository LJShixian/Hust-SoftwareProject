int show(int a, int b) {
    printint(a*b); putchar(' ');
    printint(a/b); putchar(' ');
    printint(a%b); putchar('\n');
    return 0;
}
int main(void) {
    show(-17,5); show(17,-5); show(-17,-5);
    show(0x80000000,-1); show(123,0);
    return 0;
}
