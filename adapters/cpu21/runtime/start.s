# CPU21 Harvard boot. All addresses are immediate relocations, never ROM data.
.option norvc
.option norelax
.section .text.start
.globl _start
_start:
    csrrci zero,0x004,1
    lui sp,%hi(__stack_top)
    addi sp,sp,%lo(__stack_top)
    lui t0,%hi(__bss_start)
    addi t0,t0,%lo(__bss_start)
    lui t1,%hi(__bss_end)
    addi t1,t1,%lo(__bss_end)
.Lcpu21_zero:
    beq t0,t1,.Lcpu21_devices
    sw zero,0(t0)
    addi t0,t0,4
    jal zero,.Lcpu21_zero
.Lcpu21_devices:
    lui t0,%hi(__mouse_ctrl)
    addi t0,t0,%lo(__mouse_ctrl)
    sw zero,0(t0)
    lui t0,%hi(__display_ctrl)
    addi t0,t0,%lo(__display_ctrl)
    sw zero,0(t0)
    lui t0,%hi(__display_cursor)
    addi t0,t0,%lo(__display_cursor)
    sw zero,0(t0)
    lui t0,%hi(__vga_base)
    addi t0,t0,%lo(__vga_base)
    addi t1,zero,600
.Lcpu21_clear_fb:
    sw zero,0(t0)
    addi t0,t0,4
    addi t1,t1,-1
    beq t1,zero,.Lcpu21_call
    jal zero,.Lcpu21_clear_fb
.Lcpu21_call:
    jal ra,__mycc_init_globals
    jal ra,main
    jal zero,exit

.section .text
.globl vga_cell
vga_cell:
    addi t0,zero,1200
    sltu t0,a0,t0
    beq t0,zero,.Lcpu21_cell_return
    slli t0,a0,1
    lui t1,%hi(__vga_base)
    addi t1,t1,%lo(__vga_base)
    add t0,t0,t1
    andi t1,a1,63
    sb t1,0(t0)
    andi t1,a2,7
    sb t1,1(t0)
.Lcpu21_cell_return:
    jalr zero,0(ra)

.globl vga_cursor
vga_cursor:
    addi t0,zero,40
    sltu t0,a0,t0
    beq t0,zero,.Lcpu21_cursor_return
    addi t0,zero,30
    sltu t0,a1,t0
    beq t0,zero,.Lcpu21_cursor_return
    slli t0,a1,8
    or t0,t0,a0
    lui t1,%hi(__display_cursor)
    addi t1,t1,%lo(__display_cursor)
    sw t0,0(t1)
    lui t1,%hi(__display_ctrl)
    addi t1,t1,%lo(__display_ctrl)
    addi t0,zero,1
    sw t0,0(t1)
.Lcpu21_cursor_return:
    jalr zero,0(ra)

.globl exit
exit:
    lui t0,%hi(__led)
    addi t0,t0,%lo(__led)
    sw a0,0(t0)
    lui t0,%hi(__seg)
    addi t0,t0,%lo(__seg)
    sw a0,0(t0)
.Lcpu21_exit:
    jal zero,.Lcpu21_exit

.globl __mycc_stack_overflow
__mycc_stack_overflow:
    addi a0,zero,83
    slli a0,a0,8
    addi a0,a0,84
    slli a0,a0,8
    addi a0,a0,65
    slli a0,a0,8
    addi a0,a0,75
    jal zero,exit
