OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY {
    IMEM (rx) : ORIGIN = 0x0000, LENGTH = 32K
    DMEM (rw) : ORIGIN = 0x8000, LENGTH = 16K
}
/* Provisional board I/O addresses: override with --defsym after hardware confirmation. */
PROVIDE(__uart_tx = 0x10000000);
PROVIDE(__vga_base = 0x20000000);
PROVIDE(__exit_status = 0x10000004);
SECTIONS {
    .text : { *(.text.start) *(.text*) *(.rodata*) } > IMEM
    .data : { *(.data*) *(.sdata*) } > DMEM
    .bss (NOLOAD) : {
        . = ALIGN(4); __bss_start = .;
        *(.bss*) *(.sbss*) *(COMMON)
        . = ALIGN(4); __bss_end = .;
    } > DMEM
    __stack_top = ORIGIN(DMEM) + LENGTH(DMEM);
    ASSERT(__bss_end + 4096 <= __stack_top, "DMEM does not leave 4 KiB for stack")
}
