/* Console input helpers for `scanf`.
 *
 * Split from `io.c` on purpose: everything here needs `getchar`, and the board,
 * QEMU and CPU21 ports have no keyboard. Keeping them in a separate unit means a
 * program that only prints never acquires an undefined `getchar` reference.
 *
 * A "string" and every buffer is an `int` array, because the language has no byte
 * type and the stack frame is word sized.
 */

/* Read one decimal integer into *p. Leading blanks are skipped; the character
 * that ends the number is consumed and dropped, so separate conversions with
 * whitespace in the input rather than writing "%d%c". */
void readint(int* p) {
    int c;
    int n;
    int neg;

    c = getchar();
    while (c == ' ' || c == '\n' || c == '\t' || c == '\r') c = getchar();

    neg = 0;
    if (c == '-') {
        neg = 1;
        c = getchar();
    }

    n = 0;
    while (c >= '0' && c <= '9') {
        n = n * 10 + (c - '0');
        c = getchar();
    }

    if (neg) n = -n;
    *p = n;
}

/* Store one raw character at *p, for `scanf("%c", &ch)`. */
void readchar(int* p) {
    *p = getchar();
}
