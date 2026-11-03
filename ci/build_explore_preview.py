#!/usr/bin/env python3
"""Build inert Deals + two-sport Explore fixtures. No network or live state."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ci.build_preview import build
from explore.demo import fixture
from explore.view import install


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args(argv)
    if args.output.resolve() == ROOT:
        parser.error('Use a separate review output folder')
    build(args.output, 'Explore #169 · synthetic inventory')
    install(args.output, [fixture('mtb'), fixture('ski')])
    return 0


if __name__ == '__main__': raise SystemExit(main())
