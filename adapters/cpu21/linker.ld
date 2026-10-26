OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY {
    ROM (rx) : ORIGIN = 0, LENGTH = 32K
    RAM (rw) : ORIGIN = 0, LENGTH = 4K
}
PROVIDE(__led = 0x1000);
PROVIDE(__seg = 0x1004);
PROVIDE(__vga_base = 0x2000);
PROVIDE(__display_ctrl = 0x1140);
PROVIDE(__display_cursor = 0x1144);
PROVIDE(__mouse_ctrl = 0x110c);
SECTIONS {
    .text : { KEEP(*(.text.start)) *(.text*) } > ROM
    .bss (NOLOAD) : {
        . = ALIGN(4); __bss_start = .;
        *(.bss*) *(.sbss*) *(COMMON)
        . = ALIGN(4); __bss_end = .;
    } > RAM
    .data : { *(.data*) *(.sdata*) *(.rodata*) } > RAM
    __stack_top = ORIGIN(RAM) + LENGTH(RAM);
    ASSERT(SIZEOF(.data) == 0, "CPU21 Harvard: initialized data/ROM literal pools are forbidden; compile C with --target cpu21")
    ASSERT(__bss_end <= 2048, "CPU21: globals exceed 2 KiB; at least 2 KiB of stack must remain")
}
