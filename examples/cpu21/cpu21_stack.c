int recurse(int n) { return recurse(n + 1) + n; }
int main(void) { return recurse(0); }
