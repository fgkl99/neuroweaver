from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path


def main():
    np.random.seed(7)

    fs = 250
    duration_sec = 60
    t = np.arange(0, duration_sec, 1/fs)

    # Basic synthetic ECG-ish waveform: spikes at ~70 bpm + baseline wander + noise
    hr_bpm = 70
    rr = 60.0 / hr_bpm
    peaks = np.arange(0.5, duration_sec, rr)

    ecg = np.zeros_like(t)
    for p in peaks:
        # QRS-like spike (Gaussian)
        ecg += 1.0 * np.exp(-0.5 * ((t - p) / 0.015) ** 2)

    # add baseline wander + noise
    ecg += 0.05 * np.sin(2 * np.pi * 0.33 * t)   # wander
    ecg += 0.02 * np.random.randn(len(t))        # noise

    df = pd.DataFrame({
        "t_sec": t,
        "ECG": ecg
    })

    out = Path("data") / "recording_ecg_060s.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"[OK] Wrote {out}")


if __name__ == "__main__":
    main()
