from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    root = Path(".")
    runs_dir = root / "runs"
    run_folders = sorted([p for p in runs_dir.glob("run_*") if p.is_dir()])
    if not run_folders:
        raise FileNotFoundError("No runs found. Run run.py first.")
    run_dir = run_folders[-1]
    print(f"[INFO] Using run folder: {run_dir}")

    summary = load_json(run_dir / "data_summary.json")

    feat_path = run_dir / "features.csv"
    if not feat_path.exists():
        raise FileNotFoundError("features.csv not found. Run extract_features.py first.")

    df = pd.read_csv(feat_path)
    if df.empty:
        raise ValueError("features.csv is empty.")

    # numeric columns
    num_cols = [c for c in df.columns if c != "recording_id"]
    desc = df[num_cols].describe(include="all").to_dict()

    analysis = {
        "recording_id": summary.get("recording_id"),
        "n_features": len(num_cols),
        "feature_names": num_cols,
        "summary_stats": desc,
    }

    out_path = run_dir / "analysis.json"
    out_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    print(f"[OK] Saved: {out_path}")


if __name__ == "__main__":
    main()
