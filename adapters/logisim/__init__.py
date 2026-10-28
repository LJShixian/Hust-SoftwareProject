"""Optional hardware-course Logisim CPU: Harvard ROM/RAM, no MMIO, no linker.

The course CPU has a 1024-word instruction ROM and a 1024-byte data RAM, both
addressed from zero, and every instruction in the Logisim profile. Because there
is no linker, the compiler may only reference a global through a *bounded* data
address: the PC-literal pool it would otherwise use needs a readable text segment,
which a Harvard ROM is not.

`data_address_bits=10` therefore selects the relocation-only address strategy:
``%lo(symbol)`` masked to the RAM width. That keeps every generated address
inside 0..1023 without `lui`, without ROM loads, and without a linker.
"""
from mycc import core
from mycc.core.types import CodegenPolicy

POLICY = CodegenPolicy(name='logisim', data_address_bits=10)


DECODED = core.PRESETS['logisim']


def validate_profile(profile):
    missing = profile.instructions - DECODED
    if missing:
        raise core.ProfileError(
            'Logisim CPU does not decode: ' + ', '.join(sorted(missing))
            + '; use --profile logisim', 64, 'E-TARGET-ISA')


def options(**kwargs):
    return core.CompileOptions(target='logisim', policy=POLICY, **kwargs)


def compile(src, profile=None, **kwargs):
    profile = profile or core.load_profile('logisim')
    validate_profile(profile)
    return core.compile(src, profile, options=options(**kwargs))
