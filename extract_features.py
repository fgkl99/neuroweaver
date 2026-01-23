from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import welch


EIGHT_CH = ["F3", "F4", "C3", "C4", "P3", "P4", "O1", "O2"]


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def bandpower_welch(x: np.ndarray, fs: float, band: tuple[float, float]) -> float:
    if len(x) < 8:
        return float("nan")
    nperseg = min(256, len(x))
    f, pxx = welch(x, fs=fs, nperseg=nperseg, detrend="constant")
    lo, hi = band
    mask = (f >= lo) & (f <= hi)
    if not np.any(mask):
        return float("nan")
    return float(np.trapz(pxx[mask], f[mask]))


def spectral_entropy_from_psd(x: np.ndarray, fs: float, band: tuple[float, float]) -> float:
    if len(x) < 8:
        return float("nan")
    nperseg = min(256, len(x))
    f, pxx = welch(x, fs=fs, nperseg=nperseg, detrend="constant")
    lo, hi = band
    mask = (f >= lo) & (f <= hi)
    p = pxx[mask].astype(float)
    if p.size == 0:
        return float("nan")
    p_sum = p.sum()
    if p_sum <= 0:
        return float("nan")
    p = p / p_sum
    # Shannon entropy normalized
    h = -np.sum(p * np.log(p + 1e-12))
    h_norm = h / np.log(len(p) + 1e-12)
    return float(h_norm)


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else float("nan")


def main():
    root = Path(".")
    runs_dir = root / "runs"
    run_folders = sorted([p for p in runs_dir.glob("run_*") if p.is_dir()])
    if not run_folders:
        raise FileNotFoundError("No runs found. Run run.py first.")
    run_dir = run_folders[-1]
    print(f"[INFO] Using run folder: {run_dir}")

    summary = load_json(run_dir / "data_summary.json")
    meta = load_json(root / "data" / "recording_001.meta.json")

    csv_path = root / "data" / meta["csv"]["path"]
    df = pd.read_csv(csv_path)

    fs = float(summary["fs_nominal_hz"])
    band_alpha = (8.0, 12.0)
    band_entropy = (4.0, 30.0)

    out = {"recording_id": summary["recording_id"], "features": {}}

    for ch in EIGHT_CH:
        x = df[ch].to_numpy(dtype=float)
        out["features"][f"rms_{ch.lower()}"] = rms(x)
        out["features"][f"bandpower_alpha_{ch.lower()}"] = bandpower_welch(x, fs, band_alpha)
        out["features"][f"spectral_entropy_{ch.lower()}"] = spectral_entropy_from_psd(x, fs, band_entropy)

    # Save flat csv row
    row = {"recording_id": summary["recording_id"], **out["features"]}
    feat_df = pd.DataFrame([row])

    feat_df.to_csv(run_dir / "features.csv", index=False)
    (run_dir / "feature_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"[OK] Saved: {run_dir / 'features.csv'}")
    print(f"[OK] Saved: {run_dir / 'feature_report.json'}")


if __name__ == "__main__":
    main()
