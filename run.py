from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd


EIGHT_CH = ["F3", "F4", "C3", "C4", "P3", "P4", "O1", "O2"]


@dataclass
class Checks:
    schema_version_ok: bool
    channels_ok: bool
    columns_ok: bool
    time_monotonic_ok: bool
    fs_consistent_ok: bool
    missing_ratio_ok: bool
    amplitude_ok: bool


def load_meta(meta_path: Path) -> dict:
    return json.loads(meta_path.read_text(encoding="utf-8"))


def load_csv(csv_path: Path) -> pd.DataFrame:
    return pd.read_csv(csv_path)


def compute_fs_from_t(t: pd.Series) -> float | None:
    dt = t.diff().dropna()
    if len(dt) < 5:
        return None
    med = float(dt.median())
    if med <= 0:
        return None
    return 1.0 / med


def grade_quality(c: Checks) -> str:
    critical = [
        c.schema_version_ok,
        c.channels_ok,
        c.columns_ok,
        c.time_monotonic_ok,
        c.fs_consistent_ok,
    ]
    if not all(critical):
        return "poor"
    if c.missing_ratio_ok and c.amplitude_ok:
        return "good"
    return "medium"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NeuroWeaver EEG8 data quality checks (writes a run folder).")
    parser.add_argument("--meta", type=str, default="data/recording_001.meta.json", help="Path to meta json.")
    parser.add_argument("--csv", type=str, default=None, help="Optional override CSV path (else uses meta['csv']['path']).")
    parser.add_argument("--out-root", type=str, default="runs", help="Output root folder (default: runs).")
    args = parser.parse_args(argv)

    root = Path(".")
    meta_path = root / args.meta
    meta = load_meta(meta_path)

    csv_rel = Path(args.csv) if args.csv else Path(meta["csv"]["path"])
    # resolve relative paths relative to the meta file location (more robust than repo root)
    if not csv_rel.is_absolute():
        csv_path = (meta_path.parent / csv_rel).resolve()
    else:
        csv_path = csv_rel

    df = load_csv(csv_path)

    time_col = meta["csv"]["time_column"]
    signal_cols = meta["csv"]["signal_columns"]
    fs_nominal = float(meta["sampling_rate_hz"])

    schema_version_ok = meta.get("schema_version") == "eeg8_v0"
    channels_ok = meta.get("channels") == EIGHT_CH and signal_cols == EIGHT_CH

    expected_cols = [time_col] + EIGHT_CH
    columns_ok = all(c in df.columns for c in expected_cols)

    time_monotonic_ok = False
    fs_consistent_ok = False
    fs_est = None

    if columns_ok:
        t = df[time_col]
        time_monotonic_ok = bool((t.diff().dropna() > 0).all())
        fs_est = compute_fs_from_t(t)
        if fs_est is not None:
            fs_consistent_ok = abs(fs_est - fs_nominal) / fs_nominal <= 0.03

    miss_ratio = float(df[expected_cols].isna().mean().mean()) if columns_ok else math.nan
    max_missing = float(meta.get("quality_assumptions", {}).get("max_missing_ratio", 0.02))
    missing_ratio_ok = bool(miss_ratio <= max_missing) if columns_ok else False

    lo, hi = meta.get("quality_assumptions", {}).get("expected_uV_range", [-200, 200])
    lo, hi = float(lo), float(hi)
    amp_ok = False
    out_of_range_ratio = math.nan
    if columns_ok:
        sig = df[EIGHT_CH]
        out_of_range = ((sig < lo) | (sig > hi)).mean().mean()
        out_of_range_ratio = float(out_of_range)
        amp_ok = out_of_range_ratio <= 0.005

    checks = Checks(
        schema_version_ok=schema_version_ok,
        channels_ok=channels_ok,
        columns_ok=columns_ok,
        time_monotonic_ok=time_monotonic_ok,
        fs_consistent_ok=fs_consistent_ok,
        missing_ratio_ok=missing_ratio_ok,
        amplitude_ok=amp_ok,
    )

    n_samples = int(len(df)) if columns_ok else 0
    duration_sec = float(df[time_col].iloc[-1] - df[time_col].iloc[0]) if (columns_ok and n_samples > 1) else 0.0

    summary = {
        "recording_id": meta.get("recording_id"),
        "n_samples": n_samples,
        "n_channels": 8,
        "channels": EIGHT_CH,
        "fs_nominal_hz": fs_nominal,
        "fs_estimated_hz": fs_est,
        "duration_sec": duration_sec,
        "missing_ratio": miss_ratio,
        "out_of_range_ratio": out_of_range_ratio,
        "quality_grade": grade_quality(checks),
        "notes": meta.get("notes", "")
    }

    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    out_root = root / args.out_root
    out_dir = out_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "checks.json").write_text(json.dumps(checks.__dict__, indent=2), encoding="utf-8")
    (out_dir / "data_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[OK] Wrote {out_dir}")

    # Exit non-zero if critical checks fail (useful for orchestrator)
    if summary["quality_grade"] == "poor":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
