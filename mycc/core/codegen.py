"""Stack-based ILP32 emission with ordered capability-guarded lowering rules."""
from dataclasses import dataclass
from .types import INT, i32, CodegenPolicy


@dataclass(frozen=True)
class Rule:
    requires: frozenset
    lines: tuple
    reason: str


def rule(requires, lines, reason):
    return Rule(frozenset(requires.split()),tuple(lines.split(';')),reason)


@dataclass(frozen=True)
class LoweringRecord:
    """One AO -> selected rule decision, with the evidence an external review needs.

    `delta` is the instruction-count premium over the best rule in the table, so a
    reader can tell how much a capability fallback actually costs. `rejected`
    keeps one entry per rule that was skipped and why, including rules disabled by
    a missing capability rather than by precedence.
    """
    op: str
    reason: str
    rejected: tuple = ()
    delta: int = 0
    file: str = ''
    line: int = 0
    col: int = 0

    @property
    def location(self):
        return f'{self.file}:{self.line}:{self.col}' if self.line else '-'


LOWERING_TABLE = {
    'MUL': (rule('mul','mul a0,t0,a0','hardware multiplication'),
            rule('','addi a1,a0,0;addi a0,t0,0;jal ra,__mulsi3','mul unavailable; software multiplication')),
    'DIV': (rule('div','div a0,t0,a0','hardware signed division'),
            rule('','addi a1,a0,0;addi a0,t0,0;jal ra,__divsi3','div unavailable; software signed division')),
    'REM': (rule('rem','rem a0,t0,a0','hardware signed remainder'),
            rule('div','addi sp,sp,-16;sw t0,0(sp);sw a0,4(sp);div a1,t0,a0;addi a0,t0,0;lw a0,4(sp);jal ra,__mulsi3;lw t0,0(sp);sub a0,t0,a0;addi sp,sp,16','rem unavailable; a-(a/b)*b'),
            rule('','addi a1,a0,0;addi a0,t0,0;jal ra,__modsi3','rem and div unavailable; software remainder')),
    'XOR': (rule('xor','xor a0,t0,a0','hardware xor'),
            rule('','or t1,t0,a0;and a0,t0,a0;sub a0,t1,a0','xor unavailable; (a|b)-(a&b)')),
    'SHL': (rule('sll','sll a0,t0,a0','hardware variable shift'),
            rule('','addi a1,a0,0;addi a0,t0,0;jal ra,__ashlsi3','sll unavailable; software shift')),
    'SHR': (rule('sra','sra a0,t0,a0','hardware arithmetic variable shift'),
            rule('','addi a1,a0,0;addi a0,t0,0;jal ra,__ashrsi3','sra unavailable; software shift')),
}


class Generator:
    def __init__(self,profile,options=None):
        self.profile=profile; self.lines=['.option norvc','.option norelax']
        self.policy=options.policy if options else CodegenPolicy()
        self.target=self.policy.name
        self.library=options is not None and not options.require_main
        self.global_initializers=[]
        self.serial=0; self.lowering=[]; self.ir=[]; self.loops=[]
        self.node=None

    def emit(self,*lines): self.lines.extend(lines)

    def node_of(self):
        token=getattr(self.node,'token',None)
        return (token.file,token.line,token.col) if token is not None else ('',0,0)

    def record(self,op,reason,rejected=(),delta=0):
        """Append one decision with its source position and cost premium."""
        f,l,c=self.node_of()
        self.lowering.append(LoweringRecord(op,reason,tuple(rejected),delta,f,l,c))

    def label(self,stem='label'):
        self.serial+=1
        return f'.L{stem}_{self.serial}'

    def mark(self,op,*args):
        self.ir.append((op,args))

    def choose(self,op):
        self.mark(op)
        rules=LOWERING_TABLE[op]
        rejected=[]
        for r in rules:
            missing=r.requires-self.profile.instructions
            if not missing:
                self.record(op,r.reason,rejected,len(r.lines)-len(rules[0].lines))
                self.emit(*r.lines)
                return
            rejected.append(f"{r.reason} (missing {', '.join(sorted(missing))})")
        raise RuntimeError('unreachable: missing fallback for '+op)

    def const(self,value,rd='a0'):
        value=i32(value); self.mark('CONST32',value)
        if -2048 <= value <= 2047:
            self.emit(f'addi {rd},zero,{value}'); return
        if self.profile.has('lui'):
            hi=(value+0x800)>>12; lo=value-(hi<<12)
            self.emit(f'lui {rd},{hi & 0xfffff}',f'addi {rd},{rd},{lo}')
            self.record('CONST32','lui + signed low 12 bits')
        else:
            v=value & 0xffffffff
            self.emit(f'addi {rd},zero,{v >> 24}')
            for shift in (16,8,0): self.emit(f'slli {rd},{rd},8',f'addi {rd},{rd},{(v>>shift)&255}')
            self.record('CONST32','lui unavailable; byte synthesis',
                        ('lui + signed low 12 bits (missing lui)',),7)

    def address(self,symbol,rd='a0'):
        self.mark('ADDRESS',symbol.name)
        if symbol.global_:
            if self.profile.has('lui'):
                self.emit(f'lui {rd},%hi({symbol.name})',f'addi {rd},{rd},%lo({symbol.name})')
                self.record('ADDRESS','lui %hi/%lo')
            elif self.policy.data_address_bits:
                shift=32-self.policy.data_address_bits
                self.emit(f'addi {rd},zero,%lo({symbol.name})',f'slli {rd},{rd},{shift}',f'srli {rd},{rd},{shift}')
                self.record('ADDRESS','bounded RAM address via relocations; no ROM loads',
                            ('lui %hi/%lo (missing lui)',),1)
            else:
                pc,done=self.label('pc'),self.label('addr')
                self.emit(f'jal {rd},{pc}',pc+':',f'lw {rd},8({rd})',f'jal zero,{done}',f'.word {symbol.name}',done+':')
                self.record('ADDRESS','lui unavailable; PC literal address',
                            ('lui %hi/%lo (missing lui)',),2)
        else:
            self.const(symbol.offset,rd)
            self.emit(f'add {rd},s0,{rd}')

    def push(self,reg='a0'):
        self.emit('addi sp,sp,-16')
        self.stack_check()
        self.emit(f'sw {reg},0(sp)')

    def stack_check(self):
        symbol=self.policy.stack_guard_symbol
        if not symbol: return
        if self.profile.has('lui'):
            self.emit(f'lui t3,%hi({symbol})',f'addi t3,t3,%lo({symbol})')
        else:
            # Correct a signed low relocation with MV-ISA only, before writes.
            positive=self.label('bss_positive')
            self.emit(f'addi t3,zero,%lo({symbol})','slt t4,t3,zero',f'beq t4,zero,{positive}')
            count,remainder=divmod(1<<self.policy.data_address_bits,2047)
            self.emit(*(['addi t3,t3,2047']*count),f'addi t3,t3,{remainder}',positive+':')
        done=self.label('stack_ok')
        self.emit(f'addi t3,t3,{self.policy.stack_guard_margin}','slt t4,sp,t3',f'beq t4,zero,{done}',
                  f'jal zero,{self.policy.stack_guard_trap}',done+':')

    def pop(self,reg='t0'):
        self.emit(f'lw {reg},0(sp)','addi sp,sp,16')

    def lvalue(self,n):
        if n.kind=='id': self.address(n.symbol)
        elif n.kind=='index':
            self.expression(n.children[0]); self.push()
            self.expression(n.children[1]); self.emit('slli a0,a0,2'); self.pop()
            self.emit('add a0,t0,a0')
        else: self.expression(n.children[0])

    def binary(self,op,left=INT,right=INT):
        # left in t0, right in a0. Use t1/t2 only as expression-local scratch.
        self.mark('BIN_'+op)
        if op in ('+','-'):
            if left.pointer and right==INT: self.emit('slli a0,a0,2')
            if op=='+' and left==INT and right.pointer: self.emit('slli t0,t0,2')
            self.emit(f'{"add" if op=="+" else "sub"} a0,t0,a0')
            if op=='-' and left.pointer and right.pointer: self.emit('srai a0,a0,2')
        elif op in ('*','/','%','^','<<','>>'):
            self.choose({'*':'MUL','/':'DIV','%':'REM','^':'XOR','<<':'SHL','>>':'SHR'}[op])
        elif op in ('&','|'): self.emit(f'{"and" if op=="&" else "or"} a0,t0,a0')
        elif op in ('==','!='):
            self.emit('sub a0,t0,a0','sltu a0,zero,a0')
            if op=='==': self.emit('xori a0,a0,1')
        else:
            cmp='sltu' if left.pointer or right.pointer else 'slt'
            if op in ('>','<='): self.emit(f'{cmp} a0,a0,t0')
            else: self.emit(f'{cmp} a0,t0,a0')
            if op in ('<=','>='): self.emit('xori a0,a0,1')

    def expression(self,n):
        self.node=n
        k=n.kind
        if k in ('num','sizeof'): self.const(n.value)
        elif k in ('id','index') or (k=='unary' and n.value=='*'):
            self.lvalue(n)
            if n.type.kind!='array': self.emit('lw a0,0(a0)')
        elif k=='call':
            self.mark('CALL',n.symbol.name)
            for arg in n.children[1:]: self.expression(arg); self.push()
            for index in reversed(range(len(n.children)-1)): self.pop('a'+str(index))
            self.emit(f'jal ra,{n.symbol.name}')
        elif k=='assign':
            a,b=n.children
            self.lvalue(a); self.push()
            if n.value!='=':
                self.emit('lw a0,0(a0)'); self.push()
                self.expression(b); self.pop()
                self.node=n; self.binary(n.value[:-1],a.type,b.type)
            else: self.expression(b)
            self.pop(); self.emit('sw a0,0(t0)')
        elif k=='postfix' or (k=='unary' and n.value in ('++','--')):
            a=n.children[0]; self.lvalue(a)
            step=(4 if a.type.pointer else 1)*(1 if n.value=='++' else -1)
            self.emit('addi t0,a0,0','lw a0,0(t0)',f'addi t1,a0,{step}','sw t1,0(t0)')
            if k=='unary': self.emit('addi a0,t1,0')
        elif k=='unary':
            a=n.children[0]
            if n.value=='&': self.lvalue(a); return
            self.expression(a)
            if n.value=='-': self.emit('sub a0,zero,a0')
            elif n.value=='~': self.emit('xori a0,a0,-1')
            elif n.value=='!': self.emit('sltu a0,zero,a0','xori a0,a0,1')
        elif k=='binary':
            a,b=n.children
            if n.value in ('&&','||'):
                short,done=self.label('short'),self.label('boolend')
                self.expression(a)
                if n.value=='&&': self.emit(f'beq a0,zero,{short}')
                else:
                    proceed=self.label('rhs')
                    self.emit(f'beq a0,zero,{proceed}',f'jal zero,{short}',proceed+':')
                self.expression(b); self.emit('sltu a0,zero,a0',f'jal zero,{done}',short+':')
                self.const(0 if n.value=='&&' else 1); self.emit(done+':')
            else:
                self.expression(a); self.push(); self.expression(b); self.pop()
                self.node=n; self.binary(n.value,a.type,b.type)

    def statement(self,n):
        self.node=n
        self.mark(n.kind.upper())
        if n.kind=='block':
            for child in n.children: self.statement(child)
        elif n.kind=='decl':
            if n.children:
                for index,child in enumerate(n.children):
                    self.address(n.symbol); self.const(index*4,'t0'); self.emit('add a0,a0,t0'); self.push()
                    self.expression(child); self.pop(); self.emit('sw a0,0(t0)')
                if n.type.kind=='array':
                    for index in range(len(n.children),n.type.length):
                        self.address(n.symbol); self.const(index*4,'t0'); self.emit('add t0,a0,t0','sw zero,0(t0)')
        elif n.kind=='expr': self.expression(n.children[0])
        elif n.kind=='return':
            if n.children: self.expression(n.children[0])
            self.emit(f'jal zero,{self.epilogue}')
        elif n.kind in ('break','continue'):
            self.emit(f'jal zero,{self.loops[-1][0 if n.kind=="break" else 1]}')
        elif n.kind=='if':
            no,done=self.label('else'),self.label('ifend')
            self.expression(n.children[0]); self.emit(f'beq a0,zero,{no}')
            self.statement(n.children[1]); self.emit(f'jal zero,{done}',no+':')
            if len(n.children)==3: self.statement(n.children[2])
            self.emit(done+':')
        elif n.kind in ('while','for'):
            start,step,end=self.label('loop'),self.label('step'),self.label('end')
            if n.kind=='for':
                init,cond,inc,body=n.children
                self.statement(init) if init.kind=='decl' else self.expression(init)
            else: cond,body=n.children
            self.emit(start+':'); self.expression(cond); self.emit(f'beq a0,zero,{end}')
            self.loops.append((end,step)); self.statement(body); self.loops.pop()
            self.emit(step+':')
            if n.kind=='for': self.expression(inc)
            self.emit(f'jal zero,{start}',end+':')

    def generate(self,prog):
        self.emit(f'# mycc-target: {self.target}')
        for n in prog.children:
            if n.kind!='decl': continue
            values=n.symbol.initial or []
            if self.policy.globals_in_bss:
                self.emit('.section .bss','.balign 4',f'.globl {n.symbol.name}',n.symbol.name+':',f'.zero {n.type.size}')
                self.global_initializers.extend((n.symbol,index*4,value) for index,value in enumerate(values) if value)
                continue
            self.emit('.section .data' if values else '.section .bss','.balign 4',f'.globl {n.symbol.name}',n.symbol.name+':')
            for value in values: self.emit(f'.word {value}')
            remainder=n.type.size-4*len(values)
            if remainder: self.emit(f'.zero {remainder}')
        self.emit('.section .text')
        if self.policy.initializer and not self.library:
            self.emit(f'.globl {self.policy.initializer}',self.policy.initializer+':')
            for symbol,offset,value in self.global_initializers:
                self.address(symbol,'t0'); self.const(offset,'t1'); self.emit('add t0,t0,t1')
                self.const(value); self.emit('sw a0,0(t0)')
            self.emit('jalr zero,0(ra)')
        for n in prog.children:
            if n.kind!='func': continue
            used=8
            for sym in n.value['locals']:
                used+=sym.type.size; sym.offset=-used
            frame=(used+15)&~15
            self.epilogue=self.label('return')
            self.emit('.balign 4',f'.globl {n.symbol.name}',f'.type {n.symbol.name},@function',n.symbol.name+':',
                      'addi t0,s0,0','addi t1,sp,0')
            self.const(-frame,'t2'); self.emit('add sp,sp,t2')
            self.stack_check()
            self.emit('addi s0,t1,0','sw ra,-4(s0)','sw t0,-8(s0)')
            for i,p in enumerate(n.children[:-1]):
                self.address(p.symbol,'t0'); self.emit(f'sw a{i},0(t0)')
            self.statement(n.children[-1]); self.const(0)
            self.emit(self.epilogue+':','lw ra,-4(s0)','lw t0,-8(s0)','addi sp,s0,0','addi s0,t0,0','jalr zero,0(ra)',f'.size {n.symbol.name},.-{n.symbol.name}')
        return '\n'.join(self.lines)+'\n'


def generate(prog,profile,options=None):
    generator=Generator(profile,options)
    asm=lower_assembly(generator.generate(prog),profile)
    ir=''.join(f'{i}\t{op}\t'+ '\t'.join(map(str,args))+'\n' for i,(op,args) in enumerate(generator.ir))
    return asm,generator.lowering,ir


# Minimal-ISA fallback library. Every instruction below belongs to MV-ISA.
# Functions clobber only caller-saved registers and preserve sp/s0.
MINIMAL_HELPERS = '''
.section .text
__mv_sltu:
    slt t0,a0,zero
    slt t1,a1,zero
    beq t0,t1,.Lmv_ucmp_same
    addi a0,t1,0
    jalr zero,0(ra)
.Lmv_ucmp_same:
    slt a0,a0,a1
    jalr zero,0(ra)
__mv_and:
    addi t5,zero,0
    jal zero,.Lmv_bitop
__mv_or:
    addi t5,zero,1
    jal zero,.Lmv_bitop
__mv_xor:
    addi t5,zero,2
.Lmv_bitop:
    addi t0,zero,32
    addi t1,zero,0
.Lmv_bit_loop:
    slt t2,a0,zero
    slt t3,a1,zero
    add t1,t1,t1
    beq t5,zero,.Lmv_bit_and
    addi t4,zero,1
    beq t5,t4,.Lmv_bit_or
    beq t2,t3,.Lmv_bit_next
    jal zero,.Lmv_bit_one
.Lmv_bit_and:
    beq t2,zero,.Lmv_bit_next
    beq t3,zero,.Lmv_bit_next
    jal zero,.Lmv_bit_one
.Lmv_bit_or:
    beq t2,t3,.Lmv_bit_equal
    jal zero,.Lmv_bit_one
.Lmv_bit_equal:
    beq t2,zero,.Lmv_bit_next
.Lmv_bit_one:
    addi t1,t1,1
.Lmv_bit_next:
    add a0,a0,a0
    add a1,a1,a1
    addi t0,t0,-1
    beq t0,zero,.Lmv_bit_done
    jal zero,.Lmv_bit_loop
.Lmv_bit_done:
    addi a0,t1,0
    jalr zero,0(ra)
__mv_sll:
    addi t6,zero,0
    jal zero,.Lmv_shift
__mv_srl:
    addi t6,zero,1
    jal zero,.Lmv_shift
__mv_sra:
    addi t6,zero,2
.Lmv_shift:
    addi t0,zero,0
    addi t1,zero,32
    addi t4,zero,5
.Lmv_count_loop:
    slt t2,a1,zero
    slt t3,t4,t1
    beq t3,zero,.Lmv_count_bit
    jal zero,.Lmv_count_next
.Lmv_count_bit:
    add t0,t0,t0
    add t0,t0,t2
.Lmv_count_next:
    add a1,a1,a1
    addi t1,t1,-1
    beq t1,zero,.Lmv_shift_loop
    jal zero,.Lmv_count_loop
.Lmv_shift_loop:
    beq t0,zero,.Lmv_shift_done
    beq t6,zero,.Lmv_shift_left
    slt t4,a0,zero
    addi t1,zero,31
    addi t2,zero,0
.Lmv_right_one:
    slt t3,a0,zero
    add t2,t2,t2
    add t2,t2,t3
    add a0,a0,a0
    addi t1,t1,-1
    beq t1,zero,.Lmv_right_sign
    jal zero,.Lmv_right_one
.Lmv_right_sign:
    addi a0,t2,0
    addi t1,zero,2
    beq t6,t1,.Lmv_arithmetic
    jal zero,.Lmv_shift_next
.Lmv_arithmetic:
    beq t4,zero,.Lmv_shift_next
    addi t1,zero,1
    addi t2,zero,31
.Lmv_sign_constant:
    add t1,t1,t1
    addi t2,t2,-1
    beq t2,zero,.Lmv_sign_add
    jal zero,.Lmv_sign_constant
.Lmv_sign_add:
    add a0,a0,t1
    jal zero,.Lmv_shift_next
.Lmv_shift_left:
    add a0,a0,a0
.Lmv_shift_next:
    addi t0,t0,-1
    jal zero,.Lmv_shift_loop
.Lmv_shift_done:
    jalr zero,0(ra)
__mv_sb:
    addi sp,sp,-32
    sw ra,28(sp)
    sw a0,0(sp)
    sw a1,4(sp)
    addi a1,zero,-4
    jal ra,__mv_and
    sw a0,8(sp)
    lw a0,0(sp)
    addi a1,zero,3
    jal ra,__mv_and
    add a0,a0,a0
    add a0,a0,a0
    add a0,a0,a0
    sw a0,12(sp)
    addi a1,a0,0
    addi a0,zero,255
    jal ra,__mv_sll
    addi t0,zero,-1
    sub a1,t0,a0
    lw t0,8(sp)
    lw a0,0(t0)
    jal ra,__mv_and
    sw a0,20(sp)
    lw a0,4(sp)
    addi a1,zero,255
    jal ra,__mv_and
    lw a1,12(sp)
    jal ra,__mv_sll
    lw a1,20(sp)
    jal ra,__mv_or
    lw t0,8(sp)
    sw a0,0(t0)
    lw ra,28(sp)
    addi sp,sp,32
    jalr zero,0(ra)
'''


def lower_assembly(text,profile,include_helpers=True):
    """Expand missing baseline instructions using MV-ISA only.

    Saving caller-saved registers makes this instruction-local transformation
    valid both for generated expressions and handwritten runtime assembly.
    """
    import re
    regs=['ra','t0','t1','t2','t3','t4','t5','t6',*[f'a{i}' for i in range(8)]]
    slots={reg:i*4 for i,reg in enumerate(regs)}
    slots['zero']=None
    out=[]; needed=False
    binary={'and':'and','or':'or','xor':'xor','sltu':'sltu','sll':'sll','srl':'srl','sra':'sra'}
    immediate={'andi':'and','ori':'or','xori':'xor','slti':'slt','sltiu':'sltu','slli':'sll','srli':'srl','srai':'sra'}
    for line in text.splitlines():
        stripped=line.strip()
        match=re.match(r'([a-z]+)\s+([^#]+)',stripped)
        if not match or profile.has(match[1]): out.append(line); continue
        op=match[1]; operands=[x.strip() for x in match[2].strip().split(',')]
        if op not in binary and op not in immediate and op!='sb':
            out.append(line); continue
        if op=='sb':
            value,address=operands
            offset,base=re.fullmatch(r'(-?\d+)\((\w+)\)',address).groups()
            rd,rs,arg='zero',base,value
        else: rd,rs,arg=operands
        out.append('addi sp,sp,-64')
        out.extend(f'sw {r},{offset}(sp)' for r,offset in slots.items() if offset is not None)
        def saved(reg,dest):
            if reg=='zero': return f'addi {dest},zero,0'
            if reg=='sp': return f'addi {dest},sp,64'
            if reg=='s0': return f'addi {dest},s0,0'
            return f'lw {dest},{slots[reg]}(sp)'
        out.append(saved(rs,'a0'))
        out.append(f'addi a1,zero,{arg}' if op in immediate else saved(arg,'a1'))
        if op=='sb' and int(offset): out.append(f'addi a0,a0,{offset}')
        operation='sb' if op=='sb' else immediate.get(op,binary.get(op))
        if operation=='slt': out.append('slt a0,a0,a1')
        else: out.append(f'jal ra,__mv_{operation}'); needed=True
        if rd!='zero': out.append(f'sw a0,{slots[rd]}(sp)')
        out.extend(f'lw {r},{offset}(sp)' for r,offset in slots.items() if offset is not None)
        out.append('addi sp,sp,64')
    if needed and include_helpers:
        # Localize helper labels per object to avoid duplicate global definitions.
        out.append(MINIMAL_HELPERS)
    return '\n'.join(out)+'\n'
