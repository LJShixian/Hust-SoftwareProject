/*
 * 课堂演示（逐值停顿版）：mycc 编译 → Logisim 版 RISC-V CPU 上运行
 *
 * 编译：
 *   python -m mycc examples/logisim/demo_pause.c --target logisim -o build/demo/demo_pause.asm
 *
 * 和 demo.c 是同一个程序，区别只在每个 printhex 后面多一行 exit(0)。
 *
 * 为什么需要它：这台 CPU 对 ecall 的规则是
 *     a7 == 34  ->  把 a0 显示成十六进制，然后继续执行
 *     a7 != 34  ->  停机，等 go 按钮
 * 所以 printhex 只会一闪而过，只有 exit(0)（a7=10）才真正停住。
 * 课程基准程序 risc-v-benchmark_ccab_full.asm 也是这么做的：37 条 ecall 里
 * 32 条是 a7=34 的显示，5 条是 a7=10 的分段停点。
 *
 * 预期：每按一下 go 停在一个值上，共 7 次。
 *   0x00000007  scores[0]      RAM 初值装对了
 *   0x00000021  累加和 33      指针遍历 + 循环
 *   0x00000009  最大值
 *   0x00000042  33*2 = 66      软件乘法（没有 M 扩展）
 *   0x00000008  33/4 = 8       软件除法
 *   0x00000084  33<<2 = 132    SLL
 *   0x0000007b  33^0x5A = 123  XOR
 * 最后一个值一直保持，直到再按一次 go 走完 send 入口的 a7=10 停机。
 */

int scores[6] = {7, 3, 9, 1, 5, 8};

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

    printhex(scores[0]);              exit(0);   /* 1) RAM 初值 */
    printhex(sum);                    exit(0);   /* 2) 累加和   */
    printhex(largest(scores, 6));     exit(0);   /* 3) 最大值   */
    printhex(sum * 2);                exit(0);   /* 4) 软件乘法 */
    printhex(sum / 4);                exit(0);   /* 5) 软件除法 */
    printhex(sum << 2);               exit(0);   /* 6) SLL      */
    printhex(sum ^ 0x5A);                        /* 7) XOR      */
    return 0;
}
