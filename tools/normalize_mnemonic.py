"""Normalize disassembler aliases on the input side, never in the whitelist."""
ALIASES={'nop':'addi','li':'addi','mv':'addi','ret':'jalr','jr':'jalr','j':'jal',
         'call':'jal','neg':'sub','not':'xori','seqz':'sltiu','snez':'sltu',
         'sltz':'slt','sgtz':'slt','beqz':'beq','bnez':'bne','bltz':'blt','bgez':'bge',
         'blez':'bge','bgtz':'blt','ble':'bge','bgt':'blt','bleu':'bgeu','bgtu':'bltu'}


def normalize(mnemonic): return ALIASES.get(mnemonic,mnemonic)
