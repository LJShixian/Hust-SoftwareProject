"""CPU21-specific startup rendering and ROM packing."""
import re
from mycc.cli import atomic_write


def render_startup(text,profile,addresses):
    if profile.has('lui'): return text
    def address_without_lui(match):
        reg,symbol=match[1],match[2]
        if symbol in ('__bss_start','__bss_end'):
            return f'addi {reg},zero,%lo({symbol})\nslli {reg},{reg},20\nsrli {reg},{reg},20'
        value=4096 if symbol=='__stack_top' else addresses[symbol[2:]]
        count,remainder=divmod(value,2047)
        return '\n'.join([f'addi {reg},zero,{remainder}']+[f'addi {reg},{reg},2047']*count)
    return re.sub(r'lui (\w+),%hi\((\w+)\)\s*\n\s*addi \1,\1,%lo\(\2\)',address_without_lui,text)


def export_rom(blob,out):
    """CPU21 ROM: 8192 little-endian 32-bit words, plus a local include file."""
    if len(blob)>32768: raise RuntimeError('CPU21 ROM exceeds 32 KiB')
    blob+=b'\x00'*(-len(blob)%4)
    words=[int.from_bytes(blob[i:i+4],'little') for i in range(0,len(blob),4)]
    words += [0x13]*(8192-len(words))
    atomic_write(out.with_suffix('.hex'),''.join(f'{word:08x}\n' for word in words))
    atomic_write(out.with_suffix('.logisim.hex'),'v2.0 raw\n'+' '.join(f'{word:08x}' for word in words)+'\n')
    atomic_write(out.with_suffix('.vh'),'// CPU21 ROM include, generated locally; never written into FPGA project.\n'+
                 ''.join(f"rom[{i}] = 32'h{word:08x};\n" for i,word in enumerate(words)))
