# NeuroWeaver

NeuroWeaver is a decision-oriented pipeline for EEG.
It audits data quality, plans defensible features, and executes feature extraction
under strict, reproducible constraints.

This project is intentionally conservative.
It prioritizes justified ML design over raw performance.

## What it does
- Validates EEG inputs against a fixed 8-channel wearable schema
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

## Status
This is a research/engineering prototype intended for portfolio and experimentation.
