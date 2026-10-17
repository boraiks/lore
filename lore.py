#!/usr/bin/env python3
"""Entry point: python lore.py <seed|recall|jot|mesh> ..."""

import sys

from lorelib.cli import main

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
