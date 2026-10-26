"""Verified CPU21 facts; kept outside the compiler."""
from dataclasses import dataclass
from mycc.core.isa import PRESETS

CPU21_INSTRUCTIONS = PRESETS["cpu21"]

@dataclass(frozen=True)
class CPU21Board:
    led: int = 0x1000
    seg: int = 0x1004
    vga_base: int = 0x2000
    display_ctrl: int = 0x1140
    display_cursor: int = 0x1144
    mouse_ctrl: int = 0x110c

    def as_dict(self):
        return {name:getattr(self,name) for name in self.__dataclass_fields__}

    @classmethod
    def from_mapping(cls,data):
        if not isinstance(data,dict) or set(data)!=set(cls.__dataclass_fields__):
            raise ValueError('CPU21 MMIO requires led, seg, vga_base, display_ctrl, display_cursor, mouse_ctrl; UART is unavailable')
        values={}
        for name,raw in data.items():
            try: value=int(str(raw),0)
            except (ValueError,TypeError): raise ValueError(f'{name}: enter a hexadecimal or decimal address')
            if value%4 or not 0x1000<=value<0x8000:
                raise ValueError(f'{name}: CPU21 MMIO must be aligned and within 0x1000..0x7FFC')
            values[name]=value
        if values['vga_base']+2400>0x8000:
            raise ValueError('VGA buffer exceeds the CPU21 low-address MMIO range')
        if len(set(values.values()))!=len(values):
            raise ValueError('CPU21 MMIO registers must have distinct addresses')
        if any(values['vga_base']<=value<values['vga_base']+2400 for name,value in values.items() if name!='vga_base'):
            raise ValueError('CPU21 control registers overlap the VGA framebuffer')
        return cls(**values)
