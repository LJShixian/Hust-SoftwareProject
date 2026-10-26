# Linux-user test shim only. ecall is never part of the FPGA runtime.
.option norvc
.option norelax
.section .text.start
.globl _start
_start:
    jal ra,main
    jal zero,exit
.section .text
.globl putchar
putchar:
    addi sp,sp,-16
    sw a0,0(sp)
    addi a0,zero,1
    addi a1,sp,0
    addi a2,zero,1
    addi a7,zero,64
    ecall
    lw a0,0(sp)
    addi sp,sp,16
    jalr zero,0(ra)
.globl exit
exit:
    addi a7,zero,93
    ecall
.Lhalt_linux:
    jal zero,.Lhalt_linux
