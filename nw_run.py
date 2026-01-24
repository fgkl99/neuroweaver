from __future__ import annotations
import sys
from ingesta.core.cli import main

if __name__ == "__main__":
    # preserve old entrypoint behavior:
    raise SystemExit(main(["run"] + sys.argv[1:]))
