"""MMIO configuration for the optional generic bare-metal example."""
from dataclasses import dataclass

@dataclass(frozen=True)
class BoardAddresses:
    uart_tx: int = 0x10000000
    vga_base: int = 0x20000000
    exit_status: int = 0x10000004

    @classmethod
    def from_mapping(cls,data):
        keys={'uart_tx','vga_base','exit_status'}
        if not isinstance(data,dict) or set(data)!=keys:
            raise ValueError('MMIO configuration requires uart_tx, vga_base, exit_status')
        values={}
        for key,value in data.items():
            try: value=int(str(value),0)
            except (TypeError,ValueError): raise ValueError(f'{key}: enter a hexadecimal 0x... or decimal address')
            if not 0<=value<=0xfffffffc or value%4:
                raise ValueError(f'{key}: address must be 32-bit and 4-byte aligned')
            values[key]=value
        return cls(**values)

    def as_dict(self):
        return {'uart_tx':self.uart_tx,'vga_base':self.vga_base,'exit_status':self.exit_status}
