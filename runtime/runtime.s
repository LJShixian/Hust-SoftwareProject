# Software arithmetic helpers. No M instructions, lui, or variable shifts.
.option norvc
.option norelax
.section .text
.balign 4
.globl __mulsi3
__mulsi3:
    addi t0,zero,0
.Lmul_loop:
    beq a1,zero,.Lmul_done
    andi t1,a1,1
    beq t1,zero,.Lmul_next
    add t0,t0,a0
.Lmul_next:
    slli a0,a0,1
    srli a1,a1,1
    jal zero,.Lmul_loop
.Lmul_done:
    addi a0,t0,0
    jalr zero,0(ra)

# Shared signed restoring division. Quotient in a0, remainder in a1.
.Lsigned_div:
    addi t6,a0,0
    beq a1,zero,.Ldiv_zero
    slt t3,a0,zero
    slt t4,a1,zero
    sub t5,t3,t4
    beq t3,zero,.Ldiv_abs_b
    sub a0,zero,a0
.Ldiv_abs_b:
    beq t4,zero,.Ldiv_begin
    sub a1,zero,a1
.Ldiv_begin:
    addi t0,zero,0
    addi t1,zero,0
    addi t2,zero,32
.Ldiv_loop:
    slli t1,t1,1
    srli t4,a0,31
    or t1,t1,t4
    slli a0,a0,1
    slli t0,t0,1
    sltu t4,t1,a1
    beq t4,zero,.Ldiv_subtract
    jal zero,.Ldiv_next
.Ldiv_subtract:
    sub t1,t1,a1
    addi t0,t0,1
.Ldiv_next:
    addi t2,t2,-1
    beq t2,zero,.Ldiv_sign
    jal zero,.Ldiv_loop
.Ldiv_sign:
    beq t5,zero,.Ldiv_remainder
    sub t0,zero,t0
.Ldiv_remainder:
    beq t3,zero,.Ldiv_return
    sub t1,zero,t1
.Ldiv_return:
    addi a0,t0,0
    addi a1,t1,0
    jalr zero,0(ra)
.Ldiv_zero:
    addi a0,zero,-1
    addi a1,t6,0
    jalr zero,0(ra)

.globl __divsi3
__divsi3:
    jal zero,.Lsigned_div
.globl __modsi3
__modsi3:
    addi sp,sp,-16
    sw ra,12(sp)
    jal ra,.Lsigned_div
    addi a0,a1,0
    lw ra,12(sp)
    addi sp,sp,16
    jalr zero,0(ra)

.globl __ashlsi3
__ashlsi3:
    andi a1,a1,31
.Lshl_loop:
    beq a1,zero,.Lshift_return
    slli a0,a0,1
    addi a1,a1,-1
    jal zero,.Lshl_loop
.globl __ashrsi3
__ashrsi3:
    andi a1,a1,31
.Lshr_loop:
    beq a1,zero,.Lshift_return
    srai a0,a0,1
    addi a1,a1,-1
    jal zero,.Lshr_loop
.globl __lshrsi3
__lshrsi3:
    andi a1,a1,31
.Llshr_loop:
    beq a1,zero,.Lshift_return
    srli a0,a0,1
    addi a1,a1,-1
    jal zero,.Llshr_loop
.Lshift_return:
    jalr zero,0(ra)

# Standard byte counts. Byte reads use aligned lw and immediate shifts.
.globl memcpy
memcpy:
    addi t0,a0,0
.Lcopy_loop:
    beq a2,zero,.Lmem_return
    andi t2,a1,-4
    lw t1,0(t2)
    andi t2,a1,3
.Lcopy_byte_shift:
    beq t2,zero,.Lcopy_byte_store
    srli t1,t1,8
    addi t2,t2,-1
    jal zero,.Lcopy_byte_shift
.Lcopy_byte_store:
    sb t1,0(t0)
    addi t0,t0,1
    addi a1,a1,1
    addi a2,a2,-1
    jal zero,.Lcopy_loop
.globl memset
memset:
    addi t0,a0,0
.Lset_loop:
    beq a2,zero,.Lmem_return
    sb a1,0(t0)
    addi t0,t0,1
    addi a2,a2,-1
    jal zero,.Lset_loop
.Lmem_return:
    jalr zero,0(ra)
