from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import plot


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def latest_run_dir(root: Path) -> Path:
    runs_dir = root / "runs"
    run_folders = sorted([p for p in runs_dir.glob("run_*") if p.is_dir()])
    if not run_folders:
        raise FileNotFoundError("No runs found. Run run.py first.")
    return run_folders[-1]


def make_table(title: str, df: pd.DataFrame, include_js: bool) -> str:
    fig = go.Figure(
        data=[go.Table(
            header=dict(values=list(df.columns)),
            cells=dict(values=[df[c].tolist() for c in df.columns])
        )]
    )
    fig.update_layout(title=title)
    return plot(fig, include_plotlyjs=("cdn" if include_js else False), output_type="div")


def main():
    root = Path(".")
    run_dir = latest_run_dir(root)
    print(f"[INFO] Using run folder: {run_dir}")

    summary = load_json(run_dir / "data_summary.json")
    checks = load_json(run_dir / "checks.json")

    feat_path = run_dir / "features.csv"
    win_path = run_dir / "features_windowed.csv"

    feat_df = pd.read_csv(feat_path) if feat_path.exists() else pd.DataFrame()
    win_df = pd.read_csv(win_path) if win_path.exists() else pd.DataFrame()

    blocks = []

    # Data summary
    metrics = [
        ("recording_id", summary.get("recording_id")),
        ("quality_grade", summary.get("quality_grade")),
        ("n_samples", summary.get("n_samples")),
        ("duration_sec", round(float(summary.get("duration_sec", 0.0) or 0.0), 3)),
        ("fs_nominal_hz", summary.get("fs_nominal_hz")),
        ("fs_estimated_hz", summary.get("fs_estimated_hz")),
        ("missing_ratio", summary.get("missing_ratio")),
        ("out_of_range_ratio", summary.get("out_of_range_ratio")),
    ]
    qc_df = pd.DataFrame(metrics, columns=["metric", "value"])
    blocks.append(make_table("NeuroWeaver — Data Summary", qc_df, include_js=True))

    # Checks
    chk_df = pd.DataFrame(list(checks.items()), columns=["check", "ok"])
    blocks.append(make_table("Validation Checks", chk_df, include_js=False))

    # Aggregates table (mean/std only), long format
    if not feat_df.empty:
        row = feat_df.iloc[0].to_dict()
        rec_id = row.get("recording_id", "")
        items = []
        for k, v in row.items():
            if k == "recording_id":
                continue
            # show only mean/std to keep readable
            if k.endswith("__mean") or k.endswith("__std"):
                base, agg = k.rsplit("__", 1)
                items.append((base, agg, v))
        items.sort(key=lambda x: (x[0], x[1]))
        agg_long = pd.DataFrame(items, columns=["feature", "agg", "value"])
        agg_long.insert(0, "recording_id", rec_id)

        blocks.append(make_table("Feature Aggregates (mean/std)", agg_long, include_js=False))

    # Windowed time-series plots for a few key features
    if not win_df.empty and "t_start" in win_df.columns:
        t = win_df["t_start"].to_numpy()

        # candidate features to plot (choose existing)
        candidates = ["hr_bpm", 
            "bandpower_alpha_o1",
            "bandpower_alpha_o2",
            "rms_o1",
            "rms_o2",
            "spectral_entropy_o1",
            "spectral_entropy_o2",
            "alpha_asymmetry_f3_f4",
        ]
        available = [c for c in candidates if c in win_df.columns]

        # Plot up to 4 lines max to keep clean
        to_plot = available[:4]
        if to_plot:
            fig = go.Figure()
            for c in to_plot:
                fig.add_trace(go.Scatter(x=t, y=win_df[c], mode="lines", name=c))
            fig.update_layout(
                title="Windowed Features Over Time",
                xaxis_title="t_start (sec)",
                yaxis_title="value"
            )
            blocks.append(plot(fig, include_plotlyjs=False, output_type="div"))

    html_blocks = "\n".join([f'<div class="block">{b}</div>' for b in blocks])

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>NeuroWeaver Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    h1 {{ margin-bottom: 8px; }}
    .meta {{ color: #444; margin-bottom: 16px; }}
    .block {{ margin: 24px 0; }}
  </style>
</head>
<body>
  <h1>NeuroWeaver Report</h1>
  <div class="meta">Run folder: {run_dir.as_posix()}</div>
  {html_blocks}
</body>
</html>
"""

    out_path = run_dir / "report.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[OK] Saved: {out_path}")


if __name__ == "__main__":
    main()

