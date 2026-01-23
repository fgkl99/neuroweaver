from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set
from jsonschema import Draft202012Validator, validate

import yaml

ROOT = Path(".")
ARTIFACTS = ROOT / "artifacts"


@dataclass
class CmdResult:
    cmd: List[str]
    returncode: int
    duration_s: float
    stdout: str
    stderr: str


def run_cmd(cmd: List[str], cwd: Path = ROOT) -> CmdResult:
    t0 = time.time()
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    dt = time.time() - t0
    return CmdResult(
        cmd=cmd,
        returncode=p.returncode,
        duration_s=dt,
        stdout=p.stdout or "",
        stderr=p.stderr or "",
    )


def load_change_request(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_report(out_dir: Path, report: Dict[str, Any]) -> None:
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def substitute_placeholders(cmd: List[str], out_dir: Path) -> List[str]:
    out_dir_str = str(out_dir)
    return [s.replace("{OUT_DIR}", out_dir_str) for s in cmd]


def _git_lines(args: List[str]) -> List[str]:
    p = subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True)
    if p.returncode != 0:
        # If git isn't available / not a repo, fail hard: governance requires repo discipline
        raise RuntimeError(f"Git command failed: git {' '.join(args)}\n{p.stderr}")
    return [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]


def get_changed_files() -> Set[str]:
    # Combine staged + unstaged changes (relative paths)
    unstaged = set(_git_lines(["diff", "--name-only"]))
    staged = set(_git_lines(["diff", "--name-only", "--cached"]))
    return unstaged | staged


def get_touched_feature_names(changed_files: Set[str]) -> Set[str]:
    touched: Set[str] = set()
    for f in changed_files:
        p = Path(f)
        parts = p.parts
        if len(parts) >= 2 and parts[0] == "features":
            # features/<name>/...
            touched.add(parts[1])
    return touched


def enforce_feature_contract(touched_features: Set[str]) -> List[str]:
    errors: List[str] = []

    schema_path = ROOT / "schemas" / "feature_meta.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except Exception as e:
        return [f"Invalid feature_meta schema at {schema_path}: {e}"]

    for name in sorted(touched_features):
        feat_dir = ROOT / "features" / name
        meta_path = feat_dir / "meta.json"
        test_dir = ROOT / "tests" / "features" / name

        if not feat_dir.is_dir():
            errors.append(f"Feature folder missing: features/{name}/")
            continue

        # 1) meta must exist
        if not meta_path.is_file():
            errors.append(f"Missing meta.json for touched feature: features/{name}/meta.json")
        else:
            # 2) meta must parse + validate
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                validate(instance=meta, schema=schema)
            except Exception as e:
                errors.append(f"meta.json schema invalid for feature '{name}': {e}")
        # Enforce folder-name match
        meta_id = str(meta.get("id", "")).strip()
        if meta_id != name:
            errors.append(f"meta.id mismatch for feature '{name}': meta.id='{meta_id}' but folder is features/{name}/")

        # 3) tests must exist
        if not test_dir.is_dir():
            errors.append(f"Missing test folder for touched feature: tests/features/{name}/")
        else:
            tests = list(test_dir.glob("test_*.py"))
            if len(tests) == 0:
                errors.append(f"No tests found in: tests/features/{name}/ (expected test_*.py)")

        # 4) feature.py must exist, be importable, and define callable compute
        feature_py = feat_dir / "feature.py"
        if not feature_py.is_file():
            errors.append(f"Missing feature implementation: features/{name}/feature.py")
        else:
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(f"features.{name}.feature", feature_py)
                if spec is None or spec.loader is None:
                    raise RuntimeError("Cannot create import spec")
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore
                if not hasattr(mod, "compute") or not callable(getattr(mod, "compute")):
                    errors.append(f"features/{name}/feature.py must define callable compute(df, meta)")
            except Exception as e:
                errors.append(f"Failed to import features/{name}/feature.py: {e}")

    return errors


def main() -> int:
    cr_path = ROOT / "CHANGE_REQUEST.yaml"
    cr = load_change_request(cr_path)

    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    out_dir = ARTIFACTS / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    test_cmds = cr.get("test_commands") or [["python", "-m", "pytest", "-q"]]
    verify_cmds = cr.get("verify_commands") or [
        ["python", "run.py", "--meta", "data/recording_001.meta.json", "--out-root", "{OUT_DIR}/nw_runs"]
    ]

    results: List[Dict[str, Any]] = []

    # Stage 1: tests
    for c in test_cmds:
        cmd = substitute_placeholders(list(c), out_dir)
        r = run_cmd(cmd)
        results.append(r.__dict__)
        if r.returncode != 0:
            report = {
                "change_request": cr,
                "status": "FAIL",
                "stage": "tests",
                "results": results,
                "artifacts_dir": str(out_dir),
            }
            write_report(out_dir, report)
            print(f"[FAIL] tests -> {out_dir / 'report.json'}")
            return 1

    # Stage 2: verification commands
    for c in verify_cmds:
        cmd = substitute_placeholders(list(c), out_dir)
        r = run_cmd(cmd)
        results.append(r.__dict__)
        if r.returncode != 0:
            report = {
                "change_request": cr,
                "status": "FAIL",
                "stage": "verify",
                "results": results,
                "artifacts_dir": str(out_dir),
            }
            write_report(out_dir, report)
            print(f"[FAIL] verify -> {out_dir / 'report.json'}")
            return 2

    # Stage 3: feature governance gate
    changed = get_changed_files()
    touched = get_touched_feature_names(changed)
    gate_errors = enforce_feature_contract(touched)

    if gate_errors:
        report = {
            "change_request": cr,
            "status": "FAIL",
            "stage": "feature_contract",
            "results": results,
            "artifacts_dir": str(out_dir),
            "changed_files": sorted(changed),
            "touched_features": sorted(touched),
            "errors": gate_errors,
        }
        write_report(out_dir, report)
        print(f"[FAIL] feature_contract -> {out_dir / 'report.json'}")
        for e in gate_errors:
            print(f"  - {e}")
        return 3


    # Stage 4: feature determinism gate (CR-controlled, fallback to touched)
    det_features = cr.get("determinism_features") or sorted(touched)
    if det_features:

        det_out = out_dir / "feature_determinism.json"
        det_cmd = [
            "python", "tools/feature_determinism.py",
            "--meta", "data/recording_001.meta.json",
            "--out", str(det_out),
            "--features", *list(det_features)
        ]
        r = run_cmd(det_cmd)
        results.append(r.__dict__)
        if r.returncode != 0:
            report = {
                "change_request": cr,
                "status": "FAIL",
                "stage": "feature_determinism",
                "results": results,
                "artifacts_dir": str(out_dir),
                "changed_files": sorted(changed),
                "touched_features": sorted(touched),
                "determinism_features": list(det_features),
            }
            write_report(out_dir, report)
            print(f"[FAIL] feature_determinism -> {out_dir / 'report.json'}")
            return 4

        # Stage 5: golden snapshot gate (uses determinism artifact)
        golden_cmd = [
            "python", "tools/feature_golden.py",
            "--det-report", str(det_out),
            "--mode", "check",
        ]
        r = run_cmd(golden_cmd)
        results.append(r.__dict__)
        if r.returncode != 0:
            report = {
                "change_request": cr,
                "status": "FAIL",
                "stage": "feature_golden",
                "results": results,
                "artifacts_dir": str(out_dir),
                "changed_files": sorted(changed),
                "touched_features": sorted(touched),
                "determinism_features": list(det_features),
            }
            write_report(out_dir, report)
            print(f"[FAIL] feature_golden -> {out_dir / 'report.json'}")
            return 5

    report = {
        "change_request": cr,
        "status": "PASS",
        "results": results,
        "artifacts_dir": str(out_dir),
        "changed_files": sorted(changed),
        "touched_features": sorted(touched),
    }
    write_report(out_dir, report)
    print(f"[OK] Orchestrator report: {out_dir / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

