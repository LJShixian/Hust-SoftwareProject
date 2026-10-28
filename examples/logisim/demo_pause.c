/*
 * 课堂演示（分段停钟版）：mycc 编译 → Logisim 版 RISC-V CPU 上运行
 *
 * 编译：
 *   python -m mycc examples/logisim/demo_pause.c --target logisim -o build/demo/demo_pause.asm
 *
 * 和 demo.c 打印的内容完全一样，区别只在每一行后面多一次 exit(0)。
 *
 * 为什么需要它：RISC-V 的 ecall 里只有 a7=10（exit）会让 CPU 停钟等 go，
 * a7=11（putchar）打完字符就继续跑。所以加一句 exit(0) 就得到"跑一段、停一下"
 * 的节奏：讲完这一行算了什么，按一下 go 再跑下一行。
 *
 * 预期：每按一下 go，TTY 上多出一行，共 7 行。
 *   scores[0] = 7
 *   sum       = 33
 *   max       = 9
 *   sum*2     = 66      软件乘法（没有 M 扩展）
 *   sum/4     = 8       软件除法
 *   sum<<2    = 132     SLL
 *   sum^0x5a  = 123     XOR
 * 最后停在入口存根的 a7=10 停机点。
 */

int scores[6] = {7, 3, 9, 1, 5, 8};

/* 这个编译器不支持字符串字面量，所以"标签"用 int 数组 + 字符字面量写。 */
int lbl_scores[10] = {'s', 'c', 'o', 'r', 'e', 's', '[', '0', ']', 0};
int lbl_sum[4]     = {'s', 'u', 'm', 0};
int lbl_max[4]     = {'m', 'a', 'x', 0};
int lbl_mul[6]     = {'s', 'u', 'm', '*', '2', 0};
int lbl_div[6]     = {'s', 'u', 'm', '/', '4', 0};
int lbl_shl[7]     = {'s', 'u', 'm', '<', '<', '2', 0};
int lbl_xor[9]     = {'s', 'u', 'm', '^', '0', 'x', '5', 'a', 0};

void print(int* s) {
    while (*s != 0) {
        putchar(*s);
        s = s + 1;
    }
}

void show(int* name, int value) {
    print(name);
    putchar(' ');
    putchar('=');
    putchar(' ');
    printint(value);
    putchar('\n');
}

int total(int* p, int* end) {
    int sum = 0;
    while (p < end) {
        sum = sum + *p;
        p = p + 1;
    }
    return sum;
}

int largest(int* p, int n) {
    int best = p[0];
    int i = 1;
    while (i < n) {
        if (best < p[i]) {
            best = p[i];
        }
        i = i + 1;
    }
    return best;
}

int main(void) {
    int sum = total(scores, scores + 6);

    show(lbl_scores, scores[0]);            exit(0);   /* 1) RAM 初值   */
    show(lbl_sum, sum);                     exit(0);   /* 2) 累加和     */
    show(lbl_max, largest(scores, 6));      exit(0);   /* 3) 最大值     */
    show(lbl_mul, sum * 2);                 exit(0);   /* 4) 软件乘法   */
    show(lbl_div, sum / 4);                 exit(0);   /* 5) 软件除法   */
    show(lbl_shl, sum << 2);                exit(0);   /* 6) SLL        */
    show(lbl_xor, sum ^ 0x5A);                         /* 7) XOR        */
    return 0;
}
