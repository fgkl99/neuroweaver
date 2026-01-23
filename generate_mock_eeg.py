from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

CH = ["F3","F4","C3","C4","P3","P4","O1","O2"]

def main():
    fs = 128
    duration_sec = 60
    n = fs * duration_sec
    t = np.arange(n) / fs

    rng = np.random.default_rng(42)

    # Base noise (wearable-ish)
    noise = rng.normal(0, 2.0, size=(n, len(CH)))

    # Alpha rhythm 10 Hz, stronger on O1/O2
    alpha = np.sin(2*np.pi*10*t)
    alpha_gains = {
        "F3": 1.0, "F4": 1.0,
        "C3": 0.8, "C4": 0.8,
        "P3": 1.5, "P4": 1.5,
        "O1": 3.0, "O2": 2.8
    }

    X = noise.copy()
    for j, c in enumerate(CH):
        X[:, j] += alpha_gains[c] * alpha

    df = pd.DataFrame(X, columns=CH)
    df.insert(0, "t_sec", t.round(6))

    out = Path("data") / "recording_060s.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"[OK] wrote {out} with {n} samples ({duration_sec}s at {fs}Hz)")

if __name__ == "__main__":
    main()
