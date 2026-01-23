from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

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
    # Only allow a small set of placeholders (expand later if needed)
    out_dir_str = str(out_dir)
    return [s.replace("{OUT_DIR}", out_dir_str) for s in cmd]


def main() -> int:
    cr_path = ROOT / "CHANGE_REQUEST.yaml"
    cr = load_change_request(cr_path)

    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    out_dir = ARTIFACTS / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    test_cmds = cr.get("test_commands") or [["python", "-m", "pytest", "-q"]]
    verify_cmds = cr.get("verify_commands") or [["python", "run.py", "--meta", "data/recording_001.meta.json", "--out-root", "{OUT_DIR}/nw_runs"]]

    results: List[Dict[str, Any]] = []

    # Stage 1: tests
    for c in test_cmds:
        cmd = substitute_placeholders(list(c), out_dir)
        r = run_cmd(cmd)
        results.append(r.__dict__)
        if r.returncode != 0:
            report = {"change_request": cr, "status": "FAIL", "stage": "tests", "results": results, "artifacts_dir": str(out_dir)}
            write_report(out_dir, report)
            print(f"[FAIL] tests -> {out_dir / 'report.json'}")
            return 1

    # Stage 2: verification
    for c in verify_cmds:
        cmd = substitute_placeholders(list(c), out_dir)
        r = run_cmd(cmd)
        results.append(r.__dict__)
        if r.returncode != 0:
            report = {"change_request": cr, "status": "FAIL", "stage": "verify", "results": results, "artifacts_dir": str(out_dir)}
            write_report(out_dir, report)
            print(f"[FAIL] verify -> {out_dir / 'report.json'}")
            return 2

    report = {"change_request": cr, "status": "PASS", "results": results, "artifacts_dir": str(out_dir)}
    write_report(out_dir, report)
    print(f"[OK] Orchestrator report: {out_dir / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
