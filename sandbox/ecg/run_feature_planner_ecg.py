from __future__ import annotations

import json
from pathlib import Path


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8-sig"))


def write_json(p: Path, obj: dict):
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def main():
    root = Path(".")
    runs_dir = root / "runs"
    run_folders = sorted([p for p in runs_dir.glob("run_*") if p.is_dir()])
    if not run_folders:
        raise FileNotFoundError("No runs found. Run run.py first.")
    run_dir = run_folders[-1]
    print(f"[INFO] Using run folder: {run_dir}")

    summary = load_json(run_dir / "data_summary.json")

    # Minimal deterministic ECG plan (v0)
    plan = {
        "recording_id": summary.get("recording_id"),
        "schema_version": "ecg1_v0",
        "features": [
            {
                "name": "hr_bpm",
                "family": "ecg_hr",
                "params": {"window_sec": 10.0, "stride_sec": 5.0}
            },
            {
                "name": "rmssd_ms",
                "family": "ecg_hrv",
                "params": {}
            },
            {
                "name": "sdnn_ms",
                "family": "ecg_hrv",
                "params": {}
            },
            {
                "name": "n_beats",
                "family": "ecg_qc",
                "params": {}
            }
        ],
        "notes": ["ECG v0 deterministic plan: HR windowed + basic HRV aggregates."]
    }

    out = run_dir / "feature_plan.json"
    write_json(out, plan)
    print(f"[OK] Saved: {out}")


if __name__ == "__main__":
    main()
