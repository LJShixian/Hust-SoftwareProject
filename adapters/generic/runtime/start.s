# Bare-metal addresses are linker symbols; set them for the actual board.
.option norvc
.option norelax
.section .text.start
.globl _start
_start:
    jal t0,.Lboot_pc
.Lboot_pc:
    lw sp,16(t0)
    lw t1,20(t0)
    lw t2,24(t0)
    jal zero,.Lclear
    .word __stack_top
    .word __bss_start
    .word __bss_end
.Lclear:
    beq t1,t2,.Lboot_main
    sw zero,0(t1)
    addi t1,t1,4
    jal zero,.Lclear
.Lboot_main:
    jal ra,main
    jal zero,exit

.globl putchar
putchar:
    jal t0,.Lio_pc
.Lio_pc:
    lw t1,16(t0)
    lw t2,20(t0)
    lw t3,24(t0)
    jal zero,.Lio_store
    .word __uart_tx
    .word __vga_base
    .word .Lvga_cursor
.Lio_store:
    sw a0,0(t1)
    lw t4,0(t3)
    addi t5,zero,10
    beq a0,t5,.Lvga_newline
    slli t5,t4,2
    add t5,t2,t5
    sw a0,0(t5)
    addi t4,t4,1
    jal zero,.Lvga_wrap
.Lvga_newline:
    addi t5,t4,0
    addi t6,zero,80
.Lvga_column:
    slt t0,t5,t6
    beq t0,zero,.Lvga_column_sub
    addi t4,t4,80
    sub t4,t4,t5
    jal zero,.Lvga_wrap
.Lvga_column_sub:
    sub t5,t5,t6
    jal zero,.Lvga_column
.Lvga_wrap:
    addi t6,zero,2000
    slt t5,t4,t6
    beq t5,zero,.Lvga_reset
    jal zero,.Lvga_save
.Lvga_reset:
    addi t4,zero,0
.Lvga_save:
    sw t4,0(t3)
    jalr zero,0(ra)

.globl exit
exit:
    jal t0,.Lexit_pc
.Lexit_pc:
    lw t1,8(t0)
    jal zero,.Lexit_store
    .word __exit_status
.Lexit_store:
    sw a0,0(t1)
.Lhalt:
    jal zero,.Lhalt

.section .bss
.balign 4
.Lvga_cursor:
    .zero 4
