"""Executable architecture constraints: dependencies, DAG, and GUI separation."""
import ast
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def check():
    errors=[]; graph={}
    for path in (ROOT/'mycc').rglob('*.py'):
        rel=path.relative_to(ROOT/'mycc'); tree=ast.parse(path.read_text(encoding='utf-8'))
        is_core=rel.parts[0]=='core'; is_cli=path.name=='cli.py'
        for node in ast.walk(tree):
            names=[]
            if isinstance(node,ast.Import): names=[n.name for n in node.names]
            elif isinstance(node,ast.ImportFrom): names=[node.module or '']
            for name in names:
                top=name.split('.')[0]
                if (is_core or is_cli) and top=='PySide6': errors.append(f'{rel}: Qt outside GUI')
                if is_core and top in ('cli','gui','adapters'): errors.append(f'{rel}: frontend/adapter dependency')
                if top and top not in sys.stdlib_module_names and top not in ('mycc','PySide6','core','types','lexer','parser','sema','isa','codegen','driver','workbench','views','app','cli','gui','adapters'):
                    errors.append(f'{rel}: dependency outside allowlist: {name}')
                if is_core and isinstance(node,ast.ImportFrom) and node.level==1:
                    graph.setdefault(path.stem,set()).add(top)
                if path.name=='sema.py' and top=='isa': errors.append(f'{rel}: semantic analysis must not depend on ISA')
                if path.name=='workbench.py' and top=='PySide6': errors.append(f'{rel}: GUI logic references Qt')
            if is_core and isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ('open','print','input'):
                errors.append(f'{rel}: I/O call {node.func.id}')
            if path.name=='codegen.py' and isinstance(node,ast.Name) and node.id in ('no_lui','no_vshift','use_mul','has_div'):
                errors.append(f'{rel}: option-specific codegen branch')
            if is_core and path.name!='isa.py' and isinstance(node,ast.Constant) and isinstance(node.value,str) and 'cpu21' in node.value.lower():
                errors.append(f'{rel}: board-specific fact in compiler core')
            if rel.parts[0]=='gui' and isinstance(node,ast.Name) and node.id in ('QProcess','CPU21Board','BoardAddresses'):
                errors.append(f'{rel}: external execution/board configuration in compiler GUI')
    active=set(); done=set()
    def visit(name):
        if name in active: errors.append('core import cycle: '+name); return
        if name in done: return
        active.add(name)
        for child in graph.get(name,set()): visit(child)
        active.remove(name); done.add(name)
    for name in graph: visit(name)
    modules=[p for p in (ROOT/'mycc/core').glob('*.py') if p.name!='__init__.py']
    if len(modules)>7: errors.append('core exceeds seven modules')
    return errors


def main():
    errors=check()
    for error in errors: print(error)
    if not errors: print('architecture: imports, dependency allowlist, core DAG and GUI separation ok')
    return int(bool(errors))


if __name__=='__main__': raise SystemExit(main())
