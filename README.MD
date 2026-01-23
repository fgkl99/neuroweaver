# NeuroWeaver

NeuroWeaver is a decision-oriented pipeline for EEG.
It audits data quality, plans defensible features, and executes feature extraction
under strict, reproducible constraints.

This project is intentionally conservative.
It prioritizes justified ML design over raw performance.

## What it does
- Validates EEG inputs against a fixed 8-channel schema
- Audits data quality using a strict LLM-based reviewer
- Plans feature extraction with guardrails and deterministic fallbacks
- Executes real feature extraction (RMS, bandpower, spectral entropy)

## What it does NOT do
- It does NOT train classifiers
- It does NOT optimize accuracy
- It does NOT use deep end-to-end models

## Assumed EEG format
- 8 fixed channels: F3, F4, C3, C4, P3, P4, O1, O2
- Sampling rate ~128 Hz
- CSV + JSON metadata

## Why this exists
Most ML pipelines start with model selection.
NeuroWeaver starts by asking whether a model choice is even justified.

This repository demonstrates how to:
- Prevent unjustified ML complexity
- Encode reviewer-level reasoning into code
- Build robust pipelines that survive LLM failures and quota limits

## Repository structure
- `schemas/` – JSON schemas defining hard constraints
- `prompts/` – LLM prompts treated as contracts
- `run.py` – data ingestion and validation
- `run_llm.py` – LLM data auditor
- `run_feature_planner.py` – feature planning with fallback
- `extract_features.py` – executable feature extraction
- `runs/` – fully reproducible example runs

## Data
All EEG recordings included in this repository are synthetic or mock data.
They are provided solely to demonstrate the pipeline and are not intended
to represent real physiological measurements.

## Extending the pipeline

NeuroWeaver is designed to be extended incrementally, without breaking its
decision-oriented philosophy.

### Adding new feature families
To add a new feature type (e.g. Hjorth parameters, fractal dimension):

1. Extend the feature schema (`schemas/feature_plan_v0.schema.json`)
   by adding the new feature family enum if needed.
2. Update the feature planner logic (LLM or deterministic fallback)
   to propose the new feature only when justified by data quality.
3. Implement the feature computation in `extract_features.py`,
   keeping the implementation deterministic and auditable.

New features should:
- Be explainable in physiological or signal-processing terms
- Fail gracefully when data is insufficient
- Avoid introducing hidden model assumptions

### Adding new agents
New agents (e.g. ModelStrategist, ValidationPlanner) should:
- Consume structured JSON outputs from previous steps
- Produce schema-validated JSON outputs
- Never silently override earlier decisions

Agents are expected to *refine* decisions, not to replace them.

### Supporting new EEG configurations
This repository intentionally supports a single EEG configuration (8-channel wearable).
Additional configurations should be introduced as new schemas
(e.g. `eeg16_v0`, `ear_eeg_v0`) rather than loosening existing constraints.

This preserves reproducibility and prevents scope creep.


## Status
This is a research/engineering prototype intended for experimentation.
