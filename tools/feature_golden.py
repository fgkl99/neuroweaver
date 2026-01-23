from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8").strip()

def write_text(p: Path, s: str) -> None:
    p.write_text((s.strip() + "\n"), encoding="utf-8")

def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Golden snapshot gate for NeuroWeaver features.")
    ap.add_argument("--det-report", required=True, help="Path to feature_determinism.json")
    ap.add_argument("--mode", choices=["check","update"], default="check", help="check: compare; update: write goldens")
    args = ap.parse_args(argv)

    det_path = Path(args.det_report)
    det = load_json(det_path)

    if not det.get("results"):
        print("[FAIL] determinism report has no results")
        return 5

    failures: List[str] = []

    for r in det["results"]:
        feat = r["feature"]
        ok = bool(r.get("ok"))
        if not ok:
            failures.append(f"{feat}: determinism gate not ok; cannot golden-check")
            continue

        h = str(r.get("hash1","")).strip()
        if not h:
            failures.append(f"{feat}: missing hash in determinism report")
            continue

        golden_path = Path("features") / feat / "golden.sha256"

        if args.mode == "update":
            write_text(golden_path, h)
            print(f"[OK] wrote golden for {feat}: {golden_path}")
            continue

        # check mode
        if not golden_path.is_file():
            failures.append(f"{feat}: missing golden file {golden_path}")
            continue

        golden = read_text(golden_path)
        if golden != h:
            failures.append(f"{feat}: golden mismatch (golden={golden[:8]}.. current={h[:8]}..)")
        else:
            print(f"[OK] {feat}: golden match")

    if failures:
        print("[FAIL] Golden gate failures:")
        for f in failures:
            print(f"  - {f}")
        return 5

    print("[OK] Golden gate passed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
