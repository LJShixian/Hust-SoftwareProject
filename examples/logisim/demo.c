/*
 * 课堂演示程序：mycc 编译 → Logisim 版 RISC-V CPU 上运行
 *
 * 编译（一条命令同时得到汇编和两个镜像）：
 *   python -m mycc examples/logisim/demo.c --target logisim -o build/demo/demo.asm
 *
 * 产物：
 *   build/demo/demo.asm      可读的单文件汇编（也能丢进 RARS 跑）
 *   build/demo/demo.rom.hex  载入 Logisim 的 ROM（指令）
 *   build/demo/demo.ram.hex  载入 Logisim 的 RAM（全局数组初值）
 *
 * 输出走标准 RISC-V 系统调用：putchar -> a7=11，exit -> a7=10。
 * 所以这段程序在 TTY 上打出的就是下面这几行文本；丢进 RARS 跑结果一样。
 *
 * 预期输出：
 *   scores[0] = 7          全局数组初值已从 RAM 装对
 *   sum       = 33         指针遍历 + 循环累加
 *   max       = 9          逐元素比较
 *   sum*2     = 66         软件乘法（这台 CPU 没有 M 扩展）
 *   sum/4     = 8          软件除法
 *   sum<<2    = 132        SLL
 *   sum^0x5a  = 123        XOR
 */

int scores[6] = {7, 3, 9, 1, 5, 8};

/* 这个编译器不支持字符串字面量，所以"标签"用 int 数组 + 字符字面量写。
 * 顺带正好演示全局数组、指针遍历和 *p 取数。 */
int lbl_scores[10] = {'s', 'c', 'o', 'r', 'e', 's', '[', '0', ']', 0};
int lbl_sum[4]     = {'s', 'u', 'm', 0};
int lbl_max[4]     = {'m', 'a', 'x', 0};
int lbl_mul[6]     = {'s', 'u', 'm', '*', '2', 0};
int lbl_div[6]     = {'s', 'u', 'm', '/', '4', 0};
int lbl_shl[7]     = {'s', 'u', 'm', '<', '<', '2', 0};
int lbl_xor[9]     = {'s', 'u', 'm', '^', '0', 'x', '5', 'a', 0};

/* 打印一个以 0 结尾的 int 数组：没有 print_string 系统调用，用 putchar 循环就够。 */
void print(int* s) {
    while (*s != 0) {
        putchar(*s);
        s = s + 1;
    }
}

/* 打印 "名字 = 值" 这样一行。 */
void show(int* name, int value) {
    print(name);
    putchar(' ');
    putchar('=');
    putchar(' ');
    printint(value);
    putchar('\n');
}

/* 用指针遍历：p 与 end 的比较会用到 sltu，加法则逐元素累加。 */
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

    show(lbl_scores, scores[0]);          /* RAM 初值       */
    show(lbl_sum, sum);                   /* 累加和         */
    show(lbl_max, largest(scores, 6));
    show(lbl_mul, sum * 2);               /* 软件乘法       */
    show(lbl_div, sum / 4);               /* 软件除法       */
    show(lbl_shl, sum << 2);              /* SLL            */
    show(lbl_xor, sum ^ 0x5A);            /* XOR            */
    return 0;
}
