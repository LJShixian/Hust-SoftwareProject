"""Explicit external execution adapters. The compiler never imports this package."""
from mycc.core import CompileOptions, ProfileError


def check_target(profile,target):
    """Validate an explicitly selected external execution environment."""
    if target=='generic': return
    if target!='cpu21': raise ProfileError(f'unknown target {target!r}',64)
    from .cpu21 import validate_profile
    validate_profile(profile)


def compile_options(target='generic',**kwargs):
    """Inject adapter policy only when an external target is explicitly selected."""
    if target=='generic': return CompileOptions(**kwargs)
    if target=='cpu21':
        from .cpu21 import options
        return options(**kwargs)
    raise ProfileError(f'unknown target {target!r}',64)
