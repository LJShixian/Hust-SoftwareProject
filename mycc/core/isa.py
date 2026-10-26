"""Single source of ISA capabilities; no file I/O."""
from dataclasses import dataclass
import difflib
import hashlib
import json
import re
from .types import ProfileError

MV_ISA = frozenset('add sub addi lw sw beq jal jalr slt'.split())
BASE = MV_ISA | frozenset('and or sltu sll srl sra andi ori xori slti slli srli srai lui sb bne blt'.split())
GROUPS = { 'mul': {'mul'}, 'divrem': {'div','rem'}, 'xor': {'xor'},
           'cmpbr': {'bge','bgeu','bltu','sltiu'}, 'byteload': {'lb','lbu','lh','lhu'},
           'auipc': {'auipc'}, 'lui': {'lui'}, 'vshift': {'sll','srl','sra'},
           'm': {'mul','div','rem'} }
for i,name in enumerate(['mul','divrem','xor','cmpbr','byteload','auipc'],1): GROUPS[f'EX-{i:02}']=GROUPS[name]
ALL = BASE | frozenset().union(*GROUPS.values())
PRESETS = {
    'base': BASE, 'base-nolui': BASE-{'lui'}, 'base-novshift': BASE-GROUPS['vshift'],
    'full-i': BASE|GROUPS['xor']|GROUPS['cmpbr']|GROUPS['auipc'],
    'i+m': BASE|GROUPS['m'], 'byteload': BASE|GROUPS['byteload'], 'all': ALL,
}
ALIASES = {f'PF-{i:02}': name for i,name in enumerate(PRESETS,1)}
# A reference instruction set is data only; selecting it does not select a board ABI.
PRESETS['cpu21'] = BASE | GROUPS['mul'] | GROUPS['xor'] | GROUPS['cmpbr']


@dataclass(frozen=True)
class ISAProfile:
    name: str
    instructions: frozenset
    baseline_name: str = 'base'

    def has(self,mnemonic): return mnemonic in self.instructions

    @property
    def fingerprint(self):
        return hashlib.sha256('\n'.join(sorted(self.instructions)).encode()).hexdigest()

    @property
    def groups(self):
        return frozenset(k for k,v in GROUPS.items() if not k.startswith('EX-') and v <= self.instructions)


def expand(items):
    result=set()
    for raw in items:
        for item in raw.split(','):
            item=item.strip()
            if not item: continue
            if item in GROUPS: result.update(GROUPS[item])
            elif item in ALL: result.add(item)
            else:
                near=difflib.get_close_matches(item,list(ALL|GROUPS.keys()),n=1)
                raise ProfileError(f"unknown instruction/group '{item}'; suggestion: {', '.join(near) or '--profile PF-01'}")
    return result


def load_profile(name='PF-01',enable=(),disable=(),data=None):
    baseline=ALIASES.get(name,name)
    if data is not None:
        if not isinstance(data,dict): raise ProfileError('profile must be a JSON object')
        extra=set(data)-{'name','description','schema_version','instructions'}
        if extra: raise ProfileError('unknown profile fields: '+', '.join(sorted(extra)))
        if type(data.get('schema_version')) is not int or data['schema_version'] != 1: raise ProfileError('schema_version must be 1')
        baseline=data.get('name','')
        if not isinstance(baseline,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',baseline): raise ProfileError('invalid profile name')
        if baseline in PRESETS or baseline in ALIASES: raise ProfileError('custom name conflicts with a built-in profile')
        if not isinstance(data.get('description',''),str) or len(data.get('description',''))>200: raise ProfileError('description must be a string of at most 200 characters')
        ins=data.get('instructions')
        if not isinstance(ins,list) or not all(isinstance(x,str) for x in ins): raise ProfileError('instructions must be a string array')
        if len(ins)!=len(set(ins)): raise ProfileError('duplicate instructions in profile')
        unknown=set(ins)-ALL
        if unknown: raise ProfileError('unknown instructions: '+', '.join(sorted(unknown))+'; check --dump-isa')
        instructions=set(ins)
        if not MV_ISA <= instructions: raise ProfileError('missing required instructions: '+', '.join(sorted(MV_ISA-instructions)))
    else:
        if baseline not in PRESETS: raise ProfileError(f"unknown profile '{name}'; choose PF-01..PF-07",64)
        instructions=set(PRESETS[baseline])
    instructions.update(expand(enable)); instructions.difference_update(expand(disable))
    profile=ISAProfile(baseline,frozenset(instructions),baseline)
    check_feasible(profile)
    return profile


def check_feasible(profile):
    missing=MV_ISA-profile.instructions
    if missing: raise ProfileError('missing required instructions: '+', '.join(sorted(missing))+'; use --profile PF-01',64,'E-PROFILE-MISSING-MVISA')


def dump_isa_whitelist(profile): return '\n'.join(sorted(profile.instructions))+'\n'


def dump_isa(profile):
    disabled=ALL-profile.instructions
    return (f'profile: {profile.name}\ninstructions: {len(profile.instructions)}\nfingerprint: {profile.fingerprint}\n'
            +'enabled: '+', '.join(sorted(profile.instructions))+'\ngroups: '+', '.join(sorted(profile.groups))
            +'\ndisabled: '+', '.join(sorted(disabled))
            +'\nalternatives: mul/div/rem -> software helpers; xor -> or/and/sub; lui -> byte synthesis; vshift -> helpers\n')
