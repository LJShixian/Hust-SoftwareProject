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
 * 交互：a7=34 的 ecall 只把 a0 显示成十六进制就继续，a7≠34 才停机等 go。
 *      所以这个版本会把 7 个值连续显示完，最后停在结尾的 a7=10 处。
 *      想让每个值都停住等 go（课堂演示更好用），用同目录的 demo_pause.c，
 *      它的区别只是每个 printhex 后面多了一行 exit(0)。
 *
 * 预期检查点（十六进制，依次出现）：
 *   1) 0x00000007  scores[0]，说明 RAM 里的全局数组初值装对了
 *   2) 0x00000021  累加和 7+3+9+1+5+8 = 33，指针遍历 + 循环
 *   3) 0x00000009  最大值，逐元素比较
 *   4) 0x00000042  33*2 = 66，这台 CPU 没有 M 扩展，走软件乘法
 *   5) 0x00000008  33/4 = 8，走软件除法（32 位恢复余数除法）
 *   6) 0x00000084  33<<2 = 132，用到 SLL
 *   7) 0x0000007b  33^0x5A = 123，用到 XOR
 *   最后停在入口存根的 a7=10 处，程序结束。
 */

int scores[6] = {7, 3, 9, 1, 5, 8};

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

    printhex(scores[0]);              /* 1) RAM 初值       */
    printhex(sum);                    /* 2) 累加和         */
    printhex(largest(scores, 6));     /* 3) 最大值         */
    printhex(sum * 2);                /* 4) 软件乘法       */
    printhex(sum / 4);                /* 5) 软件除法       */
    printhex(sum << 2);               /* 6) SLL            */
    printhex(sum ^ 0x5A);             /* 7) XOR            */
    return 0;
}
