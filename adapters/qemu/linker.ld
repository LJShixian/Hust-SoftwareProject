OUTPUT_ARCH(riscv)
ENTRY(_start)
SECTIONS {
    . = 0x10000;
    .text : { *(.text.start) *(.text*) *(.rodata*) }
    . = ALIGN(4096);
    .data : { *(.data*) *(.sdata*) }
    .bss : { *(.bss*) *(.sbss*) *(COMMON) }
}
