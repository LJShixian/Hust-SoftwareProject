/* CPU21 has no UART. Console writes glyph/color pairs to the 40x30 VGA grid.
 * Hardware has no distinct 0/9 glyphs: use O/Q. Lowercase is displayed uppercase.
 * Other unsupported characters use the existing '?' glyph (13).
 */
int cpu21_console_position;

int cpu21_glyph(int c) {
    if (c >= 'a' && c <= 'z') c -= 32;
    if (c >= 'A' && c <= 'Z') return c - 'A' + 16;
    if (c >= '1' && c <= '8') return c - '0';
    if (c == '0') return 30; /* O */
    if (c == '9') return 32; /* Q */
    if (c == ' ') return 0;
    if (c == '-') return 14;
    return 13;
}

void putchar(int c) {
    int n;
    if (c == '\n') cpu21_console_position = (cpu21_console_position / 40 + 1) * 40;
    else if (c == '\r') cpu21_console_position -= cpu21_console_position % 40;
    else if (c == '\t') {
        n = 4 - cpu21_console_position % 4;
        while (n > 0) { putchar(' '); n--; }
    } else {
        vga_cell(cpu21_console_position, cpu21_glyph(c), 7);
        cpu21_console_position++;
    }
    if (cpu21_console_position >= 1200) cpu21_console_position = 0;
}
