# CLAUDE.md — NeuroWeaver Codebase Guide

This file provides AI assistants with a complete orientation to the NeuroWeaver codebase: its architecture, conventions, workflows, and hard constraints.

---

## Project Overview

NeuroWeaver is a **conservative, decision-oriented EEG feature pipeline** for wearable 8-channel EEG recordings. It does NOT train models, optimize classifiers, or produce end-to-end predictions. Its purpose is to validate raw EEG data, plan meaningful feature extraction, extract features, and enforce quality gates — all with explicit rationale at every step.

**Status:** Research/engineering prototype.

**Scope is intentionally fixed:** 8-channel wearable EEG (F3, F4, C3, C4, P3, P4, O1, O2) at ~128 Hz.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.9+ |
| Data manipulation | pandas, numpy |
| Signal processing | scipy (`scipy.signal.welch`) |
| Schema validation | jsonschema (Draft 2020-12) |
| LLM integration | google-genai (Gemini API) |
| Orchestration | subprocess, PyYAML |
| Testing | pytest |

**Explicitly excluded (by design):** TensorFlow, PyTorch, scikit-learn, connectivity analysis libraries (coherence, PLV, PLI, WPLI, graph metrics).

---

## Repository Structure

```
neuroweaver/
├── run.py                     # Stage 1: Data validation & quality grading
├── run_llm.py                 # Stage 2: LLM-based data auditor (Gemini)
├── run_feature_planner.py     # Stage 3: Feature plan generator (LLM + fallback)
├── extract_features.py        # Stage 4: Feature extraction (RMS, bandpower, spectral entropy)
├── generate_mock_eeg.py       # Utility: generates reproducible mock EEG CSV
│
├── features/
│   └── bandpower/
│       ├── feature.py         # compute(df, meta) implementation
│       └── meta.json          # Feature metadata (validated against schema)
│
├── tools/
│   ├── nw_orch.py             # Orchestrator: runs all stages + contract/determinism gates
│   └── feature_determinism.py # SHA256 determinism checker for feature compute()
│
├── schemas/
│   ├── eeg8_v0.json                    # EEG recording metadata schema
│   ├── feature_meta.schema.json        # Feature module metadata schema
│   ├── feature_plan_v0.schema.json     # Feature plan output schema
│   └── llm_data_assessment_v0.schema.json  # LLM auditor output schema
│
├── prompts/
│   ├── prompt_001.txt         # LLM data auditor prompt (treated as a contract)
│   └── prompt_002.txt         # LLM feature planner prompt (treated as a contract)
│
├── data/
│   ├── recording_060s.csv     # Mock EEG data (128 Hz, 8 channels, seed=42)
│   └── recording_001.meta.json  # Metadata for mock recording
│
├── tests/
│   ├── orchestrator/test_smoke.py
│   ├── gates/test_determinism_hash.py
│   ├── schemas/test_feature_meta_schema.py
│   ├── schemas/test_bandpower_meta_validates.py
│   └── features/bandpower/test_feature.py
│
├── artifacts/                 # Orchestrator reports (gitignored)
├── runs/                      # Pipeline run outputs (gitignored)
├── docs/ORCHESTRATOR.md       # (placeholder)
├── CHANGE_REQUEST.yaml        # Orchestrator change request config
└── pytest.ini                 # Test configuration
```

---

## Pipeline Stages

The pipeline runs in four sequential stages. Each stage writes JSON output consumed by the next.

### Stage 1 — `run.py`: Data Validation

**Command:** `python run.py --meta data/recording_001.meta.json --out-root runs`

**What it does:**
- Loads EEG metadata JSON + the CSV it references
- Validates metadata against `schemas/eeg8_v0.json` (JSON Schema Draft 2020-12)
- Performs 7 quality checks:
  1. Schema conformance
  2. Channel presence (exact 8: F3, F4, C3, C4, P3, P4, O1, O2)
  3. CSV column presence
  4. Time monotonicity
  5. Sampling rate consistency
  6. Missing data ratio (threshold: 2%)
  7. Amplitude bounds (expected: ±200 µV)
- Grades recording as `poor` / `medium` / `good`
- Outputs to `runs/run_<timestamp>/`: `checks.json`, `data_summary.json`

**Exit codes:** `0` = success, `2` = poor quality

### Stage 2 — `run_llm.py`: LLM Data Auditor

**Command:** `python run_llm.py`

**What it does:**
- Reads `data_summary.json` from the latest run
- Calls Gemini API with `prompts/prompt_001.txt`
- Validates response against `schemas/llm_data_assessment_v0.schema.json`
- Enforces hard guardrail: **connectivity features are banned** (coherence, PLV, PLI, WPLI, graph)
- Outputs: `llm_data_assessment.json`

**Environment variables required:**
- `GEMINI_API_KEY` — Google Gemini API key
- `GEMINI_MODEL` — Model name (default: `gemini-2.0-flash`)

### Stage 3 — `run_feature_planner.py`: Feature Plan Generation

**Command:** `python run_feature_planner.py`

**What it does:**
- Reads `data_summary.json` + `llm_data_assessment.json`
- **Primary path:** Calls Gemini with `prompts/prompt_002.txt` (JSON mode)
- **Fallback path:** Deterministic `fallback_feature_plan()` if LLM unavailable (429, missing key, exception)
- Caps output at 12 features
- Applies confidence penalty: `≤0.2` if duration < 10s
- Validates output against `schemas/feature_plan_v0.schema.json`
- Allowed families: `bandpower`, `spectral_entropy`, `time_domain`
- Allowed scopes: `single_channel`, `pair_lr`, `all_channels`
- Default window: 2s, stride: 1s
- Outputs: `feature_plan.json`

### Stage 4 — `extract_features.py`: Feature Extraction

**Command:** `python extract_features.py`

**What it does:**
- Loads EEG CSV
- Computes across all 8 channels:
  - RMS (root mean square)
  - Bandpower alpha (8–12 Hz) via Welch's method
  - Spectral entropy (4–30 Hz, Shannon)
- Outputs: `features.csv` (flat row), `feature_report.json`

---

## Orchestrator

**Command:** `python tools/nw_orch.py`

Reads `CHANGE_REQUEST.yaml` and runs four validation stages:

1. **Test stage** — `python -m pytest -q`
2. **Verification stage** — runs `run.py` with specified data
3. **Feature contract gate** — validates all feature modules for:
   - `meta.json` exists and validates against `schemas/feature_meta.schema.json`
   - `feature.py` has a callable `compute(df, meta)` function
   - Tests exist (`test_*.py` files)
   - `meta.id` matches the folder name
4. **Feature determinism gate** — runs `compute()` twice, compares SHA256 hashes

**Exit codes:** `0` = pass, `1` = test fail, `2` = verify fail, `3` = contract fail, `4` = determinism fail

**Output:** JSON report to `artifacts/run_<timestamp>/report.json`

---

## Adding a New Feature Module

Every feature lives in `features/<name>/` and must satisfy the feature contract:

### 1. Create `features/<name>/meta.json`

```json
{
  "id": "<name>",
  "version": "0.1.0",
  "description": "Brief description",
  "inputs": {
    "channels": ["F3", "F4", "C3", "C4", "P3", "P4", "O1", "O2"],
    "sampling_rate_hz_min": 100
  },
  "outputs": [
    {
      "name": "output_column_name",
      "unit": "uV^2",
      "expected_range": [0, 1000000]
    }
  ]
}
```

Constraints:
- `id` must match the folder name exactly
- `id` must match pattern `^[a-z0-9_\-]+$`
- All 8 channels must be listed in `inputs.channels`
- `outputs` must include `name`, `unit`, `expected_range`

### 2. Create `features/<name>/feature.py`

```python
from __future__ import annotations
import pandas as pd

def compute(df: pd.DataFrame, meta: dict) -> pd.DataFrame:
    """
    Must be:
    - Deterministic: same input → same output every time
    - Handles missing channels gracefully
    - Returns a DataFrame with named columns
    """
    ...
    return result_df
```

**Critical:** `compute()` must be **strictly deterministic** — no random seeds, no time-based values, no non-deterministic library calls. The orchestrator SHA256-hashes outputs to verify this.

### 3. Create `tests/features/<name>/test_feature.py`

```python
from features.<name>.feature import compute

def test_compute_callable():
    assert callable(compute)
```

Additional tests verifying output shape, column names, and value ranges are strongly encouraged.

### 4. Update `CHANGE_REQUEST.yaml`

Add the new feature name to `determinism_features`:

```yaml
determinism_features:
  - bandpower
  - <name>
```

---

## Schema Conventions

All JSON Schema files use **Draft 2020-12** (`"$schema": "https://json-schema.org/draft/2020-12/schema"`).

Validation is performed via `jsonschema.Draft202012Validator`. Do not use older draft validators.

The four schemas and what they govern:

| Schema | Governs |
|---|---|
| `schemas/eeg8_v0.json` | EEG metadata files (`*.meta.json`) |
| `schemas/feature_meta.schema.json` | Feature module `meta.json` files |
| `schemas/feature_plan_v0.schema.json` | Output of `run_feature_planner.py` |
| `schemas/llm_data_assessment_v0.schema.json` | Output of `run_llm.py` |

---

## Hard Constraints (Never Violate)

These are architectural invariants enforced by code and prompts:

1. **No connectivity features** — coherence, PLV, PLI, WPLI, graph metrics are explicitly banned for wearable EEG. Do not add them.
2. **No ML training** — no classifiers, regressors, or neural networks. This pipeline produces features only.
3. **Determinism required** — all `compute()` functions must produce bit-identical output for identical input. Verified by SHA256.
4. **Schema validation before storage** — never write LLM output to disk without validating against the appropriate JSON schema.
5. **Fixed channel montage** — always exactly 8 channels: F3, F4, C3, C4, P3, P4, O1, O2. New EEG configurations require new schemas (e.g., `eeg16_v0`), not modifications to `eeg8_v0`.
6. **Conservative confidence** — if recording duration < 10s, confidence must be ≤ 0.2. If < 2s, confidence must be ≤ 0.1.
7. **LLM prompts are contracts** — `prompts/prompt_001.txt` and `prompts/prompt_002.txt` define hard rules for LLM behavior, not soft suggestions. Changes must be deliberate.

---

## Testing

**Run all tests:**
```bash
python -m pytest
```

**Run specific test file:**
```bash
python -m pytest tests/gates/test_determinism_hash.py
```

**Test configuration** (`pytest.ini`):
- `testpaths = tests/`
- `python_files = test_*.py`
- `python_functions = test_*`

**Test categories:**
- `tests/orchestrator/` — smoke tests for orchestrator
- `tests/gates/` — determinism hash utilities
- `tests/schemas/` — JSON schema validity and feature meta validation
- `tests/features/<name>/` — per-feature compute() tests

Every feature module **must** have at least one test file at `tests/features/<name>/test_feature.py`.

---

## Environment Setup

**Required environment variables** (for LLM stages):
```bash
export GEMINI_API_KEY=your-key-here
export GEMINI_MODEL=gemini-2.0-flash   # optional, this is the default
```

Without `GEMINI_API_KEY`, `run_llm.py` will fail and `run_feature_planner.py` will fall back to the deterministic plan.

**Dependencies** (install manually or via requirements file):
```
pandas
numpy
scipy
jsonschema
google-genai
PyYAML
pytest
```

**Generate mock data** (if `data/recording_060s.csv` is missing):
```bash
python generate_mock_eeg.py
```
Uses fixed seed 42 — output is reproducible.

---

## File Output Conventions

| Script | Output location | Files |
|---|---|---|
| `run.py` | `runs/run_<timestamp>/` | `checks.json`, `data_summary.json` |
| `run_llm.py` | same run dir | `llm_data_assessment.json` |
| `run_feature_planner.py` | same run dir | `feature_plan.json` |
| `extract_features.py` | same run dir | `features.csv`, `feature_report.json` |
| `tools/nw_orch.py` | `artifacts/run_<timestamp>/` | `report.json` |
| `tools/feature_determinism.py` | path specified by `--out` | `feature_determinism.json` |

`artifacts/` and `runs/` are gitignored. Do not commit pipeline output.

---

## Coding Conventions

- Use `from __future__ import annotations` at the top of every Python file
- Use `@dataclass` for structured intermediate data (see `run.py`'s `Checks` class)
- Snake_case for all functions, variables, and filenames
- Exit with meaningful codes: `0` (OK), `1`–`4` (specific failure modes, see orchestrator)
- Validate JSON before writing to disk; never silently accept malformed LLM output
- Prefer explicit error messages over silent failures
- Keep logic self-documenting; comments only where non-obvious
- No external HTTP calls except via google-genai library

---

## CHANGE_REQUEST.yaml

This file drives the orchestrator. It specifies:
- `id` / `title` / `intent` — change metadata
- `acceptance` — human-readable acceptance criteria
- `test_commands` — commands for the test stage
- `verify_commands` — commands for the verification stage
- `determinism_features` — list of feature names to check for determinism

Update this file when adding new features or changing pipeline behavior.

---

## Common Tasks Quick Reference

| Task | Command |
|---|---|
| Run full pipeline (orchestrator) | `python tools/nw_orch.py` |
| Validate EEG data | `python run.py --meta data/recording_001.meta.json --out-root runs` |
| LLM audit (requires API key) | `python run_llm.py` |
| Generate feature plan | `python run_feature_planner.py` |
| Extract features | `python extract_features.py` |
| Run tests | `python -m pytest` |
| Check feature determinism | `python tools/feature_determinism.py --meta features/bandpower/meta.json --csv data/recording_060s.csv --features bandpower --out /tmp/det.json` |
| Regenerate mock EEG | `python generate_mock_eeg.py` |
