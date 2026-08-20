#!/usr/bin/env python3
"""Compatibility shim for git-checkout installations and the bin/ launchers.
The interpreter lives in the cpc package; the supported installation is
`pip install` / `pipx install` (SPEC 8.12)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cpc.main import cli

if __name__ == '__main__':
    cli()
