from __future__ import annotations

import argparse
from pathlib import Path

from ingesta.core.io import read_json
from ingesta.core.runner import run_pipeline


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ingesta", description="Ingesta — signal ingestion & review runner")
    ap.add_argument("cmd", choices=["run"], help="Command")
    ap.add_argument("--meta", required=True, help="Meta JSON path (e.g., data/recording_001.meta.json)")
    ap.add_argument("--out-root", default="runs", help="Runs root folder")
    args = ap.parse_args(argv)

    meta_path = Path(args.meta)
    if not meta_path.exists():
        print(f"[ERR] meta not found: {meta_path}")
        return 2

    meta = read_json(meta_path)
    return run_pipeline(meta_path=str(meta_path), meta=meta, out_root=str(args.out_root))
