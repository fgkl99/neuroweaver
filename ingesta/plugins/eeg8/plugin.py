from __future__ import annotations

import sys
import subprocess


class EEG8Plugin:
    schema_version = "eeg8_v0"

    def run_steps(self) -> None:
        # keep current behavior
        self._run([sys.executable, "run_llm.py"])
        self._run([sys.executable, "run_feature_planner.py"])
        self._run([sys.executable, "extract_features.py"])
        self._run([sys.executable, "analysis_features.py"])
        self._run([sys.executable, "render_report.py"])

    def _run(self, cmd: list[str]) -> None:
        print(f"\n=== RUN: {' '.join(cmd)} ===")
        p = subprocess.run(cmd, check=False)
        if p.returncode != 0:
            raise SystemExit(p.returncode)
