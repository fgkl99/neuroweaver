from __future__ import annotations

import pandas as pd

EIGHT_CH = ["F3","F4","C3","C4","P3","P4","O1","O2"]

def compute(df: pd.DataFrame, meta: dict) -> pd.DataFrame:
    # Minimal deterministic "bandpower-like" feature:
    # rolling mean-square per channel (proxy for power), window = 1 second
    fs = float(meta.get("sampling_rate_hz", 128))
    win = max(3, int(round(fs)))  # ~1s window, at least 3 samples

    out = pd.DataFrame(index=df.index)

    for ch in EIGHT_CH:
        if ch not in df.columns:
            continue
        s = df[ch].astype("float64")
        out[f"power_ms_{ch}"] = (s * s).rolling(window=win, min_periods=win).mean()

    # Drop initial NaNs created by rolling to keep shape stable downstream?
    # Here: keep NaNs (deterministic), but you could also forward-fill if you want.
    return out
