import argparse
import json
from pathlib import Path
from mycc.cli import profile_from_args
from .build import profile_args


def main():
    p=argparse.ArgumentParser(); p.add_argument('hardware'); profile_args(p)
    a=p.parse_args()
    profile=profile_from_args(a)
    from mycc.core import load_profile
    hw=load_profile(data=json.loads(Path(a.hardware).read_text(encoding='utf-8')))
    left=profile.instructions-hw.instructions; right=hw.instructions-profile.instructions
    print('profile-only: '+', '.join(sorted(left)))
    print('hardware-only: '+', '.join(sorted(right)))
    return int(bool(left or right))


if __name__=='__main__': raise SystemExit(main())
