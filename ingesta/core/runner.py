from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ingesta.core.registry import REGISTRY


def _run_step(cmd: list[str]) -> None:
    print(f"\n=== RUN: {' '.join(cmd)} ===")
    p = subprocess.run(cmd, check=False)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def run_pipeline(meta_path: str, meta: dict, out_root: str) -> int:
    schema_version = meta.get("schema_version")
    if schema_version not in REGISTRY:
        print(f"[ERR] Unsupported schema_version: {schema_version}")
        return 2

    plugin = REGISTRY[schema_version]

    # Shared: validation/run (still uses your existing run.py for now)
    _run_step([sys.executable, "run.py", "--meta", meta_path, "--out-root", out_root])

    # Plugin-specific steps (still calling your existing scripts for now)
    plugin.run_steps()

    print("\n[OK] Pipeline completed.")
    return 0
