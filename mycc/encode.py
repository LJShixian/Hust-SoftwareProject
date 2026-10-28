"""Encode the single-file RARS listing into words a Logisim ROM/RAM can load.

``mycc --rars`` produces one self-contained listing whose language is small and
fully controlled by this project: twenty RV32I mnemonics plus ``ecall``, and the
directives ``.text .data .globl .align .word .space``. Encoding that subset here
means the hardware demo needs no Java, no RARS and no GNU toolchain: a C file
becomes a loadable image in one command.

The input is the *post-rewrite* listing, so ``.align n`` means ``2**n`` bytes as
RARS defines it, not GNU's ``n`` bytes. Text and data are laid out in separate
address spaces starting at zero, matching a Harvard machine whose ROM holds code
and whose RAM holds data.
"""
import re

ABI = {name: number for number, name in enumerate(
    'zero ra sp gp tp t0 t1 t2 s0 s1 a0 a1 a2 a3 a4 a5 a6 a7 '
    's2 s3 s4 s5 s6 s7 s8 s9 s10 s11 t3 t4 t5 t6'.split())}
ABI['fp'] = 8
for _index in range(32):
    ABI[f'x{_index}'] = _index

R_OPS = {'add': (0x00, 0x0), 'sub': (0x20, 0x0), 'sll': (0x00, 0x1), 'slt': (0x00, 0x2),
         'sltu': (0x00, 0x3), 'xor': (0x00, 0x4), 'srl': (0x00, 0x5), 'sra': (0x20, 0x5),
         'or': (0x00, 0x6), 'and': (0x00, 0x7),
         # RV32M shares opcode 0x33 with funct7 = 0x01.
         'mul': (0x01, 0x0), 'mulh': (0x01, 0x1), 'mulhsu': (0x01, 0x2), 'mulhu': (0x01, 0x3),
         'div': (0x01, 0x4), 'divu': (0x01, 0x5), 'rem': (0x01, 0x6), 'remu': (0x01, 0x7)}
I_ARITH = {'addi': 0x0, 'slti': 0x2, 'sltiu': 0x3, 'xori': 0x4, 'ori': 0x6, 'andi': 0x7}
I_SHIFT = {'slli': (0x1, 0x00), 'srli': (0x5, 0x00), 'srai': (0x5, 0x20)}
LOADS = {'lb': 0x0, 'lh': 0x1, 'lw': 0x2, 'lbu': 0x4, 'lhu': 0x5}
STORES = {'sb': 0x0, 'sh': 0x1, 'sw': 0x2}
BRANCHES = {'beq': 0x0, 'bne': 0x1, 'blt': 0x4, 'bge': 0x5, 'bltu': 0x6, 'bgeu': 0x7}
FIXED = {'ecall': 0x00000073, 'ebreak': 0x00100073, 'mret': 0x30200073, 'uret': 0x00200073}

LABEL = re.compile(r'^([A-Za-z_.$][\w.$]*):\s*(.*)$')
NUMBER = re.compile(r'^-?(?:0[xX][0-9a-fA-F]+|\d+)$')
RELOC = re.compile(r'^%(hi|lo)\(\s*([A-Za-z_.$][\w.$]*)\s*\)$')


class AssembleError(Exception):
    """A listing line this encoder cannot encode, with its source line number."""


def _value(token, symbols, where):
    token = token.strip()
    if NUMBER.match(token):
        return int(token, 0)
    if token in symbols:
        return symbols[token]
    match = RELOC.match(token)
    if match:
        kind, name = match.group(1), match.group(2)
        if name not in symbols:
            raise AssembleError(f'{where}: unknown symbol {name!r} in {token}')
        address = symbols[name]
        high = ((address + 0x800) >> 12) & 0xFFFFF
        if kind == 'hi':
            return high
        # lo12 is addr - (hi20 << 12): the pair must sum back to the address, not
        # wrap to the biased 0x800 window that hi20 rounds through.
        return address - (high << 12)
    raise AssembleError(f'{where}: unknown symbol or literal {token!r}')


def _register(token, where):
    name = token.strip()
    if name not in ABI:
        raise AssembleError(f'{where}: unknown register {name!r}')
    return ABI[name]


def _imm(token, symbols, where):
    value = _value(token, symbols, where)
    if not -2048 <= value <= 2047:
        raise AssembleError(f'{where}: immediate {value} does not fit in 12 signed bits')
    return value


def encode_instruction(mnemonic, operands, pc, symbols, where):
    """Return one 32-bit word for a single instruction at byte address `pc`."""
    if mnemonic in FIXED:
        if operands:
            raise AssembleError(f'{where}: {mnemonic} takes no operands')
        return FIXED[mnemonic]
    if mnemonic in R_OPS:
        funct7, funct3 = R_OPS[mnemonic]
        rd, rs1, rs2 = (_register(x, where) for x in _split(operands, 3, where))
        return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0x33
    if mnemonic in I_ARITH:
        rd, rs1, imm = _split(operands, 3, where)
        return (_imm(imm, symbols, where) & 0xFFF) << 20 \
            | _register(rs1, where) << 15 | I_ARITH[mnemonic] << 12 | _register(rd, where) << 7 | 0x13
    if mnemonic in I_SHIFT:
        funct3, funct7 = I_SHIFT[mnemonic]
        rd, rs1, imm = _split(operands, 3, where)
        amount = _value(imm, symbols, where)
        if not 0 <= amount <= 31:
            raise AssembleError(f'{where}: shift amount {amount} outside 0..31')
        return (funct7 << 25) | (amount << 20) | (_register(rs1, where) << 15) \
            | (funct3 << 12) | (_register(rd, where) << 7) | 0x13
    if mnemonic in LOADS:
        rd, address = _split(operands, 2, where)
        offset, base = _offset_base(address, symbols, where)
        return (offset & 0xFFF) << 20 | _register(base, where) << 15 \
            | LOADS[mnemonic] << 12 | _register(rd, where) << 7 | 0x03
    if mnemonic in STORES:
        source, address = _split(operands, 2, where)
        offset, base = _offset_base(address, symbols, where)
        low, high = offset & 0xFFF, (offset & 0xFFF) >> 5
        return (high << 25) | (_register(source, where) << 20) | (_register(base, where) << 15) \
            | (STORES[mnemonic] << 12) | (low & 0x1F) << 7 | 0x23
    if mnemonic in BRANCHES:
        rs1, rs2, label = _split(operands, 3, where)
        delta = _value(label, symbols, where) - pc
        if delta % 2 or not -4096 <= delta <= 4094:
            raise AssembleError(f'{where}: branch target {delta} bytes is out of range')
        offset = delta & 0x1FFF
        return (((offset >> 12) & 1) << 31) | (((offset >> 5) & 0x3F) << 25) \
            | (_register(rs2, where) << 20) | (_register(rs1, where) << 15) \
            | (BRANCHES[mnemonic] << 12) | (((offset >> 1) & 0xF) << 8) \
            | (((offset >> 11) & 1) << 7) | 0x63
    if mnemonic == 'jal':
        rd, label = _split(operands, 2, where)
        delta = _value(label, symbols, where) - pc
        if delta % 2 or not -(1 << 20) <= delta <= (1 << 20) - 2:
            raise AssembleError(f'{where}: jump target {delta} bytes is out of range')
        offset = delta & 0x1FFFFF
        return (((offset >> 20) & 1) << 31) | (((offset >> 1) & 0x3FF) << 21) \
            | (((offset >> 11) & 1) << 20) | (((offset >> 12) & 0xFF) << 12) \
            | (_register(rd, where) << 7) | 0x6F
    if mnemonic == 'jalr':
        rd, address = _split(operands, 2, where)
        offset, base = _offset_base(address, symbols, where)
        return (offset & 0xFFF) << 20 | _register(base, where) << 15 \
            | _register(rd, where) << 7 | 0x67
    if mnemonic in ('lui', 'auipc'):
        rd, imm = _split(operands, 2, where)
        value = _value(imm, symbols, where) & 0xFFFFF
        return (value << 12) | (_register(rd, where) << 7) | (0x37 if mnemonic == 'lui' else 0x17)
    raise AssembleError(f'{where}: unsupported mnemonic {mnemonic!r}')


def _split(operands, count, where):
    parts = [x.strip() for x in operands.split(',')]
    if len(parts) != count:
        raise AssembleError(f'{where}: expected {count} operands, got {len(parts)}')
    return parts


def _offset_base(token, symbols, where):
    match = re.fullmatch(r'(-?(?:0[xX][0-9a-fA-F]+|\d+))?\s*\(\s*([A-Za-z_.$][\w.$]*|\w+)\s*\)', token.strip())
    if not match:
        raise AssembleError(f'{where}: expected offset(register), got {token!r}')
    offset = int(match.group(1), 0) if match.group(1) else 0
    if not -2048 <= offset <= 2047:
        raise AssembleError(f'{where}: offset {offset} does not fit in 12 signed bits')
    return offset, match.group(2)


def _parse(text):
    """Split a listing into (section, line-number, label, mnemonic, operands) records."""
    records = []
    section = 'text'
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split('#')[0].strip()
        if not line:
            continue
        label = None
        match = LABEL.match(line)
        if match:
            label, line = match.group(1), match.group(2).strip()
            if label in ABI:
                raise AssembleError(f'line {number}: label {label!r} shadows a register name')
            if not line:
                records.append((section, number, label, None, None))
                continue
        if line.startswith('.'):
            parts = line.split(None, 1)
            name = parts[0]
            argument = parts[1].strip() if len(parts) > 1 else ''
            if name in ('.text', '.section'):
                if name == '.section' and argument and argument.lstrip('.') not in ('text', 'data'):
                    raise AssembleError(f'line {number}: unexpected section {argument!r}')
                section = 'data' if argument.lstrip('.') == 'data' else 'text'
                records.append((section, number, label, None, None))
                continue
            if name == '.data':
                section = 'data'
                records.append((section, number, label, None, None))
                continue
            records.append((section, number, label, name, argument))
            continue
        parts = line.split(None, 1)
        records.append((section, number, label, parts[0], parts[1].strip() if len(parts) > 1 else ''))
    return records


def assemble(text):
    """Encode a listing. Returns (text_words, data_words, symbols)."""
    records = _parse(text)
    symbols = {}
    text_pc = 0
    data_pc = 0
    for section, number, label, mnemonic, argument in records:
        if label:
            if label in symbols:
                raise AssembleError(f'line {number}: duplicate label {label!r}')
            symbols[label] = text_pc if section == 'text' else data_pc
        if mnemonic is None:
            continue
        where = f'line {number}'
        if mnemonic == '.globl':
            continue
        if mnemonic == '.align':
            align = 1 << int(argument, 0)
            if section == 'text':
                text_pc = (text_pc + align - 1) // align * align
            else:
                data_pc = (data_pc + align - 1) // align * align
            continue
        if mnemonic == '.word':
            data_pc += 4 * len([x for x in argument.split(',') if x.strip()])
            continue
        if mnemonic == '.space':
            data_pc += int(argument, 0)
            continue
        if section != 'text':
            raise AssembleError(f'{where}: instruction {mnemonic!r} inside a data section')
        text_pc += 4
    text_words = []
    data_words = []
    text_pc = 0
    data_pc = 0
    for section, number, label, mnemonic, argument in records:
        if mnemonic is None or mnemonic == '.globl':
            continue
        where = f'line {number}'
        if mnemonic == '.align':
            align = 1 << int(argument, 0)
            if section == 'text':
                while text_pc % align:
                    text_words.append(0)
                    text_pc += 4
            else:
                while data_pc % align:
                    data_words.append(0)
                    data_pc += 4
            continue
        if mnemonic == '.word':
            for token in argument.split(','):
                if not token.strip():
                    continue
                data_words.append(_value(token, symbols, where) & 0xFFFFFFFF)
                data_pc += 4
            continue
        if mnemonic == '.space':
            size = int(argument, 0)
            while size > 0:
                data_words.append(0)
                data_pc += 4
                size -= 4
            continue
        text_words.append(encode_instruction(mnemonic, argument, text_pc, symbols, where))
        text_pc += 4
    return text_words, data_words, symbols


def hex_image(words):
    """Logisim `v2.0 raw`: one 32-bit word per line, the format the course ROM uses."""
    return 'v2.0 raw\n' + ''.join(f'{word & 0xFFFFFFFF:08x}\n' for word in words)
