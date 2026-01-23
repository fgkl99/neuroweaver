from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def load_csv(p: Path) -> pd.DataFrame:
    return pd.read_csv(p)


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    # Normalize for stable hashing:
    # - sort columns
    # - reset index to stable range
    # - ensure consistent column order and dtypes representation
    out = df.copy()
    out = out.reindex(sorted(out.columns), axis=1)
    out = out.reset_index(drop=True)

    # Optional: make float hashing more stable across minor repr differences
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].round(10)

    return out


def df_sha256(df: pd.DataFrame) -> str:
    n = normalize_df(df)
    # CSV serialization is simple & stable enough after normalization
    csv_bytes = n.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def load_feature_compute(feature_py: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, feature_py)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import feature module from {feature_py}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    if not hasattr(mod, "compute") or not callable(getattr(mod, "compute")):
        raise RuntimeError(f"{feature_py} must define callable compute(df, meta)")
    return getattr(mod, "compute")


def check_feature_determinism(
    feature_name: str,
    df_in: pd.DataFrame,
    meta: Dict[str, Any],
) -> Dict[str, Any]:
    feature_py = Path("features") / feature_name / "feature.py"
    compute = load_feature_compute(feature_py, f"features.{feature_name}.feature")

    out1 = compute(df_in, meta)
    out2 = compute(df_in, meta)

    if not isinstance(out1, pd.DataFrame) or not isinstance(out2, pd.DataFrame):
        return {
            "feature": feature_name,
            "ok": False,
            "error": "compute() must return a pandas.DataFrame",
        }


    if out1.shape[1] == 0:
        return {
            "feature": feature_name,
            "ok": False,
            "error": "compute() produced 0 output columns (empty feature set)."
        }

    h1 = df_sha256(out1)
    h2 = df_sha256(out2)

    ok = (h1 == h2) and (list(out1.columns) == list(out2.columns)) and (len(out1) == len(out2))

    result: Dict[str, Any] = {
        "feature": feature_name,
        "ok": bool(ok),
        "hash1": h1,
        "hash2": h2,
        "n_rows_1": int(len(out1)),
        "n_rows_2": int(len(out2)),
        "cols_1": list(map(str, out1.columns)),
        "cols_2": list(map(str, out2.columns)),
    }

    if not ok:
        result["error"] = "Non-deterministic output (hash/shape/columns mismatch)."
    return result


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Determinism gate for NeuroWeaver feature compute().")
    parser.add_argument("--meta", type=str, default="data/recording_001.meta.json")
    parser.add_argument("--csv", type=str, default=None, help="Override CSV path; else uses meta['csv']['path']")
    parser.add_argument("--features", type=str, nargs="+", required=True, help="Feature folder names to check")
    parser.add_argument("--out", type=str, default=None, help="Optional output JSON report path")
    args = parser.parse_args(argv)

    meta_path = Path(args.meta)
    meta = load_json(meta_path)

    csv_rel = Path(args.csv) if args.csv else Path(meta["csv"]["path"])
    csv_path = (meta_path.parent / csv_rel).resolve() if not csv_rel.is_absolute() else csv_rel
    df = load_csv(csv_path)

    results = [check_feature_determinism(name, df, meta) for name in args.features]
    all_ok = all(r.get("ok") for r in results)

    payload = {
        "meta": str(meta_path),
        "csv": str(csv_path),
        "features": args.features,
        "all_ok": bool(all_ok),
        "results": results,
    }

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if not all_ok:
        bad = [r["feature"] for r in results if not r.get("ok")]
        print(f"[FAIL] Non-deterministic features: {bad}")
        return 4

    print("[OK] Determinism gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

