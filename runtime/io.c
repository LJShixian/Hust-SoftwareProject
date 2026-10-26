void printint(int n) {
    int digits[12];
    int count = 0;
    int r;
    if (n < 0) putchar('-');
    /* Keep negatives negative so INT_MIN is representable. */
    if (n > 0) n = -n;
    while (n != 0) {
        r = n % 10;
        digits[count++] = -r;
        n = n / 10;
    }
    if (count == 0) putchar('0');
    while (count > 0) putchar(digits[--count] + '0');
}
void printhex(int n) {
    int i = 7;
    int digit;
    putchar('0'); putchar('x');
    while (i >= 0) {
        digit = (n >> (i * 4)) & 15;
        if (digit < 10) putchar('0' + digit);
        else putchar('a' + digit - 10);
        i--;
    }
}
