"""Audit decoded ELF instructions against the selected compiler profile."""
import argparse
import re
import subprocess
import sys
from mycc.cli import profile_from_args
from .build import tool,profile_args
from .normalize_mnemonic import normalize


def lint(elf,profile,qemu=False,target='generic'):
    from mycc.core import check_target
    check_target(profile,target)
    text=subprocess.check_output([tool('objdump'),'-d','-M','no-aliases',str(elf)],text=True,timeout=30)
    allowed=set(profile.instructions)
    function=''; errors=[]
    for line in text.splitlines():
        label=re.match(r'^[0-9a-f]+ <([^>]+)>:',line)
        if label: function=label.group(1)
        inst=re.match(r'^\s*([0-9a-f]+):\s+[0-9a-f]+\s+(\S+)',line)
        if not inst: continue
        address,mnemonic=inst.groups(); mnemonic=normalize(mnemonic)
        # gas emits $d mapping symbols for inline address literals. objdump -d
        # prints these as data directives, not decoded CPU instructions.
        if mnemonic in ('.word','.4byte','.2byte','.byte'): continue
        # Linux syscalls are restricted to the explicit test shim entry points.
        if qemu and mnemonic=='ecall' and function in ('putchar','exit'): continue
        if target=='cpu21' and mnemonic=='csrrci' and function=='_start': continue
        if mnemonic not in allowed:
            errors.append(f"lint: ERROR: '{mnemonic}' at 0x{address} ({function}) is not in profile '{profile.name}'")
    return errors


def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('elf'); p.add_argument('--qemu',action='store_true'); profile_args(p)
    a=p.parse_args(argv)
    if a.qemu: a.target='generic'
    try: errors=lint(a.elf,profile_from_args(a),a.qemu,a.target)
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as exc:
        print('lint: '+str(exc),file=sys.stderr); return 1
    for error in errors: print(error,file=sys.stderr)
    if not errors: print('lint: ok')
    return int(bool(errors))


if __name__=='__main__': raise SystemExit(main())
