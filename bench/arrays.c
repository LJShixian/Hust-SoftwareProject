int data[5] = {5, 1, 4, 2, 3};
int sum(int* p, int n) {
    int i = 0;
    int total = 0;
    while (i < n) { total += p[i++]; }
    return total;
}
int main(void) {
    int i = 0;
    int local[4] = {0};
    local[i++] += 5;
    printint(i); putchar(' ');
    printint(local[0]); putchar(' ');
    printint(sum(data,5)); putchar('\n');
    return 0;
}
