/*
 * 0/1 背包（洛谷 P1048「采药」同型）：mycc 编译器演示程序
 *
 * 编译：
 *   python -m mycc examples/logisim/knapsack.c --target logisim -o build/demo/knapsack.asm
 *
 * 产物：
 *   build/demo/knapsack.rom.hex   装进 Logisim 的 ROM（964 字 / 上限 1024）
 *   build/demo/knapsack.ram.hex   装进 Logisim 的 RAM（660 字节 / 上限 1024）
 *
 * 输入格式（与 P1048 一致）：
 *   第一行            容量 cap   草药株数 count
 *   接下来 count 行   每株耗时  每株价值
 *
 * 样例输入：
 *   70 3
 *   71 100
 *   69 1
 *   1 2
 * 样例输出：
 *   items: (71,100) (69,1) (1,2)
 *   max value for cap 70 = 3
 *
 * 这段代码用到的语言与后端特性：
 *   - scanf / printf：格式串在编译期解析成对 printint 的直接调用
 *   - 字符串字面量、int 数组作字符串
 *   - 全局数组（进 RAM 镜像）、指针传参、一维下标
 *   - 函数定义与调用（imax）
 *   - 二重循环；内层逆序递推，这是 0/1 背包正确性的关键
 *
 * 容量与株数上限受课堂 CPU 的 1024 字节 RAM 限制，所以取 cap <= 80、count <= 16。
 */

int cost[16];        /* 每株耗时 */
int worth[16];       /* 每株价值 */
int best[81];        /* best[w] = 容量 w 能拿到的最大价值 */

int imax(int a, int b) {
    if (a > b) return a;
    return b;
}

int main(void) {
    int cap;
    int count;
    int i;
    int w;

    scanf("%d %d", &cap, &count);

    i = 0;
    while (i < count) {
        scanf("%d %d", &cost[i], &worth[i]);
        i = i + 1;
    }

    printf("items:");
    i = 0;
    while (i < count) {
        printf(" (%d,%d)", cost[i], worth[i]);
        i = i + 1;
    }
    printf("\n");

    /* 0/1 背包：容量必须从大到小扫，否则同一株会被重复选入。 */
    i = 0;
    while (i < count) {
        w = cap;
        while (w >= cost[i]) {
            best[w] = imax(best[w], best[w - cost[i]] + worth[i]);
            w = w - 1;
        }
        i = i + 1;
    }

    printf("max value for cap %d = %d\n", cap, best[cap]);
    return 0;
}
