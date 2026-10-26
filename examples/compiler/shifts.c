int main(void) {
    int n = 5;
    int negative = 0x80000000;
    printhex(0x12345678 << n); putchar(' ');
    printhex(negative >> n); putchar(' ');
    printhex(0x12345678 ^ 0x76543210); putchar('\n');
    return 0;
}
