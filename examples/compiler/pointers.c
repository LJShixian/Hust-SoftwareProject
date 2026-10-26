int main(void) {
    int a[4] = {2,4,6,8};
    int* p = a;
    int* q = &a[3];
    printint(q-p); putchar(' ');
    p++; *p += 3;
    printint(a[1]); putchar(' ');
    printint(sizeof(a)); putchar('\n');
    return 0;
}
