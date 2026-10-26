int first = 7;
int second = 9;
int values[4] = {0x12345678, -2, 0x80000000, 3};
int calls;
int tick(void) { calls++; return 1; }
int fact(int n) { if (n < 2) return 1; return n * fact(n - 1); }
int check(int a, int b, int q, int r) {
    if (a / b != q) return 1;
    if (a % b != r) return 2;
    return 0;
}
int main(void) {
    int a[4] = {0};
    int src[2] = {0x12345678, 0x23456789};
    int dst[2] = {0};
    int i = 0;
    int n = 5;
    int negative = 0x80000000;
    int* p = a;
    if (first != 7 || second != 9) return 10;
    if (values[0] != 0x12345678 || values[1] != -2 || values[2] != negative) return 11;
    a[i++] += 5;
    if (i != 1 || a[0] != 5) return 12;
    0 && tick(); 1 || tick();
    if (calls != 0) return 13;
    if (fact(6) != 720) return 14;
    if (check(-17,5,-3,-2) || check(17,-5,-3,2)) return 15;
    if (check(negative,-1,negative,0) || check(123,0,-1,123)) return 16;
    if ((negative >> n) != 0xfc000000 || (0x12345678 << n) != 0x468acf00) return 17;
    if ((0x12345678 ^ 0x76543210) != 0x64606468) return 18;
    p++; *p = 7;
    if (a[1] != 7 || sizeof(a) != 16) return 19;
    memcpy(dst,src,5);
    if (dst[0] != 0x12345678 || dst[1] != 0x89) return 20;
    memset(dst,255,3);
    if (dst[0] != 0x12ffffff) return 21;
    first = 123; second = 456;
    if (first != 123 || second != 456) return 22;
    putchar('P'); putchar('A'); putchar('S'); putchar('S'); putchar('\n');
    return 0;
}
